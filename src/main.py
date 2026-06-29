"""
Autonomous Multi-Agent Desktop OS — Main Entry Point

This is the CLI interface for the system. The user provides a natural-language
goal, and the orchestrator decomposes it into tasks, spawns agents, and
coordinates execution on the user's primary operating system.

Usage:
    python -m src.main "Research 10 AI startups and create a summary report"
"""

import sys
import logging
from src.config import Config
from src.orchestrator.planner import Planner
from src.orchestrator.manager import AgentManager
from src.memory.blackboard import Blackboard
from src.memory.database import Database


def setup_logging() -> None:
    """Configure console logging."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner() -> None:
    """Print startup banner."""
    banner = r"""
    +------------------------------------------------------+
    |      Autonomous Multi-Agent Desktop OS               |
    |   ----------------------------------------------     |
    |   Describe your goal. AI handles the rest.          |
    +------------------------------------------------------+
    """
    try:
        print(banner)
    except Exception:
        print("Autonomous Multi-Agent Desktop OS started.")


def request_approval(action_description: str) -> bool:
    """
    Prompt the user for approval before executing a sensitive action.

    Args:
        action_description: Human-readable description of the pending action.

    Returns:
        True if the user approves, False otherwise.
    """
    print(f"\n[APPROVAL REQUIRED]")
    print(f"   Action: {action_description}")
    response = input("   Approve? (y/n): ").strip().lower()
    return response in ("y", "yes")


def main() -> None:
    """Main execution loop."""
    setup_logging()
    logger = logging.getLogger("main")

    # ── Validate configuration ───────────────────────────────────────
    Config.ensure_dirs()
    issues = Config.validate()
    for issue in issues:
        logger.warning(issue)

    print_banner()

    # ── Get user goal ────────────────────────────────────────────────
    if len(sys.argv) > 1:
        user_goal = " ".join(sys.argv[1:])
    else:
        user_goal = input("🎯 Enter your goal: ").strip()

    if not user_goal:
        print("❌ No goal provided. Exiting.")
        sys.exit(1)

    logger.info(f"Goal received: {user_goal}")

    # ── Initialize core systems ──────────────────────────────────────
    database = Database()
    blackboard = Blackboard()
    planner = Planner()
    agent_manager = AgentManager(blackboard=blackboard, database=database)

    # ── Phase 1: Planning (LLM API is used HERE only) ────────────────
    logger.info("📋 Phase 1: Analyzing goal and creating execution plan...")
    execution_plan = planner.decompose_goal(user_goal)

    if not execution_plan or not execution_plan.tasks:
        print("[FAIL] Failed to create an execution plan. Check your Ollama setup and try again.")
        sys.exit(1)

    print(f"\n[PLAN] Execution Plan: {execution_plan.summary}")
    print(f"   Tasks: {len(execution_plan.tasks)}")
    for i, task in enumerate(execution_plan.tasks, 1):
        print(f"   {i}. [{task.agent_type}] {task.description}")

    # ── Approval gate ────────────────────────────────────────────────
    if Config.REQUIRE_APPROVAL:
        if not request_approval("Execute the above plan?"):
            print("[REJECTED] Plan rejected by user. Exiting.")
            sys.exit(0)

    # ── Phase 2: Agent Creation & Execution ──────────────────────────
    logger.info("Phase 2: Spawning agents and executing tasks...")
    agent_manager.execute_plan(execution_plan)

    # ── Phase 3: Results ─────────────────────────────────────────────
    logger.info("Phase 3: Gathering results...")
    results = blackboard.get_all_results()

    print("\n" + "=" * 60)
    print("EXECUTION RESULTS")
    print("=" * 60)
    for task_id, result in results.items():
        status = "[OK]" if result.get("success") else "[ERROR]"
        print(f"  {status} {task_id}: {result.get('summary', 'No summary')}")
    print("=" * 60)

    logger.info("Done. All tasks completed.")


if __name__ == "__main__":
    main()
