# Competitors & Prior Art: Automated API / Auth / Integration Discovery

**Purpose.** Briefing for the Composio take-home assignment ("research 100 apps' API surfaces, auth patterns, self-serve vs gated status, and buildability as an agent toolkit"). The goal is to make sure the candidate's research pipeline is informed by prior art rather than reinventing wheels.

**Method.** Ten focused web searches across the categories below, plus targeted follow-ups on Merge Blueprint, Nango `providers.yaml`, MCP registry counts, OpenAPI validation tooling, and Stripe/Klaviyo API audit posts. All URLs are cited inline and consolidated in the appendix.

**TL;DR.** The space splits into four camps:
1. **Unified-API vendors** (Merge, Nango, Apideck, Pipedream) — they ship *integrations*, not *research*. They tell you "this app has an API and we've already wired it up." They almost never publish a structured verdict on *how hard it was* or *whether you can self-serve*.
2. **OpenAPI directories** (APIs.guru, Postman API Network, RapidAPI Hub) — they catalog *specs*, not auth flows or agent-readiness. Validation is mostly linting, not behavioral testing.
3. **MCP registries** (mcp.so, Glama, PulseMCP, Smithery) — they catalog *servers*, but counts are inflated by duplicates and dead packages; quality bar is low and unverified.
4. **Academic work** (RESTler, semantic API classification) — rigorous but narrow; focused on fuzzing/classification, not "is this a good agent toolkit."

**Gap the candidate's project can uniquely own:** *no one* in the above camps produces a per-app scorecard that combines (a) auth-pattern classification, (b) self-serve vs gated verdict, and (c) "buildability as an agent toolkit" judgment. That triangulated verdict is novel and is the project's wedge.

---

## 1. Merge.dev — Unified API + AI-assisted integration building

**What they do.** Merge sells a single "Unified API" across seven categories (HRIS, ATS, Accounting, CRM, Ticketing, File Storage, MRM). Customers add integrations by hitting one canonical schema; Merge handles auth, pagination, webhooks, rate limits. ~893 companies tracked as customers (S&P Global, Revolut cited). Source: https://www.merge.dev and https://technologychecker.io/technology/merge

**How they ship new integrations — Merge Blueprint.** Blueprint (announced 2023, ongoing) is an AI-powered tool that reads API documentation and auto-infers the mapping between a third-party API and Merge's Unified API schemas. Originally powered by GPT-3.5; the user pastes a docs URL, Blueprint generates a starter integration. Sources:
- https://www.prnewswire.com/news-releases/merge-launches-blueprint-an-ai-powered-tool-for-adding-integrations-to-merges-unified-apis-301842936.html
- https://venturebeat.com/business/merge-unveils-blueprint-an-ai-powered-tool-to-enable-easier-api-integrations
- https://www.apifirst.tech/p/merge-blueprint-automating-integrations-with-ai
- https://www.youtube.com/watch?v=AhqyB-JTQkE (Merge's own "Meet Blueprint" video)
- https://medium.com/@deephearing_/streamline-api-integrations-with-merge-blueprint-empowering-developers-with-ai-powered-efficiency-729f2b6da76c

Blueprint is positioned as community-friendly: "Anyone can contribute to Merge's Unified API." This implies an editorial/QA review step on top of AI-generated drafts, but Merge does not publish their QA methodology.

**Dev experience.** "Link" widget handles end-user OAuth. The dev experience is a single SDK + webhook layer; you never see the upstream API. Good for product teams, bad for agents that want raw tool surface (you only get the unified subset). Source: https://www.merge.dev/integrations/linear and https://www.merge.dev/integrations/box

**What the candidate should copy:**
- AI-reads-the-docs-then-drafts-integration flow. Blueprint is the closest existing analog to "research 100 apps' APIs at scale." The candidate's project should adopt the same input shape (paste docs URL / spec URL) but produce a *verdict*, not a *wrapper*.
- "Anyone can contribute" framing — Merge normalizes community-submitted integrations. The candidate could publish their scorecards as a public dataset that invites PRs.
- Unified-API categorization (HRIS / ATS / CRM / …) — a clean taxonomy beats an alphabetical app list.

**What they don't do (opportunities for the candidate):**
- No public "buildability score." Merge either ships the integration or doesn't; the difficulty of doing so is internal.
- No "self-serve vs gated" classification. If the upstream API requires a partnership/sales call (e.g., Workday, SAP), Merge absorbs that pain silently. The candidate can expose it.
- No agent-toolkit verdict. Merge's Unified API is intentionally narrower than the upstream surface, which is the *opposite* of what an agent-toolkit builder wants.
- Blueprint's QA process is undocumented. The candidate can publish a transparent methodology (which checks ran, which failed).

**Self-serve vs gated handling:** Hidden inside Merge's internal backlog; not surfaced to customers.

---

## 2. Pipedream — 2,500+ integrations, MCP-everywhere

**What they do.** Pipedream is an integration/IPaaS platform with 2,500+ app integrations and 10,000+ pre-built actions. They launched 2,500+ MCP servers (one per app) in 2024–2025, each exposing the app's actions as MCP tools with built-in auth. Sources:
- https://pipedream.com/docs/connect/mcp
- https://pipedream.com/docs/changelog ("we're very excited to ship 2500+ Pipedream MCP servers with 10k+ tools")
- https://docs.leena.ai/docs/pipedream-mcp
- https://www.linkedin.com/posts/pipedreamhq_want-to-use-the-power-of-claude-with-your-activity-7317562750556139523-Gw1M

**How integrations are authored.** Pipedream apps are defined by a mix of (a) component code (Node.js) authored in their mono-repo `PipedreamHQ/pipedream` on GitHub, and (b) OAuth config. There is an OpenAPI-to-component flow, but it is not pure auto-generation — humans still hand-curate triggers and actions. Source: https://github.com/PipedreamHQ/pipedream and https://github.com/PipedreamHQ/awesome-mcp-servers

**MCP server.** One MCP server per app; auth and credentials are managed by Pipedream's hosted backend. This is essentially "every app we already integrated is now an MCP server for free." Source: https://pipedream.com/docs/connect/mcp

**OpenAPI-to-trigger auto-generation.** Stainless and Speakeasy publish the cleanest write-ups of the OpenAPI→MCP pipeline; both confirm the pattern works but suffers from "1:1 endpoint-to-tool mapping" problems (too many tiny tools, agents can't choose). Sources:
- https://www.stainless.com/mcp/convert-openapi-specs-to-mcp-servers
- https://www.stainless.com/blog/generate-mcp-servers-from-openapi-specs
- https://www.speakeasy.com/mcp/tool-design/generate-mcp-tools-from-openapi
- https://www.reddit.com/r/mcp/comments/1lr4itu/can_we_please_stop_pushing_openapi_spec_generated (community pushback on naive 1:1 mapping)

**What the candidate should copy:**
- One MCP per app is a useful unit. The candidate's "does this app already have an MCP?" lookup should hit Pipedream's list *and* the registries in §6.
- "10k+ tools" framing — separate the *app* count from the *tool* count. Agents care about tool count and granularity.
- Stainless' "three generations of MCP server design" framing (SDK code mode → OpenAPI 1:1 → higher-level programmatic tools) is worth borrowing for the candidate's "buildability" rubric. Source: https://www.youtube.com/watch?v=1YygZ62qsA0

**What they don't do:**
- Pipedream doesn't publish a per-app "this was hard to integrate" memo. Like Merge, the integration either exists or doesn't.
- No "self-serve vs gated" classification. Pipedream only ships apps where they could complete the OAuth dance; gated apps are simply absent from the catalog.
- OpenAPI→MCP tools are 1:1 with endpoints; no semantic grouping. This is *exactly* the gap the candidate's "buildability as agent toolkit" verdict should measure (tools should be coarse, composable, idempotent — not raw REST endpoints).

**Self-serve vs gated handling:** Implicit (absent = gated), not explicit.

---

## 3. Nango — open-source unified API + OAuth templates

**What they do.** Nango is an open-source platform (MIT/Apache) for building product integrations. They support 800+ APIs and ship a `providers.yaml` config file that defines OAuth2 (and API-key / Basic) flows for each provider. Sources:
- https://github.com/nangohq/nango
- https://nango.dev
- https://nango.dev/docs/integrations/api-configuration ("API configurations are listed in the providers.yaml file, located in the Nango GitHub repository")

**How they template auth.** Every provider is a YAML record in `providers.yaml`: `auth_mode` (OAUTH2 | API_KEY | BASIC | NONE), token endpoints, scopes, authorization URL, refresh behavior. This is the single best open dataset the candidate can reuse for *auth-pattern classification*. Source: https://nango.dev/docs/integrations/api-configuration and the repo itself at https://github.com/nangohq/nango (look for `packages/shared/providers.yaml`).

Nango uses `simple-oauth2` under the hood for the actual OAuth dance. Source: https://roopeshsn.com/bytes/how-nango-built-an-open-source-unified-api-platform

The Tango Elixir library is API-compatible with Nango's `providers.yaml` format — confirming this file has become a de-facto standard. Source: https://hexdocs.pm/tango

**What the candidate should copy:**
- **Steal `providers.yaml` directly.** It's a curated, community-maintained, machine-readable catalog of auth patterns for 800+ APIs. This is the single highest-leverage reuse in the entire project. The candidate should `git clone nango`, parse `providers.yaml`, and use `auth_mode` as the seed for their own auth-pattern column.
- Same YAML schema for new entries (their auth_mode enum is well thought out).
- The "anyone can contribute a provider via PR" workflow.

**What they don't do:**
- Nango's catalog is about *how to authenticate*, not *whether you're allowed to authenticate*. Self-serve vs gated is not modeled.
- No "agent toolkit" verdict. Nango provides raw provider definitions; you still need to build the tool wrappers yourself.
- No "buildability score." A provider being in `providers.yaml` means someone got OAuth to work — it says nothing about API consistency, rate limits, or tool design.
- No automatic detection of auth mode from docs. Nango's entries are human-curated.

**Self-serve vs gated handling:** None. Provider is listed or it isn't.

**Bonus relevant link:** TRMNL's `oauth2-providers` repo is a smaller community template set in the same spirit. Source: https://github.com/usetrmnl/oauth2-providers

---

## 4. Apideck — Unified API across CRM / Accounting / HR

**What they do.** Apideck sells unified APIs across ~7–8 verticals (Accounting, CRM, HRIS, File Storage, E-commerce, ATS, Issue Tracking, Lead Gen). Their pitch: "one canonical data model, 135+ platforms." Sources:
- https://www.apideck.com
- https://www.apideck.com/hris-api (59+ HR/payroll systems via one canonical model)
- https://www.apideck.com/blog/unified-to-alternatives ("200+ integrations across accounting, CRM, HRIS, file storage, ecommerce, ATS, and issue tracking")
- https://www.linkedin.com/products/apideck-unified-api (135+ platforms)

**Coverage pages.** Apideck has per-category coverage pages that list which platforms are supported in which category. They are human-readable tables, not machine-readable JSON.

**What the candidate should copy:**
- Vertical categorization (Accounting / CRM / HRIS / …) as a first-class dimension. Better than a flat app list.
- Public coverage tables as a UX pattern — easy to scan, easy to diff over time.

**What they don't do:**
- No public "buildability score" or auth-pattern breakdown.
- No "self-serve vs gated" classification. Same blind spot as Merge.
- Coverage is binary (supported / not), not graded.

**Self-serve vs gated handling:** Not surfaced.

---

## 5. Vellum / Portkey / LangChain Hub / LlamaIndex Hub — AI tool hubs

**What they do.**
- **LangChain Hub** — public registry of prompts, agents, and tools (mostly LangChain-native tool abstractions). Source: https://www.langchain.com and https://github.com/langchain-ai/langchain
- **LlamaIndex Hub (LlamaHub)** — registry of data loaders, tools, vector DB connectors, LLM integrations. Source: https://llamahub.ai
- **Portkey** — AI gateway + observability; its "registry" is really a list of supported LLM providers, not arbitrary SaaS tools. Source: https://portkey.ai/docs/virtual_key_old/integrations/libraries/llama-index-python and https://docs.langchain.com/oss/python/integrations/providers/portkey
- **Vellum** — workflow/eval platform; not a tool registry per se. Source: https://www.vellum.ai/blog/llamaindex-vs-langchain-comparison

**How they decide which tools to onboard.** None of the four publish a documented onboarding rubric. LangChain and LlamaIndex accept community PRs; the bar is "does it run and have tests." Portkey and Vellum curate LLM-provider lists internally.

**Most relevant adjacent comparators.** The candidates' project is closer to **Composio** itself (https://composio.dev — "20000+ tools across 500+ apps"), **Arcade.dev** (https://www.arcade.dev/blog/composio-alternatives), **StackOne**, and **Truto** (https://truto.one/blog/best-integration-platforms-for-langchain-llamaindex-data-retrieval — directly compares Composio, StackOne for LangChain/LlamaIndex). These are the direct competitors for "agent toolkit" catalogs.

**What the candidate should copy:**
- LlamaHub's per-loader page format: name, description, install command, code snippet, maintainer, last-updated. A clean unit for a per-app scorecard.
- Arcade.dev's comparison-table format (per Arcade's "Composio Alternatives" post) — these tables are how the market currently compares catalogs. Source: https://www.arcade.dev/blog/composio-alternatives

**What they don't do:**
- None of them publish *why* a tool was onboarded or rejected.
- None model auth-pattern or self-serve-vs-gated.
- None publish a "buildability" verdict; the implicit signal is "if it's in the hub, it builds" — which collapses a lot of useful information.

**Self-serve vs gated handling:** None of these hubs track it.

---

## 6. MCP server registries — the "does this app already have an MCP?" lookup layer

This is **directly relevant** to the candidate's project: the "is there already an MCP server for this app?" question is one of the lookup steps the candidate must perform. There are now multiple competing registries, each with different counts and quality bars.

**Counts (as of studiomeyer.io's April 2026 field report):**
- **Glama.ai** — 21,500+ open-source MCP servers indexed. Source: https://studiomeyer.io/en/blog/mcp-marketplaces-2026 and https://glama.ai/mcp/servers
- **MCP.so** — 20,000+ servers. Source: https://mcp.so and https://studiomeyer.io/en/blog/mcp-marketplaces-2026
- **PulseMCP** — 12,650 servers. Source: https://studiomeyer.io/en/blog/mcp-marketplaces-2026 (also referenced in https://explainx.ai/blog/top-10-mcp-server-directories-2026)
- **Smithery** — major discovery directory (crawls the ecosystem). Source: https://smithery.ai/blog/what-is-mcp and https://tallyfy.com/how-to-list-mcp-server-registry-smithery-glama-pulsemcp
- **MCP Market** — claims 10,000+ across 23 categories. Source: https://studiomeyer.io/en/blog/mcp-marketplaces-2026
- **Official MCP Registry** — run by the modelcontextprotocol org; the canonical record. Sources: https://safedep.io/the-state-of-mcp-registries and the official repo at https://github.com/modelcontextprotocol/servers
- **Apify scraper for MCP.so** — confirms MCP.so is treated as a structured data source by third parties. Source: https://apify.com/jungle_synthesizer/mcp-so-server-directory-scraper

**Quality bar.** Low and unverified. An arXiv measurement study (https://arxiv.org/html/2509.25292v3) explicitly notes that "MCP servers and MCP clients are indexed by multiple markets (e.g., Glama.ai, MCP.so, PulseMCP)" with "heterogeneous" metadata — i.e., the same server appears multiple times with conflicting fields. The studiomeyer.io field report reviews 33 marketplaces and finds widely varying governance and curation.

**What the candidate should copy:**
- The candidate's "does this app already have an MCP?" lookup should query **multiple registries in parallel** (Glama, MCP.so, PulseMCP, Smithery, official registry) and reconcile duplicates by GitHub repo URL — exactly the dedup problem the arXiv paper identifies.
- The studiomeyer.io "field report" format (per-marketplace: governance model, curation, enterprise-readiness, security) is a good template for evaluating the registries themselves.

**What they don't do:**
- None of the registries publishes a per-server "buildability" or "production-readiness" verdict. Counts are inflated by dead repos and duplicates.
- None classifies servers by the auth pattern of the upstream API.
- None flags "self-serve vs gated" for the underlying API the server wraps.
- Quality bar is "submitted, listed" — not "tested." The candidate's project can uniquely add a *behavioral* verification layer ("does this MCP server actually return data for an unauthenticated test call?").

**Self-serve vs gated handling:** Not modeled at all.

---

## 7. OpenAPI directory projects — cataloging & validation at scale

**APIs.guru / openapi-directory.** "Wikipedia for Web APIs." Comprehensive, standards-compliant, up-to-date directory of OpenAPI/Swagger specs. Pure catalog: specs in, browsable docs out. Sources:
- https://github.com/APIs-guru/openapi-directory
- https://apis.guru
- https://apis.guru/api-doc

**Postman API Network / Spec Hub.** Public catalog of API specs and request collections. Recently added an API Catalog and Spec Hub with versioning endpoints. Sources:
- https://www.postman.com/api-evangelist/apis-guru/request/j2j60dv/list-all-apis
- https://blog.postman.com/new-in-the-postman-api-v1-39-api-catalog-and-spec-hub-endpoints
- https://learning.postman.com/docs/design-apis/specifications/import-a-specification

**RapidAPI Hub.** Marketplace-style directory of 10,000+ APIs with in-browser testing and monetization. Source: https://community.make.com/t/check-out-these-useful-api-discovery-resources/2812 and https://nordicapis.com/13-api-directories-to-help-you-discover-apis

**Automated linters / validators the candidate can reuse.**
- **Spectral** (Stoplight) — open-source OpenAPI/AsyncAPI linter, rule-based, programmable. The de-facto standard. Sources: https://stoplight.io/open-source/spectral and https://medium.com/@mohamed.slimani/openapi-validation-by-spectral-lint-589278b4bde7
- **Postman's built-in validator** — contract testing on imported specs.
- **APIs.guru's own validation pipeline** — runs on every spec in the directory; the candidate can lift the ruleset. Source: https://github.com/APIs-guru/openapi-directory

**What the candidate should copy:**
- **Reuse APIs.guru as the canonical spec source for any of the 100 apps that publish OpenAPI.** Don't re-crawl; pull from their repo.
- **Use Spectral as the validator.** Don't write a custom OpenAPI linter; write a Spectral ruleset that scores "agent-friendliness" (operation IDs, descriptions, examples, idempotency hints).
- Postman Spec Hub's "version tags" pattern for tracking when an API changes.

**What they don't do:**
- APIs.guru validates the *spec*, not the *behavior*. A spec can be valid OpenAPI 3.0 and still describe an API that's unusable for agents (no docs, no examples, breaking changes weekly).
- No auth-pattern classification beyond what's in the spec's `securitySchemes` (often empty or wrong).
- No "self-serve vs gated" classification. The spec is either in the directory or it isn't.
- No "buildability as agent toolkit" verdict. The spec is treated as ground truth, not as raw material to be judged.

**Self-serve vs gated handling:** None. Spec present = "has API"; the rest is silence.

---

## 8. Academic / industry prior art on automated API discovery

**RESTler (Microsoft Research).** The first stateful REST API fuzzer. Reads a Swagger/OpenAPI spec, infers producer-consumer dependencies between request types, and generates sequences of requests that exercise the API's state machine. Used internally at Microsoft for cloud-service reliability testing. Sources:
- https://www.microsoft.com/en-us/research/publication/restler-stateful-rest-api-fuzzing
- https://www.microsoft.com/en-us/research/publication/rest-ler-automatic-intelligent-rest-api-fuzzing
- https://patricegodefroid.github.io/public_psfiles/icse2019.pdf (ICSE 2019 paper)
- https://github.com/microsoft/restler-fuzzer
- https://www.microsoft.com/en-us/research/publication/checking-security-properties-of-cloud-services-rest-apis (security-rules extension)

**Why this matters for the candidate:** RESTler proves that you can do *behavioral* discovery from a spec — i.e., infer what an API actually does, not just what it claims. The candidate's "buildability" verdict should ideally include a smoke-test step ("does this endpoint return 200 for an unauthenticated call?"); RESTler is the academic precedent for doing this systematically. The candidate probably doesn't need full stateful fuzzing, but the *dependency-inference* idea (which endpoints must be called before which) is directly useful for grading agent-toolkit quality.

**Other academic threads:**
- **Semantic web-service classification** — MDGCN-Lt and similar use graph convolutional networks to classify web APIs. Source: https://www.sciopen.com/article/10.26599/TST.2024.9010026
- **Crowdsourced Web API identification** — early AAAI work on automated API search engines. Source: https://fileadmin.cs.lth.se/ai/Proceedings/AAAI%20SSS%202012/01/SS12-04-014.pdf
- **Keeper (ICSE 2022)** — automated testing of software that uses ML APIs. Source: https://people.cs.uchicago.edu/~shanlu/paper/icse22.pdf
- **REST API fuzzing with LLMs** — recent work combining RESTler-style fuzzing with LLM-generated inputs. Source: https://www.mdpi.com/2673-4591/120/1/42

**What the candidate should copy:**
- The RESTler pattern of *inferring dependencies between endpoints from the spec* — directly applicable to grading "can an agent compose these tools?"
- Citing RESTler adds rigor: "we treat each app's API as a stateful surface and grade agent-readiness by inspection of (a) spec completeness, (b) endpoint compositionality, (c) auth gating."

**What they don't do:**
- None of these papers ask "is this API good for agents?" — they ask "is this API correct/secure?"
- None model auth-pattern classification or self-serve-vs-gated.
- None apply at the *catalog* level (100s of APIs); they're per-API tools.

**Self-serve vs gated handling:** Out of scope for the academic literature; that's an industry/product question, not a research one.

---

## 9. Open-source "API auth research" tools — auto-detecting OAuth2 vs API key vs Basic

**Honest finding: this category is thin.** There is no widely-adopted OSS tool that auto-detects auth pattern from docs or from a sample request. What exists:

- **Nango `providers.yaml`** (covered in §3) — the best available ground-truth dataset, but human-curated, not auto-detected. Source: https://github.com/nangohq/nango
- **Tango (Elixir)** — Nango-compatible provider config. Source: https://hexdocs.pm/tango
- **TRMNL `oauth2-providers`** — small community OAuth2 template set. Source: https://github.com/usetrmnl/oauth2-providers
- **`@octokit/auth-basic.js`** and similar per-vendor auth libraries — each handles one auth mode for one vendor; none generalizes. Source: https://github.com/octokit/auth-basic.js
- **Dev.to tutorial "How to Authenticate using Keys, BasicAuth, OAuth2 in Python"** — a manual pattern guide, not a detector. Source: https://dev.to/rahulbanerjee99/how-to-authenticate-using-keys-basicauth-oauth-in-python-4b8m
- **VishwamKumar/exp.rest-apis.auth-styles** — demo repo of auth strategies in ASP.NET Core. Source: https://github.com/VishwamKumar/exp.rest-apis.auth-styles

**What this means for the candidate:**
- There is **no off-the-shelf auth-pattern detector** to reuse. The candidate will need to build a small classifier themselves.
- The best heuristic available is: **parse the OpenAPI `securitySchemes` block** (when the spec exists), then **fall back to scraping the docs page for keywords** ("OAuth 2.0", "API key", "Bearer token", "Basic auth", "client credentials", "authorization code", "partner program", "apply for access").
- The candidate's classifier can be ~100 lines of regex + a small decision tree. This is *inventing*, not *stealing* — but the bar is low and the prior art is sparse, so it's a reasonable invention.

**What the candidate should copy:**
- Nango's `auth_mode` enum (OAUTH2 | API_KEY | BASIC | NONE) — reuse it as the classifier's output schema for compatibility with the existing ecosystem.

**What they don't do:**
- No tool auto-detects "self-serve vs gated." This requires reading the docs for phrases like "contact sales", "apply for access", "partner program", "enterprise only" — entirely greenfield.
- No tool produces a per-app "buildability" verdict.

**Self-serve vs gated handling:** No existing tool does this. **This is the candidate's biggest open lane.**

---

## 10. Recent (2024–2025) blog posts & talks on API audits

**Stripe — "APIs as infrastructure: future-proofing Stripe with versioning."** Stripe's canonical post on how they manage API versions, deprecations, and changelogs at scale. Not an "audit of N APIs," but the closest thing to a published methodology for *systematic* API governance. Source: https://stripe.com/blog/api-versioning

**Klaviyo — V1/V2 API retirement & migration.** Klaviyo overhauled their entire API surface, retiring v1/v2 by June 30, 2024 and shipping a new versioned API with scoped keys. Useful as a *case study* of what an API revamp looks like — and a reminder that "API surface" is a moving target. Sources:
- https://developers.klaviyo.com/en/docs/api_versioning_and_deprecation_policy
- https://developers.klaviyo.com/en/v1-2/reference/api-overview
- https://developers.klaviyo.com/en/v2023-02-22/docs/migrating_from_v1v2_to_the_new_klaviyo_apis
- https://community.klaviyo.com/developer-group-64/klaviyo-v1-v2-api-retirement-11262

**Landscape-level posts (closest to "we audited N APIs" genre):**
- **Kong — "The Rapidly Changing Landscape of APIs."** Industry-level audit of API trends. Source: https://konghq.com/blog/engineering/api-a-rapidly-changing-landscape
- **Postman — State of the API Report (annual).** The canonical industry survey; cited as the basis for "83% of enterprise workloads rely on APIs." Source: referenced in https://unizo.ai/blog/api-integration-guide-2025
- **InfoQ — "API Design Reviews Are Dead. Long Live API Design Reviews!"** Argues for living API catalogs that reflect real scope/depth. Source: https://www.infoq.com/articles/api-design-review
- **Victor Rentea — "Top 10 REST API Design Pitfalls" (Spring I/O 2025).** A practitioner's audit of common API mistakes. Source: https://www.youtube.com/watch?v=u_5JppAExDs

**What the candidate should copy:**
- The **Postman State of the API** survey framing — quantitative, sample-based, repeatable. The candidate's 100-app dataset is a *micro*-version of this.
- The **InfoQ "living API catalog"** framing — emphasize that the scorecard is a living document, versioned, diff-able over time.
- Stripe's **versioning/deprecation discipline** as one axis of the "buildability" rubric (an API that breaks weekly is a bad agent toolkit).

**What they don't do:**
- None of these posts audit APIs from the *agent-toolkit* angle. They audit from the *integration developer* angle (which is upstream of but not identical to agent-readiness).
- None classify self-serve vs gated.
- None produce a per-app scorecard; they're either per-API (Stripe, Klaviyo) or industry-level (Postman, Kong).

**Self-serve vs gated handling:** Not addressed in any of these posts.

---

## Cross-cutting observations

**How each camp handles "self-serve vs gated":**

| Camp | Handles self-serve vs gated? | How? |
|---|---|---|
| Unified-API vendors (Merge, Nango, Apideck, Pipedream) | No | Gated apps are silently absent from the catalog |
| OpenAPI directories (APIs.guru, Postman, RapidAPI) | No | Spec present = "has API"; gating is invisible |
| MCP registries (Glama, MCP.so, PulseMCP, Smithery) | No | Server submitted = listed; upstream gating ignored |
| Academic (RESTler et al.) | No | Out of scope; research focus is correctness/security |
| Auth tooling (Nango providers.yaml, etc.) | No | Auth pattern only; access gating not modeled |
| Industry audits (Stripe, Klaviyo, Postman survey) | No | Per-API or industry-level; no per-app gating verdict |

**Conclusion: no one models self-serve vs gated.** This is consistent across all 10 categories researched. It is the single most defensible "what we invented" claim the candidate can make.

**How each camp handles "buildability as agent toolkit":**

| Camp | Handles buildability-as-agent-toolkit? | Closest analog |
|---|---|---|
| Unified-API vendors | No (intentionally — they narrow the surface) | "Integration exists" = binary |
| Pipedream / Stainless / Speakeasy | Partial | OpenAPI→MCP tooling; community pushback on 1:1 mapping (Reddit r/mcp) |
| MCP registries | No | Server count = proxy; no quality verdict |
| OpenAPI directories | No | Spec validity = proxy |
| Academic | No | Correctness, not agent-readiness |
| Composio / Arcade / StackOne / Truto | Implicit | "In our catalog" = buildable; no published rubric |

**Conclusion: "buildability as agent toolkit" is also largely unmodeled.** The closest existing work (Stainless' "three generations of MCP server design," the r/mcp pushback on 1:1 OpenAPI→tool mapping) gives the candidate a vocabulary but not a rubric. The candidate can publish the rubric.

---

## What this project should steal vs invent

### Steal (do not reinvent)

1. **Nango's `providers.yaml`** — clone it, parse it, use `auth_mode` as the seed auth-pattern column for any of the 100 apps Nango already covers. This is the single biggest time-saver. Source: https://github.com/nangohq/nango
2. **APIs.guru's openapi-directory** — pull OpenAPI specs from here rather than re-crawling. Source: https://github.com/APIs-guru/openapi-directory
3. **Spectral** as the OpenAPI linter/validator — write a custom ruleset for "agent-friendliness" rather than a custom linter. Source: https://stoplight.io/open-source/spectral
4. **Multi-registry MCP lookup** — query Glama, MCP.so, PulseMCP, Smithery, and the official registry in parallel; dedupe by GitHub repo URL (the arXiv measurement study confirms dedup is a real problem). Sources: https://arxiv.org/html/2509.25292v3 and https://studiomeyer.io/en/blog/mcp-marketplaces-2026
5. **Nango's `auth_mode` enum** (OAUTH2 | API_KEY | BASIC | NONE) as the output schema for the candidate's auth classifier — for ecosystem compatibility.
6. **Merge's vertical taxonomy** (HRIS / ATS / CRM / Accounting / Ticketing / File Storage / MRM) as the category dimension.
7. **LlamaHub's per-loader page format** as the per-app scorecard UI pattern.
8. **RESTler's dependency-inference idea** as one input to the "buildability" rubric (which endpoints must compose with which).
9. **Stainless' "three generations of MCP server design" framing** as vocabulary for the buildability verdict. Source: https://www.youtube.com/watch?v=1YygZ62qsA0
10. **Postman State of the API** survey methodology — quantitative, sample-based, repeatable, annual. The candidate's 100-app dataset is a micro-version.

### Invent (no prior art to copy)

1. **Self-serve vs gated classifier.** No tool, directory, or paper does this. The candidate will need to scrape docs for phrases like "contact sales", "apply for access", "partner program", "enterprise only", "request access", and combine with auth-pattern signals (e.g., OAuth2 with no public client-id signup = likely gated). This is the project's biggest defensible novelty.
2. **"Buildability as agent toolkit" verdict.** No existing catalog publishes this. The candidate should define a rubric with axes like:
   - Spec availability & quality (OpenAPI present? valid? has examples?)
   - Auth friction (self-serve OAuth2 with PKCE > API key > partner-gated)
   - Tool granularity (coarse composable actions > 1:1 REST endpoints — the r/mcp thread is the prior-art warning here)
   - Idempotency & safety (GET vs POST; side-effect-free operations)
   - Rate-limit transparency (documented? generous enough for agent loops?)
   - Webhooks (for event-driven agent flows)
   - Pagination & error-schema consistency (agents choke on inconsistent shapes)
3. **Per-app scorecard as a versioned, diff-able artifact.** No one publishes this; it's a "living catalog" as InfoQ advocates but at per-app granularity. Source: https://www.infoq.com/articles/api-design-review
4. **Triangulated verdict** combining (a) auth pattern, (b) self-serve vs gated, (c) buildability — in a single per-app JSON record. None of the 10 camps produces this triple.
5. **Auth-pattern auto-detector from docs.** No off-the-shelf tool exists (§9). The candidate builds a small classifier (regex + decision tree over OpenAPI `securitySchemes` and docs-page keyword scrape). Low bar, real gap.
6. **Published methodology.** Merge's Blueprint QA is undocumented; every unified-API vendor keeps their integration-difficulty data internal. The candidate can uniquely publish *how* each verdict was reached.

### Net recommendation for the candidate's pipeline

```
For each of 100 apps:
  1. Pull OpenAPI spec from APIs.guru if present (steal).
  2. Pull auth_mode from Nango providers.yaml if present (steal).
  3. Query Glama + MCP.so + PulseMCP + Smithery + official MCP registry for existing MCP servers; dedupe by repo URL (steal).
  4. Lint the spec with Spectral + a custom "agent-friendliness" ruleset (steal Spectral, invent ruleset).
  5. Scrape the docs page for auth keywords and gating phrases (invent — no prior art).
  6. Run a behavioral smoke test: unauthenticated call to a public endpoint (steal RESTler's idea, simplify).
  7. Produce a per-app scorecard: {auth_pattern, self_serve_vs_gated, buildability_score, mcp_server_count, evidence_links} (invent the triple, steal the format from LlamaHub).
  8. Publish as a versioned, PR-able dataset (steal "anyone can contribute" from Merge/Nango, steal living-catalog framing from InfoQ).
```

The candidate's *wedge* is steps 5, 6, 7 — none of which any competitor or prior-art source does today.

---

## Appendix — all URLs cited

### Merge.dev
- https://www.merge.dev
- https://www.merge.dev/integrations/linear
- https://www.merge.dev/integrations/box
- https://technologychecker.io/technology/merge
- https://www.apifirst.tech/p/merge-blueprint-automating-integrations-with-ai
- https://www.prnewswire.com/news-releases/merge-launches-blueprint-an-ai-powered-tool-for-adding-integrations-to-merges-unified-apis-301842936.html
- https://venturebeat.com/business/merge-unveils-blueprint-an-ai-powered-tool-to-enable-easier-api-integrations
- https://www.youtube.com/watch?v=AhqyB-JTQkE
- https://medium.com/@deephearing_/streamline-api-integrations-with-merge-blueprint-empowering-developers-with-ai-powered-efficiency-729f2b6da76c
- https://www.youtube.com/watch?v=G2XY9k2vj-w
- https://www.merge.dev/blog/apideck-pricing
- https://nango.dev/blog/4-most-popular-merge-dev-alternatives

### Pipedream
- https://pipedream.com
- https://pipedream.com/docs/connect/mcp
- https://pipedream.com/docs/changelog
- https://docs.leena.ai/docs/pipedream-mcp
- https://www.linkedin.com/posts/pipedreamhq_want-to-use-the-power-of-claude-with-your-activity-7317562750556139523-Gw1M
- https://www.klavis.ai/blog/pipedream-mcp-alternatives-ai-agents
- https://github.com/PipedreamHQ/awesome-mcp-servers

### Stainless / Speakeasy (OpenAPI→MCP)
- https://www.stainless.com/mcp/convert-openapi-specs-to-mcp-servers
- https://www.stainless.com/blog/generate-mcp-servers-from-openapi-specs
- https://www.speakeasy.com/mcp/tool-design/generate-mcp-tools-from-openapi
- https://www.reddit.com/r/mcp/comments/1lr4itu/can_we_please_stop_pushing_openapi_spec_generated
- https://www.youtube.com/watch?v=1YygZ62qsA0

### Nango
- https://nango.dev
- https://github.com/nangohq/nango
- https://nango.dev/docs/integrations/api-configuration
- https://nango.dev/docs/guides/functions/functions-guide
- https://nango.dev/docs/updates/changelog
- https://nango.dev/blog/build-a-github-api-integration-for-ai-agents
- https://nango.dev/blog/merge-dev-vs-nango
- https://roopeshsn.com/bytes/how-nango-built-an-open-source-unified-api-platform
- https://apisyouwonthate.com/podcast/building-a-unified-api-on-the-shoulders-of-oss-with-robin
- https://www.withampersand.com/blog/bbest-nango-alternatives-2026
- https://hexdocs.pm/tango (Tango, Nango-compatible)
- https://github.com/usetrmnl/oauth2-providers (TRMNL, same pattern)

### Apideck
- https://www.apideck.com
- https://www.apideck.com/hris-api
- https://www.apideck.com/blog/unified-to-alternatives
- https://www.apideck.com/blog/top-benefits-of-unified-apis
- https://www.linkedin.com/products/apideck-unified-api
- https://unifiedapis.io
- https://uk-marketplace.sage.com/en-gb/apps/131030/apideck

### AI tool hubs
- https://www.langchain.com
- https://llamahub.ai
- https://portkey.ai/docs/virtual_key_old/integrations/libraries/llama-index-python
- https://docs.langchain.com/oss/python/integrations/providers/portkey
- https://www.vellum.ai/blog/llamaindex-vs-langchain-comparison
- https://truto.one/blog/best-integration-platforms-for-langchain-llamaindex-data-retrieval
- https://github.com/Portkey-AI/portkey-cookbook/blob/main/integrations/how-to-use-prompts-from-langchain-hub-and-requests-through-portkey.md

### Composio & direct competitors
- https://composio.dev
- https://composio.dev/toolkits
- https://github.com/composiohq/composio
- https://composio.dev/content
- https://www.arcade.dev/blog/composio-alternatives
- https://www.youtube.com/watch?v=aI5xMKxXU6c

### MCP registries
- https://mcp.so
- https://glama.ai/mcp/servers
- https://smithery.ai/blog/what-is-mcp
- https://studiomeyer.io/en/blog/mcp-marketplaces-2026
- https://explainx.ai/blog/top-10-mcp-server-directories-2026
- https://www.truefoundry.com/blog/best-mcp-registries
- https://safedep.io/the-state-of-mcp-registries
- https://tallyfy.com/how-to-list-mcp-server-registry-smithery-glama-pulsemcp
- https://apify.com/jungle_synthesizer/mcp-so-server-directory-scraper
- https://arxiv.org/html/2509.25292v3
- https://github.com/punkpeye/awesome-mcp-servers
- https://github.com/modelcontextprotocol/servers (official)
- https://www.youtube.com/watch?v=W19jh6nbFwY

### OpenAPI directories & validators
- https://apis.guru
- https://apis.guru/api-doc
- https://github.com/APIs-guru/openapi-directory
- https://learning.postman.com/docs/design-apis/specifications/import-a-specification
- https://blog.postman.com/new-in-the-postman-api-v1-39-api-catalog-and-spec-hub-endpoints
- https://www.postman.com/api-evangelist/apis-guru/request/j2j60dv/list-all-apis
- https://community.make.com/t/check-out-these-useful-api-discovery-resources/2812
- https://nordicapis.com/13-api-directories-to-help-you-discover-apis
- https://stoplight.io/open-source/spectral
- https://medium.com/@mohamed.slimani/openapi-validation-by-spectral-lint-589278b4bde7
- https://www.youtube.com/watch?v=Il5btHG_D74

### Academic prior art
- https://www.microsoft.com/en-us/research/publication/restler-stateful-rest-api-fuzzing
- https://www.microsoft.com/en-us/research/publication/rest-ler-automatic-intelligent-rest-api-fuzzing
- https://patricegodefroid.github.io/public_psfiles/icse2019.pdf
- https://github.com/microsoft/restler-fuzzer
- https://www.microsoft.com/en-us/research/publication/checking-security-properties-of-cloud-services-rest-apis
- https://www.microsoft.com/en-us/research/video/fuzzing-to-improve-the-security-and-reliability-of-cloud-services-with-restler
- https://www.microsoft.com/en-us/research/video/stateful-rest-api-fuzzing-with-restler
- https://www.mdpi.com/2673-4591/120/1/42
- https://www.sciopen.com/article/10.26599/TST.2024.9010026
- https://fileadmin.cs.lth.se/ai/Proceedings/AAAI%20SSS%202012/01/SS12-04-014.pdf
- https://people.cs.uchicago.edu/~shanlu/paper/icse22.pdf
- https://link.springer.com/article/10.1007/s10462-024-10726-1

### OSS auth tools
- https://github.com/octokit/auth-basic.js
- https://dev.to/rahulbanerjee99/how-to-authenticate-using-keys-basicauth-oauth-in-python-4b8m
- https://github.com/VishwamKumar/exp.rest-apis.auth-styles
- https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api
- https://stackoverflow.com/questions/14517744/how-to-use-basic-authentication-to-create-oauth2-token-for-github-api
- https://www.youtube.com/watch?v=_nosBHMJGGg
- https://notes.kodekloud.com/docs/AZ-400-Designing-and-Implementing-Microsoft-DevOps-Solutions/Design-and-Implement-Authentication-and-Authorization-Methods/Implement-and-manage-GitHub-Authentication/page
- https://www.youtube.com/watch?v=CdtX9TU4R_Q

### Industry audits & landscape posts
- https://stripe.com/blog/api-versioning
- https://developers.klaviyo.com/en/docs/api_versioning_and_deprecation_policy
- https://developers.klaviyo.com/en/v1-2/reference/api-overview
- https://developers.klaviyo.com/en/v2023-02-22/docs/migrating_from_v1v2_to_the_new_klaviyo_apis
- https://developers.klaviyo.com/en/docs/changelog_
- https://developers.klaviyo.com
- https://community.klaviyo.com/developer-group-64/klaviyo-v1-v2-api-retirement-11262
- https://konghq.com/blog/engineering/api-a-rapidly-changing-landscape
- https://api7.ai/blog/api-management-trends-you-cannot-ignore
- https://unizo.ai/blog/api-integration-guide-2025
- https://coderslab.io/blog/future-apis-trends-best-practices
- https://www.youtube.com/watch?v=u_5JppAExDs
- https://www.infoq.com/articles/api-design-review
