"""
Coding Agent — Dynamic Script Generation and Execution

Uses the local LLM to write Python scripts based on task requirements,
presents them for user approval, and executes them in a sandboxed
subprocess. Fulfills the "Coding Agent" role from goal.md.

Safety:
- All generated code is shown to the user in GUI logs.
- Execution requires explicit user approval via the approval modal.
- Scripts run in a subprocess with a timeout to prevent runaway processes.
"""

import logging
import subprocess
import sys
import tempfile
import os
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.utils.llm_client import LLMClient
from src.config import Config

logger = logging.getLogger(__name__)

CODE_SYSTEM_PROMPT = """You are a Python script writer for a desktop automation system.

Write a COMPLETE, SELF-CONTAINED Python script that accomplishes the user's task.
The script should:
- Use only standard library modules or common packages (requests, openpyxl, json, csv, os, math, statistics).
- Print results clearly to stdout — this output will be captured and returned.
- Handle errors gracefully with try/except.
- NOT use input() or any interactive prompts.
- NOT install packages or modify system settings.
- Be well-commented and readable.

IMPORTANT: The script runs standalone in a separate subprocess. If input data is provided in the prompt, you MUST define/hardcode it directly in the script as a Python variable (e.g., `input_data = ...` or `search_results = ...`) so the script is completely self-contained. Do NOT refer to undefined variables or assume variables will be injected externally.

Output ONLY the Python code, wrapped in a single ```python code block.
No explanations before or after the code."""


class CodingAgent(BaseAgent):
    """
    Generates and executes Python scripts using the local LLM.

    Capabilities:
    - Write Python scripts for calculations, data processing, and file operations
    - Execute scripts in a sandboxed subprocess with timeout
    - Pass upstream dependency data as input to scripts
    - Return script output for downstream agents
    """

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute a coding task.

        1. Build a prompt from the task description and upstream data.
        2. Ask the LLM to generate a Python script.
        3. Show the script to the user and request approval.
        4. Execute the script and capture output.
        """
        self.logger.info(f"Starting coding task: {task_description}")
        self._emit_log(f"💻 Coding Agent starting: {task_description}")

        llm = LLMClient.get_instance()

        if not llm.available:
            self._emit_log("⚠️ LLM unavailable — cannot generate code.")
            return {
                "success": False,
                "summary": "LLM is unavailable. Cannot generate code.",
            }

        # ── Build the prompt with upstream data context ──────────────
        input_data_str = ""
        if dependency_data:
            # Serialize dependency data as a compact JSON string for the LLM
            import json
            dep_summary = {}
            for dep_id, dep_result in dependency_data.items():
                if isinstance(dep_result, dict):
                    dep_summary[dep_id] = {
                        "summary": dep_result.get("summary", ""),
                        "data": dep_result.get("data", [])[:10],  # Limit data size
                        "extracted": dep_result.get("extracted", {}),
                    }
            input_data_str = json.dumps(dep_summary, indent=2, default=str)

        task_prompt = f"Task: {task_description}"
        if parameters.get("task_description"):
            task_prompt += f"\nDetails: {parameters['task_description']}"
        if input_data_str:
            task_prompt += f"\n\nInput data from previous tasks:\n{input_data_str}"
        if parameters.get("input_data"):
            task_prompt += f"\n\nAdditional input:\n{parameters['input_data']}"

        # ── Generate the Python script ──────────────────────────────
        self._emit_log("🤖 Generating Python script with LLM...")

        raw_response = llm.generate(
            prompt=task_prompt,
            system=CODE_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=4096,
            timeout=60,
        )

        if not raw_response:
            self._emit_log("❌ LLM returned empty response.")
            return {
                "success": False,
                "summary": "LLM failed to generate code.",
            }

        # Extract Python code from the response
        code = self._extract_code(raw_response)
        if not code:
            self._emit_log("❌ Could not extract Python code from LLM response.")
            return {
                "success": False,
                "summary": "Failed to extract valid Python code from LLM response.",
                "raw_response": raw_response[:500],
            }

        # ── Show code to user and request approval ──────────────────
        code_preview = code[:500] + ("..." if len(code) > 500 else "")
        self._emit_log(f"📝 Generated script ({len(code)} chars):\n{code_preview}")

        if not self.request_approval(
            f"Execute generated Python script ({len(code)} chars)? "
            f"Preview: {code[:200]}..."
        ):
            return {
                "success": False,
                "summary": "User denied script execution.",
                "generated_code": code,
            }

        # ── Execute the script ──────────────────────────────────────
        self._emit_log("▶️ Running script...")
        result = self._run_script(code)

        if result["success"]:
            self._emit_log(f"✅ Script completed successfully:\n{result['output'][:500]}")
        else:
            self._emit_log(f"❌ Script failed:\n{result['error'][:500]}")

        return result

    def _extract_code(self, response: str) -> str:
        """Extract Python code from a markdown code block or raw response."""
        import re

        # Look for ```python ... ``` block
        match = re.search(r"```python\s*\n(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Look for generic ``` ... ``` block
        match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If the whole response looks like Python code, use it as-is
        lines = response.strip().split("\n")
        if any(line.strip().startswith(("import ", "def ", "print(", "from ")) for line in lines[:5]):
            return response.strip()

        return ""

    def _run_script(self, code: str) -> dict:
        """
        Execute a Python script in a subprocess and capture output.

        The script runs with a 30-second timeout and in the workspace directory.
        """
        workspace = Config.WORKSPACE_ROOT
        workspace.mkdir(parents=True, exist_ok=True)

        # Write the script to a temporary file
        script_path = workspace / "_coding_agent_script.py"
        try:
            script_path.write_text(code, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(workspace),
            )

            output = result.stdout.strip()
            error = result.stderr.strip()

            if result.returncode == 0:
                return {
                    "success": True,
                    "summary": f"Script executed successfully. Output: {output[:200]}",
                    "output": output,
                    "stderr": error,
                    "generated_code": code,
                }
            else:
                return {
                    "success": False,
                    "summary": f"Script failed with exit code {result.returncode}: {error[:200]}",
                    "output": output,
                    "error": error,
                    "generated_code": code,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "summary": "Script timed out after 30 seconds.",
                "error": "Timeout",
                "generated_code": code,
            }
        except Exception as e:
            return {
                "success": False,
                "summary": f"Script execution failed: {e}",
                "error": str(e),
                "generated_code": code,
            }
        finally:
            # Clean up the temporary script file
            try:
                script_path.unlink(missing_ok=True)
            except Exception:
                pass
