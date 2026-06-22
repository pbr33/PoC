"""
ECI Business Estimation — modular entry point.
Run with:  streamlit run main.py
"""
import os
import streamlit as st

st.set_page_config(
    page_title="ECI — Business Estimation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide sidebar and its collapse toggle entirely
st.markdown(
    """<style>
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    button[kind="header"] { display: none !important; }
    </style>""",
    unsafe_allow_html=True,
)

from datetime import datetime

from modules.auth import check_auth
from modules.styles import inject_css, ECI_LOGO_BLUE_B64
from modules.command_palette import inject_command_palette
from modules.ai_clients import AnthropicAI, AzureAI, GeminiAI, QwenAI, VertexAnthropicAI
from modules.external_services import SP
from modules.pipeline import tab_presale, tab_run_library, tab_admin, tab_dashboard
from modules.notifications import render_notification_bell
from modules.config_loader import apply_config_to_session, is_any_ai_configured

# ── Auth gate ──────────────────────────────────────────────────────────
check_auth()

# ═══════════════════════════════════════════════════════════════════════
#  SESSION STATE DEFAULTS
# ═══════════════════════════════════════════════════════════════════════

_defaults = {
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "claude_model":      os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
    "azure_api_key":     os.environ.get("AZURE_API_KEY", ""),
    "azure_endpoint":    os.environ.get("AZURE_ENDPOINT", ""),
    "azure_api_version": "2024-06-01",
    "azure_deployment":  os.environ.get("AZURE_DEPLOYMENT", "gpt-4"),
    "gemini_api_key":    os.environ.get("GEMINI_API_KEY", ""),
    "gemini_model":      os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    "qwen_api_key":      os.environ.get("QWEN_API_KEY", ""),       # DashScope key
    "qwen_model":        os.environ.get("QWEN_MODEL", "qwen-plus"),
    "qwen_foundry_key":  os.environ.get("QWEN_FOUNDRY_KEY", ""),  # Foundry key (separate)
    "qwen_endpoint":     os.environ.get("QWEN_ENDPOINT", ""),
    "qwen_deployment":   os.environ.get("QWEN_DEPLOYMENT", ""),
    "qwen_api_version":  os.environ.get("QWEN_API_VERSION", "2024-06-01"),
    "vertex_project_id": os.environ.get("VERTEX_PROJECT_ID", ""),
    "vertex_region":     os.environ.get("VERTEX_REGION", "us-east5"),
    "vertex_model":      os.environ.get("VERTEX_MODEL", "claude-sonnet-4-5@20251001"),
    "preferred_llm":     os.environ.get("PREFERRED_LLM", "azure"),
    "chat_messages":     [],
    "proposal_versions": [],
    "live_pricing_cache": {},
    "sp_url": "", "sp_cid": "", "sp_cs": "", "sp_tid": "",
    "email_smtp": "", "email_sender": "", "cfg_email_pass": "",
    "narrator_script": "",
    "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY", ""),
    "heygen_api_key":     os.environ.get("HEYGEN_API_KEY", ""),
    "heygen_avatar_id":   os.environ.get("HEYGEN_AVATAR_ID", ""),
    "heygen_voice_id":    os.environ.get("HEYGEN_VOICE_ID", ""),
    "did_api_key":        os.environ.get("DID_API_KEY", ""),
    "narrator_result": None,
    "narrator_mode": "custom",
    "narrator_free_avatars": [],
    "narrator_photo_id": "",
    "narrator_selected_avatar": "",
    "narrator_custom_avatar_id": os.environ.get("HEYGEN_AVATAR_ID", ""),
    "narrator_test_mode": True,
    "narrator_did_image_url": "",
    "time_test_mode": False,
    "narrator_did_presenters": [],
    "processing_results": None, "historical_projects": [], "agent_logs": [],
    "discovery_results": None, "discovery_transcript": "",
    "_extracted_text": "",
    "_extracted_filenames": [],
    "feedback_items": {},
    "feedback_log": [],
    "results_before_regen": None,
    "regen_sections": [],
    "_completeness_check": None,
    "_completeness_dismissed": False,
    "_completeness_acked": set(),
    "_disc_covered": set(),
    "scenarios": [],
    "_sc_active": 0,
    "model_metrics": {"accuracy": 78.5, "proposals_processed": 0, "win_rate": 62.0, "variance": 12.3},
    "_az_err_shown": False,
    # Proposal tab editing
    "proposal_edits": {},
    "proposal_section_edit_mode": set(),
    "proposal_regen_show": set(),
    "proposal_regen_prompt": {},
    "proposal_ref_show": set(),
    "proposal_ref_text": {},
    "proposal_ref_name": {},
    "proposal_ref_use_ctx": {},
    "proposal_client_name": "",
    "proposal_contact_name": "",
    "proposal_proposal_date": "",
    "proposal_regen_loading": set(),
    "_3d_narration": {},
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Load config.yaml (overrides env-var defaults for any key that was empty)
apply_config_to_session()

inject_css()
inject_command_palette()


# ═══════════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════════

import base64 as _b64
import os as _os

# Load logo directly from file if present, otherwise fall back to embedded base64
_logo_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "eci_logo.png")
if _os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _lf:
        _logo_b64_str = _b64.b64encode(_lf.read()).decode()
else:
    _logo_b64_str = ECI_LOGO_BLUE_B64

_user_name   = st.session_state.get("auth_user", "User")
_user_email  = st.session_state.get("auth_email", "")
_auth_method = st.session_state.get("auth_method", "")
_method_icon = "🪟" if _auth_method == "Microsoft SSO" else "🔑"
_initials    = "".join(p[0].upper() for p in _user_name.split()[:2]) if _user_name else "U"

hc1, hc2, hc3 = st.columns([2, 6, 2])
with hc1:
    st.markdown(
        f'<div style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;padding:4px 0">'
        f'<img src="data:image/png;base64,{_logo_b64_str}" '
        f'style="width:120px;height:auto;display:block;'
        f'background:#ffffff;border-radius:6px;padding:4px;" />'
        f'<div class="logo-sub" style="margin-top:4px;font-size:0.75rem;letter-spacing:2px;">AGENT BY ECI</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with hc2:
    st.markdown('<div class="tagline" style="font-size:1.35rem;font-weight:600;">Business Estimation Leveraging Automated Learning</div>', unsafe_allow_html=True)
with hc3:
    _ai_any = is_any_ai_configured()
    _ai_dot = "🟢" if _ai_any else "🔴"
    st.markdown(
        f'<div style="text-align:right;font-size:.72rem;color:#64748b;margin-bottom:4px">'
        f'{datetime.now().strftime("%b %d, %Y  %H:%M")} &nbsp;'
        f'<span style="color:{"#00d4aa" if _ai_any else "#ef4444"}">{_ai_dot} {"AI Live" if _ai_any else "No AI"}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Notification bell — same depth as hc3 (level-1 col), popover inside is OK
    render_notification_bell()
    # User menu as expander (works on all Streamlit versions ≥ 1.30)
    with st.expander(f"👤 {_initials}", expanded=False):
        st.markdown(
            f'<div style="padding:4px 0 8px">'
            f'<div style="font-weight:700;color:#e2e8f0;font-size:.9rem">{_user_name}</div>'
            f'<div style="font-size:.72rem;color:#64748b;margin-top:2px">{_user_email}</div>'
            f'<div style="font-size:.7rem;color:#00b4d8;margin-top:3px">{_method_icon} {_auth_method}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("🚪 Sign Out", use_container_width=True, type="secondary", key="signout_btn"):
            for _k in ["auth_ok", "auth_user", "auth_email", "auth_method"]:
                st.session_state.pop(_k, None)
            st.rerun()


# ── Config health check ────────────────────────────────────────────────
if not is_any_ai_configured():
    _az_key = st.session_state.get("azure_api_key", "")
    _az_ep  = st.session_state.get("azure_endpoint", "")
    if _az_key and not _az_ep:
        st.warning("Azure API key found but **endpoint** is missing. Add `endpoint` to `config.yaml`.", icon="⚠️")
    elif _az_ep and not _az_key:
        st.warning("Azure endpoint found but **API key** is missing. Add `api_key` to `config.yaml`.", icon="⚠️")
    else:
        st.info(
            "**No AI provider configured.** The pipeline will run in Demo Mode (template data only). "
            "Fill in `config.yaml` with your Azure OpenAI (or other provider) credentials to enable real AI processing.",
            icon="ℹ️",
        )

# ═══════════════════════════════════════════════════════════════════════
#  MAIN TABS
# ═══════════════════════════════════════════════════════════════════════

_is_admin = st.session_state.get("auth_method") == "Admin"

if _is_admin:
    main_t0, main_t1, main_t2, main_t3 = st.tabs([
        "🏠 Dashboard",
        "⚡ Business Estimation",
        "🗂️ Run Library",
        "⚙️ Admin & Training",
    ])
    with main_t0:
        tab_dashboard()
    with main_t1:
        tab_presale()
    with main_t2:
        tab_run_library()
    with main_t3:
        tab_admin()
else:
    main_t1, main_t2 = st.tabs([
        "⚡ Business Estimation",
        "🗂️ Run Library",
    ])
    with main_t1:
        tab_presale()
    with main_t2:
        tab_run_library()
