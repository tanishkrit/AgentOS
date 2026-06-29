import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def test_engine(name, url, selector):
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"[{name}] Status: {resp.status_code}, Length: {len(resp.text)} bytes")
        soup = BeautifulSoup(resp.text, "lxml")
        elements = soup.select(selector)
        print(f"[{name}] Found {len(elements)} elements with selector '{selector}'")
        for idx, el in enumerate(elements[:5]):
            print(f"  #{idx+1}: {el.get_text(strip=True)[:60]} | {el.get('href')}")
    except Exception as e:
        print(f"[{name}] Error: {e}")

print("Testing Yahoo...")
test_engine("Yahoo", "https://search.yahoo.com/search?q=sports+turf+in+pune", "ol li h3 a")

print("\nTesting Ask...")
test_engine("Ask", "https://www.ask.com/web?q=sports+turf+in+pune", ".algo-title a")

print("\nTesting AOL...")
test_engine("AOL", "https://search.aol.com/aol/search?q=sports+turf+in+pune", "ol li h3 a")
