# ═══════════════════════════════════════════════════════════════════════
#  LIVE DEMO GENERATOR
# ═══════════════════════════════════════════════════════════════════════

import re
import base64
from datetime import datetime

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict, sc_text
from .ai_clients import (
    AnthropicAI, AzureAI, GeminiAI, QwenAI, VertexAnthropicAI,
    NanoAI, CodexAI, DeepSeekAI,
)
try:
    from .ai_clients import GrokAI
except ImportError:
    GrokAI = None

from .config_loader import get_model_for_feature


def log_agent(name, detail):
    st.session_state.agent_logs.append({"agent": name, "detail": detail, "time": datetime.now().isoformat()})


# ═══════════════════════════════════════════════════════════════════════
#  LIVE DEMO GENERATOR
# ═══════════════════════════════════════════════════════════════════════

_DEMO_CLIENTS = {
    "nano":     NanoAI,          # GPT-5.4-Nano  (Azure AI Foundry)
    "codex":    CodexAI,         # GPT-5.3-Codex (Azure OpenAI)
    "azure":    AzureAI,         # Azure OpenAI  (gpt-4o default)
    "deepseek": DeepSeekAI,      # DeepSeek V3   (Azure AI Foundry)
    "gemini":   GeminiAI,        # Google Gemini
    "qwen":     QwenAI,          # Alibaba Qwen
    "claude":   AnthropicAI,     # Anthropic Claude (needs paid credits)
    "vertex":   VertexAnthropicAI,
}
if GrokAI:
    _DEMO_CLIENTS["grok"] = GrokAI

# Priority order: newest/fastest → most capable → fallback
# Respects routing config but ensures we try all live clients
_DEMO_PRIORITY = ["nano", "codex", "azure", "deepseek", "grok", "gemini", "qwen", "vertex", "claude"]


def _pick_ai_for_raw():
    """Return a live AI client for the live_demo feature.

    Tries the configured provider first, then falls back through _DEMO_PRIORITY
    in order so the demo always generates even when one provider is unavailable.
    """
    configured = get_model_for_feature("live_demo")
    ordered    = [configured] + [k for k in _DEMO_PRIORITY if k != configured]
    for key in ordered:
        cls = _DEMO_CLIENTS.get(key)
        if cls:
            try:
                client = cls.from_session()
                if client and client.is_live:
                    return client
            except Exception:
                continue
    return None


def _build_demo_prompt(se, te, ce, r):
    """Construct the mega-prompt for generating an interactive HTML demo of the ACTUAL SOLUTION."""
    project_type   = safe_str(r.get("project_type", "Enterprise Solution"))
    reqs           = safe_list(se.get("requirements"))[:12]
    tech_stack     = safe_list(se.get("technology_stack"))[:8]
    biz_objectives = safe_list(se.get("business_objectives"))[:5]
    arch_comps     = safe_list((r.get("architecture") or {}).get("components", []))[:8]
    scope_items    = safe_list((r.get("scope") or {}).get("in_scope", []))[:8]
    pain_points    = safe_list(se.get("pain_points", []))[:5]

    req_items = "\n".join(
        f'  - {safe_str(x.get("title","Feature"))}: {safe_str(x.get("description",""))} '
        f'[{safe_str(x.get("type","functional"))} | {safe_str(x.get("complexity","Medium"))} complexity]'
        for x in reqs if isinstance(x, dict)
    ) or "  - Core platform features"

    tech_items  = ", ".join(tech_stack) or "React, Azure, .NET Core, SQL Server"
    biz_items   = "\n".join(f"  - {o}" for o in biz_objectives) or "  - Improve operational efficiency"
    arch_items  = "\n".join(
        f'  - {safe_str(a.get("name","Component"))}: {safe_str(a.get("type","Service"))}'
        for a in arch_comps if isinstance(a, dict)
    ) or "  - Frontend, API Layer, Database, Authentication"
    scope_text  = "\n".join(f"  - {sc_text(s, 'in_scope')}" for s in scope_items) or "  - Core features as per requirements"
    pain_text   = "\n".join(f"  - {p}" for p in pain_points if isinstance(p, str)) or ""

    system = (
        "You are a world-class senior product designer and frontend engineer. "
        "Generate a SINGLE complete self-contained HTML file — a stunning, realistic, interactive UI prototype "
        "of the ACTUAL SOFTWARE PRODUCT. The client will see this and think 'this is exactly what we are getting'. "
        "CRITICAL TECHNICAL RULES:\n"
        "1. ALL screen content must be written as static HTML inside <div id='screen-X'> blocks — NEVER generate screen content with JavaScript.\n"
        "2. JavaScript is ONLY used to toggle which screen is visible (add/remove CSS class 'active').\n"
        "3. The FIRST screen must be visible on page load — its div must have class='screen active' in the HTML.\n"
        "4. NO external CDNs, libraries, or script src tags. Everything inline.\n"
        "5. ALL charts are pure inline SVG drawn directly in HTML.\n"
        "6. Output ONLY raw HTML starting with <!DOCTYPE html>. No markdown, no code fences."
    )

    user = f"""Generate a stunning, complete HTML product demo for this solution.

SOLUTION: {project_type}
TECH STACK: {tech_items}
PAIN POINTS SOLVED: {pain_text or biz_items}
KEY REQUIREMENTS (these become the product features):
{req_items}
ARCHITECTURE: {arch_items}

════════════════════════════════════════════
MANDATORY HTML STRUCTURE — FOLLOW EXACTLY
════════════════════════════════════════════

The file MUST use this exact pattern:

```
<body>
  <!-- Sidebar -->
  <nav id="sidebar">
    <div class="nav-item active" onclick="show('dashboard')">🏠 Dashboard</div>
    <div class="nav-item" onclick="show('screen2')">📋 [Screen 2 Name]</div>
    ... (5-6 screens total)
  </nav>

  <!-- Main content -->
  <main id="main">
    <header>...</header>

    <!-- SCREEN 1: always has class="screen active" so it shows on load -->
    <div id="dashboard" class="screen active">
      [FULL rich HTML content here — KPI cards, SVG charts, tables, data]
    </div>

    <!-- SCREEN 2: class="screen" (hidden until clicked) -->
    <div id="screen2" class="screen">
      [FULL rich HTML content here]
    </div>

    ... all other screens with full content ...
  </main>
</body>

<script>
function show(id) {{
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  event.currentTarget.classList.add('active');
}}
</script>
```

CSS: `.screen {{ display:none }} .screen.active {{ display:block }}`

════════════════════════════════════════════
CONTENT REQUIREMENTS
════════════════════════════════════════════

SCREENS: Design 5-6 screens showing the REAL USER WORKFLOW for {project_type}.
DO NOT show: project costs, team hours, delivery phases, Azure infrastructure, risk matrices.
DO show: the actual UI end-users log into and use every day.

SCREEN 1 (Dashboard — shown on load): Rich overview with:
  - 4 KPI metric cards with real numbers and trend arrows
  - One SVG bar or line chart (200px tall, with labelled axes and real data points)
  - Recent activity feed or summary table (5+ rows of real data)

SCREEN 2-5: Pick the RIGHT screens for {project_type}:
  - List/table view of main entities (with search bar, filter, status badges, action buttons)
  - Detail/form view (realistic form fields, populated with sample data)
  - Analytics view (SVG donut chart + bar chart + metrics)
  - Settings or admin view (toggles, dropdowns, config panels)

REALISTIC DATA: Every field has real domain-specific data.
  - Names, IDs, dates, amounts must look authentic (not "John Doe" / "Item 1")
  - Status badges: coloured pills (green=active, amber=pending, red=critical)
  - Tables: minimum 5-6 rows of varied, realistic records

DESIGN:
  - Background: #0a0e1a, Sidebar: #0d1530, Cards: #111827 with border rgba(255,255,255,0.08)
  - Accent teal: #00d4aa, Purple: #7b61ff, Alert red: #ff6b6b, Warning amber: #ffd166
  - Header bar with product name, user avatar initials circle, live date
  - Cards have hover: translateY(-3px) + teal border glow
  - Sidebar active item: teal left border + teal text + teal background tint
  - Subtle dot-grid CSS background pattern on main area
  - Footer inside each screen: "Powered by ECI · {project_type} · Confidential Preview"

Generate the COMPLETE HTML now. Every screen must have FULL content. Start with <!DOCTYPE html>."""

    return system, user


def generate_live_demo_html(se, te, ce, r) -> "str | None":
    """Call AI to generate the interactive HTML demo. Returns HTML string or None."""
    ai = _pick_ai_for_raw()
    if ai is None:
        return None
    system, user = _build_demo_prompt(se, te, ce, r)
    # Try 16K first; if the provider caps out or times out, retry at 8K then 4K
    raw = None
    for max_tok in (16000, 8000, 4000):
        try:
            raw = ai.call_raw_text(system, user, max_tokens=max_tok)
            if raw:
                break
        except Exception:
            continue
    if not raw:
        return None

    # ── Clean up AI output ────────────────────────────────────────────────
    raw = raw.strip()
    # Strip markdown code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw.strip())

    # Find start of HTML
    for marker in ("<!DOCTYPE", "<!doctype", "<html", "<HTML"):
        idx = raw.find(marker)
        if idx != -1:
            raw = raw[idx:]
            break

    # ── Repair truncated HTML ─────────────────────────────────────────────
    # If the response was cut off mid-generation, close open tags so the
    # browser can still render what was generated.
    raw = _repair_truncated_html(raw)

    return raw if raw.strip() else None


def _repair_truncated_html(html: str) -> str:
    """Close any unclosed tags and ensure the first screen is always visible."""
    # Ensure .screen CSS makes screens hidden by default
    if "display:none" not in html and "display: none" not in html:
        # Inject safety CSS before </head> or at top of body
        safety_css = "<style>.screen{display:none!important}.screen.active{display:block!important}</style>"
        if "</head>" in html:
            html = html.replace("</head>", safety_css + "</head>", 1)
        elif "<body" in html:
            html = re.sub(r"(<body[^>]*>)", r"\1" + safety_css, html, count=1)

    # Make sure the first screen div has class 'active' so it shows on load
    # Pattern: first occurrence of class="screen" → class="screen active"
    if 'class="screen active"' not in html and "class='screen active'" not in html:
        html = re.sub(
            r'(class=["\'])screen(["\'])',
            r'\1screen active\2',
            html, count=1,
        )

    # Close unclosed structural tags if HTML appears truncated
    if "</html>" not in html.lower():
        # Count open vs closed body/html tags
        if "</body>" not in html.lower():
            html += "\n</body>"
        html += "\n</html>"

    return html


def _demo_loading_animation() -> str:
    """Return HTML for the cinematic loading screen shown while AI generates the demo."""
    return """
<style>
@keyframes gradShift {
  0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%}
}
@keyframes pulse { 0%,100%{opacity:.4} 50%{opacity:1} }
@keyframes spin { to{transform:rotate(360deg)} }
@keyframes barFill { from{width:0} to{width:var(--w)} }
@keyframes fadeInUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
.demo-loader {
  background: linear-gradient(135deg,#0a0e27,#0d1b4b,#0a2744);
  background-size: 200% 200%;
  animation: gradShift 4s ease infinite;
  min-height: 520px;
  border-radius: 16px;
  border: 3px solid #00d4aa;
  box-shadow: 0 0 50px rgba(0,212,170,.7), 0 0 100px rgba(0,212,170,.3), inset 0 0 80px rgba(0,212,170,.05);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
  overflow: hidden;
}
.demo-loader::before {
  content:'';
  position:absolute;inset:0;
  background: radial-gradient(circle at 20% 50%, rgba(0,212,170,.08) 0%, transparent 60%),
              radial-gradient(circle at 80% 20%, rgba(123,97,255,.08) 0%, transparent 60%);
}
.loader-ring {
  width:72px;height:72px;
  border:4px solid rgba(0,212,170,.25);
  border-top-color:#00d4aa;
  border-right-color:#7b61ff;
  border-radius:50%;
  animation:spin .8s linear infinite;
  margin-bottom:28px;
  filter: drop-shadow(0 0 12px rgba(0,212,170,.8));
}
.loader-title {
  font-size:1.4rem;font-weight:700;color:#fff;
  letter-spacing:1px;margin-bottom:8px;
  animation:fadeInUp .5s ease;
}
.loader-sub {
  font-size:.85rem;color:rgba(255,255,255,.5);
  margin-bottom:32px;
  animation:fadeInUp .5s ease .1s both;
}
.loader-steps { width:100%;max-width:420px; animation:fadeInUp .5s ease .2s both; }
.loader-step {
  display:flex;align-items:center;gap:12px;
  padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06);
}
.step-icon { font-size:1.1rem;width:24px;text-align:center; }
.step-label { flex:1;font-size:.82rem;color:rgba(255,255,255,.7); }
.step-status { font-size:.75rem;font-weight:600;padding:2px 10px;border-radius:12px; }
.step-done  { background:rgba(0,212,170,.15);color:#00d4aa; }
.step-wip   { background:rgba(123,97,255,.15);color:#7b61ff;animation:pulse 1s infinite; }
.step-wait  { background:rgba(255,255,255,.07);color:rgba(255,255,255,.3); }
.loader-progress {
  width:100%;max-width:420px;margin-top:24px;
  background:rgba(255,255,255,.08);border-radius:8px;height:6px;overflow:hidden;
  animation:fadeInUp .5s ease .3s both;
}
.loader-progress-bar {
  height:100%;background:linear-gradient(90deg,#00d4aa,#7b61ff);
  border-radius:8px;transition:width .5s ease;
}
</style>
<div class="demo-loader">
  <div class="loader-ring"></div>
  <div class="loader-title">🎯 AI is building your solution preview</div>
  <div class="loader-sub">Reading requirements &amp; designing the actual product UI your users will see…</div>
  <div class="loader-steps" id="loaderSteps">
    <div class="loader-step"><span class="step-icon">🔍</span><span class="step-label">Identifying solution type &amp; user workflows</span><span class="step-status step-done">✓ Done</span></div>
    <div class="loader-step"><span class="step-icon">🎨</span><span class="step-label">Designing product screens &amp; navigation</span><span class="step-status step-wip">Building…</span></div>
    <div class="loader-step"><span class="step-icon">📊</span><span class="step-label">Populating domain-specific sample data</span><span class="step-status step-wait">Pending</span></div>
    <div class="loader-step"><span class="step-icon">⚡</span><span class="step-icon">⚡</span><span class="step-label">Wiring interactions &amp; animations</span><span class="step-status step-wait">Pending</span></div>
    <div class="loader-step"><span class="step-icon">🚀</span><span class="step-label">Rendering your interactive product demo</span><span class="step-status step-wait">Pending</span></div>
  </div>
  <div class="loader-progress"><div class="loader-progress-bar" style="width:35%"></div></div>
</div>
"""


# ═══════════════════════════════════════════════════════════════════════
#  CLAUDE AI MASTERPIECE DEMO
# ═══════════════════════════════════════════════════════════════════════

_MASTERPIECE_BASE_CSS = """
:root{
  --bg:#060912;--surf:rgba(12,18,38,.85);--glass:rgba(255,255,255,.03);
  --gb:rgba(255,255,255,.07);--teal:#00d4aa;--purple:#7b61ff;--blue:#00b4d8;
  --amber:#ffd166;--red:#ff6b6b;--green:#06d6a0;--pink:#f72585;
  --txt:#e2e8f0;--muted:#64748b;--sw:220px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt);overflow:hidden}
body{display:grid;grid-template-columns:var(--sw) 1fr;grid-template-rows:54px 1fr;height:100vh}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(ellipse 60% 60% at 15% 15%,rgba(123,97,255,.13) 0,transparent 70%),
    radial-gradient(ellipse 50% 50% at 85% 85%,rgba(0,212,170,.10) 0,transparent 70%),
    radial-gradient(ellipse 40% 40% at 50% 50%,rgba(0,180,216,.06) 0,transparent 70%)}
body::after{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:radial-gradient(rgba(255,255,255,.035) 1px,transparent 1px);background-size:26px 26px}

/* HEADER */
#hdr{grid-column:1/-1;grid-row:1;z-index:20;position:relative;
  background:rgba(6,9,18,.92);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border-bottom:1px solid var(--gb);display:flex;align-items:center;padding:0 18px;gap:14px}
.logo{font-size:1rem;font-weight:900;background:linear-gradient(135deg,var(--teal),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  letter-spacing:-.5px;white-space:nowrap;flex-shrink:0}
.hdr-prod{font-size:.8rem;font-weight:600;color:var(--muted);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.srch{background:var(--glass);border:1px solid var(--gb);border-radius:18px;
  padding:5px 13px;font-size:.75rem;color:var(--txt);width:190px;outline:none;
  transition:border .2s,box-shadow .2s}
.srch:focus{border-color:var(--teal);box-shadow:0 0 0 2px rgba(0,212,170,.14)}
.srch::placeholder{color:var(--muted)}
.hdr-btns{display:flex;align-items:center;gap:8px;flex-shrink:0}
.icon-btn{width:30px;height:30px;border-radius:50%;background:var(--glass);border:1px solid var(--gb);
  display:flex;align-items:center;justify-content:center;cursor:pointer;position:relative;transition:all .2s;font-size:.9rem}
.icon-btn:hover{border-color:var(--teal);background:rgba(0,212,170,.1)}
.badge-dot{position:absolute;top:3px;right:3px;width:7px;height:7px;border-radius:50%;background:var(--red);border:1.5px solid var(--bg)}
.hdr-date{font-size:.7rem;color:var(--muted);white-space:nowrap}
.av{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,var(--purple),var(--teal));
  display:flex;align-items:center;justify-content:center;font-size:.68rem;font-weight:800;color:#fff;cursor:pointer}

/* SIDEBAR */
#sb{grid-row:2;z-index:10;position:relative;background:rgba(8,13,26,.96);
  backdrop-filter:blur(20px);border-right:1px solid var(--gb);
  padding:12px 8px;overflow-y:auto;display:flex;flex-direction:column;gap:2px;scrollbar-width:none}
#sb::-webkit-scrollbar{display:none}
.sb-sec{font-size:.6rem;font-weight:700;color:var(--muted);letter-spacing:1.5px;
  text-transform:uppercase;padding:10px 10px 4px;margin-top:4px}
.ni{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:9px;
  cursor:pointer;transition:all .18s;font-size:.79rem;font-weight:500;color:var(--muted);
  border:1px solid transparent;white-space:nowrap;position:relative}
.ni:hover{background:rgba(255,255,255,.04);color:var(--txt);border-color:var(--gb)}
.ni.active{background:rgba(0,212,170,.09);border-color:rgba(0,212,170,.22);color:var(--teal);font-weight:700}
.ni.active::before{content:'';position:absolute;left:-8px;top:50%;transform:translateY(-50%);
  width:3px;height:65%;border-radius:2px;background:var(--teal)}
.ni .ico{font-size:.95rem;width:18px;text-align:center;flex-shrink:0}
.nb{margin-left:auto;font-size:.58rem;font-weight:700;padding:2px 6px;border-radius:8px}
.nb-red{background:rgba(255,107,107,.18);color:var(--red)}
.nb-teal{background:rgba(0,212,170,.15);color:var(--teal);border:1px solid rgba(0,212,170,.25)}
.sb-footer{margin-top:auto;padding:10px;border-top:1px solid var(--gb);
  font-size:.68rem;color:var(--muted);text-align:center;line-height:1.5}

/* MAIN */
#main{grid-row:2;z-index:1;overflow-y:auto;padding:18px 20px;
  display:flex;flex-direction:column;gap:14px;scrollbar-width:thin;scrollbar-color:var(--gb) transparent}

/* SCREENS */
.sc{display:none}
.sc.active{display:flex;flex-direction:column;gap:14px;animation:fadeUp .28s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

/* PAGE HEADER */
.ph{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.ph-l .ph-title{font-size:1.25rem;font-weight:800;color:var(--txt)}
.ph-l .ph-sub{font-size:.75rem;color:var(--muted);margin-top:3px}
.ph-r{display:flex;gap:8px;align-items:center;flex-shrink:0}

/* BUTTONS */
.btn{padding:6px 14px;border-radius:8px;font-size:.75rem;font-weight:600;cursor:pointer;
  border:none;transition:all .2s;display:inline-flex;align-items:center;gap:5px}
.btn-p{background:var(--teal);color:#000}
.btn-p:hover{filter:brightness(1.12);transform:translateY(-1px)}
.btn-g{background:var(--glass);border:1px solid var(--gb);color:var(--txt)}
.btn-g:hover{border-color:var(--teal);background:rgba(0,212,170,.07)}
.btn-purple{background:rgba(123,97,255,.15);border:1px solid rgba(123,97,255,.3);color:var(--purple)}
.btn-purple:hover{background:rgba(123,97,255,.25)}

/* KPI CARDS */
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi{background:var(--glass);border:1px solid var(--gb);border-radius:13px;padding:16px;
  position:relative;overflow:hidden;transition:all .22s;cursor:default}
.kpi::after{content:'';position:absolute;inset:0;opacity:0;transition:opacity .22s;
  background:radial-gradient(ellipse at 50% 0%,rgba(var(--cr),.08) 0,transparent 70%)}
.kpi:hover{transform:translateY(-3px);border-color:rgb(var(--cr));box-shadow:0 6px 28px rgba(var(--cr),.14)}
.kpi:hover::after{opacity:1}
.kpi-ico{width:36px;height:36px;border-radius:9px;
  background:rgba(var(--cr),.12);border:1px solid rgba(var(--cr),.25);
  display:flex;align-items:center;justify-content:center;font-size:1rem;margin-bottom:12px}
.kpi-val{font-size:1.6rem;font-weight:900;line-height:1;margin-bottom:3px}
.kpi-lbl{font-size:.68rem;color:var(--muted);font-weight:600;letter-spacing:.3px;text-transform:uppercase}
.kpi-tr{display:flex;align-items:center;gap:4px;font-size:.7rem;font-weight:700;margin-top:7px}
.up{color:var(--green)} .dn{color:var(--red)}

/* CARDS */
.card{background:var(--glass);border:1px solid var(--gb);border-radius:13px;padding:16px}
.ch{display:flex;align-items:center;justify-content:space-between;margin-bottom:13px}
.ct{font-size:.87rem;font-weight:700;color:var(--txt)}
.cs{font-size:.7rem;color:var(--muted)}

/* TABLE */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{font-size:.64rem;font-weight:700;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;
  padding:8px 12px;text-align:left;border-bottom:1px solid var(--gb);white-space:nowrap}
td{padding:10px 12px;font-size:.79rem;color:var(--txt);border-bottom:1px solid rgba(255,255,255,.03)}
tr:hover td{background:rgba(255,255,255,.025)}
tr:last-child td{border-bottom:none}

/* BADGES */
.bdg{display:inline-flex;align-items:center;gap:4px;font-size:.64rem;font-weight:700;
  padding:3px 9px;border-radius:20px;white-space:nowrap}
.bdg::before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor}
.g{background:rgba(6,214,160,.1);color:#06d6a0;border:1px solid rgba(6,214,160,.22)}
.a{background:rgba(255,209,102,.1);color:#ffd166;border:1px solid rgba(255,209,102,.22)}
.r{background:rgba(255,107,107,.1);color:#ff6b6b;border:1px solid rgba(255,107,107,.22)}
.b{background:rgba(0,180,216,.1);color:#00b4d8;border:1px solid rgba(0,180,216,.22)}
.p{background:rgba(123,97,255,.1);color:#7b61ff;border:1px solid rgba(123,97,255,.22)}

/* SECTION LABEL */
.slbl{font-size:.67rem;font-weight:700;color:var(--muted);letter-spacing:1.2px;text-transform:uppercase;
  display:flex;align-items:center;gap:8px;margin-bottom:8px}
.slbl::after{content:'';flex:1;height:1px;background:var(--gb)}

/* ACTIVITY */
.af{display:flex;flex-direction:column;gap:0}
.ai-item{display:flex;align-items:flex-start;gap:9px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.035)}
.ai-item:last-child{border-bottom:none}
.ad{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:5px}
.ad.live{animation:lp 2s infinite}
@keyframes lp{0%,100%{box-shadow:0 0 0 0 currentColor}60%{box-shadow:0 0 0 5px transparent}}
.ai-txt{font-size:.77rem;color:var(--txt);line-height:1.4}
.ai-meta{font-size:.67rem;color:var(--muted);margin-top:2px}

/* SEARCH BAR */
.search-row{display:flex;align-items:center;gap:8px}
.sbar{display:flex;align-items:center;gap:7px;background:var(--glass);
  border:1px solid var(--gb);border-radius:9px;padding:7px 12px;flex:1}
.sbar input{background:none;border:none;outline:none;color:var(--txt);font-size:.79rem;flex:1}
.sbar input::placeholder{color:var(--muted)}

/* FORMS */
.fg{margin-bottom:14px}
.fl{font-size:.68rem;font-weight:700;color:var(--muted);letter-spacing:.4px;
  text-transform:uppercase;margin-bottom:5px;display:block}
.fi,.fsel,.fta{width:100%;background:rgba(255,255,255,.04);border:1px solid var(--gb);
  border-radius:8px;padding:8px 12px;color:var(--txt);font-size:.8rem;
  outline:none;transition:all .18s;font-family:inherit}
.fi:focus,.fsel:focus,.fta:focus{border-color:var(--teal);box-shadow:0 0 0 2px rgba(0,212,170,.12)}
.fsel option{background:#0c1226}
.fta{min-height:80px;resize:vertical}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}

/* TOGGLES */
.trow{display:flex;align-items:center;justify-content:space-between;
  padding:12px 0;border-bottom:1px solid rgba(255,255,255,.04)}
.trow:last-child{border-bottom:none}
.tinfo .tlbl{font-size:.82rem;color:var(--txt);font-weight:600}
.tinfo .tdesc{font-size:.7rem;color:var(--muted);margin-top:2px}
.tgl{position:relative;width:38px;height:20px;flex-shrink:0}
.tgl input{opacity:0;width:0;height:0}
.ts{position:absolute;inset:0;background:rgba(255,255,255,.12);border-radius:20px;cursor:pointer;transition:.25s}
.ts::before{content:'';position:absolute;width:14px;height:14px;border-radius:50%;
  background:#fff;top:3px;left:3px;transition:.25s}
.tgl input:checked+.ts{background:var(--teal)}
.tgl input:checked+.ts::before{transform:translateX(18px)}

/* GRIDS */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.g2-3{display:grid;grid-template-columns:2fr 3fr;gap:12px}

/* PROGRESS */
.pbar{height:5px;border-radius:3px;background:rgba(255,255,255,.07);overflow:hidden;margin-top:5px}
.pbf{height:100%;border-radius:3px;transition:width 1.2s cubic-bezier(.4,0,.2,1)}

/* KANBAN */
.kb{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;overflow-x:auto}
.kb-col{background:rgba(255,255,255,.025);border:1px solid var(--gb);border-radius:11px;padding:12px;min-height:300px}
.kb-hdr{font-size:.72rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;
  padding-bottom:10px;border-bottom:1px solid var(--gb);display:flex;align-items:center;justify-content:space-between}
.kb-cnt{font-size:.65rem;background:rgba(255,255,255,.07);padding:1px 7px;border-radius:9px;color:var(--txt)}
.kb-card{background:var(--surf);border:1px solid var(--gb);border-radius:9px;padding:10px;margin-top:9px;
  transition:all .18s;cursor:pointer}
.kb-card:hover{border-color:var(--teal);transform:translateY(-2px)}
.kb-tag{font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:8px;
  background:rgba(0,212,170,.1);color:var(--teal);border:1px solid rgba(0,212,170,.2);margin-bottom:6px;display:inline-block}
.kb-title{font-size:.77rem;color:var(--txt);line-height:1.4;margin-bottom:6px}
.kb-meta{font-size:.67rem;color:var(--muted);display:flex;align-items:center;justify-content:space-between}

/* AI CHAT */
.chat-wrap{display:flex;flex-direction:column;height:380px}
.chat-msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;scrollbar-width:thin}
.cm{padding:9px 13px;border-radius:11px;font-size:.77rem;line-height:1.55;max-width:85%}
.cm-ai{background:rgba(0,212,170,.07);border:1px solid rgba(0,212,170,.15);align-self:flex-start;color:var(--txt)}
.cm-user{background:rgba(123,97,255,.13);border:1px solid rgba(123,97,255,.25);align-self:flex-end;color:var(--txt)}
.cm-typing{align-self:flex-start;padding:10px 14px}
.cm-typing span{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--teal);
  animation:bounce .8s infinite;margin:0 2px}
.cm-typing span:nth-child(2){animation-delay:.15s}
.cm-typing span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-7px)}}
.chat-input-row{display:flex;gap:8px;padding:12px;border-top:1px solid var(--gb)}
.chat-inp{flex:1;background:rgba(255,255,255,.04);border:1px solid var(--gb);border-radius:9px;
  padding:8px 12px;font-size:.78rem;color:var(--txt);outline:none;font-family:inherit}
.chat-inp:focus{border-color:var(--teal)}
.chat-send{background:linear-gradient(135deg,var(--teal),var(--purple));border:none;
  border-radius:9px;padding:8px 14px;font-size:.78rem;font-weight:700;color:#fff;cursor:pointer}

/* METRIC GAUGE */
.gauge-row{display:flex;gap:14px;flex-wrap:wrap;justify-content:center}
.gauge{text-align:center;min-width:100px}
.gauge-val{font-size:1.4rem;font-weight:900;line-height:1}
.gauge-lbl{font-size:.68rem;color:var(--muted);margin-top:4px}

/* TOAST */
#toast-c{position:fixed;bottom:16px;right:16px;z-index:9999;
  display:flex;flex-direction:column;gap:7px;pointer-events:none}
.toast{background:rgba(10,16,32,.97);backdrop-filter:blur(20px);
  border:1px solid var(--gb);border-radius:11px;padding:10px 14px;
  display:flex;align-items:center;gap:9px;font-size:.76rem;color:var(--txt);
  min-width:240px;animation:toastIn .28s ease;box-shadow:0 8px 32px rgba(0,0,0,.5)}
@keyframes toastIn{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}
.t-ico{font-size:.95rem;flex-shrink:0}
.t-ttl{font-weight:700;font-size:.78rem}
.t-msg{color:var(--muted);font-size:.7rem;margin-top:1px}

/* LIVE PULSE */
.live{display:inline-flex;align-items:center;gap:5px;font-size:.66rem;font-weight:700;color:var(--green)}
.live-d{width:6px;height:6px;border-radius:50%;background:var(--green);animation:lp 1.5s infinite}

/* FOOTER */
.scftr{font-size:.64rem;color:var(--muted);text-align:center;padding:10px 0 2px;border-top:1px solid var(--gb);margin-top:auto}
"""

_MASTERPIECE_JS = """
function show(id,el){
  document.querySelectorAll('.sc').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(el)el.classList.add('active');
  else{var ni=document.querySelector('[data-sc="'+id+'"]');if(ni)ni.classList.add('active');}
  animateCounters();
}
function animateCounters(){
  document.querySelectorAll('.sc.active [data-n]').forEach(el=>{
    var t=parseFloat(el.dataset.n),sf=el.dataset.sf||'',pf=el.dataset.pf||'',cur=0,step=t/45;
    var tm=setInterval(()=>{
      cur=Math.min(cur+step,t);
      el.textContent=pf+(Number.isInteger(t)?Math.round(cur):cur.toFixed(1))+sf;
      if(cur>=t)clearInterval(tm);
    },18);
  });
}
function toast(ico,ttl,msg,col){
  var c=document.getElementById('toast-c');if(!c)return;
  var d=document.createElement('div');d.className='toast';
  d.innerHTML='<span class="t-ico">'+ico+'</span><div><div class="t-ttl" style="color:'+(col||'var(--teal)')+'">'+ttl+'</div><div class="t-msg">'+msg+'</div></div>';
  c.appendChild(d);
  setTimeout(()=>{d.style.animation='toastIn .25s ease reverse';setTimeout(()=>d.remove(),260);},3200);
}
function chatSend(){
  var inp=document.getElementById('chat-inp'),val=inp.value.trim();
  if(!val)return;
  var msgs=document.getElementById('chat-msgs');
  var um=document.createElement('div');um.className='cm cm-user';um.textContent=val;
  msgs.appendChild(um);
  inp.value='';
  var typing=document.createElement('div');typing.className='cm cm-typing';
  typing.innerHTML='<span></span><span></span><span></span>';
  msgs.appendChild(typing);
  msgs.scrollTop=msgs.scrollHeight;
  var replies=[
    'Based on the current data, I can see a strong upward trend in the key metrics. Would you like me to generate a detailed report?',
    'I\'ve analysed the records and identified 3 areas requiring attention. Shall I prioritise them by impact?',
    'The data shows a 23% improvement compared to last quarter. Here\'s what\'s driving the change...',
    'I found 2 anomalies in recent entries that might need review. Want me to highlight them?',
    'Great question. The pattern suggests an optimisation opportunity that could save approximately 15-20% of processing time.',
  ];
  setTimeout(()=>{
    typing.remove();
    var am=document.createElement('div');am.className='cm cm-ai';
    am.textContent=replies[Math.floor(Math.random()*replies.length)];
    msgs.appendChild(am);msgs.scrollTop=msgs.scrollHeight;
  },1200);
}
document.addEventListener('keydown',function(e){if(e.key==='Enter'&&document.activeElement&&document.activeElement.id==='chat-inp')chatSend();});
window.addEventListener('load',function(){
  animateCounters();
  setTimeout(()=>toast('✅','System Online','All modules connected and running','var(--green)'),800);
  setTimeout(()=>toast('📊','Data Sync','Latest records synchronised successfully'),2500);
});
"""


def _build_claude_masterpiece_prompt(se, te, ce, r):
    """Build the mega-prompt for Claude to generate a masterpiece live demo."""
    project_type   = safe_str(r.get("project_type","Enterprise Solution"))
    reqs           = safe_list(se.get("requirements"))[:14]
    tech_stack     = safe_list(se.get("technology_stack"))[:8]
    biz_objectives = safe_list(se.get("business_objectives"))[:5]
    arch_comps     = safe_list((r.get("architecture") or {}).get("components",[]))[:8]
    scope_items    = safe_list((r.get("scope") or {}).get("in_scope",[]))[:8]
    pain_points    = safe_list(se.get("pain_points",[]))[:5]
    client_name    = st.session_state.get("proposal_client_name","") or "Client"

    req_items = "\n".join(
        f'  - {safe_str(x.get("title","Feature"))}: {safe_str(x.get("description","")[:80])} [{safe_str(x.get("type","functional"))} | {safe_str(x.get("complexity","Medium"))}]'
        for x in reqs if isinstance(x, dict)
    ) or "  - Core platform features"

    tech_str  = ", ".join(tech_stack) or "React, Azure, .NET Core, SQL"
    biz_str   = "\n".join(f"  - {o}" for o in biz_objectives) or "  - Improve operational efficiency"
    arch_str  = "\n".join(f'  - {safe_str(a.get("name",""))}' for a in arch_comps if isinstance(a, dict)) or "  - Frontend, API, DB"
    scope_str = "\n".join(f"  - {sc_text(s, 'in_scope')}" for s in scope_items) or "  - Core features"
    pain_str  = "\n".join(f"  - {p}" for p in pain_points if isinstance(p, str)) or biz_str

    system = f"""You are a world-class senior UI engineer. Generate a SINGLE complete self-contained HTML file — a cinematic, stunning, interactive product demo of the ACTUAL SOFTWARE, using a fixed CSS design system provided below.

CRITICAL RULES:
1. Return ONLY raw HTML starting with <!DOCTYPE html>. No markdown, no code fences, no explanation.
2. PASTE THE FULL CSS below verbatim into <style> — do NOT invent new layout CSS.
3. Screen content is written as static HTML inside <div id="SCREENID" class="sc"> blocks.
4. The FIRST screen must have class="sc active" in HTML.
5. JavaScript ONLY toggles screens — all content is pre-rendered HTML.
6. Zero external scripts, fonts, CDN links. Fully self-contained.
7. ALL charts must be pure inline SVG drawn as <svg> elements directly in HTML.
8. Every screen must have FULL, RICH content — domain-specific realistic data, no placeholders.

USE THIS EXACT CSS VERBATIM inside <style>:
{_MASTERPIECE_BASE_CSS}

USE THIS EXACT JAVASCRIPT verbatim (add your activity arrays + domain data):
{_MASTERPIECE_JS}

HTML SKELETON — FILL EVERY SECTION:
```
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PRODUCT_NAME — Live Demo</title>
<style>PASTE_FULL_CSS_HERE</style></head>
<body>

<!-- HEADER -->
<header id="hdr">
  <div class="logo">ECI⁺</div>
  <div class="hdr-prod">PRODUCT_NAME &nbsp;·&nbsp; <span class="live"><span class="live-d"></span>LIVE</span></div>
  <input class="srch" placeholder="⌕  Search…">
  <div class="hdr-btns">
    <div class="icon-btn">🔔<div class="badge-dot"></div></div>
    <div class="icon-btn">⚙️</div>
    <div class="hdr-date" id="hdr-date"></div>
    <div class="av">JS</div>
  </div>
</header>

<!-- SIDEBAR -->
<nav id="sb">
  <div class="sb-sec">MAIN</div>
  <div class="ni active" data-sc="s1" onclick="show('s1',this)"><span class="ico">🏠</span>Dashboard</div>
  <div class="ni" data-sc="s2" onclick="show('s2',this)"><span class="ico">📋</span>SCREEN2_NAME <span class="nb nb-red">N</span></div>
  <div class="ni" data-sc="s3" onclick="show('s3',this)"><span class="ico">📊</span>SCREEN3_NAME</div>
  <div class="ni" data-sc="s4" onclick="show('s4',this)"><span class="ico">🤖</span>AI Assistant</div>
  <div class="sb-sec">MANAGE</div>
  <div class="ni" data-sc="s5" onclick="show('s5',this)"><span class="ico">📁</span>SCREEN5_NAME</div>
  <div class="ni" data-sc="s6" onclick="show('s6',this)"><span class="ico">🔗</span>SCREEN6_NAME</div>
  <div class="sb-sec">SYSTEM</div>
  <div class="ni" data-sc="s7" onclick="show('s7',this)"><span class="ico">📈</span>Reports</div>
  <div class="ni" data-sc="s8" onclick="show('s8',this)"><span class="ico">⚙️</span>Settings</div>
  <div class="sb-footer">Powered by ECI · {project_type}<br>© 2026 ECI</div>
</nav>

<!-- MAIN CONTENT -->
<main id="main">

<!-- SCREEN 1: DASHBOARD (visible on load) -->
<div id="s1" class="sc active">
  <!-- page header -->
  <div class="ph"><div class="ph-l"><div class="ph-title">Dashboard</div><div class="ph-sub">FILL domain-specific subtitle</div></div>
    <div class="ph-r"><button class="btn btn-g">📥 Export</button><button class="btn btn-p">＋ New</button></div></div>

  <!-- 4 KPI cards — use data-n="NUMBER" data-sf="SUFFIX" for animated counter -->
  <div class="kpi-row">
    <div class="kpi" style="--cr:0,212,170">
      <div class="kpi-ico" style="color:var(--teal)">📦</div>
      <div class="kpi-val" data-n="FILL_NUMBER" data-sf="FILL_SUFFIX">0</div>
      <div class="kpi-lbl">FILL_LABEL</div>
      <div class="kpi-tr up">↑ FILL% vs last month</div>
    </div>
    <!-- 3 more KPI cards with --cr:123,97,255 / --cr:0,180,216 / --cr:255,209,102 -->
  </div>

  <!-- Row: SVG chart + activity feed -->
  <div class="g2">
    <div class="card">
      <div class="ch"><div class="ct">FILL Chart Title</div><div class="cs">Last 6 months</div></div>
      <!-- FILL: Pure inline SVG bar chart 260px tall, 6 bars with labels, Y-axis, domain data -->
      <svg viewBox="0 0 360 180" style="width:100%;height:180px">...</svg>
    </div>
    <div class="card">
      <div class="ch"><div class="ct">Live Activity</div><div class="live"><span class="live-d"></span>Real-time</div></div>
      <div class="af" id="af1">
        <!-- 6 activity items: <div class="ai-item"><span class="ad live" style="background:COLOR;color:COLOR"></span>... -->
      </div>
    </div>
  </div>

  <!-- Bottom row: summary table + donut SVG -->
  <div class="g2">
    <div class="card">
      <div class="ch"><div class="ct">FILL Table Title</div></div>
      <table class="tbl">
        <thead><tr><th>COL1</th><th>COL2</th><th>STATUS</th><th>VALUE</th></tr></thead>
        <tbody><!-- 5 rows of domain-specific data with badges --></tbody>
      </table>
    </div>
    <div class="card">
      <div class="ch"><div class="ct">FILL Insight Title</div></div>
      <!-- SVG donut + metric breakdown with pbar elements -->
    </div>
  </div>
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 2: MAIN ENTITY LIST (data table with search) -->
<div id="s2" class="sc">
  <!-- FILL: Complete list view with search bar, filter buttons, rich table (7 rows), status badges, action buttons -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 3: ANALYTICS -->
<div id="s3" class="sc">
  <!-- FILL: Analytics with 3 KPIs, SVG line chart (multi-series), SVG donut chart, trend breakdown table -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 4: AI ASSISTANT -->
<div id="s4" class="sc">
  <!-- FILL: AI chat interface using .chat-wrap/.chat-msgs/.cm-ai/.cm-user structure.
       Pre-populate with 5 realistic Q&A exchanges about this {project_type}.
       Include chat-input-row with id="chat-inp" and onclick="chatSend()" button.
       Also add 3 quick-prompt suggestion chips above the chat. -->
  <div class="scftr">Powered by ECI · {project_type} · AI-Powered</div>
</div>

<!-- SCREEN 5: WORKFLOW / KANBAN -->
<div id="s5" class="sc">
  <!-- FILL: Kanban board with 4 columns (Backlog/In Progress/Review/Done) using .kb/.kb-col/.kb-card structure.
       Each column has 3-4 realistic cards with tags, titles, avatar initials, progress bars. -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 6: DETAIL / FORM VIEW -->
<div id="s6" class="sc">
  <!-- FILL: Detail/form view with 2-column layout. Left: summary card with key stats and activity timeline.
       Right: edit form using .fg/.fl/.fi/.fsel/.fta with realistic pre-filled values relevant to {project_type}.
       Include Save and Cancel buttons at bottom. -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 7: REPORTS -->
<div id="s7" class="sc">
  <!-- FILL: Reports page with 3 report template cards (different types: summary, detailed, executive).
       Each card has a mini SVG chart thumbnail, description, last generated date, and Download/Generate buttons.
       Bottom: recent exports table with filename, type, date, size, status badge. -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

<!-- SCREEN 8: SETTINGS -->
<div id="s8" class="sc">
  <!-- FILL: Settings page with 3 sections: General (3 toggles), Notifications (3 toggles), Integrations (3 toggles).
       Use .trow/.tinfo/.tgl structure. Add a team members section below with avatar+name+role+badge table. -->
  <div class="scftr">Powered by ECI · {project_type} · Confidential Preview</div>
</div>

</main>

<!-- TOAST CONTAINER -->
<div id="toast-c"></div>

<script>
PASTE_JS_HERE
// Add: domain-specific activities array for setInterval live feed
// Add: document.getElementById('hdr-date').textContent = new Date().toLocaleString()
// setInterval(() => {{ add new activity to #af1 }}, 5000)
</script>
</body></html>
```"""

    user = f"""Generate the complete Claude AI Masterpiece demo for this solution. Fill EVERY placeholder with world-class domain-specific content.

PROJECT: {project_type}
CLIENT: {client_name}
TECH STACK: {tech_str}
PAIN POINTS: {pain_str}
KEY REQUIREMENTS:
{req_items}
ARCHITECTURE COMPONENTS: {arch_str}
BUSINESS OBJECTIVES:
{biz_str}

CRITICAL:
- Replace ALL FILL/SCREEN*/PRODUCT_NAME/COL* with content specific to {project_type}
- Every KPI must have real domain numbers (not 0 or placeholder)
- SVG charts: draw REAL bars/lines with actual data — no empty SVGs
- AI Assistant (Screen 4): 5 pre-filled realistic Q&A exchanges relevant to {project_type}
- Kanban (Screen 5): domain-specific task names, not generic "Task 1"
- Activity feed must show domain-specific events (not "User logged in")
- Toast messages must reference actual {project_type} features
- The demo should look like a real, production-grade product the client will use daily

Return ONLY the complete HTML. Start with <!DOCTYPE html>. End with </html>."""

    return system, user


def generate_claude_masterpiece_html(se, te, ce, r) -> "str | None":
    """Generate the Claude AI Masterpiece demo exclusively via Anthropic Claude.

    Returns complete self-contained HTML or None on failure.
    """
    ant = AnthropicAI.from_session()
    if not ant or not ant.is_live:
        return None

    system, user = _build_claude_masterpiece_prompt(se, te, ce, r)

    raw = None
    for max_tok in (16000, 8000):
        try:
            raw = ant._make_request(system, user, max_tokens=max_tok, timeout=360)
            if raw:
                break
        except Exception:
            continue

    if not raw:
        return None

    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw.strip())

    for marker in ("<!DOCTYPE", "<!doctype", "<html", "<HTML"):
        idx = raw.find(marker)
        if idx != -1:
            raw = raw[idx:]
            break

    raw = _repair_truncated_html(raw)
    return raw if raw.strip() else None


def _masterpiece_loading_animation() -> str:
    return """
<style>
@keyframes gradShiftM{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes spinM{to{transform:rotate(360deg)}}
@keyframes pulseM{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes fadeUpM{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
@keyframes particleFloat{0%,100%{transform:translateY(0) rotate(0deg);opacity:.6}50%{transform:translateY(-20px) rotate(180deg);opacity:1}}
.mp-loader{
  background:linear-gradient(135deg,#0d0a2e,#0a0e27,#0d1040,#080a22);
  background-size:400% 400%;animation:gradShiftM 5s ease infinite;
  min-height:560px;border-radius:16px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:48px;position:relative;overflow:hidden;
  border:3px solid #7b61ff;
  box-shadow:0 0 55px rgba(123,97,255,.75),0 0 110px rgba(123,97,255,.35),inset 0 0 80px rgba(123,97,255,.05);
}
.mp-loader::before{content:'';position:absolute;inset:0;
  background:radial-gradient(circle at 25% 40%,rgba(123,97,255,.12) 0,transparent 55%),
             radial-gradient(circle at 75% 60%,rgba(0,212,170,.09) 0,transparent 55%);
  pointer-events:none}
.mp-particles{position:absolute;inset:0;pointer-events:none}
.mp-p{position:absolute;width:4px;height:4px;border-radius:50%;
  animation:particleFloat 4s ease-in-out infinite}
.mp-ring-outer{width:88px;height:88px;border-radius:50%;position:relative;margin-bottom:32px}
.mp-ring-outer::before{content:'';position:absolute;inset:0;border-radius:50%;
  border:4px solid rgba(123,97,255,.25);border-top-color:#7b61ff;
  animation:spinM .7s linear infinite;filter:drop-shadow(0 0 8px rgba(123,97,255,.9))}
.mp-ring-outer::after{content:'';position:absolute;inset:8px;border-radius:50%;
  border:3px solid rgba(0,212,170,.25);border-bottom-color:#00d4aa;
  animation:spinM 1.1s linear infinite reverse;filter:drop-shadow(0 0 6px rgba(0,212,170,.8))}
.mp-ring-inner{position:absolute;inset:20px;border-radius:50%;
  background:linear-gradient(135deg,rgba(123,97,255,.15),rgba(0,212,170,.15));
  display:flex;align-items:center;justify-content:center;font-size:1.3rem}
.mp-title{font-size:1.35rem;font-weight:800;color:#fff;letter-spacing:.5px;
  margin-bottom:6px;text-align:center;animation:fadeUpM .5s ease}
.mp-title span{background:linear-gradient(90deg,#00d4aa,#7b61ff,#00b4d8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.mp-sub{font-size:.82rem;color:rgba(255,255,255,.45);margin-bottom:36px;text-align:center;
  max-width:400px;line-height:1.6;animation:fadeUpM .5s ease .08s both}
.mp-steps{width:100%;max-width:440px;animation:fadeUpM .5s ease .16s both}
.mp-step{display:flex;align-items:center;gap:14px;padding:11px 0;
  border-bottom:1px solid rgba(255,255,255,.05)}
.mp-step:last-child{border-bottom:none}
.ms-ico{font-size:1.05rem;width:26px;text-align:center}
.ms-lbl{flex:1;font-size:.79rem;color:rgba(255,255,255,.65)}
.ms-st{font-size:.7rem;font-weight:700;padding:3px 11px;border-radius:12px}
.ms-done{background:rgba(0,212,170,.12);color:#00d4aa}
.ms-wip{background:rgba(123,97,255,.12);color:#7b61ff;animation:pulseM 1s infinite}
.ms-wait{background:rgba(255,255,255,.06);color:rgba(255,255,255,.28)}
.mp-bar{width:100%;max-width:440px;height:5px;border-radius:3px;
  background:rgba(255,255,255,.07);margin-top:28px;overflow:hidden;animation:fadeUpM .5s ease .24s both}
.mp-bar-fill{height:100%;border-radius:3px;width:18%;
  background:linear-gradient(90deg,#7b61ff,#00d4aa,#00b4d8);
  background-size:200%;animation:gradShiftM 2s linear infinite}
.mp-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(123,97,255,.1);
  border:1px solid rgba(123,97,255,.25);border-radius:20px;padding:4px 14px;
  font-size:.68rem;font-weight:700;color:#7b61ff;letter-spacing:1px;
  margin-bottom:22px;animation:fadeUpM .4s ease .04s both}
</style>
<div class="mp-loader">
  <div class="mp-particles">
    <div class="mp-p" style="left:10%;top:20%;background:#7b61ff;animation-delay:0s;animation-duration:3.5s"></div>
    <div class="mp-p" style="left:85%;top:15%;background:#00d4aa;animation-delay:.8s;animation-duration:4.2s"></div>
    <div class="mp-p" style="left:30%;top:75%;background:#00b4d8;animation-delay:1.5s;animation-duration:3.8s"></div>
    <div class="mp-p" style="left:70%;top:70%;background:#7b61ff;animation-delay:.4s;animation-duration:4.5s"></div>
    <div class="mp-p" style="left:55%;top:10%;background:#ffd166;animation-delay:2s;animation-duration:3.2s"></div>
    <div class="mp-p" style="left:20%;top:50%;background:#06d6a0;animation-delay:1s;animation-duration:5s"></div>
  </div>
  <div class="mp-badge">✦ CLAUDE AI MASTERPIECE ENGINE</div>
  <div class="mp-ring-outer"><div class="mp-ring-inner">🎯</div></div>
  <div class="mp-title">Crafting Your <span>Masterpiece Demo</span></div>
  <div class="mp-sub">AI Agent is reading your full solution scope and designing a cinematic, production-quality interactive prototype with 8 screens of real data.</div>
  <div class="mp-steps">
    <div class="mp-step"><span class="ms-ico">🔍</span><span class="ms-lbl">Deep-analysing solution scope &amp; user workflows</span><span class="ms-st ms-done">✓ Done</span></div>
    <div class="mp-step"><span class="ms-ico">🎨</span><span class="ms-lbl">Designing 8 cinematic product screens</span><span class="ms-st ms-wip">Crafting…</span></div>
    <div class="mp-step"><span class="ms-ico">📊</span><span class="ms-lbl">Rendering animated SVG charts with live data</span><span class="ms-st ms-wait">Pending</span></div>
    <div class="mp-step"><span class="ms-ico">🤖</span><span class="ms-lbl">Building AI Assistant conversation flows</span><span class="ms-st ms-wait">Pending</span></div>
    <div class="mp-step"><span class="ms-ico">⚡</span><span class="ms-lbl">Wiring micro-interactions &amp; real-time simulation</span><span class="ms-st ms-wait">Pending</span></div>
    <div class="mp-step"><span class="ms-ico">🚀</span><span class="ms-lbl">Compiling masterpiece into one self-contained file</span><span class="ms-st ms-wait">Pending</span></div>
  </div>
  <div class="mp-bar"><div class="mp-bar-fill"></div></div>
</div>
"""


def render_live_demo_tab(se, te, ce, r):
    """Render the 🎯 Live Demo tab content."""

    st.markdown("""
<style>
.demo-hero {
  background: linear-gradient(135deg, #0a0e27 0%, #0d1b4b 50%, #0a2744 100%);
  border: 1px solid rgba(0,212,170,.25);
  border-radius: 20px;
  padding: 36px 40px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}
.demo-hero::before {
  content:'';position:absolute;inset:0;
  background: radial-gradient(circle at 80% 50%, rgba(0,212,170,.07) 0%, transparent 60%);
}
.demo-hero-title {
  font-size:1.8rem;font-weight:800;color:#fff;
  margin-bottom:8px;letter-spacing:.5px;
}
.demo-hero-sub {
  font-size:.95rem;color:rgba(255,255,255,.6);
  max-width:600px;line-height:1.6;
}
.demo-badge {
  display:inline-block;
  background:linear-gradient(135deg,rgba(0,212,170,.2),rgba(123,97,255,.2));
  border:1px solid rgba(0,212,170,.4);
  color:#00d4aa;font-size:.72rem;font-weight:700;
  letter-spacing:1.5px;padding:4px 14px;border-radius:20px;
  margin-bottom:16px;
}
.demo-feature-grid {
  display:grid;grid-template-columns:repeat(3,1fr);gap:16px;
  margin-bottom:24px;
}
.demo-feature-card {
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);
  border-radius:14px;padding:20px;
  transition:all .2s ease;
}
.demo-feature-card:hover {
  background:rgba(0,212,170,.06);
  border-color:rgba(0,212,170,.25);
  transform:translateY(-2px);
}
.demo-feature-icon { font-size:1.6rem;margin-bottom:10px; }
.demo-feature-title { font-size:.9rem;font-weight:700;color:#fff;margin-bottom:4px; }
.demo-feature-desc  { font-size:.78rem;color:rgba(255,255,255,.5);line-height:1.5; }
.demo-iframe-wrap {
  border-radius:16px;overflow:hidden;
  border:1px solid rgba(0,212,170,.3);
  box-shadow:0 0 60px rgba(0,212,170,.08), 0 20px 60px rgba(0,0,0,.4);
}
.demo-iframe-bar {
  background:rgba(255,255,255,.04);
  border-bottom:1px solid rgba(255,255,255,.08);
  padding:10px 16px;
  display:flex;align-items:center;gap:8px;
}
.wbar-dot { width:12px;height:12px;border-radius:50%; }
.wbar-url {
  flex:1;background:rgba(255,255,255,.07);
  border-radius:20px;padding:4px 14px;
  font-size:.72rem;color:rgba(255,255,255,.4);
  margin:0 8px;font-family:monospace;
}
.demo-action-row {
  display:flex;gap:12px;margin-top:20px;
}
</style>
""", unsafe_allow_html=True)

    project_type = safe_str(r.get("project_type", "Enterprise Solution"))
    total_hours  = safe_int(te.get("total_hours"))
    monthly_cost = safe_int(ce.get("total_monthly_cost", 0))
    req_count    = len(safe_list(se.get("requirements")))

    # Hero banner
    st.markdown(f"""
<div class="demo-hero">
  <div class="demo-badge">✨ AI-POWERED SOLUTION VISUALISER</div>
  <div class="demo-hero-title">🎯 See Your Solution Before It's Built</div>
  <div class="demo-hero-sub">
    AI reads your scope document and generates an interactive prototype of the <strong>actual {project_type}</strong> product —
    the real screens your end users will log into. Not an estimation dashboard. Not a proposal deck.
    A live, clickable preview of what you're getting.
  </div>
</div>
<div class="demo-feature-grid">
  <div class="demo-feature-card">
    <div class="demo-feature-icon">🖥️</div>
    <div class="demo-feature-title">Real Product Screens</div>
    <div class="demo-feature-desc">AI detects your solution type (chatbot, portal, analytics, CRM…) and builds the right UI — not generic placeholders</div>
  </div>
  <div class="demo-feature-card">
    <div class="demo-feature-icon">🎨</div>
    <div class="demo-feature-title">Domain-Specific Data</div>
    <div class="demo-feature-desc">Every screen is populated with realistic, domain-appropriate sample data derived from your actual requirements</div>
  </div>
  <div class="demo-feature-card">
    <div class="demo-feature-icon">🚀</div>
    <div class="demo-feature-title">Share With Your Client</div>
    <div class="demo-feature-desc">Download as a standalone HTML file — open in any browser, embed in a deck, send before the pitch</div>
  </div>
</div>
""", unsafe_allow_html=True)

    ai = _pick_ai_for_raw()
    ai_status_color = "#00d4aa" if ai else "#ff6b6b"
    _demo_key = get_model_for_feature("live_demo")
    ai_status_text  = (f"✓ AI Ready — {type(ai).__name__} ({_demo_key})" if ai else "✗ No AI configured — add your API key to config.yaml")
    st.markdown(
        f'<span style="background:rgba(0,0,0,.3);border:1px solid {ai_status_color};color:{ai_status_color};'
        f'padding:4px 14px;border-radius:20px;font-size:.75rem;font-weight:600">{ai_status_text}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Buttons ──
    btn_cols = st.columns([2, 1, 1])
    with btn_cols[0]:
        gen_clicked = st.button(
            "🎯 Create Live Demo",
            use_container_width=True,
            type="primary",
            disabled=(ai is None),
            key="btn_gen_demo",
            help="AI reads your scope, detects the solution type, and generates realistic product screens your end users will actually use — not estimation slides",
        )
    with btn_cols[1]:
        regen_clicked = st.button(
            "🔄 Regenerate",
            use_container_width=True,
            disabled=(ai is None or "live_demo_html" not in st.session_state),
            key="btn_regen_demo",
        )
    with btn_cols[2]:
        if st.session_state.get("live_demo_html"):
            st.download_button(
                "📥 Download Demo",
                data=st.session_state["live_demo_html"],
                file_name=f"ECI_LiveDemo_{project_type.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True,
                key="btn_dl_demo",
            )

    # ── Generate ──
    if gen_clicked or regen_clicked:
        try:
            st.toast("🎯 AI is building your live demo — this takes 1-3 min…", icon="⏳")
        except Exception:
            pass
        loader_slot = st.empty()
        loader_slot.markdown(_demo_loading_animation(), unsafe_allow_html=True)
        try:
            html_result = generate_live_demo_html(se, te, ce, r)
            loader_slot.empty()
            if html_result:
                st.session_state["live_demo_html"] = html_result
                st.rerun()
            else:
                loader_slot.empty()
                st.error("Demo generation failed — AI did not return valid HTML. Check your API key in the sidebar.")
        except Exception as ex:
            loader_slot.empty()
            st.error(f"Generation error: {str(ex)[:300]}")

    # ── Render the iframe ──
    demo_html = st.session_state.get("live_demo_html")
    if demo_html:
        # Wrap in fake browser chrome for wow factor
        b64 = base64.b64encode(demo_html.encode("utf-8")).decode("utf-8")
        st.markdown(f"""
<div class="demo-iframe-wrap">
  <div class="demo-iframe-bar">
    <div class="wbar-dot" style="background:#ff5f56"></div>
    <div class="wbar-dot" style="background:#ffbd2e"></div>
    <div class="wbar-dot" style="background:#27c93f"></div>
    <div class="wbar-url">https://eci-demo.azure.com/{project_type.lower().replace(' ','-')}/live</div>
    <span style="font-size:.7rem;color:rgba(0,212,170,.7);font-weight:600">🔒 SECURE · LIVE DEMO</span>
  </div>
  <iframe
    src="data:text/html;base64,{b64}"
    width="100%" height="820"
    style="border:none;display:block;"
    sandbox="allow-scripts allow-same-origin"
    title="ECI Live Demo">
  </iframe>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            "💡 **Tip:** Click the sidebar nav items inside the demo to explore the product screens. "
            "This shows the actual solution your end users will use — download and share with your client before the pitch."
        )
    elif not gen_clicked:
        # Teaser preview when nothing generated yet
        st.markdown("""
<div style="border:2px dashed rgba(0,212,170,.2);border-radius:16px;padding:60px 40px;
     text-align:center;background:rgba(0,212,170,.02);margin-top:16px">
  <div style="font-size:3rem;margin-bottom:16px">🎯</div>
  <div style="font-size:1.2rem;font-weight:700;color:rgba(255,255,255,.8);margin-bottom:8px">
    Your solution preview will appear here
  </div>
  <div style="font-size:.85rem;color:rgba(255,255,255,.4);max-width:480px;margin:0 auto;line-height:1.6">
    Click <strong style="color:#00d4aa">Create Live Demo</strong> above and AI will read your scope,
    identify the solution type (chatbot, portal, analytics platform…) and generate realistic product
    screens — the actual UI your end users will log into. Show your client exactly what they're getting.
  </div>
</div>
""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    #  CLAUDE AI MASTERPIECE DEMO SECTION
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")

    # ── Hero card ──
    st.markdown("""
<div style="background:linear-gradient(135deg,#0a0620 0%,#0d0a2e 40%,#060e20 100%);
     border:1px solid rgba(123,97,255,.35);border-radius:20px;padding:34px 38px;
     margin-bottom:20px;position:relative;overflow:hidden">
  <div style="position:absolute;inset:0;pointer-events:none;
    background:radial-gradient(ellipse at 80% 40%,rgba(123,97,255,.1) 0,transparent 60%),
               radial-gradient(ellipse at 20% 70%,rgba(0,212,170,.07) 0,transparent 60%)"></div>
  <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(123,97,255,.12);
    border:1px solid rgba(123,97,255,.3);border-radius:20px;padding:4px 14px;
    font-size:.7rem;font-weight:700;color:#7b61ff;letter-spacing:1.2px;margin-bottom:14px">
    ✦ CLAUDE AI EXCLUSIVE · MASTERPIECE ENGINE
  </div>
  <div style="font-size:1.75rem;font-weight:900;color:#fff;margin-bottom:8px;letter-spacing:.3px">
    🌟 AI Agent Masterpiece Demo
  </div>
  <div style="font-size:.9rem;color:rgba(255,255,255,.55);max-width:640px;line-height:1.65;margin-bottom:22px">
    AI Agent reads your entire solution scope and generates a <strong style="color:#7b61ff">cinematic,
    production-grade 8-screen interactive prototype</strong> — glassmorphism design system, animated SVG charts,
    AI assistant built in, kanban workflow, real-time live data simulation, and domain-specific data
    throughout. The most realistic product preview possible before a single line of code is written.
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px">
      <div style="font-size:1.4rem;margin-bottom:6px">🖥️</div>
      <div style="font-size:.82rem;font-weight:700;color:#e2e8f0;margin-bottom:3px">8 Full Screens</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.4)">Dashboard, Analytics, AI Chat, Kanban, Forms, Reports, Settings</div>
    </div>
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px">
      <div style="font-size:1.4rem;margin-bottom:6px">📊</div>
      <div style="font-size:.82rem;font-weight:700;color:#e2e8f0;margin-bottom:3px">Animated SVG Charts</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.4)">Bar, line & donut charts with live data and real domain numbers</div>
    </div>
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px">
      <div style="font-size:1.4rem;margin-bottom:6px">🤖</div>
      <div style="font-size:.82rem;font-weight:700;color:#e2e8f0;margin-bottom:3px">Built-in AI Chat</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.4)">Pre-loaded Q&A flows specific to your solution domain</div>
    </div>
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px">
      <div style="font-size:1.4rem;margin-bottom:6px">⚡</div>
      <div style="font-size:.82rem;font-weight:700;color:#e2e8f0;margin-bottom:3px">Real-time Simulation</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.4)">Live activity feed, toast notifications, animated KPI counters</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Claude status ──
    ant_client = AnthropicAI.from_session()
    ant_live   = ant_client and ant_client.is_live
    ant_color  = "#7b61ff" if ant_live else "#ff6b6b"
    ant_label  = "✓ AI Agent Ready — Masterpiece Engine Online" if ant_live else "✗ AI Agent not configured — add API key & endpoint to Settings"
    st.markdown(
        f'<span style="background:rgba(0,0,0,.4);border:1px solid {ant_color};color:{ant_color};'
        f'padding:4px 14px;border-radius:20px;font-size:.75rem;font-weight:600">{ant_label}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Buttons ──
    _mp_key = "claude_masterpiece_html"
    _mp_html = st.session_state.get(_mp_key)

    mp_cols = st.columns([2, 1, 1])
    with mp_cols[0]:
        mp_gen = st.button(
            "🌟 Generate AI Agent Masterpiece Demo",
            use_container_width=True,
            type="primary",
            disabled=(not ant_live),
            key="btn_mp_gen",
            help="AI Agent reads your full solution scope and generates a cinematic 8-screen prototype with glassmorphism design, animated charts, AI assistant, kanban board and real-time simulation",
        )
    with mp_cols[1]:
        mp_regen = st.button(
            "🔄 Regenerate",
            use_container_width=True,
            disabled=(not ant_live or not _mp_html),
            key="btn_mp_regen",
        )
    with mp_cols[2]:
        if _mp_html:
            st.download_button(
                "📥 Download Masterpiece",
                data=_mp_html,
                file_name=f"ECI_Masterpiece_{project_type.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True,
                key="btn_mp_dl",
            )

    # ── Generate ──
    if mp_gen or mp_regen:
        try:
            st.toast("✦ AI Agent Masterpiece Engine started — crafting 8 cinematic screens…", icon="🌟")
        except Exception:
            pass
        mp_slot = st.empty()
        mp_slot.markdown(_masterpiece_loading_animation(), unsafe_allow_html=True)
        try:
            mp_result = generate_claude_masterpiece_html(se, te, ce, r)
            mp_slot.empty()
            if mp_result:
                st.session_state[_mp_key] = mp_result
                st.rerun()
            else:
                mp_slot.empty()
                st.error("Masterpiece generation failed — AI Agent did not return HTML. Check API key & endpoint in Settings.", icon="⚠️")
        except Exception as mp_ex:
            try:
                mp_slot.empty()
            except Exception:
                pass
            st.error(f"Generation error: {str(mp_ex)[:300]}", icon="⚠️")

    # ── Render masterpiece iframe ──
    if _mp_html:
        b64_mp = base64.b64encode(_mp_html.encode("utf-8")).decode("utf-8")
        st.markdown(f"""
<div style="border-radius:18px;overflow:hidden;border:1px solid rgba(123,97,255,.4);
     box-shadow:0 0 80px rgba(123,97,255,.1),0 0 40px rgba(0,212,170,.06),0 24px 80px rgba(0,0,0,.5)">
  <div style="background:rgba(255,255,255,.03);border-bottom:1px solid rgba(255,255,255,.07);
       padding:10px 16px;display:flex;align-items:center;gap:8px">
    <div style="width:12px;height:12px;border-radius:50%;background:#ff5f56"></div>
    <div style="width:12px;height:12px;border-radius:50%;background:#ffbd2e"></div>
    <div style="width:12px;height:12px;border-radius:50%;background:#27c93f"></div>
    <div style="flex:1;background:rgba(255,255,255,.06);border-radius:20px;padding:4px 14px;
         font-size:.72rem;color:rgba(255,255,255,.35);margin:0 8px;font-family:monospace">
      https://eci-masterpiece.azure.com/{project_type.lower().replace(' ','-')}/live
    </div>
    <span style="font-size:.68rem;color:rgba(123,97,255,.8);font-weight:700">✦ CLAUDE MASTERPIECE · LIVE</span>
  </div>
  <iframe
    src="data:text/html;base64,{b64_mp}"
    width="100%" height="900"
    style="border:none;display:block;"
    sandbox="allow-scripts allow-same-origin"
    title="ECI AI Agent Masterpiece Demo">
  </iframe>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            "💡 **Masterpiece Tip:** Click every sidebar item to explore all 8 screens — "
            "Dashboard, Analytics, AI Assistant, Kanban, Detail View, Reports, and Settings. "
            "The AI Assistant screen has a live chat — type questions about your solution. "
            "Download the HTML file to share with your client before the pitch."
        )
    elif not mp_gen:
        st.markdown("""
<div style="border:2px dashed rgba(123,97,255,.2);border-radius:16px;padding:70px 40px;
     text-align:center;background:rgba(123,97,255,.02);margin-top:8px">
  <div style="font-size:3.5rem;margin-bottom:16px">🌟</div>
  <div style="font-size:1.2rem;font-weight:700;color:rgba(255,255,255,.8);margin-bottom:10px">
    AI Agent Masterpiece Demo will appear here
  </div>
  <div style="font-size:.85rem;color:rgba(255,255,255,.38);max-width:520px;margin:0 auto;line-height:1.65">
    Click <strong style="color:#7b61ff">Generate AI Agent Masterpiece Demo</strong> above.
    AI Agent will spend 2-4 minutes crafting a cinematic 8-screen prototype —
    glassmorphism UI, animated charts, built-in AI assistant, kanban board,
    real-time live data, and domain-specific content throughout.
    The most impressive solution preview you can show a client.
  </div>
</div>
""", unsafe_allow_html=True)
