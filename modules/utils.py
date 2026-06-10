# ═══════════════════════════════════════════════════════════════════════
#  HELPERS: Safe data access
# ═══════════════════════════════════════════════════════════════════════

def safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def safe_str(val, default=""):
    if val is None:
        return default
    return str(val)

def safe_list(val):
    if isinstance(val, list):
        return val
    return []

def safe_dict(val):
    if isinstance(val, dict):
        return val
    return {}


# Scope item field mappings — used when items are structured dicts
_SC_FIELDS = {
    "in_scope":      ("title", "description"),
    "out_of_scope":  ("exclusion",),
    "assumptions":   ("statement",),
    "prerequisites": ("item",),
}

def sc_text(item, section: str = "") -> str:
    """Convert a scope item (dict or plain str) to a clean, readable string.

    For in_scope dicts: returns "title: description"
    For other sections: returns the primary field value
    Falls back to str(item) for plain strings or unknown dicts.
    """
    if not isinstance(item, dict):
        return str(item) if item else ""
    fields = _SC_FIELDS.get(section, ())
    if section == "in_scope":
        title = str(item.get("title", "")).strip()
        desc  = str(item.get("description", "")).strip()
        return f"{title}: {desc}" if desc and title else title or desc or str(item)
    for f in fields:
        val = str(item.get(f, "")).strip()
        if val:
            return val
    # fallback: join all non-empty string values
    parts = [str(v).strip() for v in item.values() if v and not str(v).startswith("SC-") and not str(v).startswith("EX-") and not str(v).startswith("AS-") and not str(v).startswith("PR-")]
    return " | ".join(p for p in parts if p) or str(item)
