"""Audit all 100 records for data quality issues.
   Flags: missing required fields, suspicious values, inconsistent enums, etc."""
import json, collections, re
from pathlib import Path

APPS_DIR = Path("/home/z/my-project/data/apps")
records = [json.loads(p.read_text()) for p in sorted(APPS_DIR.glob("*.json"))]

issues = []
VALID_AUTH = {"oauth2", "api_key", "basic", "bearer_token", "jwt", "session_cookie",
              "webhook_signature", "mtls", "none", "other", "client_credentials", "digest",
              "s2s_oauth2", "oauth", "unknown", "API_KEY"}
VALID_BLOCKERS = {"none", "auth_complexity", "gated_access", "poor_docs", "no_public_api",
                  "rate_limits", "legal_terms", "technical_instability", "unknown", None}
VALID_GATING = {"free", "free_trial", "paid_required", "contact_sales", "partner_program",
                "admin_approval", "enterprise_only", "unknown", None}
VALID_CONFIDENCE = {"high", "medium", "low"}

for r in records:
    name = r.get("app_name", "?")
    slug = r.get("app_slug", "?")
    issues_for_app = []
    
    # 1. Missing required fields
    required = ["app_name", "category", "docs_url", "auth_methods", "self_serve",
                "buildability_score", "main_blocker", "confidence"]
    for f in required:
        if f not in r or r[f] is None:
            if f == "auth_methods":
                # ok if app has no API
                if r.get("main_blocker") != "no_public_api":
                    issues_for_app.append(f"missing required: {f}")
            elif f == "self_serve":
                if r.get("main_blocker") != "no_public_api":
                    issues_for_app.append(f"missing required: {f}")
            elif f == "buildability_score":
                issues_for_app.append(f"missing required: {f}")
            elif f == "confidence":
                issues_for_app.append(f"missing required: {f}")
    
    # 2. Invalid enum values
    auths = r.get("auth_methods") or []
    for a in auths:
        if a not in VALID_AUTH:
            issues_for_app.append(f"invalid auth_method: {a!r}")
    
    if r.get("main_blocker") not in VALID_BLOCKERS:
        issues_for_app.append(f"invalid main_blocker: {r.get('main_blocker')!r}")
    if r.get("gating_type") not in VALID_GATING:
        issues_for_app.append(f"invalid gating_type: {r.get('gating_type')!r}")
    if r.get("confidence") not in VALID_CONFIDENCE:
        issues_for_app.append(f"invalid confidence: {r.get('confidence')!r}")
    
    # 3. Buildability score out of range
    bs = r.get("buildability_score")
    if bs is not None and (bs < 0 or bs > 5):
        issues_for_app.append(f"buildability_score out of range: {bs}")
    
    # 4. Inconsistency: buildability_score=5 but blocker != none
    if bs == 5 and r.get("main_blocker") not in ("none", None):
        issues_for_app.append(f"buildability=5 but blocker={r.get('main_blocker')} (should be 'none')")
    
    # 5. Inconsistency: buildability=0 but blocker == none
    if bs == 0 and r.get("main_blocker") == "none":
        issues_for_app.append(f"buildability=0 but blocker=none (should be 'no_public_api' or 'gated_access')")
    
    # 6. Inconsistency: self_serve=True but gating_type=contact_sales/enterprise_only
    if r.get("self_serve") is True and r.get("gating_type") in ("contact_sales", "enterprise_only", "partner_program"):
        issues_for_app.append(f"self_serve=True but gating_type={r.get('gating_type')} (contradiction)")
    
    # 7. Inconsistency: self_serve=False but gating_type=free/free_trial
    if r.get("self_serve") is False and r.get("gating_type") in ("free", "free_trial"):
        issues_for_app.append(f"self_serve=False but gating_type={r.get('gating_type')} (contradiction)")
    
    # 8. Auth method "none" but buildability > 0 (no auth usually means no API)
    if auths == ["none"] and (bs or 0) > 2:
        issues_for_app.append(f"auth=[none] but buildability={bs} (suspicious)")
    
    # 9. No auth_methods but buildability > 0
    if not auths and (bs or 0) > 0:
        issues_for_app.append(f"no auth_methods but buildability={bs} (suspicious)")
    
    # 10. Composio_supported but no composio_auth_schemes
    if r.get("composio_supported") is True and not r.get("composio_auth_schemes"):
        issues_for_app.append(f"composio_supported=True but no composio_auth_schemes")
    
    # 11. mcp_server_exists=True but no mcp_server_sources
    if r.get("mcp_server_exists") is True and not r.get("mcp_server_sources"):
        issues_for_app.append(f"mcp_server_exists=True but no mcp_server_sources")
    
    if issues_for_app:
        issues.append((name, slug, issues_for_app))

print(f"=== AUDIT RESULTS ===")
print(f"Total records: {len(records)}")
print(f"Records with issues: {len(issues)}")
print(f"Total issues: {sum(len(i[2]) for i in issues)}")
print()
print("=== Issues by app ===")
for name, slug, app_issues in issues:
    print(f"\n{name} ({slug}):")
    for i in app_issues:
        print(f"  - {i}")

# Save audit report
audit = {
    "total_records": len(records),
    "records_with_issues": len(issues),
    "total_issues": sum(len(i[2]) for i in issues),
    "issues": [{"app": n, "slug": s, "issues": i} for n, s, i in issues],
}
Path("/home/z/my-project/data/audit_report.json").write_text(json.dumps(audit, indent=2))
print(f"\nSaved to /home/z/my-project/data/audit_report.json")
