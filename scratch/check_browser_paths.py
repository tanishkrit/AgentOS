import os
from pathlib import Path

possible_paths = [
    # Chrome paths
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Users\kritg\AppData\Local\Google\Chrome\Application\chrome.exe",
    # Brave paths
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Users\kritg\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
    # Edge paths
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

print("--- Checking browser paths ---")
found = []
for p in possible_paths:
    path = Path(p)
    if path.exists():
        print(f"FOUND: {p}")
        found.append(p)
    else:
        print(f"NOT FOUND: {p}")
        
if not found:
    print("No browser found in default paths.")
