import subprocess
import time
import shutil
import pyautogui
import pyperclip
from pathlib import Path
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

workspace = Path(r"c:\Users\kritg\OneDrive\Desktop\Tanish\Promgrams\AI Agents\workspace")
dest_file = workspace / "temp_google_search_debug.html"
dest_folder = workspace / "temp_google_search_debug_files"

# Cleanup
if dest_file.exists():
    dest_file.unlink()
if dest_folder.exists():
    shutil.rmtree(dest_folder)

# Disable PyAutoGUI fail-safe for debugging
pyautogui.FAILSAFE = False

browser_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
browser_title = "Chrome"

query = "sports turf in pune contact number email"
query_url = f"https://www.google.com/search?q={quote_plus(query)}&num=20&hl=en"

artifact_dir = Path(r"C:\Users\kritg\.gemini\antigravity-ide\brain\c65b47e9-8c14-4978-992f-beb1a818f888")

print("1. Launching browser in a new window...")
subprocess.Popen([browser_path, "--new-window", query_url])
time.sleep(7)

print("2. Performing center click...")
try:
    width, height = pyautogui.size()
    pyautogui.click(width // 2, height // 2)
    time.sleep(0.5)
except Exception as e:
    print("Click failed:", e)

print("3. Doing alt bypass...")
try:
    pyautogui.press("alt")
    time.sleep(0.2)
except Exception as e:
    print("Alt failed:", e)

# Focus window
print("4. Focusing window...")
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
        title = buff.value
        if browser_title.lower() in title.lower():
            found_hwnd.append(hwnd)
            print("Matched title:", title)
            return False
    return True

EnumWindows(EnumWindowsProc(foreach_window), 0)
if found_hwnd:
    hwnd = found_hwnd[0]
    ShowWindow(hwnd, 9)
    time.sleep(0.5)
    SetForegroundWindow(hwnd)
    time.sleep(0.5)
    print("Focused successfully.")
else:
    print("Could not find window matching title:", browser_title)
print("5. Pressing Ctrl+S...")
pyautogui.hotkey("ctrl", "s")
time.sleep(3)

print("6. Copying & pasting path...")
pyperclip.copy(str(dest_file))
time.sleep(0.2)
pyautogui.hotkey("ctrl", "v")
time.sleep(0.5)
pyautogui.press("enter")

print("7. Waiting for save...")
time.sleep(5)
pyautogui.press("enter")
time.sleep(1.5)

print("8. Closing tab...")
pyautogui.hotkey("ctrl", "w")
time.sleep(0.8)

print("9. Checking if file exists...")
if dest_file.exists():
    print(f"Success! File saved, size: {dest_file.stat().st_size} bytes")
    text_content = dest_file.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(text_content, "lxml")
    h3s = soup.find_all("h3")
    print(f"Found {len(h3s)} h3 elements.")
else:
    print("Failure: File does not exist.")
