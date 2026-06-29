import subprocess
import time
import pyautogui
import pyperclip
import ctypes
import shutil
from pathlib import Path

# Setup paths
workspace = Path(r"c:\Users\kritg\OneDrive\Desktop\Tanish\Promgrams\AI Agents\workspace")
workspace.mkdir(parents=True, exist_ok=True)
dest_file = workspace / "search_test.html"

# Center mouse to prevent fail-safe
try:
    width, height = pyautogui.size()
    pyautogui.FAILSAFE = False
    pyautogui.moveTo(width // 2, height // 2)
    print(f"Moved mouse to center of screen: ({width // 2}, {height // 2})")
except Exception as e:
    print(f"Error centering mouse: {e}")

# Delete if already exists
if dest_file.exists():
    dest_file.unlink()
dest_folder = workspace / "search_test_files"
if dest_folder.exists():
    try:
        shutil.rmtree(dest_folder)
        print("Deleted existing search_test_files folder.")
    except Exception as e:
        print(f"Error deleting search_test_files folder: {e}")

# ctypes definitions for window management
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
                return False  # Stop enumeration
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

# Choose Chrome
browser_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
query_url = "https://www.google.com/search?q=sports+turf+in+pune+contact+number+email&num=20&hl=en"

print("--- Launching Browser directly with query URL ---")
subprocess.Popen([browser_path, query_url])
print("Waiting 8 seconds for page to load...")
time.sleep(8)

# Try focusing the window
print("--- Activating and Focusing Browser ---")
try:
    pyautogui.press("alt")
    time.sleep(0.2)
except Exception:
    pass

focus_window_by_title("Chrome")
time.sleep(1)

print("--- Saving Page ---")
pyautogui.hotkey("ctrl", "s")
time.sleep(4)  # Wait for save dialog

# Type destination file path
save_path = str(dest_file)
print(f"Typing save path: {save_path}")
pyperclip.copy(save_path)
time.sleep(0.2)
pyautogui.hotkey("ctrl", "v")
time.sleep(0.5)
pyautogui.press("enter")

# Wait for download to finish
print("Waiting for page to save...")
time.sleep(8)

# Press enter again in case of file overwrite dialog
pyautogui.press("enter")
time.sleep(2)

# Close the tab (Ctrl+W) to leave the user's browser clean
print("Closing search tab...")
pyautogui.hotkey("ctrl", "w")
time.sleep(1)

# Verify if file was created
if dest_file.exists():
    print(f"SUCCESS: File saved! Size: {dest_file.stat().st_size} bytes")
else:
    print("FAILED: File was not saved. Check if save dialog failed or path was incorrect.")
