import os
"""Test both API keys — GLM (Z.ai) and Gemini — and report what models/capabilities we have."""
import json
import requests

GLM_KEY = os.environ.get("GLM_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")

print("=" * 70)
print("1. TESTING GLM (Z.ai) API KEY")
print("=" * 70)

# Try listing models first
try:
    r = requests.get(
        "https://open.bigmodel.cn/api/paas/v4/models",
        headers={"Authorization": f"Bearer {GLM_KEY}"},
        timeout=15,
    )
    print(f"GET /models  →  HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            models = [m.get("id") for m in data["data"]]
            print(f"Available models ({len(models)}):")
            for m in models[:30]:
                print(f"  - {m}")
        else:
            print(json.dumps(data, indent=2)[:1500])
    else:
        print(r.text[:500])
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=" * 70)
print("2. TESTING GLM CHAT COMPLETION (chat model)")
print("=" * 70)

# Try a simple chat completion with the most likely model name
for model in ["glm-4-flash", "glm-4.6", "glm-4.5-flash", "glm-4-flash-250414", "glm-4.7-flash"]:
    print(f"\nTrying model: {model}")
    try:
        r = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={
                "Authorization": f"Bearer {GLM_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Reply with exactly: GLM_OK"}
                ],
                "temperature": 0,
                "max_tokens": 20,
            },
            timeout=30,
        )
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            print(f"  ✓ WORKS — response: {content!r}")
            print(f"  Model used: {data.get('model', 'n/a')}")
            print(f"  Tokens: {data.get('usage', {})}")
            break
        else:
            print(f"  ✗ {r.text[:200]}")
    except Exception as e:
        print(f"  ✗ {e}")

print()
print("=" * 70)
print("3. TESTING GLM EMBEDDINGS (in case we need them)")
print("=" * 70)
try:
    r = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/embeddings",
        headers={
            "Authorization": f"Bearer {GLM_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "embedding-3",
            "input": "test",
        },
        timeout=15,
    )
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        print("  ✓ Embeddings endpoint works")
    else:
        print(f"  {r.text[:200]}")
except Exception as e:
    print(f"  ✗ {e}")

print()
print("=" * 70)
print("4. TESTING GEMINI API KEY")
print("=" * 70)

# List Gemini models
try:
    r = requests.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}",
        timeout=15,
    )
    print(f"GET /models  →  HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        models = data.get("models", [])
        print(f"Available Gemini models ({len(models)}):")
        for m in models[:25]:
            name = m.get("name", "")
            methods = m.get("supportedGenerationMethods", [])
            print(f"  - {name}  methods={methods}")
    else:
        print(r.text[:500])
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=" * 70)
print("5. TESTING GEMINI CHAT (gemini-2.0-flash or 1.5-flash)")
print("=" * 70)

for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"]:
    print(f"\nTrying model: {model}")
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "Reply with exactly: GEMINI_OK"}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 20},
            },
            timeout=30,
        )
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"  ✓ WORKS — response: {text!r}")
            usage = data.get("usageMetadata", {})
            print(f"  Tokens: {usage}")
            break
        else:
            print(f"  ✗ {r.text[:200]}")
    except Exception as e:
        print(f"  ✗ {e}")

print()
print("=" * 70)
print("DONE")
print("=" * 70)
