"""
Event Bus — Centralized Event System for GUI↔Backend Communication

Provides a thread-safe publish/subscribe mechanism that allows the
orchestrator backend to push real-time updates to the GUI frontend.

Events:
- plan_created: Planner produced an execution plan
- task_status: A task changed state (pending → thinking → running → completed/failed)
- log_message: An agent emitted a log message
- approval_request: An agent needs user approval for a sensitive action
- approval_response: The user responded to an approval request
"""

import threading
import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)


class EventBus:
    """
    Thread-safe event bus for decoupled GUI↔Backend communication.

    Usage:
        bus = EventBus()
        bus.on("task_status", my_handler)
        bus.emit("task_status", {"task_id": "t1", "status": "running"})
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton — one event bus for the entire application."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers = defaultdict(list)
                cls._instance._approval_events = {}
                cls._instance._approval_responses = {}
            return cls._instance

    def on(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to '{event_type}': {handler.__name__}")

    def off(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def emit(self, event_type: str, data: dict | None = None) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event_type: The event category.
            data: Arbitrary event payload.
        """
        logger.debug(f"Event: {event_type} → {data}")
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(data or {})
            except Exception as e:
                logger.error(f"Event handler error [{event_type}]: {e}")

    # ── Approval Flow ────────────────────────────────────────────────

    def request_approval(self, request_id: str, description: str) -> bool:
        """
        Request approval from the GUI. Blocks until the user responds.

        Called by agents on a background thread.
        The GUI picks this up via an 'approval_request' event and
        responds via `respond_approval()`.

        Args:
            request_id: Unique ID for this approval request.
            description: Human-readable description of the action.

        Returns:
            True if approved, False if denied.
        """
        event = threading.Event()
        self._approval_events[request_id] = event

        # Notify the GUI
        self.emit("approval_request", {
            "request_id": request_id,
            "description": description,
        })

        # Block until GUI responds (timeout 5 minutes)
        event.wait(timeout=300)

        # Read the response
        approved = self._approval_responses.pop(request_id, False)
        self._approval_events.pop(request_id, None)
        return approved

    def respond_approval(self, request_id: str, approved: bool) -> None:
        """
        Called by the GUI to respond to an approval request.

        Unblocks the waiting agent thread.
        """
        self._approval_responses[request_id] = approved
        event = self._approval_events.get(request_id)
        if event:
            event.set()
        self.emit("approval_response", {
            "request_id": request_id,
            "approved": approved,
        })
