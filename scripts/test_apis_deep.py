"""Deeper test — figure out which GLM models actually work on the free tier,
   and test structured output / tool calling / longer responses."""
import os
import json
import requests

GLM_KEY = os.environ.get("GLM_KEY", "")
BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
HEADERS = {"Authorization": f"Bearer {GLM_KEY}", "Content-Type": "application/json"}

# Test which models actually work without paid balance
candidates = ["glm-4.5-flash", "glm-4.5-air", "glm-4.5", "glm-4.6", "glm-4.7"]
print("=" * 70)
print("STEP 1: Which models work on free tier?")
print("=" * 70)
working = []
for m in candidates:
    try:
        r = requests.post(BASE, headers=HEADERS, json={
            "model": m,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 100,
            "temperature": 0,
        }, timeout=30)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            usage = r.json().get("usage", {})
            print(f"  ✓ {m}: works (response: {content!r}, tokens: {usage})")
            working.append(m)
        else:
            err = r.json().get("error", {})
            print(f"  ✗ {m}: HTTP {r.status_code} — {err.get('message', r.text[:100])}")
    except Exception as e:
        print(f"  ✗ {m}: {e}")

print()
print("=" * 70)
print(f"STEP 2: Test structured output on best working model: {working[0] if working else 'none'}")
print("=" * 70)

if working:
    model = working[0]
    # Test JSON mode + structured output
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You extract structured data. Output JSON only."},
            {"role": "user", "content": """Extract from this text and return JSON only.
Text: 'Slack uses OAuth 2.0 for user auth and bot tokens (xoxb-) for apps. API keys available at api.slack.com/web. Self-serve signup at slack.com/create.'

Return JSON with fields: app_name (string), auth_methods (array of strings), self_serve (boolean), docs_url (string)"""},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 300,
        "temperature": 0,
    }
    r = requests.post(BASE, headers=HEADERS, json=payload, timeout=60)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"]["content"]
        print(f"Raw response: {content}")
        try:
            parsed = json.loads(content)
            print(f"Parsed OK: {parsed}")
        except:
            print("Could not parse as JSON")
    else:
        print(r.text[:500])

print()
print("=" * 70)
print("STEP 3: Test tool calling / function calling")
print("=" * 70)

if working:
    model = working[0]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "What's the weather in Tokyo?"}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"]
                }
            }
        }],
        "tool_choice": "auto",
        "max_tokens": 200,
    }
    r = requests.post(BASE, headers=HEADERS, json=payload, timeout=30)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        msg = r.json()["choices"][0]["message"]
        print(f"Tool calls: {msg.get('tool_calls', 'none')}")
    else:
        print(r.text[:500])

print()
print("=" * 70)
print("STEP 4: Test long-context doc reading (5000 token prompt)")
print("=" * 70)
if working:
    model = working[0]
    long_text = "Stripe is a payment processor. " * 500  # ~2500 tokens
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": f"Read this and tell me what company it is. Just the name.\n\n{long_text}"}
        ],
        "max_tokens": 50,
        "temperature": 0,
    }
    r = requests.post(BASE, headers=HEADERS, json=payload, timeout=60)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        print(f"Response: {r.json()['choices'][0]['message']['content']!r}")
        print(f"Usage: {r.json().get('usage', {})}")
    else:
        print(r.text[:500])

print()
print("=" * 70)
print("STEP 5: Check if z-ai-web-dev-sdk CLI works in this environment")
print("=" * 70)
import subprocess
r = subprocess.run(["which", "z-ai"], capture_output=True, text=True)
print(f"z-ai CLI: {r.stdout.strip() or 'not found'}")
r = subprocess.run(["z-ai", "--help"], capture_output=True, text=True, timeout=10)
print(f"Help output (first 500 chars): {r.stdout[:500]}")
