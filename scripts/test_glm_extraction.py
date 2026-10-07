"""Test GLM-4.5-flash properly — disable thinking if possible, use higher max_tokens."""
import json
import requests

GLM_KEY = os.environ.get("GLM_KEY", "")
BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
HEADERS = {"Authorization": f"Bearer {GLM_KEY}", "Content-Type": "application/json"}

print("=" * 70)
print("TEST 1: High max_tokens, default thinking")
print("=" * 70)
r = requests.post(BASE, headers=HEADERS, json={
    "model": "glm-4.5-flash",
    "messages": [{"role": "user", "content": "Say OK"}],
    "max_tokens": 2000,
    "temperature": 0.5,
}, timeout=60)
print(f"HTTP {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Content: {data['choices'][0]['message']['content']!r}")
    print(f"Usage: {data.get('usage', {})}")

print()
print("=" * 70)
print("TEST 2: Try disabling thinking with thinking parameter")
print("=" * 70)
for payload_extra in [
    {"thinking": {"type": "disabled"}},
    {"thinking": False},
    {"enable_thinking": False},
    {"do_sample": False},
]:
    print(f"\nWith extra: {payload_extra}")
    payload = {
        "model": "glm-4.5-flash",
        "messages": [{"role": "user", "content": "Say OK"}],
        "max_tokens": 500,
        "temperature": 0.5,
        **payload_extra,
    }
    r = requests.post(BASE, headers=HEADERS, json=payload, timeout=30)
    if r.status_code == 200:
        data = r.json()
        content = data['choices'][0]['message']['content']
        usage = data.get('usage', {})
        rt = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
        print(f"  Content: {content!r}  reasoning_tokens: {rt}")
    else:
        print(f"  HTTP {r.status_code}: {r.text[:200]}")

print()
print("=" * 70)
print("TEST 3: Realistic extraction task — extract from Stripe docs snippet")
print("=" * 70)
docs_snippet = """
import os
Stripe API Authentication

Stripe uses API keys to authenticate requests. You can view and manage your API keys in the Stripe Dashboard.

Your API keys include:
- Secret key (sk_live_...) — for server-side requests
- Publishable key (pk_live_...) — for client-side requests
- Restricted keys — for limited permissions

Test mode: Use sk_test_... keys during development. No real charges occur.

Stripe also supports OAuth 2.0 via Stripe Connect, allowing platforms to authenticate on behalf of connected accounts.

Self-serve: Anyone can create a free Stripe account and obtain API keys immediately. No sales contact required.

Rate limits: 100 read operations/sec, 100 write operations/sec per key.

Docs: https://docs.stripe.com/api
"""
payload = {
    "model": "glm-4.5-flash",
    "messages": [
        {"role": "system", "content": "You extract structured data from API documentation. Return only valid JSON, no markdown."},
        {"role": "user", "content": f"""Extract from this Stripe docs snippet:

{docs_snippet}

Return JSON with these fields:
- app_name: string
- auth_methods: array of strings (e.g., "api_key", "oauth2")
- self_serve: boolean (true if a developer can get credentials without sales contact)
- rate_limit: string (e.g., "100/sec")
- docs_url: string
- api_surface_breadth: "broad" | "medium" | "narrow"
- buildable_as_toolkit: boolean
- blocker: string or null
- evidence_quote: string (verbatim quote supporting auth_methods)
"""},
    ],
    "response_format": {"type": "json_object"},
    "max_tokens": 3000,
    "temperature": 0.2,
}
r = requests.post(BASE, headers=HEADERS, json=payload, timeout=90)
print(f"HTTP {r.status_code}")
if r.status_code == 200:
    data = r.json()
    content = data['choices'][0]['message']['content']
    print(f"Raw content:\n{content}")
    print(f"\nUsage: {data.get('usage', {})}")
    try:
        parsed = json.loads(content)
        print(f"\n✓ Parsed OK: {json.dumps(parsed, indent=2)}")
    except Exception as e:
        print(f"\n✗ Parse error: {e}")

print()
print("=" * 70)
print("TEST 4: Tool-calling structured extraction (alternative path)")
print("=" * 70)
tools = [{
    "type": "function",
    "function": {
        "name": "record_extraction",
        "description": "Record the extracted API research data for an app",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"},
                "auth_methods": {"type": "array", "items": {"type": "string"}},
                "self_serve": {"type": "boolean"},
                "rate_limit": {"type": "string"},
                "docs_url": {"type": "string"},
                "api_surface_breadth": {"type": "string", "enum": ["broad", "medium", "narrow"]},
                "buildable_as_toolkit": {"type": "boolean"},
                "blocker": {"type": ["string", "null"]},
                "evidence_quote": {"type": "string"}
            },
            "required": ["app_name", "auth_methods", "self_serve", "docs_url", "buildable_as_toolkit", "evidence_quote"]
        }
    }
}]
payload = {
    "model": "glm-4.5-flash",
    "messages": [
        {"role": "system", "content": "Extract API research data from docs and call record_extraction."},
        {"role": "user", "content": docs_snippet},
    ],
    "tools": tools,
    "tool_choice": {"type": "function", "function": {"name": "record_extraction"}},
    "max_tokens": 3000,
    "temperature": 0.2,
}
r = requests.post(BASE, headers=HEADERS, json=payload, timeout=90)
print(f"HTTP {r.status_code}")
if r.status_code == 200:
    msg = r.json()['choices'][0]['message']
    if msg.get('tool_calls'):
        args = msg['tool_calls'][0]['function']['arguments']
        print(f"Tool args: {args}")
        try:
            parsed = json.loads(args)
            print(f"\n✓ Parsed: {json.dumps(parsed, indent=2)}")
        except Exception as e:
            print(f"Parse error: {e}")
    else:
        print(f"No tool call. Content: {msg.get('content')!r}")
    print(f"\nUsage: {r.json().get('usage', {})}")
