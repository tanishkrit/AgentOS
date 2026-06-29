"""
Browser Agent — Web Application Interaction

Drives a real browser (Brave, Chrome, etc.) via Playwright to interact
with web applications: clicking buttons, filling forms, navigating pages,
and extracting data from dynamic web content.
"""

import logging
from src.agents.base_agent import BaseAgent
from src.tools.browser import BrowserTool

logger = logging.getLogger(__name__)


class BrowserAgent(BaseAgent):
    """
    Interacts with web applications through a real browser instance.

    Capabilities:
    - Navigate to URLs
    - Click elements by selector or text
    - Fill form fields
    - Extract text and structured data from pages
    - Take screenshots for verification
    """

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute a browser interaction task.

        Expected parameters:
            - url (str): Target URL to navigate to
            - actions (list[dict]): Sequence of browser actions
              Each action: {"type": "click|type|screenshot|extract", ...}
        """
        self.logger.info(f"Starting browser task: {task_description}")

        url = parameters.get("url", "")
        actions = parameters.get("actions", [])
        browser_tool = BrowserTool()

        try:
            # Navigate to the target URL
            if url:
                self.logger.info(f"Navigating to: {url}")
                browser_tool.navigate(url)

            results = []

            # Execute each action in sequence
            for action in actions:
                action_type = action.get("type", "")
                self.logger.info(f"Executing action: {action_type}")

                if action_type == "click":
                    selector = action.get("selector", "")
                    browser_tool.click(selector)
                    results.append({"action": "click", "selector": selector, "status": "done"})

                elif action_type == "type":
                    selector = action.get("selector", "")
                    text = action.get("text", "")
                    browser_tool.type_text(selector, text)
                    results.append({"action": "type", "selector": selector, "status": "done"})

                elif action_type == "screenshot":
                    path = action.get("path", "screenshot.png")
                    browser_tool.screenshot(path)
                    results.append({"action": "screenshot", "path": path, "status": "done"})

                elif action_type == "extract":
                    selector = action.get("selector", "body")
                    content = browser_tool.extract_text(selector)
                    results.append({"action": "extract", "content": content[:2000]})

            return {
                "success": True,
                "summary": f"Executed {len(actions)} browser actions on {url}",
                "results": results,
            }

        except Exception as e:
            self.logger.error(f"Browser task failed: {e}")
            return {
                "success": False,
                "summary": f"Browser task failed: {e}",
                "results": [],
            }

        finally:
            browser_tool.close()
