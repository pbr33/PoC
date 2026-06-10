"""Custom CSS styles for the ECI Presale Agent UI."""
import streamlit as st


def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=DM+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

        /* ── Global Overrides ── */
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-card: #151c2e;
            --bg-card-hover: #1a2340;
            --border-primary: #1e2a4a;
            --border-accent: #00d4aa;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #00d4aa;
            --accent-blue: #00b4d8;
            --accent-purple: #7b61ff;
            --accent-pink: #ff6b9d;
            --accent-red: #ff6b6b;
            --accent-yellow: #ffd166;
            --accent-green: #06d6a0;
            --glow-cyan: rgba(0,212,170,0.15);
            --glow-purple: rgba(123,97,255,0.15);
        }

        .stApp {
            background: var(--bg-primary) !important;
        }

        /* ── Main content styling ── */
        .main .block-container {
            padding-top: 1rem;
            max-width: 100%;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d1321 0%, #111827 100%) !important;
            border-right: 1px solid var(--border-primary);
        }

        section[data-testid="stSidebar"] .stTextInput input,
        section[data-testid="stSidebar"] .stSelectbox select {
            background: var(--bg-card) !important;
            border: 1px solid var(--border-primary) !important;
            color: var(--text-primary) !important;
        }

        /* ── Header ── */
        .eci-logo-container {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .eci-logo-icon {
            font-size: 2.2rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 12px var(--glow-cyan));
        }
        .eci-logo-text {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }
        .eci-logo-sub {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.75rem;
            color: var(--text-secondary);
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .header-tagline {
            text-align: center;
            font-family: 'DM Sans', sans-serif;
            color: var(--text-secondary);
            font-size: 0.9rem;
            padding-top: 0.8rem;
        }
        .header-datetime {
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-muted);
            font-size: 0.8rem;
            padding-top: 1rem;
        }

        /* ── Sidebar Config ── */
        .sidebar-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-primary);
        }
        .config-section-header {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--accent-cyan);
            margin: 0.8rem 0 0.4rem 0;
            letter-spacing: 0.5px;
        }
        .config-status {
            background: var(--bg-card);
            border-radius: 8px;
            padding: 12px;
            border: 1px solid var(--border-primary);
        }
        .status-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.82rem;
            color: var(--text-secondary);
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        .status-dot.active { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
        .status-dot.inactive { background: var(--text-muted); }

        /* ── Section Headers ── */
        .section-header {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 1.5rem 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-icon {
            font-size: 1.4rem;
        }
        .pipeline-header {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-cyan);
            text-align: center;
            padding: 12px;
            background: linear-gradient(135deg, var(--glow-cyan), var(--glow-purple));
            border-radius: 8px;
            margin-bottom: 1rem;
            border: 1px solid var(--border-primary);
        }

        /* ── Cards ── */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 12px;
            padding: 1.2rem;
            margin-bottom: 0.8rem;
            transition: border-color 0.3s ease;
        }
        .card:hover {
            border-color: var(--accent-cyan);
        }
        .card-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.3rem;
        }
        .card-desc {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.82rem;
            color: var(--text-secondary);
            margin-bottom: 0.8rem;
        }

        /* ── KPI Cards ── */
        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        .kpi-card:hover {
            border-color: var(--accent-cyan);
            box-shadow: 0 0 20px var(--glow-cyan);
            transform: translateY(-2px);
        }
        .kpi-icon { font-size: 1.8rem; margin-bottom: 0.4rem; }
        .kpi-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-cyan);
        }
        .kpi-title {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-top: 0.2rem;
        }
        .kpi-sub {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.72rem;
            color: var(--text-muted);
        }

        /* ── Agent Log ── */
        .agent-log-row {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 6px 12px;
            background: var(--bg-card);
            border-radius: 6px;
            margin-bottom: 4px;
            border-left: 3px solid var(--accent-cyan);
        }
        .agent-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--accent-blue);
            min-width: 160px;
        }
        .agent-status-ok {
            color: var(--accent-green);
            font-size: 0.8rem;
            font-weight: 500;
            min-width: 90px;
        }
        .agent-detail {
            font-family: 'DM Sans', sans-serif;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }

        /* ── Requirements ── */
        .req-category-header {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 0.8rem;
        }
        .req-category-header.func { background: rgba(0,212,170,0.1); color: var(--accent-cyan); border: 1px solid rgba(0,212,170,0.2); }
        .req-category-header.nonfunc { background: rgba(0,180,216,0.1); color: var(--accent-blue); border: 1px solid rgba(0,180,216,0.2); }
        .req-category-header.integ { background: rgba(123,97,255,0.1); color: var(--accent-purple); border: 1px solid rgba(123,97,255,0.2); }

        .req-item {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 6px;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.82rem;
            color: var(--text-secondary);
        }
        .req-item strong { color: var(--text-primary); font-size: 0.85rem; }
        .req-complexity {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--accent-yellow);
            margin-top: 2px;
        }

        .tech-tags-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .tech-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            background: var(--bg-card);
            border: 1px solid var(--accent-purple);
            color: var(--accent-purple);
            padding: 3px 10px;
            border-radius: 12px;
        }

        /* ── Risk ── */
        .risk-score-banner {
            background: var(--bg-card);
            padding: 16px 20px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 1rem;
        }
        .risk-score-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .risk-score-label {
            font-family: 'DM Sans', sans-serif;
            font-size: 1rem;
            color: var(--text-secondary);
        }
        .risk-card {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 8px;
        }
        .risk-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .risk-card-header strong { color: var(--text-primary); font-family: 'DM Sans', sans-serif; }
        .risk-severity { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }
        .risk-card p { color: var(--text-secondary); font-size: 0.82rem; margin: 4px 0; }
        .risk-mitigation { font-size: 0.8rem; color: var(--accent-green); }

        /* ── Architecture ── */
        .arch-component {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
            transition: all 0.3s ease;
        }
        .arch-component:hover {
            border-color: var(--accent-purple);
            box-shadow: 0 0 16px var(--glow-purple);
        }
        .arch-comp-name {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        .arch-comp-type {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--accent-purple);
            margin-bottom: 6px;
        }
        .arch-comp-services {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.8rem;
            color: var(--text-secondary);
            padding-left: 16px;
        }
        .arch-comp-services li { margin-bottom: 2px; }

        .data-flow-viz {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--accent-cyan);
            background: var(--bg-card);
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid var(--border-primary);
            text-align: center;
            letter-spacing: 0.5px;
        }

        /* ── Learning Loop ── */
        .loop-step {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 10px;
            padding: 16px 12px;
            text-align: center;
            min-height: 160px;
        }
        .loop-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 8px;
        }
        .loop-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 6px;
        }
        .loop-desc {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.72rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        /* ── Method Cards ── */
        .method-card {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            min-height: 120px;
        }
        .method-icon { font-size: 1.6rem; margin-bottom: 6px; }
        .method-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }
        .method-desc {
            font-family: 'DM Sans', sans-serif;
            font-size: 0.72rem;
            color: var(--text-secondary);
            line-height: 1.3;
        }

        /* ── Training Card ── */
        .training-project-card {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 6px;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        .training-project-card strong { color: var(--text-primary); }

        /* ── Buttons ── */
        .stButton > button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue)) !important;
            color: #0a0e1a !important;
            font-family: 'DM Sans', sans-serif !important;
            font-weight: 600 !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.5rem !important;
            transition: all 0.3s ease !important;
        }
        .stButton > button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            box-shadow: 0 0 20px var(--glow-cyan) !important;
            transform: translateY(-1px);
        }
        .stButton > button[kind="secondary"],
        button[data-testid="stBaseButton-secondary"] {
            background: var(--bg-card) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-primary) !important;
            border-radius: 8px !important;
        }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: var(--bg-secondary);
            padding: 4px;
            border-radius: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            color: var(--text-secondary);
            border-radius: 8px;
            padding: 8px 16px;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.85rem;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: var(--bg-card) !important;
            color: var(--accent-cyan) !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        /* ── File uploader ── */
        [data-testid="stFileUploader"] {
            background: var(--bg-card);
            border: 1px dashed var(--border-primary);
            border-radius: 10px;
            padding: 1rem;
        }

        /* ── Expander ── */
        .streamlit-expanderHeader {
            background: var(--bg-card) !important;
            border-radius: 8px;
            font-family: 'DM Sans', sans-serif;
        }

        /* ── Metrics ── */
        [data-testid="stMetric"] {
            background: var(--bg-card);
            border: 1px solid var(--border-primary);
            border-radius: 10px;
            padding: 12px 16px;
        }
        [data-testid="stMetricLabel"] {
            font-family: 'DM Sans', sans-serif !important;
        }
        [data-testid="stMetricValue"] {
            font-family: 'JetBrains Mono', monospace !important;
            color: var(--accent-cyan) !important;
        }

        /* ── Scrollbar ── */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--border-primary); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-cyan); }

        /* ── Hide default Streamlit branding ── */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header[data-testid="stHeader"] { background: rgba(10,14,26,0.95); backdrop-filter: blur(10px); }
        </style>
        """,
        unsafe_allow_html=True,
    )
