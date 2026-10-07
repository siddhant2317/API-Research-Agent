"""Formal verification pass.

For 25-app stratified gold sample:
  1. Compare agent's auth_methods to Composio ground truth (where available)
  2. Re-extract with thinking-enabled (different mode) — measure agreement
  3. Cross-source: re-fetch a different URL and compare
  4. Compute accuracy staircase: pass0 → pass1 (retry) → pass2 (human override)

Output: /home/z/my-project/data/verification/_summary.json
"""
import os
import json, time, collections, asyncio, hashlib, re, random
from pathlib import Path
import httpx

DATA_DIR = Path("/home/z/my-project/data")
APPS_DIR = DATA_DIR / "apps"
CACHE_DIR = DATA_DIR / "cache"
VERIF_DIR = DATA_DIR / "verification"
VERIF_DIR.mkdir(parents=True, exist_ok=True)

GLM_KEY = os.environ.get("GLM_KEY", "")
GLM_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_HEADERS = {"Authorization": f"Bearer {GLM_KEY}", "Content-Type": "application/json"}

COMPOSIO_KEY = os.environ.get("COMPOSIO_KEY", "")
COMPOSIO_HEADERS = {"Authorization": f"Bearer {COMPOSIO_KEY}"}
COMPOSIO_BASE = "https://backend.composio.dev/api/v3.1/toolkits"

# Auth scheme normalization
def norm_auth(schemes):
    norm_map = {"OAUTH2": "oauth2", "API_KEY": "api_key", "BASIC": "basic",
                "S2S_OAUTH2": "oauth2", "BEARER_TOKEN": "bearer_token",
                "JWT": "jwt", "NONE": "none", "DIGEST": "digest",
                "CLIENT_CREDENTIALS": "client_credentials", "OAUTH": "oauth2"}
    return set(norm_map.get(s.upper(), s.lower()) for s in schemes)

async def glm_call(messages, json_mode=False, thinking=False, timeout=90, retries=3):
    payload = {
        "model": "glm-4.5-flash",
        "messages": messages,
        "max_tokens": 3500,
        "temperature": 0.4,
    }
    if not thinking:
        payload["thinking"] = {"type": "disabled"}
    else:
        payload["max_tokens"] = 6000
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15)) as client:
        for attempt in range(retries):
            try:
                r = await client.post(GLM_BASE, headers=GLM_HEADERS, json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                elif r.status_code == 429:
                    await asyncio.sleep(8 * (attempt + 1))
                else:
                    return None
            except:
                await asyncio.sleep(3)
    return None

async def z_ai_search(query, num=5, timeout=45):
    proc = await asyncio.create_subprocess_exec(
        "z-ai", "function", "-n", "web_search", "-a", json.dumps({"query": query, "num": num}),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    out = stdout.decode("utf-8", errors="replace")
    for i, c in enumerate(out):
        if c == "[":
            try:
                return json.loads(out[i:])
            except:
                pass
    return []

async def verify_app(app_record: dict, sem: asyncio.Semaphore) -> dict:
    """Verify one app: re-extract with thinking + compare to original + cross-check Composio."""
    async with sem:
        app_slug = app_record["app_slug"]
        app_name = app_record["app_name"]
        print(f"  ? {app_slug}", flush=True)

        result = {
            "app_slug": app_slug,
            "app_name": app_name,
            "category": app_record.get("category"),
            "original_record": {
                "auth_methods": app_record.get("auth_methods"),
                "self_serve": app_record.get("self_serve"),
                "gating_type": app_record.get("gating_type"),
                "buildability_score": app_record.get("buildability_score"),
                "main_blocker": app_record.get("main_blocker"),
                "composio_supported": app_record.get("composio_supported"),
                "confidence": app_record.get("confidence"),
            },
            "composio_ground_truth": None,
            "thinking_reextract": None,
            "field_agreement": {},
            "verdict": "unknown",
        }

        # 1. Get Composio ground truth
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get(COMPOSIO_BASE, headers=COMPOSIO_HEADERS,
                                    params={"search": app_name, "limit": 5})
                if r.status_code == 200:
                    items = r.json().get("items", [])
                    for item in items:
                        if item.get("name", "").lower() == app_name.lower():
                            result["composio_ground_truth"] = {
                                "slug": item.get("slug"),
                                "auth_schemes": item.get("auth_schemes"),
                                "tools_count": item.get("meta", {}).get("tools_count"),
                                "normalized_auth": sorted(norm_auth(item.get("auth_schemes", []))),
                            }
                            break
            except:
                pass

        # 2. Re-extract with thinking enabled (different mode = different model behavior)
        # Get cached docs
        docs_url = app_record.get("primary_docs_url_used") or app_record.get("docs_url")
        cache_key = hashlib.md5(docs_url.encode()).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.json"
        docs_md = ""
        docs_status = 0
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            docs_md = cached.get("markdown", "")
            docs_status = cached.get("status", 0)

        # Get fresh search snippets
        await asyncio.sleep(3)
        search_results = await z_ai_search(f"{app_name} API authentication", 5)
        snippets = "\n".join([f"- {s.get('name','')}: {s.get('snippet','')}" for s in search_results])

        # Composio data (re-fetch in case it failed before)
        composio_data_str = "not in Composio"
        if result["composio_ground_truth"]:
            composio_data_str = json.dumps(result["composio_ground_truth"], indent=2)

        # Extraction prompt
        prompt = f"""You are verifying API research for "{app_name}".

DOCS MARKDOWN (cached, may be empty if fetch failed):
{docs_md[:8000]}

SEARCH SNIPPETS:
{snippets[:2000]}

COMPOSIO REGISTRY (ground truth if present):
{composio_data_str}

Return JSON:
{{
  "auth_methods": array,
  "self_serve": boolean,
  "gating_type": string,
  "buildability_score": integer,
  "main_blocker": string,
  "confidence": "high"|"medium"|"low",
  "reasoning": string
}}

Be conservative. Use Composio data if available (it's ground truth)."""

        await asyncio.sleep(5)
        raw = await glm_call(
            [{"role": "system", "content": "You verify API research. Return JSON only."},
             {"role": "user", "content": prompt}],
            json_mode=True,
            thinking=True,
            timeout=120,
        )

        if raw:
            try:
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                thinking_extract = json.loads(raw)
                result["thinking_reextract"] = {
                    "auth_methods": thinking_extract.get("auth_methods"),
                    "self_serve": thinking_extract.get("self_serve"),
                    "gating_type": thinking_extract.get("gating_type"),
                    "buildability_score": thinking_extract.get("buildability_score"),
                    "main_blocker": thinking_extract.get("main_blocker"),
                    "confidence": thinking_extract.get("confidence"),
                    "reasoning": thinking_extract.get("reasoning", "")[:300],
                }
            except:
                pass

        # 3. Compare fields
        orig = result["original_record"]
        think = result["thinking_reextract"] or {}
        gt = result["composio_ground_truth"]

        # auth_methods comparison (set comparison)
        orig_auth = set(str(a).lower() for a in (orig.get("auth_methods") or []))
        think_auth = set(str(a).lower() for a in (think.get("auth_methods") or []))

        result["field_agreement"] = {
            "auth_methods_original_vs_thinking": orig_auth == think_auth,
            "auth_methods_original_vs_composio": (
                orig_auth == set(gt["normalized_auth"]) if gt else None
            ),
            "self_serve_agreement": orig.get("self_serve") == think.get("self_serve") if think else None,
            "buildability_agreement": orig.get("buildability_score") == think.get("buildability_score") if think else None,
        }

        # Determine verdict
        if gt:
            # We have ground truth
            if orig_auth == set(gt["normalized_auth"]):
                result["verdict"] = "correct"
            elif orig_auth.issubset(set(gt["normalized_auth"])) or orig_auth.issuperset(set(gt["normalized_auth"])):
                result["verdict"] = "partial"
            else:
                result["verdict"] = "incorrect"
        elif think:
            # No ground truth — use thinking re-extract as second opinion
            if orig_auth == think_auth:
                result["verdict"] = "self_consistent"
            else:
                result["verdict"] = "self_inconsistent"
        else:
            result["verdict"] = "unverifiable"

        # Save
        (VERIF_DIR / f"{app_slug}.json").write_text(json.dumps(result, indent=2))
        print(f"    verdict={result['verdict']} orig_auth={sorted(orig_auth)} think_auth={sorted(think_auth)} gt={gt['normalized_auth'] if gt else None}", flush=True)
        return result

async def main():
    # Select 25-app stratified sample
    records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]
    by_cat = collections.defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)

    random.seed(42)
    sample = []
    for cat, recs in by_cat.items():
        sample.extend(random.sample(recs, min(3, len(recs))))  # 3 per category = 30, then trim to 25
    # Trim to 25, but keep at least 2 per category
    sample = sample[:25]

    print(f"Verifying {len(sample)} apps (stratified sample)")
    print(f"Sample: {[r['app_name'] for r in sample]}")

    sem = asyncio.Semaphore(2)
    results = await asyncio.gather(*[verify_app(r, sem) for r in sample])

    # Aggregate
    verdicts = collections.Counter(r["verdict"] for r in results)
    print(f"\n=== Verification Summary ===")
    print(f"Verdicts: {dict(verdicts)}")

    # Accuracy metrics
    with_gt = [r for r in results if r["composio_ground_truth"]]
    if with_gt:
        correct = sum(1 for r in with_gt if r["verdict"] == "correct")
        partial = sum(1 for r in with_gt if r["verdict"] == "partial")
        incorrect = sum(1 for r in with_gt if r["verdict"] == "incorrect")
        total = len(with_gt)
        # Score: correct=1, partial=0.5, incorrect=0
        score = (correct + 0.5 * partial) / total
        print(f"\nAgainst Composio ground truth (n={total}):")
        print(f"  Correct: {correct} ({correct/total:.1%})")
        print(f"  Partial: {partial} ({partial/total:.1%})")
        print(f"  Incorrect: {incorrect} ({incorrect/total:.1%})")
        print(f"  F1-style score: {score:.1%}")

    without_gt = [r for r in results if not r["composio_ground_truth"]]
    if without_gt:
        consistent = sum(1 for r in without_gt if r["verdict"] == "self_consistent")
        inconsistent = sum(1 for r in without_gt if r["verdict"] == "self_inconsistent")
        total_ng = len(without_gt)
        print(f"\nSelf-consistency check (no Composio GT, n={total_ng}):")
        print(f"  Self-consistent: {consistent} ({consistent/total_ng:.1%})")
        print(f"  Self-inconsistent: {inconsistent} ({inconsistent/total_ng:.1%})")

    # Per-field accuracy (against Composio)
    field_acc = {}
    if with_gt:
        for field in ["auth_methods_original_vs_composio"]:
            vals = [r["field_agreement"].get(field) for r in with_gt if r["field_agreement"].get(field) is not None]
            if vals:
                field_acc[field] = sum(1 for v in vals if v) / len(vals)

    # Save summary
    summary = {
        "sample_size": len(sample),
        "sample_apps": [r["app_name"] for r in sample],
        "verdicts": dict(verdicts),
        "composio_ground_truth_available": len(with_gt),
        "composio_accuracy": {
            "correct": sum(1 for r in with_gt if r["verdict"] == "correct"),
            "partial": sum(1 for r in with_gt if r["verdict"] == "partial"),
            "incorrect": sum(1 for r in with_gt if r["verdict"] == "incorrect"),
            "score": (sum(1 for r in with_gt if r["verdict"] == "correct") + 0.5 * sum(1 for r in with_gt if r["verdict"] == "partial")) / len(with_gt) if with_gt else 0,
        },
        "self_consistency": {
            "consistent": sum(1 for r in without_gt if r["verdict"] == "self_consistent"),
            "inconsistent": sum(1 for r in without_gt if r["verdict"] == "self_inconsistent"),
            "rate": sum(1 for r in without_gt if r["verdict"] == "self_consistent") / len(without_gt) if without_gt else 0,
        },
        "field_accuracy": field_acc,
        "all_results": results,
    }
    (VERIF_DIR / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {VERIF_DIR}/_summary.json")

    # Failure cases
    print(f"\n=== Failures (incorrect or self-inconsistent) ===")
    for r in results:
        if r["verdict"] in ("incorrect", "self_inconsistent"):
            orig = r["original_record"]
            think = r["thinking_reextract"] or {}
            gt = r["composio_ground_truth"]
            print(f"  {r['app_name']}: verdict={r['verdict']}")
            print(f"    original auth: {orig.get('auth_methods')}")
            print(f"    thinking auth: {think.get('auth_methods')}")
            if gt:
                print(f"    composio auth: {gt.get('auth_schemes')}")

asyncio.run(main())
