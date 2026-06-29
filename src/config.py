"""
Configuration module for the Autonomous Multi-Agent Desktop OS.

Loads settings from environment variables (.env file) and provides
a centralized Config object used across all modules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Config:
    """Centralized configuration for the entire system."""

    # ── LLM (Ollama — Planning Only) ─────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")

    # ── Browser ──────────────────────────────────────────────────────
    BROWSER_EXECUTABLE_PATH: str = os.getenv("BROWSER_EXECUTABLE_PATH", "")

    # ── Workspace ────────────────────────────────────────────────────
    WORKSPACE_ROOT: Path = Path(
        os.getenv("WORKSPACE_ROOT", str(_PROJECT_ROOT / "workspace"))
    ).resolve()

    # ── Safety ───────────────────────────────────────────────────────
    REQUIRE_APPROVAL: bool = os.getenv("REQUIRE_APPROVAL", "true").lower() == "true"
    FAILSAFE_ENABLED: bool = os.getenv("FAILSAFE_ENABLED", "true").lower() == "true"

    # ── Logging ──────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Paths ────────────────────────────────────────────────────────
    PROJECT_ROOT: Path = _PROJECT_ROOT
    DATABASE_PATH: Path = _PROJECT_ROOT / "data" / "agent_os.db"
    MEMORY_DIR: Path = _PROJECT_ROOT / "data" / "memory"

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of configuration warnings/errors."""
        issues = []
        if not cls.OLLAMA_BASE_URL:
            issues.append(
                "OLLAMA_BASE_URL is not set. Planning features will use "
                "fallback mode. Set your Ollama URL in .env."
            )
        if cls.BROWSER_EXECUTABLE_PATH and not Path(cls.BROWSER_EXECUTABLE_PATH).exists():
            issues.append(
                f"BROWSER_EXECUTABLE_PATH points to '{cls.BROWSER_EXECUTABLE_PATH}' "
                "which does not exist."
            )
        return issues

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required directories if they don't exist."""
        cls.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def update_llm_config(
        cls,
        model: str | None = None,
        base_url: str | None = None,
        persist: bool = True,
    ) -> None:
        """
        Update LLM configuration at runtime and optionally persist to .env.

        Args:
            model: New Ollama model name (e.g. 'qwen2.5:14b').
            base_url: New Ollama base URL (e.g. 'http://localhost:11434').
            persist: If True, write the changes to the .env file.
        """
        if model is not None:
            cls.OLLAMA_MODEL = model
        if base_url is not None:
            cls.OLLAMA_BASE_URL = base_url.rstrip("/")

        if persist:
            cls._persist_env({
                "OLLAMA_MODEL": cls.OLLAMA_MODEL,
                "OLLAMA_BASE_URL": cls.OLLAMA_BASE_URL,
            })

    @classmethod
    def _persist_env(cls, updates: dict[str, str]) -> None:
        """
        Update specific keys in the .env file, preserving other content.

        Reads the current .env, replaces matching KEY=value lines, and
        writes back. Keys not found are appended at the end.
        """
        env_path = cls.PROJECT_ROOT / ".env"
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

        remaining = dict(updates)
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Match KEY=... lines (skip comments and blanks)
            if stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in remaining:
                    new_lines.append(f"{key}={remaining.pop(key)}\n")
                    continue
            new_lines.append(line if line.endswith("\n") else line + "\n")

        # Append any keys that were not found in the file
        for key, value in remaining.items():
            new_lines.append(f"{key}={value}\n")

        env_path.write_text("".join(new_lines), encoding="utf-8")
