"""
GUI Module — PyWebView Desktop Application

Creates a native desktop window using PyWebView that loads the HTML/CSS/JS
frontend and exposes a Python API for the frontend to call.

This is the main entry point for the GUI application:
    python -m src.gui

Architecture:
    ┌─────────────────────────┐
    │   PyWebView Window      │
    │  ┌───────────────────┐  │
    │  │ React UI (Vite)   │  │
    │  │                   │◄─┼── evaluate_js() pushes updates
    │  │                   │──┼── pywebview.api.* calls Python
    │  └───────────────────┘  │
    │           ▲              │
    │           │              │
    │  ┌───────┴───────────┐  │
    │  │ PythonAPI class   │  │
    │  │  submit_goal()    │  │
    │  │  approve_plan()   │  │
    │  │  respond_approval │  │
    │  └───────────────────┘  │
    └─────────────────────────┘
             ▼
    ┌─────────────────────────┐
    │ Orchestrator (backend)  │
    │  Planner → Manager →   │
    │  Agents → Tools         │
    └─────────────────────────┘
"""

import base64
import io
import json
import logging
import threading
import time
from pathlib import Path

import pyautogui
import webview
from PIL import Image

from src.config import Config
from src.events import EventBus
from src.orchestrator.planner import Planner
from src.orchestrator.manager import AgentManager
from src.memory.blackboard import Blackboard
from src.memory.database import Database

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────

UI_DIR = Path(__file__).resolve().parent / "ui"


# ═══════════════════════════════════════════════════════════════════
# Screen Streamer — background thread pushing live desktop frames
# ═══════════════════════════════════════════════════════════════════


class ScreenStreamer:
    """
    Captures the desktop at a low frame rate (~1-2 FPS), compresses
    each frame to JPEG, base64-encodes it, and calls a callback so
    the GUI can push it to the frontend.
    """

    def __init__(self, on_frame_callback, fps: float = 1.5) -> None:
        self._callback = on_frame_callback
        self._interval = 1.0 / fps
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("ScreenStreamer started.")

    def stop(self) -> None:
        self._running = False
        logger.info("ScreenStreamer stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def _capture_loop(self) -> None:
        """Continuously capture, compress, and emit frames."""
        while self._running:
            try:
                # Capture screenshot
                screenshot = pyautogui.screenshot()

                # Downscale to reduce bandwidth (max 960px wide)
                max_w = 960
                w, h = screenshot.size
                if w > max_w:
                    ratio = max_w / w
                    screenshot = screenshot.resize(
                        (max_w, int(h * ratio)), Image.LANCZOS
                    )

                # Compress to JPEG
                buf = io.BytesIO()
                screenshot.save(buf, format="JPEG", quality=55)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                # Get current mouse position
                mx, my = pyautogui.position()
                sw, sh = pyautogui.size()

                self._callback(b64, mx, my, sw, sh)
            except Exception as e:
                logger.debug(f"ScreenStreamer frame error: {e}")

            time.sleep(self._interval)


# ═══════════════════════════════════════════════════════════════════
# Python API exposed to the frontend via window.pywebview.api
# ═══════════════════════════════════════════════════════════════════

class PythonAPI:
    """
    API methods callable from the JS frontend.

    The frontend calls these via:
        window.pywebview.api.submit_goal("my goal", "manual")
    """

    def __init__(self) -> None:
        self._window = None  # Set after window is created
        self._event_bus = EventBus()
        self._planner = Planner()
        self._blackboard = Blackboard()
        self._database = Database()
        self._plan_approved_event = threading.Event()
        self._plan_approved = False
        self._current_plan = None

        # Screen streamer
        self._streamer = ScreenStreamer(on_frame_callback=self._on_screen_frame)

        # Subscribe to events from the orchestrator
        self._event_bus.on("task_status", self._on_task_status)
        self._event_bus.on("log_message", self._on_log_message)
        self._event_bus.on("approval_request", self._on_approval_request)
        self._event_bus.on("workflow_results", self._on_workflow_results)

    def set_window(self, window) -> None:
        """Set the pywebview window reference for JS evaluation."""
        self._window = window

    def _eval_js(self, js_code: str) -> None:
        """Safely evaluate JavaScript in the frontend."""
        if self._window:
            try:
                self._window.evaluate_js(js_code)
            except Exception as e:
                logger.error(f"JS eval failed: {e}")

    # ── Frontend-callable methods ─────────────────────────────────

    def submit_goal(self, goal: str, approval_mode: str) -> None:
        """
        Called by the frontend when the user submits a goal.

        Runs planning + execution on a background thread so the
        GUI remains responsive.
        """
        require_approval = approval_mode == "manual"
        Config.REQUIRE_APPROVAL = require_approval

        # Start live screen streaming
        self._streamer.start()

        thread = threading.Thread(
            target=self._run_workflow,
            args=(goal,),
            daemon=True,
        )
        thread.start()

    def approve_plan(self, approved: bool) -> None:
        """Called by the frontend when the user approves/rejects the plan."""
        self._plan_approved = approved
        self._plan_approved_event.set()

    def respond_approval(self, request_id: str, approved: bool) -> None:
        """Called by the frontend when the user responds to an action approval."""
        self._event_bus.respond_approval(request_id, approved)

    def toggle_screen_stream(self) -> None:
        """Called by the frontend to toggle the live screen stream on/off."""
        if self._streamer.is_running:
            self._streamer.stop()
        else:
            self._streamer.start()

    def get_llm_config(self) -> dict:
        """
        Return current LLM configuration for the Settings panel.

        Called by the frontend to populate the settings form.
        """
        from src.utils.llm_client import LLMClient
        llm = LLMClient.get_instance()
        return {
            "base_url": Config.OLLAMA_BASE_URL,
            "model": Config.OLLAMA_MODEL,
            "available": llm.available,
        }

    def save_llm_config(self, config_json: str) -> dict:
        """
        Save new LLM settings, persist to .env, and reconfigure the client.

        Args:
            config_json: JSON string with 'base_url' and/or 'model' keys.

        Returns:
            Status dict with 'success', 'message', 'available', and 'models'.
        """
        from src.utils.llm_client import LLMClient
        try:
            data = json.loads(config_json) if isinstance(config_json, str) else config_json
            new_model = data.get("model", "").strip()
            new_url = data.get("base_url", "").strip()

            Config.update_llm_config(
                model=new_model or None,
                base_url=new_url or None,
                persist=True,
            )

            llm = LLMClient.get_instance()
            llm.reconfigure()

            return {
                "success": True,
                "message": f"Saved. Model: {Config.OLLAMA_MODEL}, URL: {Config.OLLAMA_BASE_URL}",
                "available": llm.available,
            }
        except Exception as e:
            logger.error(f"Failed to save LLM config: {e}")
            return {
                "success": False,
                "message": str(e),
                "available": False,
            }

    def list_local_models(self) -> list:
        """
        Return a list of locally downloaded Ollama models.

        Called by the frontend to populate the model dropdown.
        """
        from src.utils.llm_client import LLMClient
        return LLMClient.list_local_models()

    # ── Background workflow execution ─────────────────────────────

    def _run_workflow(self, goal: str) -> None:
        """Full workflow: plan → approve → execute → report."""
        try:
            # Phase 1: Planning (LLM API call)
            self._emit_log("system", "Analyzing goal with AI planner...")
            plan = self._planner.decompose_goal(goal)

            if not plan or not plan.tasks:
                self._emit_log("error", "Failed to generate a plan. Check your Ollama setup.")
                return

            self._current_plan = plan

            # Send plan to frontend
            plan_data = {
                "summary": plan.summary,
                "tasks": [
                    {
                        "id": t.id,
                        "description": t.description,
                        "agent_type": t.agent_type,
                        "depends_on": t.depends_on,
                        "parameters": t.parameters,
                    }
                    for t in plan.tasks
                ],
            }
            self._eval_js(f"window.onPlanCreated({json.dumps(plan_data)})")

            # Phase 2: Wait for plan approval (if manual mode)
            if Config.REQUIRE_APPROVAL:
                self._emit_log("system", "Waiting for user to approve the workflow...")
                self._plan_approved_event.clear()
                self._plan_approved_event.wait(timeout=600)  # 10 min timeout

                if not self._plan_approved:
                    self._emit_log("warning", "Workflow was rejected or timed out.")
                    return

            # Phase 3: Execute
            self._emit_log("system", "Starting workflow execution...")
            manager = AgentManager(
                blackboard=self._blackboard,
                database=self._database,
                event_bus=self._event_bus,
            )
            workflow_results = manager.execute_plan(plan)

            # Phase 4: Report results
            completed = sum(1 for t in plan.tasks if t.status == "completed")
            failed = sum(1 for t in plan.tasks if t.status == "failed")
            total = len(plan.tasks)

            result_data = {
                "total": total,
                "completed": completed,
                "failed": failed,
                "created_files": workflow_results.get("created_files", []),
            }

            self._eval_js(
                f"window.onWorkflowComplete({json.dumps(result_data)})"
            )

            # Stop screen streaming after workflow completes
            self._streamer.stop()

        except Exception as e:
            logger.error(f"Workflow error: {e}", exc_info=True)
            self._emit_log("error", f"Workflow error: {str(e)}")
            self._streamer.stop()

    # ── Event handlers ────────────────────────────────────────────

    def _on_task_status(self, data: dict) -> None:
        """Forward task status changes to the frontend."""
        self._eval_js(f"window.onTaskStatus({json.dumps(data)})")

    def _on_log_message(self, data: dict) -> None:
        """Forward log messages to the frontend."""
        self._eval_js(f"window.onLogMessage({json.dumps(data)})")

    def _on_approval_request(self, data: dict) -> None:
        """Forward approval requests to the frontend."""
        self._eval_js(f"window.onApprovalRequest({json.dumps(data)})")

    def _on_workflow_results(self, data: dict) -> None:
        """Forward workflow results (created files, etc.) to the frontend."""
        self._eval_js(f"window.onWorkflowResults({json.dumps(data)})")

    def _on_screen_frame(
        self, b64_frame: str, mx: int, my: int, sw: int, sh: int
    ) -> None:
        """Push a live screen frame + cursor position to the frontend."""
        # Send as compact JSON — cursor coordinates are relative to screen size
        payload = json.dumps({
            "frame": b64_frame,
            "cx": mx, "cy": my,
            "sw": sw, "sh": sh,
        })
        self._eval_js(f"window.onScreenUpdate({payload})")

    def _emit_log(self, level: str, message: str) -> None:
        """Helper to push a log message to the frontend."""
        self._eval_js(
            f"window.onLogMessage({json.dumps({'agent_id': 'system', 'message': message, 'level': level})})"
        )


# ═══════════════════════════════════════════════════════════════════
# Application Launch
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    """Launch the AgentOS desktop application."""
    # Setup
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    Config.ensure_dirs()

    issues = Config.validate()
    for issue in issues:
        logger.warning(issue)

    # Create the API bridge
    api = PythonAPI()

    # Create the PyWebView window
    window = webview.create_window(
        title="AgentOS — Autonomous AI Workforce",
        url=str(UI_DIR / "index.html"),
        js_api=api,
        width=1400,
        height=900,
        min_size=(1000, 700),
        background_color="#0A0B0F",
        text_select=True,
    )

    api.set_window(window)

    logger.info("Launching AgentOS desktop application...")
    webview.start(debug=Config.LOG_LEVEL == "DEBUG")


if __name__ == "__main__":
    main()
