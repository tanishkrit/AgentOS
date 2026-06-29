import webbrowser
import time
import pyautogui
import pyperclip
import ctypes

pyautogui.FAILSAFE = False

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
        ShowWindow(hwnd, 9)
        time.sleep(0.5)
        SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    return False

query_url = "https://www.google.com/search?q=sports+turf+in+pune+contact+number+email&num=20&hl=en"

print("1. Opening URL via webbrowser...")
webbrowser.open(query_url)
print("Waiting 8 seconds for page to load...")
time.sleep(8)

print("2. Focusing browser...")
# Focus Chrome or Brave
focused = False
for browser in ["Chrome", "Brave", "Edge"]:
    if focus_window_by_title(browser):
        focused = True
        break
        
if not focused:
    print("Could not focus browser.")
else:
    # Click center of screen to focus browser content
    try:
        width, height = pyautogui.size()
        pyautogui.click(width // 2, height // 2)
        time.sleep(0.5)
    except Exception as e:
        print("Click error:", e)

    pyperclip.copy("")
    
    print("3. Opening source (Ctrl+U)...")
    pyautogui.hotkey("ctrl", "u")
    time.sleep(4)
    
    print("4. Copying (Ctrl+A -> Ctrl+C)...")
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.5)
    
    print("5. Closing tabs (Ctrl+W)...")
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.8)
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.8)
    
    html = safe_paste_text()
    print(f"HTML copied length: {len(html)}")
    if len(html) > 1000:
        print("SUCCESS! Page source retrieved.")
        if "recaptcha" in html.lower() or "captcha" in html.lower():
            print("WARNING: CAPTCHA is still shown!")
        else:
            print("No CAPTCHA detected in source.")
    else:
        print("FAILED: Clipboard is empty.")
