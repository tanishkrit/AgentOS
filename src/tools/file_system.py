"""
File System Tool — Safe File Operations

Provides controlled read/write access to the file system within
the configured workspace directory. Operations outside the workspace
are blocked for safety.
"""

import logging
from pathlib import Path
from src.config import Config

logger = logging.getLogger(__name__)


class FileSystemTool:
    """
    Safe file system operations restricted to the workspace root.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._root = (workspace_root or Config.WORKSPACE_ROOT).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, relative_path: str) -> Path:
        """
        Resolve a path and ensure it's within the workspace.

        Raises:
            PermissionError: If the resolved path escapes the workspace.
        """
        resolved = (self._root / relative_path).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise PermissionError(
                f"Path '{relative_path}' resolves outside the workspace: {resolved}"
            )
        return resolved

    def read_file(self, relative_path: str) -> str:
        """
        Read a text file from the workspace.

        Args:
            relative_path: Path relative to the workspace root.

        Returns:
            File contents as a string.
        """
        path = self._safe_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_text(encoding="utf-8")
        logger.info(f"Read file: {path} ({len(content)} chars)")
        return content

    def write_file(self, relative_path: str, content: str) -> str:
        """
        Write content to a file in the workspace.

        Creates parent directories if needed.

        Args:
            relative_path: Path relative to the workspace root.
            content: String content to write.

        Returns:
            Absolute path to the written file.
        """
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote file: {path} ({len(content)} chars)")
        return str(path)

    def list_files(self, relative_dir: str = ".", pattern: str = "*") -> list[str]:
        """
        List files in a workspace directory.

        Args:
            relative_dir: Directory relative to workspace root.
            pattern: Glob pattern to filter files.

        Returns:
            List of relative file paths.
        """
        dir_path = self._safe_path(relative_dir)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        files = []
        for p in dir_path.glob(pattern):
            if p.is_file():
                files.append(str(p.relative_to(self._root)))

        logger.info(f"Listed {len(files)} files in {dir_path}")
        return files

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists in the workspace."""
        try:
            path = self._safe_path(relative_path)
            return path.exists()
        except PermissionError:
            return False

    def create_directory(self, relative_path: str) -> str:
        """Create a directory in the workspace."""
        path = self._safe_path(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {path}")
        return str(path)

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file from the workspace.

        Returns:
            True if the file was deleted, False if it didn't exist.
        """
        path = self._safe_path(relative_path)
        if path.exists() and path.is_file():
            path.unlink()
            logger.info(f"Deleted file: {path}")
            return True
        return False
