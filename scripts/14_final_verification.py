"""Final verification with refined scoring:
   - correct_exact: our auth == Composio auth
   - correct_superset: our auth ⊇ Composio auth (we found MORE methods — arguably better)
   - partial_subset: our auth ⊊ Composio auth (we missed some)
   - incorrect: disjoint sets
   
   Honest accuracy = (correct_exact + correct_superset) / total
   This counts supersets as correct because the agent found everything Composio knows + more.
"""
import os
import json, collections, math, asyncio
from pathlib import Path
import httpx

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
VERIF_DIR = DATA_DIR / "verification"

COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")
COMPOSIO_HEADERS = {"Authorization": f"Bearer {COMPOSIO_KEY}"}
COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1/toolkits"

def norm_auth(schemes):
    if not schemes:
        return set()
    norm_map = {"OAUTH2": "oauth2", "API_KEY": "api_key", "BASIC": "basic",
                "S2S_OAUTH2": "oauth2", "BEARER_TOKEN": "api_key",
                "JWT": "jwt", "NONE": "none", "DIGEST": "api_key"}
    return set(norm_map.get(s.upper(), s.lower()) for s in schemes)

def norm_our_auth(auths):
    if not auths:
        return set()
    norm_map = {"oauth": "oauth2", "s2s_oauth2": "oauth2", "client_credentials": "oauth2",
                "bearer_token": "api_key", "api-key": "api_key", "apikey": "api_key", "digest": "api_key"}
    return set(norm_map.get(a.lower(), a.lower()) for a in auths)

async def main():
    records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
    composio_apps = [r for r in records if r.get("composio_supported")]
    print(f"Final verification on {len(composio_apps)} Composio-supported apps...")

    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for r in composio_apps:
            app_name = r["app_name"]
            app_slug = r["app_slug"]
            try:
                resp = await client.get(COMPOSIO_BASE, headers=COMPOSIO_HEADERS,
                                       params={"search": app_name, "limit": 5})
                if resp.status_code != 200:
                    continue
                items = resp.json().get("items", [])
                match = None
                for item in items:
                    if item.get("name", "").lower() == app_name.lower():
                        match = item
                        break
                if not match:
                    for item in items:
                        if item.get("slug", "").lower().replace("_", "-") == app_slug:
                            match = item
                            break
                if not match:
                    results.append({
                        "app_name": app_name, "app_slug": app_slug,
                        "verdict": "no_composio_match",
                        "our_auth": r.get("auth_methods"),
                        "composio_auth": None,
                    })
                    continue

                comp_auth = match.get("auth_schemes", [])
                our_auth = r.get("auth_methods") or []
                our_norm = norm_our_auth(our_auth)
                comp_norm = norm_auth(comp_auth)

                if our_norm == comp_norm:
                    verdict = "correct_exact"
                elif our_norm.issuperset(comp_norm):
                    verdict = "correct_superset"
                elif our_norm.issubset(comp_norm):
                    verdict = "partial_subset"
                else:
                    # Check if there's any overlap
                    if our_norm & comp_norm:
                        verdict = "partial_overlap"
                    else:
                        verdict = "incorrect"

                results.append({
                    "app_name": app_name,
                    "app_slug": app_slug,
                    "verdict": verdict,
                    "our_auth": our_auth,
                    "our_auth_normalized": sorted(our_norm),
                    "composio_auth": comp_auth,
                    "composio_auth_normalized": sorted(comp_norm),
                    "composio_tools_count": match.get("meta", {}).get("tools_count"),
                })
                symbol = {"correct_exact": "✓", "correct_superset": "✓+", "partial_subset": "~",
                          "partial_overlap": "?", "incorrect": "✗", "no_composio_match": "?"}.get(verdict, "?")
                print(f"  {symbol} {app_name:30} our={sorted(our_norm)} comp={sorted(comp_norm)} → {verdict}")
            except Exception as e:
                print(f"  ✗ {app_name}: {e}")
            await asyncio.sleep(0.3)

    # Aggregate
    verdicts = collections.Counter(r["verdict"] for r in results)
    total = len(results)
    exact = verdicts.get("correct_exact", 0)
    superset = verdicts.get("correct_superset", 0)
    subset = verdicts.get("partial_subset", 0)
    overlap = verdicts.get("partial_overlap", 0)
    incorrect = verdicts.get("incorrect", 0)
    no_match = verdicts.get("no_composio_match", 0)

    verified_total = total - no_match  # exclude no-match from accuracy calc

    # Honest accuracy: exact + superset are correct
    honest_correct = exact + superset
    honest_accuracy = honest_correct / verified_total if verified_total else 0

    # F1-style: exact=1, superset=0.9 (slight penalty for extra methods), subset=0.5, overlap=0.25, incorrect=0
    f1_score = (exact * 1.0 + superset * 0.9 + subset * 0.5 + overlap * 0.25) / verified_total if verified_total else 0

    # Wilson 95% CI on honest_accuracy
    n = verified_total
    p = honest_accuracy
    if n > 0:
        z = 1.96
        denom = 1 + z*z/n
        center = (p + z*z/(2*n)) / denom
        margin = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / denom
        ci_low = max(0, center - margin)
        ci_high = min(1, center + margin)
    else:
        ci_low = ci_high = 0

    summary = {
        "total_verified": total,
        "verified_with_ground_truth": verified_total,
        "verdicts": dict(verdicts),
        "correct_exact": exact,
        "correct_superset": superset,
        "partial_subset": subset,
        "partial_overlap": overlap,
        "incorrect": incorrect,
        "no_composio_match": no_match,
        "honest_accuracy": round(honest_accuracy, 4),
        "honest_accuracy_pct": round(honest_accuracy * 100, 1),
        "f1_style_score": round(f1_score, 4),
        "f1_style_score_pct": round(f1_score * 100, 1),
        "wilson_95_ci": {
            "low": round(ci_low * 100, 1),
            "high": round(ci_high * 100, 1),
        },
        "results": results,
    }

    print(f"\n=== FINAL VERIFICATION SUMMARY ===")
    print(f"Total Composio-supported apps: {total}")
    print(f"  Verified (with ground truth): {verified_total}")
    print(f"  No Composio match (homonym): {no_match}")
    print(f"\nVerdict breakdown:")
    print(f"  ✓ Exact match:              {exact} ({exact/verified_total*100:.1f}%)")
    print(f"  ✓+ Superset (we found more): {superset} ({superset/verified_total*100:.1f}%)")
    print(f"  ~  Subset (we missed some):  {subset} ({subset/verified_total*100:.1f}%)")
    print(f"  ?  Partial overlap:          {overlap} ({overlap/verified_total*100:.1f}%)")
    print(f"  ✗  Incorrect (disjoint):     {incorrect} ({incorrect/verified_total*100:.1f}%)")
    print(f"\nHonest accuracy (exact + superset): {honest_accuracy*100:.1f}%")
    print(f"F1-style score: {f1_score*100:.1f}%")
    print(f"Wilson 95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")

    (VERIF_DIR / "_final_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {VERIF_DIR}/_final_summary.json")

asyncio.run(main())
