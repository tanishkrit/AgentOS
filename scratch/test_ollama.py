import requests
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
api_key = os.getenv("OLLAMA_API_KEY", "")
model = os.getenv("OLLAMA_MODEL", "llama3")

print("--- Ollama API Key Test ---")
print(f"OLLAMA_BASE_URL: {base_url}")
print(f"OLLAMA_MODEL: {model}")
print(f"OLLAMA_API_KEY: {api_key[:10]}...{api_key[-10:] if len(api_key) > 10 else ''}")

# 1. Test tags/availability
print("\n[Test 1] Checking /api/tags endpoint...")
headers = {}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

try:
    resp = requests.get(f"{base_url.rstrip('/')}/api/tags", headers=headers, timeout=10)
    print(f"Response Status: {resp.status_code}")
    try:
        print(f"Response Body (truncated): {resp.text[:500]}")
    except Exception:
        print("Could not print response body.")
except Exception as e:
    print(f"Error connecting to tags endpoint: {e}")

# 2. Test generation/completion
print("\n[Test 2] Testing /api/generate endpoint (minimal prompt)...")
payload = {
    "model": model,
    "prompt": "Hi, reply with one word: 'Success'.",
    "stream": False,
    "options": {"num_predict": 10}
}
try:
    resp = requests.post(f"{base_url.rstrip('/')}/api/generate", json=payload, headers=headers, timeout=60)
    print(f"Response Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("Success! Ollama Response:")
        print(data.get("response"))
    else:
        print(f"Failed response body: {resp.text}")
except Exception as e:
    print(f"Error connecting to generate endpoint: {e}")
