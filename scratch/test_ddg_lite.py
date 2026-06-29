import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

query = "sports turf in pune"
url = f"https://lite.duckduckgo.com/lite/"
data = {"q": query}

try:
    resp = requests.post(url, headers=headers, data=data, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Content Length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, "lxml")
    
    # Results in DDG Lite are in table rows.
    # Let's look for result links.
    links = soup.select(".result-link")
    print(f"Found {len(links)} links:")
    for idx, link in enumerate(links[:10]):
        print(f"  #{idx+1}: {link.get_text(strip=True)} | {link.get('href')}")
        
except Exception as e:
    print(f"Error: {e}")
