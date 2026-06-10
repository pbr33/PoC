# ═══════════════════════════════════════════════════════════════════════
#  TEMPLATE LIBRARY  —  Admin-managed reusable content blocks
#
#  Categories:
#    scope_section   — pre-written scope narrative for a project type
#    assumption      — standard assumption per technology
#    risk_mitigation — risk mitigation text per risk category
#    team_bio        — team member bio paragraph per role
# ═══════════════════════════════════════════════════════════════════════
import json
import sqlite3
from datetime import datetime

from .database import _DB_PATH


# ── Category metadata ────────────────────────────────────────────────────
CATEGORIES = {
    "scope_section":   {"label": "Scope Sections",      "icon": "📋", "color": "#00b4d8"},
    "assumption":      {"label": "Assumptions",          "icon": "💡", "color": "#7b61ff"},
    "risk_mitigation": {"label": "Risk Mitigations",     "icon": "⚠️", "color": "#ffd166"},
    "team_bio":        {"label": "Team Bios",             "icon": "👤", "color": "#00d4aa"},
}

PROJECT_TYPES = [
    "AI / Machine Learning", "Data & Analytics", "Cloud Migration",
    "Web Application", "Mobile Application", "SharePoint / M365",
    "Integration / API", "DevOps / CI-CD", "Security", "General",
]

RISK_CATEGORIES = [
    "Technical Complexity", "Timeline / Schedule", "Resource Availability",
    "Budget Overrun", "Third-party Dependencies", "Data Migration",
    "Security & Compliance", "Change Management", "Vendor Risk", "General",
]

ROLES = [
    "Solution Architect", "Lead Developer", "Senior Developer",
    "Junior Developer", "QA Engineer", "DevOps Engineer",
    "Project Manager", "Business Analyst", "Data Engineer",
    "ML Engineer", "Security Engineer", "Scrum Master",
]

TECHNOLOGIES = [
    "Azure OpenAI", "Azure Data Factory", "Azure Kubernetes Service",
    "Azure SQL", "Cosmos DB", "Azure DevOps", "SharePoint",
    "Power BI", "Python", "React", ".NET", "Node.js",
    "Terraform", "Docker", "Power Platform", "General",
]


# ── DB init ──────────────────────────────────────────────────────────────
def _tpl_init():
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            tags        TEXT    NOT NULL DEFAULT '[]',
            content     TEXT    NOT NULL DEFAULT '',
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_by  TEXT    NOT NULL DEFAULT 'Admin',
            updated_ts  TEXT    NOT NULL DEFAULT ''
        )
    """)
    con.commit()
    con.close()
    _seed_defaults()


def _seed_defaults():
    """Insert built-in templates if the table is empty."""
    con = sqlite3.connect(_DB_PATH)
    count = con.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    con.close()
    if count > 0:
        return  # already seeded

    _defaults = [
        # ── Scope Sections ──────────────────────────────────────────────
        {
            "category": "scope_section",
            "title": "AI / ML Project Overview",
            "tags": ["AI / Machine Learning", "Azure OpenAI", "Python"],
            "content": (
                "This engagement covers the design, development, and deployment of an AI-powered "
                "solution leveraging Azure OpenAI and associated cognitive services. The scope "
                "includes data preparation, model integration, API layer development, user interface "
                "delivery, and production deployment with monitoring and alerting configured via "
                "Azure Monitor and Application Insights. ECI will follow the Microsoft Well-Architected "
                "Framework throughout, ensuring security, reliability, and cost optimisation at every layer."
            ),
        },
        {
            "category": "scope_section",
            "title": "Data & Analytics Platform Overview",
            "tags": ["Data & Analytics", "Azure Data Factory", "Power BI"],
            "content": (
                "This engagement delivers a modern data platform on Azure, encompassing ingestion "
                "pipelines (Azure Data Factory), transformation layers, a centralised data lake "
                "(Azure Data Lake Storage Gen2), and self-service analytics via Power BI. ECI will "
                "implement medallion architecture (Bronze / Silver / Gold) with full lineage tracking, "
                "role-based access control, and automated data quality checks. Deliverables include "
                "documented pipelines, semantic models, and a training session for the client's BI team."
            ),
        },
        {
            "category": "scope_section",
            "title": "Cloud Migration Overview",
            "tags": ["Cloud Migration", "Azure Kubernetes Service", "Terraform"],
            "content": (
                "ECI will lead the end-to-end migration of identified workloads to Microsoft Azure "
                "using the Cloud Adoption Framework. The engagement covers discovery and assessment, "
                "landing zone configuration, workload migration (lift-and-shift and re-platform where "
                "appropriate), post-migration validation, and handover documentation. Infrastructure "
                "will be defined as code using Terraform, enabling repeatable deployments across "
                "development, staging, and production environments."
            ),
        },
        {
            "category": "scope_section",
            "title": "SharePoint / M365 Intranet Overview",
            "tags": ["SharePoint / M365"],
            "content": (
                "This project delivers a modern SharePoint Online intranet leveraging Microsoft 365 "
                "capabilities including Teams integration, Viva Connections, and Power Automate "
                "workflows. ECI will design the information architecture, configure site collections, "
                "implement custom web parts where required, and migrate content from the existing "
                "platform. The solution includes governance documentation and end-user training "
                "to ensure long-term adoption."
            ),
        },

        # ── Assumptions ──────────────────────────────────────────────────
        {
            "category": "assumption",
            "title": "Azure OpenAI — API Access",
            "tags": ["Azure OpenAI", "AI / Machine Learning"],
            "content": (
                "The client has an active Azure subscription with Azure OpenAI service enabled and "
                "quota approved for the required model (GPT-4o or equivalent). Any delays in quota "
                "approval from Microsoft may impact the project timeline and are outside ECI's control."
            ),
        },
        {
            "category": "assumption",
            "title": "Data Availability & Quality",
            "tags": ["Data & Analytics", "Azure Data Factory"],
            "content": (
                "Source data is accessible via agreed connectors or export mechanisms by the agreed "
                "project start date. Data quality remediation beyond the agreed cleansing scope will "
                "be treated as a change request. The client will provide a data owner to validate "
                "transformation logic and approve semantic models."
            ),
        },
        {
            "category": "assumption",
            "title": "Client Environments & Access",
            "tags": ["General"],
            "content": (
                "The client will provision necessary development and staging environments prior to "
                "the project start date. ECI engineers will be granted appropriate access (Azure AD "
                "roles, DevOps pipelines, repository access) within the first week of the engagement. "
                "Delays in access provisioning will be logged as risks and may require timeline adjustment."
            ),
        },
        {
            "category": "assumption",
            "title": "Microsoft 365 Licensing",
            "tags": ["SharePoint / M365"],
            "content": (
                "The client holds valid Microsoft 365 E3 or E5 licences covering all named users "
                "in scope. Premium features requiring additional licensing (e.g., Viva Suite, Power "
                "BI Premium) are the client's responsibility to procure unless explicitly included "
                "in the ECI commercial proposal."
            ),
        },
        {
            "category": "assumption",
            "title": "Terraform State Management",
            "tags": ["Terraform", "Cloud Migration", "DevOps / CI-CD"],
            "content": (
                "Terraform state will be stored in Azure Blob Storage with state locking via Azure "
                "Cosmos DB or Azure Storage native locking. The client will create the state storage "
                "account prior to infrastructure provisioning. ECI will not be responsible for state "
                "corruption resulting from manual changes made outside the agreed Terraform workflow."
            ),
        },

        # ── Risk Mitigations ─────────────────────────────────────────────
        {
            "category": "risk_mitigation",
            "title": "Technical Complexity — AI Integration",
            "tags": ["Technical Complexity", "AI / Machine Learning"],
            "content": (
                "ECI will conduct a technical spike in Week 1 to validate the AI integration approach "
                "and identify any model limitations early. A fallback architecture using Azure AI "
                "Studio with a smaller model will be prepared in parallel. Weekly technical reviews "
                "with the client's architecture team will ensure early identification and resolution "
                "of blockers."
            ),
        },
        {
            "category": "risk_mitigation",
            "title": "Timeline Risk — Phased Delivery",
            "tags": ["Timeline / Schedule"],
            "content": (
                "To reduce timeline risk, delivery is structured in independently deployable phases. "
                "Phase 1 delivers a minimum viable product that provides immediate business value, "
                "with subsequent phases building additional capability. This approach ensures the "
                "client receives value even if later phases require timeline adjustment. A dedicated "
                "project manager will track milestones weekly and escalate blockers within 24 hours."
            ),
        },
        {
            "category": "risk_mitigation",
            "title": "Data Migration Risk",
            "tags": ["Data Migration"],
            "content": (
                "A data migration runbook will be produced and rehearsed in the staging environment "
                "a minimum of two weeks before production cutover. Data reconciliation reports will "
                "be generated pre- and post-migration. A rollback plan will be agreed and documented "
                "before any production migration activity begins. A 48-hour hypercare window "
                "post-migration will be staffed by the ECI data lead."
            ),
        },
        {
            "category": "risk_mitigation",
            "title": "Third-party Dependency Risk",
            "tags": ["Third-party Dependencies"],
            "content": (
                "All third-party APIs, services, and vendor dependencies have been identified and "
                "are logged in the project RAID log. Integration contracts (API specifications, "
                "SLAs) will be agreed with third parties before development begins. Where a third "
                "party is unable to meet agreed timelines, ECI will implement a mock/stub layer to "
                "allow parallel development to continue unblocked."
            ),
        },
        {
            "category": "risk_mitigation",
            "title": "Security & Compliance Risk",
            "tags": ["Security & Compliance"],
            "content": (
                "ECI will conduct a security design review at the architecture stage before any "
                "development begins. All credentials and secrets will be stored in Azure Key Vault "
                "with no hardcoded values in source code. Data in transit will be encrypted via "
                "TLS 1.2+ and data at rest via AES-256. A penetration test will be commissioned "
                "prior to production go-live if required by the client's security policy."
            ),
        },
        {
            "category": "risk_mitigation",
            "title": "Change Management & Adoption Risk",
            "tags": ["Change Management"],
            "content": (
                "ECI recommends establishing a change champion network within the client organisation "
                "prior to go-live. End-user training will be delivered in small cohorts with "
                "role-specific guides produced for each user group. A feedback mechanism will be "
                "embedded in the solution during the first 30 days post-launch to capture adoption "
                "issues early and allow rapid iteration."
            ),
        },

        # ── Team Bios ────────────────────────────────────────────────────
        {
            "category": "team_bio",
            "title": "Solution Architect",
            "tags": ["Solution Architect"],
            "content": (
                "Our Solution Architect brings over 12 years of experience designing enterprise-grade "
                "cloud solutions on Microsoft Azure, holding Microsoft Certified: Azure Solutions "
                "Architect Expert certification. They will own the technical vision for this "
                "engagement, conduct architecture reviews at each phase gate, and be the primary "
                "point of escalation for technical decisions. Their track record includes successful "
                "delivery of 40+ Azure projects across Financial Services, Healthcare, and Retail sectors."
            ),
        },
        {
            "category": "team_bio",
            "title": "Lead Developer",
            "tags": ["Lead Developer"],
            "content": (
                "Our Lead Developer is a full-stack engineer with deep expertise in Python, .NET, "
                "and Azure PaaS services. With 8 years of professional experience including 4 years "
                "specialising in cloud-native development, they will be responsible for core "
                "component delivery, code quality standards, and mentoring junior team members. "
                "They are an active contributor to open-source projects and hold the Microsoft "
                "Certified: Azure Developer Associate certification."
            ),
        },
        {
            "category": "team_bio",
            "title": "Data Engineer",
            "tags": ["Data Engineer"],
            "content": (
                "Our Data Engineer specialises in building scalable data pipelines and lake house "
                "architectures on Azure. With expertise in Azure Data Factory, Databricks, dbt, "
                "and Azure Synapse Analytics, they will design and implement the data ingestion, "
                "transformation, and serving layers for this engagement. They hold the Microsoft "
                "Certified: Azure Data Engineer Associate certification and have delivered data "
                "platforms processing in excess of 10 TB daily in production."
            ),
        },
        {
            "category": "team_bio",
            "title": "ML Engineer",
            "tags": ["ML Engineer"],
            "content": (
                "Our ML Engineer combines software engineering rigour with deep expertise in machine "
                "learning and large language model integration. Experienced with Azure OpenAI, "
                "Azure Machine Learning, and the Hugging Face ecosystem, they will lead model "
                "selection, prompt engineering, RAG pipeline design, and LLMOps practices for this "
                "engagement. They hold a Master's degree in Computer Science with a focus on "
                "Natural Language Processing."
            ),
        },
        {
            "category": "team_bio",
            "title": "Project Manager",
            "tags": ["Project Manager"],
            "content": (
                "Our Project Manager is a PMP-certified delivery professional with 10+ years "
                "leading complex technology programmes for enterprise clients. They will be "
                "responsible for project governance, stakeholder communication, risk and issue "
                "management, and ensuring deliverables are met on time and within budget. "
                "They operate an agile delivery model with two-week sprints, weekly steering "
                "updates, and a transparent RAID log accessible to all stakeholders."
            ),
        },
        {
            "category": "team_bio",
            "title": "DevOps Engineer",
            "tags": ["DevOps Engineer"],
            "content": (
                "Our DevOps Engineer is an infrastructure-as-code specialist with extensive "
                "experience in Azure DevOps, GitHub Actions, Terraform, and Kubernetes. They "
                "will design and implement the CI/CD pipelines, environment management strategy, "
                "and observability stack for this engagement. They hold the Microsoft Certified: "
                "DevOps Engineer Expert certification and have a strong background in SRE practices "
                "including SLO definition, incident management, and chaos engineering."
            ),
        },
    ]

    for t in _defaults:
        _add_template(
            category=t["category"],
            title=t["title"],
            tags=t["tags"],
            content=t["content"],
            created_by="System",
        )


# ── CRUD ─────────────────────────────────────────────────────────────────
def _add_template(category: str, title: str, tags: list, content: str, created_by: str = "Admin") -> int:
    con = sqlite3.connect(_DB_PATH)
    try:
        cur = con.execute(
            "INSERT INTO templates (ts, category, title, tags, content, created_by, updated_ts) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                category, title,
                json.dumps(tags),
                content,
                created_by,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        new_id = cur.lastrowid
        con.commit()
        return new_id
    finally:
        con.close()


def add_template(category: str, title: str, tags: list, content: str, created_by: str = "Admin") -> int:
    return _add_template(category, title, tags, content, created_by)


def get_templates(category: str = None, active_only: bool = True) -> list:
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        if category:
            rows = con.execute(
                "SELECT * FROM templates WHERE category=? AND is_active>=? ORDER BY title",
                (category, 1 if active_only else 0),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM templates WHERE is_active>=? ORDER BY category, title",
                (1 if active_only else 0,),
            ).fetchall()
    finally:
        con.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags", "[]"))
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


def update_template(template_id: int, title: str, tags: list, content: str, is_active: bool = True):
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute(
            "UPDATE templates SET title=?, tags=?, content=?, is_active=?, updated_ts=? WHERE id=?",
            (title, json.dumps(tags), content, 1 if is_active else 0,
             datetime.now().strftime("%Y-%m-%d %H:%M"), template_id),
        )
        con.commit()
    finally:
        con.close()


def delete_template(template_id: int):
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute("DELETE FROM templates WHERE id=?", (template_id,))
        con.commit()
    finally:
        con.close()


# ── Matching engine ──────────────────────────────────────────────────────
def find_matching_templates(
    project_type: str = "",
    tech_stack: list = None,
    risk_level: str = "",
) -> dict:
    """
    Return a dict keyed by category with a list of matching template dicts.
    Matching is tag-based: a template matches if any of its tags appear in
    the normalised project type string or tech stack list.

    Returns:
        {
          "scope_section":   [template, ...],
          "assumption":      [template, ...],
          "risk_mitigation": [template, ...],
          "team_bio":        [template, ...],
        }
    """
    tech_stack = tech_stack or []
    all_tpls = get_templates(active_only=True)

    # Build a set of terms to match against
    project_lower = project_type.lower()
    tech_lower    = {t.lower() for t in tech_stack}

    # Map friendly project types → keywords for matching
    _PT_KEYWORDS = {
        "ai / machine learning": ["ai", "machine learning", "openai", "ml", "gpt", "llm", "cognitive"],
        "data & analytics":      ["data", "analytics", "bi", "power bi", "warehouse", "etl"],
        "cloud migration":       ["cloud", "migration", "azure", "lift", "shift"],
        "web application":       ["web", "application", "react", ".net", "node"],
        "sharepoint / m365":     ["sharepoint", "m365", "office", "teams", "viva"],
        "integration / api":     ["integration", "api", "service bus", "function", "logic app"],
        "devops / ci-cd":        ["devops", "ci/cd", "pipeline", "terraform", "docker", "kubernetes"],
        "security":              ["security", "compliance", "penetration", "soc"],
        "general":               [],
    }

    def _score(template: dict) -> int:
        tags_lower = {t.lower() for t in template.get("tags", [])}
        score = 0

        # Match against project type keywords
        for pt_key, kws in _PT_KEYWORDS.items():
            if pt_key in project_lower or any(k in project_lower for k in kws):
                if any(t in tags_lower for t in [pt_key] + kws):
                    score += 3

        # Match against tech stack
        for tech in tech_lower:
            if any(tech in tag.lower() for tag in template.get("tags", [])):
                score += 2

        # "General" templates always included at low score
        if "general" in tags_lower:
            score += 1

        return score

    matched: dict = {cat: [] for cat in CATEGORIES}

    for tpl in all_tpls:
        cat = tpl.get("category")
        if cat not in matched:
            continue
        s = _score(tpl)
        if s > 0:
            tpl["_score"] = s
            matched[cat].append(tpl)

    # Sort each category by score descending, take top 3
    for cat in matched:
        matched[cat] = sorted(matched[cat], key=lambda x: x["_score"], reverse=True)[:3]

    return matched


def format_templates_for_prompt(matched: dict) -> str:
    """
    Render the matched templates as a structured text block suitable for
    injection into an LLM system prompt.
    """
    lines = ["=== PRE-APPROVED CONTENT BLOCKS ===",
             "Use the following human-approved content as grounding material.",
             "Incorporate these sections verbatim or adapt them to fit the specific proposal context.",
             "Do NOT hallucinate content that contradicts these blocks.",
             ""]

    labels = {
        "scope_section":   "SCOPE SECTIONS",
        "assumption":      "STANDARD ASSUMPTIONS",
        "risk_mitigation": "RISK MITIGATION STATEMENTS",
        "team_bio":        "TEAM BIOS",
    }

    has_content = False
    for cat, label in labels.items():
        items = matched.get(cat, [])
        if not items:
            continue
        has_content = True
        lines.append(f"--- {label} ---")
        for t in items:
            lines.append(f"[{t['title']}]")
            lines.append(t["content"])
            lines.append("")

    if not has_content:
        return ""

    return "\n".join(lines)


# ── Run init on import ───────────────────────────────────────────────────
_tpl_init()
