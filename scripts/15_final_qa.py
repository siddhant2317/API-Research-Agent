"""Final QA checklist for the case study."""
import json, re, os
from pathlib import Path

html = Path("/home/z/my-project/download/index.html").read_text()
data = json.loads(Path("/home/z/my-project/data/all_apps.json").read_text())
patterns = json.loads(Path("/home/z/my-project/data/patterns.json").read_text())
verif = json.loads(Path("/home/z/my-project/data/verification/_final_summary.json").read_text())

print("=" * 70)
print("FINAL QA CHECKLIST")
print("=" * 70)

checks = []

# 1. Headline finding is one sentence, top-left, ≥24px
checks.append(("Headline finding present", "67% are buildable" in html))
checks.append(("Run agent button above fold", 'id="runAgentBtn"' in html))

# 2. Sticky nav with 5 anchors
nav_anchors = all(f'#{a}' in html for a in ["patterns", "matrix", "agent", "proof", "verify"])
checks.append(("Sticky nav with 5 anchors", nav_anchors))

# Hero metrics — count "metric" class (not "metrics" container)
import re
metric_cards = len(re.findall(r'class="metric(?:\s+accent)?"', html))
checks.append(("Hero metrics (4 cards)", metric_cards >= 4))

# 3. Charts (3 ECharts)
checks.append(("3 chart containers", all(f'id="chart-{c}"' in html for c in ["cat", "auth", "ss"])))
checks.append(("ECharts CDN loaded", "echarts" in html))

# 4. 100-row table
checks.append(("100 app records in data", len(data) == 100))
checks.append(("Table has search input", 'id="searchInput"' in html))
checks.append(("Table has category filter", 'id="filterCat"' in html))
checks.append(("Table has auth filter", 'id="filterAuth"' in html))
checks.append(("Table has verdict filter", 'id="filterVerdict"' in html))

# 5. Agent section
checks.append(("Agent section: 4 stages", "What it does (4 stages)" in html))
checks.append(("Agent section: human handoffs", "Where a human was needed" in html))

# 6. Proof section
checks.append(("Live run button", 'id="liveRunBtn"' in html))
checks.append(("Serverless function file exists", Path("/home/z/my-project/download/api/run-agent.js").exists()))

# 7. Verification section
checks.append(("Verification staircase (4 steps)", html.count('class="stair-step') >= 4))
checks.append(("Verification table", 'id="verifyTbody"' in html))
checks.append(("Methodology section", "Methodology" in html or "methodology" in html))

# 8. Footer
checks.append(("Footer with author", "Bhavishya Jain" in html))
checks.append(("Footer with email", "bhavishyajain011@gmail.com" in html))

# 9. Mobile responsive
checks.append(("Mobile viewport meta", 'width=device-width' in html))
checks.append(("Mobile media query (768px)", "@media (max-width:768px)" in html))
checks.append(("Mobile media query (420px)", "@media (max-width:420px)" in html))

# 10. Accessibility
checks.append(("prefers-reduced-motion", "prefers-reduced-motion" in html))
checks.append(("Lang attribute", '<html lang="en">' in html))

# 11. Data integrity
checks.append(("Patterns: 67 buildable", patterns["totals"]["buildable"] == 67))
checks.append(("Patterns: 51 composio", patterns["totals"]["composio_supported"] == 51))
checks.append(("Patterns: 84 self_serve", patterns["totals"]["self_serve"] == 84))
checks.append(("Verification: 49 verified", verif["verified_with_ground_truth"] == 49))
checks.append(("Verification: 42 exact", verif["correct_exact"] == 42))
checks.append(("Verification: 7 superset", verif["correct_superset"] == 7))
checks.append(("Verification: 0 incorrect", verif["incorrect"] == 0))

# 12. Self-contained
checks.append(("Inlined JSON data", 'id="appData"' in html))
checks.append(("No external fetch for data", "fetch('/data" not in html and "fetch('apps.json" not in html))

# 13. Vercel config
checks.append(("vercel.json exists", Path("/home/z/my-project/download/vercel.json").exists()))
checks.append(("README exists", Path("/home/z/my-project/download/README.md").exists()))

# Print results
passed = sum(1 for _, ok in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed\n")
for desc, ok in checks:
    print(f"  {'✓' if ok else '✗'} {desc}")

# File sizes
print(f"\n=== FILE SIZES ===")
for p in ["/home/z/my-project/download/index.html", 
          "/home/z/my-project/download/api/run-agent.js",
          "/home/z/my-project/download/data/apps.json",
          "/home/z/my-project/download/vercel.json",
          "/home/z/my-project/download/README.md"]:
    size = os.path.getsize(p)
    print(f"  {p}: {size:,} bytes ({size/1024:.1f} KB)")

if passed == total:
    print(f"\n🎉 ALL {total} CHECKS PASSED")
else:
    print(f"\n⚠ {total - passed} checks failed — review above")
