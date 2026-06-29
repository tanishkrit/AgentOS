import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

session = requests.Session()
session.headers.update(headers)

query = "turf in pune"
encoded_query = quote_plus(query)
search_url = f"https://www.google.com/search?q={encoded_query}&num=10&hl=en"

try:
    resp = session.get(search_url, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"HTML length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, "lxml")
    h3s = soup.find_all("h3")
    print(f"Found {len(h3s)} h3 elements.")
    for idx, h3 in enumerate(h3s[:5]):
        print(f"  h3 #{idx+1}: {h3.get_text(strip=True)}")
        
    links = soup.find_all("a")
    valid_links = 0
    for a in links:
        href = a.get("href", "")
        if "google.com" not in href and (href.startswith("http") or href.startswith("/url?q=")):
            valid_links += 1
            if valid_links <= 5:
                print(f"  Link #{valid_links}: {href[:60]} | Text: {a.get_text(strip=True)[:40]}")
    print(f"Found {valid_links} redirect/direct links.")
    
except Exception as e:
    print(f"Error: {e}")
