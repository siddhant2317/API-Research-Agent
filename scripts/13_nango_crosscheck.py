"""Cross-check our auth_methods against Nango's providers.yaml.
   Nango has 800+ curated provider configs with auth_mode field."""
import json, yaml, collections
from pathlib import Path

# Load Nango providers.yaml
with open("/tmp/nango/packages/providers/providers.yaml") as f:
    # providers.yaml is large; parse it
    content = f.read()

# Try yaml parsing — it may have multiple documents or be a single dict
try:
    providers = yaml.safe_load(content)
except yaml.YAMLError as e:
    print(f"YAML parse error: {e}")
    providers = None

if not providers:
    print("Could not parse providers.yaml")
    exit(1)

print(f"Nango providers.yaml loaded: {type(providers)}")
if isinstance(providers, dict):
    print(f"Top-level keys: {list(providers.keys())[:5]}")
    # The structure is usually {provider_slug: {auth: {...}, ...}}
    provider_list = providers
elif isinstance(providers, list):
    provider_list = {p.get("provider", ""): p for p in providers}
    print(f"Number of providers: {len(provider_list)}")

print(f"Total Nango providers: {len(provider_list)}")

# Build a name→auth_mode lookup
nango_by_name = {}
nango_by_slug = {}
for slug, config in provider_list.items():
    if not isinstance(config, dict):
        continue
    name = config.get("display_name", slug)
    # auth_mode is at top level, not nested
    auth_mode = config.get("auth_mode")
    nango_by_name[name.lower()] = {"slug": slug, "auth_mode": auth_mode, "config": config}
    nango_by_slug[slug.lower()] = {"slug": slug, "auth_mode": auth_mode, "config": config}

print(f"\nSample Nango entries (first 5):")
for i, (k, v) in enumerate(nango_by_name.items()):
    if i >= 5: break
    print(f"  {k}: auth_mode={v['auth_mode']}")

# Load our records
records = [json.loads(p.read_text()) for p in sorted(Path("/home/z/my-project/data/apps").glob("*.json"))]

# Cross-check
def norm_nango_auth(auth_mode):
    if not auth_mode:
        return None
    am = auth_mode.upper()
    if "OAUTH2" in am or "OAUTH" in am:
        return "oauth2"
    if "API_KEY" in am or "APIKEY" in am:
        return "api_key"
    if "BASIC" in am:
        return "basic"
    if "BEARER" in am:
        return "api_key"  # bearer tokens delivered via API key flow
    if "JWT" in am:
        return "jwt"
    if "NONE" in am or "NO_AUTH" in am:
        return "none"
    return am.lower()

def norm_our_auth(auths):
    if not auths:
        return set()
    norm_map = {"oauth": "oauth2", "s2s_oauth2": "oauth2", "client_credentials": "oauth2",
                "bearer_token": "api_key", "api-key": "api_key", "apikey": "api_key", "digest": "api_key"}
    return set(norm_map.get(a.lower(), a.lower()) for a in auths)

matches = []
mismatches = []
nango_only = []
our_only = []

for r in records:
    app_name = r["app_name"]
    app_slug = r["app_slug"]
    our_auth = r.get("auth_methods") or []
    
    # Try to find in Nango
    nango_match = None
    # Try exact name
    if app_name.lower() in nango_by_name:
        nango_match = nango_by_name[app_name.lower()]
    # Try slug variants
    else:
        for slug_key, nango_data in nango_by_slug.items():
            if app_slug.replace("-", "_") == slug_key or app_slug == slug_key.replace("_", "-"):
                nango_match = nango_data
                break
        # Try fuzzy name match
        if not nango_match:
            for nango_name_key, nango_data in nango_by_name.items():
                if app_name.lower() in nango_name_key or nango_name_key in app_name.lower():
                    # Make sure it's a real match, not substring
                    if len(app_name.lower()) >= 4 and len(nango_name_key) >= 4:
                        nango_match = nango_data
                        break
    
    if not nango_match:
        continue
    
    nango_auth_mode = nango_match["auth_mode"]
    nango_auth_norm = norm_nango_auth(nango_auth_mode)
    our_auth_norm = norm_our_auth(our_auth)
    
    if nango_auth_norm and nango_auth_norm in our_auth_norm:
        matches.append({
            "app": app_name,
            "our_auth": our_auth,
            "nango_auth_mode": nango_auth_mode,
            "nango_normalized": nango_auth_norm,
            "verdict": "match",
        })
    elif nango_auth_norm and our_auth_norm:
        mismatches.append({
            "app": app_name,
            "our_auth": our_auth,
            "nango_auth_mode": nango_auth_mode,
            "nango_normalized": nango_auth_norm,
            "verdict": "mismatch",
        })
    elif nango_auth_norm and not our_auth_norm:
        nango_only.append({
            "app": app_name,
            "nango_auth_mode": nango_auth_mode,
            "verdict": "nango_has_auth_we_dont",
        })
    elif our_auth_norm and not nango_auth_norm:
        our_only.append({
            "app": app_name,
            "our_auth": our_auth,
            "verdict": "we_have_auth_nango_doesnt",
        })

print(f"\n=== NANGO CROSS-CHECK ===")
print(f"Apps found in Nango: {len(matches) + len(mismatches) + len(nango_only) + len(our_only)}")
print(f"  Matches (our auth contains Nango's auth_mode): {len(matches)}")
print(f"  Mismatches (different auth): {len(mismatches)}")
print(f"  Nango has auth, we don't: {len(nango_only)}")
print(f"  We have auth, Nango doesn't: {len(our_only)}")

if mismatches:
    print(f"\n=== Mismatches (need investigation) ===")
    for m in mismatches:
        print(f"  {m['app']:30} our={m['our_auth']}  nango={m['nango_auth_mode']}")

if nango_only:
    print(f"\n=== Nango has auth, we don't (may need fix) ===")
    for m in nango_only:
        print(f"  {m['app']:30} nango_auth={m['nango_auth_mode']}")

# Save
summary = {
    "total_in_nango": len(matches) + len(mismatches) + len(nango_only) + len(our_only),
    "matches": len(matches),
    "mismatches": len(mismatches),
    "nango_only": len(nango_only),
    "our_only": len(our_only),
    "match_rate": len(matches) / (len(matches) + len(mismatches)) if (matches or mismatches) else 0,
    "mismatches_detail": mismatches,
    "nango_only_detail": nango_only,
}
Path("/home/z/my-project/data/nango_crosscheck.json").write_text(json.dumps(summary, indent=2, default=str))
print(f"\nSaved to /home/z/my-project/data/nango_crosscheck.json")
print(f"\nMatch rate (where both have auth): {summary['match_rate']*100:.1f}%")
