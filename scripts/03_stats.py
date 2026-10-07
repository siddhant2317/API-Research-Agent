"""Quick stats on the first-pass research results."""
import json, collections
from pathlib import Path

apps_dir = Path("/home/z/my-project/data/apps")
records = [json.loads(p.read_text()) for p in sorted(apps_dir.glob("*.json"))]
print(f"Total records: {len(records)}")

# Confidence distribution
conf = collections.Counter(r.get("confidence", "unknown") for r in records)
print(f"\nConfidence: {dict(conf)}")

# Composio coverage
comp = sum(1 for r in records if r.get("composio_supported"))
print(f"Composio-supported: {comp}/100")

# Auth methods distribution
auth_counter = collections.Counter()
for r in records:
    for a in (r.get("auth_methods") or []):
        auth_counter[a] += 1
print(f"\nAuth methods (apps can have multiple):")
for a, c in auth_counter.most_common():
    print(f"  {a}: {c}")

# Self-serve distribution
ss = collections.Counter(r.get("self_serve") for r in records)
print(f"\nSelf-serve: {dict(ss)}")

# Gating type
gt = collections.Counter(r.get("gating_type") for r in records)
print(f"\nGating type: {dict(gt)}")

# Buildability score distribution
bs = collections.Counter(str(r.get("buildability_score")) for r in records)
print(f"\nBuildability score: {dict(bs.most_common())}")

# Main blocker
mb = collections.Counter(r.get("main_blocker") for r in records)
print(f"\nMain blocker: {dict(mb.most_common())}")

# MCP server exists
mcp = collections.Counter(r.get("mcp_server_exists") for r in records)
print(f"\nMCP server exists: {dict(mcp)}")

# By category
print(f"\n=== By category ===")
cats = collections.defaultdict(list)
for r in records:
    cats[r.get("category", "?")].append(r)
for cat, recs in sorted(cats.items()):
    avg_bs = sum(r.get("buildability_score", 0) or 0 for r in recs) / len(recs)
    ss_count = sum(1 for r in recs if r.get("self_serve"))
    comp_count = sum(1 for r in recs if r.get("composio_supported"))
    print(f"  {cat:45} n={len(recs):2}  avg_build={avg_bs:.1f}  self_serve={ss_count}/{len(recs)}  composio={comp_count}/{len(recs)}")

# Low-confidence apps (need verification focus)
print(f"\n=== Low-confidence apps (need verification) ===")
low = [r for r in records if r.get("confidence") == "low"]
for r in low:
    print(f"  {r['app_name']:30} cat={r['category']:35} blocker={r.get('main_blocker')} notes={r.get('agent_notes', '')[:80]}")
