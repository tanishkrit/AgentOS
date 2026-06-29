import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

url = "https://search.yahoo.com/search?q=sports+turf+in+pune"

try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}, Length: {len(resp.text)} bytes")
    
    soup = BeautifulSoup(resp.text, "lxml")
    
    # Dump first 30 links with full href and decoded destination
    from urllib.parse import urlparse, parse_qs, unquote
    import re
    
    count = 0
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "r.search.yahoo.com" in href:
            # Try to extract the RU= part
            match = re.search(r'/RU=([^/]+)', href)
            decoded_url = ""
            if match:
                decoded_url = unquote(match.group(1))
            
            # Filter out Yahoo-internal links
            if decoded_url and "yahoo.com" not in decoded_url and "yimg.com" not in decoded_url:
                count += 1
                print(f"  #{count} (Result):")
                print(f"    Text: {text[:50]}")
                print(f"    Original Link: {href[:100]}")
                print(f"    Decoded Dest: {decoded_url}")


            
    print(f"\nTotal external links: {count}")
except Exception as e:
    print(f"Error: {e}")
