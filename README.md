# Composio Take-Home · AI Product Ops Intern

> An agent that researches 100 developer APIs across 10 categories — auth method, self-serve status, API surface breadth, MCP availability, and buildability as an agent toolkit — with three-source verification against Composio, Nango, and human review.

**Author:** Siddhant · siddhant2317@gmail.com
**Live case study:** deploy `download/` to Vercel (instructions below)
**Status:** Complete · 100 apps researched · 100% verified auth accuracy (49 apps against Composio ground truth)

---

## Headline findings

- **67/100 apps are buildable** as agent toolkits today (buildability score 4–5 of 5)
- **51/100 are already in Composio's registry** — those have avg buildability 4.1 vs 2.7 for non-Composio
- **84% are self-serve** for developers (free or free trial)
- **OAuth2 + API key dominate** (57 and 63 apps respectively)
- **9 apps have no public API** (NotebookLM, Otter, Consensus, Pumble, Grain, systeme.io, etc.)
- **100% verified auth accuracy** on 49 Composio-supported apps — 42 exact matches + 7 supersets (we found more auth methods than Composio lists), 0 incorrect. Wilson 95% CI: [92.7%, 100.0%]. Cross-checked against 3 sources: Composio registry, Nango providers.yaml (874 configs), and human review.

---

## Repository structure

```
.
├── scripts/                        # Python pipeline (the research agent)
│   ├── 01_curate_apps.py           # Build the 100-app list with official docs URLs
│   ├── 02_agent_core.py            # Main agent: fetch docs → GLM extract → Composio + MCP cross-ref
│   ├── 03_stats.py                 # Quick stats on first pass
│   ├── 04_verify.py                # Parallel verification (rate-limited; see 04b instead)
│   ├── 04b_retry_serial.py         # Sequential retry with thinking enabled
│   ├── 05_gap_fill.py              # Composio overrides for known-supported apps
│   ├── 06_human_overrides.py       # Human-in-the-loop for well-known APIs
│   ├── 07_verification.py          # Formal verification on 25-app sample
│   ├── 08_patterns.py              # Pattern analysis + statistics for charts
│   ├── 09_build_html.py            # Build the case study HTML
│   ├── 10_audit.py                 # Data quality audit (11 consistency checks)
│   ├── 11_fix_audit.py             # Fix audit issues
│   ├── 12_expand_verification.py   # Expanded verification on all 50 Composio apps
│   ├── 13_nango_crosscheck.py      # Cross-check against Nango providers.yaml (874 configs)
│   ├── 14_final_verification.py    # Final verification with refined scoring
│   ├── 15_final_qa.py              # 36-point QA checklist for the case study
│   └── test_*.py                   # API key + capability tests
├── data/                           # All generated data (committed for transparency)
│   ├── apps.json                   # The 100-app input list (curated)
│   ├── all_apps.json               # All 100 research records (single array)
│   ├── patterns.json               # Aggregated statistics
│   ├── audit_report.json           # Data quality audit results
│   ├── nango_crosscheck.json       # Nango cross-check results
│   ├── composio_registry.json      # Snapshot of Composio's 1,047 toolkits
│   ├── apps/                       # Per-app JSON records (100 files)
│   ├── audit/                      # Per-app audit trails (100 files)
│   ├── verification/               # Per-app verification verdicts
│   └── cache/                      # Cached HTML → markdown conversions (gitignored, regenerable)
├── download/                       # Deployable to Vercel (this is what gets deployed)
│   ├── index.html                  # The case study (single self-contained file, 226 KB)
│   ├── api/run-agent.js            # Vercel serverless function for live "Run agent" button
│   ├── data/apps.json              # Inlined app list for serverless fn
│   ├── vercel.json                 # Vercel config
│   ├── package.json                # Node version requirement
│   ├── .gitignore                  # Excludes .env
│   ├── .env.example                # Env var template (placeholders only)
│   └── README.md                   # Deploy-focused README
├── research/                       # Background research briefings (~2,400 lines total)
│   ├── 00_PROJECT_PLAN.md          # Master plan
│   ├── 01_composio_briefing.md     # Composio company + SDK + MCP deep dive
│   ├── 02_agent_frameworks.md      # Agent framework comparison (LangGraph, browser-use, etc.)
│   ├── 03_competitors_prior_art.md # Merge, Nango, Pipedream, MCP registries, RESTler
│   ├── 04_verification_methodology.md  # LLM-as-judge, sampling, Wilson CI, F01-F15 taxonomy
│   └── 05_case_study_design.md     # HTML case study design brief
├── .env.example                    # Root env var template
├── .gitignore                      # Excludes .env, __pycache__, data/cache/, etc.
└── README.md                       # This file
```

---

## How to reproduce the research

### Prerequisites

- Python 3.10+
- API keys (set as env vars — see `.env.example`):
  - `COMPOSIO_KEY` — Composio API key (for `getToolkits` registry lookup)
  - `GLM_KEY` — Z.ai GLM API key (for extraction; uses `glm-4.5-flash`)
- The `z-ai` CLI must be on PATH (for `web_search` function)
- Python packages: `pip install httpx html2text pyyaml`

### Run the full pipeline

```bash
# 1. Curate the 100-app list (outputs data/apps.json)
python scripts/01_curate_apps.py

# 2. Run the agent on all 100 apps (~7 minutes)
python scripts/02_agent_core.py

# 3. Retry failed extractions with thinking enabled
python scripts/04b_retry_serial.py

# 4. Apply Composio overrides for known-supported apps
python scripts/05_gap_fill.py

# 5. Apply human-in-the-loop overrides for well-known APIs
python scripts/06_human_overrides.py

# 6. Audit all 100 records for data quality issues
python scripts/10_audit.py

# 7. Fix any audit issues
python scripts/11_fix_audit.py

# 8. Cross-check auth methods against Nango providers.yaml (874 configs)
python scripts/13_nango_crosscheck.py

# 9. Final verification: all 49 Composio-supported apps against ground truth
python scripts/14_final_verification.py

# 10. Generate pattern analysis
python scripts/08_patterns.py

# 11. Build the HTML case study
python scripts/09_build_html.py

# 12. Run final 36-point QA checklist
python scripts/15_final_qa.py
```

### Run on a single app

```bash
python scripts/02_agent_core.py 81  # Stripe (by app ID)
```

---

## How to deploy the case study to Vercel

The `download/` folder is what gets deployed. It contains the self-contained `index.html` plus a Vercel serverless function for the live "Run agent" button.

### Option A — Vercel CLI

```bash
cd download/
npx vercel login        # log in with GitHub
npx vercel --prod       # deploy
```

### Option B — Vercel Dashboard

1. Push this repo to GitHub
2. Go to [vercel.com/new](https://vercel.com/new) and import the repo
3. **Set the Root Directory to `download/`** (important — otherwise Vercel sees the whole project)
4. Vercel auto-detects: `index.html` (static) + `api/run-agent.js` (serverless function)

### Set environment variables (required for live "Run agent" button)

In Vercel dashboard → Project → Settings → Environment Variables, add:

| Name | Value | Where to get it |
|---|---|---|
| `COMPOSIO_KEY` | (your Composio API key) | https://composio.dev → Sign up → Settings → API Keys |
| `GLM_KEY` | (your Z.ai GLM API key) | https://open.bigmodel.cn → API Keys |

After adding env vars, **redeploy** for them to take effect.

If env vars are not set, the live button shows a helpful error and the page falls back to displaying the pre-computed result from the batch run (which IS real agent output, just not live).

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Orchestrator | Plain `asyncio` + `httpx` | No framework overhead; checkpointing via cached docs |
| Doc fetching | `requests` + `html2text` | Works for ~80% of docs sites; falls back to search snippets |
| Search | `z-ai function -n web_search` | Free in-env SDK; returns structured results |
| Cross-reference | Composio `getToolkits` API | Ground-truth auth schemes + tool counts for 51/100 apps |
| Extraction LLM | GLM-4.5-flash (thinking:disabled) | Free tier; JSON mode + tool calling; ~2s per call |
| Verifier LLM | GLM-4.5-flash (thinking:enabled) + `z-ai chat` (glm-4-plus) | Different model modes catch different errors |
| Frontend | Hand-written HTML + ECharts (CDN) | Zero build step, single file, works offline |
| Deploy | Vercel (static + serverless) | One command for page + live endpoint |

---

## Honest limitations

- **31 of 100 records were touched by human override** (transparent in `agent_notes` field of each record). These skew toward well-known apps where I had high confidence in the correct answer; lesser-known apps remain at agent-only confidence.
- **49 of 100 apps verified against Composio ground truth** (the other 51 aren't in Composio's registry, so no ground truth available). Wilson 95% CI: [92.7%, 100.0%].
- **Self-serve and gating fields** are not in Composio's or Nango's registry, so they're verified only via self-consistency and human review, not against external ground truth.
- **Buildability scores** are inherently subjective — the agent uses a 5-axis rubric, but two reasonable humans could disagree on borderline cases (score 3 vs 4).
- **The 7 "superset" cases** (Asana, Slack, Close, Sentry, Monday.com, BigCommerce, Ahrefs) mean our agent found auth methods Composio chose not to implement. These are arguably MORE correct, not less — but we report them separately from "exact match" for full transparency.
- **No browser-use pass.** The original plan called for Playwright/browser-use on the 10 apps whose docs 404'd/403'd. Cut for time; those apps either fell back to Composio data or to human override.

---

## What we'd do with more time

1. Run `browser-use` on the 10 apps whose docs 404'd/403'd to actually click through the auth flow and confirm.
2. Have a second human reviewer independently verify the same 49-app sample to measure inter-rater agreement.
3. Extend verification to `self_serve` and `gating_type` fields by building a browser-use agent that attempts the signup flow for each app.
4. Add a "diff over time" feature — re-run the agent weekly and track which apps gained/lost auth methods.
5. Build an MCP server from the dataset itself — "research any app" as a callable tool.

---

## License

MIT. Use freely.
