import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.browser import BrowserTool

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

print("Initializing BrowserTool...")
tool = BrowserTool()

query = "sports turf in pune contact number email"
print(f"Running GUI search for: '{query}'...")
results = tool._google_search_gui(query)

print(f"Search completed! Found {len(results)} results:")
for idx, r in enumerate(results[:5]):
    print(f"  #{idx+1}: {r['title']} -> {r['url']}")
