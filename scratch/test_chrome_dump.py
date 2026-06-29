import subprocess
from bs4 import BeautifulSoup

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Let's test searching Google via headless chrome
url = "https://www.google.com/search?q=sports+turf+in+pune"

try:
    print("Running Chrome --headless=new --dump-dom...")
    user_agent = "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    cmd = [chrome_path, "--headless=new", "--dump-dom", user_agent, url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, encoding="utf-8", errors="ignore")
    
    html = result.stdout
    print(f"Exit code: {result.returncode}")
    print(f"Output length: {len(html)} characters")
    
    soup = BeautifulSoup(html, "lxml")
    h3s = soup.find_all("h3")
    print(f"Found {len(h3s)} h3 elements:")
    for idx, h3 in enumerate(h3s[:10]):
        parent_a = h3.find_parent("a")
        href = parent_a.get("href", "") if parent_a else ""
        print(f"  h3 #{idx+1}: {h3.get_text(strip=True)} | Link: {href[:60]}")
        
except Exception as e:
    print(f"Error: {e}")
