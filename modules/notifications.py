# ═══════════════════════════════════════════════════════════════════════
#  NOTIFICATION SYSTEM  —  in-app bell + optional email/Teams/Slack
# ═══════════════════════════════════════════════════════════════════════
import json
import sqlite3
from datetime import datetime

from .database import _DB_PATH


# ── Icons per event type ────────────────────────────────────────────────
_EVENT_ICONS = {
    "run_saved":        "📊",
    "run_reviewed":     "✅",
    "run_unreviewed":   "↩️",
    "run_deleted":      "🗑️",
    "pipeline_start":   "🚀",
    "pipeline_done":    "🎉",
    "training_updated": "🧠",
    "email_sent":       "📧",
    "export_done":      "📥",
    "error":            "❌",
    "info":             "ℹ️",
}


# ── DB init / migrate ───────────────────────────────────────────────────
def _notif_init():
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            event_type TEXT    NOT NULL DEFAULT 'info',
            title      TEXT    NOT NULL DEFAULT '',
            message    TEXT    NOT NULL DEFAULT '',
            is_read    INTEGER NOT NULL DEFAULT 0,
            metadata   TEXT    NOT NULL DEFAULT '{}'
        )
    """)
    con.commit()
    con.close()


_notif_init()


# ── Core CRUD ───────────────────────────────────────────────────────────
def notify(event_type: str, title: str, message: str = "", metadata: dict = None):
    """Insert a new notification. Safe to call from anywhere."""
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute(
            "INSERT INTO notifications (ts, event_type, title, message, metadata) VALUES (?,?,?,?,?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                event_type,
                title,
                message,
                json.dumps(metadata or {}),
            ),
        )
        con.commit()
        con.close()
        # Prune old notifications — keep latest 100
        _prune(100)
    except Exception:
        pass  # never crash the caller


def _prune(keep: int = 100):
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute(
            "DELETE FROM notifications WHERE id NOT IN "
            "(SELECT id FROM notifications ORDER BY id DESC LIMIT ?)",
            (keep,),
        )
        con.commit()
        con.close()
    except Exception:
        pass


def get_notifications(limit: int = 30) -> list:
    """Return latest notifications, newest first."""
    try:
        con = sqlite3.connect(_DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        con.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.get("metadata", "{}"))
            except Exception:
                d["metadata"] = {}
            d["icon"] = _EVENT_ICONS.get(d["event_type"], "ℹ️")
            result.append(d)
        return result
    except Exception:
        return []


def get_unread_count() -> int:
    try:
        con = sqlite3.connect(_DB_PATH)
        count = con.execute(
            "SELECT COUNT(*) FROM notifications WHERE is_read=0"
        ).fetchone()[0]
        con.close()
        return count
    except Exception:
        return 0


def mark_read(notif_id: int):
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notif_id,))
        con.commit()
        con.close()
    except Exception:
        pass


def mark_all_read():
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute("UPDATE notifications SET is_read=1")
        con.commit()
        con.close()
    except Exception:
        pass


def delete_notification(notif_id: int):
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute("DELETE FROM notifications WHERE id=?", (notif_id,))
        con.commit()
        con.close()
    except Exception:
        pass


def clear_all_notifications():
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute("DELETE FROM notifications")
        con.commit()
        con.close()
    except Exception:
        pass


# ── Streamlit UI helper ─────────────────────────────────────────────────
def render_notification_bell():
    """
    Renders the notification bell icon + popover panel.
    Call this from the header area in main.py.
    """
    import streamlit as st

    unread = get_unread_count()
    badge  = f" ({unread})" if unread else ""
    label  = f"🔔{badge}"

    with st.popover(label, width="content"):
        st.markdown(
            '<div style="font-weight:700;font-size:.95rem;color:#e2e8f0;'
            'margin-bottom:8px">Notifications</div>',
            unsafe_allow_html=True,
        )

        notifs = get_notifications(limit=20)

        if not notifs:
            st.markdown(
                '<div style="color:#64748b;font-size:.82rem;padding:12px 0">No notifications yet.</div>',
                unsafe_allow_html=True,
            )
        else:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                if unread:
                    if st.button("Mark all read", key="_notif_mark_all", width="stretch"):
                        mark_all_read()
                        st.rerun()
            with col_r:
                if st.button("Clear all", key="_notif_clear_all", width="stretch"):
                    clear_all_notifications()
                    st.rerun()

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            for n in notifs:
                is_unread = not n["is_read"]
                bg      = "rgba(0,180,216,.08)" if is_unread else "rgba(255,255,255,.03)"
                border  = "rgba(0,180,216,.35)" if is_unread else "rgba(255,255,255,.07)"
                dot     = '<span style="width:7px;height:7px;background:#00b4d8;border-radius:50%;' \
                          'display:inline-block;margin-right:6px;flex-shrink:0"></span>' if is_unread else \
                          '<span style="width:7px;height:7px;display:inline-block;margin-right:6px"></span>'
                ts_str  = n.get("ts", "")[:16]  # "YYYY-MM-DD HH:MM"

                _msg_html = (
                    '<div style="font-size:.77rem;color:#94a3b8;margin-top:3px;padding-left:13px">'
                    + n["message"] + '</div>'
                ) if n["message"] else ""
                st.markdown(
                    f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
                    f'padding:9px 12px;margin-bottom:6px;cursor:default">'
                    f'<div style="display:flex;align-items:center;gap:4px">'
                    f'{dot}'
                    f'<span style="font-size:1rem">{n["icon"]}</span>&nbsp;'
                    f'<span style="font-weight:600;font-size:.82rem;color:#e2e8f0">{n["title"]}</span>'
                    f'</div>'
                    f'{_msg_html}'
                    f'<div style="font-size:.7rem;color:#475569;margin-top:4px;padding-left:13px">{ts_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if is_unread:
                    mark_read(n["id"])
