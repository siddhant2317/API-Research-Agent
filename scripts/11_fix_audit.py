"""Fix the 3 audit issues + recheck all human overrides took effect."""
import json, time
from pathlib import Path

APPS_DIR = Path("/home/z/my-project/data/apps")

# Fix 1: Mermaid CLI — it's a CLI tool, not an API. Buildability 2 (can be wrapped as subprocess), blocker none
p = APPS_DIR / "mermaid-cli.json"
r = json.loads(p.read_text())
r["buildability_score"] = 2
r["main_blocker"] = "none"
r["buildability_rationale"] = "CLI tool (no API), but can be wrapped as a subprocess tool for agents. Open-source, self-serve, no auth needed."
r["agent_notes"] = (r.get("agent_notes") or "") + " [AUDIT FIX: buildability 3→2; it's a CLI not an API, but still usable as a subprocess tool.]"
r["audited_at"] = time.time()
p.write_text(json.dumps(r, indent=2))
print(f"✓ Mermaid CLI: buildability 3→2, blocker→none")

# Fix 2: Twilio — mcp_server_exists should be False (we have no verified MCP source)
p = APPS_DIR / "twilio.json"
r = json.loads(p.read_text())
r["mcp_server_exists"] = False
r["mcp_server_sources"] = []
r["agent_notes"] = (r.get("agent_notes") or "") + " [AUDIT FIX: mcp_server_exists True→False; we have no verified MCP source.]"
r["audited_at"] = time.time()
p.write_text(json.dumps(r, indent=2))
print(f"✓ Twilio: mcp_server_exists True→False")

# Fix 3: WhatsApp Business — override didn't take effect, re-apply
p = APPS_DIR / "whatsapp-business.json"
r = json.loads(p.read_text())
r["auth_methods"] = ["oauth2", "api_key"]
r["auth_methods_evidence"] = "WhatsApp Business Cloud API uses Meta OAuth 2.0 + Bearer token. https://developers.facebook.com/docs/whatsapp/whatsapp-cloud-api/get-started"
r["self_serve"] = True
r["self_serve_evidence"] = "Free Meta developer account; first 1000 conversations/month free. https://developers.facebook.com/docs/whatsapp"
r["gating_type"] = "free"
r["api_surface_breadth"] = "medium"
r["api_protocol"] = ["rest", "webhook"]
r["endpoint_count_estimate"] = 25
r["openapi_spec_available"] = False
r["mcp_server_exists"] = True
r["mcp_server_sources"] = ["composio:whatsapp"]
r["composio_supported"] = True
r["composio_auth_schemes"] = ["OAUTH2", "API_KEY"]
r["composio_tools_count"] = 57
r["buildability_score"] = 4
r["buildability_rationale"] = "Self-serve free tier, OAuth2 + Bearer, Composio-supported, webhooks."
r["main_blocker"] = "none"
r["confidence"] = "high"
r["agent_notes"] = "[HUMAN OVERRIDE: WhatsApp Cloud API uses Meta OAuth2. Free dev account. Composio-supported.] [AUDIT FIX: re-applied override that didn't take effect.]"
r["evidence_urls"] = ["https://developers.facebook.com/docs/whatsapp/whatsapp-cloud-api/get-started"]
r["one_line_description"] = "WhatsApp Cloud messaging API for businesses"
r["audited_at"] = time.time()
p.write_text(json.dumps(r, indent=2))
print(f"✓ WhatsApp Business: re-applied override (auth=['oauth2','api_key'], buildability=4)")

# Re-run audit to confirm
print("\n=== Re-running audit ===")
import subprocess
result = subprocess.run(["python3", "/home/z/my-project/scripts/10_audit.py"], capture_output=True, text=True)
# Just show the summary
output = result.stdout
# Find the summary section
for line in output.split('\n')[:8]:
    print(line)
