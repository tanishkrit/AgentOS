import pyautogui
from pathlib import Path

artifact_dir = Path(r"C:\Users\kritg\.gemini\antigravity-ide\brain\c65b47e9-8c14-4978-992f-beb1a818f888")
screenshot_path = artifact_dir / "desktop_state.png"

print("Capturing screen...")
img = pyautogui.screenshot()
img.save(str(screenshot_path))
print(f"Screenshot saved to: {screenshot_path}")
