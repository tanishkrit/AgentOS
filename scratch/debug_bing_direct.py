import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

url = "https://www.bing.com/search?q=sports+turf+in+pune"

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Content Length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, "lxml")
    
    print("Searching for occurrences of 'pune':")
    import re
    for m in re.finditer(r'pune', resp.text, re.IGNORECASE):
        start = max(0, m.start() - 100)
        end = min(len(resp.text), m.end() + 100)
        print(f"Occurrence at {m.start()}:\n{resp.text[start:end]}\n" + "-"*40)


        
except Exception as e:
    print(f"Error: {e}")
