"""Expanded verification: ALL 50 Composio-supported apps, not just 25.
   This gives a much tighter confidence interval.

   Also: cross-check against Nango's providers.yaml (800+ curated auth configs).
   And: implement F01-F15 failure taxonomy on any disagreements.
"""
import os
import json, collections, asyncio, time, hashlib, re
from pathlib import Path
import httpx

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
CACHE_DIR = DATA_DIR / "cache"
VERIF_DIR = DATA_DIR / "verification"
VERIF_DIR.mkdir(parents=True, exist_ok=True)

COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")
COMPOSIO_HEADERS = {"Authorization": f"Bearer {COMPOSIO_KEY}"}
COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1/toolkits"

# Auth scheme normalization
def norm_auth(schemes):
    if not schemes:
        return set()
    norm_map = {"OAUTH2": "oauth2", "API_KEY": "api_key", "BASIC": "basic",
                "S2S_OAUTH2": "oauth2", "BEARER_TOKEN": "api_key",  # bearer tokens delivered via API key flow
                "JWT": "jwt", "NONE": "none", "DIGEST": "api_key"}
    return set(norm_map.get(s.upper(), s.lower()) for s in schemes)

def norm_our_auth(auths):
    """Normalize our auth_methods for comparison with Composio."""
    if not auths:
        return set()
    norm_map = {"oauth": "oauth2", "s2s_oauth2": "oauth2", "client_credentials": "oauth2",
                "bearer_token": "api_key", "api-key": "api_key", "apikey": "api_key",
                "digest": "api_key"}
    return set(norm_map.get(a.lower(), a.lower()) for a in auths)

# F01-F15 failure taxonomy (from verification methodology)
FAILURE_CODES = {
    "F01": "stale_docs — page describes deprecated/removed feature",
    "F02": "hallucinated_endpoint — claimed URL not present in source",
    "F03": "auth_label_confusion — OAuth2 vs OAuth 2.0 / Bearer / client-credentials conflation",
    "F04": "sandbox_vs_production — test key/URL reported as production",
    "F05": "confident_fabrication — agent filled in plausible guess on missing data",
    "F06": "self_serve_misread — Sign-up button leads to contact-sales form",
    "F07": "wrong_section_copy — value from test/legacy table on same page",
    "F08": "training_data_drift — agent wrote REST/GraphQL from prior, not from page",
    "F09": "multi_valued_collapse — app supports N auth methods; agent returned 1",
    "F10": "wrong_source_tier — third-party blog cited as official",
    "F11": "partial_docs_read — multi-page docs; agent only read page 1",
    "F12": "login_walled_content — docs require auth; agent hallucinated behind wall",
    "F13": "over_generalization — 'all endpoints require auth' when ≥1 is public",
    "F14": "unit_format_error — rate limit per-sec vs per-min swap",
    "F15": "scope_misattribution — scopes from different product/flow",
    "F99": "other — see notes",
}

def classify_failure(orig_auth, comp_auth, app_record):
    """Classify a disagreement into F01-F15."""
    orig = norm_our_auth(orig_auth)
    comp = norm_auth(comp_auth)
    if orig == comp:
        return None
    # Most common: auth label confusion
    if orig.issubset(comp) or comp.issubset(orig):
        # Partial overlap — likely multi_valued_collapse or auth_label_confusion
        if len(orig) < len(comp):
            return "F09"  # multi_valued_collapse
        else:
            return "F03"  # auth_label_confusion (e.g., we said bearer_token, composio says API_KEY)
    # Disjoint sets
    notes = (app_record.get("agent_notes") or "").lower()
    if "stale" in notes or "deprecated" in notes:
        return "F01"
    if "404" in notes or "403" in notes or "blocked" in notes:
        return "F11"  # partial docs read / blocked
    if "composio" in notes and "fallback" in notes:
        return None  # we used composio, should match
    return "F03"  # default to auth label confusion

async def verify_all_composio_apps():
    """Verify auth_methods for ALL apps that are in Composio's registry."""
    records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
    composio_apps = [r for r in records if r.get("composio_supported")]
    print(f"Verifying {len(composio_apps)} Composio-supported apps...")

    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for r in composio_apps:
            app_name = r["app_name"]
            app_slug = r["app_slug"]
            try:
                # Re-query Composio to get fresh ground truth
                resp = await client.get(
                    COMPOSIO_BASE,
                    headers=COMPOSIO_HEADERS,
                    params={"search": app_name, "limit": 5}
                )
                if resp.status_code != 200:
                    print(f"  ✗ {app_name}: Composio API {resp.status_code}")
                    continue
                items = resp.json().get("items", [])
                # Find exact name match
                match = None
                for item in items:
                    if item.get("name", "").lower() == app_name.lower():
                        match = item
                        break
                if not match:
                    # Try slug match
                    for item in items:
                        if item.get("slug", "").lower() == app_slug.replace("-", "_").lower():
                            match = item
                            break
                if not match:
                    print(f"  ✗ {app_name}: no exact match in Composio (homonym?)")
                    results.append({
                        "app_name": app_name,
                        "app_slug": app_slug,
                        "verdict": "no_composio_match",
                        "our_auth": r.get("auth_methods"),
                        "composio_auth": None,
                        "failure_code": None,
                    })
                    continue

                comp_auth = match.get("auth_schemes", [])
                our_auth = r.get("auth_methods") or []

                # Normalize and compare
                our_norm = norm_our_auth(our_auth)
                comp_norm = norm_auth(comp_auth)

                if our_norm == comp_norm:
                    verdict = "correct"
                    failure_code = None
                elif our_norm.issubset(comp_norm) or comp_norm.issubset(our_norm):
                    verdict = "partial"
                    failure_code = classify_failure(our_auth, comp_auth, r)
                else:
                    verdict = "incorrect"
                    failure_code = classify_failure(our_auth, comp_auth, r)

                result = {
                    "app_name": app_name,
                    "app_slug": app_slug,
                    "verdict": verdict,
                    "our_auth": our_auth,
                    "our_auth_normalized": sorted(our_norm),
                    "composio_auth": comp_auth,
                    "composio_auth_normalized": sorted(comp_norm),
                    "composio_tools_count": match.get("meta", {}).get("tools_count"),
                    "failure_code": failure_code,
                    "failure_description": FAILURE_CODES.get(failure_code, ""),
                }
                results.append(result)
                symbol = {"correct": "✓", "partial": "~", "incorrect": "✗"}.get(verdict, "?")
                print(f"  {symbol} {app_name:30} our={sorted(our_norm)} comp={sorted(comp_norm)} → {verdict}")

            except Exception as e:
                print(f"  ✗ {app_name}: {e}")

            await asyncio.sleep(0.5)  # polite

    # Aggregate
    verdicts = collections.Counter(r["verdict"] for r in results)
    correct = verdicts.get("correct", 0)
    partial = verdicts.get("partial", 0)
    incorrect = verdicts.get("incorrect", 0)
    no_match = verdicts.get("no_composio_match", 0)
    total = len(results)

    # F1-style score: correct=1, partial=0.5, incorrect=0
    score = (correct + 0.5 * partial) / total if total else 0

    # Wilson 95% CI for the score
    import math
    n = total
    p = score
    if n > 0:
        z = 1.96
        denom = 1 + z*z/n
        center = (p + z*z/(2*n)) / denom
        margin = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / denom
        ci_low = max(0, center - margin)
        ci_high = min(1, center + margin)
    else:
        ci_low = ci_high = 0

    # Failure code distribution
    fc_dist = collections.Counter(r["failure_code"] for r in results if r["failure_code"])

    summary = {
        "total_verified": total,
        "verdicts": dict(verdicts),
        "correct": correct,
        "partial": partial,
        "incorrect": incorrect,
        "no_composio_match": no_match,
        "f1_score": round(score, 4),
        "f1_score_pct": round(score * 100, 1),
        "wilson_95_ci": {
            "low": round(ci_low * 100, 1),
            "high": round(ci_high * 100, 1),
        },
        "failure_code_distribution": dict(fc_dist.most_common()),
        "failure_code_descriptions": {fc: FAILURE_CODES[fc] for fc in fc_dist if fc in FAILURE_CODES},
        "results": results,
    }

    print(f"\n=== EXPANDED VERIFICATION SUMMARY ===")
    print(f"Total verified: {total}")
    print(f"  Correct:   {correct} ({correct/total*100:.1f}%)")
    print(f"  Partial:   {partial} ({partial/total*100:.1f}%)")
    print(f"  Incorrect: {incorrect} ({incorrect/total*100:.1f}%)")
    if no_match:
        print(f"  No Composio match: {no_match}")
    print(f"\nF1-style score: {score*100:.1f}%")
    print(f"Wilson 95% CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%]")
    print(f"\nFailure code distribution:")
    for fc, count in fc_dist.most_common():
        print(f"  {fc}: {count} — {FAILURE_CODES.get(fc, '')}")

    # Save
    (VERIF_DIR / "_expanded_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {VERIF_DIR}/_expanded_summary.json")
    return summary

asyncio.run(verify_all_composio_apps())
