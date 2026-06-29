"""
Blackboard — Shared Memory for Inter-Agent Communication

The Blackboard is a thread-safe key-value store that agents use to:
- Publish results and intermediate data
- Subscribe to data published by other agents
- Store and retrieve task results

This enables decoupled agent communication — agents don't need to
know about each other directly, they just read/write to the blackboard.
"""

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Blackboard:
    """
    Thread-safe shared memory for agent communication.

    Data is organized into:
    - Task results (keyed by task_id)
    - Named channels (keyed by agent_id + channel_name)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task_results: dict[str, dict] = {}
        self._channels: dict[str, dict] = {}

    # ── Task Results ─────────────────────────────────────────────────

    def publish_result(self, task_id: str, result: dict) -> None:
        """
        Store the result of a completed task.

        Args:
            task_id: Unique task identifier.
            result: Result data dict (should contain "success" and "summary").
        """
        with self._lock:
            self._task_results[task_id] = {
                **result,
                "_timestamp": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"Published result for task '{task_id}'")

    def get_result(self, task_id: str) -> dict | None:
        """Retrieve the result of a specific task."""
        with self._lock:
            return self._task_results.get(task_id)

    def get_all_results(self) -> dict[str, dict]:
        """Return all task results."""
        with self._lock:
            return dict(self._task_results)

    # ── Named Channels ───────────────────────────────────────────────

    def publish(self, agent_id: str, channel: str, data: dict) -> None:
        """
        Publish data to a named channel.

        Args:
            agent_id: ID of the publishing agent.
            channel: Channel name (e.g., "research_findings", "lead_list").
            data: Arbitrary data dict.
        """
        key = f"{agent_id}:{channel}"
        with self._lock:
            self._channels[key] = {
                **data,
                "_publisher": agent_id,
                "_channel": channel,
                "_timestamp": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"Agent '{agent_id}' published to channel '{channel}'")

    def subscribe(self, channel: str) -> dict | None:
        """
        Read the latest data from a named channel.

        Searches all publishers for the given channel name.

        Args:
            channel: Channel name to subscribe to.

        Returns:
            The data dict from the most recent publish, or None.
        """
        with self._lock:
            # Find all entries matching this channel name
            matches = [
                v for k, v in self._channels.items()
                if v.get("_channel") == channel
            ]
            if not matches:
                return None
            # Return the most recent
            return max(matches, key=lambda x: x.get("_timestamp", ""))

    def clear(self) -> None:
        """Clear all stored data."""
        with self._lock:
            self._task_results.clear()
            self._channels.clear()
        logger.info("Blackboard cleared.")
