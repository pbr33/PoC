"""
Quick Azure OpenAI connection test — reads config.yaml and prints results.
Run:  python test_azure.py
"""
import json, sys, urllib.request, urllib.error

# ── Read config.yaml ──────────────────────────────────────────────────────────
try:
    import yaml
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
except ImportError:
    # fallback: very simple parser
    import re
    cfg = {}
    with open("config.yaml", encoding="utf-8") as f:
        raw = f.read()
    # Extract azure block values
    for key in ("api_key", "endpoint", "deployment", "api_version"):
        m = re.search(rf'^\s+{key}:\s+"?([^"\n#]+)"?', raw, re.MULTILINE)
        if m:
            if "azure" not in cfg:
                cfg.setdefault("providers", {}).setdefault("azure", {})
            cfg["providers"]["azure"][key] = m.group(1).strip()

azure = cfg.get("providers", {}).get("azure", {})
API_KEY    = azure.get("api_key", "").strip()
ENDPOINT   = azure.get("endpoint", "").rstrip("/")
DEPLOYMENT = azure.get("deployment", "").strip()
API_VER    = azure.get("api_version", "2024-06-01").strip()

print("=" * 60)
print("  Azure OpenAI Connection Test")
print("=" * 60)
print(f"  Endpoint:   {ENDPOINT or '(empty)'}")
print(f"  API key:    {API_KEY[:8]}...{API_KEY[-4:] if len(API_KEY) > 12 else '(too short)'}")
print(f"  Deployment: {DEPLOYMENT or '(empty)'}")
print(f"  API ver:    {API_VER}")
print("=" * 60)

if not API_KEY or not ENDPOINT or not DEPLOYMENT:
    print("\n❌  One or more required values are empty. Edit config.yaml.")
    sys.exit(1)

# ── Step 1: List all deployments on this resource ─────────────────────────────
print("\n[1/2] Fetching deployment list from Azure...")
list_url = f"{ENDPOINT}/openai/deployments?api-version={API_VER}"
req = urllib.request.Request(
    list_url,
    headers={"api-key": API_KEY, "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    deployments = [d["id"] for d in data.get("data", [])]
    print(f"  ✅ Found {len(deployments)} deployment(s) on this resource:")
    for d in deployments:
        marker = "  ◄ THIS ONE" if d == DEPLOYMENT else ""
        print(f"      • {d}{marker}")
    if DEPLOYMENT not in deployments:
        print(f"\n  ⚠️  '{DEPLOYMENT}' is NOT in the list above.")
        print("  Update the 'deployment' field in config.yaml to one of the names above.")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"  ⚠️  Could not list deployments (HTTP {e.code}): {body[:300]}")
    print("  This may be a permissions issue — continuing to chat test...")
except Exception as e:
    print(f"  ⚠️  Could not list deployments: {e}")

# ── Step 2: Send a test chat completion ───────────────────────────────────────
print(f"\n[2/2] Testing chat completion with deployment '{DEPLOYMENT}'...")
chat_url = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VER}"
payload = json.dumps({
    "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
    "max_tokens": 5,
    "temperature": 0,
}).encode("utf-8")
req2 = urllib.request.Request(
    chat_url, data=payload,
    headers={"api-key": API_KEY, "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req2, timeout=15) as resp:
        result = json.loads(resp.read())
    reply = result["choices"][0]["message"]["content"].strip()
    print(f"  ✅ SUCCESS — model replied: '{reply}'")
    print("\n  Azure OpenAI is working correctly!")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    err = json.loads(body) if body.startswith("{") else {"raw": body}
    code = err.get("error", {}).get("code", "")
    msg  = err.get("error", {}).get("message", body[:200])
    print(f"  ❌ HTTP {e.code} — {code}: {msg}")
    if e.code == 404 and "DeploymentNotFound" in code:
        print(f"\n  FIX: The deployment name '{DEPLOYMENT}' does not exist.")
        print("  Check the list in Step 1 above and update config.yaml.")
    elif e.code == 401:
        print("\n  FIX: API key is invalid. Check config.yaml → providers.azure.api_key")
    elif e.code == 400:
        # Try with max_completion_tokens for o-series models
        print("  Retrying with max_completion_tokens (o-series model)...")
        payload2 = json.dumps({
            "messages": [{"role": "user", "content": "Reply OK"}],
            "max_completion_tokens": 5,
        }).encode("utf-8")
        req3 = urllib.request.Request(
            chat_url, data=payload2,
            headers={"api-key": API_KEY, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req3, timeout=15) as resp3:
                r3 = json.loads(resp3.read())
                print(f"  ✅ SUCCESS with max_completion_tokens: '{r3['choices'][0]['message']['content'].strip()}'")
        except Exception as e2:
            print(f"  ❌ Retry also failed: {e2}")
except Exception as e:
    print(f"  ❌ Connection error: {e}")

print("\n" + "=" * 60)
