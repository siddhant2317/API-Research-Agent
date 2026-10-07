"""
Composio Take-Home: App Research Agent
=======================================
Core agent that researches one app's API/auth/buildability profile.

Stack:
  - Search:  z-ai function -n web_search  (finds canonical docs URLs + gives snippets)
  - Fetch:   requests + html2text         (works for ~80% of docs sites)
  - Extract: GLM-4.5-flash via Z.ai API   (thinking:disabled for speed)
  - Verify:  GLM-4.5-flash (thinking:enabled) + z-ai chat (glm-4-plus) on disputes
  - MCP:     Direct queries to glama.ai / mcp.so / smithery.ai search APIs

Outputs per app:
  /home/z/my-project/data/apps/<slug>.json   — the research record
  /home/z/my-project/data/audit/<slug>.json  — full audit trail (URLs fetched, model calls, etc.)
"""
import os
from __future__ import annotations
import asyncio
import json
import re
import subprocess
import time
import hashlib
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Literal, Any
from urllib.parse import urlparse

import httpx
import html2text

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
GLM_KEY = os.environ.get("GLM_KEY", "")
GLM_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_HEADERS = {"Authorization": f"Bearer {GLM_KEY}", "Content-Type": "application/json"}
GLM_MODEL = "glm-4.5-flash"  # only free-tier model on this key

# Composio API (now we have a key!)
COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")
COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1/toolkits"
COMPOSIO_HEADERS = {"Authorization": f"Bearer {COMPOSIO_KEY}", "Content-Type": "application/json"}

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
AUDIT_DIR = DATA_DIR / "audit"
CACHE_DIR = DATA_DIR / "cache"
APPS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Concurrency & politeness
MAX_CONCURRENT = 4
FETCH_TIMEOUT = 20
HTTP_TIMEOUT = httpx.Timeout(FETCH_TIMEOUT, connect=10)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

h2t = html2text.HTML2Text()
h2t.ignore_links = False
h2t.ignore_images = True
h2t.body_width = 0
h2t.ignore_emphasis = True

def html_to_md(html: str) -> str:
    md = h2t.handle(html)
    md = re.sub(r"\n\s*\n\s*\n+", "\n\n", md).strip()
    return md

# ---------------------------------------------------------------------------
# Z-AI CLI WRAPPER (for web_search and chat)
# ---------------------------------------------------------------------------
async def z_ai_function(name: str, args: dict, timeout: int = 30) -> Any:
    """Call z-ai CLI function (e.g., web_search). Returns parsed JSON or None on error."""
    cmd = ["z-ai", "function", "-n", name, "-a", json.dumps(args)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        # z-ai CLI prints "🚀 Initializing..." header then JSON. Extract JSON.
        # Find first [ or { and parse from there
        for i, c in enumerate(out):
            if c in "[{":
                try:
                    return json.loads(out[i:])
                except json.JSONDecodeError:
                    # try to find the matching end
                    pass
        return None
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        log(f"  z_ai_function({name}) error: {e}")
        return None

async def z_ai_chat(prompt: str, system: str = "", thinking: bool = False, timeout: int = 60) -> Optional[str]:
    """Call z-ai chat (uses glm-4-plus internally via SDK auth). Returns content string or None."""
    cmd = ["z-ai", "chat", "-p", prompt]
    if system:
        cmd.extend(["-s", system])
    if thinking:
        cmd.append("-t")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace")
        # parse JSON response
        for i, c in enumerate(out):
            if c == "{":
                try:
                    data = json.loads(out[i:])
                    return data["choices"][0]["message"]["content"]
                except:
                    break
        return None
    except Exception as e:
        log(f"  z_ai_chat error: {e}")
        return None

# ---------------------------------------------------------------------------
# GLM API (direct HTTP)
# ---------------------------------------------------------------------------
async def glm_chat(
    messages: list[dict],
    *,
    thinking_enabled: bool = False,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 3000,
    timeout: int = 90,
    retries: int = 3,
) -> Optional[str]:
    """Call GLM-4.5-flash with optional thinking and JSON mode."""
    payload: dict[str, Any] = {
        "model": GLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if not thinking_enabled:
        payload["thinking"] = {"type": "disabled"}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15)) as client:
        for attempt in range(retries):
            try:
                r = await client.post(GLM_BASE, headers=GLM_HEADERS, json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                elif r.status_code == 429:
                    wait = 5 * (attempt + 1)
                    log(f"  GLM 429, waiting {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    log(f"  GLM HTTP {r.status_code}: {r.text[:200]}")
                    return None
            except Exception as e:
                log(f"  GLM error: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(3)
    return None

# ---------------------------------------------------------------------------
# URL FETCH (with caching)
# ---------------------------------------------------------------------------
async def fetch_url(url: str, *, client: httpx.AsyncClient, allow_cache: bool = True) -> tuple[int, str]:
    """Fetch URL and return (status, markdown). Caches by URL hash."""
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if allow_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            return cached["status"], cached["markdown"]
        except:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = await client.get(url, headers=headers, follow_redirects=True)
        status = r.status_code
        if status == 200 and "text/" in r.headers.get("content-type", ""):
            md = html_to_md(r.text)
        else:
            md = ""
    except Exception as e:
        status = 0
        md = ""

    if allow_cache:
        cache_file.write_text(json.dumps({"url": url, "status": status, "markdown": md, "fetched_at": time.time()}))
    return status, md

# ---------------------------------------------------------------------------
# MCP REGISTRY LOOKUP
# ---------------------------------------------------------------------------
async def lookup_composio(app_name: str, *, client: httpx.AsyncClient) -> Optional[dict]:
    """Query Composio's toolkit registry for this app. Returns the toolkit dict or None.
    This is GROUND TRUTH for auth schemes, tool counts, and version — much more
    reliable than docs scraping.
    """
    try:
        # Try direct search
        r = await client.get(
            COMPOSIO_BASE,
            headers=COMPOSIO_HEADERS,
            params={"search": app_name, "limit": 10},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        # Match by name (case-insensitive exact)
        name_lower = app_name.lower().strip()
        for item in items:
            if item.get("name", "").lower().strip() == name_lower:
                return item
        # Fuzzy: try the first item if its name contains our query
        for item in items:
            if name_lower in item.get("name", "").lower():
                return item
        return None
    except Exception as e:
        log(f"  composio lookup error: {e}")
        return None

async def lookup_mcp_registries(app_name: str, *, client: httpx.AsyncClient) -> list[dict]:
    """Check Glama, mcp.so, Smithery, and GitHub for existing MCP servers."""
    hits: list[dict] = []
    queries = [
        app_name.lower(),
        f"{app_name.lower()} mcp",
        f"{app_name.lower()} mcp server",
    ]

    # 1. Glama.ai
    try:
        r = await client.get(
            "https://glama.ai/api/mcp/servers",
            params={"search": app_name},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            servers = data if isinstance(data, list) else data.get("servers", data.get("data", []))
            for s in servers[:5]:
                hits.append({
                    "registry": "glama.ai",
                    "name": s.get("name", ""),
                    "url": f"https://glama.ai/mcp/servers/{s.get('slug', s.get('id', ''))}",
                    "description": (s.get("description") or "")[:200],
                })
    except Exception:
        pass

    # 2. mcp.so — no clean JSON API; use web_search as proxy
    # (We use z-ai web_search as a fallback for "site:mcp.so {app_name}")

    # 3. Smithery
    try:
        r = await client.get(
            "https://smithery.ai/api/servers",
            params={"q": app_name},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            servers = data if isinstance(data, list) else data.get("servers", [])
            for s in servers[:5]:
                hits.append({
                    "registry": "smithery.ai",
                    "name": s.get("name", s.get("qualifiedName", "")),
                    "url": f"https://smithery.ai/server/{s.get('qualifiedName', s.get('name', ''))}",
                    "description": (s.get("description") or "")[:200],
                })
    except Exception:
        pass

    # 4. Web search for "{app} MCP server github"
    search_results = await z_ai_function("web_search", {"query": f"{app_name} MCP server site:github.com", "num": 5})
    if search_results:
        for r in search_results:
            url = r.get("url", "")
            if "github.com" in url and "mcp" in (r.get("name", "") + url).lower():
                hits.append({
                    "registry": "github (via search)",
                    "name": r.get("name", "")[:120],
                    "url": url,
                    "description": (r.get("snippet") or "")[:200],
                })

    # 5. Web search for "{app} MCP server" (broader)
    search_results2 = await z_ai_function("web_search", {"query": f"{app_name} MCP server", "num": 5})
    if search_results2:
        for r in search_results2:
            url = r.get("url", "")
            name = r.get("name", "")
            if app_name.lower() in name.lower() and "mcp" in name.lower():
                hits.append({
                    "registry": "web search",
                    "name": name[:120],
                    "url": url,
                    "description": (r.get("snippet") or "")[:200],
                })

    # Dedupe by URL
    seen = set()
    unique: list[dict] = []
    for h in hits:
        if h["url"] not in seen:
            seen.add(h["url"])
            unique.append(h)
    return unique

# ---------------------------------------------------------------------------
# EXTRACTION (the core LLM call)
# ---------------------------------------------------------------------------
EXTRACT_SYSTEM = """You are an expert at API research. You extract structured facts about developer APIs from documentation.
You always cite evidence — every claim must be backed by a verbatim quote from the docs.
You are honest: if the docs don't say something, you say "unknown" rather than guess.
Return JSON only, no markdown, no commentary."""

EXTRACT_PROMPT_TEMPLATE = """Research the app "{app_name}" (category: {category}).

Official docs URL: {docs_url}
App website: {website}

I have fetched and converted the docs to markdown. Below are the raw materials:

=== SEARCH RESULTS (top hits for "{app_name} API authentication") ===
{search_snippets}

=== FETCHED DOCS (markdown, may be truncated) ===
DOCS URL: {docs_url}
HTTP STATUS: {docs_status}
CONTENT:
{docs_md}

=== ADDITIONAL FETCHED PAGES ===
{extra_pages}

=== COMPOSIO REGISTRY ===
{composio_data}

=== MCP REGISTRY HITS (non-Composio) ===
{mcp_hits}

Extract the following as JSON. Be CONSERVATIVE — only assert what the evidence supports.

{{
  "app_name": string,
  "category": "{category}",
  "one_line_description": string (what the app does, in <=12 words),
  "auth_methods": array of strings, each one of: "oauth2", "api_key", "basic", "bearer_token", "jwt", "session_cookie", "webhook_signature", "mtls", "none", "other",
  "auth_methods_evidence": string (verbatim quote from docs supporting the auth methods),
  "self_serve": boolean (true if a developer can obtain credentials themselves, free or trial, without contacting sales/admin/partner),
  "self_serve_evidence": string (verbatim quote, or note if signup is gated),
  "gating_type": one of "free", "free_trial", "paid_required", "contact_sales", "partner_program", "admin_approval", "enterprise_only", "unknown",
  "api_surface_breadth": one of "broad" (50+ endpoints / GraphQL), "medium" (10-50 endpoints), "narrow" (<10 endpoints), "unknown",
  "api_protocol": array of strings, each one of "rest", "graphql", "grpc", "webhook", "soap", "ws", "other",
  "endpoint_count_estimate": integer or null,
  "openapi_spec_available": boolean,
  "mcp_server_exists": boolean (true if any MCP registry hits above are real matches — INCLUDES Composio),
  "mcp_server_sources": array of strings (URLs from the registry hits above, or "composio:<slug>" if Composio-supported),
  "composio_supported": boolean (true if the app was found in Composio's registry above),
  "composio_auth_schemes": array of strings or null (the auth_schemes field from Composio, or null if not in Composio),
  "composio_tools_count": integer or null (tools_count from Composio, or null),
  "buildability_score": integer 0-5 (5 = ready to ship as agent toolkit today, 0 = blocked entirely),
  "buildability_rationale": string (one sentence why),
  "main_blocker": one of "none", "auth_complexity", "gated_access", "poor_docs", "no_public_api", "rate_limits", "legal_terms", "technical_instability", "unknown",
  "evidence_urls": array of strings (URLs that support the findings above),
  "confidence": one of "high", "medium", "low",
  "agent_notes": string (any caveats the human reviewer should know)
}}

RULES:
- If the docs are empty/blocked, say so in agent_notes and use "unknown" for fields you can't determine.
- For "self_serve": "free" or "free_trial" gating = true; "contact_sales"/"partner_program"/"enterprise_only" = false.
- For "mcp_server_exists": true if Composio-supported OR any non-Composio MCP registry hit is clearly for this app.
- For "buildability_score": consider (a) auth friction, (b) docs quality, (c) API breadth, (d) gating, (e) MCP exists.
  5 = self-serve + good docs + broad API + OAuth2 or API key + no gating + (optionally) Composio-supported.
  0 = no public API, or hard enterprise gate with no trial.
- Always include at least one evidence_url (the docs_url at minimum).
- If Composio data is present, USE IT for auth_methods and tools_count — it's ground truth from a registry that already integrated this app.
  But still verify self_serve and gating from the actual docs (Composio doesn't tell you if a developer can self-onboard)."""

async def extract_app_research(
    app: dict,
    *,
    docs_md: str,
    docs_status: int,
    search_snippets: str,
    extra_pages: str,
    mcp_hits: list[dict],
    composio_data: Optional[dict] = None,
    thinking_enabled: bool = False,
) -> Optional[dict]:
    """Run the extraction LLM call. Returns parsed dict or None."""
    composio_str = "(not in Composio registry)"
    if composio_data:
        composio_str = json.dumps({
            "name": composio_data.get("name"),
            "slug": composio_data.get("slug"),
            "auth_schemes": composio_data.get("auth_schemes"),
            "composio_managed_auth_schemes": composio_data.get("composio_managed_auth_schemes"),
            "no_auth": composio_data.get("no_auth"),
            "is_local_toolkit": composio_data.get("is_local_toolkit"),
            "tools_count": composio_data.get("meta", {}).get("tools_count"),
            "triggers_count": composio_data.get("meta", {}).get("triggers_count"),
            "app_url": composio_data.get("meta", {}).get("app_url"),
            "categories": [c.get("name") for c in composio_data.get("meta", {}).get("categories", [])],
            "version": composio_data.get("meta", {}).get("version"),
            "description": composio_data.get("meta", {}).get("description"),
        }, indent=2)

    prompt = EXTRACT_PROMPT_TEMPLATE.format(
        app_name=app["name"],
        category=app["category"],
        docs_url=app["docs_url"],
        website=app.get("website", ""),
        search_snippets=search_snippets[:3000],
        docs_md=docs_md[:12000],
        docs_status=docs_status,
        extra_pages=extra_pages[:6000],
        composio_data=composio_str,
        mcp_hits=json.dumps(mcp_hits, indent=2)[:2000] if mcp_hits else "(no MCP registry hits found)",
    )

    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    raw = await glm_chat(
        messages,
        thinking_enabled=thinking_enabled,
        json_mode=True,
        temperature=0.2 if not thinking_enabled else 0.4,
        max_tokens=3500 if not thinking_enabled else 6000,
        timeout=120,
    )
    if not raw:
        return None
    try:
        # Sometimes GLM wraps in ```json ... ``` — strip if so
        raw_stripped = raw.strip()
        if raw_stripped.startswith("```"):
            raw_stripped = re.sub(r"^```(?:json)?\s*", "", raw_stripped)
            raw_stripped = re.sub(r"\s*```$", "", raw_stripped)
        return json.loads(raw_stripped)
    except json.JSONDecodeError as e:
        log(f"  JSON parse error for {app['name']}: {e}")
        log(f"  Raw (first 500): {raw[:500]}")
        return None

# ---------------------------------------------------------------------------
# MAIN: research one app
# ---------------------------------------------------------------------------
async def research_one_app(app: dict) -> dict:
    """Full research pipeline for one app. Returns the research record + audit trail."""
    app_slug = slug(app["name"])
    audit: dict = {
        "app_id": app["id"],
        "app_name": app["name"],
        "app_slug": app_slug,
        "started_at": time.time(),
        "fetched_urls": [],
        "model_calls": [],
        "errors": [],
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # 1. Fetch the docs URL
            log(f"  [{app_slug}] fetching docs...")
            status, docs_md = await fetch_url(app["docs_url"], client=client)
            audit["fetched_urls"].append({"url": app["docs_url"], "status": status, "md_len": len(docs_md)})

            # 2. If docs failed or are very thin, search for the canonical docs URL and try again
            extra_pages_md = ""
            if status != 200 or len(docs_md) < 500:
                log(f"  [{app_slug}] docs thin (status={status}, len={len(docs_md)}), searching for better URL...")
                search_q = f"{app['name']} API documentation authentication"
                search_results = await z_ai_function("web_search", {"query": search_q, "num": 5}, timeout=30)
                if search_results:
                    for sr in search_results[:2]:
                        alt_url = sr.get("url", "")
                        if alt_url and alt_url != app["docs_url"]:
                            alt_status, alt_md = await fetch_url(alt_url, client=client)
                            audit["fetched_urls"].append({"url": alt_url, "status": alt_status, "md_len": len(alt_md), "via": "search_fallback"})
                            if alt_status == 200 and len(alt_md) > len(docs_md):
                                docs_md = alt_md
                                status = alt_status
                                audit["primary_docs_url_used"] = alt_url

            # 3. Run web_search to get snippets (always useful, even if docs fetched)
            search_snippets = ""
            search_results = await z_ai_function("web_search", {"query": f"{app['name']} API authentication oauth api key", "num": 5}, timeout=30)
            if search_results:
                search_snippets = "\n\n".join([
                    f"URL: {r.get('url', '')}\nTitle: {r.get('name', '')}\nSnippet: {r.get('snippet', '')}"
                    for r in search_results
                ])

            # 4. Look up MCP registries
            log(f"  [{app_slug}] checking Composio + MCP registries...")
            composio_data = await lookup_composio(app["name"], client=client)
            audit["composio_lookup"] = {
                "found": composio_data is not None,
                "slug": composio_data.get("slug") if composio_data else None,
                "auth_schemes": composio_data.get("auth_schemes") if composio_data else None,
                "tools_count": composio_data.get("meta", {}).get("tools_count") if composio_data else None,
            }
            mcp_hits = await lookup_mcp_registries(app["name"], client=client)
            audit["mcp_hits"] = mcp_hits

            # 5. Run extraction
            log(f"  [{app_slug}] extracting (composio={'yes' if composio_data else 'no'})...")
            t0 = time.time()
            extracted = await extract_app_research(
                app,
                docs_md=docs_md,
                docs_status=status,
                search_snippets=search_snippets,
                extra_pages=extra_pages_md,
                mcp_hits=mcp_hits,
                composio_data=composio_data,
                thinking_enabled=False,  # fast pass
            )
            audit["model_calls"].append({
                "step": "extract_fast",
                "model": GLM_MODEL,
                "thinking_enabled": False,
                "duration_s": round(time.time() - t0, 2),
                "success": extracted is not None,
            })

            if not extracted:
                audit["errors"].append("extraction_failed")
                extracted = {
                    "app_name": app["name"],
                    "category": app["category"],
                    "agent_notes": "Extraction failed; record is empty.",
                    "confidence": "low",
                }

            # 6. Assemble final record
            record = {
                "id": app["id"],
                "app_name": app["name"],
                "app_slug": app_slug,
                "category": app["category"],
                "website": app.get("website", ""),
                "docs_url": app["docs_url"],
                "primary_docs_url_used": audit.get("primary_docs_url_used", app["docs_url"]),
                **extracted,
                "audit_summary": {
                    "fetched_url_count": len(audit["fetched_urls"]),
                    "mcp_hit_count": len(mcp_hits),
                    "errors": audit["errors"],
                },
                "researched_at": time.time(),
            }

            # 7. Save
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(record, indent=2))
            audit["completed_at"] = time.time()
            audit["duration_s"] = round(audit["completed_at"] - audit["started_at"], 2)
            (AUDIT_DIR / f"{app_slug}.json").write_text(json.dumps(audit, indent=2))

            return record

    except Exception as e:
        audit["errors"].append(f"unhandled: {str(e)}")
        audit["traceback"] = traceback.format_exc()
        (AUDIT_DIR / f"{app_slug}.json").write_text(json.dumps(audit, indent=2))
        log(f"  [{app_slug}] UNHANDLED ERROR: {e}")
        return {
            "id": app["id"],
            "app_name": app["name"],
            "app_slug": app_slug,
            "category": app["category"],
            "docs_url": app["docs_url"],
            "agent_notes": f"Research failed: {e}",
            "confidence": "low",
        }

# ---------------------------------------------------------------------------
# BATCH RUNNER
# ---------------------------------------------------------------------------
async def main(apps_to_run: list[dict] | None = None, concurrency: int = MAX_CONCURRENT):
    """Run the agent on a list of apps. Defaults to all 100."""
    if apps_to_run is None:
        apps_to_run = json.loads((DATA_DIR / "apps.json").read_text())

    log(f"Starting research on {len(apps_to_run)} apps (concurrency={concurrency})")
    sem = asyncio.Semaphore(concurrency)

    async def bounded(app):
        async with sem:
            log(f"=> {app['name']} (id={app['id']})")
            t0 = time.time()
            result = await research_one_app(app)
            log(f"<= {app['name']} done in {time.time()-t0:.1f}s (confidence={result.get('confidence','?')})")
            return result

    t_start = time.time()
    results = await asyncio.gather(*[bounded(a) for a in apps_to_run])
    log(f"\nAll done in {time.time()-t_start:.1f}s. Results saved to {APPS_DIR}/")

    # Quick stats
    ok = sum(1 for r in results if r.get("confidence") in ("high", "medium"))
    log(f"Records with medium+ confidence: {ok}/{len(results)}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Pilot mode: pass app ids to run
        ids = [int(x) for x in sys.argv[1:]]
        all_apps = json.loads((DATA_DIR / "apps.json").read_text())
        apps_to_run = [a for a in all_apps if a["id"] in ids]
        asyncio.run(main(apps_to_run, concurrency=2))
    else:
        asyncio.run(main())
