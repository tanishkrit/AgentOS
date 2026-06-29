import sys
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.browser import BrowserTool
from src.config import Config

Config.LOG_LEVEL = "DEBUG"

print("Initializing browser tool...")
bt = BrowserTool()
try:
    print("Searching for 'artificial intelligence'...")
    results = bt.search("artificial intelligence")
    print(f"Found {len(results)} results:")
    for i, res in enumerate(results[:5]):
        print(f"\n[{i+1}] {res['title']}")
        print(f"    URL: {res['url']}")
        print(f"    Snippet: {res['snippet'][:100]}...")
finally:
    bt.close()
