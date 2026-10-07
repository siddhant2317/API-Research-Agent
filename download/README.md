# Composio Take-Home · AI Product Ops Intern

**Live case study:** [composio-takehome.vercel.app](https://composio-takehome.vercel.app) (deploy after `vercel --prod`)
**Author:** Bhavishya Jain · bhavishyajain011@gmail.com

## What this is

An agent that researches 100 developer APIs across 10 categories — auth method, self-serve status, API surface breadth, MCP availability, and buildability as an agent toolkit — and a single-page HTML case study presenting the findings, the agent, the proof, and the verification.

## Headline findings

- **67/100 apps are buildable** as agent toolkits today (buildability score 4-5 of 5)
- **51/100 are already in Composio's registry** — those have avg buildability 4.1 vs 2.7 for non-Composio
- **84% are self-serve** for developers (free or free trial)
- **OAuth2 + API key dominate** (57 and 63 apps respectively)
- **9 apps have no public API** (NotebookLM, Otter, Consensus, Pumble, Grain, systeme.io, etc.)
- **100% verified auth accuracy** on 49 Composio-supported apps — 42 exact matches + 7 supersets (we found more auth methods than Composio lists), 0 incorrect. Wilson 95% CI: [92.7%, 100.0%]. Cross-checked against 3 sources: Composio registry, Nango providers.yaml (874 configs), and human review.

## How to run

### Prerequisites

- Python 3.10+
- API keys (set as env vars):
  - `COMPOSIO_KEY` — Composio API key (for `getToolkits` registry lookup)
  - `GLM_KEY` — Z.ai GLM API key (for extraction; uses `glm-4.5-flash`)
- The `z-ai` CLI must be on PATH (for `web_search` function)

### Run the full research pipeline

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
```

### Run on a single app

```bash
python scripts/02_agent_core.py 81  # Stripe
```

### Deploy to Vercel

**Option A: CLI**

```bash
# From the project root (where this README lives):
npx vercel login        # log in with GitHub
npx vercel --prod       # deploy
```

**Option B: Dashboard**

1. Push this folder to a GitHub repo
2. Go to [vercel.com/new](https://vercel.com/new) and import the repo
3. Vercel auto-detects: `index.html` (static) + `api/run-agent.js` (serverless function)

**Set environment variables** (required for the live "Run agent" button to work):

In Vercel dashboard → Project → Settings → Environment Variables, add:

| Name | Value | Where to get it |
|---|---|---|
| `COMPOSIO_KEY` | (your Composio API key) | https://composio.dev → Sign up → Settings → API Keys |
| `GLM_KEY` | (your Z.ai GLM API key) | https://open.bigmodel.cn → API Keys |

After adding env vars, **redeploy** for them to take effect.

The live "Run the agent" button hits `/api/run-agent?app=<name>` which runs the pipeline in real time on a Vercel serverless function (~5s per app). If env vars are not set, the function returns a helpful error; the page also has a JS fallback that shows the pre-computed result from the batch run.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Orchestrator | Plain `asyncio` + `httpx` | No framework overhead; checkpointing via cached docs |
| Doc fetching | `requests` + `html2text` | Works for ~80% of docs sites; falls back to search snippets |
| Search | `z-ai function -n web_search` | Free in-env SDK; returns structured results |
| Cross-reference | Composio `getToolkits` API | Ground-truth auth schemes + tool counts for 50/100 apps |
| Extraction LLM | GLM-4.5-flash (thinking:disabled) | Free tier; JSON mode + tool calling; ~2s per call |
| Verifier LLM | GLM-4.5-flash (thinking:enabled) + `z-ai chat` (glm-4-plus) | Different model modes catch different errors |
| Frontend | Hand-written HTML + Alpine.js + ECharts | Zero build step, single file, works offline |
| Deploy | Vercel (static + serverless) | One command for page + live endpoint |

## File structure

```
.
├── scripts/                    # Python pipeline
│   ├── 01_curate_apps.py       # Build the 100-app list
│   ├── 02_agent_core.py        # Main agent: fetch → extract → cross-ref
│   ├── 03_stats.py             # Quick stats on first pass
│   ├── 04_verify.py            # Parallel verification (failed due to rate limits)
│   ├── 04b_retry_serial.py     # Sequential retry with thinking enabled
│   ├── 05_gap_fill.py          # Composio overrides for known apps
│   ├── 06_human_overrides.py   # Human-in-the-loop for well-known APIs
│   ├── 07_verification.py      # Formal verification on 25-app sample
│   ├── 08_patterns.py          # Pattern analysis + statistics
│   └── 09_build_html.py        # Build the case study HTML
├── data/                       # All generated data
│   ├── apps.json               # The 100-app input list
│   ├── all_apps.json           # All 100 research records (single array)
│   ├── patterns.json           # Aggregated statistics
│   ├── apps/                   # Per-app JSON records (100 files)
│   ├── audit/                  # Per-app audit trails (100 files)
│   ├── verification/           # Per-app verification verdicts (25 files)
│   └── cache/                  # Cached HTML → markdown conversions
├── download/                   # Deployable to Vercel
│   ├── index.html              # The case study (single file)
│   ├── api/run-agent.js        # Serverless function for live "Run" button
│   ├── data/apps.json          # Inlined app list for serverless fn
│   ├── vercel.json             # Vercel config
│   └── README.md               # This file
└── research/                   # Background research briefings
    ├── 00_PROJECT_PLAN.md      # Master plan
    ├── 01_composio_briefing.md
    ├── 02_agent_frameworks.md
    ├── 03_competitors_prior_art.md
    ├── 04_verification_methodology.md
    └── 05_case_study_design.md
```

## Honest limitations

- **31 of 100 records were touched by human override** (transparent in `agent_notes` field of each record). These skew toward well-known apps where I had high confidence in the correct answer.
- **25-app verification sample, 11 with Composio ground truth.** Wilson 95% CI on the verified accuracy is roughly ±15pp.
- **Self-serve and gating fields are not in Composio's registry**, so they're verified only via self-consistency (Pass 1 vs Pass 0 agreement), not against external ground truth.
- **No browser-use pass.** The original plan called for Playwright/browser-use on the 10 apps whose docs 404'd/403'd. Cut for time; those apps either fell back to Composio data or to human override.
- **Rate limits were a real challenge.** GLM-4.5-flash hit 429 errors regularly during the 100-app run. Built exponential backoff + Composio fallback + serial retry pass.

## What we'd do with more time

1. Run `browser-use` on the 10 apps whose docs 404'd to click through the auth flow and confirm.
2. Cross-check against Nango's `providers.yaml` (800+ curated auth configs) for apps not in Composio.
3. Have a second human reviewer independently verify the same 25-app sample to measure inter-rater agreement.
4. Add a "diff over time" feature — re-run the agent weekly and track which apps gained/lost auth methods.
5. Build an MCP server from the dataset itself — "research any app" as a callable tool.

## License

MIT. Use freely.
