# ═══════════════════════════════════════════════════════════════════════
#  PERSISTENT RUN DATABASE  (SQLite — survives page refreshes)
# ═══════════════════════════════════════════════════════════════════════
import os, sqlite3, json
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eci_runs.db")

_CATEGORY_KEYWORDS = {
    "AI":    ["ai", "openai", "gpt", "claude", "gemini", "llm", "machine learning",
               "nlp", "copilot", "foundry", "azure ai", "cognitive", "neural",
               "vector", "embedding", "rag", "chatbot", "generative"],
    "Data":  ["data", "analytics", "bi", "power bi", "data lake", "databricks",
               "synapse", "warehouse", "etl", "pipeline", "reporting", "dashboard",
               "sql", "cosmos", "tableau", "fabric", "dbt", "ingestion"],
    "Cloud": ["cloud", "azure", "aws", "gcp", "kubernetes", "docker", "devops",
               "ci/cd", "microservice", "serverless", "migration", "infrastructure",
               "terraform", "container", "app service", "functions"],
}

def _detect_category(project_type: str, tech_stack: list) -> str:
    combined = (project_type + " " + " ".join(tech_stack or [])).lower()
    scores   = {cat: sum(1 for kw in kws if kw in combined)
                for cat, kws in _CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def _db_init():
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            ts                TEXT    NOT NULL,
            category          TEXT    NOT NULL DEFAULT 'General',
            project_type      TEXT,
            client_name       TEXT    DEFAULT '',
            project_title     TEXT    DEFAULT '',
            total_hours       INTEGER DEFAULT 0,
            duration_weeks    TEXT,
            monthly_cost      INTEGER DEFAULT 0,
            annual_cost       INTEGER DEFAULT 0,
            risk_level        TEXT,
            risk_score        INTEGER DEFAULT 0,
            req_count         INTEGER DEFAULT 0,
            tech_stack        TEXT    DEFAULT '[]',
            model_used        TEXT,
            three_point       TEXT    DEFAULT '{}',
            results_json      TEXT    DEFAULT '{}',
            architect_reviewed INTEGER DEFAULT 0,
            review_ts         TEXT    DEFAULT NULL,
            review_notes      TEXT    DEFAULT '',
            created_by        TEXT    DEFAULT '',
            created_by_email  TEXT    DEFAULT '',
            is_archived       INTEGER DEFAULT 0,
            review_status     TEXT    DEFAULT 'pending',
            reviewed_by       TEXT    DEFAULT '',
            project_outcome   TEXT    DEFAULT 'pending',
            actual_hours      INTEGER DEFAULT NULL,
            actual_cost       INTEGER DEFAULT NULL,
            outcome_notes     TEXT    DEFAULT '',
            parent_run_id     INTEGER DEFAULT NULL
        )
    """)
    con.commit()
    con.close()

_db_init()


def _db_migrate():
    con = sqlite3.connect(_DB_PATH)
    existing_cols = {row[1] for row in con.execute("PRAGMA table_info(proposals)").fetchall()}
    for col, ddl in [
        ("architect_reviewed", "INTEGER DEFAULT 0"),
        ("review_ts",          "TEXT    DEFAULT NULL"),
        ("review_notes",       "TEXT    DEFAULT ''"),
        ("client_name",        "TEXT    DEFAULT ''"),
        ("project_title",      "TEXT    DEFAULT ''"),
        ("created_by",         "TEXT    DEFAULT ''"),
        ("created_by_email",   "TEXT    DEFAULT ''"),
        ("is_archived",        "INTEGER DEFAULT 0"),
        ("review_status",      "TEXT    DEFAULT 'pending'"),
        ("reviewed_by",        "TEXT    DEFAULT ''"),
        ("project_outcome",    "TEXT    DEFAULT 'pending'"),
        ("actual_hours",       "INTEGER DEFAULT NULL"),
        ("actual_cost",        "INTEGER DEFAULT NULL"),
        ("outcome_notes",      "TEXT    DEFAULT ''"),
        ("parent_run_id",        "INTEGER DEFAULT NULL"),
        # ── Versioning & negotiation metadata ──────────────────────────
        ("version_number",       "INTEGER DEFAULT 1"),
        ("version_status",       "TEXT    DEFAULT 'draft'"),
        ("negotiation_stage",    "TEXT    DEFAULT 'initial'"),
        ("revision_reason_type", "TEXT    DEFAULT ''"),
        ("revision_notes",       "TEXT    DEFAULT ''"),
        ("parking_lot",          "TEXT    DEFAULT '[]'"),
        ("competitor_context",   "TEXT    DEFAULT ''"),
        ("submitted_at",         "TEXT    DEFAULT NULL"),
        ("is_winning_version",   "INTEGER DEFAULT 0"),
        ("is_baseline_locked",   "INTEGER DEFAULT 0"),
    ]:
        if col not in existing_cols:
            con.execute(f"ALTER TABLE proposals ADD COLUMN {col} {ddl}")
    # Backfill review_status for rows already marked reviewed in old binary scheme
    con.execute(
        "UPDATE proposals SET review_status='approved' "
        "WHERE architect_reviewed=1 AND (review_status IS NULL OR review_status='pending' OR review_status='')"
    )
    con.commit()
    con.close()

_db_migrate()


def db_save_run(snapshot: dict, full_results: dict) -> int:
    """Insert a run into the DB and return its new row id."""
    tech = snapshot.get("tech_stack", [])
    cat  = _detect_category(snapshot.get("project_type", ""), tech)
    con  = sqlite3.connect(_DB_PATH)
    try:
        cur = con.execute("""
            INSERT INTO proposals
                (ts, category, project_type, client_name, project_title,
                 total_hours, duration_weeks,
                 monthly_cost, annual_cost, risk_level, risk_score,
                 req_count, tech_stack, model_used, three_point, results_json,
                 created_by, created_by_email, parent_run_id,
                 version_number, version_status, negotiation_stage,
                 revision_reason_type, revision_notes, parking_lot,
                 competitor_context)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot.get("ts",                    datetime.now().strftime("%Y-%m-%d %H:%M")),
            cat,
            snapshot.get("project_type",          ""),
            snapshot.get("client_name",           ""),
            snapshot.get("project_title",         ""),
            snapshot.get("total_hours",           0),
            snapshot.get("duration_weeks",        ""),
            snapshot.get("monthly_cost",          0),
            snapshot.get("annual_cost",           0),
            snapshot.get("risk_level",            ""),
            snapshot.get("risk_score",            0),
            snapshot.get("req_count",             0),
            json.dumps(tech),
            snapshot.get("model_used",            ""),
            json.dumps(snapshot.get("three_point", {})),
            json.dumps(full_results, default=str),
            snapshot.get("created_by",            ""),
            snapshot.get("created_by_email",      ""),
            snapshot.get("parent_run_id",         None),
            snapshot.get("version_number",        1),
            snapshot.get("version_status",        "draft"),
            snapshot.get("negotiation_stage",     "initial"),
            snapshot.get("revision_reason_type",  ""),
            snapshot.get("revision_notes",        ""),
            json.dumps(snapshot.get("parking_lot", [])),
            snapshot.get("competitor_context",    ""),
        ))
        row_id = cur.lastrowid
        # Lock the baseline (V1) so it is never overwritten
        if snapshot.get("parent_run_id") is None and row_id:
            con.execute("UPDATE proposals SET is_baseline_locked=1 WHERE id=?", (row_id,))
        con.commit()
        return row_id
    finally:
        con.close()


def db_load_runs(category: str = "All", include_archived: bool = False) -> list:
    """Return list of run dicts (no results_json) newest-first."""
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        conditions, params = [], []
        if category and category != "All":
            conditions.append("category=?")
            params.append(category)
        if not include_archived:
            conditions.append("(is_archived IS NULL OR is_archived=0)")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows  = con.execute(
            f"SELECT * FROM proposals {where} ORDER BY id DESC", params
        ).fetchall()
    finally:
        con.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tech_stack"]  = json.loads(d.get("tech_stack",  "[]"))
        except Exception:
            d["tech_stack"]  = []
        try:
            d["three_point"] = json.loads(d.get("three_point", "{}"))
        except Exception:
            d["three_point"] = {}
        d.pop("results_json", None)
        result.append(d)
    return result


def db_load_results(run_id: int) -> dict:
    """Return the full results_json for a single run (parsed)."""
    con = sqlite3.connect(_DB_PATH)
    try:
        row = con.execute(
            "SELECT results_json FROM proposals WHERE id=?", (run_id,)
        ).fetchone()
    finally:
        con.close()
    if row:
        try:
            return json.loads(row[0])
        except Exception:
            pass
    return {}


def db_delete_run(run_id: int):
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute("DELETE FROM proposals WHERE id=?", (run_id,))
        con.commit()
    finally:
        con.close()


def db_mark_reviewed(run_id: int, notes: str = "", unmark: bool = False, reviewed_by: str = ""):
    """Toggle the architect-reviewed flag for a run."""
    con = sqlite3.connect(_DB_PATH)
    try:
        if unmark:
            con.execute(
                "UPDATE proposals SET architect_reviewed=0, review_ts=NULL, review_notes='', "
                "review_status='pending', reviewed_by='' WHERE id=?",
                (run_id,),
            )
        else:
            con.execute(
                "UPDATE proposals SET architect_reviewed=1, review_ts=?, review_notes=?, "
                "review_status='approved', reviewed_by=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), notes, reviewed_by, run_id),
            )
        con.commit()
    finally:
        con.close()


def db_set_review_status(run_id: int, status: str, notes: str = "", reviewed_by: str = ""):
    """Set review_status: 'pending' | 'approved' | 'needs_changes'."""
    approved = 1 if status == "approved" else 0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M") if status != "pending" else None
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute(
            "UPDATE proposals SET review_status=?, architect_reviewed=?, "
            "review_ts=?, review_notes=?, reviewed_by=? WHERE id=?",
            (status, approved, ts, notes, reviewed_by, run_id),
        )
        con.commit()
    finally:
        con.close()


def db_archive_run(run_id: int):
    """Soft-delete — hidden from library by default."""
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute("UPDATE proposals SET is_archived=1 WHERE id=?", (run_id,))
        con.commit()
    finally:
        con.close()


def db_unarchive_run(run_id: int):
    """Restore an archived run back to active."""
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute("UPDATE proposals SET is_archived=0 WHERE id=?", (run_id,))
        con.commit()
    finally:
        con.close()


def db_category_counts() -> dict:
    """Return {category: count, 'All': total} for the badge pills (excludes archived)."""
    con = sqlite3.connect(_DB_PATH)
    try:
        rows  = con.execute(
            "SELECT category, COUNT(*) as n FROM proposals "
            "WHERE (is_archived IS NULL OR is_archived=0) GROUP BY category"
        ).fetchall()
        total = con.execute(
            "SELECT COUNT(*) FROM proposals WHERE (is_archived IS NULL OR is_archived=0)"
        ).fetchone()[0]
    finally:
        con.close()
    counts = {r[0]: r[1] for r in rows}
    counts["All"] = total
    return counts


def db_update_outcome(run_id: int, outcome: str,
                      actual_hours=None, actual_cost=None, notes: str = ""):
    """Record real-world outcome: 'won' | 'lost' | 'no_bid' | 'pending'."""
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute(
            "UPDATE proposals SET project_outcome=?, actual_hours=?, "
            "actual_cost=?, outcome_notes=? WHERE id=?",
            (outcome, actual_hours, actual_cost, notes, run_id),
        )
        con.commit()
    finally:
        con.close()


def db_check_duplicate(client_name: str, project_type: str, days: int = 7) -> list:
    """Return runs with the same client+project_type within the last N days."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, ts, client_name, project_type, created_by FROM proposals "
            "WHERE (is_archived IS NULL OR is_archived=0) AND ts >= ? "
            "AND LOWER(TRIM(client_name))=? AND LOWER(TRIM(project_type))=? "
            "ORDER BY id DESC LIMIT 5",
            (cutoff, client_name.strip().lower(), project_type.strip().lower()),
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def db_get_lineage(run_id: int) -> list:
    """Walk the parent_run_id chain and return list of ancestor run IDs (oldest last)."""
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    chain, seen = [], set()
    current = run_id
    try:
        while current and current not in seen:
            seen.add(current)
            row = con.execute(
                "SELECT id, ts, project_type, client_name, parent_run_id FROM proposals WHERE id=?",
                (current,),
            ).fetchone()
            if not row:
                break
            chain.append(dict(row))
            current = row["parent_run_id"]
    finally:
        con.close()
    return chain   # index 0 = the run itself, last = oldest ancestor


def db_get_version_chain(run_id: int) -> list:
    """Return all versions of a proposal (root + all children), oldest first.
    Works from any version in the chain — finds the root then walks forward."""
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        # Walk up to find the root (V1 has no parent)
        root_id, seen = run_id, set()
        while True:
            if root_id in seen:
                break
            seen.add(root_id)
            row = con.execute("SELECT parent_run_id FROM proposals WHERE id=?", (root_id,)).fetchone()
            if not row or not row["parent_run_id"]:
                break
            root_id = row["parent_run_id"]
        # Now walk forward: collect all runs whose lineage traces to root_id
        all_rows = con.execute(
            "SELECT id, ts, client_name, project_type, total_hours, monthly_cost, "
            "risk_level, risk_score, review_status, project_outcome, "
            "version_number, version_status, negotiation_stage, "
            "revision_reason_type, revision_notes, parking_lot, "
            "competitor_context, submitted_at, is_winning_version, "
            "is_baseline_locked, parent_run_id, created_by "
            "FROM proposals ORDER BY id ASC"
        ).fetchall()
        # BFS from root to find all descendants
        chain_ids, queue = set(), [root_id]
        while queue:
            cur = queue.pop(0)
            chain_ids.add(cur)
            for r in all_rows:
                if r["parent_run_id"] == cur and r["id"] not in chain_ids:
                    queue.append(r["id"])
        result = [dict(r) for r in all_rows if r["id"] in chain_ids]
        for d in result:
            try: d["parking_lot"] = json.loads(d.get("parking_lot") or "[]")
            except Exception: d["parking_lot"] = []
        return sorted(result, key=lambda x: x["id"])
    finally:
        con.close()


def db_mark_submitted(run_id: int):
    """Mark a version as submitted to the client (sets submitted_at timestamp)."""
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute(
            "UPDATE proposals SET version_status='submitted', submitted_at=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), run_id),
        )
        con.commit()
    finally:
        con.close()


def db_mark_winning_version(run_id: int):
    """Flag this version as the one that won the deal."""
    con = sqlite3.connect(_DB_PATH)
    try:
        # First, clear winning flag from all versions in same chain
        chain = db_get_version_chain(run_id)
        for v in chain:
            con.execute("UPDATE proposals SET is_winning_version=0 WHERE id=?", (v["id"],))
        con.execute("UPDATE proposals SET is_winning_version=1 WHERE id=?", (run_id,))
        con.commit()
    finally:
        con.close()


def db_get_next_version_number(parent_run_id: int) -> int:
    """Return version_number for a new child of parent_run_id."""
    chain = db_get_version_chain(parent_run_id)
    return (max(v.get("version_number", 1) for v in chain) + 1) if chain else 2


# ══════════════════════════════════════════════════════════════════════
#  USER ACTIVITY LOG
# ══════════════════════════════════════════════════════════════════════

def _db_init_activity():
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            user_email  TEXT    DEFAULT '',
            user_name   TEXT    DEFAULT '',
            action      TEXT    DEFAULT '',
            details     TEXT    DEFAULT '',
            module      TEXT    DEFAULT ''
        )
    """)
    con.commit()
    con.close()

_db_init_activity()


def db_log_activity(user_email: str, user_name: str, action: str,
                    details: str = "", module: str = ""):
    """Append one event to the user_activity log (silent on error)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute(
            "INSERT INTO user_activity (ts, user_email, user_name, action, details, module) "
            "VALUES (?,?,?,?,?,?)",
            (ts, user_email or "", user_name or "", action or "",
             details or "", module or ""),
        )
        con.commit()
        con.close()
    except Exception:
        pass


def db_get_activity_log(limit: int = 500, user_email: str = "",
                        action: str = "") -> list:
    """Return activity log entries newest-first, with optional filters."""
    try:
        con = sqlite3.connect(_DB_PATH)
        con.row_factory = sqlite3.Row
        conditions, params = [], []
        if user_email:
            conditions.append("user_email=?"); params.append(user_email)
        if action:
            conditions.append("action=?"); params.append(action)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows  = con.execute(
            f"SELECT * FROM user_activity {where} ORDER BY id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Backwards-compatible aliases ──────────────────────────────────────
_db_save_run        = db_save_run
_db_load_runs       = db_load_runs
_db_load_results    = db_load_results
_db_delete_run      = db_delete_run
_db_mark_reviewed   = db_mark_reviewed
_db_category_counts = db_category_counts

# ── Short-name aliases ────────────────────────────────────────────────
save_run          = db_save_run
load_runs         = db_load_runs
delete_run        = db_delete_run
set_review_status = db_set_review_status
archive_run       = db_archive_run
unarchive_run     = db_unarchive_run
update_outcome    = db_update_outcome
check_duplicate   = db_check_duplicate
get_lineage           = db_get_lineage
log_activity          = db_log_activity
get_activity_log      = db_get_activity_log
get_version_chain     = db_get_version_chain
mark_submitted        = db_mark_submitted
mark_winning_version  = db_mark_winning_version
get_next_version_number = db_get_next_version_number
