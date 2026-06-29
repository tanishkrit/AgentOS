"""
Verification Agent — Task Completion Validation

After all tasks in a workflow have executed, the VerificationAgent
inspects the results to determine whether the overall goal was
achieved.  If something is incomplete, it identifies the specific
agent / task that needs to re-run and produces a targeted remediation
plan — **not** a full re-execution of the entire workflow.

Flow:
    1. Receive the goal, the completed plan, and all task results.
    2. Use the local LLM to analyze whether the goal is fully met.
    3. If everything looks good → return verified = True.
    4. If something is missing → return verified = False with a
       remediation plan that lists only the specific task(s) to re-run
       and what needs to change.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.utils.llm_client import LLMClient
from src.config import Config

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# LLM Prompts
# ═════════════════════════════════════════════════════════════════════

VERIFICATION_SYSTEM = """You are a strict Quality Assurance inspector for an autonomous desktop automation system.

You will be given:
1. The user's original goal.
2. A list of tasks that were planned and executed.
3. The result of each task (success/failure, summary, created files).

Your job is to determine whether the user's goal has been FULLY achieved.

Return ONLY valid JSON in this exact format:
{
  "verified": true/false,
  "confidence": 0.0 to 1.0,
  "assessment": "Brief explanation of your assessment",
  "missing_items": ["list of specific things that are missing or incomplete"],
  "remediation": [
    {
      "task_id": "the ID of the task that needs to re-run (e.g. task_2)",
      "agent_type": "the type of agent to use (e.g. presentation, research)",
      "reason": "Why this task needs to re-run",
      "adjusted_parameters": {"key": "value"}
    }
  ]
}

RULES:
- Set "verified" to true ONLY if the goal is fully achieved.
- If a file was supposed to be created (e.g. .pptx, .xlsx, .docx) and the task reported success with a filepath, check that the summary confirms the file was created.
- If a task failed, the goal is NOT fully achieved.
- In "remediation", only list the SPECIFIC task(s) that need to re-run. Do NOT suggest re-running the entire workflow.
- If the goal asked for research + presentation, and research succeeded but presentation failed, only list the presentation task for remediation.
- "adjusted_parameters" should contain any parameter changes that might help the retry succeed.
- Be strict but fair: minor formatting issues don't warrant a failure.
- If all tasks succeeded and the outputs seem to match the goal, set verified=true.
"""


# ═════════════════════════════════════════════════════════════════════
# Verification Result
# ═════════════════════════════════════════════════════════════════════

@dataclass
class VerificationResult:
    """Result of a verification check."""
    verified: bool = False
    confidence: float = 0.0
    assessment: str = ""
    missing_items: list[str] = field(default_factory=list)
    remediation: list[dict] = field(default_factory=list)


# ═════════════════════════════════════════════════════════════════════
# Verification Agent
# ═════════════════════════════════════════════════════════════════════

class VerificationAgent(BaseAgent):
    """
    Validates whether a workflow's execution fully achieved the
    user's goal. Returns a detailed assessment and, if needed,
    a targeted remediation plan.
    """

    MAX_RETRIES = 2  # Maximum remediation cycles

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Run verification on the completed workflow.

        Expected parameters:
            - goal (str): The user's original goal.
            - plan_tasks (list[dict]): List of planned tasks with results.
            - created_files (list[str]): Paths to files created during execution.
        """
        self._emit_log("🔍 Verification Agent: Inspecting task results...")

        goal = parameters.get("goal", task_description)
        plan_tasks = parameters.get("plan_tasks", [])
        created_files = parameters.get("created_files", [])

        # Basic checks before LLM analysis
        result = self._run_basic_checks(plan_tasks, created_files)
        if result and not result.verified:
            self._emit_log(f"❌ Basic check failed: {result.assessment}")
            return self._to_dict(result)

        # LLM-powered deep analysis
        llm = LLMClient.get_instance()
        if llm.available:
            result = self._llm_verify(llm, goal, plan_tasks, created_files)
        else:
            # Without LLM, rely on basic checks only
            result = self._basic_verify(plan_tasks, created_files)

        if result.verified:
            self._emit_log(
                f"✅ Verification PASSED (confidence: {result.confidence:.0%}): "
                f"{result.assessment}"
            )
        else:
            self._emit_log(
                f"⚠️ Verification FAILED: {result.assessment}"
            )
            if result.missing_items:
                for item in result.missing_items:
                    self._emit_log(f"   • Missing: {item}")
            if result.remediation:
                for r in result.remediation:
                    self._emit_log(
                        f"   🔄 Remediation: re-run {r.get('agent_type', '?')} "
                        f"agent — {r.get('reason', 'unknown reason')}"
                    )

        return self._to_dict(result)

    def _run_basic_checks(
        self, plan_tasks: list[dict], created_files: list[str],
    ) -> VerificationResult | None:
        """Run fast sanity checks that don't need the LLM."""

        # Check for any failed tasks
        failed_tasks = [
            t for t in plan_tasks
            if t.get("status") == "failed"
            or (isinstance(t.get("result"), dict) and not t["result"].get("success", True))
        ]

        if failed_tasks:
            remediation = []
            missing = []
            for t in failed_tasks:
                error_msg = ""
                if isinstance(t.get("result"), dict):
                    error_msg = t["result"].get("error", t["result"].get("summary", ""))
                missing.append(f"Task '{t.get('description', t.get('id', '?'))[:50]}' failed: {error_msg}")
                remediation.append({
                    "task_id": t.get("id", "unknown"),
                    "agent_type": t.get("agent_type", "unknown"),
                    "reason": f"Task failed: {error_msg}",
                    "adjusted_parameters": t.get("parameters", {}),
                })

            return VerificationResult(
                verified=False,
                confidence=0.9,
                assessment=f"{len(failed_tasks)} task(s) failed during execution.",
                missing_items=missing,
                remediation=remediation,
            )

        # Check for created files that should exist
        for fpath in created_files:
            if fpath and not Path(fpath).exists():
                return VerificationResult(
                    verified=False,
                    confidence=0.95,
                    assessment=f"Expected output file does not exist: {fpath}",
                    missing_items=[f"File not found: {fpath}"],
                    remediation=[],
                )

        return None  # Basic checks passed, continue to LLM analysis

    def _basic_verify(
        self, plan_tasks: list[dict], created_files: list[str],
    ) -> VerificationResult:
        """Simple verification without LLM (checks task statuses only)."""
        all_succeeded = all(
            t.get("status") == "completed"
            or (isinstance(t.get("result"), dict) and t["result"].get("success", False))
            for t in plan_tasks
        )

        if all_succeeded:
            return VerificationResult(
                verified=True,
                confidence=0.7,  # Lower confidence without LLM
                assessment="All tasks completed successfully (basic check only).",
            )
        else:
            failed = [t for t in plan_tasks if t.get("status") != "completed"]
            return VerificationResult(
                verified=False,
                confidence=0.7,
                assessment=f"{len(failed)} task(s) did not complete.",
                missing_items=[
                    f"Task '{t.get('id', '?')}' ({t.get('agent_type', '?')}): {t.get('status', 'unknown')}"
                    for t in failed
                ],
            )

    def _llm_verify(
        self,
        llm: LLMClient,
        goal: str,
        plan_tasks: list[dict],
        created_files: list[str],
    ) -> VerificationResult:
        """Use the LLM to deeply analyze whether the goal was met."""

        # Build a summary of all task results
        task_summaries = []
        for t in plan_tasks:
            result = t.get("result", {})
            task_summaries.append({
                "id": t.get("id"),
                "agent_type": t.get("agent_type"),
                "description": t.get("description"),
                "status": t.get("status"),
                "success": result.get("success") if isinstance(result, dict) else None,
                "summary": result.get("summary", "") if isinstance(result, dict) else str(result),
                "filepath": result.get("filepath", "") if isinstance(result, dict) else "",
            })

        prompt = (
            f"User's original goal:\n\"\"\"\n{goal}\n\"\"\"\n\n"
            f"Tasks executed:\n{json.dumps(task_summaries, indent=2, default=str)}\n\n"
            f"Files created: {json.dumps(created_files, default=str)}\n\n"
            f"Analyze whether the goal has been fully achieved."
        )

        try:
            data = llm.generate_json(
                prompt=prompt,
                system=VERIFICATION_SYSTEM,
                temperature=0.2,
                max_tokens=1024,
                timeout=60,
            )

            if not data:
                return self._basic_verify(plan_tasks, created_files)

            return VerificationResult(
                verified=data.get("verified", False),
                confidence=float(data.get("confidence", 0.5)),
                assessment=data.get("assessment", "No assessment provided."),
                missing_items=data.get("missing_items", []),
                remediation=data.get("remediation", []),
            )

        except Exception as e:
            logger.warning(f"LLM verification failed: {e}")
            return self._basic_verify(plan_tasks, created_files)

    def _to_dict(self, result: VerificationResult) -> dict:
        """Convert VerificationResult to a dict for the orchestrator."""
        return {
            "success": result.verified,
            "verified": result.verified,
            "confidence": result.confidence,
            "summary": result.assessment,
            "assessment": result.assessment,
            "missing_items": result.missing_items,
            "remediation": result.remediation,
        }
