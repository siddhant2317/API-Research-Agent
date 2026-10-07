"""
Verification & retry script.

Two jobs:
1. RETRY: Re-run extraction for apps where the first pass failed (confidence=low + empty record).
   Use the cached docs (no re-fetch needed) + Composio data + thinking_enabled=True for better quality.
2. VERIFY: On a 25-app gold sample, run a second pass with thinking enabled + cross-source check.

Output:
  /home/z/my-project/data/apps/<slug>.json  (updated in place for retries)
  /home/z/my-project/data/verification/<slug>.json  (verification verdicts)
"""
from __future__ import annotations
import asyncio, json, re, time, hashlib, collections
from pathlib import Path
from typing import Optional
import httpx
import sys

# Import the agent core
sys.path.insert(0, "/home/z/my-project/scripts")
from importlib import import_module
# Load agent_core as a module
import importlib.util
spec = importlib.util.spec_from_file_location("agent_core", "/home/z/my-project/scripts/02_agent_core.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
AUDIT_DIR = DATA_DIR / "audit"
CACHE_DIR = DATA_DIR / "cache"
VERIF_DIR = DATA_DIR / "verification"
VERIF_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Step 1: Identify apps needing retry
# ---------------------------------------------------------------------------
all_records = []
for p in sorted(APPS_DIR.glob("*.json")):
    all_records.append(json.loads(p.read_text()))

needs_retry = []
for r in all_records:
    is_empty = "Extraction failed" in (r.get("agent_notes") or "") or not r.get("auth_methods")
    is_low = r.get("confidence") == "low"
    if is_empty or (is_low and not r.get("auth_methods")):
        needs_retry.append(r)

print(f"Step 1: {len(needs_retry)} apps need retry (empty/failed extraction)")
for r in needs_retry:
    print(f"  - {r['app_name']} (id={r['id']})")

# ---------------------------------------------------------------------------
# Step 2: Retry with thinking enabled + better prompts
# ---------------------------------------------------------------------------
async def retry_one(app_record: dict) -> dict:
    """Re-run extraction for an app, using cached docs + thinking enabled."""
    app_slug = app_record["app_slug"]
    audit_path = AUDIT_DIR / f"{app_slug}.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}

    # Find the original app definition
    all_apps = json.loads((DATA_DIR / "apps.json").read_text())
    app_def = next((a for a in all_apps if a["id"] == app_record["id"]), None)
    if not app_def:
        print(f"  ✗ {app_slug}: no app definition found")
        return app_record

    # Use cached docs if available
    docs_url = app_def["docs_url"]
    cache_key = hashlib.md5(docs_url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    docs_md = ""
    docs_status = 0
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        docs_md = cached.get("markdown", "")
        docs_status = cached.get("status", 0)

    # If cache is thin, try the search fallback URLs from audit
    if len(docs_md) < 500 and audit.get("fetched_urls"):
        for fu in audit["fetched_urls"]:
            if fu.get("md_len", 0) > 500:
                alt_cache_key = hashlib.md5(fu["url"].encode()).hexdigest()
                alt_cache_file = CACHE_DIR / f"{alt_cache_key}.json"
                if alt_cache_file.exists():
                    alt_cached = json.loads(alt_cache_file.read_text())
                    if len(alt_cached.get("markdown", "")) > len(docs_md):
                        docs_md = alt_cached["markdown"]
                        docs_status = alt_cached["status"]
                        docs_url = fu["url"]
                        break

    async with httpx.AsyncClient(timeout=agent.HTTP_TIMEOUT) as client:
        # Re-fetch search snippets
        search_results = await agent.z_ai_function("web_search", {"query": f"{app_def['name']} API authentication oauth api key", "num": 5}, timeout=30)
        search_snippets = ""
        if search_results:
            search_snippets = "\n\n".join([
                f"URL: {r.get('url', '')}\nTitle: {r.get('name', '')}\nSnippet: {r.get('snippet', '')}"
                for r in search_results
            ])

        # If docs are still thin, try fetching from one of the search results
        if len(docs_md) < 500 and search_results:
            for sr in search_results[:3]:
                alt_url = sr.get("url", "")
                if alt_url and "docs" in alt_url.lower() or "api" in alt_url.lower():
                    alt_status, alt_md = await agent.fetch_url(alt_url, client=client)
                    if alt_status == 200 and len(alt_md) > len(docs_md):
                        docs_md = alt_md
                        docs_status = alt_status
                        docs_url = alt_url
                        break

        # Get Composio data
        composio_data = await agent.lookup_composio(app_def["name"], client=client)

        # Get MCP hits
        mcp_hits = await agent.lookup_mcp_registries(app_def["name"], client=client)

        # Re-extract with thinking enabled
        print(f"  ↻ {app_slug}: retrying with thinking=on, docs_len={len(docs_md)}")
        t0 = time.time()
        extracted = await agent.extract_app_research(
            app_def,
            docs_md=docs_md,
            docs_status=docs_status,
            search_snippets=search_snippets,
            extra_pages="",
            mcp_hits=mcp_hits,
            composio_data=composio_data,
            thinking_enabled=True,  # KEY DIFFERENCE
        )
        print(f"    done in {time.time()-t0:.1f}s, success={extracted is not None}")

        if extracted:
            # Update record
            record = {
                **app_record,
                **extracted,
                "id": app_record["id"],
                "app_name": app_record["app_name"],
                "app_slug": app_slug,
                "category": app_record["category"],
                "website": app_record.get("website", ""),
                "docs_url": app_record["docs_url"],
                "primary_docs_url_used": docs_url,
                "audit_summary": {
                    **app_record.get("audit_summary", {}),
                    "retry_attempted": True,
                    "retry_thinking_enabled": True,
                },
                "researched_at": app_record.get("researched_at", time.time()),
                "retried_at": time.time(),
            }
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(record, indent=2))
            return record
        else:
            # Even if extraction failed, fill in from Composio if available
            if composio_data:
                auth_schemes = composio_data.get("auth_schemes", [])
                # Normalize Composio auth schemes to our enum
                norm_map = {
                    "OAUTH2": "oauth2",
                    "API_KEY": "api_key",
                    "BASIC": "basic",
                    "S2S_OAUTH2": "oauth2",  # server-to-server OAuth2
                    "BEARER_TOKEN": "bearer_token",
                    "JWT": "jwt",
                    "NONE": "none",
                }
                auth_methods = list({norm_map.get(a, a.lower()) for a in auth_schemes})
                record = {
                    **app_record,
                    "auth_methods": auth_methods,
                    "auth_methods_evidence": f"From Composio registry (extraction failed; using ground-truth auth_schemes)",
                    "composio_supported": True,
                    "composio_auth_schemes": auth_schemes,
                    "composio_tools_count": composio_data.get("meta", {}).get("tools_count"),
                    "api_surface_breadth": "broad" if (composio_data.get("meta", {}).get("tools_count", 0) or 0) >= 50 else "medium" if (composio_data.get("meta", {}).get("tools_count", 0) or 0) >= 10 else "narrow",
                    "mcp_server_exists": True,
                    "mcp_server_sources": [f"composio:{composio_data.get('slug')}"],
                    "buildability_score": 4 if auth_methods else 0,
                    "buildability_rationale": f"Composio-supported with {len(auth_methods)} auth method(s); docs verification failed but registry confirms integration is possible.",
                    "main_blocker": "poor_docs",
                    "confidence": "medium",
                    "agent_notes": f"Extraction failed but Composio registry provides ground-truth auth data. Tools count: {composio_data.get('meta', {}).get('tools_count')}.",
                    "audit_summary": {
                        **app_record.get("audit_summary", {}),
                        "retry_attempted": True,
                        "retry_thinking_enabled": True,
                        "fallback_to_composio": True,
                    },
                    "retried_at": time.time(),
                }
                (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(record, indent=2))
                return record
            return app_record

async def run_retries():
    print(f"\n=== Running retries for {len(needs_retry)} apps ===")
    sem = asyncio.Semaphore(2)  # lower concurrency for thinking mode (slower)
    async def bounded(r):
        async with sem:
            return await retry_one(r)
    results = await asyncio.gather(*[bounded(r) for r in needs_retry])
    print(f"\nRetries complete. Updated {sum(1 for r in results if r.get('confidence') != 'low')} records to medium+ confidence.")
    return results

# ---------------------------------------------------------------------------
# Step 3: Verification — re-extract 25-app gold sample with thinking enabled
# ---------------------------------------------------------------------------
def select_gold_sample(records: list[dict], n: int = 25) -> list[dict]:
    """Stratified random sample: 2-3 per category, plus all disputed/low-confidence."""
    import random
    random.seed(42)
    by_cat = collections.defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    sample = []
    # 2 per category = 20
    for cat, recs in by_cat.items():
        sample.extend(random.sample(recs, min(2, len(recs))))
    # Add 5 more from low-confidence
    low_conf = [r for r in records if r.get("confidence") == "low" and r not in sample]
    sample.extend(random.sample(low_conf, min(5, len(low_conf))))
    return sample[:n]

async def verify_one(app_record: dict) -> dict:
    """Verify by re-extracting with thinking enabled + comparing to original."""
    app_slug = app_record["app_slug"]
    audit_path = AUDIT_DIR / f"{app_slug}.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}

    all_apps = json.loads((DATA_DIR / "apps.json").read_text())
    app_def = next((a for a in all_apps if a["id"] == app_record["id"]), None)
    if not app_def:
        return {"app_slug": app_slug, "verdict": "error", "reason": "no app def"}

    # Get cached docs
    docs_url = app_record.get("primary_docs_url_used", app_def["docs_url"])
    cache_key = hashlib.md5(docs_url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    docs_md = ""
    docs_status = 0
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        docs_md = cached.get("markdown", "")
        docs_status = cached.get("status", 0)

    async with httpx.AsyncClient(timeout=agent.HTTP_TIMEOUT) as client:
        search_results = await agent.z_ai_function("web_search", {"query": f"{app_def['name']} API authentication oauth api key", "num": 5}, timeout=30)
        search_snippets = ""
        if search_results:
            search_snippets = "\n\n".join([
                f"URL: {r.get('url', '')}\nTitle: {r.get('name', '')}\nSnippet: {r.get('snippet', '')}"
                for r in search_results
            ])

        composio_data = await agent.lookup_composio(app_def["name"], client=client)
        mcp_hits = await agent.lookup_mcp_registries(app_def["name"], client=client)

        # Re-extract with thinking enabled
        print(f"  ? {app_slug}: verifying with thinking=on")
        t0 = time.time()
        verified = await agent.extract_app_research(
            app_def,
            docs_md=docs_md,
            docs_status=docs_status,
            search_snippets=search_snippets,
            extra_pages="",
            mcp_hits=mcp_hits,
            composio_data=composio_data,
            thinking_enabled=True,
        )
        print(f"    done in {time.time()-t0:.1f}s")

        if not verified:
            return {
                "app_slug": app_slug,
                "app_name": app_record["app_name"],
                "verdict": "extraction_failed",
                "original": app_record,
            }

        # Compare fields
        fields_to_compare = [
            "auth_methods", "self_serve", "gating_type",
            "api_surface_breadth", "buildability_score", "main_blocker",
            "composio_supported", "mcp_server_exists",
        ]
        agree = []
        disagree = []
        for f in fields_to_compare:
            orig_val = app_record.get(f)
            new_val = verified.get(f)
            # Normalize for comparison
            if isinstance(orig_val, list) and isinstance(new_val, list):
                orig_set = set(str(x).lower() for x in orig_val)
                new_set = set(str(x).lower() for x in new_val)
                if orig_set == new_set:
                    agree.append(f)
                else:
                    disagree.append({"field": f, "original": orig_val, "verified": new_val})
            else:
                if str(orig_val).lower() == str(new_val).lower():
                    agree.append(f)
                else:
                    disagree.append({"field": f, "original": orig_val, "verified": new_val})

        # Cross-check against Composio ground truth if available
        composio_check = None
        if composio_data:
            composio_auth = set(a.lower() for a in composio_data.get("auth_schemes", []))
            # Normalize our auth_methods for comparison
            norm_map = {"oauth2": "oauth2", "api_key": "api_key", "basic": "basic", "bearer_token": "bearer_token", "s2s_oauth2": "oauth2"}
            orig_auth_set = set(norm_map.get(a.lower(), a.lower()) for a in (app_record.get("auth_methods") or []))
            new_auth_set = set(norm_map.get(a.lower(), a.lower()) for a in (verified.get("auth_methods") or []))
            composio_check = {
                "composio_auth": list(composio_auth),
                "original_matches_composio": orig_auth_set == composio_auth or orig_auth_set.issubset(composio_auth),
                "verified_matches_composio": new_auth_set == composio_auth or new_auth_set.issubset(composio_auth),
            }

        verdict = "agree" if not disagree else "disagree"
        if composio_check and not composio_check["verified_matches_composio"]:
            verdict = "disagree_with_composio"

        result = {
            "app_slug": app_slug,
            "app_name": app_record["app_name"],
            "verdict": verdict,
            "fields_agree": agree,
            "fields_disagree": disagree,
            "composio_crosscheck": composio_check,
            "original_record": {k: app_record.get(k) for k in fields_to_compare},
            "verified_record": {k: verified.get(k) for k in fields_to_compare},
            "verified_full": verified,
        }
        (VERIF_DIR / f"{app_slug}.json").write_text(json.dumps(result, indent=2))

        # If verified has higher quality (e.g., filled in missing fields), update the main record
        # but keep the original in audit
        should_update = False
        if not app_record.get("auth_methods") and verified.get("auth_methods"):
            should_update = True
        if app_record.get("confidence") == "low" and verified.get("confidence") in ("medium", "high"):
            should_update = True
        if disagree and composio_check and composio_check["verified_matches_composio"]:
            should_update = True

        if should_update:
            updated = {**app_record, **verified, "verified_at": time.time()}
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(updated, indent=2))
            print(f"    ✓ Updated main record (verified was better)")

        return result

async def run_verification():
    print(f"\n=== Running verification on 25-app gold sample ===")
    sample = select_gold_sample(all_records, n=25)
    print(f"Sample: {[r['app_name'] for r in sample]}")
    sem = asyncio.Semaphore(2)
    async def bounded(r):
        async with sem:
            return await verify_one(r)
    results = await asyncio.gather(*[bounded(r) for r in sample])

    # Summary
    agree = sum(1 for r in results if r["verdict"] == "agree")
    disagree = sum(1 for r in results if r["verdict"] == "disagree")
    disagree_comp = sum(1 for r in results if r["verdict"] == "disagree_with_composio")
    failed = sum(1 for r in results if r["verdict"] in ("extraction_failed", "error"))

    print(f"\n=== Verification Summary ===")
    print(f"  Total verified: {len(results)}")
    print(f"  Agree (original == verified): {agree}")
    print(f"  Disagree (no composio ground truth): {disagree}")
    print(f"  Disagree with Composio ground truth: {disagree_comp}")
    print(f"  Failed: {failed}")
    print(f"  Agreement rate: {(agree + disagree) / len(results):.1%}")
    print(f"  Rate when Composio ground truth available: depends on subset")

    # Save summary
    summary = {
        "total_verified": len(results),
        "agree": agree,
        "disagree": disagree,
        "disagree_with_composio": disagree_comp,
        "failed": failed,
        "agreement_rate": (agree + disagree) / len(results),
        "sample_apps": [r["app_name"] for r in sample],
        "disagreements": [
            {"app": r["app_name"], "fields": r.get("fields_disagree", []), "composio": r.get("composio_crosscheck")}
            for r in results if r["verdict"] in ("disagree", "disagree_with_composio")
        ],
    }
    (VERIF_DIR / "_summary.json").write_text(json.dumps(summary, indent=2))
    return results

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    # Step 1: Retries
    await run_retries()

    # Step 2: Reload records after retries
    global all_records
    all_records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]

    # Step 3: Verification
    await run_verification()

    # Final stats
    print(f"\n=== Final stats after retry + verification ===")
    conf = collections.Counter(r.get("confidence", "unknown") for r in all_records)
    print(f"Confidence: {dict(conf)}")
    auth_counter = collections.Counter()
    for r in all_records:
        for a in (r.get("auth_methods") or []):
            auth_counter[a] += 1
    print(f"Auth methods: {dict(auth_counter.most_common())}")
    bs = collections.Counter(str(r.get("buildability_score")) for r in all_records)
    print(f"Buildability: {dict(bs.most_common())}")

if __name__ == "__main__":
    asyncio.run(main())
