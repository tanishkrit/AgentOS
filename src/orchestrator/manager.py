"""
Agent Manager — Lifecycle Management and Task Dispatch

Creates specialized agents dynamically based on task requirements,
assigns tasks from the execution plan, and coordinates their execution.
Agents are spawned and destroyed as needed — they are not permanent residents.

Now integrated with the EventBus to push real-time status updates
to the GUI frontend.
"""

import logging
import time
from src.orchestrator.planner import ExecutionPlan, Task
from src.memory.blackboard import Blackboard
from src.memory.database import Database
from src.events import EventBus
from src.agents.base_agent import BaseAgent
from src.agents.research_agent import ResearchAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.desktop_agent import DesktopAgent
from src.agents.email_agent import EmailAgent
from src.agents.coding_agent import CodingAgent
from src.agents.presentation_agent import PresentationAgent
from src.agents.verification_agent import VerificationAgent
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ── Agent Registry ───────────────────────────────────────────────────
# Maps agent_type strings (from the planner) to concrete agent classes.

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "browser": BrowserAgent,
    "desktop": DesktopAgent,
    "email": EmailAgent,
    "coding": CodingAgent,
    "presentation": PresentationAgent,
    "verification": VerificationAgent,
}


class AgentManager:
    """
    Manages the full lifecycle of agents: creation, task assignment,
    execution, and teardown.

    Emits events via the EventBus so the GUI can display real-time
    status updates.
    """

    def __init__(
        self,
        blackboard: Blackboard,
        database: Database,
        event_bus: EventBus | None = None,
    ) -> None:
        self._blackboard = blackboard
        self._database = database
        self._event_bus = event_bus or EventBus()
        self._active_agents: dict[str, BaseAgent] = {}

    def _emit_status(self, task_id: str, status: str, summary: str = "", result: dict = None) -> None:
        """Emit a task status change event to the GUI."""
        self._event_bus.emit("task_status", {
            "task_id": task_id,
            "status": status,
            "summary": summary,
            "result": result,
        })

    def _emit_log(self, agent_id: str, message: str) -> None:
        """Emit a log message event to the GUI."""
        self._event_bus.emit("log_message", {
            "agent_id": agent_id,
            "message": message,
        })

    def _spawn_agent(self, agent_type: str, task_id: str) -> BaseAgent:
        """
        Instantiate an agent of the given type.

        Args:
            agent_type: Key into AGENT_REGISTRY (e.g., "research", "browser").
            task_id: The task this agent is being created for (for logging).

        Returns:
            An initialized BaseAgent subclass instance.

        Raises:
            ValueError: If agent_type is not registered.
        """
        agent_class = AGENT_REGISTRY.get(agent_type)
        if agent_class is None:
            logger.warning(
                f"Unknown agent type '{agent_type}' for task '{task_id}'. "
                f"Falling back to ResearchAgent."
            )
            agent_class = ResearchAgent

        agent = agent_class(
            agent_id=f"{agent_type}_{task_id}",
            blackboard=self._blackboard,
            event_bus=self._event_bus,
        )
        self._active_agents[task_id] = agent
        logger.info(f"Spawned {agent_class.__name__} for task '{task_id}'")
        self._emit_log(f"{agent_type}_{task_id}", f"Agent spawned for: {task_id}")
        return agent

    def _resolve_dependencies(self, task: Task) -> dict:
        """
        Gather outputs from dependency tasks via the blackboard.

        Returns a dict of {dependency_task_id: result_data}.
        """
        dep_data = {}
        for dep_id in task.depends_on:
            result = self._blackboard.get_result(dep_id)
            if result is not None:
                dep_data[dep_id] = result
            else:
                logger.warning(
                    f"Dependency '{dep_id}' for task '{task.id}' "
                    f"has no result on the blackboard."
                )
        return dep_data

    def execute_plan(self, plan: ExecutionPlan) -> dict:
        """
        Execute all tasks in the plan in dependency order, then
        verify the results and attempt targeted remediation if needed.

        Returns a summary dict with all results and created file paths.
        """
        logger.info(f"Executing plan: {plan.summary}")
        self._database.log_event("plan_start", {"goal": plan.goal, "task_count": len(plan.tasks)})
        self._current_plan = plan

        # ── Phase 1: Execute all planned tasks ───────────────────────
        all_filepaths = self._execute_all_tasks(plan)

        # Find the verification task in the plan
        verification_task = next((t for t in plan.tasks if t.agent_type == "verification"), None)

        # ── Phase 2: Verification + Remediation Loop ─────────────────
        max_remediation_cycles = 2
        for cycle in range(max_remediation_cycles):
            # Check if verification task completed successfully
            if verification_task and verification_task.status == "completed":
                self._emit_log(
                    "verification",
                    f"✅ Verification PASSED: {verification_task.result.get('summary', 'All good')}",
                )
                break

            # If verification task is not in the plan or has not run, fall back to self._verify_plan
            if not verification_task or not verification_task.result:
                verification_result = self._verify_plan(plan, all_filepaths)
            else:
                verification_result = verification_task.result

            if verification_result.get("verified", False):
                # If we verified it in the fallback, or if we got verified=True, make sure verification_task is completed
                if verification_task:
                    verification_task.status = "completed"
                    verification_task.result = verification_result
                break

            # Verification failed — attempt targeted remediation
            remediation = verification_result.get("remediation", [])
            if not remediation:
                self._emit_log(
                    "verification",
                    f"⚠️ Verification failed but no remediation suggested: "
                    f"{verification_result.get('assessment', 'Unknown')}",
                )
                break

            self._emit_log(
                "verification",
                f"🔄 Remediation cycle {cycle+1}/{max_remediation_cycles}: "
                f"re-running {len(remediation)} task(s)...",
            )

            # Re-run only the specific tasks identified by the verifier
            task_map = {t.id: t for t in plan.tasks}
            for fix in remediation:
                task_id = fix.get("task_id", "")
                task_to_fix = task_map.get(task_id)
                if not task_to_fix:
                    logger.warning(f"Remediation references unknown task: {task_id}")
                    continue

                # Apply adjusted parameters if provided
                adjusted = fix.get("adjusted_parameters", {})
                if adjusted:
                    task_to_fix.parameters.update(adjusted)

                self._emit_log(
                    "verification",
                    f"🔧 Re-running [{task_to_fix.agent_type}] "
                    f"{task_to_fix.description[:50]}: {fix.get('reason', '')}",
                )

                # Reset task status and re-execute
                task_to_fix.status = "pending"
                task_to_fix.result = {}
                self._execute_task(task_to_fix)

                # Collect any new file paths
                if task_to_fix.result and task_to_fix.result.get("filepath"):
                    filepath = task_to_fix.result["filepath"]
                    if filepath not in all_filepaths:
                        all_filepaths.append(filepath)

            # After re-running the modified tasks, we MUST re-run the verification task so it updates
            if verification_task:
                self._emit_log(
                    "verification",
                    "🔍 Re-running Verification Agent to check updated results...",
                )
                verification_task.status = "pending"
                verification_task.result = {}
                self._execute_task(verification_task)
        else:
            # Exhausted remediation cycles
            self._emit_log(
                "verification",
                f"⚠️ Remediation limit reached ({max_remediation_cycles} cycles). "
                f"Some tasks may still be incomplete.",
            )

        # ── Finalize ─────────────────────────────────────────────────
        completed_count = sum(1 for t in plan.tasks if t.status == "completed")
        self._database.log_event("plan_complete", {"completed": completed_count})
        logger.info(f"Plan execution complete. {completed_count}/{len(plan.tasks)} tasks finished.")

        workflow_results = {
            "completed_tasks": completed_count,
            "total_tasks": len(plan.tasks),
            "created_files": all_filepaths,
        }
        self._event_bus.emit("workflow_results", workflow_results)

        return workflow_results

    def _execute_all_tasks(self, plan: ExecutionPlan) -> list[str]:
        """
        Execute all tasks in dependency order.
        Returns a list of created file paths.
        """
        completed: set[str] = set()
        remaining = list(plan.tasks)
        all_filepaths = []

        while remaining:
            progress_made = False

            for task in list(remaining):
                if all(dep in completed for dep in task.depends_on):
                    self._execute_task(task)
                    completed.add(task.id)
                    remaining.remove(task)
                    progress_made = True

                    if task.result and task.result.get("filepath"):
                        all_filepaths.append(task.result["filepath"])

            if not progress_made:
                logger.error(
                    f"Deadlock detected: {len(remaining)} tasks have "
                    f"unresolvable dependencies. Force-executing."
                )
                for task in remaining:
                    self._execute_task(task)
                    completed.add(task.id)
                    if task.result and task.result.get("filepath"):
                        all_filepaths.append(task.result["filepath"])
                remaining.clear()

        return all_filepaths

    def _verify_plan(
        self, plan: ExecutionPlan, created_files: list[str],
    ) -> dict:
        """
        Run the VerificationAgent to check if the goal was achieved.
        """
        self._emit_log("verification", "🔍 Running verification check...")

        # Build task data for the verifier
        plan_tasks = []
        for t in plan.tasks:
            plan_tasks.append({
                "id": t.id,
                "agent_type": t.agent_type,
                "description": t.description,
                "status": t.status,
                "parameters": t.parameters,
                "result": t.result,
            })

        verifier = self._spawn_agent("verification", "verify")
        try:
            result = verifier.execute(
                task_description="Verify workflow completion",
                parameters={
                    "goal": plan.goal,
                    "plan_tasks": plan_tasks,
                    "created_files": created_files,
                },
                dependency_data={},
            )
            return result
        except Exception as e:
            logger.error(f"Verification agent failed: {e}")
            return {"verified": True, "assessment": f"Verification skipped: {e}"}
        finally:
            verifier.cleanup()
            self._active_agents.pop("verify", None)

    def _execute_task(self, task: Task) -> None:
        """Execute a single task by spawning the appropriate agent."""
        logger.info(f"▶ Executing task: [{task.agent_type}] {task.description}")
        self._database.log_event("task_start", {"task_id": task.id, "type": task.agent_type})

        # Emit "thinking" state — the agent is analyzing the task
        task.status = "thinking"
        self._emit_status(task.id, "thinking", f"Analyzing: {task.description}")
        time.sleep(0.8)  # Brief pause so the UI shows the thinking state

        # Emit "running" state
        task.status = "running"
        self._emit_status(task.id, "running", f"Executing: {task.description}")

        # Populate verification parameters dynamically
        if task.agent_type == "verification" and hasattr(self, "_current_plan") and self._current_plan:
            plan_tasks = []
            created_files = []
            for t in self._current_plan.tasks:
                if t.id == task.id:
                    continue
                plan_tasks.append({
                    "id": t.id,
                    "agent_type": t.agent_type,
                    "description": t.description,
                    "status": t.status,
                    "parameters": t.parameters,
                    "result": t.result,
                })
                if t.result and t.result.get("filepath"):
                    created_files.append(t.result["filepath"])
            
            task.parameters["goal"] = self._current_plan.goal
            task.parameters["plan_tasks"] = plan_tasks
            task.parameters["created_files"] = created_files

        agent = self._spawn_agent(task.agent_type, task.id)

        try:
            # Gather dependency outputs
            dep_data = self._resolve_dependencies(task)

            # Execute the agent's work
            result = agent.execute(
                task_description=task.description,
                parameters=task.parameters,
                dependency_data=dep_data,
            )

            # Check if the result indicates failure — try self-healing
            if not result.get("success", True):
                healed_result = self._try_self_heal(task, result, dep_data)
                if healed_result and healed_result.get("success"):
                    result = healed_result
                    logger.info(f"🩹 Self-healed task '{task.id}' successfully.")

            # Store result on the blackboard for downstream agents
            if result.get("success", True):
                task.status = "completed"
                task.result = result
                self._blackboard.publish_result(task.id, result)
                self._database.log_event("task_complete", {"task_id": task.id, "success": True})
                self._emit_status(task.id, "completed", result.get("summary", "Done"), result)
                logger.info(f"✅ Task '{task.id}' completed successfully.")
            else:
                task.status = "failed"
                task.result = result
                self._blackboard.publish_result(task.id, result)
                self._database.log_event("task_failed", {"task_id": task.id, "success": False, "error": result.get("error", "")})
                self._emit_status(task.id, "failed", result.get("summary", "Failed"), result)
                logger.error(f"❌ Task '{task.id}' failed.")

        except Exception as e:
            task.status = "failed"
            error_result = {"success": False, "error": str(e)}
            task.result = error_result
            self._blackboard.publish_result(task.id, error_result)
            self._database.log_event("task_failed", {"task_id": task.id, "error": str(e)})
            self._emit_status(task.id, "failed", str(e))
            logger.error(f"❌ Task '{task.id}' failed: {e}")

        finally:
            # Teardown agent
            agent.cleanup()
            self._active_agents.pop(task.id, None)

    def _try_self_heal(
        self, task: Task, failed_result: dict, dep_data: dict
    ) -> dict | None:
        """
        Attempt to self-heal a failed task using the LLM.

        Asks the LLM to diagnose the failure and suggest adjusted parameters.
        If it returns valid suggestions, re-runs the task with the new params.
        """
        llm = LLMClient.get_instance()
        if not llm.available:
            return None

        error_info = failed_result.get("error", failed_result.get("summary", "Unknown error"))
        logger.info(f"🩹 Attempting self-heal for task '{task.id}': {error_info}")
        self._emit_log(
            f"{task.agent_type}_{task.id}",
            f"🩹 Self-healing: analyzing failure...",
        )

        diagnosis = llm.generate_json(
            prompt=(
                f"A task failed in our automation system.\n"
                f"Task type: {task.agent_type}\n"
                f"Task description: {task.description}\n"
                f"Original parameters: {task.parameters}\n"
                f"Error: {error_info}\n\n"
                f"Should we retry this task? If yes, suggest adjusted parameters.\n"
                f"Return JSON: {{\"should_retry\": true/false, \"reason\": \"...\", "
                f"\"adjusted_parameters\": {{...}}}}"
            ),
            system=(
                "You are a diagnostic assistant for a desktop automation system. "
                "Analyze task failures and suggest fixes. Be concise."
            ),
            temperature=0.2,
            max_tokens=512,
            timeout=20,
        )

        if not diagnosis or not diagnosis.get("should_retry"):
            logger.info(f"Self-heal decided not to retry task '{task.id}'.")
            return None

        # Apply adjusted parameters and retry
        adjusted_params = diagnosis.get("adjusted_parameters", {})
        if adjusted_params:
            task.parameters.update(adjusted_params)

        self._emit_log(
            f"{task.agent_type}_{task.id}",
            f"🔄 Retrying with adjusted parameters: {diagnosis.get('reason', '')}",
        )

        # Spawn a fresh agent and retry
        retry_agent = self._spawn_agent(task.agent_type, f"{task.id}_retry")
        try:
            return retry_agent.execute(
                task_description=task.description,
                parameters=task.parameters,
                dependency_data=dep_data,
            )
        except Exception as e:
            logger.warning(f"Self-heal retry also failed: {e}")
            return None
        finally:
            retry_agent.cleanup()
            self._active_agents.pop(f"{task.id}_retry", None)
