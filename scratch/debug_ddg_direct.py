import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

url = "https://html.duckduckgo.com/html/?q=sports+turf+in+pune"

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Content Length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select(".result__a")
    print(f"Found {len(links)} results:")
    for idx, link in enumerate(links[:5]):
        print(f"  #{idx+1}: {link.get_text(strip=True)} | {link.get('href')}")
        
    if "ddg" in resp.text.lower() and len(links) == 0:
        print("--- First 500 chars of HTML ---")
        print(resp.text[:500])
except Exception as e:
    print(f"Error: {e}")
