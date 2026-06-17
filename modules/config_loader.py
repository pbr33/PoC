"""
config_loader.py — reads config.yaml and populates Streamlit session state.

Works with OR without pyyaml installed: falls back to a minimal built-in parser.

Usage in main.py (after _defaults loop):
    from modules.config_loader import apply_config_to_session
    apply_config_to_session()
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


# ── YAML loading ──────────────────────────────────────────────────────────────

def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser for the config.yaml structure — no external deps."""
    stack: list[tuple[dict, int]] = [({}, -1)]   # (dict, indent_level)

    for raw_line in text.splitlines():
        # Strip inline comments that are NOT inside quotes
        line = raw_line.rstrip()
        in_q, qchar = False, None
        comment_pos = -1
        for i, ch in enumerate(line):
            if ch in ('"', "'") and not in_q:
                in_q, qchar = True, ch
            elif in_q and ch == qchar:
                in_q = False
            elif ch == "#" and not in_q:
                comment_pos = i
                break
        if comment_pos >= 0:
            line = line[:comment_pos].rstrip()

        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        if ":" not in stripped:
            continue

        key, sep, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        # Unquote string values
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]

        # Pop stack back to the correct parent depth
        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()

        parent = stack[-1][0]

        if not val:
            # Container node (dict)
            child: dict = {}
            parent[key] = child
            stack.append((child, indent))
        else:
            # Leaf value — store as string; caller does type conversion
            parent[key] = val

    return stack[0][0]


def load_config() -> dict:
    """Read config.yaml. Returns {} if missing or unreadable."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        raw = _CONFIG_PATH.read_text(encoding="utf-8")
    except Exception:
        return {}

    # Try pyyaml first (most accurate)
    try:
        import yaml  # noqa: F401  (pyyaml)
        data = yaml.safe_load(raw) or {}
        return data
    except ImportError:
        pass   # fall through to built-in parser
    except Exception:
        return {}

    # Fallback: use our simple built-in parser
    try:
        return _parse_simple_yaml(raw)
    except Exception:
        return {}


# ── Session-state population ──────────────────────────────────────────────────

def apply_config_to_session() -> None:
    """Populate session state from config.yaml.

    Only overwrites keys that are currently empty/falsy in session state,
    so env-var values set before this call are preserved.
    """
    cfg = load_config()
    if not cfg:
        return

    prov = cfg.get("providers", {})

    # ── Azure OpenAI ─────────────────────────────────────────────────────
    azure = prov.get("azure", {})
    _set("azure_api_key",     azure.get("api_key", ""))
    _set("azure_endpoint",    azure.get("endpoint", ""))
    _set("azure_deployment",  azure.get("deployment", ""))
    _set("azure_api_version", azure.get("api_version", "2024-06-01"))

    # ── Anthropic / Claude Sonnet (standard or Azure AI Services hosted) ──
    claude = prov.get("claude", {})
    _set("anthropic_api_key", claude.get("api_key", ""))
    _set("claude_model",      claude.get("model", "claude-sonnet-4-6"))
    _set("claude_endpoint",   claude.get("endpoint", ""))   # Azure AI Services URL

    # ── Claude Opus (separate deployment — activate via routing) ─────────
    opus = prov.get("claude_opus", {})
    _set("claude_opus_api_key",    opus.get("api_key",    claude.get("api_key", "")))
    _set("claude_opus_model",      opus.get("model",      "claude-opus-4-8"))
    _set("claude_opus_deployment", opus.get("deployment", "claude-opus-4-8"))
    _set("claude_opus_endpoint",   opus.get("endpoint",   claude.get("endpoint", "")))

    # ── Google Gemini ─────────────────────────────────────────────────────
    gemini = prov.get("gemini", {})
    _set("gemini_api_key", gemini.get("api_key", ""))
    _set("gemini_model",   gemini.get("model", "gemini-2.0-flash"))

    # ── Grok (xAI via Azure AI Foundry) ──────────────────────────────────
    grok = prov.get("grok", {})
    _set("grok_endpoint",    grok.get("endpoint", ""))
    _set("grok_key",         grok.get("key", ""))
    _set("grok_deployment",  grok.get("deployment", "grok-4-1-fast-reasoning"))
    _set("grok_api_version", grok.get("api_version", "2024-05-01-preview"))

    # ── DeepSeek (via Azure AI Foundry OpenAI-compat endpoint) ───────────
    deepseek = prov.get("deepseek", {})
    _set("deepseek_endpoint",   deepseek.get("endpoint",   ""))
    _set("deepseek_key",        deepseek.get("key",        ""))
    _set("deepseek_deployment", deepseek.get("deployment", "DeepSeek-V3.1"))

    # ── GPT-5.3-Codex (Azure OpenAI, standard endpoint) ──────────────────
    codex = prov.get("codex", {})
    _set("codex_api_key",     codex.get("api_key",     ""))
    _set("codex_endpoint",    codex.get("endpoint",    ""))
    _set("codex_deployment",  codex.get("deployment",  "gpt-5.3-codex"))
    _set("codex_api_version", codex.get("api_version", "2025-04-01-preview"))

    # ── GPT-5.4-Nano (Azure AI Foundry OpenAI-compat endpoint) ───────────
    nano = prov.get("nano", {})
    _set("nano_endpoint",   nano.get("endpoint",   ""))
    _set("nano_key",        nano.get("key",        ""))
    _set("nano_deployment", nano.get("deployment", "gpt-5.4-nano"))

    # ── Qwen ─────────────────────────────────────────────────────────────
    qwen = prov.get("qwen", {})
    qwen_mode = qwen.get("mode", "dashscope")
    if qwen_mode in ("foundry", "inference"):
        _set("qwen_endpoint",    qwen.get("endpoint", ""))
        _set("qwen_foundry_key", qwen.get("foundry_key", ""))
        _set("qwen_deployment",  qwen.get("deployment", "") or qwen.get("model", ""))
        _set("qwen_api_version", qwen.get("api_version", "2024-06-01"))
        _set("qwen_model",       qwen.get("deployment", "") or qwen.get("model", ""))
        _set("qwen_mode",        qwen_mode)
    else:
        _set("qwen_api_key", qwen.get("api_key", ""))
        _set("qwen_model",   qwen.get("model", "qwen-plus"))
        _set("qwen_mode",    "dashscope")

    # ── Vertex AI ────────────────────────────────────────────────────────
    vertex = prov.get("vertex", {})
    _set("vertex_project_id", vertex.get("project_id", ""))
    _set("vertex_region",     vertex.get("region", "us-east5"))
    _set("vertex_model",      vertex.get("model", "claude-sonnet-4-5@20251001"))

    # ── Routing ──────────────────────────────────────────────────────────
    routing = cfg.get("routing", {})
    default_llm = routing.get("default", "azure")
    _set("preferred_llm", default_llm)
    # Always refresh _routing so get_model_for_feature() is current
    st.session_state["_routing"] = routing

    # ── Integrations ─────────────────────────────────────────────────────
    integ = cfg.get("integrations", {})

    sp = integ.get("sharepoint", {})
    _set("sp_url", sp.get("site_url", ""))
    _set("sp_cid", sp.get("client_id", ""))
    _set("sp_cs",  sp.get("client_secret", ""))
    _set("sp_tid", sp.get("tenant_id", ""))

    email = integ.get("email", {})
    smtp = email.get("smtp_server", "")
    port = email.get("smtp_port", "")
    _set("email_smtp",    f"{smtp}:{port}" if (smtp and port) else smtp)
    _set("email_sender",   email.get("sender", ""))
    _set("cfg_email_pass", email.get("password", ""))

    narrator = integ.get("narrator", {})
    _set("elevenlabs_api_key", narrator.get("elevenlabs_api_key", ""))
    _set("heygen_api_key",     narrator.get("heygen_api_key", ""))
    _set("heygen_avatar_id",   narrator.get("heygen_avatar_id", ""))
    _set("heygen_voice_id",    narrator.get("heygen_voice_id", ""))
    _set("did_api_key",        narrator.get("did_api_key", ""))

    milvus = integ.get("milvus", {})
    _set("milvus_host",                 milvus.get("host", ""))
    _set("milvus_port",                 str(milvus.get("port", "19530")))
    _set("milvus_user",                 milvus.get("user", ""))
    _set("milvus_password",             milvus.get("password", ""))
    _set("milvus_db",                   milvus.get("db_name", ""))
    _set("milvus_embedding_endpoint",   milvus.get("embedding_endpoint", ""))
    _set("milvus_embedding_key",        milvus.get("embedding_key", ""))
    _set("milvus_embedding_deployment", milvus.get("embedding_deployment", "text-embedding-3-small"))
    _set("milvus_embedding_api_version",milvus.get("embedding_api_version", "2025-01-01-preview"))


def can_view_team_roles() -> bool:
    """Return True if the current user may see the Team & Roles (cost) tab.

    Controlled by access_control.team_roles_emails in config.yaml —
    a comma-separated list of allowed email addresses.
    If the list is empty or the key is absent, everyone can see the tab.
    """
    cfg = load_config()
    raw = cfg.get("access_control", {}).get("team_roles_emails", "")
    if not raw or not raw.strip():
        return True  # no restriction configured → allow all
    allowed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    user_email = st.session_state.get("auth_email", "").strip().lower()
    return user_email in allowed


def get_model_for_feature(feature: str) -> str:
    """Return the provider key for a named feature (e.g. 'chat', 'cost').

    Falls back to routing.default, then 'azure'.
    """
    routing: dict = st.session_state.get("_routing", {})
    if feature in routing:
        return routing[feature]
    return routing.get("default", st.session_state.get("preferred_llm", "azure"))


def is_any_ai_configured() -> bool:
    """Return True if at least one AI provider has credentials loaded."""
    return bool(
        (st.session_state.get("azure_api_key") and st.session_state.get("azure_endpoint"))
        or st.session_state.get("anthropic_api_key")
        or st.session_state.get("claude_opus_api_key")
        or st.session_state.get("gemini_api_key")
        or st.session_state.get("qwen_api_key")
        or st.session_state.get("qwen_foundry_key")
        or st.session_state.get("vertex_project_id")
        or (st.session_state.get("grok_key") and st.session_state.get("grok_endpoint"))
        or (st.session_state.get("deepseek_key") and st.session_state.get("deepseek_endpoint"))
        or (st.session_state.get("codex_api_key") and st.session_state.get("codex_endpoint"))
        or (st.session_state.get("nano_key") and st.session_state.get("nano_endpoint"))
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _set(key: str, value) -> None:
    """Write config.yaml value to session state.

    config.yaml always wins over hardcoded _defaults (e.g. azure_deployment="gpt-4").
    Only skips if config.yaml itself has an empty/blank value.
    """
    if value:  # non-empty value from config.yaml → always apply
        st.session_state[key] = value
