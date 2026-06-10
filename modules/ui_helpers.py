# ═══════════════════════════════════════════════════════════════════════
#  UI / UX HELPERS
# ═══════════════════════════════════════════════════════════════════════
import time
import streamlit as st
from .database import _db_category_counts, _db_load_runs


def show_toast(message: str, kind: str = "success"):
    icons = {"success": "✅", "error": "❌", "info": "ℹ️", "warn": "⚠️"}
    icon = icons.get(kind, "ℹ️")
    st.markdown(
        f'<div class="toast {kind}">{icon}&nbsp; {message}</div>',
        unsafe_allow_html=True,
    )


def _pipeline_stepper_html(steps: list, current_idx: int) -> str:
    parts = []
    for i, label in enumerate(steps):
        if i < current_idx:
            dot_cls, lbl_cls, dot_txt = "done", "done", "✓"
        elif i == current_idx:
            dot_cls, lbl_cls, dot_txt = "active", "active", str(i + 1)
        else:
            dot_cls, lbl_cls, dot_txt = "pend", "", str(i + 1)
        parts.append(
            f'<div class="ps-step">'
            f'<div class="ps-dot {dot_cls}">{dot_txt}</div>'
            f'<span class="ps-lbl {lbl_cls}">{label}</span>'
            f'</div>'
        )
        if i < len(steps) - 1:
            conn_cls = "done" if i < current_idx else "pend"
            parts.append(f'<div class="ps-conn {conn_cls}"></div>')
    return '<div class="pipe-stepper">' + "".join(parts) + "</div>"


def _kpi_card(icon: str, title: str, value: str, subtitle: str, animated: bool = False) -> str:
    extra_cls = " kpi-glow" if animated else ""
    return (
        f'<div class="kpi{extra_cls}">'
        f'<div class="kpi-i">{icon}</div>'
        f'<div class="kpi-v">{value}</div>'
        f'<div class="kpi-t">{title}</div>'
        f'<div class="kpi-s">{subtitle}</div>'
        f"</div>"
    )


def _home_stats_banner():
    try:
        counts = _db_category_counts()
        total  = counts.get("All", 0)
        runs   = _db_load_runs("All")
        hours  = sum((r.get("total_hours") or 0) for r in runs)
        cost   = sum((r.get("monthly_cost") or 0) for r in runs)
    except Exception:
        total = hours = cost = 0
    st.markdown(
        f'<div class="home-stats">'
        f'<div class="hs-item"><span class="hs-n">{total}</span><span class="hs-l">Proposals Generated</span></div>'
        f'<div class="hs-sep"></div>'
        f'<div class="hs-item"><span class="hs-n">{hours:,}</span><span class="hs-l">Hours Estimated</span></div>'
        f'<div class="hs-sep"></div>'
        f'<div class="hs-item"><span class="hs-n">${cost:,}/mo</span><span class="hs-l">Infrastructure Sized</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _empty_upload():
    st.markdown(
        '<div class="empty-state">'
        '<div class="es-icon">📄</div>'
        '<div class="es-arr">⬆</div>'
        '<div class="es-title">Drop scope documents to begin</div>'
        '<div class="es-sub">Upload PDF, DOCX, XLSX, PPTX, TXT or CSV — '
        'the AI pipeline will extract requirements, estimate hours, cost, risk, and build the full proposal.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _empty_chat():
    st.markdown(
        '<div class="empty-state">'
        '<div class="es-icon">💬</div>'
        '<div class="typing-dots"><span></span><span></span><span></span></div>'
        '<div class="es-title">Ask anything about this proposal</div>'
        '<div class="es-sub">'
        'Try: <em>"Why does Phase 2 take so long?"</em> · '
        '<em>"What is the biggest risk?"</em> · '
        '<em>"How can we cut infrastructure cost by 20%?"</em>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _empty_library():
    st.markdown(
        '<div class="empty-state">'
        '<div class="es-icon">🗂️</div>'
        '<div class="es-title">No proposals yet</div>'
        '<div class="es-sub">Upload a scope document in <strong>⚡ Business Estimation</strong> '
        'and run the pipeline — results appear here automatically.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _stream_answer(text: str):
    """Word-by-word generator for st.write_stream() typing effect."""
    words = text.split()
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.022)
