# Case Study Design Brief — 2-Minute-Skimmable HTML Page

> **Audience:** the candidate (Composio take-home) and the frontend implementer they hand this to.
> **Goal:** a single self-explanatory HTML page a reviewer understands in ~2 minutes with no narration, showing **findings → patterns → agent → proof → verification**, with clarity and presentation as the point.
> **Status:** research + design brief. Source: verified web search results + established design references (URLs cited inline and in the appendix).

---

## TL;DR (the brief in 90 seconds)

1. **Lead with the verdict.** The first viewport must contain a one-sentence headline finding, three hero metrics (numerator/denominator), and a runnable "proof" button. Everything else is evidence.
2. **One chart per scroll.** A 100% stacked bar (self-serve vs gated) up top → a treemap (category × auth) → a Sankey (auth → buildability). Each tells the story in ~2 seconds.
3. **The 100-row matrix is sortable/filterable/searchable, with a color-coded verdict column** (● build / ● partial / ● gated). Sticky header + sticky first column. Plain JS or Alpine.js is enough; no virtualization needed at 100 rows.
4. **Data is inlined as JSON** in a `<script type="application/json">` block. No fetch, no CORS, one file, works offline — survives any host.
5. **Stack:** hand-written HTML/CSS + Alpine.js (CDN) + ECharts (CDN) + inlined JSON. No build step. Deploy on Vercel (one command) because you'll want a serverless function for the live "Run the agent" button.
6. **Honesty is a section, not a footnote.** A small "hits and misses" table with red/amber rows + an accuracy %.
7. **Mobile bar:** readable at 375px; charts stack; table scrolls horizontally or cardifies; WCAG AA contrast; keyboard-navigable filters.

---

## Part A — Research Findings

### 1. Reference designs — what to steal, what to skip

| Reference | URL | What works | What doesn't | Steal this |
|---|---|---|---|---|
| **Stripe Press** | https://press.stripe.com | Typographic restraint; ~680px reading measure; single column; considered color palette; one idea per page | Commerce/book-buying chrome; slow reveals | The reading **measure** (≈680px) and typographic calm — long-form should not fight the eye |
| **Stripe blog (long-form)** | https://stripe.com/blog | Engineering credibility; inline diagrams; clear section headers; footnoted detail | Some pieces run long without a TL;DR | Section headers as a skimmable spine; inline evidence over screenshots of dashboards |
| **Linear changelog / `now`** | https://linear.app/now | Extreme density that stays legible; semantic color chips for status; dated entries; tiny type done well | Density assumes an already-bought-in reader; can feel impenetrable cold | **Color-chip status semantics** and dated, scannable entries (worknotes.ai calls it "the gold standard for dev-tool design") — https://www.worknotes.ai/blog/best-changelog-page-designs |
| **Linear `method`** | https://linear.app/method | Beliefs-as-prose; numbered principles; opinionated voice | Manifesto framing can read as marketing | Opinionated, numbered principles as a way to state "how the agent works" crisply |
| **Vercel customer stories** | https://vercel.com/customers | Big headline metric + logo + one-sentence outcome; SaaSFrame notes the "minimalist aesthetic, generous whitespace, muted palette" — https://www.saasframe.io/examples/vercel-customer-stories | Marketing-length narrative; metric often unsourced | **One hero stat + one sentence** opener; logo strip for credibility |
| **PostHog blog (deep dives)** | https://posthog.com/blog | Opinionated "we tried X, here's what happened" voice; inline screenshots; technical honesty | 3000–4000 word length | Voice + inline evidence + willingness to show the dead-ends |
| **Anthropic research notes** | https://www.anthropic.com/research | Abstract-first; key claims as bullets; clean figures with captions; collapsible methodology | Academic dryness; dense | **Abstract/TL;DR block** at top, figure captions, collapsible "methodology" detail — https://www.anthropic.com/research/alignment-faking |
| **Bloomberg "What is Code?"** | https://www.bloomberg.com/graphics/2015-paul-ford-what-is-code/ | Playful, opinionated, structure-as-journey, interactive | Enormous scope (not replicable in a take-home) | Voice and the idea that structure *is* the story |
| **Distill.pub** | https://distill.pub | Interactive figures that change as you read; hover-for-detail; mathematical clarity | ML-paper framing; now on indefinite hiatus — https://distill.pub/about | **Interactive figures tied to prose**; hover affordances — see "Communicating with Interactive Articles," https://distill.pub/2020/communicating-with-interactive-articles and the style guide https://distill.pub/guide |
| **The Pudding** | https://pudding.cool | Chart-first visual essays; scroll choreography; charts *are* the text | Heavy bespoke D3 (time-costly) | Chart-as-primary-text; scroll-driven reveals |
| **Observable notebooks** | https://observablehq.com | Data interleaved with prose; live values; reactive | Looks like a tool, not a deliverable; notebook chrome | **Data-next-to-claim** layout; consider Observable Plot (https://observablehq.com/plot) for quick charts if not using ECharts |
| **rauno.me** | https://rauno.me | Information density where every pixel earns its place; keyboard-first | Requires high reader tolerance; risky for a cold 2-min reviewer | Density discipline and information scent — but use sparingly |

**Synthesis for this project:** take Stripe Press's *measure and calm*, Linear's *color-chip status semantics*, Vercel's *hero-stat opener*, Anthropic's *abstract block + collapsible method*, Distill's *interactive-figure-tied-to-prose*, and PostHog's *opinionated-but-honest voice*. Avoid The-Pudding-level bespoke D3 (too costly) and rauno-level density (too risky for a cold reviewer).

### 2. Two-minute skimmability

- **F-shaped reading (Nielsen Norman Group).** Eyetracking shows users scan: many fixations at top-left, two horizontal sweeps, then a vertical move down the left edge. "79% of users scan new pages, only 16% read word-by-word." → put the headline finding **top-left**; bold the first 2–3 words of each paragraph; left-align; use subheads and bullets as scanning anchors. Source: https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/ (original study: https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/).
- **Inverted pyramid (NN/g).** "The most important information — or what might even be considered the conclusion — is presented first." → open with the **verdict**, then supporting evidence, then background/method. Source: https://www.nngroup.com/articles/inverted-pyramid/. (Also: https://www.stylemanual.gov.au/structuring-content/types-structure/inverted-pyramid-structure, https://data.europa.eu/apps/data-visualisation-guide/the-inverted-pyramid.)
- **What MUST be in the first viewport:** (1) one-sentence headline finding (the verdict), (2) three hero metrics as numerator/denominator chips, (3) one chart that embodies the headline pattern, (4) the live "Run"/proof button, (5) sticky section nav. If a reviewer only sees the fold, they should already know the answer.
- **Make the headline finding unmissable:** ≥24px, top-left, contrast ≥7:1, a single complete sentence with a number in it ("We mapped 100 dev tools; 47% are self-serve buildable without a human in the loop."). Pair it with the single most decisive metric as a large numeral.

### 3. Table/matrix design (the 100-row problem)

100 rows is a lot to scroll but trivial for the browser. The design question is **lookup vs pattern** — they need different treatments, so use both.

- **Pattern layer (above the table):** charts (see §4). The story belongs here.
- **Lookup layer (the table):** the evidence. Make it sortable, filterable, searchable.
- **NN/g on comparison tables:** columns = entities, rows = attributes (or vice-versa); use checkmarks/dashes; align consistently; group rows when there are many. Source: https://www.nngroup.com/articles/comparison-tables/. (Also: https://uxpatterns.dev/patterns/data-display/comparison-table.)
- **Color-code the verdict column** as a categorical heatmap: `● build` (green), `● partial` (amber), `● gated` (red). This is the single highest-value column — make it a colored chip, not plain text.
- **Sticky header + sticky first column** so app names and column headers stay visible while scrolling. Horizontal scroll for the rest.
- **When table vs cards vs Sankey:**
  - **Table** → when the reader wants to *find app X* (lookup). Required for the 100-row evidence.
  - **Cards** → when the reader wants to *browse featured examples* (3–6 deep dives). Optional sidebar/section.
  - **Sankey/heatmap/treemap** → when the reader wants the *pattern* (the story). Goes above the table.
- **Library choice (filter/sort/search for 100 rows):**
  - **Alpine.js + ~30 lines of JS** — recommended. ~15KB, no jQuery, no build, declarative `x-for`/`x-show`. Examples: https://alpinejs.dev/plugins/sort, https://www.raymondcamden.com/2022/05/02/building-table-sorting-and-pagination-in-alpinejs.
  - **List.js** (https://listjs.com) — lightweight, drop-in search/sort, no dependencies. Good fallback.
  - **DataTables** (https://datatables.net) — most features, but heavier and jQuery-flavored; overkill for 100 rows; client-side filtering covered at https://datatables.net/forums/discussion/9698/fast-client-side-filtering.
  - **Vanilla `Array.filter`** — honestly fine for 100 rows if you'd rather have zero deps.
  - **Recommendation:** Alpine.js for the whole page's interactivity (nav, tabs, filters, collapsibles) so you have one consistent pattern, or plain JS if you want zero CDNs.
- **Data shape:** inline as JSON. See §5.

### 4. Charts that tell a story in 2 seconds

Pick chart types by what the reviewer must grasp instantly. **Lead with one chart only** at the top; the others appear on scroll.

| Chart | Question it answers | When to use | Source |
|---|---|---|---|
| **100% stacked bar** (self-serve vs gated, one bar per category) | "How much of each category is buildable?" | **Headline chart.** Most legible at a glance; no legend friction if direct-labeled. | — |
| **Treemap** (category × auth method, area = count) | "Where do the 100 apps sit?" | Second chart — shows distribution and proportion simultaneously. NN/g: treemaps "capture two types of information" (hierarchy + size). https://www.nngroup.com/articles/treemaps/, https://www.tableau.com/chart/what-is-treemap | |
| **Sankey** (auth method → buildability verdict) | "What's the pipeline from auth to buildable?" | Third chart — most expressive, shows flow volume. Risk: clutter; direct-label nodes, limit to ≤6 source + ≤4 target nodes. https://www.highcharts.com/chartchooser/sankey-categorical-flow, https://www.storytellingwithdata.com/blog/what-is-a-sankey-diagram | |

**Rules for instant comprehension:**
- Direct-label series on the chart; avoid a legend the reader must decode.
- Put the percentage on the bar, not in a tooltip.
- One variable per chart for the headline; the Sankey can carry two because flow is its whole point.
- Every chart gets a one-line caption underneath stating the takeaway ("47% self-serve; auth method is the strongest predictor").
- Provide a **data table beneath each chart** as the accessible fallback (screen readers + skimmers who want exact numbers).

### 5. Tech stack for a single self-contained HTML page

| Layer | Options | Recommendation | Rationale |
|---|---|---|---|
| **Markup/CSS** | Hand-written HTML/CSS · Tailwind Play CDN · Tailwind compiled | **Hand-written HTML/CSS** (minimal) | Zero build, zero CDN, maximum portability — the page works even offline. Tailwind Play CDN is fast but adds a runtime dep; acceptable if you prefer utility classes. |
| **Interactivity** | Vanilla JS · Alpine.js · htmx | **Alpine.js via CDN** (~15KB) | Declarative `x-data`/`x-for`/`x-show` covers filters, search, tabs, collapsibles without a build step or JSX. |
| **Charts** | ECharts · Chart.js · D3 · Observable Plot | **ECharts via CDN** | Treemap, 100% stacked bar, and Sankey are all first-class in one library. Chart.js lacks native Sankey/treemap (needs plugins); D3 is too much code for a time-boxed one-pager; Observable Plot is great but less familiar. https://echarts.apache.org/ |
| **Data** | Inline JSON · fetched CSV · fetched JSON | **Inline JSON** in `<script type="application/json" id="data">` | Single file, no CORS, no fetch failure mode, works offline, survives any host. CSV is fine but requires parsing and a second request — unnecessary for 100 rows. |
| **SSG** | Astro · Eleventy · 11ty | **Skip** | Overkill for one page; adds a build step and a directory to maintain. Plain HTML wins on portability. |

**Why inline JSON wins:** a reviewer might be on a slow connection, behind a corp proxy, or opening the file directly from `file://`. Inlined data has no failure mode. Parse once on `DOMContentLoaded`, render charts + table from the same array.

### 6. "Proof" section design

Most-credible → least-credible for a 2-minute review:

1. **Live "Research one app" button** (primary) — a button that hits a deployed serverless endpoint (Vercel Function / Cloudflare Worker), runs the agent on one app, and streams back real JSON + a rendered result in ~15s. This is the gold standard: the reviewer sees the agent actually work, live. **Always pair with a recorded fallback** in case the endpoint is asleep, rate-limited, or the reviewer is impatient.
2. **15-second looping GIF/short Loom** (secondary) — a recorded run, captioned with what's happening. Survives endpoint downtime. Embed inline, autoplay muted, loop.
3. **GitHub repo + one-line `curl -sL … | bash`** (tertiary) — for the reviewer who wants to run it locally. Credible with devs; lower-friction than a sandbox.
4. **Embedded CodeSandbox/StackBlitz** — credible but adds load time and IDE chrome; only if the run needs a full environment.

**Recommendation:** primary = live button + GIF fallback side by side; tertiary = repo link with the curl one-liner. Put the **live button above the fold** (proof visible immediately) and the full proof section mid-page.

### 7. Honesty patterns — showing where the agent was wrong, credibly

- **Make it a named section, not a footnote.** "Verification" or "Hits & misses" as its own headed section. Reviewers actively hunt for this; hiding it reads as spin.
- **Small table:** `Input | Agent said | Actual | Why it missed`. Color rows: red = wrong, amber = partial, green = correct (show a few greens too so it's not all red).
- **State the accuracy number honestly** as a fraction: "71/100 correct on a 25-item audited gold set." Don't round up to "97% accurate."
- **Anthropic-style:** state each failure mode plainly, then one line on what would fix it ("docs were stale → re-fetch on a 7-day cadence").
- **Why this increases credibility:** visible, specific limitations read as competence. Vague "some limitations apply" reads as evasion.

### 8. Deployment options

| Host | One-command deploy | Free tier | Best for |
|---|---|---|---|
| **Vercel** | `vercel --prod` | Yes | **Recommended default** — you likely need a serverless function for the live "Run" button; `vercel` handles static + function in one deploy. https://vercel.com/ |
| **Cloudflare Pages** | `npx wrangler pages deploy .` | Yes | Pure static, fastest edge, great if no serverless needed. https://pages.cloudflare.com/ |
| **GitHub Pages** | push to `gh-pages` branch | Yes | Zero-config if repo is already on GitHub; pure static only. https://pages.github.com/ |
| **Netlify** | `netlify deploy --prod` | Yes | Static + serverless functions (similar to Vercel). https://www.netlify.com/ |

**Pick:** **Vercel** if the proof section has a live endpoint (one command deploys page + function). **Cloudflare Pages** if pure static (fastest, simplest). Either is one command after initial `link`.

### 9. Accessibility & mobile (minimum bar)

Reviewers may open this on a phone during a commute. Minimum viable:

- **Responsive, mobile-first.** Test at **375px** (iPhone SE) and 768px. Base font ≥16px.
- **The 100-row table on mobile:** either (a) horizontally scrollable with sticky first column, or (b) collapses to cards (one card per app). Pick one; sticky-column scroll is simpler.
- **Charts stack vertically** on mobile; don't side-by-side.
- **WCAG AA contrast (4.5:1 body, 3:1 large text & UI).** Test the green/amber/red chips — color alone must not convey meaning, so pair each chip with a text label (`● gated`).
- **Keyboard-navigable:** filters, search, and table sortable headers reachable + operable via Tab/Enter; focus visible.
- **Charts have text alternatives:** a data table beneath each chart (doubles as the accessible fallback).
- **`prefers-reduced-motion`** respected — disable chart entrance animations and GIF autoplay where possible.
- **Semantic HTML:** `<section>` with `aria-labelledby`, real `<table>` with `<thead>`, heading hierarchy h1→h2→h3 without skips, `alt` on every screenshot.
- Reference: WCAG 2.2 — https://www.w3.org/WAI/standards-guidelines/wcag/.

---

## Part B — Design Brief (hand to the implementer)

**One-page HTML case study.** Single `index.html` + inlined JSON + two CDN scripts (Alpine.js, ECharts). No build step. Deploys via `vercel --prod`.

### Information architecture (top → bottom)

1. **Sticky nav** — wordmark + 5 anchor links: *Patterns · Matrix · Agent · Proof · Verify*.
2. **Hero (above the fold)** — one-sentence headline finding (the verdict) + three hero metric chips (numerator/denominator) + the live "Run the agent" button + repo link.
3. **Patterns** — three one-liner insights + three charts (100% stacked bar → treemap → Sankey), each with a caption and a data-table fallback.
4. **The Matrix** — filterable/sortable/searchable 100-row table; color-coded verdict column; sticky header + sticky first column; "download CSV / view raw JSON" links.
5. **The Agent** — one architecture diagram + 4-step "what it does" + "where a human was needed" (inline list of hand-offs).
6. **Proof** — live "Research one app" button (streams real JSON) + 15s looping GIF fallback + `curl | bash` one-liner + repo link.
7. **Verification** — accuracy % as fraction + hits-and-misses table (red/amber/green rows) + 2–3 named limitations with fixes.
8. **Footer** — method, data sources, reproduce links, "built with."

### Visual language

- **Measure:** content column ~720px for prose; full-bleed for charts/table up to ~1100px.
- **Type:** one sans (system or Inter) for UI, optional serif for the hero headline only. Base 16px / 1.6 line-height.
- **Color:** neutral surface (near-white / near-black); **three semantic chips only** — green `build`, amber `partial`, red `gated`. Reuse these everywhere a verdict appears (chart, table, miss-table) so the legend is learned once.
- **Density:** Linear-inspired chips, Stripe-Press-inspired calm. Avoid rauno-level density.
- **Motion:** subtle only; respect `prefers-reduced-motion`.

### Interaction contract

- Filters (category, auth, verdict) + free-text search all reduce the same 100-row array; result count shown ("showing 47 of 100").
- Sorting by any column header; default sort = verdict then app name.
- "Run the agent" button → loading state → real JSON rendered inline; on failure, show the GIF + an honest "endpoint asleep — here's a recorded run."
- All charts re-render from the *filtered* dataset when a filter is active (so the pattern reflects what's shown in the table) — or keep charts fixed to the full 100 and clearly label "all 100." Pick one and label it.

---

## Part C — Wireframe (ASCII)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ● Composio Take-Home      Patterns · Matrix · Agent · Proof · Verify    │  sticky nav
├──────────────────────────────────────────────────────────────────────────┤
│  CASE STUDY · AGENT-MAPPED DEV-TOOL BUILDABILITY                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  We mapped 100 dev tools. 47% are self-serve buildable             │  │  H1 — the verdict (top-left, ≥24px)
│  │  without a human in the loop.                                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  [ 47 / 100 self-serve ]  [ 12 auth methods ]  [ 71 / 100 accurate ]     │  3 hero metric chips
│                                                                          │
│  ▶ [Run the agent on one app — live]      [ repo · curl -sL … | bash ]    │  proof CTA above the fold
├──────────────────────────────────────────────────────────────────────────┤
│  PATTERNS  — what the 100 apps tell us                                   │
│   • auth method is the strongest predictor of buildability               │  one-line insights
│   • API-key apps build 4× more often than OAuth-gated ones               │
│   • CI/CD category is 80% self-serve; analytics is 20%                   │
│                                                                          │
│   ┌──────────────────────────┐   ┌──────────────────────────┐           │
│   │ [100% stacked bar]       │   │ [treemap: category×auth] │           │  chart 1 (headline split)
│   │ self-serve vs gated      │   │ area = count             │           │  chart 2 (where they sit)
│   │ by category              │   │                          │           │
│   └──────────────────────────┘   └──────────────────────────┘           │
│   caption: "47% self-serve…"          caption: "CI/CD dominates…"        │
│                                                                          │
│   ┌──────────────────────────────────────────────────────┐              │
│   │ [Sankey: auth method ──▶ buildability verdict]       │              │  chart 3 (the pipeline)
│   └──────────────────────────────────────────────────────┘              │
│   caption: "API key flows mostly to ● build; OAuth splits to ● partial"  │
├──────────────────────────────────────────────────────────────────────────┤
│  THE MATRIX — all 100 apps                              showing 100/100  │
│  [🔍 search…]  [category ▾]  [auth ▾]  [verdict ▾]   [CSV] [JSON]        │  filter bar
│  ┌────────────┬───────────┬───────────┬──────────┬─────────────────────┐│
│  │ App      ▲ │ Category  │ Auth      │ Verdict  │ Build path          ││  sticky header
│  ├────────────┼───────────┼───────────┼──────────┼─────────────────────┤│
│  │ Acme CI   │ CI/CD      │ API key   │ ● build  │ curl -sL acme/run   ││  ● color-coded verdict
│  │ Beta Log  │ Observ.    │ OAuth     │ ● partial│ POST /v1/ingest …   ││  (green/amber/red)
│  │ Gamma DB  │ Database   │ SSO       │ ● gated  │ requires human      ││
│  │ … (97)    │            │           │          │                     ││
│  └────────────┴───────────┴───────────┴──────────┴─────────────────────┘│
├──────────────────────────────────────────────────────────────────────────┤
│  THE AGENT                                                               │
│  ┌─────────────────────┐   What it does (4 steps):                       │
│  │ [architecture        │   1 plan  2 fetch docs  3 classify auth        │
│  │  diagram]            │   4 test build path → score buildability       │
│  └─────────────────────┘   Where a human was needed (3 hand-offs):       │
│                            • app #14 — broke a CAPTCHA login             │
│                            • app #61 — needed a paid-tier sandbox        │
│                            • app #88 — ratified an ambiguous verdict     │
├──────────────────────────────────────────────────────────────────────────┤
│  PROOF                                                                   │
│  ▶ [Research one app — live]   streams real JSON in ~15s                 │
│  [15s looping GIF of a run]    [repo · curl -sL … | bash]                │
├──────────────────────────────────────────────────────────────────────────┤
│  VERIFICATION — honesty section                                          │
│  Accuracy: 71 / 100 correct (audited on 25-item gold set).               │
│  ┌────────────┬──────────────┬──────────────┬───────────────────────┐   │
│  │ Input      │ Agent said   │ Actual       │ Why it missed         │   │
│  ├────────────┼──────────────┼──────────────┼───────────────────────┤   │
│  │ App X      │ ● build      │ ● gated      │ docs stale (fix: 7d)  │ █ │ red row
│  │ App Y      │ API key      │ OAuth        │ login wall            │ █ │ amber row
│  │ App Z      │ ● partial    │ ● partial    │ —                     │ █ │ green row
│  └────────────┴──────────────┴──────────────┴───────────────────────┘   │
│  Limitations: public docs only; no authed scraping; rate-limited fetch.  │
├──────────────────────────────────────────────────────────────────────────┤
│  METHOD · DATA · REPRODUCE   [CSV][JSON][repo]   built with Alpine+ECharts│  footer
└──────────────────────────────────────────────────────────────────────────┘
```

**Mobile (375px) deltas:** nav collapses to a `≡` menu; hero metrics stack 1×3; charts stack vertically full-width; table becomes horizontally scrollable with sticky first column (or cardifies); Sankey hidden behind a "see flow" toggle if it breaks at narrow widths.

---

## Part D — Recommended Tech Stack (one-line rationale each)

| Choice | One-line rationale |
|---|---|
| **Hand-written HTML/CSS** | Zero build step, zero CDN for the shell → page works from `file://` and on any host. |
| **Alpine.js via CDN** (~15KB) | Declarative `x-data`/`x-for`/`x-show` covers filters, search, tabs, collapsibles with no JSX or build. https://alpinejs.dev/ |
| **ECharts via CDN** | Treemap + 100% stacked bar + Sankey all first-class in one library; less code than D3, more capable than Chart.js for these chart types. https://echarts.apache.org/ |
| **Inlined JSON** in `<script type="application/json" id="data">` | Single-file, no fetch/CORS/offline failure mode; one source array feeds both charts and table. |
| **Vercel** for deploy | `vercel --prod` ships the static page *and* the serverless function for the live "Run" button in one command. https://vercel.com/ |
| **(Fallback) Cloudflare Pages** | If you drop the live endpoint, `npx wrangler pages deploy .` is the fastest pure-static deploy. https://pages.cloudflare.com/ |

**What to deliberately skip:** Astro/Eleventy (overkill for one page), Tailwind Play CDN (fine but adds a runtime dep you don't need), D3 (too much code for time-boxed), DataTables (jQuery-ish and heavier than Alpine+30 lines for 100 rows).

---

## Part E — 2-Minute Review Checklist (must-haves)

A reviewer should be able to pass/fail the page against this in ~2 minutes.

- [ ] **Headline finding is one sentence, top-left, ≥24px** — visible without scrolling.
- [ ] **Three hero metrics as numerator/denominator** above the fold (47/100, 12 auth methods, 71/100 accurate).
- [ ] **A runnable "proof" trigger is visible above the fold** (live button or curl one-liner).
- [ ] **Sticky section nav** with 5 anchors that jump correctly.
- [ ] **One chart communicates the headline pattern in <2s** — direct-labeled, no legend deciphering, captioned takeaway.
- [ ] **100-row table is sortable + filterable + searchable**, sticky header, color-coded verdict column, result count shown.
- [ ] **"The Agent" section names what was built AND where a human intervened** (≥1 specific hand-off).
- [ ] **Verification section shows ≥3 honest misses** in a table with reasons, color-coded red/amber; accuracy stated as a fraction.
- [ ] **Page is one self-contained `index.html`** (works offline except the live endpoint).
- [ ] **Public URL loads in <3s**; one-command deploy.
- [ ] **Mobile-readable at 375px** — charts stack, table scrolls/cardifies, nav collapses.
- [ ] **No placeholder content** — no lorem ipsum, no fake charts, no broken links.
- [ ] **Skim-only test passes:** reading only the headings + first chart + table verdict column still conveys the full story.

---

## Part F — 5 Reference Links to Open & Study Before Designing

1. **NN/g — F-Shaped Pattern of Reading on the Web** — https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
   *Why:* the empirical basis for "put the verdict top-left, bold lead words, left-align." Dictates the hero layout.
2. **NN/g — Inverted Pyramid: Writing for Comprehension** — https://www.nngroup.com/articles/inverted-pyramid/
   *Why:* justifies verdict-first ordering. The whole page is an inverted pyramid.
3. **Distill.pub — Communicating with Interactive Articles** — https://distill.pub/2020/communicating-with-interactive-articles/
   *Why:* the canonical treatment of tying interactive figures to prose; steal the pattern for chart+caption pairs.
4. **Vercel — Customers** — https://vercel.com/customers
   *Why:* the "one hero stat + one sentence + logo" opener pattern, directly transferable to the hero.
5. **Linear — Now (changelog)** — https://linear.app/now
   *Why:* how to do dense, color-chipped, scannable status semantics without losing legibility — the model for the matrix's verdict chips.

**Bonus (open if time allows):**
- Anthropic research note layout (abstract block + collapsible method) — https://www.anthropic.com/research/alignment-faking
- NN/g comparison-tables guidance — https://www.nngroup.com/articles/comparison-tables/
- NN/g treemaps guidance — https://www.nngroup.com/articles/treemaps/
- ECharts treemap + Sankey demos — https://echarts.apache.org/examples/en/index.html
- Bloomberg "What is Code?" (voice + structure-as-story) — https://www.bloomberg.com/graphics/2015-paul-ford-what-is-code/

---

## Appendix — Full URL list

**Reference designs**
- Stripe Press — https://press.stripe.com
- Stripe blog — https://stripe.com/blog
- Linear /now (changelog) — https://linear.app/now
- Linear /method — https://linear.app/method
- Best changelog page designs (worknotes.ai) — https://www.worknotes.ai/blog/best-changelog-page-designs
- Vercel customers — https://vercel.com/customers
- Vercel customer-stories UI analysis (SaaSFrame) — https://www.saasframe.io/examples/vercel-customer-stories
- PostHog blog — https://posthog.com/blog
- Anthropic research — https://www.anthropic.com/research
- Anthropic — Alignment faking — https://www.anthropic.com/research/alignment-faking
- Bloomberg — What is Code? — https://www.bloomberg.com/graphics/2015-paul-ford-what-is-code/
- Distill.pub — https://distill.pub
- Distill.pub — About (hiatus note) — https://distill.pub/about
- Distill.pub — Style guide — https://distill.pub/guide
- Distill.pub — Communicating with Interactive Articles — https://distill.pub/2020/communicating-with-interactive-articles
- The Pudding — https://pudding.cool
- Observable — https://observablehq.com
- Observable Plot — https://observablehq.com/plot
- rauno.me — https://rauno.me

**Skimmability research**
- NN/g — F-shaped pattern (current) — https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- NN/g — F-shaped pattern (original study) — https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/
- NN/g — Inverted pyramid — https://www.nngroup.com/articles/inverted-pyramid/
- Style Manual (AU) — Inverted pyramid structure — https://www.stylemanual.gov.au/structuring-content/types-structure/inverted-pyramid-structure
- data.europa.eu — The inverted pyramid — https://data.europa.eu/apps/data-visualisation-guide/the-inverted-pyramid

**Tables & matrices**
- NN/g — Comparison tables — https://www.nngroup.com/articles/comparison-tables/
- UX Patterns — Comparison table — https://uxpatterns.dev/patterns/data-display/comparison-table
- Alpine.js Sort plugin — https://alpinejs.dev/plugins/sort
- Alpine.js table sorting/pagination tutorial — https://www.raymondcamden.com/2022/05/02/building-table-sorting-and-pagination-in-alpinejs
- DataTables — https://datatables.net
- DataTables client-side filtering — https://datatables.net/forums/discussion/9698/fast-client-side-filtering
- List.js — https://listjs.com

**Charts**
- ECharts — https://echarts.apache.org/
- ECharts examples — https://echarts.apache.org/examples/en/index.html
- Chart.js — https://www.chartjs.org/
- D3 — https://d3js.org/
- Observable Plot — https://observablehq.com/plot
- NN/g — Treemaps — https://www.nngroup.com/articles/treemaps/
- Tableau — What is a treemap — https://www.tableau.com/chart/what-is-treemap
- Highcharts — Sankey categorical flow — https://www.highcharts.com/chartchooser/sankey-categorical-flow
- Storytelling with data — What is a Sankey diagram — https://www.storytellingwithdata.com/blog/what-is-a-sankey-diagram

**Deployment**
- Vercel — https://vercel.com/
- Cloudflare Pages — https://pages.cloudflare.com/
- GitHub Pages — https://pages.github.com/
- Netlify — https://www.netlify.com/

**Accessibility & mobile**
- WCAG 2.2 — https://www.w3.org/WAI/standards-guidelines/wcag/
