import os
"""Test the Composio API key against multiple endpoints to figure out what works."""
import requests
import json

KEY = os.environ.get("COMPOSIO_KEY", "")
HEADERS = {"x_api_key": KEY, "Content-Type": "application/json"}
HEADERS_BEARER = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# Try multiple base URLs and endpoints
test_endpoints = [
    # Most likely per docs.composio.dev
    ("GET", "https://backend.composio.dev/api/v3.1/toolkits", None, HEADERS_BEARER),
    ("GET", "https://backend.composio.dev/api/v3.1/toolkits?limit=5", None, HEADERS_BEARER),
    # Try x-api-key header variant
    ("GET", "https://backend.composio.dev/api/v3.1/toolkits?limit=5", None, HEADERS),
    # Try without version prefix
    ("GET", "https://backend.composio.dev/api/toolkits", None, HEADERS_BEARER),
    # Try api.composio.dev
    ("GET", "https://api.composio.dev/v3.1/toolkits?limit=5", None, HEADERS_BEARER),
    # Search for github
    ("GET", "https://backend.composio.dev/api/v3.1/toolkits?search=github&limit=3", None, HEADERS_BEARER),
    # Try a specific app — Stripe
    ("GET", "https://backend.composio.dev/api/v3.1/toolkits?search=stripe&limit=3", None, HEADERS_BEARER),
]

print("=" * 70)
print(f"TESTING COMPOSIO API KEY: {KEY[:8]}...")
print("=" * 70)

for method, url, body, headers in test_endpoints:
    print(f"\n>>> {method} {url}")
    print(f"    Headers: {list(headers.keys())}")
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        else:
            r = requests.post(url, headers=headers, json=body, timeout=15)
        print(f"    HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Show structure
            if isinstance(data, dict):
                print(f"    Keys: {list(data.keys())}")
                if "items" in data:
                    print(f"    Items count: {len(data['items'])}")
                    if data["items"]:
                        print(f"    First item keys: {list(data['items'][0].keys())}")
                        print(f"    First item sample:")
                        print(json.dumps(data["items"][0], indent=2)[:1500])
                elif "toolkits" in data:
                    print(f"    Toolkits count: {len(data['toolkits'])}")
                    if data["toolkits"]:
                        print(f"    First item sample:")
                        print(json.dumps(data["toolkits"][0], indent=2)[:1500])
                else:
                    print(json.dumps(data, indent=2)[:1500])
            else:
                print(f"    Response type: {type(data)}, length: {len(data) if hasattr(data, '__len__') else 'n/a'}")
                if isinstance(data, list) and data:
                    print(f"    First item:")
                    print(json.dumps(data[0], indent=2)[:1500])
        else:
            print(f"    Response: {r.text[:400]}")
    except Exception as e:
        print(f"    ERROR: {e}")
