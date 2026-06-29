from bs4 import BeautifulSoup
from pathlib import Path

file_path = Path(r"c:\Users\kritg\OneDrive\Desktop\Tanish\Promgrams\AI Agents\scratch\google_response.html")

if not file_path.exists():
    print("File does not exist.")
else:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    print(f"File size: {len(text)} characters")
    soup = BeautifulSoup(text, "lxml")
    links = soup.find_all("a")
    print(f"Found {len(links)} links in total.")
    for idx, a in enumerate(links[:60]):
        href = a.get("href", "")
        text_content = a.get_text(strip=True).encode('ascii', errors='ignore').decode('ascii')
        print(f"Link #{idx+1}: {href[:80]} | Text: {text_content[:40]}")


