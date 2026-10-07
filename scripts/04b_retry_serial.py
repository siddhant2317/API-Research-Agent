"""Sequential retry + verify with aggressive rate-limit handling.
   Run one app at a time, with 5s sleep between calls."""
import asyncio, json, time, hashlib, collections, sys
from pathlib import Path
import httpx

sys.path.insert(0, "/home/z/my-project/scripts")
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

# Identify apps needing retry
all_apps = json.loads((DATA_DIR / "apps.json").read_text())
records = {json.loads(p.read_text())["app_name"]: json.loads(p.read_text()) for p in APPS_DIR.glob("*.json")}

needs_retry = []
for app in all_apps:
    r = records.get(app["name"])
    if not r:
        continue
    is_empty = "Extraction failed" in (r.get("agent_notes") or "") or not r.get("auth_methods")
    if is_empty:
        needs_retry.append((app, r))

print(f"=== {len(needs_retry)} apps need retry ===")
for app, _ in needs_retry:
    print(f"  - {app['name']}")

async def retry_one_serial(app: dict) -> dict:
    """Retry one app, sequentially, with thinking enabled and patient waits."""
    app_slug = agent.slug(app["name"])
    audit_path = AUDIT_DIR / f"{app_slug}.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}

    # Get cached docs
    docs_url = app["docs_url"]
    cache_key = hashlib.md5(docs_url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    docs_md = ""
    docs_status = 0
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        docs_md = cached.get("markdown", "")
        docs_status = cached.get("status", 0)

    # Try audit's fetched_urls for fallback
    if len(docs_md) < 500 and audit.get("fetched_urls"):
        for fu in audit["fetched_urls"]:
            if fu.get("md_len", 0) > 500:
                alt_key = hashlib.md5(fu["url"].encode()).hexdigest()
                alt_file = CACHE_DIR / f"{alt_key}.json"
                if alt_file.exists():
                    alt_cached = json.loads(alt_file.read_text())
                    if len(alt_cached.get("markdown", "")) > len(docs_md):
                        docs_md = alt_cached["markdown"]
                        docs_status = alt_cached["status"]
                        docs_url = fu["url"]
                        break

    async with httpx.AsyncClient(timeout=agent.HTTP_TIMEOUT) as client:
        # Re-search
        print(f"  [{app_slug}] searching...", flush=True)
        await asyncio.sleep(3)  # polite
        search_results = await agent.z_ai_function("web_search", {"query": f"{app['name']} API authentication oauth api key", "num": 5}, timeout=45)
        search_snippets = ""
        if search_results:
            search_snippets = "\n\n".join([
                f"URL: {r.get('url', '')}\nTitle: {r.get('name', '')}\nSnippet: {r.get('snippet', '')}"
                for r in search_results
            ])

        # Try fetching one of the search results if docs are thin
        if len(docs_md) < 500 and search_results:
            for sr in search_results[:3]:
                alt_url = sr.get("url", "")
                if alt_url and alt_url != app["docs_url"]:
                    try:
                        alt_status, alt_md = await agent.fetch_url(alt_url, client=client)
                        if alt_status == 200 and len(alt_md) > len(docs_md):
                            docs_md = alt_md
                            docs_status = alt_status
                            docs_url = alt_url
                            print(f"  [{app_slug}] using fallback URL: {alt_url}", flush=True)
                            break
                    except:
                        pass

        # Composio lookup
        await asyncio.sleep(2)
        composio_data = await agent.lookup_composio(app["name"], client=client)
        await asyncio.sleep(2)
        mcp_hits = await agent.lookup_mcp_registries(app["name"], client=client)

        # Extract with thinking
        print(f"  [{app_slug}] extracting (thinking=on, docs_len={len(docs_md)}, composio={'yes' if composio_data else 'no'})", flush=True)
        # Wait extra to avoid rate limit
        await asyncio.sleep(5)
        t0 = time.time()
        extracted = await agent.extract_app_research(
            app,
            docs_md=docs_md,
            docs_status=docs_status,
            search_snippets=search_snippets,
            extra_pages="",
            mcp_hits=mcp_hits,
            composio_data=composio_data,
            thinking_enabled=True,
        )
        print(f"  [{app_slug}] done in {time.time()-t0:.1f}s, success={extracted is not None}", flush=True)

        if extracted:
            old_record = records[app["name"]]
            new_record = {**old_record, **extracted,
                "id": old_record["id"], "app_name": old_record["app_name"], "app_slug": app_slug,
                "category": old_record["category"], "website": old_record.get("website", ""),
                "docs_url": old_record["docs_url"], "primary_docs_url_used": docs_url,
                "retried_at": time.time(),
                "audit_summary": {**old_record.get("audit_summary", {}), "retry_thinking_enabled": True, "retry_succeeded": True},
            }
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(new_record, indent=2))
            return new_record
        elif composio_data:
            # Fallback to Composio
            auth_schemes = composio_data.get("auth_schemes", [])
            norm_map = {"OAUTH2": "oauth2", "API_KEY": "api_key", "BASIC": "basic", "S2S_OAUTH2": "oauth2", "BEARER_TOKEN": "bearer_token", "JWT": "jwt", "NONE": "none"}
            auth_methods = list({norm_map.get(a, a.lower()) for a in auth_schemes})
            tools_count = composio_data.get("meta", {}).get("tools_count", 0) or 0
            old_record = records[app["name"]]
            new_record = {**old_record,
                "auth_methods": auth_methods,
                "auth_methods_evidence": f"From Composio registry (extraction failed; using ground-truth auth_schemes: {auth_schemes})",
                "composio_supported": True,
                "composio_auth_schemes": auth_schemes,
                "composio_tools_count": tools_count,
                "api_surface_breadth": "broad" if tools_count >= 50 else "medium" if tools_count >= 10 else "narrow",
                "mcp_server_exists": True,
                "mcp_server_sources": [f"composio:{composio_data.get('slug')}"],
                "buildability_score": 4 if auth_methods else 0,
                "buildability_rationale": f"Composio-supported with {len(auth_methods)} auth method(s); docs verification failed but registry confirms integration is possible.",
                "main_blocker": "poor_docs",
                "confidence": "medium",
                "agent_notes": f"Extraction failed but Composio registry provides ground-truth. Tools count: {tools_count}.",
                "retried_at": time.time(),
                "audit_summary": {**old_record.get("audit_summary", {}), "retry_thinking_enabled": True, "retry_succeeded": False, "fallback_to_composio": True},
            }
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(new_record, indent=2))
            print(f"  [{app_slug}] ✓ fell back to Composio data", flush=True)
            return new_record
        else:
            print(f"  [{app_slug}] ✗ retry failed, no Composio fallback", flush=True)
            return records[app["name"]]

async def main():
    print(f"\n=== Retrying {len(needs_retry)} apps serially ===")
    for i, (app, _) in enumerate(needs_retry):
        print(f"\n[{i+1}/{len(needs_retry)}] {app['name']}", flush=True)
        try:
            await retry_one_serial(app)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
        # Sleep between apps to avoid rate limits
        if i < len(needs_retry) - 1:
            await asyncio.sleep(8)

    # Final stats
    print(f"\n=== Final stats after retries ===")
    final = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
    conf = collections.Counter(r.get("confidence", "unknown") for r in final)
    print(f"Confidence: {dict(conf)}")

if __name__ == "__main__":
    asyncio.run(main())
