# ═══════════════════════════════════════════════════════════════════════
#  PERSISTENT RUN DATABASE  (SQLite — survives page refreshes)
# ═══════════════════════════════════════════════════════════════════════
import os, sqlite3, json
from datetime import datetime

# Store the DB next to the main app file so it persists between Streamlit restarts.
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eci_runs.db")

# Category keyword mapping — used to auto-tag every run
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
    """Return the best-fit category: AI | Data | Cloud | General."""
    combined = (project_type + " " + " ".join(tech_stack or [])).lower()
    scores   = {cat: sum(1 for kw in kws if kw in combined)
                for cat, kws in _CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def _db_init():
    """Create the proposals table if it doesn't exist."""
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
            review_notes      TEXT    DEFAULT ''
        )
    """)
    con.commit()
    con.close()

_db_init()   # run once at import time

# ── Migrate existing databases to add architect-review columns ────────
def _db_migrate():
    con = sqlite3.connect(_DB_PATH)
    existing_cols = {row[1] for row in con.execute("PRAGMA table_info(proposals)").fetchall()}
    for col, ddl in [
        ("architect_reviewed", "INTEGER DEFAULT 0"),
        ("review_ts",          "TEXT    DEFAULT NULL"),
        ("review_notes",       "TEXT    DEFAULT ''"),
        ("client_name",        "TEXT    DEFAULT ''"),
        ("project_title",      "TEXT    DEFAULT ''"),
    ]:
        if col not in existing_cols:
            con.execute(f"ALTER TABLE proposals ADD COLUMN {col} {ddl}")
    con.commit()
    con.close()

_db_migrate()


def db_save_run(snapshot: dict, full_results: dict) -> int:
    """Insert a run into the DB and return its new row id."""
    tech = snapshot.get("tech_stack", [])
    cat  = _detect_category(snapshot.get("project_type", ""), tech)
    con  = sqlite3.connect(_DB_PATH)
    try:
        cur  = con.execute("""
            INSERT INTO proposals
                (ts, category, project_type, client_name, project_title,
                 total_hours, duration_weeks,
                 monthly_cost, annual_cost, risk_level, risk_score,
                 req_count, tech_stack, model_used, three_point, results_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot.get("ts",             datetime.now().strftime("%Y-%m-%d %H:%M")),
            cat,
            snapshot.get("project_type",   ""),
            snapshot.get("client_name",    ""),
            snapshot.get("project_title",  ""),
            snapshot.get("total_hours",    0),
            snapshot.get("duration_weeks", ""),
            snapshot.get("monthly_cost",   0),
            snapshot.get("annual_cost",    0),
            snapshot.get("risk_level",     ""),
            snapshot.get("risk_score",     0),
            snapshot.get("req_count",      0),
            json.dumps(tech),
            snapshot.get("model_used",     ""),
            json.dumps(snapshot.get("three_point", {})),
            json.dumps(full_results, default=str),
        ))
        row_id = cur.lastrowid
        con.commit()
        return row_id
    finally:
        con.close()


def db_load_runs(category: str = "All") -> list:
    """Return list of run dicts (no results_json) newest-first."""
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        if category and category != "All":
            rows = con.execute(
                "SELECT * FROM proposals WHERE category=? ORDER BY id DESC", (category,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM proposals ORDER BY id DESC"
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
        d.pop("results_json", None)   # omit blob from list query
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


def db_mark_reviewed(run_id: int, notes: str = "", unmark: bool = False):
    """Toggle the architect-reviewed flag for a run."""
    con = sqlite3.connect(_DB_PATH)
    try:
        if unmark:
            con.execute(
                "UPDATE proposals SET architect_reviewed=0, review_ts=NULL, review_notes='' WHERE id=?",
                (run_id,),
            )
        else:
            con.execute(
                "UPDATE proposals SET architect_reviewed=1, review_ts=?, review_notes=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), notes, run_id),
            )
        con.commit()
    finally:
        con.close()


def db_category_counts() -> dict:
    """Return {category: count, 'All': total} for the badge pills."""
    con = sqlite3.connect(_DB_PATH)
    try:
        rows = con.execute(
            "SELECT category, COUNT(*) as n FROM proposals GROUP BY category"
        ).fetchall()
        total = con.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
    finally:
        con.close()
    counts = {r[0]: r[1] for r in rows}
    counts["All"] = total
    return counts


# ── Backwards-compatible aliases (used in pipeline/tabs) ──────────────
_db_save_run       = db_save_run
_db_load_runs      = db_load_runs
_db_load_results   = db_load_results
_db_delete_run     = db_delete_run
_db_mark_reviewed  = db_mark_reviewed
_db_category_counts = db_category_counts

# ── Short-name aliases ────────────────────────────────────────────────
save_run   = db_save_run
load_runs  = db_load_runs
delete_run = db_delete_run
