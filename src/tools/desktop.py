"""
Desktop Tool — PyAutoGUI Wrapper for Native OS Control

Provides controlled access to mouse, keyboard, and screen capture.
Used by the DesktopAgent to interact with native applications
on the user's primary operating system.

Safety:
- PyAutoGUI's fail-safe is enabled (move mouse to corner to abort)
- All actions are logged
"""

import logging
import subprocess
import time
import pyautogui
import pyperclip
from pathlib import Path
from src.config import Config

logger = logging.getLogger(__name__)

# Enable PyAutoGUI fail-safe (move mouse to top-left corner to abort)
pyautogui.FAILSAFE = Config.FAILSAFE_ENABLED

# Add a small pause between actions for stability
pyautogui.PAUSE = 0.5


class DesktopTool:
    """
    Wrapper around PyAutoGUI for safe, logged desktop interactions.
    """

    def click(self, x: int, y: int, clicks: int = 1, button: str = "left") -> None:
        """
        Click at screen coordinates.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.
            clicks: Number of clicks (1=single, 2=double).
            button: Mouse button ("left", "right", "middle").
        """
        logger.info(f"Click ({button}) at ({x}, {y}), clicks={clicks}")
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)

    def move_to(self, x: int, y: int, duration: float = 0.3) -> None:
        """Move mouse cursor to coordinates smoothly."""
        logger.info(f"Move to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=duration)

    def type_text(self, text: str, interval: float = 0.02) -> None:
        """
        Type text character-by-character into the currently focused field.
        Only works with ASCII characters.

        Args:
            text: The string to type.
            interval: Delay between keystrokes in seconds.
        """
        logger.info(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")
        pyautogui.typewrite(text, interval=interval)

    def type_text_unicode(self, text: str) -> None:
        """
        Type any text (including unicode) by copying to clipboard and pasting.

        This works for all characters, unlike typewrite() which is ASCII-only.
        """
        logger.info(f"Typing unicode text: {text[:50]}{'...' if len(text) > 50 else ''}")
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)

    def hotkey(self, *keys: str) -> None:
        """
        Press a keyboard shortcut.

        Args:
            *keys: Key names (e.g., "ctrl", "s" for Ctrl+S).
        """
        logger.info(f"Hotkey: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)

    def press(self, key: str) -> None:
        """Press and release a single key."""
        logger.info(f"Press key: {key}")
        pyautogui.press(key)

    def screenshot(self, save_path: str = "screenshot.png") -> str:
        """
        Capture the full screen and save to file.

        Returns:
            The absolute path to the saved screenshot.
        """
        path = Path(save_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        img = pyautogui.screenshot()
        img.save(str(path))
        logger.info(f"Screenshot saved: {path}")
        return str(path)

    def get_screen_size(self) -> tuple[int, int]:
        """Return (width, height) of the primary display."""
        return pyautogui.size()

    def get_mouse_position(self) -> tuple[int, int]:
        """Return current (x, y) of the mouse cursor."""
        return pyautogui.position()

    def open_application(self, app_name: str) -> None:
        """
        Open a desktop application by name using the OS start command.

        Works with user's installed software: Brave, Excel, Notepad, etc.

        Args:
            app_name: Application name or executable path.
        """
        logger.info(f"Opening application: {app_name}")

        # Common application aliases for Windows
        app_aliases = {
            "brave": "brave.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "excel": "excel.exe",
            "word": "winword.exe",
            "powerpoint": "powerpnt.exe",
            "ppt": "powerpnt.exe",
            "notepad": "notepad.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "vscode": "code.exe",
            "code": "code.exe",
        }

        executable = app_aliases.get(app_name.lower(), app_name)

        try:
            subprocess.Popen(
                ["start", "", executable],
                shell=True,
            )
            time.sleep(3)  # Wait for app to start
            logger.info(f"Application '{app_name}' launched.")
        except Exception as e:
            logger.error(f"Failed to open '{app_name}': {e}")
            raise

    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        """
        Scroll the mouse wheel.

        Args:
            clicks: Number of scroll increments (positive=up, negative=down).
            x, y: Optional position to scroll at.
        """
        logger.info(f"Scroll {clicks} clicks at ({x}, {y})")
        pyautogui.scroll(clicks, x=x, y=y)

    def wait(self, seconds: float) -> None:
        """Wait for the specified number of seconds."""
        logger.info(f"Waiting {seconds}s...")
        time.sleep(seconds)
