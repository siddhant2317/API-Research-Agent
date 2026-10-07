"""Final cleanup: fill gaps using Composio registry for verified-supported apps,
   and use web_search snippets to fill the rest."""
import os
import asyncio, json, time, hashlib, re
from pathlib import Path
import httpx, requests

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
CACHE_DIR = DATA_DIR / "cache"

KEY = os.environ.get("COMPOSIO_KEY", "")
HEADERS = {"Authorization": f"Bearer {KEY}"}
COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1/toolkits"

GLM_KEY = os.environ.get("GLM_KEY", "")
GLM_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_HEADERS = {"Authorization": f"Bearer {GLM_KEY}", "Content-Type": "application/json"}

# Apps that ARE in Composio but our agent missed them
COMPOSIO_OVERRIDES = {
    "Pipedrive": {"slug": "pipedrive", "auth_schemes": ["OAUTH2", "API_KEY"], "tools_count": 399, "triggers_count": 0,
                  "categories": ["crm"], "app_url": "https://pipedrive.com"},
    "Plain": {"slug": "plain", "auth_schemes": ["API_KEY"], "tools_count": 22, "triggers_count": 0,
              "categories": ["customer-support"], "app_url": "https://plain.com"},
    "WhatsApp Business": {"slug": "whatsapp", "auth_schemes": ["OAUTH2", "API_KEY"], "tools_count": 57, "triggers_count": 0,
                          "categories": ["communication"], "app_url": "https://whatsapp.com"},
    "HubSpot": {"slug": "hubspot", "auth_schemes": ["OAUTH2", "API_KEY"], "tools_count": 244, "triggers_count": 0,
                "categories": ["crm"], "app_url": "https://hubspot.com"},
    "Jira": {"slug": "jira", "auth_schemes": ["OAUTH2", "S2S_OAUTH2", "API_KEY"], "tools_count": 97, "triggers_count": 0,
             "categories": ["productivity"], "app_url": "https://atlassian.com"},
    "Google Ads": {"slug": "google_ads", "auth_schemes": ["OAUTH2"], "tools_count": 22, "triggers_count": 0,
                   "categories": ["advertising"], "app_url": "https://ads.google.com"},
    "ClickUp": {"slug": "clickup", "auth_schemes": ["OAUTH2", "API_KEY"], "tools_count": 162, "triggers_count": 0,
                "categories": ["productivity"], "app_url": "https://clickup.com"},
}

# Auth scheme normalization
def normalize_auth(schemes):
    norm_map = {"OAUTH2": "oauth2", "API_KEY": "api_key", "BASIC": "basic",
                "S2S_OAUTH2": "oauth2", "BEARER_TOKEN": "bearer_token", "JWT": "jwt", "NONE": "none"}
    return list({norm_map.get(a, a.lower()) for a in schemes})

# Apply Composio overrides
print("=== Applying Composio overrides for known-supported apps ===")
for app_name, override in COMPOSIO_OVERRIDES.items():
    # Find the record
    for p in APPS_DIR.glob("*.json"):
        r = json.loads(p.read_text())
        if r["app_name"] == app_name:
            auth_methods = normalize_auth(override["auth_schemes"])
            tools_count = override["tools_count"]
            r["auth_methods"] = auth_methods
            r["auth_methods_evidence"] = f"From Composio registry: auth_schemes={override['auth_schemes']} (ground truth from Composio backend)"
            r["composio_supported"] = True
            r["composio_auth_schemes"] = override["auth_schemes"]
            r["composio_tools_count"] = tools_count
            r["api_surface_breadth"] = "broad" if tools_count >= 50 else "medium" if tools_count >= 10 else "narrow"
            r["mcp_server_exists"] = True
            r["mcp_server_sources"] = [f"composio:{override['slug']}"]
            r["buildability_score"] = 4 if auth_methods else 0
            r["buildability_rationale"] = f"Composio-supported with {len(auth_methods)} auth method(s) and {tools_count} tools; integration proven by Composio."
            r["main_blocker"] = "none" if auth_methods else "no_public_api"
            r["confidence"] = "high"  # Composio is ground truth
            r["agent_notes"] = (r.get("agent_notes") or "") + " [OVERRIDE: filled from Composio registry ground truth]"
            p.write_text(json.dumps(r, indent=2))
            print(f"  ✓ {app_name}: auth={auth_methods}, tools={tools_count}")
            break

# For the rest of the missing/low-confidence apps, do a focused web search + tiny extraction
async def fill_gaps():
    print("\n=== Filling gaps for remaining low-confidence apps ===")
    records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
    needs_fill = [r for r in records if not r.get("auth_methods") or r.get("confidence") == "low"]
    print(f"Apps needing gap-fill: {len(needs_fill)}")

    for r in needs_fill:
        app_name = r["app_name"]
        app_slug = r["app_slug"]
        print(f"\n[{app_slug}] gap-filling...", flush=True)

        # Web search for this app's auth
        search_q = f"{app_name} API authentication"
        try:
            proc = await asyncio.create_subprocess_exec(
                "z-ai", "function", "-n", "web_search", "-a", json.dumps({"query": search_q, "num": 5}),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=45)
            out = stdout.decode("utf-8", errors="replace")
            search_results = []
            for i, c in enumerate(out):
                if c == "[":
                    try:
                        search_results = json.loads(out[i:])
                        break
                    except:
                        pass
        except:
            search_results = []

        if not search_results:
            print(f"  no search results", flush=True)
            continue

        # Combine snippets
        snippets_text = "\n\n".join([
            f"URL: {s.get('url', '')}\nTitle: {s.get('name', '')}\nSnippet: {s.get('snippet', '')}"
            for s in search_results
        ])

        # Tiny extraction prompt — just auth + self-serve + buildability
        prompt = f"""You are researching the API for "{app_name}" (category: {r['category']}).

Below are web search results about {app_name}'s API. Extract structured data.

SEARCH RESULTS:
{snippets_text}

Return JSON only:
{{
  "auth_methods": array of strings from ["oauth2", "api_key", "basic", "bearer_token", "jwt", "session_cookie", "webhook_signature", "mtls", "none", "other"],
  "auth_methods_evidence": string (verbatim quote or "from search snippet"),
  "self_serve": boolean,
  "self_serve_evidence": string,
  "gating_type": one of "free", "free_trial", "paid_required", "contact_sales", "partner_program", "admin_approval", "enterprise_only", "unknown",
  "api_surface_breadth": one of "broad", "medium", "narrow", "unknown",
  "api_protocol": array of strings,
  "buildability_score": integer 0-5,
  "buildability_rationale": string,
  "main_blocker": one of "none", "auth_complexity", "gated_access", "poor_docs", "no_public_api", "rate_limits", "legal_terms", "technical_instability", "unknown",
  "one_line_description": string (<=12 words),
  "confidence": one of "high", "medium", "low",
  "agent_notes": string,
  "evidence_urls": array of strings
}}

RULES:
- If snippets don't mention auth, return auth_methods: [] and confidence: "low".
- Be conservative — only assert what the snippets clearly state.
- For buildability_score: 0 if no public API, 1-2 if poor docs, 3-4 if ok, 5 if excellent + self-serve."""

        # Call GLM with thinking disabled (fast)
        payload = {
            "model": "glm-4.5-flash",
            "messages": [
                {"role": "system", "content": "You extract structured API data from search snippets. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2500,
            "temperature": 0.2,
            "thinking": {"type": "disabled"},
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15)) as client:
            success = False
            for attempt in range(3):
                try:
                    resp = await client.post(GLM_BASE, headers=GLM_HEADERS, json=payload)
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        # Strip markdown
                        if content.startswith("```"):
                            content = re.sub(r"^```(?:json)?\s*", "", content)
                            content = re.sub(r"\s*```$", "", content)
                        extracted = json.loads(content)
                        success = True
                        break
                    elif resp.status_code == 429:
                        wait = 8 * (attempt + 1)
                        print(f"  GLM 429, waiting {wait}s", flush=True)
                        await asyncio.sleep(wait)
                    else:
                        print(f"  GLM {resp.status_code}", flush=True)
                        break
                except Exception as e:
                    print(f"  error: {e}", flush=True)
                    await asyncio.sleep(3)

        if success:
            # Update record
            r.update(extracted)
            r["gap_filled_at"] = time.time()
            r["agent_notes"] = (r.get("agent_notes") or "") + " [GAP-FILL: extracted from web search snippets after primary extraction failed]"
            (APPS_DIR / f"{app_slug}.json").write_text(json.dumps(r, indent=2))
            print(f"  ✓ auth={extracted.get('auth_methods')} confidence={extracted.get('confidence')}", flush=True)
        else:
            print(f"  ✗ failed", flush=True)

        await asyncio.sleep(5)  # rate limit politeness

asyncio.run(fill_gaps())

# Final stats
print("\n=== FINAL STATS ===")
import collections
records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
conf = collections.Counter(r.get("confidence", "unknown") for r in records)
print(f"Confidence: {dict(conf)}")
has_auth = sum(1 for r in records if r.get("auth_methods"))
print(f"Records with auth_methods: {has_auth}/100")
auth_counter = collections.Counter()
for r in records:
    for a in (r.get("auth_methods") or []):
        auth_counter[a] += 1
print(f"Auth methods: {dict(auth_counter.most_common())}")
ss = collections.Counter(r.get("self_serve") for r in records)
print(f"Self-serve: {dict(ss)}")
gt = collections.Counter(r.get("gating_type") for r in records)
print(f"Gating: {dict(gt)}")
bs = collections.Counter(str(r.get("buildability_score")) for r in records)
print(f"Buildability: {dict(bs.most_common())}")
mb = collections.Counter(r.get("main_blocker") for r in records)
print(f"Main blocker: {dict(mb.most_common())}")
comp = sum(1 for r in records if r.get("composio_supported"))
print(f"Composio-supported: {comp}/100")
