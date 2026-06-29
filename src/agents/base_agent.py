"""
Base Agent — Abstract Foundation for All Specialized Agents

Every agent inherits from BaseAgent, which provides:
- Access to the shared Blackboard for inter-agent communication
- A standard execute() interface
- Logging and cleanup hooks
- Human-in-the-loop approval via the EventBus (GUI modal) or console fallback
"""

import logging
import uuid
from abc import ABC, abstractmethod
from src.memory.blackboard import Blackboard
from src.events import EventBus
from src.config import Config

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Subclasses must implement the `execute()` method to perform
    their specialized work.
    """

    def __init__(
        self,
        agent_id: str,
        blackboard: Blackboard,
        event_bus: EventBus | None = None,
    ) -> None:
        """
        Args:
            agent_id: Unique identifier for this agent instance.
            blackboard: Shared memory object for cross-agent communication.
            event_bus: Optional event bus for GUI communication.
        """
        self.agent_id = agent_id
        self.blackboard = blackboard
        self._event_bus = event_bus or EventBus()
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self.logger.info(f"Agent '{agent_id}' initialized.")

    @abstractmethod
    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute the agent's primary work.

        Args:
            task_description: Human-readable description of what to do.
            parameters: Task-specific parameters from the planner.
            dependency_data: Outputs from upstream dependency tasks.

        Returns:
            A result dict with at least {"success": bool, "summary": str}.
        """
        ...

    def request_approval(self, action_description: str) -> bool:
        """
        Ask the user for approval before performing a sensitive action.

        If REQUIRE_APPROVAL is disabled in config, auto-approves.

        When connected to the GUI, sends an approval request via the
        EventBus and blocks until the user responds via the modal.
        Falls back to console input if no GUI is available.
        """
        if not Config.REQUIRE_APPROVAL:
            self.logger.info(f"Auto-approved (REQUIRE_APPROVAL=false): {action_description}")
            return True

        # Generate a unique request ID that includes the task ID
        # so the frontend can associate it with a node
        request_id = f"{self.agent_id}_{uuid.uuid4().hex[:8]}"

        self.logger.info(f"Requesting approval: {action_description}")
        self._emit_log(f"⚠️ Awaiting approval: {action_description}")

        try:
            # Use the EventBus approval flow (blocks until GUI responds)
            approved = self._event_bus.request_approval(request_id, action_description)
        except Exception:
            # Fallback to console if EventBus fails
            print(f"\n⚠️  AGENT '{self.agent_id}' REQUESTS APPROVAL ⚠️")
            print(f"   Action: {action_description}")
            response = input("   Approve? (y/n): ").strip().lower()
            approved = response in ("y", "yes")

        if approved:
            self.logger.info(f"User approved: {action_description}")
            self._emit_log(f"✅ Approved: {action_description}")
        else:
            self.logger.warning(f"User denied: {action_description}")
            self._emit_log(f"❌ Denied: {action_description}")

        return approved

    def _emit_log(self, message: str) -> None:
        """Push a log message to the GUI via the event bus."""
        self._event_bus.emit("log_message", {
            "agent_id": self.agent_id,
            "message": message,
            "level": "agent",
        })

    def publish(self, key: str, data: dict) -> None:
        """Publish intermediate data to the blackboard."""
        self.blackboard.publish(self.agent_id, key, data)

    def subscribe(self, key: str) -> dict | None:
        """Read data published by another agent from the blackboard."""
        return self.blackboard.subscribe(key)

    def cleanup(self) -> None:
        """
        Called after task execution. Subclasses can override this
        to release resources (close browsers, disconnect, etc.).
        """
        self.logger.info(f"Agent '{self.agent_id}' cleaned up.")
