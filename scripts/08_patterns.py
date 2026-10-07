"""Generate the pattern analysis + statistics for the case study.
   Outputs: /home/z/my-project/data/patterns.json
"""
import json, collections, statistics
from pathlib import Path

APPS_DIR = Path("/home/z/my-project/data/apps")
records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
print(f"Loaded {len(records)} records")

# Auth scheme normalization (so oauth2/OAUTH2/OAuth2 all count together)
def norm(a):
    if not a:
        return None
    a = a.lower().strip()
    m = {"oauth": "oauth2", "s2s_oauth2": "oauth2", "client_credentials": "oauth2",
         "bearer_token": "api_key",  # bearer tokens are typically delivered via API key flow
         "api-key": "api_key", "apikey": "api_key"}
    return m.get(a, a)

# --- 1. AUTH METHOD DISTRIBUTION ---
auth_apps = collections.Counter()  # primary auth (first one listed)
auth_all = collections.Counter()  # all auth methods across all apps
no_auth_count = 0
for r in records:
    auths = r.get("auth_methods") or []
    if not auths:
        no_auth_count += 1
        continue
    normed = [norm(a) for a in auths if norm(a)]
    if not normed:
        no_auth_count += 1
        continue
    for a in set(normed):  # unique per app
        auth_all[a] += 1
    auth_apps[normed[0]] += 1  # primary

print(f"\n=== Auth method distribution ===")
print(f"Apps with no auth (no public API): {no_auth_count}")
print(f"Auth methods (apps can have multiple):")
for a, c in auth_all.most_common():
    print(f"  {a}: {c} ({c/100*100:.0f}%)")

# --- 2. SELF-SERVE vs GATED ---
ss = collections.Counter()
for r in records:
    if r.get("self_serve") is True:
        ss["self_serve"] += 1
    elif r.get("self_serve") is False:
        ss["gated"] += 1
    else:
        ss["unknown"] += 1
print(f"\n=== Self-serve vs gated ===")
print(f"{dict(ss)}")

# Gating type breakdown
gt = collections.Counter(r.get("gating_type") or "unknown" for r in records)
print(f"Gating type: {dict(gt.most_common())}")

# --- 3. BUILDABILITY DISTRIBUTION ---
bs = collections.Counter(str(r.get("buildability_score")) for r in records)
print(f"\n=== Buildability score ===")
print(f"{dict(bs.most_common())}")

# Buildable (4-5) vs partial (2-3) vs not (0-1)
buildable = sum(1 for r in records if (r.get("buildability_score") or 0) >= 4)
partial = sum(1 for r in records if 2 <= (r.get("buildability_score") or 0) <= 3)
not_buildable = sum(1 for r in records if (r.get("buildability_score") or 0) <= 1)
print(f"Buildable (4-5): {buildable}")
print(f"Partial (2-3): {partial}")
print(f"Not buildable (0-1): {not_buildable}")

# --- 4. MAIN BLOCKERS ---
mb = collections.Counter(r.get("main_blocker") or "unknown" for r in records)
print(f"\n=== Main blockers ===")
for b, c in mb.most_common():
    print(f"  {b}: {c}")

# --- 5. BY CATEGORY ---
by_cat = collections.defaultdict(list)
for r in records:
    by_cat[r["category"]].append(r)

print(f"\n=== By category ===")
category_stats = {}
for cat, recs in sorted(by_cat.items()):
    avg_bs = statistics.mean(r.get("buildability_score", 0) or 0 for r in recs)
    ss_count = sum(1 for r in recs if r.get("self_serve"))
    comp_count = sum(1 for r in recs if r.get("composio_supported"))
    buildable_count = sum(1 for r in recs if (r.get("buildability_score") or 0) >= 4)
    no_api_count = sum(1 for r in recs if (r.get("main_blocker") == "no_public_api"))
    gated_count = sum(1 for r in recs if (r.get("main_blocker") == "gated_access"))
    category_stats[cat] = {
        "n": len(recs),
        "avg_buildability": round(avg_bs, 2),
        "self_serve_count": ss_count,
        "composio_count": comp_count,
        "buildable_count": buildable_count,
        "no_api_count": no_api_count,
        "gated_count": gated_count,
    }
    print(f"  {cat:45} build_avg={avg_bs:.1f} self_serve={ss_count}/{len(recs)} buildable={buildable_count}/{len(recs)} composio={comp_count}/{len(recs)}")

# --- 6. AUTH × BUILDABILITY cross-tab ---
print(f"\n=== Auth method × Buildability ===")
auth_build = collections.defaultdict(lambda: collections.Counter())
for r in records:
    auths = r.get("auth_methods") or []
    normed = [norm(a) for a in auths if norm(a)]
    if not normed:
        auth_build["(no api)"][r.get("buildability_score", 0) or 0] += 1
    else:
        # Attribute to primary auth
        primary = normed[0]
        auth_build[primary][r.get("buildability_score", 0) or 0] += 1

for a in ["oauth2", "api_key", "basic", "jwt", "none", "(no api)"]:
    if a in auth_build:
        scores = auth_build[a]
        total = sum(scores.values())
        avg = sum(int(s)*c for s,c in scores.items()) / total
        print(f"  {a:10} n={total:3} avg_build={avg:.1f} dist={dict(sorted(scores.items()))}")

# --- 7. COMPOSIO COVERAGE ---
comp_count = sum(1 for r in records if r.get("composio_supported"))
print(f"\n=== Composio coverage ===")
print(f"Composio-supported: {comp_count}/100")
# Avg buildability for composio vs non-composio
comp_avg = statistics.mean(r.get("buildability_score", 0) or 0 for r in records if r.get("composio_supported"))
non_comp_avg = statistics.mean(r.get("buildability_score", 0) or 0 for r in records if not r.get("composio_supported"))
print(f"  Composio-supported avg buildability: {comp_avg:.2f}")
print(f"  Non-Composio avg buildability: {non_comp_avg:.2f}")

# --- 8. MCP SERVER EXISTENCE ---
mcp_count = sum(1 for r in records if r.get("mcp_server_exists"))
print(f"\n=== MCP server existence ===")
print(f"MCP server exists: {mcp_count}/100")
# Of those, how many via Composio
comp_mcp = sum(1 for r in records if r.get("mcp_server_exists") and r.get("composio_supported"))
non_comp_mcp = mcp_count - comp_mcp
print(f"  Via Composio: {comp_mcp}")
print(f"  Via other registries: {non_comp_mcp}")

# --- 9. HEADLINE FINDINGS ---
print(f"\n=== HEADLINE FINDINGS ===")
print(f"1. {buildable}/100 apps ({buildable}%) are buildable as agent toolkits today (score 4-5)")
print(f"2. {ss.get('self_serve', 0)}/100 ({ss.get('self_serve', 0)}%) are self-serve for developers")
print(f"3. {no_auth_count}/100 ({no_auth_count}%) have no public API at all")
print(f"4. {comp_count}/100 ({comp_count}%) are already in Composio's registry")
print(f"5. OAuth2 is the dominant auth method ({auth_all.get('oauth2', 0)} apps)")
print(f"6. {mb.most_common(1)[0][0]} is the most common blocker ({mb.most_common(1)[0][1]} apps)")
print(f"7. Composio-supported apps have avg buildability {comp_avg:.1f} vs {non_comp_avg:.1f} for non-Composio")
print(f"8. Most buildable category: {max(category_stats.items(), key=lambda x: x[1]['avg_buildability'])[0]}")
print(f"9. Least buildable category: {min(category_stats.items(), key=lambda x: x[1]['avg_buildability'])[0]}")

# Save the patterns JSON
patterns = {
    "totals": {
        "apps": 100,
        "categories": 10,
        "buildable": buildable,
        "partial": partial,
        "not_buildable": not_buildable,
        "self_serve": ss.get("self_serve", 0),
        "gated": ss.get("gated", 0),
        "unknown_self_serve": ss.get("unknown", 0),
        "composio_supported": comp_count,
        "mcp_server_exists": mcp_count,
        "no_public_api": no_auth_count,
    },
    "auth_methods": dict(auth_all.most_common()),
    "primary_auth": dict(auth_apps.most_common()),
    "gating_types": dict(gt.most_common()),
    "buildability_distribution": dict(bs.most_common()),
    "main_blockers": dict(mb.most_common()),
    "category_stats": category_stats,
    "auth_vs_buildability": {
        a: {"n": sum(scores.values()), "avg": sum(int(s)*c for s,c in scores.items())/sum(scores.values()),
            "dist": dict(sorted(scores.items()))}
        for a, scores in auth_build.items()
    },
    "composio_comparison": {
        "composio_avg_buildability": round(comp_avg, 2),
        "non_composio_avg_buildability": round(non_comp_avg, 2),
    },
    "mcp_breakdown": {
        "via_composio": comp_mcp,
        "via_other": non_comp_mcp,
    },
}

Path("/home/z/my-project/data/patterns.json").write_text(json.dumps(patterns, indent=2))
print(f"\n✓ Saved patterns to /home/z/my-project/data/patterns.json")

# Also save the full records as a single array for the case study
Path("/home/z/my-project/data/all_apps.json").write_text(json.dumps(records, indent=2))
print(f"✓ Saved all 100 records to /home/z/my-project/data/all_apps.json")
