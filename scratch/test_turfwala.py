import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("Fetching Turfwala homepage...")
try:
    r = requests.get("https://turfwala.com/", headers=headers, timeout=10)
    print("Status:", r.status_code)
    
    soup = BeautifulSoup(r.text, "lxml")
    links = soup.find_all("a")
    pune_links = []
    for a in links:
        href = a.get("href", "")
        if "pune" in href.lower() or "city" in href.lower():
            pune_links.append((href, a.get_text(strip=True)))
            
    print(f"Found {len(pune_links)} potential Pune/city links:")
    for l, txt in set(pune_links):
        print(f"  Link: {l} | Text: {txt}")
        
except Exception as e:
    print("Error:", e)
