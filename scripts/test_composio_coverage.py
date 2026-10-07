import os
"""Check which of our 100 apps are already in Composio's toolkit registry."""
import requests, json, time
from pathlib import Path

KEY = os.environ.get("COMPOSIO_KEY", "")
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BASE = "https://backend.composio.dev/api/v3.1/toolkits"

# Fetch ALL of Composio's toolkits (paginated)
all_toolkits = []
cursor = None
page = 0
while True:
    params = {"limit": 1000}
    if cursor:
        params["cursor"] = cursor
    r = requests.get(BASE, headers=HEADERS, params=params, timeout=30)
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text[:200]}")
        break
    data = r.json()
    items = data.get("items", [])
    all_toolkits.extend(items)
    page += 1
    print(f"Page {page}: got {len(items)} items (total so far: {len(all_toolkits)})")
    cursor = data.get("next_cursor")
    if not cursor or not items:
        break
    if page > 5:  # safety
        break

print(f"\nTotal Composio toolkits fetched: {len(all_toolkits)}")

# Build a name→toolkit lookup
composio_by_name = {t["name"].lower(): t for t in all_toolkits}
composio_by_slug = {t["slug"].lower(): t for t in all_toolkits}

# Check our 100 apps
our_apps = json.loads(Path("/home/z/my-project/data/apps.json").read_text())
matches = []
misses = []
for app in our_apps:
    name_lower = app["name"].lower()
    # Try direct match
    if name_lower in composio_by_name:
        matches.append((app, composio_by_name[name_lower]))
    else:
        # Try slug match
        # Generate candidate slug
        import re
        cand_slug = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")
        if cand_slug in composio_by_slug:
            matches.append((app, composio_by_slug[cand_slug]))
        else:
            # Try fuzzy: search API
            r = requests.get(BASE, headers=HEADERS, params={"search": app["name"], "limit": 1}, timeout=15)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items and items[0]["name"].lower() == name_lower:
                    matches.append((app, items[0]))
                    continue
            misses.append(app)

print(f"\nComposio coverage of our 100 apps: {len(matches)}/100 ({len(matches)}%)")
print(f"\nMatches:")
for app, t in matches:
    auth = t.get("auth_schemes", [])
    tools = t.get("meta", {}).get("tools_count", 0)
    print(f"  ✓ {app['name']:30} auth={auth}  tools={tools}")

print(f"\nMisses (apps NOT in Composio):")
for app in misses:
    print(f"  ✗ {app['name']:30} category={app['category']}")

# Save the Composio registry snapshot
Path("/home/z/my-project/data/composio_registry.json").write_text(
    json.dumps(all_toolkits, indent=2)
)
print(f"\nSaved Composio registry snapshot ({len(all_toolkits)} toolkits) to data/composio_registry.json")
