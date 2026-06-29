"""
Desktop Agent — Native OS Application Control

Interacts with the user's desktop applications (Excel, file explorer,
text editors, etc.) using PyAutoGUI for mouse/keyboard control
and direct file creation tools (openpyxl for Excel).

This agent has SMART ACTION RECIPES — it can figure out what to do
based on the task description and data from upstream agents, without
requiring pre-built action lists from the planner.
"""

import logging
import os
from pathlib import Path
from src.agents.base_agent import BaseAgent
from src.tools.desktop import DesktopTool
from src.tools.file_system import FileSystemTool
from src.tools.excel import ExcelTool
from src.config import Config

logger = logging.getLogger(__name__)


class DesktopAgent(BaseAgent):
    """
    Controls desktop applications via native mouse/keyboard input
    and direct file creation tools.

    Capabilities:
    - Create Excel spreadsheets with data from upstream agents
    - Open applications and type text
    - Save files to the workspace
    - Keyboard shortcuts and mouse control
    """

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute a desktop automation task.

        Smart routing: if no explicit actions are provided, the agent
        analyzes the task description and parameters to determine
        what recipe to use.
        """
        self.logger.info(f"Starting desktop task: {task_description}")

        desktop_tool = DesktopTool()
        fs_tool = FileSystemTool()
        excel_tool = ExcelTool()

        try:
            # ── Smart routing: determine what to do ──────────────────
            save_to_excel = parameters.get("save_to_excel", False)
            save_to_notepad = parameters.get("save_to_notepad", False)
            app = parameters.get("app", "")
            actions = parameters.get("actions", [])
            content = parameters.get("content", "")

            # Auto-detect from task description if flags aren't set
            desc_lower = task_description.lower()
            if not save_to_excel and ("excel" in desc_lower or "spreadsheet" in desc_lower):
                save_to_excel = True
            if not save_to_notepad and ("notepad" in desc_lower or "text file" in desc_lower):
                save_to_notepad = True

            # ── Recipe: Save to Excel ────────────────────────────────
            if save_to_excel:
                return self._excel_recipe(excel_tool, desktop_tool, dependency_data, parameters)

            # ── Recipe: Save to Notepad ──────────────────────────────
            if save_to_notepad:
                return self._notepad_recipe(desktop_tool, fs_tool, dependency_data, content, parameters)

            # ── Recipe: Open app + type content ──────────────────────
            if app and content:
                return self._open_and_type_recipe(desktop_tool, app, content)

            # ── Recipe: Open application ─────────────────────────────
            if app:
                return self._open_app_recipe(desktop_tool, app)

            # ── Recipe: Execute explicit action list ─────────────────
            if actions:
                return self._execute_actions(desktop_tool, fs_tool, actions)

            # ── Fallback: try to figure it out from dependency data ──
            if dependency_data:
                # If we have upstream data, save it to a text file
                return self._save_results_recipe(fs_tool, dependency_data, parameters)

            return {
                "success": True,
                "summary": "Desktop task completed (no specific actions needed).",
                "results": [],
            }

        except Exception as e:
            self.logger.error(f"Desktop task failed: {e}")
            return {
                "success": False,
                "summary": f"Desktop task failed: {e}",
                "results": [],
            }

    def _excel_recipe(
        self,
        excel_tool: ExcelTool,
        desktop_tool: DesktopTool,
        dependency_data: dict,
        parameters: dict,
    ) -> dict:
        """
        Create an Excel file from upstream agent data and open it.

        Extracts structured data (emails, phones, search results)
        from dependency data and creates a professional spreadsheet.
        """
        self.logger.info("Executing Excel recipe...")
        self._emit_log("📊 Creating Excel spreadsheet from research data...")

        headers = []
        rows = []

        # ── Prefer LLM-extracted structured data (from Research Agent) ───
        for dep_id, dep_result in dependency_data.items():
            if not isinstance(dep_result, dict):
                continue

            structured_data = dep_result.get("structured_data", [])
            structured_fields = dep_result.get("structured_fields", [])

            if structured_data and structured_fields:
                # Use the clean LLM-extracted data
                headers = ["#"] + [f.replace("_", " ").title() for f in structured_fields]
                if "source_url" not in structured_fields:
                    headers.append("Source URL")

                for i, item in enumerate(structured_data):
                    row = [str(i + 1)]
                    for field in structured_fields:
                        val = item.get(field, "")
                        row.append(str(val) if val is not None else "")
                    if "source_url" not in structured_fields:
                        row.append(item.get("source_url", ""))
                    rows.append(row)

                self._emit_log(
                    f"📊 Using LLM-structured data: {len(rows)} items with "
                    f"{len(structured_fields)} fields"
                )
                break  # Use the first dependency with structured data

        # ── Fallback: Extract data from upstream research tasks ──────────
        if not rows:
            for dep_id, dep_result in dependency_data.items():
                if not isinstance(dep_result, dict):
                    continue

                extracted = dep_result.get("extracted", {})
                data_items = dep_result.get("data", [])

                # Build rows from scraped sources with contact info
                emails = extracted.get("emails", [])
                phones = extracted.get("phones", [])

                if data_items:
                    # We have scraped page data
                    headers = ["#", "Source", "Title", "Snippet"]

                    # Add email and phone columns if we found any
                    if emails:
                        headers.append("Email")
                    if phones:
                        headers.append("Phone")

                    for i, item in enumerate(data_items):
                        row = [
                            str(i + 1),
                            item.get("source", item.get("url", "")),
                            item.get("title", ""),
                            (item.get("snippet", "") or item.get("content", ""))[:200],
                        ]
                        # Add email if available
                        if emails:
                            row.append(emails[i] if i < len(emails) else "")
                        if phones:
                            row.append(phones[i] if i < len(phones) else "")
                        rows.append(row)

                    # If we have more emails/phones than data items, add them
                    max_idx = len(data_items)
                    extra_count = max(len(emails), len(phones)) - max_idx
                    if extra_count > 0:
                        for j in range(extra_count):
                            idx = max_idx + j
                            row = [str(idx + 1), "", "", ""]
                            if emails:
                                row.append(emails[idx] if idx < len(emails) else "")
                            if phones:
                                row.append(phones[idx] if idx < len(phones) else "")
                            rows.append(row)

                elif emails or phones:
                    # Only contact info, no page data
                    headers = ["#"]
                    if emails:
                        headers.append("Email")
                    if phones:
                        headers.append("Phone")

                    max_len = max(len(emails), len(phones))
                    for i in range(max_len):
                        row = [str(i + 1)]
                        if emails:
                            row.append(emails[i] if i < len(emails) else "")
                        if phones:
                            row.append(phones[i] if i < len(phones) else "")
                        rows.append(row)

        # Fallback if no structured data found
        if not headers:
            headers = ["#", "Information"]
            for dep_id, dep_result in dependency_data.items():
                if isinstance(dep_result, dict):
                    summary = dep_result.get("summary", str(dep_result))
                    rows.append(["1", summary])

        if not rows:
            rows.append(["1", "No data collected from upstream tasks."])

        # ── Create the Excel file ────────────────────────────────────
        self._emit_log(f"📊 Preparing Excel file with {len(rows)} rows of data...")

        # Request approval before creating the file
        if not self.request_approval(f"Create Excel file with {len(rows)} rows of data"):
            return {
                "success": False,
                "summary": "User denied Excel file creation.",
            }

        try:
            return self._excel_recipe_visible(excel_tool, desktop_tool, dependency_data, parameters, headers, rows)
        except Exception as e:
            self.logger.error(f"Visible Excel entry failed: {e}. Falling back to background creation.")
            self._emit_log(f"⚠️ Visible Excel entry failed: {e}. Falling back to background creation.")
            return self._excel_recipe_background(excel_tool, headers, rows)

    def _excel_recipe_background(
        self,
        excel_tool: ExcelTool,
        headers: list[str],
        rows: list[list[str]],
    ) -> dict:
        """
        Background programmatic creation of Excel workbook as a fallback.
        """
        filepath = excel_tool.create_workbook(
            headers=headers,
            rows=rows,
            sheet_name="Agent Results",
        )
        excel_tool.open_in_excel(filepath)
        return {
            "success": True,
            "summary": f"Created Excel file programmatically in background: {filepath}",
            "filepath": filepath,
            "row_count": len(rows),
            "results": [{"action": "create_excel_background", "path": filepath, "rows": len(rows), "status": "done"}],
        }

    def _excel_recipe_visible(
        self,
        excel_tool: ExcelTool,
        desktop_tool: DesktopTool,
        dependency_data: dict,
        parameters: dict,
        headers: list[str],
        rows: list[list[str]],
    ) -> dict:
        """
        Create an Excel file visibly by launching Excel and typing the data cell-by-cell.
        """
        import time
        import pyautogui
        
        self.logger.info("Executing visible Excel GUI typist recipe...")
        self._emit_log("📊 Launching Excel visibly for live entry...")
        
        old_failsafe = True
        try:
            old_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = True  # Force fail-safe active for user safety
        except Exception:
            pass
            
        start_row_idx = 0
        total_rows = len(rows)
        headers_typed = False
        
        try:
            while True:
                try:
                    if not headers_typed:
                        # 1. Launch Excel
                        desktop_tool.open_application("excel")
                        time.sleep(6)  # Wait for Excel startup
                        
                        # 2. Excel standard behavior: on opening blank spreadsheet, 
                        # we need to press Enter or Esc to start a blank workbook, 
                        # or press Ctrl+N to ensure a blank sheet is created.
                        desktop_tool.press("esc")
                        time.sleep(0.5)
                        desktop_tool.hotkey("ctrl", "n")
                        time.sleep(1.5)
                        
                        # Let's focus Excel window title
                        focus_success = False
                        for title in ["Excel", "Book", "Spreadsheet", "Microsoft Excel"]:
                            if desktop_tool.press("alt"): # bypass alt key block
                                time.sleep(0.2)
                            
                            import ctypes
                            EnumWindows = ctypes.windll.user32.EnumWindows
                            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                            GetWindowText = ctypes.windll.user32.GetWindowTextW
                            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
                            IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                            SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
                            ShowWindow = ctypes.windll.user32.ShowWindow

                            found_hwnd = []
                            def foreach_window(hwnd, lParam):
                                if IsWindowVisible(hwnd):
                                    length = GetWindowTextLength(hwnd)
                                    buff = ctypes.create_unicode_buffer(length + 1)
                                    GetWindowText(hwnd, buff, length + 1)
                                    if title.lower() in buff.value.lower():
                                        found_hwnd.append(hwnd)
                                        return False
                                return True
                            
                            EnumWindows(EnumWindowsProc(foreach_window), 0)
                            if found_hwnd:
                                ShowWindow(found_hwnd[0], 9)
                                time.sleep(0.5)
                                SetForegroundWindow(found_hwnd[0])
                                time.sleep(0.5)
                                focus_success = True
                                break
                        
                        # 3. Enter A1
                        # Standard keyboard entry: Type column headers
                        self._emit_log("✍️ Typing Excel column headers live...")
                        for idx, header in enumerate(headers):
                            desktop_tool.type_text_unicode(header)
                            if idx < len(headers) - 1:
                                desktop_tool.press("tab")
                            else:
                                desktop_tool.press("enter")
                        time.sleep(0.5)
                        headers_typed = True
                    
                    # Type cells row-by-row
                    for r_idx in range(start_row_idx, total_rows):
                        row = rows[r_idx]
                        self._emit_log(f"✍️ Live typing row {r_idx + 1}/{total_rows}...")
                        for c_idx, cell in enumerate(row):
                            desktop_tool.type_text_unicode(str(cell) if cell is not None else "")
                            if c_idx < len(row) - 1:
                                desktop_tool.press("tab")
                            else:
                                desktop_tool.press("enter")
                        time.sleep(0.1) # brief pause between rows
                        start_row_idx = r_idx + 1
                        
                    # 4. Save workbook via Ctrl+S
                    self._emit_log("💾 Saving the typed Excel workbook...")
                    desktop_tool.hotkey("ctrl", "s")
                    time.sleep(3) # Wait for save dialog
                    
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"agent_results_{timestamp}.xlsx"
                    filepath = str(Config.WORKSPACE_ROOT / filename)
                    
                    # Type the destination path
                    desktop_tool.type_text_unicode(filepath)
                    time.sleep(0.5)
                    desktop_tool.press("enter")
                    time.sleep(4) # Wait for save to complete
                    
                    # Press enter again in case of confirmation
                    desktop_tool.press("enter")
                    time.sleep(1)
                    
                    self._emit_log(f"✅ Excel sheet saved live: {filepath}")
                    return {
                        "success": True,
                        "summary": f"Created Excel file visibly with {len(rows)} rows: {filepath}",
                        "filepath": filepath,
                        "row_count": len(rows),
                        "results": [{"action": "create_excel_visible", "path": filepath, "rows": len(rows), "status": "done"}],
                    }
                    
                except pyautogui.FailSafeException:
                    self._emit_log(f"⚠️ Live Excel entry was halted (row index: {start_row_idx}) because the mouse was moved!")
                    
                    # First offer the continue option
                    resume = self.request_approval(
                        f"Live Excel entry was interrupted. Would you like to CONTINUE/RESUME live typing "
                        f"from row {start_row_idx + 1}? (Please select the correct cell in Excel first, then click Yes)"
                    )
                    if resume:
                        self._emit_log(f"🔄 Resuming live GUI Excel entry from row {start_row_idx + 1} in 3 seconds...")
                        time.sleep(3)
                        continue
                    
                    # Next, offer the fallback option
                    fallback_bg = self.request_approval(
                        "Would you like to fallback to creating the Excel file in the background?"
                    )
                    if fallback_bg:
                        self._emit_log("📊 Falling back to background Excel writing...")
                        return self._excel_recipe_background(excel_tool, headers, rows)
                    
                    # Next, offer to restart from the beginning
                    restart = self.request_approval(
                        "Would you like to restart the Excel visible typing from the beginning?"
                    )
                    if restart:
                        self._emit_log("🔄 Restarting live GUI Excel entry from the beginning...")
                        start_row_idx = 0
                        headers_typed = False
                        continue
                    else:
                        self._emit_log("❌ Live Excel entry aborted by user.")
                        raise RuntimeError("Excel visible entry aborted by user.")
        finally:
            try:
                pyautogui.FAILSAFE = old_failsafe
            except Exception:
                pass

    def _notepad_recipe(
        self,
        desktop_tool: DesktopTool,
        fs_tool: FileSystemTool,
        dependency_data: dict,
        content: str,
        parameters: dict,
    ) -> dict:
        """
        Save results to a text file and open in Notepad.
        """
        self.logger.info("Executing Notepad recipe...")
        self._emit_log("📝 Preparing text file from research data...")

        # Build text content from dependency data
        if not content:
            lines = ["=" * 60, "AGENT OS — RESEARCH RESULTS", "=" * 60, ""]
            for dep_id, dep_result in dependency_data.items():
                if not isinstance(dep_result, dict):
                    continue

                lines.append(f"--- Task: {dep_id} ---")
                lines.append(f"Summary: {dep_result.get('summary', 'N/A')}")
                lines.append("")

                extracted = dep_result.get("extracted", {})
                if extracted.get("emails"):
                    lines.append("Emails Found:")
                    for email in extracted["emails"]:
                        lines.append(f"  • {email}")
                    lines.append("")

                if extracted.get("phones"):
                    lines.append("Phone Numbers Found:")
                    for phone in extracted["phones"]:
                        lines.append(f"  • {phone}")
                    lines.append("")

                data = dep_result.get("data", [])
                if data:
                    lines.append("Sources:")
                    for item in data:
                        title = item.get("title", "")
                        url = item.get("source", item.get("url", ""))
                        lines.append(f"  • {title}: {url}")
                    lines.append("")

            content = "\n".join(lines)

        # Save the file
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results_{timestamp}.txt"

        if not self.request_approval(f"Create text file: {filename}"):
            return {"success": False, "summary": "User denied text file creation."}

        filepath = fs_tool.write_file(filename, content)

        # Open in Notepad
        self._emit_log(f"📂 Opening in Notepad: {filepath}")
        desktop_tool.open_application("notepad")
        desktop_tool.wait(1)

        # Use os.startfile for reliability
        try:
            os.startfile(filepath)
        except Exception:
            pass

        return {
            "success": True,
            "summary": f"Created text file: {filepath}",
            "filepath": filepath,
            "results": [{"action": "create_text_file", "path": filepath, "status": "done"}],
        }

    def _open_and_type_recipe(self, desktop_tool: DesktopTool, app: str, content: str) -> dict:
        """Open an application and type content into it."""
        if not self.request_approval(f"Open {app} and type content"):
            return {"success": False, "summary": f"User denied opening {app}."}

        desktop_tool.open_application(app)
        desktop_tool.wait(2)
        desktop_tool.type_text_unicode(content)

        return {
            "success": True,
            "summary": f"Opened {app} and typed content.",
            "results": [{"action": "open_and_type", "app": app, "status": "done"}],
        }

    def _open_app_recipe(self, desktop_tool: DesktopTool, app: str) -> dict:
        """Open an application."""
        if not self.request_approval(f"Open application: {app}"):
            return {"success": False, "summary": f"User denied opening {app}."}

        desktop_tool.open_application(app)
        return {
            "success": True,
            "summary": f"Opened {app}.",
            "results": [{"action": "open_app", "app": app, "status": "done"}],
        }

    def _save_results_recipe(self, fs_tool: FileSystemTool, dependency_data: dict, parameters: dict) -> dict:
        """Save upstream results to a text file when no specific app is requested."""
        self.logger.info("Saving results to text file (fallback recipe)...")
        self._emit_log("💾 Saving results to file...")

        lines = ["AGENT RESULTS", "=" * 40, ""]
        for dep_id, dep_result in dependency_data.items():
            if isinstance(dep_result, dict):
                lines.append(f"Task {dep_id}: {dep_result.get('summary', 'Done')}")
        content = "\n".join(lines)

        from datetime import datetime
        filename = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = fs_tool.write_file(filename, content)

        return {
            "success": True,
            "summary": f"Results saved to: {filepath}",
            "filepath": filepath,
            "results": [{"action": "save_file", "path": filepath, "status": "done"}],
        }

    def _vision_verify_action(
        self,
        desktop_tool: DesktopTool,
        expected_text: str | None = None,
        timeout: float = 5.0,
    ) -> bool:
        """
        Take a screenshot after an action and verify the screen state
        changed as expected using OCR.

        Args:
            desktop_tool: The DesktopTool instance for screenshots.
            expected_text: If provided, verify this text appears on screen.
            timeout: Max seconds to wait for the expected state.

        Returns:
            True if verification passed, False otherwise.
        """
        import time
        from src.vision.ocr import OCR

        ocr = OCR()
        start = time.time()

        while time.time() - start < timeout:
            try:
                screen_text = ocr.extract_from_screen()
                if expected_text is None:
                    # No specific expectation — just confirm screen is readable
                    return len(screen_text) > 0
                if expected_text.lower() in screen_text.lower():
                    self.logger.info(
                        f"Vision verify: found expected text '{expected_text}'"
                    )
                    return True
            except Exception as e:
                self.logger.debug(f"Vision verify error: {e}")
            time.sleep(0.5)

        self.logger.warning(
            f"Vision verify: expected text '{expected_text}' not found within {timeout}s"
        )
        return False

    def _vision_find_and_click(
        self,
        desktop_tool: DesktopTool,
        target_text: str,
        timeout: float = 8.0,
    ) -> bool:
        """
        Use OCR to locate text on screen and click it.

        This is the core of the vision-guided control loop:
        1. Take a screenshot
        2. Run OCR to find the target text and its bounding box
        3. Click the center of the bounding box
        4. Verify the state changed

        Args:
            desktop_tool: DesktopTool instance.
            target_text: The text to search for on screen (e.g. a button label).
            timeout: Max seconds to search for the text.

        Returns:
            True if the text was found and clicked, False otherwise.
        """
        import time
        from src.vision.ocr import OCR

        ocr = OCR()
        start = time.time()
        self._emit_log(f"👁️ Vision: searching for '{target_text}' on screen...")

        while time.time() - start < timeout:
            try:
                coords = ocr.find_text_on_screen(target_text)
                if coords:
                    x, y = coords
                    self._emit_log(
                        f"👁️ Vision: found '{target_text}' at ({x}, {y}), clicking..."
                    )
                    desktop_tool.click(x, y)
                    time.sleep(0.5)
                    return True
            except Exception as e:
                self.logger.debug(f"Vision find error: {e}")
            time.sleep(0.5)

        self._emit_log(f"👁️ Vision: could not find '{target_text}' on screen")
        return False

    def _execute_actions(self, desktop_tool: DesktopTool, fs_tool: FileSystemTool, actions: list) -> dict:
        """Execute an explicit list of actions (legacy support)."""
        results = []

        for action in actions:
            action_type = action.get("type", "")
            self.logger.info(f"Desktop action: {action_type}")

            if action_type == "click":
                x = action.get("x", 0)
                y = action.get("y", 0)
                desktop_tool.click(x, y)
                results.append({"action": "click", "x": x, "y": y, "status": "done"})

            elif action_type == "type":
                text = action.get("text", "")
                desktop_tool.type_text_unicode(text)
                results.append({"action": "type", "status": "done"})

            elif action_type == "hotkey":
                keys = action.get("keys", [])
                desktop_tool.hotkey(*keys)
                results.append({"action": "hotkey", "keys": keys, "status": "done"})

            elif action_type == "screenshot":
                path = action.get("path", "desktop_screenshot.png")
                desktop_tool.screenshot(path)
                results.append({"action": "screenshot", "path": path, "status": "done"})

            elif action_type == "write_file":
                file_path = action.get("path", "")
                content = action.get("content", "")
                if self.request_approval(f"Write file: {file_path}"):
                    fs_tool.write_file(file_path, content)
                    results.append({"action": "write_file", "path": file_path, "status": "done"})
                else:
                    results.append({"action": "write_file", "path": file_path, "status": "denied"})

            elif action_type == "read_file":
                file_path = action.get("path", "")
                content = fs_tool.read_file(file_path)
                results.append({"action": "read_file", "path": file_path, "content": content[:2000]})

        return {
            "success": True,
            "summary": f"Executed {len(actions)} desktop actions.",
            "results": results,
        }
