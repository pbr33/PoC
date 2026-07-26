# ═══════════════════════════════════════════════════════════════════════
#  AUTH — Microsoft SSO + admin fallback
# ═══════════════════════════════════════════════════════════════════════
import base64, hashlib
import streamlit as st

try:
    import msal
    import requests as _requests
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False

# ── Credentials & Azure AD config (override via .streamlit/secrets.toml) ──
_ADMIN_USER     = "prabhakar"
_ADMIN_PASS_SHA = "2f835a18449213e30763cc07f71dedd57ba138f3543de60d7830bec305e9652c"  # password: prabhakar

import os as _os

def _secret(key: str, default: str = "") -> str:
    """Safe secrets accessor — env var > secrets.toml > default.

    Priority order (highest first):
      1. Environment variable (set on VM/Docker/systemd)
      2. .streamlit/secrets.toml
      3. default value
    """
    env_val = _os.environ.get(key, "")
    if env_val:
        return env_val
    try:
        return st.secrets.get(key, default) or default
    except Exception:
        return default

def _detect_base_url() -> str:
    """Auto-detect the public URL of this Streamlit deployment from request headers.

    Works on any server without configuration — reads the Host header that the
    browser sent, so it automatically matches whatever URL the user typed.
    """
    try:
        # Streamlit 1.37+ exposes st.context.headers
        _h = st.context.headers  # type: ignore[attr-defined]
        host = _h.get("Host", "") or _h.get("host", "")
        if host and "localhost" not in host and "127.0.0.1" not in host:
            proto = "https" if _h.get("X-Forwarded-Proto", "").lower() == "https" else "http"
            return f"{proto}://{host}"
    except Exception:
        pass
    return "http://localhost:8501"


def _get_sso_config() -> dict:
    """Read SSO credentials — env vars > secrets.toml > config.yaml fallback.

    APP_BASE_URL is auto-detected from the incoming request when not explicitly set,
    so the same config works on localhost and any server without changes.
    """
    _mapping = {
        "AAD_CLIENT_ID":     "client_id",
        "AAD_TENANT_ID":     "tenant_id",
        "AAD_CLIENT_SECRET": "client_secret",
        "APP_BASE_URL":      "app_base_url",
    }
    # Load config.yaml as lowest-priority fallback
    try:
        from .config_loader import load_config
        _sso_cfg = load_config().get("integrations", {}).get("sso", {})
    except Exception:
        _sso_cfg = {}

    result = {}
    for env_key, cfg_key in _mapping.items():
        val = _secret(env_key, "") or _sso_cfg.get(cfg_key, "")
        result[env_key] = val

    # Auto-detect base URL if not explicitly configured or still pointing to localhost
    _explicit = result.get("APP_BASE_URL", "")
    if not _explicit or "localhost" in _explicit or "127.0.0.1" in _explicit:
        _auto = _detect_base_url()
        if "localhost" not in _auto:
            result["APP_BASE_URL"] = _auto

    result.setdefault("APP_BASE_URL", "http://localhost:8501")
    return result

# ── MSAL confidential-client app (created fresh each login render) ────
def _msal_app(client_id: str, tenant_id: str, client_secret: str):
    if not (HAS_MSAL and client_id and tenant_id):
        return None
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        return msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret or None,
        )
    except Exception:
        return None

def _logo_b64(path: str) -> str:
    try:
        return base64.b64encode(open(path, "rb").read()).decode()
    except Exception:
        return ""

# ── Login page UI ─────────────────────────────────────────────────────
def _show_login():
    logo_b64 = _logo_b64("eci_logo_white.png") or _logo_b64("eci_logo.png") or _logo_b64("eci.png")
    logo_lg  = (f'<img src="data:image/png;base64,{logo_b64}" style="height:52px" />'
                if logo_b64 else
                '<div style="font-size:2rem;font-weight:900;color:#fff;letter-spacing:1px">ECI<span style="color:#00b4d8">+</span></div>')
    logo_sm  = (f'<img src="data:image/png;base64,{logo_b64}" style="height:36px;display:block;margin:0 auto 18px" />'
                if logo_b64 else '')

    # ── Pre-compute SSO URL before any rendering ─────────────────────
    _sso        = _get_sso_config()
    _client_id  = _sso["AAD_CLIENT_ID"]
    _tenant_id  = _sso["AAD_TENANT_ID"]
    _client_sec = _sso["AAD_CLIENT_SECRET"]
    _base_url   = _sso["APP_BASE_URL"]
    _redirect   = _base_url.rstrip("/") + "/"
    # Store redirect URI in session so users can see it when debugging
    st.session_state["_sso_redirect_uri"] = _redirect
    msal_app    = _msal_app(_client_id, _tenant_id, _client_sec)

    # Handle OAuth callback immediately (before any HTML renders)
    _doing_callback = msal_app and _client_id and "code" in st.query_params

    # Build SSO HTML snippet (all in one string — included in first markdown)
    if msal_app and _client_id and not _doing_callback:
        _auth_url = msal_app.get_authorization_request_url(["User.Read"], redirect_uri=_redirect)
        _sso_html = (
            f'<a href="{_auth_url}" target="_self" class="ms-btn">'
            f'<span class="ms-grid">'
            f'<span style="background:#f25022"></span>'
            f'<span style="background:#7fba00"></span>'
            f'<span style="background:#00a4ef"></span>'
            f'<span style="background:#ffb900"></span>'
            f'</span>Sign in with Microsoft</a>'
            f'<div class="or-div">or continue with</div>'
        )
    else:
        _sso_html = (
            '<div class="sso-info">🪟 Microsoft SSO — configure '
            '<code>AAD_CLIENT_ID</code>, <code>AAD_TENANT_ID</code> '
            'in <code>.streamlit/secrets.toml</code> to enable</div>'
        )

    # ── Global styles + background ────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

[data-testid="stAppViewContainer"] * { font-family:'Inter',system-ui,sans-serif !important; }
[data-testid="stAppViewContainer"]  { background:#07091c !important; min-height:100vh; }
[data-testid="stHeader"]  { display:none !important; }
[data-testid="stSidebar"] { display:none !important; }
#MainMenu,footer { visibility:hidden; }
[data-testid="stMain"]          { padding:0 !important; background:transparent !important; }
[data-testid="block-container"] { padding:0 !important; max-width:100vw !important; }

/* dot grid */
[data-testid="stAppViewContainer"]::before {
    content:''; position:fixed; inset:0;
    background-image:radial-gradient(rgba(255,255,255,.05) 1px,transparent 1px);
    background-size:30px 30px; pointer-events:none; z-index:0;
}

/* orbs */
.lp-orb{position:fixed;border-radius:50%;filter:blur(100px);pointer-events:none;z-index:0}
.lp-orb-1{width:700px;height:700px;background:rgba(0,80,255,.16);top:-220px;left:-220px;animation:lporb1 22s ease-in-out infinite}
.lp-orb-2{width:600px;height:600px;background:rgba(110,30,255,.13);bottom:-180px;right:-120px;animation:lporb2 28s ease-in-out infinite}
.lp-orb-3{width:420px;height:420px;background:rgba(0,180,140,.1);top:45%;left:38%;transform:translate(-50%,-50%);animation:lporb3 19s ease-in-out infinite}
@keyframes lporb1{0%,100%{transform:translate(0,0)}50%{transform:translate(70px,-60px)}}
@keyframes lporb2{0%,100%{transform:translate(0,0)}50%{transform:translate(-65px,-75px)}}
@keyframes lporb3{0%,100%{transform:translate(-50%,-50%)}50%{transform:translate(-44%,-56%)}}

/* particles */
.lp-particles{position:fixed;inset:0;pointer-events:none;z-index:1;overflow:hidden}
.lp-p{position:absolute;border-radius:50%;background:rgba(255,255,255,.55);animation:lprise linear infinite}
@keyframes lprise{
    0%{transform:translateY(105vh) translateX(0);opacity:0}
    6%{opacity:1} 94%{opacity:.35}
    100%{transform:translateY(-60px) translateX(var(--dx,0px));opacity:0}
}

/* vertical separator */
.lp-vrule{position:fixed;left:42%;top:8%;height:84%;width:1px;
    background:linear-gradient(to bottom,transparent,rgba(255,255,255,.07) 25%,rgba(255,255,255,.07) 75%,transparent);
    pointer-events:none;z-index:5}

/* columns */
[data-testid="stHorizontalBlock"]{gap:0 !important;min-height:100vh !important}

/* left column fills viewport */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1){
    min-height:100vh !important;
}

/* right column — centres the card */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){
    display:flex !important; align-items:center !important; justify-content:center !important;
    min-height:100vh !important; padding:40px 32px !important;
    position:relative !important; z-index:10 !important;
    animation:lpSlideUp .85s cubic-bezier(.16,1,.3,1) both; animation-delay:.08s;
}
@keyframes lpSlideUp{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:translateY(0)}}

/* THE CARD — applied to the stVerticalBlock inside the right column */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) > [data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) > div > [data-testid="stVerticalBlock"]{
    background:rgba(255,255,255,.038) !important;
    backdrop-filter:blur(52px) !important; -webkit-backdrop-filter:blur(52px) !important;
    border:1px solid rgba(255,255,255,.09) !important;
    border-radius:28px !important;
    padding:48px 44px 44px !important;
    width:100% !important; max-width:440px !important;
    box-shadow:0 0 0 1px rgba(255,255,255,.04),0 48px 120px rgba(0,0,0,.65),0 0 80px rgba(0,50,200,.05) !important;
    position:relative !important;
}
/* top sheen */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) > [data-testid="stVerticalBlock"]::before,
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) > div > [data-testid="stVerticalBlock"]::before{
    content:'' !important; position:absolute !important; top:0 !important; left:0 !important; right:0 !important; height:1px !important;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.18) 50%,transparent) !important; pointer-events:none !important;
}

/* brand panel */
.brand-panel{min-height:100vh;padding:64px 52px 64px 64px;display:flex;flex-direction:column;
    justify-content:center;position:relative;z-index:10;
    animation:lpSlideLeft .9s cubic-bezier(.16,1,.3,1) both}
@keyframes lpSlideLeft{from{opacity:0;transform:translateX(-28px)}to{opacity:1;transform:translateX(0)}}
.brand-logo{margin-bottom:44px}
.brand-badge{display:inline-flex;align-items:center;gap:8px;padding:5px 14px;
    background:rgba(0,180,216,.08);border:1px solid rgba(0,180,216,.2);border-radius:100px;
    font-size:.68rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;
    color:rgba(0,200,230,.85);margin-bottom:24px}
.brand-badge .bdot{width:6px;height:6px;border-radius:50%;background:#00d4ff;animation:bdotpulse 2.2s ease-in-out infinite}
@keyframes bdotpulse{0%,100%{box-shadow:0 0 0 0 rgba(0,212,255,.5)}50%{box-shadow:0 0 0 5px rgba(0,212,255,0)}}
.brand-h1{font-size:2.85rem;font-weight:900;line-height:1.18;letter-spacing:-1.5px;margin-bottom:18px;
    background:linear-gradient(140deg,#ffffff 0%,#c6e4ff 45%,#a78bfa 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.brand-desc{font-size:.93rem;color:rgba(255,255,255,.38);line-height:1.75;max-width:390px;margin-bottom:48px}
.stat-grid{display:flex;flex-direction:column;gap:13px}
.stat-card{display:flex;align-items:center;gap:16px;padding:15px 20px;
    background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);
    border-radius:16px;position:relative;overflow:hidden;
    animation:lpStatIn .65s cubic-bezier(.16,1,.3,1) both}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.07),transparent)}
.stat-card:nth-child(1){animation-delay:.35s;border-color:rgba(0,100,255,.14)}
.stat-card:nth-child(2){animation-delay:.52s;border-color:rgba(110,30,255,.14)}
.stat-card:nth-child(3){animation-delay:.69s;border-color:rgba(0,180,140,.14)}
@keyframes lpStatIn{from{opacity:0;transform:translateX(-18px)}to{opacity:1;transform:translateX(0)}}
.stat-icon{width:44px;height:44px;border-radius:12px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:1.15rem}
.ic-b{background:rgba(0,100,255,.1);border:1px solid rgba(0,100,255,.22)}
.ic-p{background:rgba(110,30,255,.1);border:1px solid rgba(110,30,255,.22)}
.ic-t{background:rgba(0,180,140,.1);border:1px solid rgba(0,180,140,.22)}
.stat-val{font-size:.88rem;font-weight:700;color:rgba(255,255,255,.88)}
.stat-desc{font-size:.72rem;color:rgba(255,255,255,.32);margin-top:2px}

/* card header elements */
.card-welcome{font-size:.68rem;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;
    color:rgba(0,190,230,.7);margin-bottom:8px;text-align:center}
.card-title{font-size:1.55rem;font-weight:800;color:#fff;letter-spacing:-.3px;margin-bottom:6px;text-align:center}
.card-sub{font-size:.76rem;color:rgba(255,255,255,.28);letter-spacing:.2px;line-height:1.55;
    text-align:center;margin-bottom:28px}

/* MS button */
.ms-btn{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;
    padding:14px 20px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.11);
    border-radius:14px;color:rgba(255,255,255,.92) !important;font-size:.9rem;font-weight:600;
    text-decoration:none !important;letter-spacing:.2px;
    transition:all .25s cubic-bezier(.16,1,.3,1)}
.ms-btn:hover{background:rgba(255,255,255,.09);border-color:rgba(255,255,255,.22);
    transform:translateY(-2px);box-shadow:0 12px 36px rgba(0,0,0,.32);
    color:#fff !important;text-decoration:none !important}
.ms-grid{display:grid;grid-template-columns:1fr 1fr;gap:2.5px;width:20px;height:20px;flex-shrink:0}
.ms-grid span{border-radius:1.5px}

/* OR divider */
.or-div{display:flex;align-items:center;gap:14px;margin:20px 0;
    color:rgba(255,255,255,.17);font-size:.68rem;font-weight:600;letter-spacing:2px;text-transform:uppercase}
.or-div::before,.or-div::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.07)}

/* SSO info */
.sso-info{background:rgba(0,180,216,.06);border:1px solid rgba(0,180,216,.14);
    border-radius:12px;padding:11px 16px;font-size:.74rem;color:rgba(255,255,255,.35);
    text-align:center;margin-bottom:4px}

/* Admin Access toggle button */
div[data-testid="stButton"] > button {
    background:rgba(255,255,255,.04) !important;
    border:1px solid rgba(255,255,255,.1) !important;
    border-radius:14px !important;
    color:rgba(255,255,255,.6) !important;
    font-size:.88rem !important; font-weight:600 !important;
    padding:13px !important; letter-spacing:.3px !important;
    transition:all .22s ease !important; width:100% !important;
}
div[data-testid="stButton"] > button:hover{
    background:rgba(255,255,255,.08) !important;
    border-color:rgba(255,255,255,.2) !important;
    color:rgba(255,255,255,.85) !important;
    transform:translateY(-1px) !important;
}

/* admin label */
.admin-lbl{font-size:.67rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;
    color:rgba(255,255,255,.22);margin-bottom:14px;padding-bottom:10px;
    border-bottom:1px solid rgba(255,255,255,.05)}

/* inputs */
div[data-testid="stTextInput"]{margin-bottom:4px !important}
div[data-testid="stTextInput"] label{color:rgba(255,255,255,.48) !important;font-size:.75rem !important;
    font-weight:500 !important;letter-spacing:.2px !important}
div[data-testid="stTextInput"] input{background:rgba(255,255,255,.04) !important;
    border:1px solid rgba(255,255,255,.09) !important;border-radius:14px !important;
    color:#fff !important;padding:13px 16px !important;font-size:.88rem !important;
    height:auto !important;transition:all .22s ease !important}
div[data-testid="stTextInput"] input:focus{border-color:rgba(0,170,220,.45) !important;
    box-shadow:0 0 0 3px rgba(0,170,220,.1),0 2px 12px rgba(0,170,220,.07) !important;
    background:rgba(0,170,220,.03) !important;outline:none !important}
div[data-testid="stTextInput"] input::placeholder{color:rgba(255,255,255,.17) !important}
div[data-testid="InputInstructions"]{display:none !important}
small[data-testid="InputInstructions"]{display:none !important}

/* Sign In submit button */
div[data-testid="stFormSubmitButton"] button{
    background:linear-gradient(135deg,#0050ff 0%,#003ecc 45%,#5b2fff 100%) !important;
    border:none !important;border-radius:14px !important;
    font-weight:700 !important;font-size:.92rem !important;
    padding:14px !important;letter-spacing:.3px !important;
    box-shadow:0 6px 24px rgba(0,80,255,.35),inset 0 1px 0 rgba(255,255,255,.12) !important;
    transition:all .25s cubic-bezier(.16,1,.3,1) !important;
    width:100% !important;margin-top:10px !important;color:#fff !important}
div[data-testid="stFormSubmitButton"] button:hover{
    transform:translateY(-2px) !important;
    box-shadow:0 12px 40px rgba(0,80,255,.5),0 0 60px rgba(91,47,255,.18),
               inset 0 1px 0 rgba(255,255,255,.15) !important}

/* alerts */
div[data-testid="stAlert"]{background:rgba(255,50,50,.07) !important;
    border:1px solid rgba(255,50,50,.17) !important;border-radius:12px !important;
    color:rgba(255,140,140,.9) !important;font-size:.82rem !important;padding:12px 16px !important}
</style>

<div class="lp-orb lp-orb-1"></div>
<div class="lp-orb lp-orb-2"></div>
<div class="lp-orb lp-orb-3"></div>
<div class="lp-vrule"></div>
<div class="lp-particles" id="lp-ptcl"></div>
<script>
(function(){
  var c=document.getElementById('lp-ptcl');if(!c)return;
  for(var i=0;i<42;i++){
    var el=document.createElement('div');el.className='lp-p';
    var s=(Math.random()*2+1).toFixed(1)+'px';
    el.style.cssText='left:'+(Math.random()*100)+'vw;width:'+s+';height:'+s+
      ';animation-duration:'+(Math.random()*18+10)+'s'+
      ';animation-delay:'+(Math.random()*22)+'s'+
      ';--dx:'+(Math.random()*130-65)+'px';
    c.appendChild(el);
  }
})();
</script>
""", unsafe_allow_html=True)

    left, right = st.columns([11, 9], gap="small")

    # ── LEFT: brand panel (pure HTML, no Streamlit widgets) ──────────
    with left:
        st.markdown(f"""
<div class="brand-panel">
  <div class="brand-logo">{logo_lg}</div>
  <div class="brand-badge"><span class="bdot"></span>AI-Powered Presales Platform</div>
  <div class="brand-h1">Business Estimation<br>Leveraging Automated Learning</div>
  <div class="brand-desc">
    Generate intelligent proposals, precise cost estimates,<br>
    and risk assessments — powered by multi-model AI<br>
    and historical project intelligence.
  </div>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-icon ic-b">⚡</div>
      <div><div class="stat-val">85% faster proposals</div>
           <div class="stat-desc">Complete SOW generated in minutes, not weeks</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon ic-p">🧠</div>
      <div><div class="stat-val">Multi-model AI engine</div>
           <div class="stat-desc">Best model per task</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon ic-t">📊</div>
      <div><div class="stat-val">RAG-powered accuracy</div>
           <div class="stat-desc">Learns from historical project data for precise estimates</div></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── RIGHT: login card — CSS makes stVerticalBlock the card ───────
    with right:
        # OAuth callback handling — full-screen animated splash
        if _doing_callback:
            st.markdown(f"""
<style>
.sso-splash{{
    position:fixed;inset:0;z-index:9999;
    background:linear-gradient(135deg,#07091c 0%,#0a0f2e 60%,#0d0820 100%);
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    gap:0;
}}
/* ring loader */
.sso-ring{{
    position:relative;width:90px;height:90px;margin-bottom:32px;
}}
.sso-ring svg{{
    position:absolute;inset:0;animation:ringRotate 1.6s linear infinite;
}}
.sso-ring-track{{stroke:rgba(255,255,255,.06);stroke-width:3;fill:none}}
.sso-ring-arc{{
    stroke:url(#ssoGrad);stroke-width:3;fill:none;
    stroke-linecap:round;
    stroke-dasharray:180 283;
    animation:ringDash 1.6s cubic-bezier(.4,0,.2,1) infinite;
}}
@keyframes ringRotate{{to{{transform:rotate(360deg)}}}}
@keyframes ringDash{{
    0%{{stroke-dashoffset:0;opacity:1}}
    50%{{stroke-dashoffset:-80;opacity:.85}}
    100%{{stroke-dashoffset:-180;opacity:1}}
}}
/* ms logo in centre */
.sso-ms{{
    position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
}}
.sso-ms-grid{{
    display:grid;grid-template-columns:1fr 1fr;gap:3px;width:26px;height:26px;
    animation:msBreath 2s ease-in-out infinite;
}}
.sso-ms-grid span{{border-radius:2px}}
@keyframes msBreath{{
    0%,100%{{transform:scale(1);opacity:.9}}
    50%{{transform:scale(1.12);opacity:1}}
}}
/* text block */
.sso-splash-title{{
    font-family:'Inter',system-ui,sans-serif;
    font-size:1.35rem;font-weight:800;letter-spacing:-.4px;
    background:linear-gradient(120deg,#fff 0%,#a8cfff 50%,#c4b5fd 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    margin-bottom:10px;text-align:center;
}}
.sso-splash-sub{{
    font-family:'Inter',system-ui,sans-serif;
    font-size:.82rem;color:rgba(255,255,255,.35);letter-spacing:.3px;
    text-align:center;margin-bottom:40px;
}}
/* step dots */
.sso-steps{{display:flex;flex-direction:column;gap:14px;width:260px}}
.sso-step{{
    display:flex;align-items:center;gap:14px;
    animation:stepFadeIn .5s ease both;
}}
.sso-step:nth-child(1){{animation-delay:.1s}}
.sso-step:nth-child(2){{animation-delay:.55s}}
.sso-step:nth-child(3){{animation-delay:1.0s}}
@keyframes stepFadeIn{{from{{opacity:0;transform:translateX(-12px)}}to{{opacity:1;transform:translateX(0)}}}}
.sso-step-dot{{
    width:8px;height:8px;border-radius:50%;flex-shrink:0;
    animation:dotPulse 1.8s ease-in-out infinite;
}}
.sso-step:nth-child(1) .sso-step-dot{{background:#00b4d8;animation-delay:0s}}
.sso-step:nth-child(2) .sso-step-dot{{background:#7b2fff;animation-delay:.55s}}
.sso-step:nth-child(3) .sso-step-dot{{background:#00c896;animation-delay:1.0s}}
@keyframes dotPulse{{
    0%,100%{{box-shadow:0 0 0 0 rgba(255,255,255,.3)}}
    50%{{box-shadow:0 0 0 5px rgba(255,255,255,0)}}
}}
.sso-step-lbl{{
    font-family:'Inter',system-ui,sans-serif;
    font-size:.78rem;color:rgba(255,255,255,.45);letter-spacing:.2px;
}}
/* orbs (reuse login page ones but re-declare for safety) */
.sso-orb{{position:fixed;border-radius:50%;filter:blur(110px);pointer-events:none;z-index:9998}}
.sso-orb-1{{width:500px;height:500px;background:rgba(0,80,255,.14);top:-160px;left:-160px}}
.sso-orb-2{{width:450px;height:450px;background:rgba(120,30,255,.11);bottom:-150px;right:-100px}}
</style>

<div class="sso-orb sso-orb-1"></div>
<div class="sso-orb sso-orb-2"></div>
<div class="sso-splash">
  <div class="sso-ring">
    <svg viewBox="0 0 90 90" width="90" height="90">
      <defs>
        <linearGradient id="ssoGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stop-color="#0050ff"/>
          <stop offset="50%"  stop-color="#7b2fff"/>
          <stop offset="100%" stop-color="#00c8ff"/>
        </linearGradient>
      </defs>
      <circle class="sso-ring-track" cx="45" cy="45" r="42"/>
      <circle class="sso-ring-arc"   cx="45" cy="45" r="42"/>
    </svg>
    <div class="sso-ms">
      <div class="sso-ms-grid">
        <span style="background:#f25022"></span>
        <span style="background:#7fba00"></span>
        <span style="background:#00a4ef"></span>
        <span style="background:#ffb900"></span>
      </div>
    </div>
  </div>

  <div class="sso-splash-title">Signing you in&hellip;</div>
  <div class="sso-splash-sub">Verifying your Microsoft identity</div>

  <div class="sso-steps">
    <div class="sso-step">
      <div class="sso-step-dot"></div>
      <div class="sso-step-lbl">Exchanging authorisation token</div>
    </div>
    <div class="sso-step">
      <div class="sso-step-dot"></div>
      <div class="sso-step-lbl">Fetching your Microsoft profile</div>
    </div>
    <div class="sso-step">
      <div class="sso-step-dot"></div>
      <div class="sso-step-lbl">Setting up your workspace</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            try:
                result = msal_app.acquire_token_by_authorization_code(
                    st.query_params["code"], scopes=["User.Read"], redirect_uri=_redirect,
                )
                if "access_token" in result:
                    headers = {"Authorization": "Bearer " + result["access_token"]}
                    profile = _requests.get(
                        "https://graph.microsoft.com/v1.0/me", headers=headers
                    ).json()
                    st.session_state["auth_user"]   = profile.get("displayName", "User")
                    st.session_state["auth_email"]  = profile.get("mail") or profile.get("userPrincipalName", "")
                    st.session_state["auth_method"] = "Microsoft SSO"
                    st.session_state["auth_ok"]     = True
                    try:
                        from .database import db_log_activity
                        db_log_activity(
                            st.session_state["auth_email"],
                            st.session_state["auth_user"],
                            "login", "Signed in via Microsoft SSO", "Auth",
                        )
                    except Exception:
                        pass
                    st.query_params.clear()
                    st.rerun()
                else:
                    err_msg = result.get('error_description', result.get('error', 'Unknown'))
                    if "AADSTS500113" in err_msg or "reply address" in err_msg.lower():
                        st.error(
                            f"Azure AD redirect URI mismatch. "
                            f"Add exactly `{_redirect}` as a Redirect URI in your Azure AD app registration "
                            f"(App ID: {_client_id}) under Authentication → Web platform."
                        )
                    else:
                        st.error(f"SSO error: {err_msg}")
            except Exception as ex:
                st.error(f"SSO callback failed: {ex}")

        # Card header + SSO button — ALL in one st.markdown block so the
        # button renders immediately below the header with no gap.
        st.markdown(f"""
{logo_sm}
<div class="card-welcome">Welcome back</div>
<div class="card-title">Sign in</div>
<div class="card-sub">Business Estimation Leveraging Automated Learning</div>
{_sso_html}
""", unsafe_allow_html=True)

        # Admin form — hidden by default, revealed on button click
        show_admin = st.session_state.get("_show_admin_form", False)
        if not show_admin:
            if st.button("🔐  Admin Access", key="_admin_toggle", width="stretch"):
                st.session_state["_show_admin_form"] = True
                st.rerun()
        else:
            st.markdown('<div class="admin-lbl">Admin Credentials</div>', unsafe_allow_html=True)
            with st.form("login_form", clear_on_submit=False):
                username  = st.text_input("Username", placeholder="Enter your username")
                password  = st.text_input("Password", type="password", placeholder="Enter your password")
                login_btn = st.form_submit_button("Sign In →", type="primary", width="stretch")

            if login_btn:
                pw_hash = hashlib.sha256(password.encode()).hexdigest()
                if username.strip() == _ADMIN_USER and pw_hash == _ADMIN_PASS_SHA:
                    st.session_state["auth_ok"]     = True
                    st.session_state["auth_user"]   = "Prabhakar Gupta"
                    st.session_state["auth_email"]  = "admin@eci.com"
                    st.session_state["auth_method"] = "Admin"
                    try:
                        from .database import db_log_activity
                        db_log_activity(
                            "admin@eci.com", "Prabhakar Gupta",
                            "login", "Signed in via Admin credentials", "Auth",
                        )
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")


def check_auth() -> bool:
    """Returns True if user is authenticated. Shows login page otherwise."""
    if st.session_state.get("auth_ok"):
        return True
    _show_login()
    st.stop()
    return False
