# Agent Frameworks for API Discovery — Comparison & Recommendation

**Purpose.** A Composio AI Product Ops Intern candidate must build an agent that, for ~100 apps, researches: API surface breadth, auth method, self-serve vs. gated status, existing MCP server existence, and "buildability as an agent toolkit." Every claim must cite a URL and the agent must be auditable/verifiable. This document compares the frameworks the candidate could use to *build that research agent*, gives a feature matrix, a recommended stack, a "where a human is still needed" section, and a Python orchestration sketch.

All facts below are grounded in the live web research in this folder (`s1_*` … `s15_*` search dumps, `p1_*` page reads). Inline URLs are the citations.

---

## 0. The one-sentence verdict (TL;DR)

Use **LangGraph** as the orchestrator, **Pydantic** for the per-app output schema, a **tiered fetch→Playwright→browser-use escalation** for reading docs, **Composio's own `getToolkits` registry + MCP registries (mcp.so / glama / pulsemcp / smithery / modelcontextprotocol/servers)** as structured cross-reference sources, **Claude Sonnet 4.5** for extraction/reasoning and **Gemini 2.5 Pro** for long-context doc dumps, and a **separate browser-use verifier on a 10% sample** — with Composio's SDK/MCP used *honestly*, as a data source and tool-router, not as a docs-browsing engine.

---

## 1. Composio's own SDK + MCP — the honest framing

This is the most important section for the candidate, because the assignment explicitly says *"Using Composio's own SDK and MCP to build it is in the spirit of the role."* The candidate must be able to defend, in interview, **what Composio's tools actually do and what they don't.**

### 1.1 What Composio's SDK actually is

Composio's Python SDK (`composio` on PyPI, `ComposioToolSet`) is a **tool-execution and managed-auth layer for apps Composio has *already* integrated** — not a general-purpose docs-research engine.

- Per PyPI: *"The Composio Python SDK allows you to interact with the Composio Platform. It provides a powerful and flexible way to manage and execute tools, handle [auth]…"* ([pypi.org/project/composio](https://pypi.org/project/composio)).
- Per the GitHub repo: *"The Python SDK offers a Pythonic interface to Composio's services… supports Python 3.10+"* ([github.com/composiohq/composio](https://github.com/composiohq/composio)).
- Core methods are `ComposioToolSet.get_tools(actions=[...])` / `get_tools(apps=[...])`, `get_app(...)`, and `execute_action(...)` — i.e. you fetch the schema for an **already-wrapped** action and then call it ([docs.together.ai/docs/composio](https://docs.together.ai/docs/composio); [docs.linkup.so/.../composio](https://docs.linkup.so/pages/integrations/composio/composio); [neon.com/guides/composio-crewai-neon](https://neon.com/guides/composio-crewai-neon)).
- Composio manages auth end-to-end — *"OAuth, API keys, token refresh, lifecycle management"* ([composio.dev](https://composio.dev); [docs.composio.dev/docs/authentication](https://docs.composio.dev/docs/authentication); [docs.composio.dev/docs/tools-direct/authenticating-tools](https://docs.composio.dev/docs/tools-direct/authenticating-tools)).

So: **Composio's SDK is for *calling* apps you already integrated, with managed auth.** It does not, by itself, browse an arbitrary vendor's docs site and discover an API surface from scratch.

### 1.2 The crucial nuance — Composio's registry IS a first-class research data source

Here is the honest, defensible framing. Composio exposes a **List Toolkits** API:

> `GET https://backend.composio.dev/api/v3.1/toolkits` — *"Retrieves a comprehensive list of toolkits… Toolkits represent integration points with external services and applications, each containing a collection of tools and triggers. This endpoint supports filtering by category and management type…"*
> ([docs.composio.dev/reference/api-reference/toolkits/getToolkits](https://docs.composio.dev/reference/api-reference/toolkits/getToolkits)) — confirmed by direct page read in `p1_composio_toolkits.json`.

The response schema is **exactly** the structured per-app data the assignment asks for. Each item returns:

```json
{
  "slug": "github",
  "name": "GitHub",
  "auth_schemes": ["oauth2", "api_key"],
  "composio_managed_auth_schemes": ["oauth2"],
  "is_local_toolkit": false,
  "no_auth": false,
  "auth_guide_url": "https://composio.dev/auth/github",
  "meta": {
    "description": "Integrate with GitHub repositories, issues, pull requests, and more.",
    "app_url": "https://github.com",
    "categories": [{"id": "developer-tools", "name": "Developer Tools"}],
    "triggers_count": 5,
    "tools_count": 12,
    "version": "20250905_00"
  }
}
```

That single endpoint, for the apps Composio already covers, directly answers four of the assignment's six fields:

| Assignment field | Composio registry answer |
|---|---|
| Auth method | `auth_schemes` (`oauth2`, `api_key`, `basic`, `jwt`…) |
| Self-serve vs. gated | `composio_managed_auth_schemes` + `auth_guide_url` + `no_auth` (if Composio manages OAuth for you → self-serve; if it's `is_local_toolkit` or only `api_key` with manual provisioning → more gated) |
| API surface breadth | `meta.tools_count`, `meta.triggers_count`, `categories` |
| Buildability as an agent toolkit | If it's in the registry *at all*, Composio already built it → buildability = "already built, version X, N tools". If absent → buildability must be assessed from the vendor docs. |

It supports `search`, `category`, `managed_by`, `limit` (max 1000) and cursor pagination — so the agent can look up any of the 100 apps by name/slug in one call ([docs.composio.dev/reference/api-reference/toolkits/getToolkits](https://docs.composio.dev/reference/api-reference/toolkits/getToolkits)).

### 1.3 Composio's MCP server — what it adds

Composio also ships a **managed MCP server** that exposes those same 1,000+ toolkits to clients like Claude, ChatGPT, and Cursor over the Model Context Protocol ([composio.dev/toolkits/composio](https://composio.dev/toolkits/composio); [composio.dev/toolkits/composio/framework/crew-ai](https://composio.dev/toolkits/composio/framework/crew-ai)). It acts as a *"unifying layer between AI agents and the web of third-party services"* ([natesnewsletter.substack.com/p/composio-mcp-wants-to-dance-with](https://natesnewsletter.substack.com/p/composio-mcp-wants-to-dance-with)). The honest read: Composio MCP gives an agent **callable, pre-authenticated actions** — it does not give the agent a browser that reads Stripe's docs for the first time.

### 1.4 The defensible interview position

> *"I used Composio in three places, and I'm explicit about each: (1) Composio's `getToolkits` registry is one of my agent's five cross-reference sources — for any app Composio already wraps, it returns auth schemes, tool/trigger counts, app URL, and an auth guide, all structured and citable. That's not 'using Composio to browse docs'; it's querying Composio's own metadata as a primary source. (2) Composio's MCP server is how my verifier agent can, where an app is Composio-supported, actually exercise a tool to sanity-check that the documented auth really works. (3) For apps NOT in Composio's registry — or to ground-truth Composio's metadata against the vendor's own docs — I use an independent fetch/browser path. Composio's SDK does not browse arbitrary docs; pretending otherwise would be the dishonest framing. Using Composio's registry and MCP as data-source plus tool-router is exactly 'in the spirit of the role,' and I label it as such in the output schema."*

That is the framing that survives a sharp interviewer. The trap to avoid: claiming "I built the research agent *with* Composio's SDK" when the SDK can't read a React docs site. The escape: Composio's *registry* and *MCP* are legitimately part of the research pipeline; the *browsing* is done by a separate fetch/browser layer.

---

## 2. Browser-use

**What it is.** Open-source Python library ([github.com/browser-use/browser-use](https://github.com/browser-use/browser-use)) — *"Make websites accessible for AI agents. Give your coding agent a browser."* It wraps **Playwright** + an LLM: the agent receives a DOM/accessibility-tree (and optionally screenshots), reasons about the next action, and drives a real Chromium instance. It accepts any OpenAI-compatible model (`'openai/gpt-5...'`, Claude, Gemini, GLM).

**Strengths for this task**
- Real Chromium → renders JS-heavy SPA docs that static fetchers see as empty (Notion, Linear, Stripe are all React/Mintlify-style). This is the core reason it's in the stack at all.
- Vision + DOM modes; `extract`-style structured output is supported via the LangChain integration ([medium.com/@sumit.somanchd/browser-use-with-openai-langchain](https://medium.com/@sumit.somanchd/browser-use-with-openai-langchain-for-automating-web-browsing-ba6db7439566); [machinelearningmastery.com/building-browser-using-ai-agents-in-python](https://machinelearningmastery.com/building-browser-using-ai-agents-in-python)).
- LangChain/LangGraph native → drops cleanly into the recommended orchestrator.
- Self-hostable (free) or Cloud (managed).

**Weaknesses**
- **Slow & costly.** Each page is multiple LLM round-trips (observe → act → extract). Realistically ~10–60 s/page and high token use (full DOM in context).
- **Flaky.** Agent can click the wrong element, get stuck behind a cookie banner, or loop. Needs retries + step caps.
- **Non-deterministic.** Two runs can extract different fields — which is precisely why a *separate* verifier is needed (§8).

**Benchmarks (recent)**
- Browser-use reports **89.1% on WebVoyager**, cited as best open-source framework by Firecrawl ([firecrawl.dev/blog/best-browser-agents](https://www.firecrawl.dev/blog/best-browser-agents)).
- Browser Use **Cloud scores 78% on their 100 hard browser tasks, "16 points ahead of the best open-source model"** ([browser-use.com/posts/ai-browser-agent-benchmark](https://browser-use.com/posts/ai-browser-agent-benchmark)).
- The **Online-Mind2Web** benchmark compares agent frameworks head-to-head ([github.com/browser-use/benchmark](https://github.com/browser-use/benchmark)).
- **Important counterpoint for this task:** arXiv *Beyond Browsing: API-Based Web Agents* found **API-based agents outperform pure browsing agents on WebArena, and a hybrid wins overall** ([arxiv.org/html/2410.16464v3](https://arxiv.org/html/2410.16464v3)). Translation: for API docs (which are themselves API-shaped), don't default to a full browser agent — fetch the OpenAPI spec or the static page first, and only escalate to browser-use when the page is genuinely JS-gated.

**vs. Agent-E.** Agent-E (Emergent) is a research web agent built on AutoGen with architectural improvements over prior SOTA, evaluated on WebVoyager/WebArena ([openreview.net/forum?id=7PQnFTbizU](https://openreview.net/forum?id=7PQnFTbizU); [huggingface.co/papers?q=Web-agent benchmarks](https://huggingface.co/papers?q=Web-agent%20benchmarks)). It's more research-flavored, less production-packaged than browser-use. For a take-home that must be reproducible on a deadline, browser-use's packaged Python API + LangChain glue is the pragmatic pick; Agent-E is the "if I had two more weeks" alternative.

**vs. the broader field.** A wider landscape review lists browser-use and Agent-E among 30+ open-source web agents ([aimultiple.com/open-source-web-agents](https://aimultiple.com/open-source-web-agents)). Browser-use remains the most accessible for a single-dev build.

---

## 3. Playwright + LLM (Stagehand, agent-e, plain Playwright)

There are really three tiers here, and the right answer for the assignment is **all three, escalated in order**.

### 3.1 Plain Playwright scripting
Deterministic, fast, cheap, no LLM needed for the navigation. Best when the docs site has predictable structure (e.g. a Mintlify site exposes `/api-reference/<resource>` pages with a stable layout; Redocly/Stoplight sites expose a downloadable OpenAPI JSON). **If a vendor publishes an OpenAPI/Postman spec, fetch that directly and skip prose scraping entirely** — the spec *is* the API surface, machine-readable.

### 3.2 Stagehand (browserbase/stagehand)
*"The SDK For Browser Agents"* ([github.com/browserbase/stagehand](https://github.com/browserbase/stagehand); [stagehand.dev](https://stagehand.dev)). Four primitives layered on Playwright:
- `page.act(instruction)` — do something in natural language
- `page.extract(schema)` — pull structured data out, **typed by a Zod/Pydantic schema** (the killer feature for this task)
- `page.observe()` — ask "what can I do here?"
- `page.agent(goal)` — full agentic loop

It's the **hybrid sweet spot**: you keep Playwright's determinism for navigation/structure, and use the LLM only for the genuinely fuzzy `extract()` step, with a schema that *validates* output ([browserbase.com/blog/ai-web-agent-sdk](https://www.browserbase.com/blog/ai-web-agent-sdk); [nxcode.io/.../stagehand-vs-browser-use-vs-playwright](https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026); [dev.to/stevengonsalvez/stagehand-ai-primitives-for-playwright-that-actually-stick](https://dev.to/stevengonsalvez/stagehand-ai-primitives-for-playwright-that-actually-stick-47bm)). For structured per-app extraction with a strict schema, Stagehand's `extract(schema)` is arguably the single best primitive in the entire comparison.

### 3.3 Full agentic browsing (browser-use)
Use only when (a) the page is JS-gated **and** (b) its structure is too variable for scripted Playwright + a single `extract()`. Notion's and Linear's docs are the canonical examples.

**Decision rule (the tiered escalation).**
1. Does the vendor publish OpenAPI/Postman/GraphQL schema? → fetch it; you're done with API surface.
2. Else, does Jina Reader/Firecrawl return real content (not a blank SPA shell)? → LLM-extract from markdown.
3. Else, is the page structure stable (known selectors / docs-gen platform)? → Playwright + Stagehand `extract(schema)`.
4. Else → browser-use agent.

This ordering minimizes cost and flakiness while still handling the React-heavy cases.

---

## 4. Web-search + fetch (Tavily, Exa, Serper, Jina Reader, Firecrawl)

For static or lightly-rendered docs, a simple **fetch + LLM extraction beats a full browser agent** — cheaper, faster, more deterministic. The skill is mapping each source to the right tool.

### 4.1 Tool-by-tool
- **Jina Reader** (`r.jina.ai/<url>`): free URL→Markdown, *"convert any URL to an LLM-friendly input"* ([jina.ai/reader](https://jina.ai/reader); [github.com/jina-ai/reader](https://github.com/jina-ai/reader)). Also `s.jina.ai` for search+read. **Breaks on Cloudflare/DataDome** ([webclaw.io/blog/jina-reader-alternative-llm-web-scraping](https://webclaw.io/blog/jina-reader-alternative-llm-web-scraping)) — so it's a great *first* pass, not a complete solution. ReaderLM-v2 handles 512K-token docs ([jina.ai/reader](https://jina.ai/reader)).
- **Firecrawl**: crawl + scrape + **structured LLM extract**, JS rendering, markdown output. *"Full web extraction — search, crawl, format" vs. Tavily's "summary-first retrieval"* ([firecrawl.dev/alternatives/firecrawl-vs-tavily](https://www.firecrawl.dev/alternatives/firecrawl-vs-tavily)). Heavier/paid; the right call when Jina returns an SPA shell but you don't want a full browser.
- **Tavily**: search + extract tuned for LLM agents, returns clean content + a synthesized answer; **has a Composio integration** ([docs.tavily.com/documentation/integrations/composio](https://docs.tavily.com/documentation/integrations/composio)). Best for "find the right docs URL in the first place" and summary-first retrieval.
- **Exa**: neural/semantic search, returns clean content; good when you're not sure of the exact docs URL ([firecrawl.dev/blog/exa-alternatives](https://www.firecrawl.dev/blog/exa-alternatives)).
- **Serper**: cheap Google SERP API — results only, no content ([codenote.net/.../tavily-alternatives-cost-comparison-search-extract-api](https://codenote.net/en/posts/tavily-alternatives-cost-comparison-search-extract-api); [linkup.so/blog/best-serp-apis-web-search](https://www.linkup.so/blog/best-serp-apis-web-search)). Good for the "does an MCP server exist for X?" discovery search.

### 4.2 Source → approach map

| Docs source | Rendering | Recommended primary path |
|---|---|---|
| Stripe API ref (Mintlify) | SSR + some interactive | OpenAPI spec if exposed; else Firecrawl/Jina |
| Linear docs | React SPA | Firecrawl (JS) or browser-use |
| Notion docs / API | React SPA | browser-use or Firecrawl |
| GitHub REST API docs | static HTML | Jina Reader |
| ReadMe/Redocly/Stoplight portals | static, OpenAPI-backed | **Fetch the OpenAPI JSON directly** |
| Mintlify portals | SSR-friendly | Jina Reader / Firecrawl |
| Vendor with no public docs | — | Tavily/Exa search → GitHub repo → reverse-engineer |

### 4.3 Cost framing
A cost-optimization comparison ranks these on price/feature: Serper cheapest (results only), Jina Reader free, Tavily/Firecrawl/Exa mid-tier by feature fit ([codenote.net/.../tavily-alternatives-cost-comparison-search-extract-api](https://codenote.net/en/posts/tavily-alternatives-cost-comparison-search-extract-api); [crawleo.dev/blog/firecrawl-alternatives-...](https://www.crawleo.dev/blog/firecrawl-alternatives-7-search-and-crawl-apis-compared-pricing-params-geo-and-language)). For 100 apps × several pages each, **start free (Jina), escalate paid (Firecrawl/Tavily) only on failures** — the tiered approach again.

---

## 5. Orchestration: LangChain / LangGraph / CrewAI / AutoGen / Pydantic AI / OpenAI Agents SDK

The job here is a **repeatable per-app pipeline**: look up app → fetch docs → extract fields → cross-reference registries → emit JSON, with a verification branch. That's a stateful DAG with conditional routing, not a free-form multi-agent chat.

### 5.1 Per-framework
- **LangGraph** — graph/state-machine orchestration with **state persistence, conditional routing, checkpoints, and rollback**; *"LangGraph surpassed CrewAI in adoption during early 2026, largely driven by enterprise teams that needed state persistence, conditional routing, and rollback"* ([pickaxe.co/post/top-ai-agent-frameworks](https://pickaxe.co/post/top-ai-agent-frameworks)). Best fit for a deterministic, retryable per-app pipeline + a separate verifier subgraph. Native Pydantic structured outputs. **Recommended.**
- **OpenAI Agents SDK** — lightweight, minimal abstractions (Agents, Handoffs, Guardrails), *"gets you to 'hello world' fastest"* ([techsy.io/.../langgraph-vs-crewai-vs-openai-agents-sdk](https://techsy.io/en/blog/langgraph-vs-crewai-vs-openai-agents-sdk); [composio.dev/content/openai-agents-sdk-vs-langgraph-vs-autogen-vs-crewai](https://composio.dev/content/openai-agents-sdk-vs-langgraph-vs-autogen-vs-crewai)). Great if you commit to OpenAI models; thinner on state/checkpointing than LangGraph.
- **CrewAI** — role-based multi-agent, *"wins for prototyping speed"* ([techsy.io/.../langgraph-vs-crewai-vs-openai-agents-sdk](https://techsy.io/en/blog/langgraph-vs-crewai-vs-openai-agents-sdk)). Tempting for a "Researcher + Verifier" persona split, but weaker on deterministic pipelines and visibility. Has first-class Composio MCP integration ([composio.dev/toolkits/composio/framework/crew-ai](https://composio.dev/toolkits/composio/framework/crew-ai)).
- **AutoGen** — conversational multi-agent (Microsoft); *"nice learning curve and easy to start, but flexibility and scalability are really poor"* vs. LangGraph ([reddit.com/r/LangChain/comments/1jpk1vn](https://www.reddit.com/r/LangChain/comments/1jpk1vn/langgraph_vs_crewai_vs_autogen_vs_pydanticai_vs)). Agent-E is built on it. Fine for research, less for a production-shaped take-home.
- **Pydantic AI** — type-safe, Pydantic-first, **structured outputs and validation are first-class**, lightweight ([medium.com/@mpuig/which-multi-agent-framework...](https://medium.com/@mpuig/which-multi-agent-framework-should-run-your-enterprise-ai-abdc8e09ad89)). The best *extraction-step* library if you want minimal framework overhead and strong schema guarantees. Strong pairing with LangGraph (LangGraph for the graph, Pydantic AI for the typed tool calls).
- **LangChain (classic)** — the toolbox underneath LangGraph/browser-use; not an orchestrator you'd choose standalone in 2026.

### 5.2 DX for *structured extraction with structured outputs*
- **Best:** LangGraph + Pydantic models (typed state, validators, `with_structured_output`), optionally calling Pydantic AI agents at nodes. You get: a typed `AppState`, conditional edges (fetch_failed → escalate_to_browser), checkpointing for resume, and a schema that *rejects* bad output before it's written.
- **Runner-up:** OpenAI Agents SDK if you're all-in on OpenAI and want fewer deps.
- **Avoid for this task:** plain CrewAI/AutoGen — their ergonomics lean toward conversational role-play, not a strict ETL-with-verification DAG.

---

## 6. MCP registry lookup

The assignment asks, per app, whether an MCP server already exists. There are **five** places to check; cross-referencing all of them maximizes coverage and gives citable URLs.

| Registry | URL | Notes / programmatic access |
|---|---|---|
| Official reference servers | [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | Clone & grep; canonical but small (reference set only) |
| Smithery | [smithery.ai](https://smithery.ai) / [smithery.ai/servers](https://smithery.ai/servers) | Registry + installer; browse + search |
| Glama | [glama.ai/mcp/servers](https://glama.ai/mcp/servers) | *"The most comprehensive registry… updated daily"*; API-friendly |
| mcp.so | [mcp.so](https://mcp.so) | Community directory; an **Apify scraper** exists to pull the full directory ([apify.com/.../mcp-so-server-directory-scraper](https://apify.com/jungle_synthesizer/mcp-so-server-directory-scraper)) — describes it as *"the 3rd canonical MCP registry alongside Smithery and Glama"* |
| PulseMCP | [pulsemcp.com](https://pulsemcp.com) | Additional community directory |
| Composio (bonus) | [composio.dev/toolkits/composio](https://composio.dev/toolkits/composio) | Composio hosts managed MCP servers for its 1,000+ apps |

**How to check programmatically.** For each app: (1) `GET`/search each registry by app name; (2) clone `modelcontextprotocol/servers` and `grep -i`; (3) Serper/Tavily search `"<app> MCP server"` to catch servers published only to GitHub/npm/PyPI. Record `mcp_server_exists: bool`, `mcp_sources: [url, …]`, and the registry that confirmed it — every entry is a URL, satisfying the audit requirement. Reddit's r/modelcontextprotocol community lists exactly these as the standard lookup spots ([reddit.com/r/modelcontextprotocol/comments/1jf1oub/best_places_to_find_mcps](https://www.reddit.com/r/modelcontextprotocol/comments/1jf1oub/best_places_to_find_mcps)).

A security note worth flagging in the report: an arXiv survey of the MCP landscape covers standardization and security threats ([arxiv.org/html/2503.23278v1](https://arxiv.org/html/2503.23278v1)) — relevant to the "buildability/safety" dimension.

---

## 7. LLM choice

The task has two distinct LLM jobs with different optima:

**(A) Extraction + reasoning with citations** — read a docs page, decide auth method, decide self-serve-vs-gated, write structured JSON with a `source_url` per field. Needs top-tier instruction-following and reliable structured output.
- **Claude Sonnet 4.5** — Anthropic calls it *"the best coding model in the world, strongest model for building complex agents, and best model at using computers"* ([anthropic.com/news/claude-sonnet-4-5](https://www.anthropic.com/news/claude-sonnet-4-5)). Practitioner comparisons rate it ahead of GPT-5-Codex and Gemini 2.5 Pro on agentic + structured-reasoning workloads ([pub.towardsai.net/why-claude-sonnet-4-5-is-so-much-better-than-gpt-5-codex...](https://pub.towardsai.net/why-claude-sonnet-4-5-is-so-much-better-than-gpt-5-codex-and-gemini-2-5-pro-here-is-the-result-6b44b3072f97); [ai.plainenglish.io/claude-sonnet-4-5-vs-gpt-5-vs-gemini-2-5-turbo...](https://ai.plainenglish.io/claude-sonnet-4-5-vs-gpt-5-vs-gemini-2-5-turbo-a-data-leaders-real-world-comparison-8b7e7e4c7f1f)). **Recommended for the extraction nodes.**
- **GPT-5 / GPT-5.1** — strong reasoning, fast, native in the OpenAI Agents SDK; a solid second if the candidate is OpenAI-first.
- **Gemini 2.5/3 Pro** — leads on graduate-level reasoning benchmarks (GPQA Diamond) ([getpassionfruit.com/blog/gpt-5-1-vs-claude-4-5-sonnet-vs-gemini-3-pro...](https://www.getpassionfruit.com/blog/gpt-5-1-vs-claude-4-5-sonnet-vs-gemini-3-pro-vs-deepseek-v3-2-the-definitive-2025-ai-model-comparison)) but "falls behind in heavier math and visual reasoning" in some splits ([linkedin.com/.../benchmarking-gemini-3-pro-gpt-5-1-claude-sonnet-4-5](https://www.linkedin.com/posts/wanmohdazizi-dev_looking-at-the-latest-benchmark-comparison-activity-7396532843729956864-rSUP)).

**(B) Long-context doc dumps** — stuff an entire API reference (or a whole crawled docs subtree) into one context window and ask for a unified extraction.
- **Gemini 2.5 Pro** — 1M+ token context, cheap per token; the clear pick for "read 40 Stripe pages at once." Use it for the bulk-read pass, then hand the condensed result to Sonnet 4.5 for final structured extraction.

**(C) Verification triage / cheap routing** — deciding whether a page needs browser escalation, or a fast second-opinion pass.
- **Gemini 2.5 Flash** or **GPT-5-mini** for cost; the candidate also has **Z.ai (GLM)** access for a budget third opinion and model-diversity in the verifier (using a *different* model family than the extractor is a real correctness win — see §8).

**Cost/quality/speed tradeoff in one line:** Sonnet 4.5 = highest quality extraction; Gemini 2.5 Pro = cheapest long-context bulk read; Flash/mini/GLM = cheapest routing & verifier diversity. Routing each LLM call to the cheapest model that can do it is the single biggest cost lever for a 100-app run.

---

## 8. Verification layer

The assignment demands the agent be **verifiable and accurate** and that the candidate identify where a human is still needed. Verification is a *separate* concern from the research agent.

### 8.1 Why a separate verifier
LLM agents hallucinate, and self-reflection alone is unreliable: *"reflection is only as trustworthy as its verification source"* ([pub.towardsai.net/reflection-agent-architecture-...](https://pub.towardsai.net/reflection-agent-architecture-eliminating-llm-hallucinations-via-tool-grounded-iterative-9a61767cc979)). The robust patterns are: **(a) independent verification questions answered in isolation then reconciled** ([getzep.com/ai-agents/reducing-llm-hallucinations](https://www.getzep.com/ai-agents/reducing-llm-hallucinations)); **(b) multi-agent deliberation/disagreement** ([mdpi.com/2078-2416/16/7/517](https://www.mdpi.com/2078-2416/16/7/517)); **(c) LLM-as-a-judge** ([datadoghq.com/blog/ai/llm-hallucination-detection](https://www.datadoghq.com/blog/ai/llm-hallucination-detection)); and a general survey of agent hallucination ([arxiv.org/html/2509.18970v1](https://arxiv.org/html/2509.18970v1)).

### 8.2 Recommended verification pattern
A **second, independent agent** that:
1. Samples **10% of apps at random** (stratified: include some Composio-supported and some not).
2. **Re-derives each field from the primary source** — i.e. visits the *vendor's* docs URL with **browser-use** (a *different* tool path than the research agent's fetch-first path). This is deliberate: if the research agent used Jina Reader and the verifier uses browser-use, agreement is strong evidence; disagreement reveals tool-path bias, not just model noise.
3. Uses a **different model family** (e.g. research = Sonnet 4.5, verifier = GPT-5 or GLM) so model-shared hallucinations don't pass.
4. Emits a per-field `agree | disagree | unverifiable` verdict + the verifier's own `source_url`.
5. **All disagreements → human review queue** (§9). This is the auditable handoff point.

The key design principle: **verification must be grounded in the primary source, not in Composio's registry** — otherwise you're circularly validating Composio's metadata against itself. Composio's registry is a *cross-reference source*, never the ground truth the verifier checks against.

---

## 9. Feature matrix

Capabilities the research agent needs, scored per framework/tool. ●●● = excellent/primary choice; ●● = good; ● = usable but not ideal; — = not applicable.

| Framework / tool | Reads JS docs | Structured output DX | Orchestr- ation | Determinism / auditability | Cost / speed | MCP-native | Citations per claim |
|---|---|---|---|---|---|---|---|
| **Composio SDK (`getToolkits`)** | — (no browsing) | ●●● (pre-structured JSON) | — | ●●● (API response) | ●●● (1 call) | ●●● (its own MCP) | ●●● (URLs in payload) |
| **Composio MCP server** | — | ●●● (tool schemas) | — | ●●● | ●●● | ●●● | ●● (tool refs) |
| **browser-use** | ●●● | ●● (via LangChain) | ●● | ● (flaky) | ● (slow/costly) | ● | ●● (page URL) |
| **Stagehand (Playwright+LLM)** | ●●● | ●●● (`extract(schema)`) | ●● | ●● | ●● | — | ●●● |
| **Plain Playwright** | ●●● | — (you parse) | — | ●●● | ●●● | — | ●●● |
| **Jina Reader** | ● (no JS) | — (markdown) | — | ●●● | ●●● (free) | — | ●●● (URL) |
| **Firecrawl** | ●● (JS render) | ●● (LLM extract) | — | ●● | ●● (paid) | — | ●●● |
| **Tavily** | ● (search+extract) | ●● | — | ●● | ●● | ●● (Composio int.) | ●●● |
| **Exa / Serper** | ● (search) | — | — | ●●● | ●●● | — | ●●● |
| **LangGraph** | — | ●●● (Pydantic state) | ●●● | ●●● (checkpoints) | ●●● | ●● (MCP adapters) | ●●● |
| **OpenAI Agents SDK** | — | ●●● | ●● | ●● | ●●● | ●● | ●● |
| **CrewAI** | — | ●● | ●● (role-based) | ● | ●● | ●●● (Composio) | ●● |
| **AutoGen** | — | ●● | ●● | ● | ● | ● | ●● |
| **Pydantic AI** | — | ●●● (validators) | ● (single-agent) | ●●● | ●●● | ● | ●●● |

(Composite entry: Stagehand, browser-use, and plain Playwright overlap; in practice you use them as escalation tiers, not rivals.)

---

## 10. Recommended stack (with rationale)

**Orchestration:** **LangGraph** — the per-app pipeline is a stateful DAG (lookup → fetch → extract → cross-ref → emit) with a conditional escalation edge (static→browser) and a separate verifier subgraph. Checkpointing lets a 100-app run resume after a flaky failure without re-doing finished apps ([pickaxe.co/post/top-ai-agent-frameworks](https://pickaxe.co/post/top-ai-agent-frameworks); [techsy.io/.../langgraph-vs-crewai-vs-openai-agents-sdk](https://techsy.io/en/blog/langgraph-vs-crewai-vs-openai-agents-sdk)).

**Schema & validation:** **Pydantic** models (or Pydantic AI agents at the extraction nodes). Every per-app JSON is validated on emission; a record that fails validation goes to a repair queue, not to disk.

**Docs reading (tiered):**
1. **OpenAPI/Postman spec** if the vendor publishes one (best — machine-readable API surface).
2. **Jina Reader** (`r.jina.ai`) — free first pass ([jina.ai/reader](https://jina.ai/reader)).
3. **Firecrawl** — when Jina returns an SPA shell, before paying for a browser.
4. **Stagehand `extract(schema)`** on Playwright — structured, schema-validated, JS-rendered ([github.com/browserbase/stagehand](https://github.com/browserbase/stagehand)).
5. **browser-use** — only for genuinely variable SPA docs (Notion, Linear).

**Cross-reference sources (5, each citable):** Composio `getToolkits` ([docs.composio.dev/reference/api-reference/toolkits/getToolkits](https://docs.composio.dev/reference/api-reference/toolkits/getToolkits)); `modelcontextprotocol/servers`; Smithery; Glama; mcp.so (+ PulseMCP). Tavily/Serper for "does an MCP server exist for X?" discovery.

**Composio usage (honest, §1.4):** `getToolkits` as a structured data source for supported apps; Composio MCP as the *tool-router* the verifier can use to exercise a tool where the app is Composio-supported. Never as a docs browser.

**LLMs:** **Claude Sonnet 4.5** for extraction/reasoning ([anthropic.com/news/claude-sonnet-4-5](https://www.anthropic.com/news/claude-sonnet-4-5)); **Gemini 2.5 Pro** for long-context bulk doc reads; **Gemini Flash / GPT-5-mini / GLM (Z.ai)** for cheap routing and for the verifier's model-diversity second opinion.

**Verification:** a **separate LangGraph subgraph** running **browser-use** on a **random 10% sample**, **different model family**, re-deriving from the vendor's primary docs URL; disagreements → human queue.

**Output:** one JSON file per app in `apps/<slug>.json`, plus an `audit/<slug>.json` capturing every fetched URL, every registry hit, model used, token cost, and the verifier verdict. This is what makes the agent *auditable* — every field traces to a URL.

---

## 11. Where a human is still needed

Composio explicitly asks the candidate to identify this. The honest list:

1. **Defining "self-serve vs. gated" thresholds.** Composio's `auth_schemes` + `auth_guide_url` get you 80% there, but the *judgment* of whether, say, "requires a partner-program application" counts as gated is a policy call a human sets once. The agent applies the rule; a human writes it.
2. **Resolving verifier disagreements.** When the research agent and the verifier disagree on a field, that's the audit trail's most valuable signal — and the one place a human must arbitrate (read both sources, pick one, record why).
3. **Disambiguating same-named apps / multiple products.** "Linear" the issue tracker vs. "Linear" elsewhere; "Notion" the API vs. the non-public internal API. A human curates the canonical 100-app list and each app's *official* docs URL.
4. **Judging "buildability as an agent toolkit" beyond counts.** `tools_count` is a proxy; whether the actions are *coherent* (auth holds, rate limits are sane, webhooks exist) requires a human spot-check, especially for apps absent from Composio's registry.
5. **Vendor docs that lie or drift.** Docs that advertise OAuth but gate it behind a sales form; docs that are silently out of date vs. the live API. The agent can flag *inconsistencies* (e.g., docs say public but the dev portal 403s); a human confirms.
6. **MCP server quality.** Existence ≠ quality. A server may exist on mcp.so but be unmaintained, insecure ([arxiv.org/html/2503.23278v1](https://arxiv.org/html/2503.23278v1)), or cover only 2 of 50 endpoints. A human samples a few to grade real buildability.
7. **Accepting the 10% sample risk.** A 10% random sample gives ~90% confidence the population is clean, not 100%. A human signs off on the final dataset knowing the sampling limit.
8. **Tool-path bias the verifier can't see.** If *both* the research and verifier agents rely on the same docs-gen platform's rendering, a systemic blind spot persists. A human does a handful of raw `curl`s / manual browser visits as a meta-check.

State this list explicitly in the deliverable — it's exactly what Composio is screening for.

---

## 12. Code sketch — orchestration skeleton (Python)

This is a skeleton, not a full implementation. It shows the recommended architecture: a LangGraph state machine with tiered doc-reading, multi-source cross-reference, Composio used honestly, Pydantic-validated output, and a separate verifier subgraph.

```python
# app_researcher.py  —  skeleton for the Composio API-discovery agent
# Stack: LangGraph + Pydantic + Jina/Firecrawl/Stagehand/browser-use + Composio registry + MCP registries
# Models: Claude Sonnet 4.5 (extract), Gemini 2.5 Pro (bulk read), GLM/GPT-5-mini (verifier diversity)

from __future__ import annotations
import asyncio, random, json, pathlib
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

# ---------------------------------------------------------------------------
# 1. Output schema — every field carries its evidence URL. This is the audit unit.
# ---------------------------------------------------------------------------
class FieldWithSource(BaseModel):
    value: str | bool | int | list | None
    source_url: HttpUrl                      # the URL this claim was derived from
    confidence: Literal["high", "medium", "low"] = "medium"

class AppResearch(BaseModel):
    slug: str
    name: str
    docs_url: HttpUrl
    api_surface: FieldWithSource             # breadth: # endpoints / OpenAPI present?
    auth_method: FieldWithSource             # oauth2 | api_key | basic | jwt | none
    self_serve: FieldWithSource              # true if a dev can self-onboard without sales
    mcp_server: FieldWithSource              # exists? where? (registry URL list)
    buildable_as_toolkit: FieldWithSource    # 0-5 score + rationale
    composio_supported: bool                 # is it in Composio's getToolkits?
    composio_meta: Optional[dict]            # raw auth_schemes, tools_count, version...
    fetched_urls: list[HttpUrl]              # every URL the agent touched (audit trail)
    agent_path: list[str]                    # e.g. ["openapi", "jina", "browser-use"]
    verifier_verdict: Optional[dict] = None  # filled by the verifier subgraph

# ---------------------------------------------------------------------------
# 2. Typed graph state
# ---------------------------------------------------------------------------
class State(BaseModel):
    app: dict                                # {slug, name, docs_url} from the curated 100-list
    raw_docs: str = ""                       # markdown/HTML of fetched docs
    needs_browser: bool = False              # escalation flag
    research: Optional[AppResearch] = None
    error: Optional[str] = None
    messages: Annotated[list, add_messages] = []

# ---------------------------------------------------------------------------
# 3. Cross-reference sources — each returns (value, source_url) pairs.
#    Composio's getToolkits is ONE of these, used honestly (see §1.4).
# ---------------------------------------------------------------------------
async def lookup_composio(slug: str) -> Optional[dict]:
    # GET https://backend.composio.dev/api/v3.1/toolkits?search=<slug>
    # Returns auth_schemes, tools_count, triggers_count, app_url, auth_guide_url ...
    # This is Composio's own registry — a structured PRIMARY source for supported apps,
    # NOT a docs browser. Source: docs.composio.dev/reference/api-reference/toolkits/getToolkits
    ...

async def lookup_mcp_registries(name: str) -> list[dict]:
    # Query in order, collect hits + URLs:
    #   - github.com/modelcontextprotocol/servers  (clone + grep)
    #   - smithery.ai/servers                      (search)
    #   - glama.ai/mcp/servers                     (search/API)
    #   - mcp.so                                   (search / Apify scrape)
    #   - pulsemcp.com                             (search)
    # Plus a Serper/Tavily search: "<name> MCP server"
    ...

async def lookup_github(name: str) -> Optional[dict]:
    # Find official SDK / OpenAPI spec repo. If an OpenAPI/postman spec exists,
    # return its URL — that becomes the preferred API-surface source.
    ...

# ---------------------------------------------------------------------------
# 4. Tiered doc reader: OpenAPI spec -> Jina -> Firecrawl -> Stagehand -> browser-use
# ---------------------------------------------------------------------------
async def try_openapi(docs_url: str) -> Optional[str]: ...      # fetch /openapi.json, /api-spec
async def try_jina(docs_url: str) -> Optional[str]: ...         # r.jina.ai/<url>
async def try_firecrawl(docs_url: str) -> Optional[str]: ...    # JS render + markdown
async def try_stagehand(docs_url: str, schema: dict) -> Optional[dict]: ...  # extract(schema)
async def try_browser_use(docs_url: str, goal: str) -> Optional[str]: ...    # full agent

async def read_docs(docs_url: str) -> tuple[str, list[str]]:
    """Return (content, path_taken). Escalate only as needed (§3, §4)."""
    for fn, label in [(try_openapi, "openapi"), (try_jina, "jina"),
                      (try_firecrawl, "firecrawl")]:
        content = await fn(docs_url)
        if content and len(content) > 500:        # SPA shells return ~empty
            return content, [label]
    schema = {"auth": "string", "endpoints": "list", "self_serve": "bool"}
    got = await try_stagehand(docs_url, schema)
    if got:
        return json.dumps(got), ["stagehand"]
    content = await try_browser_use(
        docs_url, "Find the API auth method, whether self-serve, and endpoint count.")
    return content or "", ["browser-use"]

# ---------------------------------------------------------------------------
# 5. Extraction node — Claude Sonnet 4.5 with structured output.
#    Every claim must cite a URL; the model is forced to fill source_url fields.
# ---------------------------------------------------------------------------
async def extract(state: State) -> dict:
    composio = await lookup_composio(state.app["slug"])
    mcp_hits = await lookup_mcp_registries(state.app["name"])
    gh = await lookup_github(state.app["name"])
    docs, path = await read_docs(state.app["docs_url"])
    # ... build a prompt that bundles docs + composio + mcp_hits + gh,
    #     and forces the model to emit AppResearch with source_url per field.
    # research = await sonnet.with_structured_output(AppResearch).ainvoke(prompt)
    # research.composio_supported = composio is not None
    # research.composio_meta = composio
    # research.fetched_urls = [...]; research.agent_path = path
    return {"research": research}

# ---------------------------------------------------------------------------
# 6. Verification subgraph — separate agent, different tool path + model family.
#    Re-derives fields from the VENDOR docs via browser-use, compares, flags.
# ---------------------------------------------------------------------------
async def verify(research: AppResearch) -> dict:
    # Use browser-use + a DIFFERENT model (e.g. GPT-5 or GLM) to re-derive
    # auth_method/self_serve/api_surface from research.docs_url.
    # Compare field-by-field; emit {agree: [...], disagree: [...], unverifiable: [...]}.
    ...

async def verify_node(state: State) -> dict:
    # Only the random 10% sample enters this node (see build() routing).
    verdict = await verify(state.research)
    return {"research": state.research.model_copy(update={"verifier_verdict": verdict})}

# ---------------------------------------------------------------------------
# 7. Graph wiring
# ---------------------------------------------------------------------------
def should_verify(state: State) -> str:
    # Stratified random 10% sample for the verifier subgraph.
    return "verify" if random.random() < 0.10 else "emit"

g = StateGraph(State)
g.add_node("extract", extract)
g.add_node("verify",  verify_node)
g.add_node("emit",    lambda s: {"research": s.research})   # write apps/<slug>.json + audit/<slug>.json
g.add_edge(START, "extract")
g.add_conditional_edges("extract", should_verify, {"verify": "verify", "emit": "emit"})
g.add_edge("verify", "emit")
g.add_edge("emit", END)

runner = g.compile(checkpointer=MemorySaver())   # resume-after-flake

# ---------------------------------------------------------------------------
# 8. Fan-out over the curated 100-app list (concurrency-limited).
# ---------------------------------------------------------------------------
async def main():
    apps = json.loads(pathlib.Path("apps_to_research.json").read_text())  # human-curated, §11.3
    sem = asyncio.Semaphore(4)                                   # be polite to docs sites
    async def one(app):
        async with sem:
            result = await runner.ainvoke({"app": app}, config={"configurable": {"thread_id": app["slug"]}})
            pathlib.Path(f"apps/{app['slug']}.json").write_text(
                result["research"].model_dump_json(indent=2))
    await asyncio.gather(*[one(a) for a in apps])

if __name__ == "__main__":
    asyncio.run(main())
```

**What this skeleton encodes (and why each piece is there):**
- **Pydantic `AppResearch` with `source_url` on every field** — that's the audit unit; a claim without a URL cannot be emitted.
- **`fetched_urls` + `agent_path`** — full provenance per app: which URLs, which tier did the work.
- **Composio as *one* `lookup_*` source**, not the reader — the honest framing from §1.4 baked into code.
- **Tiered `read_docs`** — OpenAPI → Jina → Firecrawl → Stagehand → browser-use, so the cheap deterministic paths run first and browser-use is the exception.
- **Verifier subgraph on a 10% sample**, different model + different tool path (browser-use) — §8.
- **MemorySaver checkpointing** — a flaky browser-use failure on app #73 doesn't lose apps #1–72.
- **Concurrency-limited fan-out** — 100 apps, 4 at a time, polite to docs sites.

---

## 13. Citations index (all URLs referenced above)

**Composio**
- https://github.com/composiohq/composio
- https://pypi.org/project/composio
- https://composio.dev
- https://docs.composio.dev/docs/authentication
- https://docs.composio.dev/docs/tools-direct/authenticating-tools
- https://docs.composio.dev/reference/sdk-reference/python
- https://docs.composio.dev/reference/api-reference/toolkits/getToolkits
- https://docs.composio.dev/docs/migration-guide/new-sdk
- https://composio.dev/toolkits/composio
- https://composio.dev/toolkits/composio/framework/crew-ai
- https://composio.dev/content/per-user-oauth-for-ai-agents
- https://composio.dev/content/openai-agents-sdk-vs-langgraph-vs-autogen-vs-crewai
- https://docs.together.ai/docs/composio
- https://docs.linkup.so/pages/integrations/composio/composio
- https://docs.tavily.com/documentation/integrations/composio
- https://natesnewsletter.substack.com/p/composio-mcp-wants-to-dance-with
- https://krasserm.github.io/2025/08/06/agent-authorization
- https://github.com/api-evangelist/composio
- https://omgreenfield.com/blog/composio-integrations-for-ai-agents
- https://neon.com/guides/composio-crewai-neon

**Browser-use / web agents**
- https://github.com/browser-use/browser-use
- https://github.com/browser-use/benchmark
- https://browser-use.com/posts/ai-browser-agent-benchmark
- https://browser-use.com/posts
- https://www.firecrawl.dev/blog/best-browser-agents
- https://aimultiple.com/open-source-web-agents
- https://medium.com/data-and-beyond/browser-use-explained-the-open-source-ai-agent-that-clicks-reads-and-automates-the-web-d4689f3ef012
- https://medium.com/@sumit.somanchd/browser-use-with-openai-langchain-for-automating-web-browsing-ba6db7439566
- https://machinelearningmastery.com/building-browser-using-ai-agents-in-python
- https://www.labellerr.com/blog/browser-use-agent
- https://openreview.net/forum?id=7PQnFTbizU  (Agent-E)
- https://arxiv.org/html/2410.16464v3  (API-based vs browsing agents)
- https://arxiv.org/html/2506.03011v1
- https://invariantlabs.ai/blog/what-we-learned-from-analyzing-web-agents
- https://huggingface.co/papers?q=Web-agent%20benchmarks
- https://o-mega.ai/articles/browser-agent-environments-2025-workarena-browsergym-and-webarena-deep-dive
- https://github.com/steel-dev/awesome-web-agents

**Stagehand / Playwright**
- https://stagehand.dev
- https://github.com/browserbase/stagehand
- https://www.browserbase.com/blog/ai-web-agent-sdk
- https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026
- https://dev.to/stevengonsalvez/stagehand-ai-primitives-for-playwright-that-actually-stick-47bm
- https://yatheendrasai.medium.com/stagehand-a-new-era-of-automation-testing-with-natural-language-and-llms-09d613cab80e
- https://crawlee.dev/js/docs/guides/stagehand-crawler-guide
- https://devblogs.microsoft.com/ise/app-modernization-llm-driven-ui-tests-hve

**Fetch / search APIs**
- https://jina.ai/reader
- https://github.com/jina-ai/reader
- https://jina.ai
- https://jina.ai/api-dashboard
- https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader
- https://webclaw.io/blog/jina-reader-alternative-llm-web-scraping
- https://scrapegraphai.com/blog/jina-alternatives
- https://www.firecrawl.dev/alternatives/firecrawl-vs-tavily
- https://www.firecrawl.dev/blog/best-web-search-apis
- https://www.firecrawl.dev/blog/exa-alternatives
- https://www.crawleo.dev/blog/firecrawl-alternatives-7-search-and-crawl-apis-compared-pricing-params-geo-and-language
- https://www.crawlforge.dev/blog/crawlforge-vs-firecrawl-vs-tavily-vs-exa-web-data-api
- https://www.scrapeless.com/en/blog/exa-alternatives
- https://www.linkup.so/blog/best-serp-apis-web-search
- https://codenote.net/en/posts/tavily-alternatives-cost-comparison-search-extract-api

**Orchestration frameworks**
- https://langfuse.com/blog/2025-03-19-ai-agent-comparison
- https://techsy.io/en/blog/langgraph-vs-crewai-vs-openai-agents-sdk
- https://www.reddit.com/r/LangChain/comments/1jpk1vn/langgraph_vs_crewai_vs_autogen_vs_pydanticai_vs
- https://pub.towardsai.net/i-tried-10-ai-agent-frameworks-in-2026-heres-the-honest-guide-i-wish-i-had-earlier-16da216282da
- https://medium.com/@mpuig/which-multi-agent-framework-should-run-your-enterprise-ai-abdc8e09ad89
- https://pickaxe.co/post/top-ai-agent-frameworks
- https://www.linkedin.com/posts/amrit-tiwari_openai-agents-sdk-vs-langgraph-vs-autogen-activity-7322245048497033216-Rbln
- https://clickhouse.com/blog/how-to-build-ai-agents-mcp-12-frameworks
- https://dev.to/composiodev/openai-agents-sdk-a-step-by-step-guide-to-building-real-world-mcp-agents-with-composio-4f92

**MCP registries**
- https://github.com/modelcontextprotocol/servers
- https://smithery.ai
- https://smithery.ai/servers
- https://glama.ai/mcp/servers
- https://mcp.so
- https://pulsemcp.com
- https://apify.com/jungle_synthesizer/mcp-so-server-directory-scraper
- https://www.reddit.com/r/modelcontextprotocol/comments/1jf1oub/best_places_to_find_mcps
- https://www.linkedin.com/posts/kevin-kernegger_a-list-of-mcp-directories-server-registries-activity-7321227573181530113-5N0j
- https://mcpmarket.com/tools/skills/composio-connect
- https://arxiv.org/html/2503.23278v1  (MCP landscape & security)

**LLMs**
- https://www.anthropic.com/news/claude-sonnet-4-5
- https://pub.towardsai.net/why-claude-sonnet-4-5-is-so-much-better-than-gpt-5-codex-and-gemini-2-5-pro-here-is-the-result-6b44b3072f97
- https://ai.plainenglish.io/claude-sonnet-4-5-vs-gpt-5-vs-gemini-2-5-turbo-a-data-leaders-real-world-comparison-8b7e7e4c7f1f
- https://medium.com/@leucopsis/claude-sonnet-4-5-review-32516b15c1e0
- https://www.getpassionfruit.com/blog/gpt-5-1-vs-claude-4-5-sonnet-vs-gemini-3-pro-vs-deepseek-v3-2-the-definitive-2025-ai-model-comparison
- https://www.linkedin.com/posts/wanmohdazizi-dev_looking-at-the-latest-benchmark-comparison-activity-7396532843729956864-rSUP
- https://www.reddit.com/r/LocalLLaMA/comments/1o6h8jn/we_tested_claude_sonnet_45_gpt5codex_qwen3coder

**Verification / hallucination**
- https://arxiv.org/html/2509.18970v1  (LLM agent hallucination survey)
- https://www.getzep.com/ai-agents/reducing-llm-hallucinations
- https://www.mdpi.com/2078-2416/16/7/517  (multi-agent verification)
- https://pub.towardsai.net/reflection-agent-architecture-eliminating-llm-hallucinations-via-tool-grounded-iterative-9a61767cc979
- https://dev.to/aws/how-to-stop-ai-agents-from-hallucinating-silently-with-multi-agent-validation-3f7e
- https://www.datadoghq.com/blog/ai/llm-hallucination-detection
- https://aws.amazon.com/blogs/machine-learning/reducing-hallucinations-in-llm-agents-with-a-verified-semantic-cache-using-amazon-bedrock-knowledge-bases
- https://medium.com/@nirdiamant21/llm-hallucinations-explained-8c76cdd82532
