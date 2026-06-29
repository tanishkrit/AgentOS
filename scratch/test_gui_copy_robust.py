import subprocess
import time
import pyautogui
import pyperclip
import ctypes
from pathlib import Path

# Disable PyAutoGUI fail-safe for debugging
pyautogui.FAILSAFE = False

# Robust clipboard wrappers
def safe_copy_text(text: str, retries: int = 5, delay: float = 0.1) -> bool:
    for i in range(retries):
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            time.sleep(delay)
    return False

def safe_paste_text(retries: int = 5, delay: float = 0.1) -> str:
    for i in range(retries):
        try:
            return pyperclip.paste()
        except Exception:
            time.sleep(delay)
    return ""

def focus_window_by_title(target_name: str) -> bool:
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
            title = buff.value
            if target_name.lower() in title.lower():
                found_hwnd.append(hwnd)
                print(f"Matched window: {title}")
                return False
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    
    if found_hwnd:
        hwnd = found_hwnd[0]
        ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
        SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    return False

browser_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
query_url = "https://www.google.com/search?q=sports+turf+in+pune+contact+number+email&num=20&hl=en"

print("1. Launching browser...")
subprocess.Popen([browser_path, "--new-window", query_url])
print("Waiting 8 seconds for page to load...")
time.sleep(8)

print("2. Focusing browser...")
focus_window_by_title("Chrome")
time.sleep(0.5)

# Click center of screen to focus browser content
try:
    width, height = pyautogui.size()
    pyautogui.click(width // 2, height // 2)
    time.sleep(0.5)
except Exception as e:
    print("Click error:", e)

# Clear clipboard safely
safe_copy_text("")

print("3. Pressing Ctrl+U to view source...")
pyautogui.hotkey("ctrl", "u")
print("Waiting 4 seconds for source tab...")
time.sleep(4)

print("4. Pressing Ctrl+A and Ctrl+C in source tab...")
pyautogui.hotkey("ctrl", "a")
time.sleep(0.5)
pyautogui.hotkey("ctrl", "c")
time.sleep(0.5)

print("5. Closing source tab (Ctrl+W)...")
pyautogui.hotkey("ctrl", "w")
time.sleep(1)

print("6. Closing search tab (Ctrl+W)...")
pyautogui.hotkey("ctrl", "w")
time.sleep(1)

html_content = safe_paste_text()
print(f"Clipboard content length: {len(html_content)} characters")
if len(html_content) > 100:
    print("SUCCESS! Clipboard contains page source starting with:")
    print(html_content[:300])
else:
    print("FAILED: Clipboard is empty or too short.")
