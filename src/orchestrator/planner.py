"""
Planner Module — Goal Decomposition via LLM (Ollama)

This is the ONLY module that calls the LLM API. It takes a user's
natural-language goal and produces a structured ExecutionPlan containing
ordered tasks, each tagged with the agent type that should handle it.

The LLM is used exclusively for understanding intent and breaking down
the goal. All actual execution is handled by deterministic tool wrappers.

Uses Ollama's local HTTP API — no cloud API keys required.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from src.config import Config
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────────────


@dataclass
class Task:
    """A single executable task within a plan."""

    id: str
    description: str
    agent_type: str  # e.g., "research", "browser", "desktop", "email"
    depends_on: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | failed
    result: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """The full decomposed plan produced by the Planner."""

    goal: str
    summary: str
    tasks: list[Task] = field(default_factory=list)


# ── Planner ──────────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are an AI task planner for a desktop automation system.

Given a user's goal, break it down into a list of concrete, executable tasks.

Each task must specify:
- "id": A unique short identifier (e.g., "task_1", "task_2")
- "description": What the task does (human-readable)
- "agent_type": One of: "research", "browser", "desktop", "email", "coding", "presentation"
- "depends_on": List of task IDs this task depends on (empty list if none)
- "parameters": Specific parameters needed for execution

Agent types and their capabilities:
- "research": Searches the web (queries Google & DuckDuckGo), visits URLs, scrapes page contents, and extracts structured lists/tables of items (such as names, phone numbers, emails, addresses) using a local LLM. Always use this agent to gather and compile contact or list information. Parameters: {"search_query": "...", "urls": [...]}
- "browser": Opens URLs in a real browser (Brave/Chrome). Parameters: {"url": "..."}
- "desktop": Controls desktop apps (Excel, Notepad, Word, etc.). If "save_to_excel" is true, it automatically reads the structured lists extracted by the "research" agent and writes them into an Excel spreadsheet. Parameters: {"app": "excel|notepad|word", "save_to_excel": true/false, "save_to_notepad": true/false, "content": "text to type"}
- "email": Drafts and sends emails via SMTP. Parameters: {"recipients": [...], "subject": "...", "template": "..."}
- "coding": Writes and executes Python scripts for custom API calls, file format conversions, or mathematical computations. Do NOT use this agent for web searching, contact scraping, or writing to Excel/text, as the "research" and "desktop" agents already handle these tasks.
- "presentation": Creates professional PowerPoint (.pptx) presentations with styled themes, layouts, and animations. Use this when the user wants a PPT, presentation, slide deck, or pitch deck. It takes research data from upstream tasks and generates a polished multi-slide deck. Parameters: {"raw_goal": "...", "theme": "charcoal_dark|deep_navy|midnight_violet|clean_light"}

IMPORTANT RULES:
1. If the user wants to search for lists of items (e.g. turfs, businesses, restaurants) and save them to Excel, create a simple 2-task workflow: a "research" task to find and extract the details, followed by a "desktop" task (with "save_to_excel": true) depending on it. Do NOT add a "coding" task.
2. If the user mentions "excel" or "spreadsheet" or "save", add a desktop task with "save_to_excel": true
3. If the user mentions "notepad" or "text file" or "note", add a desktop task with "save_to_notepad": true
4. If the user mentions a specific topic to research for the presentation/ppt (e.g. "create a presentation about AI Agents"), create a "research" task first to gather information, then a "presentation" task depending on it. If there is no specific topic to research (e.g., "create a ppt" or "create ppt using powerpoint"), create only the "presentation" task directly.
5. Research tasks should always include a "search_query" parameter
6. Desktop tasks that need data from research must list the research task in "depends_on"
7. Keep tasks small and focused — one clear action each


Respond ONLY with valid JSON in this format:
{
  "summary": "Brief one-line summary of the plan",
  "tasks": [
    {
      "id": "task_1",
      "description": "...",
      "agent_type": "...",
      "depends_on": [],
      "parameters": {}
    }
  ]
}
"""


class Planner:
    """
    Decomposes a user goal into an ExecutionPlan using the local Ollama LLM.

    Uses the shared LLMClient for all inference requests.
    Falls back to smart keyword-based planning when LLM is unavailable.
    """

    def __init__(self) -> None:
        self._llm = LLMClient.get_instance()

    def decompose_goal(self, goal: str) -> ExecutionPlan:
        """
        Analyze the user's goal and return a structured ExecutionPlan.

        If the LLM is unavailable, returns a smart fallback plan.
        """
        plan = None
        if not self._llm.available:
            plan = self._fallback_plan(goal)
        else:
            try:
                logger.info("Sending goal to Ollama for decomposition...")

                plan_data = self._llm.generate_json(
                    prompt=f"User goal: {goal}",
                    system=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=4096,
                    timeout=120,
                )

                if plan_data is None:
                    logger.warning("LLM returned no valid JSON. Using fallback.")
                    plan = self._fallback_plan(goal)
                else:
                    plan = self._parse_plan(goal, plan_data)

            except Exception as e:
                logger.error(f"Planning failed: {e}")
                plan = self._fallback_plan(goal)

        # Append verification task to the plan so it shows in the workflow
        if plan and plan.tasks:
            has_verification = any(t.agent_type == "verification" for t in plan.tasks)
            if not has_verification:
                verification_task = Task(
                    id="verification_task",
                    description="Verify if the user's goal was fully achieved",
                    agent_type="verification",
                    depends_on=[t.id for t in plan.tasks],
                    parameters={"goal": goal},
                )
                plan.tasks.append(verification_task)

        return plan

    def _parse_plan(self, goal: str, data: dict) -> ExecutionPlan:
        """Convert raw JSON dict into an ExecutionPlan."""
        tasks = []
        for t in data.get("tasks", []):
            tasks.append(
                Task(
                    id=t.get("id", f"task_{len(tasks) + 1}"),
                    description=t.get("description", "Unknown task"),
                    agent_type=t.get("agent_type", "research"),
                    depends_on=t.get("depends_on", []),
                    parameters=t.get("parameters", {}),
                )
            )

        if not tasks:
            logger.warning("LLM returned empty task list. Using fallback.")
            return self._fallback_plan(goal)

        return ExecutionPlan(
            goal=goal,
            summary=data.get("summary", "Execution plan"),
            tasks=tasks,
        )

    def _fallback_plan(self, goal: str) -> ExecutionPlan:
        """
        Generate a smart multi-task plan when the LLM is unavailable.

        Analyzes the goal text to determine what tasks are needed.
        """
        logger.warning("Using fallback plan (no LLM decomposition).")

        goal_lower = goal.lower()
        tasks = []

        # ── Detect if research/search is needed ──────────────────────
        needs_research = any(
            kw in goal_lower
            for kw in [
                "research", "search", "find", "look up", "get info",
                "collect", "gather", "scrape", "list", "discover",
                "about", "what", "who", "where", "best", "top",
            ]
        )

        # ── Detect if Excel output is needed ─────────────────────────
        needs_excel = any(
            kw in goal_lower
            for kw in ["excel", "spreadsheet", "xlsx", "save in excel", "save to excel"]
        )

        # ── Detect if Notepad/text output is needed ──────────────────
        needs_notepad = any(
            kw in goal_lower
            for kw in ["notepad", "text file", "save as text", "write to file", "note"]
        )

        # ── Detect if presentation is needed ─────────────────────────
        needs_presentation = any(
            kw in goal_lower
            for kw in [
                "ppt", "powerpoint", "presentation", "slide",
                "pitch deck", "slide deck", "slidedeck",
            ]
        )

        # ── Detect if email is needed ────────────────────────────────
        needs_email = any(
            kw in goal_lower
            for kw in ["email", "send", "mail", "outreach"]
        )

        # ── Build search query from goal ─────────────────────────────
        # Strip common filler words to extract the search essence
        search_query = goal
        for filler in [
            "create a presentation about", "create a presentation on",
            "create presentation about", "create presentation on",
            "create a ppt about", "create a ppt on",
            "create ppt about", "create ppt on",
            "create a powerpoint about", "create a powerpoint on",
            "create powerpoint about", "create powerpoint on",
            "research about", "research on", "research", 
            "search for", "search",
            "find me", "find", "look up", "get info on", "get info about",
            "collect", "gather", "and save in excel", "and save to excel",
            "save in excel", "save to excel", "and create a",
            "and give", "give me", "their", "there",
            "create a presentation", "create a ppt", "make a ppt",
            "make a presentation", "create a powerpoint",
            "create ppt", "create powerpoint", "make ppt", "make presentation",
            "using powerpoint", "using ppt",
            "and create", "create", "make",
        ]:
            search_query = search_query.lower().replace(filler, "").strip()

        # If presentation is requested, research is needed only if there is a specific topic
        if needs_presentation:
            if search_query:
                needs_research = True
            else:
                needs_research = False

        # Always add a research task if any research-like keywords are found
        if (needs_research and search_query) or (not needs_presentation and not (needs_email and not needs_excel and not needs_notepad)):
            tasks.append(
                Task(
                    id="task_1",
                    description=f"Search the web and gather information: {search_query if search_query else goal}",
                    agent_type="research",
                    parameters={
                        "search_query": search_query if search_query else goal,
                        "raw_goal": goal,
                    },
                )
            )

        # Add Presentation output task
        if needs_presentation:
            tasks.append(
                Task(
                    id=f"task_{len(tasks) + 1}",
                    description=f"Create a professional PowerPoint presentation",
                    agent_type="presentation",
                    depends_on=["task_1"] if (tasks and needs_research) else [],
                    parameters={
                        "raw_goal": goal,
                    },
                )
            )

        # Add Excel output task
        if needs_excel:
            tasks.append(
                Task(
                    id=f"task_{len(tasks) + 1}",
                    description=f"Save research results to an Excel spreadsheet",
                    agent_type="desktop",
                    depends_on=["task_1"] if tasks else [],
                    parameters={
                        "app": "excel",
                        "save_to_excel": True,
                        "raw_goal": goal,
                    },
                )
            )

        # Add Notepad output task
        if needs_notepad:
            tasks.append(
                Task(
                    id=f"task_{len(tasks) + 1}",
                    description=f"Save results to a text file in Notepad",
                    agent_type="desktop",
                    depends_on=["task_1"] if tasks else [],
                    parameters={
                        "app": "notepad",
                        "save_to_notepad": True,
                        "raw_goal": goal,
                    },
                )
            )

        # Add email task
        if needs_email:
            tasks.append(
                Task(
                    id=f"task_{len(tasks) + 1}",
                    description=f"Draft and send emails based on results",
                    agent_type="email",
                    depends_on=[tasks[-1].id] if tasks else [],
                    parameters={"raw_goal": goal},
                )
            )

        # If no specific output detected, just do research
        if not tasks:
            tasks.append(
                Task(
                    id="task_1",
                    description=goal,
                    agent_type="research",
                    parameters={"search_query": goal, "raw_goal": goal},
                )
            )

        return ExecutionPlan(
            goal=goal,
            summary=f"Plan for: {goal[:60]}{'...' if len(goal) > 60 else ''}",
            tasks=tasks,
        )
