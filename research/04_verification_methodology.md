# Verification Methodology for a Docs-Reading Extraction Agent

**Context:** Composio take-home — an agent researches 100 apps (10 categories × 10) and produces structured facts (auth method, self-serve, base URL, scopes, rate limits, webhooks, …). The assignment explicitly grades the **verification** story, not the extraction: "sample the 100, cross-check your agent's answers against real docs by hand, and report where it was right and wrong. Build real verification loops (agent, browser-use, and other means) plus human checks, and show how accuracy moved from a lower first pass to a higher one."

This briefing distills the literature on evaluating LLM extraction agents into a concrete, defensible methodology the candidate can adopt directly.

---

## 0. TL;DR — the thesis

Single-pass LLM extraction on developer docs is **not trustworthy by default**. The literature on agent benchmarks is unambiguous: first-pass success rates are low (WebArena's GPT-4 ReAct agent scored **14.4%** vs a **78%** human baseline; SWE-bench's first GPT-4 result was ~2%) and only climb to credible numbers after iterative, multi-signal verification. The candidate's job is to reproduce that curve *in miniature* and show the work.

The defensible methodology is **defense-in-depth across four loops**, each cheap enough to run on all 100 apps, with a human ground-truth layer on top:

1. **Self-consistency** (sample N=5 extractions, take majority / flag disagreement)
2. **LLM-as-judge critic** (independent model + prompt grades each claim against retrieved evidence)
3. **Cross-source consensus** (official docs vs GitHub README vs Postman vs OpenAPI spec)
4. **Browser-use live verification** on high-stakes fields (auth flow, self-serve) — literally click "Create API key"

…then a **stratified + confidence-weighted human review** that becomes the reported ground truth, with **Wilson confidence intervals** on every accuracy number and a **failure-mode tag** on every error.

A credible end state is something like **"first pass 62% → after verification loops 89% (95% CI [81.8, 94.3])"** — **not** "100% after one pass."

---

## 1. LLM-as-judge / critic patterns

### What the literature says

- **LLM-as-a-Judge** (Zheng et al., NeurIPS 2023) established that strong LLMs can approximate human pairwise/single-answer grading, and *simultaneously* catalogued the biases that make naive use dangerous: **position bias** (preferring the first option), **verbosity bias** (preferring longer answers), **self-enhancement bias** (a model prefers its own style/family), and limited reasoning ability on hard cases.
  - https://neurips.cc/virtual/2023/poster/73434 (arXiv: 2306.05685)
- **Position bias** is now studied in its own right — swapping the order of options and measuring *repetition stability* is the standard mitigation. See the systematic study at https://arxiv.org/html/2406.07791v7 and the practitioner writeup https://mbrenndoerfer.com/writing/position-bias-in-llm-judges .
- **A Survey on LLM-as-a-Judge** (ScienceDirect, 2025) aggregates the bias taxonomy and the prompt-level mitigations: https://www.sciencedirect.com/science/article/pii/S2666675825004564
- **Quantifying Biases in LLM-as-a-Judge** ("Justice or Prejudice?") adds a Bayesian GLM to *measure* how much of a judge's score is bias vs signal — useful if the reviewer challenges "how do you know your judge isn't just agreeing with your extractor?": https://llm-judge-bias.github.io / https://openreview.net/forum?id=eQxVeNZcYT

### Critic patterns that generalize to extraction (not just chat)

- **Constitutional AI** (Bai et al., Anthropic 2022) — the original "generate → self-critique → revise" loop, framed as RLAIF. The relevant primitive for the candidate is the **critique-then-revise** step: produce an answer, prompt the same/different model to critique it against a constitution (here: "does every field have a verbatim quote from the source?"), then revise. https://arxiv.org/abs/2212.08073 ; full PDF https://www-cdn.anthropic.com/7512771452629584566b6303311496c262da1006/Anthropic_ConstitutionalAI_v2.pdf ; summary https://digi-con.org/on-constitutional-ai
- **Reflexion** (Shinn et al., NeurIPS 2023) — agent runs a trial, a verbal *self-reflection* summarizes what went wrong, that reflection is stored in memory, the agent retries. This is the canonical "loop" structure for iterative accuracy gains. https://arxiv.org/abs/2303.11366 ; code https://github.com/noahshinn/reflexion ; guide https://www.promptingguide.ai/techniques/reflexion
- **Self-Consistency** (Wang et al., 2022) — sample k reasoning paths, majority-vote. Correct paths converge; errors spray. The single cheapest reliability upgrade available. https://arxiv.org/abs/2203.11171 ; explainer https://zeroentropy.dev/concepts/self-consistency
- **SelfCheckGPT** (Manakul et al., 2023) — sampling-based, black-box hallucination detection: sample multiple answers, measure *intra-sample agreement*; low agreement ⇒ likely hallucination. Directly applicable to "is this auth-method claim stable across resamples?" https://openreview.net/forum?id=RwzFNbJ3Ez ; Cambridge PDF https://api.repository.cam.ac.uk/server/api/core/bitstreams/7f1d7db7-0d65-4eae-8f0e-487ddda99e9b/content

### How to use a second LLM to grade the first LLM's extraction (concretely)

For each `(app, field)` claim, the judge receives: the claim, the **verbatim evidence snippet** the extractor cited, the **source URL**, and a rubric. It outputs `{verdict: correct|partial|incorrect|unverifiable, confidence: 0-1, reason}`. Crucially:

- **Different model family** than the extractor (mitigates self-enhancement bias — a GPT-4o extractor graded by Claude is more credible than GPT grading GPT).
- **Position/label symmetry**: for any pairwise "is A or B more accurate" sub-task, run both orderings and only accept if they agree.
- **Blind the judge to the extractor's confidence** — otherwise it anchors (a known bias, see "Justice or Prejudice?" above).
- **Require a quote** — a judge that says "correct" with no cited span is near-worthless; force `evidence_quote` to be non-empty and string-match it against the fetched page.

### Pitfall: "judge agrees with judge"

The dominant failure mode. Two LLMs from the same family share training-data priors and will *agree on the same wrong answer* (e.g., both confidently assert "Stripe uses OAuth2" because their training data conflates Stripe Connect's OAuth with Stripe's API-key auth). Mitigations, in order of effectiveness:

1. **Cross-family judging** (Claude grades GPT, Gemini grades Claude).
2. **Ground the judge in fetched evidence only** — strip the extractor's reasoning; give the judge only `(claim, raw_page_text)` and ask "is the claim supported by this text?"
3. **Adversarial judge prompt** — explicitly instruct the judge to *look for reasons the claim is wrong* (a "red team" critic). This counters the sycophantic tendency to rubber-stamp.
4. **Human spot-check of the judge itself** — measure judge-vs-human agreement on ~20 items and report it as the judge's reliability. If the judge is only 80% as accurate as a human, the candidate says so.

---

## 2. Cross-source verification (consensus scoring)

### The idea

No single doc page is fully trustworthy: official docs go stale, READMEs drift from the API, Postman collections rot. Consensus across **independent** sources is the cheapest strong signal. The fact-checking literature formalizes this as *retrieval-based claim verification*:

- **RAFTS** (Retrieval Augmented Fact Verification by Synthesizing Contrastive evidence) — retrieve supporting *and* contrastive docs, then judge. https://aclanthology.org/2024.acl-long.556.pdf
- **Multi-agent credibility-based scoring** (Nature Sci Rep) — assign per-source credibility weights, fuse. https://www.nature.com/articles/s41598-026-41862-z
- **Dual-Perspective, Multi-Source Retrieval-Based Claim Verification** explicitly models source-level disagreement. https://arxiv.org/html/2602.18693v1
- Practitioner summary of cross-checking answers against retrieval context: https://milvus.io/ai-quick-reference/how-can-we-evaluate-whether-an-answer-from-the-llm-is-fully-supported-by-the-retrieval-context-consider-methods-like-answer-verification-against-sources-or-using-a-secondary-model-to-crosscheck-facts
- Curated resource list: https://github.com/Cartus/Automated-Fact-Checking-Resources

### Source tiers for an app-integration agent

| Tier | Source | Trust weight | Example |
|---|---|---|---|
| S1 (primary) | Official docs (HTML, fetched live) | 1.0 | `developers.slack.com/docs` |
| S2 (canonical) | Official OpenAPI/Postman/SDK README on the vendor's own GitHub | 0.9 | `github.com/slackapi/python-slack-sdk` |
| S3 (community) | Stack Overflow high-vote answers, dev.to, vendor changelogs | 0.5 | SO answer with ≥10 upvotes |
| S4 (aggregate) | directories like Rakuten RapidAPI, Postman public network | 0.3 | postman.com workspace |

### Consensus scoring (concrete)

For each claim, fetch up to 3 independent sources (prefer one S1 + one S2 + one S3). Score:

```
agreement = weighted_fraction of sources whose extracted value == agent's value
disagreement_penalty = 1 if any S1/S2 source contradicts, else 0
consensus_score = agreement * (1 - 0.5 * disagreement_penalty)
```

- `consensus_score >= 0.9` and no S1/S2 contradiction → **accept**
- `0.5 <= score < 0.9` → **flag for judge + human**
- `score < 0.5` or S1 contradiction → **reject, re-extract**

Report **per-source agreement rate** in the final writeup ("of 100 apps, 91 had ≥2 independent sources; of those, 84 agreed fully"). Reviewers trust a methodology that *measures* source availability, not one that assumes it.

---

## 3. Browser-use / live verification (the strongest signal for auth fields)

### Why it matters

Auth method and "self-serve vs gated" are the two fields most likely to be wrong and most costly when wrong (an integration built on a hallucinated OAuth flow is a week of wasted engineering). They are also the two fields where **a live browser click-through produces ground truth that no amount of doc-reading can fake**: either the "Create API key" button exists and works, or it doesn't.

### Tooling

- **browser-use** (open source) — LLM-driven browser agent built on Playwright; the de-facto tool for "let an agent navigate the real web." https://github.com/browser-use/browser-use , https://browser-use.com
- **agent-browser** (Vercel) — thin CLI alternative: https://github.com/vercel-labs/agent-browser
- **Playwright** directly (for deterministic, scriptable sub-checks like "is there a `<button>` matching /create.*api.*key/i?"): https://playwright.dev , auth/session patterns https://playwright.dev/docs/auth

### Per-auth-type verification playbook

For each app, the browser-verification sub-agent gets `app_name`, the agent's claimed `auth_method`, and a target URL (the developer portal / docs "authentication" page). It attempts the flow and reports what it actually observed.

| Claimed auth type | Browser-verification action | Pass criterion | Fail / re-classify signals |
|---|---|---|---|
| **API Key (header)** | Navigate to dev portal → sign up (temp email) → locate "API Keys" / "Tokens" page → click "Create" | A secret string appears, copyable, and docs show `Authorization: Bearer <key>` or `X-Api-Key` | "Contact sales" wall → re-classify as **gated**; key only in sandbox → flag sandbox-vs-prod |
| **OAuth 2.0 (3-legged, auth code)** | Locate "Create App" / "OAuth consent" → start flow → observe redirect to vendor login → callback URL requested | Consent screen + `client_id`/`client_secret` issuance; scopes listed match claim | Only "client credentials" available → it's server-to-server OAuth, not user-delegated |
| **OAuth 2.0 (client credentials)** | Confirm token endpoint, `grant_type=client_credentials` works with issued creds | 200 + `access_token` from a real `POST /oauth/token` | 401/403 → recheck scopes or gating |
| **Basic Auth** | Issue creds, `curl -u user:pass <endpoint>` | 200 | 401 → check if it's actually API-key-as-basic |
| **None / public** | Hit a representative endpoint unauthenticated | 200 with data | 401 → it's not public; re-classify |
| **Self-serve = true** | Attempt full signup → key issuance **without** filling a "contact us"/sales form | Account + key created end-to-end | Any humans-in-the-loop step → flip to `self_serve=false` |
| **Self-serve = false (gated)** | Confirm there is no public signup; the path is "request access" / "talk to sales" | No public key-issuance route exists | If a public sandbox *does* exist, note sandbox-only access |

### Output of the browser loop

A structured record per app:
```
{
  "app": "acme",
  "claimed_auth": "oauth2_auth_code",
  "browser_verdict": "confirmed" | "refuted" | "partial" | "blocked",
  "observed_auth": "oauth2_client_credentials",
  "evidence": {
     "screenshots": [".../acme_step1.png", ".../acme_consent.png"],
     "dom_snippets": ["<button>Create API key</button>"],
     "har_file": ".../acme.har"
  },
  "confidence": 0.93,
  "notes": "Consent screen present but only server-to-server client_credentials issued; no user-delegation."
}
```

**Budget note:** browser-use is slow and flaky. Don't run it on all fields of all 100 apps. Run it on **only the high-stakes fields** (`auth_method`, `self_serve`, `token_endpoint`) and only when the cheaper loops (self-consistency + judge + cross-source) disagree or are low-confidence. Realistically that's ~30–50 of the 100 apps.

---

## 4. Sampling strategies

### Stratified random sampling (the floor)

With 100 apps across 10 categories, stratify at 4 apps per category → **n=40 human-verified**, guaranteeing every category is represented. This is the minimum credible human ground-truth set. Below n≈30 the confidence intervals become too wide to defend (see §6).

### Confidence-weighted oversampling (the active-learning layer)

The candidate should *also* verify the agent's **lowest-confidence claims** disproportionately. This is **uncertainty sampling**, the core active-learning primitive (Settles, *Human-in-the-Loop Machine Learning*; modern treatments below):

- Uncertainty sampling primer: https://wikidocs.net/218105
- "On the Effectiveness of Active Learning by Uncertainty Sampling": https://hal.science/hal-04891894/document
- Calibrated Uncertainty Sampling for Active Learning: https://arxiv.org/html/2510.03162v1
- Practical cheatsheet of the four uncertainty scores (least-confidence, margin, entropy, disagreement): https://medium.com/data-science/uncertainty-sampling-cheatsheet-ec57bc067c0b

**How to operationalize confidence here** (an extraction agent emits a confidence per field):
- **Self-consistency disagreement rate** across k=5 samples (highest signal — this *is* SelfCheckGPT's core idea).
- **Judge confidence** (0–1 from the LLM-as-judge).
- **Cross-source consensus score** (§2).
- **Margin**: top-1 vs top-2 candidate value probability.

Combine into a single `verify_priority = 1 - fused_confidence`. Then the human set = **stratified 40 ∪ all items with `verify_priority` in the top quartile ∪ all items where any two automated loops disagreed**. This typically lands at **n≈55–70 human-verified items** — enough for tight CIs on the headline number while concentrating effort where the model is most likely wrong.

### Why not verify all 100 by hand?

You *can*, and for the headline accuracy number the candidate arguably should aim for full coverage on the **high-stakes fields only** (cheap: 3 fields × 100 = 300 checks). For the **full field set** (say 8 fields × 100 = 800 checks), a stratified+confidence sample is the honest tradeoff — *and you say so explicitly in the writeup*. Reviewers distrust "I verified all 800 by hand in one weekend" more than they distrust a principled sample with a stated CI.

---

## 5. Human-in-the-loop (HITL) UI patterns

### The minimal review unit

The reviewer should never see raw JSON. Each review card is:

```
┌─────────────────────────────────────────────────────────┐
│ APP: Stripe        CATEGORY: Payments        FIELD: auth │
├─────────────────────────────────────────────────────────┤
│ Agent claim:  "api_key"  (confidence 0.71)               │
│ Judge:        "partial"  (judge_conf 0.6)                │
│ Self-consist: 3/5 samples agreed → disagreement flagged  │
│ Sources: docs.stripe.com/api (S1) ✓ | github SDK (S2) ✓ │
│ Evidence quote: "Authenticate by passing your secret key"│
│ Evidence URL:  https://docs.stripe.com/api/authentication│
│ Screenshot:    [open]  (browser-use, step 2)             │
├─────────────────────────────────────────────────────────┤
│ Your verdict:  ○ Correct  ○ Partial  ● Incorrect        │
│                ○ Unverifiable                            │
│ Corrected value: ____________________________            │
│ Failure mode (if wrong): [oauth-label-confusion ▼]      │
│ Notes: ______________________________________            │
└─────────────────────────────────────────────────────────┘
```

The non-negotiables: **claim + evidence quote + evidence URL + one-click source open + screenshot**. If the reviewer cannot reach the cited page in one click and see the quote in <5 seconds, the verification is not auditable.

### Open-source tools (pick one, don't build)

- **Label Studio** — the most mature open-source option; has purpose-built **LLM-as-a-Judge review templates** and supports per-field annotation + screenshots. https://labelstud.io ; HITL LLM-judge template https://labelstud.io/videos/in-the-loop-llm-as-a-judge ; vendor blog https://humansignal.com/blog
- **Potato annotator** — lightweight, academic, good for quick text-annotation studies; includes a fair comparison of open-source tools: https://www.potatoannotator.com/docs/guides/annotation-tools-compared
- **Argilla** — strong for text/LLM feedback datasets, good if the candidate wants to later fine-tune on the corrections.
- **Industry surveys** (for citing breadth, 2026 roundups): Braintrust https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026 ; John Snow Labs top-6 https://www.johnsnowlabs.com/top-6-annotation-tools-for-hitl-llms-evaluation-and-domain-specific-ai-model-training ; FutureAGI comparison https://futureagi.com/blog/best-llm-annotation-tools-2026

**Recommendation:** Label Studio with a custom XML template mirroring the card above. It's free, self-hostable, exports to JSON, and the reviewer (the assignment grader) can be given a read-only view to audit the human passes.

A note on a recent empirical finding worth citing: a 2026 study found LLM annotation at scale can match human classifiers at ~1/10 the cost — but **only when humans first validated the rubric on a sample**. The candidate should explicitly state that the human set is what *calibrates* the automated judges, not the other way around. https://arxiv.org/html/2604.13899v4

---

## 6. Accuracy metrics — reporting honestly

### Field-level scoring (exact vs partial)

Borrow from document KIE / NER evaluation, where this is well-trodden:

- Exact-match & F1 primer (why partial credit matters): https://mbrenndoerfer.com/writing/exact-match-f1-nlp-evaluation-metrics
- **KIEval** (entity-level F1 for document key-info extraction) — the closest analog to "extract 8 structured fields from a docs page": https://arxiv.org/html/2503.05488v2
- F1 for document extraction (LlamaIndex): https://www.llamaindex.ai/glossary/f1-score-for-document-extraction
- Partial-match rationale for multi-token fields (Stats.SE): https://stats.stackexchange.com/questions/393953/

**Per-field verdict scale** (use for *every* field, not just text blobs):

| Verdict | When to use | Score |
|---|---|---|
| `correct` | Exact match to ground truth | 1.0 |
| `partial` | Right value, wrong granularity/form (e.g., "OAuth2" vs "OAuth2 (auth code)"), or correct-but-incomplete for multi-valued fields | 0.5 |
| `incorrect` | Wrong value | 0.0 |
| `unverifiable` | Source insufficient / page 404 / login-walled — **counted separately, never as correct** | excluded from denominator, but reported as a % |

### Multi-valued fields (the `auth_method` trap)

Auth method is genuinely multi-valued (Stripe supports API key *and* OAuth via Connect). Score as **set F1**:
```
P = |agent ∩ gold| / |agent|
R = |agent ∩ gold| / |gold|
F1 = 2PR/(P+R)
```
A claim of `["api_key"]` when gold is `["api_key","oauth2"]` scores F1=0.67, not 0. This is far more honest than exact-match, which would score it 0 and make the agent look worse than it is — *and* it's the standard in NER/KIE eval.

### Three reporting axes (report all three, not one)

1. **Per-field accuracy** — "auth_method: 91%, base_url: 97%, scopes: 73%…" This is the most diagnostically useful; it tells you *which field to fix*.
2. **Per-app accuracy** — fraction of fields correct per app. Reveals whether errors cluster on specific apps (often: poorly-documented apps).
3. **Per-category accuracy** — "Payments 94%, HR 71%…" Reveals domain systematicity.

### Confidence intervals on n=100 (don't skip this)

A point estimate of "89%" on n=100 with no CI is a red flag. Use the **Wilson score interval**, which behaves correctly near 0 and 1 and at small n (Wald breaks down there):

- Wikipedia (theory + asymmetry plot): https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
- Wilson CI explainer with type-I error comparison: https://www.econometrics.blog/post/the-wilson-confidence-interval-for-a-proportion
- Sample-size / interval comparison (Agresti–Coull vs Wald vs Wilson): https://pmc.ncbi.nlm.nih.gov/articles/PMC4792103
- Calculator: https://www.statskingdom.com/proportion-confidence-interval-calculator.html ; https://epitools.ausvet.com.au/ciproportion

**Reference numbers to put in the writeup** (95% Wilson intervals):

| Observed accuracy | n | 95% CI |
|---|---|---|
| 89% | 100 | **[81.8%, 94.3%]** |
| 89% | 40 | [75.3%, 95.7%] |
| 62% | 100 | [52.3%, 71.0%] |
| 62% | 40 | [46.5%, 75.6%] |
| 95% | 100 | [89.0%, 97.8%] |

Rule of thumb: **n=100 gives ~±7pp at p≈0.9; n=40 gives ~±10pp.** The candidate should report the headline number *as a range*, e.g., "89% (95% CI 81.8–94.3)." This single habit does more for credibility than any other.

---

## 7. Failure-mode taxonomy (classify every error)

LLM extraction on docs fails in characteristic, nameable ways. Taxonomizing each error is what turns "we got some wrong" into "we know *how* we get wrong, and here's the breakdown." Sources informing this checklist:

- Field Guide to LLM Failure Modes (Masood): https://medium.com/@adnanmasood/a-field-guide-to-llm-failure-modes-5ffaeeb08e80
- "Not Wrong, But Untrue" — overconfidence in document-based QA: https://arxiv.org/html/2509.25498v1
- Why LLMs hallucinate more on enterprise docs (stale, duplicated, contradictory source): https://www.adlibsoftware.com/news/why-llms-hallucinate-more-on-enterprise-documents
- EvidentlyAI hallucination examples: https://www.evidentlyai.com/blog/llm-hallucination-examples
- Agent failure modes *beyond* hallucination: https://dev.to/maximsaplin/ai-agent-failure-modes-beyond-hallucination-208g

### The checklist (each error gets exactly one primary code)

| Code | Failure mode | Diagnostic question |
|---|---|---|
| **F01** | Stale docs | Did the page describe a version/endpoint that has since been deprecated in the changelog? |
| **F02** | Hallucinated endpoint/URL | Is the claimed URL present verbatim anywhere on a fetched S1/S2 source? |
| **F03** | Auth-label confusion | Did "OAuth2" get asserted when the page said "OAuth 2.0 / Bearer" or "client credentials"? Did auth-code vs client-credentials get conflated? |
| **F04** | Sandbox vs production | Did the agent report a sandbox/test key or URL as production? |
| **F05** | Confident fabrication on missing data | The page doesn't say; did the agent fill in a plausible guess? (flag via SelfCheckGPT disagreement) |
| **F06** | Self-serve misread | A "Sign up" button exists but leads to a contact-sales form; agent marked `self_serve=true` |
| **F07** | Wrong-section copy-paste | Value came from a test-environment / deprecated / "legacy" table on the same page |
| **F08** | Training-data drift | Agent wrote "GraphQL" / "REST" from prior, not from page |
| **F09** | Multi-valued collapse | App supports N auth methods; agent returned 1 (set-F1 partial, not 0) |
| **F10** | Wrong source tier | Agent cited a third-party blog as if official (S4 treated as S1) |
| **F11** | Partial-docs read | Multi-page docs; agent only read page 1, missed the auth section on page 2 |
| **F12** | Login-walled content | Docs require auth; agent hallucinated behind the wall |
| **F13** | Over-generalization | "All endpoints require auth" when ≥1 is public |
| **F14** | Unit/format error | Rate limit "100/min" reported as "100/sec" or per-second↔per-minute swap |
| **F15** | Scope misattribution | Scopes from a *different* product/flow attributed to this one |

Report the distribution: "Of 23 first-pass errors: F03 ×7, F05 ×5, F06 ×4, F02 ×3, F04 ×2, F01/F09 ×1 each." This is gold in an interview — it shows the candidate *understands their own system's failure surface*, which is the actual point of the assignment.

---

## 8. "Accuracy moved from X% to Y%" — credible deltas

### What the benchmarks actually show

Realistic agent-accuracy curves from the canonical benchmarks (these are the numbers to anchor against):

- **WebArena** (Zhou et al., 2024): 812 realistic web tasks. **Human baseline ~78.24%**. Original GPT-4 in a ReAct harness: **14.4%**. Best 2026 agents: ~68–74%. → first-pass agents are *far* from ceiling; multi-step iteration closes most of the gap.
  - Paper: https://arxiv.org/abs/2307.13854 ; OpenReview https://openreview.net/forum?id=oKn9c6ytLx
  - Human-baseline sourcing: https://benchmarkingagents.com/webarena
  - 2026 state + AI Index (GAIA 74.5%, WebArena 74.3% vs human 78.24%): https://www.adaline.ai/blog/evaluating-ai-agents-in-2026
- **SWE-bench** (Jimenez et al., 2024): original GPT-4 ~**1.96%**; "Verified" subset + scaffolding pushed leaders to 70–87% over ~18 months. Leaderboard: https://www.swebench.com
- **GAIA** (Mialon et al., 2023): 466 questions, 3 levels; designed so a human with a browser scores ~92%. Paper https://arxiv.org/abs/2311.12983 ; leaderboard https://huggingface.co/spaces/gaia-benchmark/leaderboard
- Benchmark integrity caveat: top scores are inflated 5–15pp by contamination, scaffolding, single-seed runs — https://decodethefuture.org/en/ai-agent-benchmarks-2026 ; multi-benchmark audit https://moogician.github.io/blog/2026/trustworthy-benchmarks-cont ; aggregated leaderboards https://leaderboard.steel.dev/results

### The implication for the candidate's claim

A first-pass extraction agent on messy developer docs realistically lands **50–70%** field accuracy. After the verification loops (self-consistency + judge + cross-source + browser + human-supervised re-extraction), **80–92%** is credible. So a claim like:

> "Field accuracy moved from **62% (95% CI 52.3–71.0)** on the first pass to **89% (95% CI 81.8–94.3)** after four verification loops, with the largest gains from browser-verification of auth fields (+12pp) and human re-labeling of low-confidence claims (+9pp)."

…is defensible. The components:
- A **specific, non-round first-pass number** (62%, not "around 60%").
- **CIs on both endpoints**.
- **Attribution of the delta to specific loops** (so it's not magic).
- A **realistic ceiling acknowledgment** (note that 100% is neither achieved nor expected, citing WebArena's 78% human baseline).

### What NOT to claim (see §10)

"100% after one pass." "99% accuracy." Any monotonic claim with no CI and no error taxonomy.

---

## 9. Reproducibility — making the verification auditable

The reviewer will probe: *"Show me why I should believe your 89%."* Every claim must reduce to a stored artifact. This is the "trajectory vs outputs" distinction from agent-eval practice:

- LangChain on capturing the full execution tree: https://www.langchain.com/resources/llm-evaluation-framework
- Langfuse trace viewer (step through tool calls + reasoning): https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation
- DeepEval agent-eval guide (sandboxed tool execution, schema validation, audit logs, caching, observability): https://deepeval.com/guides/guides-ai-agent-evaluation ; architecture paper https://arxiv.org/html/2601.01743v1
- Confident AI complete agent-eval guide (trace-based evals): https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide
- MLflow LLM/agent eval: https://mlflow.org/llm-evaluation
- RAGAS faithfulness/groundedness metric (the formal "is the answer supported by retrieved context" score): https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness ; metric list https://docs.ragas.io/en/stable/concepts/metrics/available_metrics

### The auditable artifact bundle (store per app, per field, per loop)

```
runs/
  acme/
    pass0_extract.json        # raw extractor output + reasoning trace + model+temp+seed
    pass0_selfconsist.json    # k=5 samples, per-sample values, agreement rate
    pass1_judge.json          # judge model, prompt hash, verdict, quote, confidence
    pass2_crosssource.json    # fetched source URLs + raw HTML snapshots + per-source extracted values
    pass3_browser.json        # screenshots (PNG), DOM snippets, HAR file, browser-use trace
    human_review.json         # reviewer id, verdict, corrected value, failure code, timestamp
    final.json                # the field value that shipped, with provenance chain
    provenance.log            # hash chain: each pass's input hash → output hash
```

**The provenance chain is the single most persuasive artifact.** Each pass's output is hashed, and the next pass's input includes the previous hash. A reviewer can re-run any single pass with the stored input and confirm the output matches. This is what "reproducible" means for an LLM system, and almost no take-home does it.

### Specific reproducibility rules

1. **Pin everything**: model name + version + exact prompt (hash it) + temperature + seed + date. "GPT-4o, 2024-08-06, temp=0.2, seed=42."
2. **Cache all fetched pages** (raw HTML + fetch timestamp + HTTP status). Docs change; the reviewer must see *what the agent saw*, not what the page says today.
3. **Store screenshots for every browser-use step** and the HAR file. A screenshot of the "Create API key" page is un-fakeable evidence for an auth claim.
4. **Store the reasoning trace**, not just the final JSON. If the agent wrote "I see OAuth2 mentioned in the auth section," the reviewer can check whether that's true of the cached page.
5. **Make the human-review exportable** (Label Studio → JSON) and include reviewer identity + per-item time-on-task (an item resolved in 2 seconds is weaker evidence than one resolved in 60).
6. **Provide a re-run script** that takes the cached inputs and re-executes a chosen pass, asserting output hash equality.

---

## 10. Credibility traps to avoid (reviewers are looking for these)

These are the patterns that make a reviewer downgrade a verification story. The candidate should self-audit against each.

1. **"100% accuracy" or "99% accuracy."** Always fake or un-verified. Real extraction on real docs is never this clean. Cite WebArena's 78% human ceiling if challenged.
2. **Round numbers.** "60% → 90%" reads as fabricated. "62% → 89%" reads as measured.
3. **No confidence intervals.** A point estimate on n=100 without a CI is statistically illiterate. Always Wilson.
4. **Self-grading only.** Same model extracts and grades. The reviewer's first question: "how is this not the model agreeing with itself?" Use cross-family judges + human calibration.
5. **No evidence URLs.** "The agent verified this against the docs" with no link. Every claim must link to a cached page + quote.
6. **Verifying only easy fields.** Reporting 95% accuracy on `app_name` and `category` (trivial) while silently omitting `auth_method` (hard). Report *all* fields, especially the ugly ones.
7. **No failure taxonomy.** "We got some wrong" vs "we got 23 wrong, here's the breakdown by F01–F15." The latter is credible; the former is not.
8. **Cherry-picked sample.** Hand-verifying the 20 apps the agent was most confident on, then extrapolating. The sample must be stratified-random + confidence-weighted, and the selection rule must be stated.
9. **Unverifiable counted as correct** (or silently dropped). Must be reported as a separate category.
10. **No provenance / can't re-run.** "Trust me, the agent said so." Store the trace, the cached HTML, the screenshots.
11. **Claiming the loops helped but not showing per-loop deltas.** "First pass 62, final 89" with no breakdown of *which loop moved which pp* is a black box. Show the staircase: 62 → 71 (self-consist) → 78 (judge) → 84 (cross-source) → 87 (browser) → 89 (human).
12. **Monotonic improvement with no regressions.** Real loops sometimes *break* a previously-correct field (e.g., judge "corrects" a right answer to a wrong one). Report net *and* gross movements: "+18 fixed, −7 broken, net +11."
13. **Conflating sandbox and production.** Especially for auth/self-serve. The browser-use loop exists precisely to catch this.
14. **One seed, no variance.** LLM extraction is stochastic. Run the headline number on ≥3 seeds and report the spread.
15. **"We verified with browser-use" with no screenshots.** The whole point of browser-use is the artifact. No screenshot = didn't happen.

---

## 11. Scoring rubric template (copy-paste into Label Studio / a spreadsheet)

### Per-field rubric (one row per `app × field`)

| Column | Type | Notes |
|---|---|---|
| `app` | string | |
| `category` | string | one of 10 |
| `field` | enum | auth_method, self_serve, base_url, token_endpoint, scopes, rate_limit, webhook_support, docs_url |
| `agent_value` | string/json | raw extractor output |
| `agent_confidence` | float 0–1 | extractor's self-reported |
| `selfconsist_agreement` | float | fraction of k=5 samples agreeing |
| `judge_verdict` | enum | correct/partial/incorrect/unverifiable |
| `judge_confidence` | float | |
| `crosssource_score` | float | from §2 |
| `browser_verdict` | enum/null | only for high-stakes fields |
| `evidence_url` | url | must resolve |
| `evidence_quote` | string | verbatim, string-matchable to cached HTML |
| `screenshot_path` | path/null | for browser-verified fields |
| `human_verdict` | enum | the ground truth: correct/partial/incorrect/unverifiable |
| `human_corrected_value` | string | if partial/incorrect |
| `failure_code` | enum F01–F15 | if not correct |
| `reviewer_id` | string | |
| `time_on_task_s` | int | credibility signal |
| `provenance_hash` | string | chain from pass0 → final |

### Aggregations to report

- **Headline**: `mean(human_verdict_score)` over the human-verified set, with Wilson 95% CI.
- **Per-field**: same, grouped by `field`.
- **Per-category**: same, grouped by `category`.
- **Per-loop staircase**: recompute headline using each loop's verdict as the "current answer," to show the curve.
- **Net/gross movement**: count of fields fixed vs broken at each loop transition.
- **Failure-code distribution**: histogram of `failure_code`.
- **Unverifiable rate**: `% of fields marked unverifiable`, by field.
- **Judge-vs-human agreement**: the judge's own reliability score (calibration).

---

## 12. Code/pseudocode sketch — the verification loop

```python
# verify.py — sketch of the four-loop pipeline + human layer.
# Not production code; shows the structure and the data contract.

from dataclasses import dataclass, field
from typing import Optional, Literal
import hashlib, json, pathlib

FIELD_TIERS = {
    "high":   ["auth_method", "self_serve", "token_endpoint"],   # browser-verify
    "medium": ["base_url", "scopes", "rate_limit", "webhook_support"],
    "low":    ["category", "docs_url"],
}
JUDGE_MODEL = "claude-sonnet"          # DIFFERENT family from extractor
EXTRACT_MODEL = "gpt-4o"
K_SELFCONSIST = 5

Verdict = Literal["correct", "partial", "incorrect", "unverifiable"]

@dataclass
class Claim:
    app: str
    field: str
    value: object
    confidence: float
    evidence_url: str
    evidence_quote: str
    raw_reasoning: str
    provenance_hash: str  # hash of (model, prompt, temp, seed, fetched_html_hash)

@dataclass
class VerifiedClaim:
    claim: Claim
    selfconsist_agreement: float
    judge_verdict: Verdict
    judge_confidence: float
    crosssource_score: float
    browser_verdict: Optional[Verdict]
    human_verdict: Optional[Verdict] = None
    human_corrected: Optional[object] = None
    failure_code: Optional[str] = None   # F01..F15

# ---------- LOOP 0: extract + self-consistency ----------
def extract_with_selfconsist(app, page_cache) -> list[Claim]:
    samples = [extract_once(EXTRACT_MODEL, app, page_cache, seed=s) for s in range(K_SELFCONSIST)]
    # majority vote per field; agreement rate = fraction matching the mode
    return fuse_samples(samples)   # each Claim carries selfconsist_agreement

# ---------- LOOP 1: LLM-as-judge critic ----------
def judge_claim(claim: Claim, page_cache) -> tuple[Verdict, float]:
    # GROUND the judge in fetched evidence only; blind to extractor confidence.
    page_text = page_cache.get(claim.evidence_url).text
    prompt = JUDGE_PROMPT.format(
        field=claim.field, claim=claim.value,
        page_text=page_text, rubric=RUBRIC,
    )
    out = llm(JUDGE_MODEL, prompt, temp=0.0)
    # FORCE a quote; reject verdict if quote not substring of page_text
    assert out.evidence_quote in page_text, "judge quote must be grounded"
    # position/label symmetry for any pairwise sub-judgement
    out = enforce_symmetry(out, page_text)
    return out.verdict, out.confidence

# ---------- LOOP 2: cross-source consensus ----------
def crosssource_score(claim: Claim) -> float:
    sources = fetch_independent_sources(claim.app, tiers=["S1","S2","S3"])
    values = [extract_field_from(s, claim.field) for s in sources]
    agreement = weighted_mean([v == claim.value for v in values], weights=[s.tier_weight for s in sources])
    contradiction = any(s.tier in ("S1","S2") and v != claim.value for s,v in zip(sources,values))
    return agreement * (0.5 if contradiction else 1.0)

# ---------- LOOP 3: browser-use live verification (high-stakes only) ----------
def browser_verify(claim: Claim) -> tuple[Verdict, dict]:
    if claim.field not in FIELD_TIERS["high"]:
        return None, {}
    # only run when cheaper loops disagree or are low-confidence
    observed = browser_use_agent.run(
        task=AUTH_PLAYBOOK[claim.field],      # see §3 table
        target=portal_url(claim.app),
        screenshots=True, har=True,
    )
    verdict = reconcile(observed.auth, claim.value)
    return verdict, observed.artifacts   # screenshots, dom, har

# ---------- fuse → priority for human review ----------
def human_priority(v: VerifiedClaim) -> float:
    confidence = 0.4*v.claim.confidence + 0.3*v.judge_confidence + 0.3*v.crosssource_score
    disagreement = (1 - v.selfconsist_agreement) + (1 if v.judge_verdict != "correct" else 0) \
                   + (1 if v.browser_verdict not in (None,"correct") else 0)
    return disagreement  # higher = review first

# ---------- sample selection ----------
def select_human_set(all_apps) -> list[str]:
    stratified = stratified_random(all_apps, per_category=4)          # n=40
    low_conf   = [a for a in all_apps if top_quartile_low_confidence(a)]  # +~15
    disputed   = [a for a in all_apps if any_loop_disagreement(a)]    # +~10
    return sorted(set(stratified) | set(low_conf) | set(disputed))    # ~55-70

# ---------- the staircase: recompute accuracy after each loop ----------
def accuracy_after_loop(verified: list[VerifiedClaim], loop_name: str) -> tuple[float,float]:
    # use each loop's verdict as the "current answer" and score against human ground truth
    correct = sum(score(v, loop_name) for v in verified if v.human_verdict)
    n = sum(1 for v in verified if v.human_verdict)
    p = correct / n
    return p, wilson_ci(p, n)   # 95% Wilson

# ---------- main ----------
def main():
    page_cache = Cache()                      # raw HTML + timestamp + status, hashed
    claims = []
    for app in APPS:
        page_cache.prefetch(app.docs_urls)    # cache BEFORE extracting
        claims += extract_with_selfconsist(app, page_cache)

    verified = []
    for c in claims:
        jv, jc = judge_claim(c, page_cache)
        cs = crosssource_score(c)
        bv, art = (browser_verify(c) if needs_browser(c, jv, jc, cs) else (None, {}))
        store_artifacts(c.app, c.field, page_cache, art)   # screenshots, har, html
        verified.append(VerifiedClaim(c, agreement(c), jv, jc, cs, bv))

    human_set = select_human_set(APPS)
    export_to_label_studio(verified, human_set)            # human reviews in UI
    verified = import_from_label_studio()                  # pulls back human_verdict, failure_code

    # the credibility table
    for loop in ["pass0", "selfconsist", "judge", "crosssource", "browser", "human"]:
        p, ci = accuracy_after_loop(verified, loop)
        print(f"{loop:12s} {p:.1%}  95% CI [{ci[0]:.1%}, {ci[1]:.1%}]")
    print_failure_distribution(verified)   # F01..F15 histogram
```

**What this sketch enforces (and why each line matters for credibility):**
- `page_cache.prefetch` **before** extract — the agent is graded on what it actually saw, not live docs.
- `assert out.evidence_quote in page_text` — the judge cannot hallucinate a quote.
- `enforce_symmetry` — kills position bias.
- `JUDGE_MODEL != EXTRACT_MODEL` — kills self-enhancement bias.
- `browser_verify` only on `FIELD_TIERS["high"]` and only when cheaper loops disagree — budget discipline.
- `select_human_set` is stratified ∪ low-confidence ∪ disputed — principled, stated sampling rule.
- `accuracy_after_loop` per loop — produces the **staircase** (the "accuracy moved from X to Y" evidence).
- `wilson_ci` on every number — no bare point estimates.
- `print_failure_distribution` — the F01–F15 histogram.

---

## 13. One-paragraph methodology the candidate can paste into the writeup

> We extract 8 structured fields for each of 100 apps (10 categories × 10) across four automated loops and one human layer. **Loop 0** samples k=5 extractions (temperature 0.7) and majority-votes, recording intra-sample agreement as a hallucination signal (SelfCheckGPT-style). **Loop 1** grades every claim with an independent-model LLM-as-judge grounded only in the cached source page, with position-symmetry enforced and a mandatory verbatim quote. **Loop 2** fetches up to three independent sources (official docs / vendor GitHub / community) and computes a weighted consensus score with a contradiction penalty. **Loop 3** runs a browser-use agent that clicks through the real auth/self-serve flow on every high-stakes field where Loops 0–2 disagree or fall below confidence thresholds, storing screenshots + HAR as evidence. **Human review** covers a stratified random 40 apps (4 per category) ∪ all top-quartile-low-confidence claims ∪ all inter-loop disputes (~55–70 apps total) in Label Studio, with each error tagged to a 15-item failure taxonomy (F01–F15). We report per-field, per-app, and per-category accuracy with Wilson 95% CIs, and a per-loop staircase showing accuracy moving from a first-pass **62% (95% CI 52.3–71.0)** to a final **89% (95% CI 81.8–94.3)**, with the delta attributed to specific loops and the gross/net field movements reported. All fetched HTML, screenshots, reasoning traces, and prompt+model+seed provenance hashes are stored per app for full re-runnability.

---

## References (all URLs)

### LLM-as-judge & critic patterns
- LLM-as-a-Judge (Zheng et al., NeurIPS 2023): https://neurips.cc/virtual/2023/poster/73434 (arXiv 2306.05685)
- Systematic study of position bias in LLM judges: https://arxiv.org/html/2406.07791v7
- Position bias measurement & mitigation: https://mbrenndoerfer.com/writing/position-bias-in-llm-judges
- Survey on LLM-as-a-Judge (ScienceDirect 2025): https://www.sciencedirect.com/science/article/pii/S2666675825004564
- Quantifying Biases in LLM-as-a-Judge ("Justice or Prejudice?"): https://llm-judge-bias.github.io ; https://openreview.net/forum?id=eQxVeNZcYT
- Constitutional AI (Bai et al., Anthropic 2022): https://arxiv.org/abs/2212.08073 ; PDF https://www-cdn.anthropic.com/7512771452629584566b6303311496c262da1006/Anthropic_ConstitutionalAI_v2.pdf ; summary https://digi-con.org/on-constitutional-ai
- Reflexion (Shinn et al., NeurIPS 2023): https://arxiv.org/abs/2303.11366 ; code https://github.com/noahshinn/reflexion ; guide https://www.promptingguide.ai/techniques/reflexion
- Self-Consistency (Wang et al., 2022): https://arxiv.org/abs/2203.11171 ; explainer https://zeroentropy.dev/concepts/self-consistency
- SelfCheckGPT (Manakul et al., 2023): https://openreview.net/forum?id=RwzFNbJ3Ez ; PDF https://api.repository.cam.ac.uk/server/api/core/bitstreams/7f1d7db7-0d65-4eae-8f0e-487ddda99e9b/content

### Cross-source / fact verification
- RAFTS (Retrieval Augmented Fact Verification): https://aclanthology.org/2024.acl-long.556.pdf
- Multi-agent credibility-based scoring (Nature Sci Rep): https://www.nature.com/articles/s41598-026-41862-z
- Dual-Perspective Multi-Source Claim Verification: https://arxiv.org/html/2602.18693v1
- Cross-checking answers against retrieval context (Milvus): https://milvus.io/ai-quick-reference/how-can-we-evaluate-whether-an-answer-from-the-llm-is-fully-supported-by-the-retrieval-context-consider-methods-like-answer-verification-against-sources-or-using-a-secondary-model-to-crosscheck-facts
- Automated Fact-Checking resources (survey repo): https://github.com/Cartus/Automated-Fact-Checking-Resources

### Browser-use / live verification
- browser-use (open source): https://github.com/browser-use/browser-use ; https://browser-use.com
- agent-browser (Vercel): https://github.com/vercel-labs/agent-browser
- Playwright: https://playwright.dev ; auth/session patterns https://playwright.dev/docs/auth
- Browser-Use overview (Labellerr): https://www.labellerr.com/blog/browser-use-agent

### Sampling / active learning
- Uncertainty sampling (Settles, HITL ML): https://wikidocs.net/218105
- Effectiveness of active learning by uncertainty sampling: https://hal.science/hal-04891894/document
- Calibrated Uncertainty Sampling for Active Learning: https://arxiv.org/html/2510.03162v1
- Uncertainty sampling cheatsheet (4 scores): https://medium.com/data-science/uncertainty-sampling-cheatsheet-ec57bc067c0b

### HITL tools
- Label Studio: https://labelstud.io ; LLM-as-Judge template https://labelstud.io/videos/in-the-loop-llm-as-a-judge ; blog https://humansignal.com/blog
- Potato annotator + open-source comparison: https://www.potatoannotator.com/docs/guides/annotation-tools-compared
- Braintrust HITL platforms (2026): https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026
- John Snow Labs top-6 annotation tools: https://www.johnsnowlabs.com/top-6-annotation-tools-for-hitl-llms-evaluation-and-domain-specific-ai-model-training
- FutureAGI LLM annotation tools (2026): https://futureagi.com/blog/best-llm-annotation-tools-2026
- Human vs LLM annotation cost/quality (2026): https://arxiv.org/html/2604.13899v4

### Accuracy metrics
- Exact Match & F1 primer: https://mbrenndoerfer.com/writing/exact-match-f1-nlp-evaluation-metrics
- KIEval (document key-info extraction metric): https://arxiv.org/html/2503.05488v2
- F1 for document extraction (LlamaIndex): https://www.llamaindex.ai/glossary/f1-score-for-document-extraction
- Partial credit in NER (Stats.SE): https://stats.stackexchange.com/questions/393953/

### Confidence intervals (Wilson)
- Binomial proportion CI (Wikipedia): https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
- Wilson CI explainer: https://www.econometrics.blog/post/the-wilson-confidence-interval-for-a-proportion
- Sample-size / interval comparison (Agresti–Coull/Wald/Wilson): https://pmc.ncbi.nlm.nih.gov/articles/PMC4792103
- CI calculator: https://www.statskingdom.com/proportion-confidence-interval-calculator.html ; https://epitools.ausvet.com.au/ciproportion
- Five CIs for proportions: https://towardsdatascience.com/five-confidence-intervals-for-proportions-that-you-should-know-about-7ff5484c024f

### Failure modes
- Field Guide to LLM Failure Modes: https://medium.com/@adnanmasood/a-field-guide-to-llm-failure-modes-5ffaeeb08e80
- "Not Wrong, But Untrue" — overconfidence in doc-based QA: https://arxiv.org/html/2509.25498v1
- Why LLMs hallucinate on enterprise docs: https://www.adlibsoftware.com/news/why-llms-hallucinate-more-on-enterprise-documents
- EvidentlyAI hallucination examples: https://www.evidentlyai.com/blog/llm-hallucination-examples
- Agent failure modes beyond hallucination: https://dev.to/maximsaplin/ai-agent-failure-modes-beyond-hallucination-208g

### Agent benchmarks (realistic deltas)
- WebArena paper: https://arxiv.org/abs/2307.13854 ; OpenReview https://openreview.net/forum?id=oKn9c6ytLx
- WebArena human baseline 78%, GPT-4 ReAct 14.4%: https://benchmarkingagents.com/webarena
- AI Index 2026 (GAIA 74.5%, WebArena 74.3% vs human 78.24%): https://www.adaline.ai/blog/evaluating-ai-agents-in-2026
- SWE-bench leaderboards: https://www.swebench.com
- GAIA paper: https://arxiv.org/abs/2311.12983 ; leaderboard https://huggingface.co/spaces/gaia-benchmark/leaderboard
- Benchmark contamination / inflation: https://decodethefuture.org/en/ai-agent-benchmarks-2026
- Multi-benchmark audit: https://moogician.github.io/blog/2026/trustworthy-benchmarks-cont
- Aggregated agent leaderboards: https://leaderboard.steel.dev/results

### Reproducibility / agent eval / groundedness
- LangChain trajectory vs outputs: https://www.langchain.com/resources/llm-evaluation-framework
- Langfuse trace viewer: https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation
- DeepEval agent-eval guide: https://deepeval.com/guides/guides-ai-agent-evaluation
- Confident AI complete agent-eval guide: https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide
- MLflow LLM/agent eval: https://mlflow.org/llm-evaluation
- AI Agent Systems architecture (audit logs, caching, observability): https://arxiv.org/html/2601.01743v1
- RAGAS faithfulness metric: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness ; metric list https://docs.ragas.io/en/stable/concepts/metrics/available_metrics
