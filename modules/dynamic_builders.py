# ═══════════════════════════════════════════════════════════════════════
#  DYNAMIC ESTIMATE BUILDERS
# ═══════════════════════════════════════════════════════════════════════
from .utils import safe_int, safe_str, safe_list, safe_dict
from .text_analysis import _INFRA_COST_CATALOG, _TECH_CATALOG, _analyze_text_dynamic


def _split_large_task(name, hours, role, justification):
    """Split a task > 8 hours into granular 4-8h sub-tasks for justifiable estimates."""
    name_short = name[:45]
    name_lower = name.lower()

    if any(k in name_lower for k in ["design", "architect", "blueprint"]):
        splits = [
            ("Requirements analysis: " + name_short, 0.35, role, "Analyze requirements and constraints"),
            ("Design document: " + name_short, 0.35, role, "Create detailed design specification"),
            ("Design review and sign-off: " + name_short, 0.30, role, "Peer review, feedback, approval"),
        ]
    elif any(k in name_lower for k in ["test", "qa", "validation", "uat"]):
        splits = [
            ("Test plan and case design: " + name_short, 0.25, role, "Define test scenarios and acceptance criteria"),
            ("Test environment setup: " + name_short, 0.15, role, "Configure test environment and data"),
            ("Test execution: " + name_short, 0.35, role, "Execute test cases, log results"),
            ("Defect validation and reporting: " + name_short, 0.25, role, "Verify fixes, generate test report"),
        ]
    elif any(k in name_lower for k in ["deploy", "release", "provision", "infra"]):
        splits = [
            ("Environment configuration: " + name_short, 0.30, role, "Setup and configure environment"),
            ("Deployment execution: " + name_short, 0.35, role, "Deploy artifacts, run migrations"),
            ("Smoke testing and verification: " + name_short, 0.20, role, "Post-deployment validation"),
            ("Runbook and documentation: " + name_short, 0.15, role, "Document steps and rollback procedures"),
        ]
    elif any(k in name_lower for k in ["integrate", "api", "connector", "migration"]):
        splits = [
            ("Integration design: " + name_short, 0.20, role, "Define API contracts, data mapping"),
            ("Connector development: " + name_short, 0.35, role, "Build integration adapter and handlers"),
            ("Error handling and retry logic: " + name_short, 0.20, role, "Implement fault tolerance"),
            ("Integration testing: " + name_short, 0.25, role, "Validate end-to-end data flow"),
        ]
    elif any(k in name_lower for k in ["ai", "ml", "model", "pipeline", "rag", "prompt"]):
        splits = [
            ("Model/pipeline design: " + name_short, 0.25, role, "Architecture and approach selection"),
            ("Implementation: " + name_short, 0.35, role, "Core development and configuration"),
            ("Testing and tuning: " + name_short, 0.25, role, "Quality validation and optimization"),
            ("Documentation: " + name_short, 0.15, role, "Technical documentation"),
        ]
    elif any(k in name_lower for k in ["document", "training", "guide", "knowledge"]):
        splits = [
            ("Content planning: " + name_short, 0.25, role, "Outline structure and content plan"),
            ("Content creation: " + name_short, 0.45, role, "Write and format documentation"),
            ("Review and finalize: " + name_short, 0.30, role, "Peer review and final edits"),
        ]
    else:
        splits = [
            ("Technical design: " + name_short, 0.20, role, "Detailed design and approach — " + justification),
            ("Development: " + name_short, 0.35, role, "Core implementation — " + justification),
            ("Unit tests: " + name_short, 0.20, role, "Automated test coverage"),
            ("Code review and refactor: " + name_short, 0.15, role, "Peer review and address feedback"),
            ("Integration validation: " + name_short, 0.10, role, "Verify integration with other components"),
        ]

    result = []
    remaining = hours
    for i, (sub_name, pct, sub_role, sub_just) in enumerate(splits):
        if i == len(splits) - 1:
            sub_hrs = remaining
        else:
            sub_hrs = max(2, min(8, round(hours * pct)))
            remaining -= sub_hrs
        while sub_hrs > 8:
            chunk = 8
            result.append({
                "name": sub_name + " (part " + str(len(result) + 1) + ")",
                "hours": chunk,
                "low_hours": int(chunk * 0.8),
                "high_hours": int(chunk * 1.35),
                "role": sub_role,
                "justification": sub_just,
            })
            sub_hrs -= chunk
        if sub_hrs > 0:
            result.append({
                "name": sub_name,
                "hours": sub_hrs,
                "low_hours": int(sub_hrs * 0.8),
                "high_hours": int(sub_hrs * 1.35),
                "role": sub_role,
                "justification": sub_just,
            })
    return result


def _tech_multiplier(tech_lower: str) -> float:
    """Return a composite complexity multiplier for the detected tech stack."""
    mult = 1.0
    if any(k in tech_lower for k in ["microsoft fabric", "fabric lakehouse", "onelake"]):
        mult *= 1.40
    elif any(k in tech_lower for k in ["azure databricks", "databricks", "delta lake"]):
        mult *= 1.50
    elif any(k in tech_lower for k in ["azure synapse", "synapse analytics"]):
        mult *= 1.30
    if any(k in tech_lower for k in ["azure data factory", "data factory", " adf "]):
        mult *= 1.15
    if any(k in tech_lower for k in ["azure machine learning", "azure ml"]):
        mult *= 1.20
    if any(k in tech_lower for k in ["azure openai", "openai", "gpt", "ai foundry", "foundry", "llm"]):
        mult *= 1.20
    if any(k in tech_lower for k in ["kubernetes", "aks", "container"]):
        mult *= 1.15
    if any(k in tech_lower for k in ["private endpoint", "private network", "vnet integration"]):
        mult *= 1.10
    return round(min(mult, 2.8), 2)   # cap composite at 2.8×


def _task(name, role, hrs, just="", mult=1.0):
    h = max(2, round(hrs * mult))
    return {"name": name, "role": role, "hours": h,
            "low_hours": max(1, round(h * 0.75)), "high_hours": round(h * 1.40),
            "justification": just}


def _stream(name, domain, tasks, mult=1.0, parallel_with=None):
    """Wrap a list of tasks into a work-stream phase dict."""
    total = round(sum(t["hours"] for t in tasks) * mult)
    weeks = round(total / 40, 1)
    return {
        "name": name, "domain": domain,
        "hours": total,
        "low_hours": round(total * 0.75), "high_hours": round(total * 1.40),
        "percentage": "",
        "week_label": f"{weeks:.0f}w",
        "duration_weeks": weeks,
        "complexity_multiplier": round(mult, 2),
        "runs_parallel_with": parallel_with or [],
        "tasks": tasks,
    }


def _build_dynamic_time(semantic, text="", rag=None):
    """Domain-aware parallel-stream time estimator with per-tech complexity multipliers."""
    reqs            = safe_list(semantic.get("requirements"))
    mandated        = safe_list(semantic.get("mandated_technologies", []))
    all_tech        = safe_list(semantic.get("technology_stack", []))
    source_sys      = set(safe_list(semantic.get("source_systems", [])))
    domains         = safe_list(semantic.get("project_domains", []))
    complexity      = safe_int(semantic.get("complexity_score", 5))
    engagement_type = safe_str(semantic.get("engagement_type", "Implementation"))
    _discovery_only = (engagement_type == "Discovery")

    # ── Domain and tech detection ─────────────────────────────────────────
    tech_lower = " ".join(mandated + all_tech).lower()
    M = _tech_multiplier(tech_lower)   # composite project multiplier

    n_func  = len([r for r in reqs if isinstance(r, dict) and r.get("type") == "functional"])
    n_nf    = len([r for r in reqs if isinstance(r, dict) and r.get("type") == "non-functional"])
    n_int   = len([r for r in reqs if isinstance(r, dict) and r.get("type") == "integration"])
    n_total = max(1, len(reqs))

    # ── Classify functional reqs: AI/ML feature vs DevOps/infra ──────────
    _DEVOPS_REQ_KEYS = (
        "private endpoint", "key vault", "entra", "entra id", "encryption",
        "cspm", "deploy resource", "deploy to prod", "production environment",
        "network security", "log ingestion", "log analytics", "security baseline",
        "prompt log", "configure private", "create secret", "rbac", "ssl", "tls",
        "firewall", "nsg", "vnet", "defender", "compliance policy", "key rotation",
        "backup", "disaster recovery", "monitoring alert", "log retention",
    )
    def _is_devops_req(r_dict):
        tl = safe_str(r_dict.get("title", "")).lower()
        dl = safe_str(r_dict.get("description", "")).lower()
        return any(k in tl or k in dl for k in _DEVOPS_REQ_KEYS)

    _devops_reqs = [
        safe_dict(r) for r in reqs
        if isinstance(r, dict) and r.get("type") == "functional" and _is_devops_req(safe_dict(r))
    ]

    def _h(k): return k in tech_lower
    # Also scan raw scope text for keywords the AI may have missed in tech_stack
    _text_lower = (text or "").lower()
    def _th(k): return k in tech_lower or k in _text_lower

    is_fabric     = _h("microsoft fabric") or _h("fabric lakehouse") or _h("onelake")
    is_databricks = _h("azure databricks") or _h("databricks")
    is_synapse    = _h("azure synapse") or _h("synapse analytics")
    is_adf        = _h("azure data factory") or _h("data factory")
    is_adls       = _h("adls") or _h("data lake storage")
    is_data_eng   = is_fabric or is_databricks or is_synapse or is_adf or is_adls or \
                    "Data Engineering" in " ".join(domains) or \
                    any(k in tech_lower for k in [
                        "data warehouse", "dwh", "sql server", "azure sql",
                        "sql dw", "azure synapse", "data lake", "data platform",
                        "data mart", "medallion",
                    ])
    is_ai         = _h("azure openai") or _h("openai") or _h("gpt") or _h("ai foundry") or \
                    _h("foundry") or _h("llm") or _h("ai search") or _h("azure ml") or \
                    "AI / ML" in " ".join(domains)
    is_rag        = _h("ai search") or _h("rag") or _h("vector") or _h("embedding")
    is_teams      = _h("microsoft teams") or _h("teams bot") or _h("teams app")
    # SharePoint: ONLY fire when tech stack explicitly says "sharepoint".
    # The domains list can misclassify AI/data projects — never use it alone.
    is_sharepoint = _h("sharepoint")
    is_custom_app = _h("react") or _h("angular") or _h("app service") or _h("fastapi") or \
                    _h(".net") or _h("blazor")
    is_devops     = _h("devops") or _h("ci/cd") or _h("kubernetes") or _h("github actions")
    has_multi_env = "two environment" in " ".join(
        safe_str(r.get("description","")) for r in reqs if isinstance(r,dict)
    ).lower() or "dev/test" in tech_lower

    # ── Power Platform Developer stream ───────────────────────────────────
    # Only fires on explicit Power Platform / RPA keywords in tech or scope text.
    # "platform", "automate", "app" alone are too generic — require compound phrase.
    is_power_platform = _th("power automate") or _th("power apps") or \
                        _th("power platform") or _th("rpa") or \
                        _th("automate desktop") or _th("canvas app") or \
                        _th("model-driven app") or _th("model driven app")

    # ── Visualization Developer stream ─────────────────────────────────────
    # Only fires on explicit BI tool names. Generic words like "dashboard",
    # "analytics", "reporting" would fire on almost every AI project — excluded.
    is_visualization  = _th("power bi") or _th("bi report") or _th("bi dashboard") or \
                        _th("tableau") or _th("qlik") or _th("looker") or \
                        any(k in tech_lower for k in ["power bi", "bi reporting", "bi dashboard"])

    # ── User-selected project type overrides (UI multiselect takes priority) ─
    # If the user explicitly chose a project type, force the matching stream flag
    # even when the document's tech stack doesn't mention the right keywords.
    _upt = [t.strip().lower() for t in safe_list(semantic.get("project_type_tags", []))]
    if _upt:
        if any(t in ("ai", "ai/ml", "ml") for t in _upt):
            is_ai = True
        if any(t in ("data",) for t in _upt):
            is_data_eng = True
            is_visualization = True   # data projects almost always include dashboards
        if any(t in ("sharepoint",) for t in _upt):
            is_sharepoint = True
        if any(t in ("custom app", "app") for t in _upt):
            is_custom_app = True   # remove the tech-keyword requirement
        if any(t in ("cloud",) for t in _upt):
            is_devops = True       # Cloud type = enhanced DevOps & Platform stream

    # Shared source-count: prefer actual source_systems list; fall back to integration req count
    n_src = max(1, len(source_sys)) if source_sys else max(1, n_int)

    # ── PARALLEL WORK STREAMS ────────────────────────────────────────────
    streams: list[dict] = []

    # ── Stream 0: Discovery & Design — complexity-scaled ────────────────
    # Simpler projects skip ceremony overhead; complex ones get full rigour
    _disc_scale = 0.65 if complexity <= 4 else 0.85 if complexity <= 6 else 1.0
    disc_tasks = [
        _task("Stakeholder kickoff meeting",              "PM",        max(2, int(4  * _disc_scale)), "Initial alignment with sponsors and team"),
        _task("Requirements elicitation workshops",       "BA",        max(3, int(min(10, n_total)   * _disc_scale)), str(n_total) + " requirements"),
        _task("Requirements documentation",               "BA",        max(2, int(min(8,  n_func)    * _disc_scale)), str(n_func) + " functional reqs"),
        _task("Scope and gap analysis",                   "BA",        max(2, int(min(6,  n_total // 2 + 1) * _disc_scale)), "Identify gaps vs scope"),
        _task("Solution architecture design",             "Architect", max(4, int(min(12, len(all_tech) + 2) * _disc_scale)), str(len(all_tech)) + " technologies"),
        _task("Architecture review and sign-off",         "Architect", max(2, int(4  * _disc_scale)), "Peer review, stakeholder walkthrough, formal sign-off"),
        _task("Security and compliance assessment",       "Security",  max(2, int(min(8,  n_nf)      * _disc_scale)), str(n_nf) + " non-func reqs"),
        _task("Risk identification and mitigation plan",  "PM",        max(2, int(3  * _disc_scale)), "Risk register, response strategies"),
    ]
    streams.append(_stream("Discovery & Design", "Discovery", disc_tasks, mult=1.0))

    # ── Stream 1: Data Engineering ────────────────────────────────────────
    if is_data_eng:
        de_tasks: list[dict] = []

        if is_fabric:
            de_tasks += [
                _task("Microsoft Fabric capacity and workspace provisioning", "Data Engineer", 8,  "Capacity SKU, workspace config, admin settings"),
                _task("OneLake setup — container hierarchy and RBAC",         "Data Engineer", 6,  "Folder structure, managed identity, workspace roles"),
                _task("Network security — Managed VNET and private endpoints","Data Engineer", 4,  "Fabric managed VNET, private links to source systems"),
            ]
            for i in range(min(n_src, 6)):
                lbl = f"Source {i + 1}"
                de_tasks += [
                    _task(f"Pipeline design and schema mapping — {lbl}",    "Data Engineer", 5,  "Schema analysis, data mapping, ingestion strategy"),
                    _task(f"Fabric Data Factory pipeline — {lbl}",          "Data Engineer", 7,  "Copy activities, incremental load, scheduling, error handling"),
                    _task(f"Bronze layer validation — {lbl}",               "Data Engineer", 3,  "Raw data quality checks, schema validation"),
                ]
            de_tasks += [
                _task("Silver layer: data cleansing and standardisation",   "Data Engineer", 8,  "Business rules, deduplication, type casting"),
                _task("Silver layer: entity resolution and key mapping",    "Data Engineer", 6,  "Surrogate keys, reference data linking"),
                _task("Gold layer: aggregations and KPI calculations",      "Data Engineer", 8,  "Metrics, rollups, partitioning strategy"),
                _task("Gold layer: business entity models",                 "Data Engineer", 8,  "Dimensional model, conformed dimensions"),
                _task("Fabric Semantic Model — measures and hierarchies",   "Data Engineer", 10, "DAX measures, hierarchies, KPIs"),
                _task("Power BI report development",                        "Data Engineer", 8,  "Dashboard design, visualisations, drillthrough"),
                _task("Row-Level Security and data access policies",        "Data Engineer", 6,  "RLS rules, workspace roles, sensitivity labels"),
                _task("Data quality monitoring — rules and alerting",       "Data Engineer", 8,  "DQ expectations, Purview, alerting pipelines"),
                _task("Pipeline performance tuning and optimisation",       "Data Engineer", 6,  "V-order, partition pruning, caching"),
                _task("End-to-end data flow testing and reconciliation",    "Data Engineer", 8,  "Full pipeline test, row count validation"),
            ]
        elif is_databricks:
            de_tasks += [
                _task("Databricks workspace provisioning and cluster config",  "Data Engineer", 8,  "Cluster policies, Unity Catalog, RBAC"),
                _task("Auto Loader / ADF ingestion pipeline design",           "Data Engineer", 12, "Streaming ingestion, schema inference, checkpoints"),
            ]
            for i in range(min(n_src, 4)):
                de_tasks.append(_task(f"Source pipeline — source {i + 1}", "Data Engineer", 6, "End-to-end ingestion pipeline per source"))
            de_tasks += [
                _task("Delta Lake Bronze-to-Silver transforms (PySpark)",   "Data Engineer", 8,  "Business rules, deduplication, normalisation"),
                _task("Delta Lake Silver-to-Gold aggregations",             "Data Engineer", 10, "KPI calcs, analytical aggregations"),
                _task("Delta Live Tables DQ expectations",                  "Data Engineer", 8,  "Data quality rules, monitoring"),
                _task("Feature store and ML-ready datasets",                "Data Engineer", 8,  "Feature engineering, train/test splits"),
                _task("Performance tuning — ZORDER, caching, compaction",   "Data Engineer", 6,  "Query performance, partition strategy"),
                _task("End-to-end pipeline testing",                        "Data Engineer", 8,  "Pipeline tests, data reconciliation"),
            ]
        elif is_synapse:
            de_tasks += [
                _task("Synapse workspace provisioning",                     "Data Engineer", 8,  "Dedicated/serverless pool, RBAC, linked services"),
                _task("Synapse Pipeline design and implementation",         "Data Engineer", 12, "Copy activities, mapping dataflows, triggers"),
            ]
            for i in range(min(n_src, 4)):
                de_tasks.append(_task(f"Source integration — source {i + 1}", "Data Engineer", 6, "End-to-end integration"))
            de_tasks += [
                _task("SQL pool schema design and DDL",                     "Data Engineer", 6,  "Distributions, indexing, partition strategy"),
                _task("Data transformation stored procedures",              "Data Engineer", 8,  "Business logic, ETL procedures"),
                _task("Reporting layer and external tables",                "Data Engineer", 8,  "Power BI connectivity, external table setup"),
                _task("End-to-end testing and reconciliation",              "Data Engineer", 8,  "Data validation, row counts, business logic"),
            ]
        else:   # ADF / ADLS
            de_tasks += [
                _task("ADLS Gen2 setup and folder hierarchy",               "Data Engineer", 6,  "Container structure, RBAC, lifecycle policies"),
                _task("ADF linked services and datasets",                   "Data Engineer", 6,  "Source/sink connectors, parameterised datasets"),
            ]
            for i in range(min(n_src, 4)):
                de_tasks.append(_task(f"ADF pipeline — source {i + 1}", "Data Engineer", 6, "Copy + transform pipeline per source"))
            de_tasks += [
                _task("Mapping Dataflows for data transformation",          "Data Engineer", 10, "Data cleansing, joins, aggregations"),
                _task("Pipeline triggers, monitoring, and alerting",        "Data Engineer", 6,  "Scheduled triggers, ADF monitor, email alerts"),
                _task("End-to-end testing and data validation",             "Data Engineer", 8,  "Pipeline tests, row count reconciliation"),
            ]
        # Per-req feature tasks: skip for Fabric/Databricks/Synapse — their comprehensive
        # Bronze→Silver→Gold templates already cover all functional requirements.
        # For ADF/ADLS only: add High/Medium reqs (Low are covered by the base pipeline tasks).
        if not (is_fabric or is_databricks or is_synapse):
            for r in reqs:
                r_dict = safe_dict(r)
                if r_dict.get("type") != "functional":
                    continue
                cplx = safe_str(r_dict.get("complexity", "Medium"))
                if cplx == "Low":
                    continue
                title = safe_str(r_dict.get("title"))
                desc  = safe_str(r_dict.get("description", title))
                base  = 8 if cplx == "High" else 5
                de_tasks.append(_task(f"Feature: {title}", "Data Engineer", base, desc))

        streams.append(_stream("Data Engineering", "Data Engineering", de_tasks, mult=1.0,
                               parallel_with=["AI / ML Stream"] if is_ai else []))

    # ── Stream: Power Platform Developer ─────────────────────────────────
    if is_power_platform:
        _has_rpa = _th("rpa") or _th("automate desktop") or _th("robot") or _th("bot")
        pp_tasks: list[dict] = []
        if _has_rpa:
            pp_tasks += [
                _task("RPA process analysis and bot specification",        "Power Platform Dev", 8,  "AS-IS process mapping, exception paths, bot architecture spec"),
                _task("Power Automate Desktop bot — environment and infra setup", "Power Platform Dev", 6, "Unattended bot VM, credential store, connection config"),
            ]
            for _bi in range(min(n_src, 5)):
                pp_tasks.append(_task(f"Power Automate Desktop bot — process {_bi + 1}",
                                      "Power Platform Dev", 12,
                                      "UI automation, web scraping / data extraction, exception handling"))
            pp_tasks += [
                _task("Bot error handling, retry logic, and alerting",     "Power Platform Dev", 6,  "Exception flows, alert emails, re-queue logic"),
                _task("Bot testing — unit and integration",                "Power Platform Dev", 8,  "Dry-run validation, mock data, exception path testing"),
            ]
        # Cloud flows and apps (always in Power Platform stream)
        pp_tasks += [
            _task("Power Automate Cloud flows — design and mapping",       "Power Platform Dev", 6,  "Trigger/action design, connector selection, data mapping"),
            _task("Power Automate Cloud flows — development",              "Power Platform Dev", 10, "Flow implementation, approvals, notifications, error branches"),
            _task("Power Apps canvas / model-driven app — UX design",     "Power Platform Dev", 6,  "Screen wireframes, navigation, component layout"),
            _task("Power Apps canvas / model-driven app — development",   "Power Platform Dev", 12, "Data connections, formulas, business rules, offline mode"),
            _task("Power Apps testing and UAT",                            "Power Platform Dev", 6,  "Functional testing, user acceptance, defect fixes"),
            _task("Power Platform deployment and governance",              "Power Platform Dev", 4,  "Solution packaging, DLP policy, environment promotion"),
        ]
        streams.append(_stream("Power Platform Developer", "Power Platform", pp_tasks, mult=1.0,
                               parallel_with=["Data Engineering", "Visualization Developer"]))

    # ── Stream: Visualization Developer ──────────────────────────────────
    if is_visualization:
        viz_tasks = [
            _task("Dashboard UX wireframes and mockups",                   "Visualization Dev", 6,  "Screen layouts, visual hierarchy, stakeholder sign-off"),
            _task("Power BI data model review and connection setup",       "Visualization Dev", 4,  "Import vs DirectQuery, gateway, semantic model review"),
            _task("Power BI report development — report pages",            "Visualization Dev", max(6, min(16, n_func * 2)),
                  str(n_func) + " functional requirements → report pages"),
            _task("DAX measures and calculated columns",                   "Visualization Dev", 8,  "KPI measures, time intelligence, % calculations"),
            _task("Power BI Row-Level Security (RLS) configuration",       "Visualization Dev", 4,  "RLS roles, rules, testing across user personas"),
            _task("Power BI Service deployment and workspace setup",       "Visualization Dev", 4,  "Dataset scheduled refresh, gateway, workspace permissions"),
            _task("Report testing and stakeholder UAT",                    "Visualization Dev", 6,  "Accuracy checks, layout review, sign-off"),
        ]
        streams.append(_stream("Visualization Developer", "Visualization", viz_tasks, mult=1.0,
                               parallel_with=["Data Engineering", "Power Platform Developer"]))

    # ── Stream 2: AI / ML ─────────────────────────────────────────────────
    if is_ai:
        ai_tasks = [
            _task("AI/ML solution architecture and model selection",        "ML Engineer", 8,  "Service topology, model benchmarking, cost profiling"),
            _task("Azure OpenAI / AI Foundry deployment and config",        "ML Engineer", 6,  "Model deployment, quotas, content filters, VNET"),
            _task("Prompt engineering and system message design",           "ML Engineer", 10, "System prompts, few-shot examples, function calling"),
            _task("Prompt testing and guardrail implementation",            "ML Engineer", 8,  "Red-team testing, output validation, safety filters"),
        ]
        if is_rag:
            ai_tasks += [
                _task("Document ingestion strategy and pipeline design",    "ML Engineer", 8,  "Document types, chunking strategy, metadata tagging"),
                _task("Document processing — parsing and chunking",         "ML Engineer", 10, "PDF/Word/PPT parsing, recursive chunking, overlap config"),
                _task("Embedding generation and batch indexing",            "ML Engineer", 8,  "Embedding model selection, batch API, rate limiting"),
                _task("AI Search index schema and semantic config",         "ML Engineer", 8,  "Index fields, semantic config, scoring profiles, synonyms"),
                _task("Hybrid retrieval pipeline (keyword + vector)",       "ML Engineer", 10, "Hybrid search, RRF re-ranking, context assembly"),
                _task("RAG answer generation and citation extraction",      "ML Engineer", 8,  "Response formatting, source attribution, confidence"),
                _task("RAG quality evaluation and optimisation",            "ML Engineer", 8,  "RAGAS metrics, precision@k, faithfulness scoring"),
            ]
        ai_tasks += [
            _task("AI orchestration layer (LangChain / Semantic Kernel)",   "ML Engineer", 12, "Multi-step reasoning, tool use, memory, agent loops"),
            _task("Conversation history and session management",            "ML Engineer", 6,  "Context window management, session store, TTL"),
            _task("Content Safety and moderation integration",              "ML Engineer", 6,  "Azure Content Safety, custom blocklists, jailbreak guards"),
            _task("AI performance benchmarking and cost optimisation",      "ML Engineer", 8,  "Latency p95/p99, caching, token budgets, batch mode"),
            _task("AI integration testing and regression suite",            "ML Engineer", 8,  "E2E tests, adversarial prompts, performance regression"),
        ]
        if is_teams:
            ai_tasks += [
                _task("Teams Bot Framework registration and manifest",      "ML Engineer", 6,  "Bot app registration, channel config, SSO setup"),
                _task("Teams Bot conversational flows and Adaptive Cards",  "ML Engineer", 12, "Waterfalls, Adaptive Cards, proactive messages, SSO"),
                _task("Teams Bot — edge cases and error handling",          "ML Engineer", 6,  "Retry, rate limit, fallback, error card responses"),
            ]
        # Per-req AI tasks: only when DE doesn't handle them (avoids double-count).
        # Only High/Medium complexity — Low reqs are covered by the base AI framework tasks.
        # DevOps/infra reqs are excluded here and added to the DevOps stream instead.
        if not is_data_eng:
            for r in reqs:
                r_dict = safe_dict(r)
                if r_dict.get("type") != "functional":
                    continue
                cplx = safe_str(r_dict.get("complexity", "Medium"))
                if cplx == "Low":
                    continue
                if _is_devops_req(r_dict):
                    continue  # routed to DevOps stream
                title = safe_str(r_dict.get("title"))
                desc  = safe_str(r_dict.get("description", title))
                base  = 10 if cplx == "High" else 6
                # Single combined task (do not split into implementation + testing rows)
                ai_tasks.append(_task(f"Feature: {title}", "ML Engineer", base, desc))

        streams.append(_stream("AI / ML Stream", "AI / ML", ai_tasks, mult=1.0,
                               parallel_with=["Data Engineering"] if is_data_eng else []))

    # ── Stream 3: SharePoint / M365 ───────────────────────────────────────
    if is_sharepoint:
        sp_tasks = [
            _task("SharePoint site architecture and provisioning",          "SharePoint Dev", 8,  "Site collections, hub sites, navigation, permissions model"),
            _task("Content types, columns and metadata taxonomy",           "SharePoint Dev", 8,  "Term store, managed metadata, content type hub"),
            _task("SPFx web parts and application customisers",             "SharePoint Dev", 12, "React-based SPFx, property pane, API calls"),
            _task("Power Apps canvas / model-driven app development",       "SharePoint Dev", 12, "Forms, screens, data connections, business rules"),
            _task("Power Automate flows and approval workflows",            "SharePoint Dev", 10, "Trigger/action flows, approvals, email notifications"),
            _task("SharePoint Search configuration and result sources",     "SharePoint Dev", 6,  "Search verticals, managed properties, refiners"),
            _task("User roles, permission matrix and AAD group mapping",    "SharePoint Dev", 6,  "Permission levels, broken inheritance, AAD groups"),
        ]
        if is_teams:
            sp_tasks += [
                _task("SharePoint pages as Teams tabs integration",         "SharePoint Dev", 8,  "Tab configuration, SSO, deep link support"),
                _task("Teams notifications and adaptive cards from flows",  "SharePoint Dev", 6,  "Power Automate to Teams channel cards, @mentions"),
            ]
        streams.append(_stream("SharePoint / M365", "SharePoint", sp_tasks, mult=1.20,
                               parallel_with=["AI / ML Stream", "Data Engineering"]))

    # ── Stream 4: Custom Application ─────────────────────────────────────
    if is_custom_app:
        app_tasks = [
            _task("UI architecture, design system and routing setup",       "Frontend Dev", 6,  "Component library, theme, route structure"),
            _task("Page layouts and responsive navigation",                 "Frontend Dev", 8,  "Layouts, nav bar, breadcrumbs, responsive grid"),
            _task("Feature UI implementation",                              "Frontend Dev", max(8, min(24, n_func * 3)), str(n_func) + " feature screens"),
            _task("State management and API service layer",                 "Frontend Dev", 8,  "Redux/context, API client, error handling"),
            _task("Form validation and user feedback components",           "Frontend Dev", 6,  "Form library, inline validation, toast notifications"),
            _task("Accessibility (WCAG 2.1 AA) and cross-browser testing",  "Frontend Dev", 6,  "Screen reader, keyboard nav, mobile responsiveness"),
        ]
        be_tasks: list[dict] = []
        for r in reqs:
            r = safe_dict(r)
            if r.get("type") == "functional":
                title = safe_str(r.get("title"))
                cplx  = safe_str(r.get("complexity"))
                base  = 10 if cplx == "High" else 7 if cplx == "Medium" else 4
                be_tasks.append(_task("Backend: " + title, "Senior Dev", base, safe_str(r.get("description"))))
        if not be_tasks:
            be_tasks = [
                _task("Core backend services and business logic",           "Senior Dev", 16, "Primary domain logic and service layer"),
                _task("REST API design, implementation and validation",     "Senior Dev", 12, "Endpoint development, auth, request validation"),
                _task("Data access layer and repository pattern",           "Developer",  10, "ORM config, query optimisation, connection pooling"),
                _task("Unit and integration test suite",                    "Developer",  10, "Automated tests, mocking, coverage > 80%"),
            ]
        streams.append(_stream("Custom Application", "Custom App", app_tasks + be_tasks, mult=1.10,
                               parallel_with=["Data Engineering", "AI / ML Stream"]))

    # ── Stream 5: Integration (standalone, only when no dedicated DE stream) ──
    if n_int > 0 and not is_data_eng:
        int_tasks: list[dict] = []
        for r in reqs:
            r = safe_dict(r)
            if r.get("type") == "integration":
                title = safe_str(r.get("title"))
                cplx  = safe_str(r.get("complexity"))
                desc  = safe_str(r.get("description"))
                if cplx == "High":
                    int_tasks += [
                        _task("Integration design: " + title,      "Architect", 8,  "API contracts, data mapping, auth flow — " + desc),
                        _task("Connector development: " + title,    "Developer", 12, "Adapter, data mapping, transformation"),
                        _task("Auth and security: " + title,        "Developer", 8,  "OAuth/API key, token management"),
                        _task("Integration testing: " + title,      "QA",        8,  "E2E flow validation, edge cases"),
                    ]
                elif cplx == "Medium":
                    int_tasks += [
                        _task("Integration design: " + title,      "Architect", 6,  "API contract — " + desc),
                        _task("Connector development: " + title,    "Developer", 10, "Adapter and request handling"),
                        _task("Integration testing: " + title,      "QA",        8,  "E2E validation"),
                    ]
                else:
                    int_tasks += [
                        _task("Integration design: " + title,      "Developer", 4,  "API mapping"),
                        _task("Connector development: " + title,    "Developer", 8,  "Adapter and transform"),
                        _task("Integration testing: " + title,      "QA",        6,  "Happy path testing"),
                    ]
        if int_tasks:
            streams.append(_stream("Integration", "Integration", int_tasks, mult=1.10,
                                   parallel_with=["Custom Application"]))

    # ── Stream 6: DevOps & Platform (runs throughout in parallel) ────────
    # Lite mode for simple SharePoint/M365-only or small custom-app projects
    # that don't need the full data-platform DevOps runbook.
    _devops_lite = not is_data_eng and not is_ai and not is_devops and not is_databricks
    if _devops_lite:
        devops_tasks = [
            _task("Azure resource provisioning and configuration",           "DevOps", 6,  "Resource deployment, managed identities, app registration"),
            _task("CI/CD pipeline setup",                                    "DevOps", 6,  "GitHub Actions / Azure DevOps build+deploy pipeline"),
            _task("Azure Key Vault and secrets management",                  "DevOps", 3,  "Secret bindings, managed identity access policies"),
            _task("Azure Monitor and alerting basics",                       "DevOps", 4,  "Alert rules, basic dashboards, log queries"),
            _task("Go-live deployment and verification",                     "DevOps", 4,  "Production deployment, smoke tests, rollback runbook"),
        ]
    else:
        devops_tasks = [
            _task("CI/CD pipeline design — branch strategy and gates",       "DevOps", 6,  "GitHub Actions / Azure DevOps pipelines, PR gates, approvals"),
            _task("Infrastructure as Code — Bicep/Terraform templates",      "DevOps", 8,  "IaC for all Azure resources, parameterised environments"),
            _task("Dev environment provisioning and configuration",           "DevOps", 4,  "Resource deployment, config, managed identities"),
            _task("Test / UAT environment provisioning",                      "DevOps", 3,  "Staging env, config parity, data masking"),
            _task("Production environment provisioning",                      "DevOps", 5,  "Prod resources, DNS, SSL/TLS, firewall rules"),
            _task("Azure Key Vault and secrets management setup",             "DevOps", 4,  "Secret rotation, managed identity bindings, access policies"),
            _task("Azure Monitor, Log Analytics and Application Insights",    "DevOps", 6,  "Workbooks, alert rules, dashboards, log queries"),
            _task("Network security — Private Endpoints and NSG rules",      "DevOps", 5,  "Private endpoints, VNET integration, NSG, Defender"),
            _task("Backup, DR and business continuity setup",                 "DevOps", 4,  "Backup policies, RTO/RPO validation, DR runbook"),
            _task("Production deployment runbook and go-live checklist",      "DevOps", 3,  "Step-by-step guide, rollback procedures, smoke tests"),
            _task("Go-live cutover and post-deployment verification",         "DevOps", 4,  "Traffic switch, smoke test, hypercare monitoring"),
        ]
    if is_devops:   # only for dedicated DevOps projects, not every data project
        devops_tasks.append(_task("Advanced CI/CD — environment-specific pipelines", "DevOps", 6, "Multi-stage YAML, environment approvals, slot swap"))
    # Per-req DevOps/infra tasks: requirements explicitly about security, infra, or deployment
    _existing_devops_titles = {t["name"].lower() for t in devops_tasks}
    for _dr in _devops_reqs:
        _cplx  = safe_str(_dr.get("complexity", "Medium"))
        _title = safe_str(_dr.get("title"))
        _desc  = safe_str(_dr.get("description", _title))
        _hrs   = 8 if _cplx == "High" else 5
        _task_name = f"Configure: {_title}"
        if _task_name.lower() not in _existing_devops_titles:
            devops_tasks.append(_task(_task_name, "DevOps", _hrs, _desc))
    # ── Non-functional requirement tasks — injected into DevOps stream ───────
    # Each NFR generates a concrete task routed to the right role based on its category.
    _nf_reqs = [safe_dict(r) for r in reqs
                if isinstance(r, dict) and r.get("type") == "non-functional"]
    _nfr_seen = {t["name"].lower() for t in devops_tasks}
    for _nfr in _nf_reqs:
        _nfr_title = safe_str(_nfr.get("title", "")).strip()
        _nfr_desc  = safe_str(_nfr.get("description", _nfr_title))
        _nfr_lower = (_nfr_title + " " + _nfr_desc).lower()
        _cplx      = safe_str(_nfr.get("complexity", "Medium"))
        _hrs       = 6 if _cplx == "High" else 4
        if not _nfr_title:
            continue
        if any(k in _nfr_lower for k in ["performance", "load test", "throughput", "concurrent user",
                                          "response time", "latency", "benchmark"]):
            _tn, _role = f"Performance testing and tuning: {_nfr_title}", "QA"
        elif any(k in _nfr_lower for k in ["security", "encrypt", "auth", "mfa", "sso",
                                            "zero trust", "access control", "identity"]):
            _tn, _role = f"Security hardening: {_nfr_title}", "Security"
        elif any(k in _nfr_lower for k in ["availab", "uptime", "sla", "disaster recovery",
                                            "rto", "rpo", "failover", "redundan", "resilience"]):
            _tn, _role = f"HA/DR implementation: {_nfr_title}", "DevOps"
        elif any(k in _nfr_lower for k in ["compliance", "gdpr", "iso", "soc2", "hipaa",
                                            "audit", "regulatory", "pci", "data protection"]):
            _tn, _role = f"Compliance control: {_nfr_title}", "Security"
        elif any(k in _nfr_lower for k in ["scalab", "elastic", "auto-scale", "autoscale",
                                            "scale out", "scale up", "horizontal"]):
            _tn, _role = f"Scalability implementation: {_nfr_title}", "DevOps"
        else:
            _tn, _role = f"NFR verification: {_nfr_title}", "DevOps"
        if _tn.lower() not in _nfr_seen:
            devops_tasks.append(_task(_tn, _role, _hrs, _nfr_desc))
            _nfr_seen.add(_tn.lower())

    # Small infra multiplier: private endpoints and multi-env add real overhead
    devops_mult = round(min(1.0 * (1.10 if has_multi_env else 1.0) * (1.10 if _h("private endpoint") or _h("kubernetes") else 1.0), 1.30), 2)
    streams.append(_stream("DevOps & Platform", "DevOps", devops_tasks, mult=devops_mult,
                           parallel_with=["Data Engineering", "AI / ML Stream", "Custom Application", "SharePoint / M365"]))

    # ── Apply tech-stack complexity multiplier M to all technical streams ────
    # M is 1.0 for basic stacks; Databricks → 1.50, Fabric → 1.40, OpenAI → 1.20, etc.
    # Discovery, Documentation, and PM are excluded — they scale with req count, not tech.
    if M > 1.0:
        _SKIP_DOMAINS = {"Discovery", "Documentation", "PM"}
        for _s in streams:
            if _s.get("domain") in _SKIP_DOMAINS:
                continue
            _s["hours"]               = max(1, round(_s["hours"] * M))
            _s["low_hours"]           = max(1, round(_s["low_hours"] * M))
            _s["high_hours"]          = max(1, round(_s["high_hours"] * M))
            _s["duration_weeks"]      = round(_s["hours"] / 40, 1)
            _s["complexity_multiplier"] = round(_s.get("complexity_multiplier", 1.0) * M, 2)
            for _t in _s.get("tasks", []):
                _t["hours"]     = max(1, round(_t["hours"] * M))
                _t["low_hours"] = max(1, round(_t.get("low_hours", _t["hours"]) * M))
                _t["high_hours"]= max(1, round(_t.get("high_hours", _t["hours"]) * M))

    # ── QA & Testing — NOT a separately estimated phase at ECI ──────────
    # QA is treated as 30% of total dev effort (built into delivery cost).
    # We derive its duration for Gantt visualisation only — NOT added to streams.
    _dev_hrs_for_qa = sum(s["hours"] for s in streams if s["domain"] not in ("Discovery", "DevOps", "PM"))
    _qa_hours_ref   = max(40, round(_dev_hrs_for_qa * 0.30))
    _qa_weeks_ref   = round(_qa_hours_ref / 40, 1)

    # ── Bug fixes and stabilisation: sub-task injected into the largest dev stream ──
    _dev_streams = [s for s in streams if s["domain"] not in ("Discovery", "DevOps", "PM", "Documentation")]
    if _dev_streams:
        _biggest_dev = max(_dev_streams, key=lambda s: s["hours"])
        _pre_dev_hrs = _biggest_dev["hours"]
        _bug_hrs     = max(4, min(12, int(_pre_dev_hrs * 0.07)))
        _bug_task    = _task(
            "Bug fixes and stabilisation", "Developer", _bug_hrs,
            "Resolve defects found during development, edge-case handling and code quality improvements",
        )
        _biggest_dev["tasks"].append(_bug_task)
        _biggest_dev["hours"]      += _bug_hrs
        _biggest_dev["low_hours"]  += int(_bug_hrs * 0.8)
        _biggest_dev["high_hours"] += int(_bug_hrs * 1.35)
        _biggest_dev["duration_weeks"] = round(_biggest_dev["hours"] / 40, 1)

    # ── Stream 8: Documentation & Training — complexity-scaled ───────────
    # Simpler projects need lighter handover docs; complex ones require the full suite
    _doc_scale  = 0.55 if complexity <= 4 else 0.75 if complexity <= 6 else 1.0
    has_frontend = is_custom_app or is_sharepoint or is_teams
    doc_tasks = [
        _task("Architecture and design documentation",             "Architect", max(3, int(8 * _doc_scale)), "Technical design doc, ADRs, component diagrams"),
        _task("Operations runbook and incident response guide",    "DevOps",    max(2, int(6 * _doc_scale)), "SOP, escalation paths, runbook, troubleshooting"),
        _task("Knowledge transfer session — technical team",       "Architect", max(2, int(6 * _doc_scale)), "Deep-dive with client engineering team"),
    ]
    if has_frontend or complexity >= 5:
        doc_tasks.append(_task("End-user guide and help documentation", "Writer", max(3, int(8 * _doc_scale)), "User manual, annotated screenshots, FAQ"))
        doc_tasks.append(_task("Knowledge transfer session — end users", "BA",    max(2, int(6 * _doc_scale)), "End-user training workshop, hands-on exercises"))
    if (is_custom_app or n_int > 0) and complexity >= 5:
        doc_tasks.append(_task("API documentation and developer integration guide", "Developer", max(3, int(8 * _doc_scale)), "OpenAPI specs, code samples, error catalogue"))
    if complexity >= 6:
        doc_tasks.append(_task("Admin and configuration reference guide", "Writer", max(2, int(6 * _doc_scale)), "System admin procedures, config reference"))
    streams.append(_stream("Documentation & Training", "Documentation", doc_tasks, mult=1.0))

    # ── Project Management (ongoing overhead) ─────────────────────────────
    # PM based on pure delivery hours (dev + devops); documentation and PM itself excluded.
    _pm_base = sum(s["hours"] for s in streams if s["domain"] not in ("PM", "Documentation"))
    pm_hrs = max(16, int(_pm_base * 0.08))
    pm_tasks = [
        _task("Sprint planning and backlog grooming",              "PM", min(12, max(4, pm_hrs // 4)), "Bi-weekly sprints, story sizing, prioritisation"),
        _task("Status reporting and stakeholder updates",          "PM", min(12, max(4, pm_hrs // 4)), "Weekly status reports, steering committee deck"),
        _task("Risk and issue management",                         "PM", min(8,  max(4, pm_hrs // 5)), "Risk register updates, issue resolution tracking"),
        _task("Resource coordination and dependency management",   "PM", min(8,  max(4, pm_hrs // 6)), "Team allocation, cross-stream dependencies"),
        _task("Change request evaluation and approval management", "PM", min(6, max(3, pm_hrs // 8)), "Impact analysis, scope change approval workflows"),
    ]
    pm_actual = sum(t["hours"] for t in pm_tasks)
    for t in pm_tasks:
        t["low_hours"] = int(t["hours"] * 0.8)
        t["high_hours"] = int(t["hours"] * 1.35)
    streams.append(_stream("Project Management", "PM", pm_tasks, mult=1.0))

    # ── Discovery-only engagement: strip all dev streams ──────────────────
    if _discovery_only:
        streams = [s for s in streams if s["domain"] in ("Discovery", "PM")]

    # ── Totals and critical-path duration ─────────────────────────────────
    total      = sum(s["hours"]     for s in streams)
    total_low  = sum(s["low_hours"] for s in streams)
    total_high = sum(s["high_hours"] for s in streams)

    # ── RAG hour calibration — blend formula with historical similar projects ─
    rag_calibration = None
    if rag:
        _sim = [p for p in safe_list(rag.get("similar_projects", []))
                if isinstance(p, dict) and safe_int(p.get("hours", 0)) > 0]
        _bench = safe_int(rag.get("benchmark_hours", 0))
        _wsum, _wtot = 0.0, 0.0
        for p in _sim[:8]:
            _sim_score = float(p.get("similarity") or 0.5)
            _hrs = safe_int(p.get("hours", 0))
            if _hrs > 0 and _sim_score > 0.20:
                _wsum += _hrs * _sim_score
                _wtot += _sim_score
        _hist_hrs = int(_wsum / _wtot) if _wtot > 0 else _bench
        if not _hist_hrs and _bench:
            _hist_hrs = _bench
        if _hist_hrs > 0:
            _avg_sim  = (_wtot / len(_sim)) if _sim else 0.30
            # Weight of historical data: more similar → slightly more influence,
            # but formula always dominates so one outlier can't swing the number wildly
            hist_w = 0.35 if _avg_sim >= 0.65 else 0.20 if _avg_sim >= 0.40 else 0.10
            _formula  = total
            calibrated = int(_formula * (1 - hist_w) + _hist_hrs * hist_w)
            if calibrated != _formula and _formula > 0:
                _ratio = calibrated / _formula
                for s in streams:
                    s["hours"]          = max(1, int(s["hours"]      * _ratio))
                    s["low_hours"]      = max(1, int(s["low_hours"]  * _ratio))
                    s["high_hours"]     = max(1, int(s["high_hours"] * _ratio))
                    s["duration_weeks"] = round(s["hours"] / 40, 1)
                    for t in s.get("tasks", []):
                        t["hours"]      = max(1, int(t["hours"]                           * _ratio))
                        t["low_hours"]  = max(1, int(t.get("low_hours",  t["hours"])      * _ratio))
                        t["high_hours"] = max(1, int(t.get("high_hours", t["hours"])      * _ratio))
            total      = sum(s["hours"]     for s in streams)
            total_low  = sum(s["low_hours"] for s in streams)
            total_high = sum(s["high_hours"] for s in streams)
            rag_calibration = {
                "formula_hours":    _formula,
                "historical_hours": _hist_hrs,
                "similar_count":    len(_sim),
                "avg_similarity":   round(_avg_sim, 2),
                "hist_weight":      f"{int(hist_w * 100)}%",
                "calibrated_hours": total,
            }
    # ─────────────────────────────────────────────────────────────────────────

    disc_w     = streams[0]["duration_weeks"]
    par_strs   = [s for s in streams if s["domain"] not in ("Discovery", "Documentation", "PM")]
    critical_w = max((s["duration_weeks"] for s in par_strs), default=4.0)
    doc_w      = next((s["duration_weeks"] for s in streams if s["domain"] == "Documentation"), 1.0)
    # QA runs fully parallel with dev (not a sequential phase), so it doesn't extend the timeline.
    total_weeks = round(disc_w + critical_w + doc_w + 0.5)
    _min_weeks  = 2 if _discovery_only else max(2, round(critical_w + disc_w))
    total_weeks = max(total_weeks, _min_weeks)

    buffer_pct = 18 if complexity >= 7 else 15 if complexity >= 5 else 12
    conf       = "Medium (" + str(max(60, 90 - complexity * 3)) + "%)"

    # Assign week labels — Discovery is sequential; everything else parallel
    w = 1
    for s in streams:
        sw = max(1, round(s["duration_weeks"]))
        s["week_label"] = "Wk " + str(w) + ("–" + str(w + sw - 1) if sw > 1 else "")
        if not s.get("percentage"):
            s["percentage"] = str(round(s["hours"] / max(total, 1) * 100)) + "%"
        if s["domain"] == "Discovery":
            w += sw

    # ── Role mix ─────────────────────────────────────────────────────────
    roles: list[dict] = [
        {"name": "Project Manager",    "allocation_pct": 0.10 + (0.05 * (n_total > 10)), "rate": 125},
        {"name": "Solution Architect", "allocation_pct": 0.15 + (0.05 * (len(all_tech) > 8)), "rate": 150},
    ]
    if is_data_eng:
        roles.append({"name": "Data Engineer",     "allocation_pct": min(1.0, 0.6 + (0.1 if is_fabric else 0)), "rate": 115})
    if is_ai:
        ai_kw = sum(1 for t in all_tech if any(k in t.lower() for k in ["ai", "openai", "ml", "llm", "gpt", "foundry"]))
        roles.append({"name": "ML Engineer",       "allocation_pct": min(1.0, 0.5 + ai_kw * 0.1), "rate": 140})
    if is_custom_app:
        roles.append({"name": "Backend Developer", "allocation_pct": min(1.0, 0.5 + n_func * 0.05), "rate": 110})
        roles.append({"name": "Frontend Developer","allocation_pct": min(1.0, 0.3 + n_func * 0.04), "rate": 100})
    if is_sharepoint:
        roles.append({"name": "SharePoint Developer", "allocation_pct": 0.5, "rate": 105})
    if not is_custom_app and not is_sharepoint:
        roles.append({"name": "Backend Developer", "allocation_pct": min(1.0, 0.4 + n_func * 0.04), "rate": 110})
    roles.append({"name": "DevOps Engineer",       "allocation_pct": 0.35 if is_devops else 0.25, "rate": 120})
    roles.append({"name": "QA Engineer",           "allocation_pct": min(0.6, 0.3 + n_total * 0.02), "rate": 95})
    roles.append({"name": "Product Owner",         "allocation_pct": 0.10, "rate": 130})

    milestones = [
        {"name": "Kickoff",                "week": 1,                              "description": "Team onboarding and project initiation"},
        {"name": "Requirements Baselined", "week": max(2, total_weeks // 8),       "description": "Scope sign-off and design start"},
        {"name": "Design Approved",        "week": max(3, total_weeks // 5),       "description": "Architecture review complete"},
        {"name": "MVP Ready",              "week": max(6, total_weeks // 2),       "description": "Core features functional in Dev env"},
        {"name": "UAT Start",              "week": max(8, int(total_weeks * 0.75)),"description": "User acceptance testing begins"},
        {"name": "Go-Live",                "week": total_weeks,                    "description": "Production deployment and hypercare"},
    ]

    return {
        "total_hours":      total,
        "duration_weeks":   str(total_weeks) + " weeks",
        "confidence":       conf,
        "buffer":           str(buffer_pct) + "%",
        "phases":           streams,
        "milestones":       milestones,
        "three_point":      {"optimistic": total_low, "most_likely": total, "pessimistic": total_high},
        "roles":            roles,
        "rag_calibration":  rag_calibration,
        "qa_weeks":         _qa_weeks_ref,
    }


def _cost_category(service_name: str) -> str:
    s = service_name.lower()
    if any(k in s for k in ["fabric", "databricks", "synapse", "data factory", "adls", "data lake", "stream analytics"]):
        return "Data Platform"
    if any(k in s for k in ["openai", "ai search", "foundry", "machine learning", "cognitive"]):
        return "AI/ML"
    if any(k in s for k in ["app service", "functions", "container", "static web"]):
        return "Compute"
    if any(k in s for k in ["sql", "cosmos", "redis", "blob", "storage", "postgresql", "mysql"]):
        return "Database"
    if any(k in s for k in ["key vault", "entra", "active directory", "purview"]):
        return "Security"
    if any(k in s for k in ["devops", "monitor", "log analytics", "insights"]):
        return "Monitoring"
    if any(k in s for k in ["service bus", "event hub", "event grid", "logic app", "api management"]):
        return "Integration"
    if any(k in s for k in ["front door", "cdn", "firewall", "signalr"]):
        return "Networking"
    return "Other"


def _build_dynamic_cost(semantic, time_est, text: str = ""):
    """Build infrastructure cost estimate, respecting mandated tech and excluding source systems.
    text: raw scope document text — used to detect tier upgrades (e.g. Premium APIM for zone redundancy).
    """
    from .text_analysis import _fetch_live_azure_pricing, _TIER_UPGRADE_SIGNALS
    try:
        live_prices = _fetch_live_azure_pricing()
    except Exception:
        live_prices = {}

    # Scope text for tier detection — also check raw text stored in semantic
    _scope_lower = (text or semantic.get("_raw_text", "") or "").lower()

    def _pick_tier(catalog_name, default_tier, default_monthly, default_desc):
        """Return (tier, monthly, desc) — upgraded if scope text contains tier signals."""
        if _scope_lower and catalog_name in _TIER_UPGRADE_SIGNALS:
            for signals, tier_label, tier_monthly, tier_desc in _TIER_UPGRADE_SIGNALS[catalog_name]:
                if any(sig in _scope_lower for sig in signals):
                    # Use live price if available for the upgraded tier, else use catalog value
                    live_override = live_prices.get(catalog_name + " " + tier_label, tier_monthly)
                    return tier_label, live_override, tier_desc
        # Default: prefer live price over hardcoded base_monthly
        return default_tier, live_prices.get(catalog_name, default_monthly), default_desc

    mandated    = safe_list(semantic.get("mandated_technologies", []))
    source_sys  = safe_list(semantic.get("source_systems", []))
    all_tech    = safe_list(semantic.get("technology_stack", []))
    # Build from mandated if available; otherwise use full stack minus confirmed source systems
    build_tech  = mandated if mandated else [t for t in all_tech if t not in source_sys]

    def _tech_matches_catalog(tech_name: str, catalog_name: str) -> bool:
        """True when tech_name refers to catalog_name via exact match, keyword overlap, or tech-catalog aliases."""
        tn = tech_name.lower()
        cn = catalog_name.lower()
        if tn == cn:
            return True
        # Catalog key words (>3 chars) all present in tech name
        if all(w in tn for w in cn.split() if len(w) > 3):
            return True
        # Tech-catalog alias keywords (e.g. "apim", "api management" → "Azure API Management")
        aliases = _TECH_CATALOG.get(catalog_name, [])
        if any(alias in tn for alias in aliases):
            return True
        return False

    azure_costs = []
    seen = set()
    for tech_name in build_tech:
        for catalog_name, (tier, base_monthly, desc) in _INFRA_COST_CATALOG.items():
            if catalog_name in seen:
                continue
            if _tech_matches_catalog(tech_name, catalog_name):
                _tier, _monthly, _desc = _pick_tier(catalog_name, tier, base_monthly, desc)
                azure_costs.append({"service": catalog_name, "tier": _tier,
                                    "monthly_cost": _monthly, "description": _desc,
                                    "category": _cost_category(catalog_name)})
                seen.add(catalog_name)
                break
    # Also scan remaining all_tech for catalog matches not covered above (non-source)
    for tech_name in all_tech:
        if tech_name in source_sys:
            continue
        for catalog_name, (tier, base_monthly, desc) in _INFRA_COST_CATALOG.items():
            if catalog_name in seen:
                continue
            if _tech_matches_catalog(tech_name, catalog_name):
                _tier, _monthly, _desc = _pick_tier(catalog_name, tier, base_monthly, desc)
                azure_costs.append({"service": catalog_name, "tier": _tier,
                                    "monthly_cost": _monthly, "description": _desc,
                                    "category": _cost_category(catalog_name)})
                seen.add(catalog_name)
                break

    # Always include baseline security/ops unless already present
    for base_svc in ["Azure Key Vault", "Azure Monitor", "Azure AD / Entra ID"]:
        if base_svc not in seen and base_svc in _INFRA_COST_CATALOG:
            tier, base_monthly, desc = _INFRA_COST_CATALOG[base_svc]
            monthly = live_prices.get(base_svc, base_monthly)
            azure_costs.append({"service": base_svc, "tier": tier, "monthly_cost": monthly,
                                 "description": desc, "category": _cost_category(base_svc)})
            seen.add(base_svc)

    third_party = []
    active_costs = [c for c in azure_costs if c["monthly_cost"] > 0]
    total_monthly = sum(c["monthly_cost"] for c in active_costs)

    optimization = []
    if any("app service" in c["service"].lower() for c in azure_costs):
        optimization.append("Use Reserved Instances for 36% savings on App Service")
    if any("sql" in c["service"].lower() for c in azure_costs):
        optimization.append("Use elastic pools for SQL if multiple databases")
    if any("cosmos" in c["service"].lower() for c in azure_costs):
        optimization.append("Monitor Cosmos DB RU consumption and right-size autoscale")
    if any("openai" in c["service"].lower() or "foundry" in c["service"].lower() for c in azure_costs):
        optimization.append("Implement token caching and prompt optimization to reduce AI costs")
    optimization.append("Enable auto-shutdown for non-production environments")
    optimization.append("Use Azure Cost Management alerts at 80% and 100% budget thresholds")

    return {
        "total_monthly_cost": total_monthly,
        "total_annual_cost": total_monthly * 12,
        "azure_costs": active_costs,
        "third_party_costs": third_party,
        "cost_optimization": optimization,
        "notes": "Estimates based on detected tech stack (" + str(len(active_costs)) + " services). Dev/staging adds ~40% of prod costs.",
    }


def _build_dynamic_risk(semantic, time_est, cost_est):
    """Build risk assessment from project analysis."""
    complexity = safe_int(semantic.get("complexity_score", 5))
    reqs = safe_list(semantic.get("requirements"))
    tech = safe_list(semantic.get("technology_stack"))
    hours = safe_int(time_est.get("total_hours", 0))
    monthly = safe_int(cost_est.get("total_monthly_cost", 0))

    n_int = len([r for r in reqs if isinstance(r, dict) and r.get("type") == "integration"])
    has_ai = any(k in " ".join(tech).lower() for k in ["ai", "openai", "foundry", "llm", "claude"])

    risks = []

    if n_int >= 2:
        risks.append({"category": "Technical", "title": "Integration Complexity (" + str(n_int) + " integrations)",
                       "description": str(n_int) + " integration points identified — API compatibility and data mapping risks.",
                       "severity": "High" if n_int >= 4 else "Medium", "probability": "Medium", "impact": "High",
                       "mitigation": "Early PoC for each integration. Validate APIs in Week 1."})
    if has_ai:
        risks.append({"category": "Technical", "title": "AI Model Performance",
                       "description": "LLM response quality, hallucination risk, and prompt engineering complexity.",
                       "severity": "High", "probability": "Medium", "impact": "High",
                       "mitigation": "Extensive prompt tuning, fallback model routing, response validation."})
    if len(tech) > 8:
        risks.append({"category": "Technical", "title": "Technology Stack Complexity",
                       "description": str(len(tech)) + " technologies — increased learning curve and integration overhead.",
                       "severity": "Medium", "probability": "Medium", "impact": "Medium",
                       "mitigation": "Assign specialists per technology. Conduct architecture reviews."})

    if hours > 500:
        risks.append({"category": "Schedule", "title": "Extended Timeline (" + str(hours) + " hours)",
                       "description": "Large project scope increases risk of delays and scope creep.",
                       "severity": "High", "probability": "High", "impact": "High",
                       "mitigation": "Strict change request process. Agile sprints with bi-weekly reviews."})
    else:
        risks.append({"category": "Schedule", "title": "Scope Creep",
                       "description": "Requirements may evolve during development.",
                       "severity": "Medium", "probability": "High", "impact": "Medium",
                       "mitigation": "Formal change request process and sprint backlog management."})

    risks.append({"category": "Resource", "title": "Key Personnel Availability",
                   "description": "Specialists may have limited availability across concurrent projects.",
                   "severity": "Medium", "probability": "Medium", "impact": "High",
                   "mitigation": "Secure resource commitments early. Cross-train team members."})

    if monthly > 500:
        risks.append({"category": "Budget", "title": "Cloud Cost Overrun ($" + str(monthly) + "/mo)",
                       "description": "Infrastructure costs of $" + str(monthly) + "/month may exceed estimates with usage growth.",
                       "severity": "Medium" if monthly < 2000 else "High", "probability": "Medium", "impact": "Medium",
                       "mitigation": "Azure Cost Management alerts. Monthly cost reviews. Reserved instances."})

    if any(k in " ".join(tech).lower() for k in ["sharepoint", "blob", "sql", "cosmos", "data"]):
        risks.append({"category": "Data", "title": "Data Quality & Migration",
                       "description": "Document quality, format inconsistencies, or data integrity issues during processing.",
                       "severity": "Medium", "probability": "Medium", "impact": "Medium",
                       "mitigation": "Early data profiling. Validate sample documents. Implement error handling."})

    score = min(10, max(1, int(complexity * 0.7 + len(risks) * 0.3)))
    level = "Low" if score <= 3 else "Medium" if score <= 6 else "High"
    return {"overall_score": score, "overall_level": level, "risks": risks}


def _build_dynamic_arch(semantic):
    """Build architecture from detected tech stack, honouring mandated technologies."""
    tech = safe_list(semantic.get("technology_stack", []))
    # Mandated tech has higher priority — merge on top so presence flags fire correctly
    mandated = safe_list(semantic.get("mandated_technologies", []))
    all_tech = list(dict.fromkeys(mandated + tech))   # mandated first, deduplicated
    tech_lower = " ".join(all_tech).lower()
    domains = safe_list(semantic.get("project_domains", []))

    components = []
    data_flow = []
    security = []

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _has(*keys):
        return any(k in tech_lower for k in keys)

    # ═══════════════════════════════════════════════════════════════════════
    #  DOMAIN — Modern Data Platform  (Fabric / Synapse / ADF / Databricks)
    # ═══════════════════════════════════════════════════════════════════════
    is_data_platform = (
        _has("microsoft fabric", "fabric workspace", "fabric lakehouse", "onelake")
        or _has("azure synapse", "synapse analytics")
        or _has("azure databricks", "databricks")
        or "Data Engineering & Analytics" in domains
        or "Modern Data Platform" in domains
    )

    if is_data_platform:
        # ── Data Sources ──────────────────────────────────────────────────
        components.append({"name": "Data Sources", "type": "Ingestion",
                           "azure_service": "ADLS Gen2 / Blob Storage / Event Hubs",
                           "services": ["Raw files (CSV / Parquet / JSON)",
                                        "Operational databases",
                                        "Streaming events (Event Hubs / Kafka)",
                                        "Third-party APIs / SaaS connectors"]})
        data_flow.append("Data Sources")

        # ── Ingestion / Orchestration ─────────────────────────────────────
        if _has("microsoft fabric", "fabric pipeline", "fabric workspace"):
            components.append({"name": "Microsoft Fabric", "type": "Data Platform",
                               "azure_service": "Microsoft Fabric",
                               "services": ["Fabric Lakehouse (OneLake)",
                                            "Fabric Data Engineering (Notebooks / Spark)",
                                            "Fabric Data Factory (Pipelines)",
                                            "Fabric Data Warehouse",
                                            "Fabric Real-Time Analytics (KQL)",
                                            "Fabric Semantic Model (Power BI Direct Lake)"]})
            data_flow.append("Microsoft Fabric")
        else:
            if _has("azure data factory", "data factory", " adf "):
                components.append({"name": "Azure Data Factory", "type": "Orchestration",
                                   "azure_service": "Azure Data Factory",
                                   "services": ["Ingestion pipelines", "Copy activity",
                                                "Data flow transformations", "Trigger-based scheduling"]})
                data_flow.append("ADF Pipelines")
            if _has("azure databricks", "databricks", "delta lake"):
                components.append({"name": "Azure Databricks", "type": "Compute",
                                   "azure_service": "Azure Databricks",
                                   "services": ["Spark notebooks (Python / Scala)",
                                                "Delta Lake (Bronze → Silver → Gold)",
                                                "MLflow for experiment tracking",
                                                "Unity Catalog for governance"]})
                data_flow.append("Databricks")
            if _has("azure synapse", "synapse analytics"):
                components.append({"name": "Azure Synapse Analytics", "type": "Analytics",
                                   "azure_service": "Azure Synapse Analytics",
                                   "services": ["Synapse Spark pools",
                                                "Serverless SQL pool",
                                                "Dedicated SQL pool (DWH)",
                                                "Synapse Pipelines"]})
                data_flow.append("Synapse")
            if _has("adls", "azure data lake", "data lake storage"):
                components.append({"name": "Data Lake (ADLS Gen2)", "type": "Storage",
                                   "azure_service": "ADLS Gen2",
                                   "services": ["Bronze layer — raw ingest",
                                                "Silver layer — cleansed / conformed",
                                                "Gold layer — aggregated / business-ready",
                                                "Hierarchical namespace with ACL security"]})
                data_flow.append("Data Lake")

        # ── Semantic / Reporting layer ─────────────────────────────────────
        if _has("power bi", "powerbi", "pbi"):
            components.append({"name": "Reporting & Analytics", "type": "Presentation",
                               "azure_service": "Power BI",
                               "services": ["Power BI Premium / Embedded",
                                            "DirectQuery / Import / Direct Lake",
                                            "Self-service analytics",
                                            "Paginated reports"]})
            data_flow.append("Power BI")

        # ── Data Governance ───────────────────────────────────────────────
        if _has("azure purview", "microsoft purview", "data catalog", "data governance"):
            components.append({"name": "Data Governance", "type": "Governance",
                               "azure_service": "Microsoft Purview",
                               "services": ["Data catalog & discovery",
                                            "Data lineage tracking",
                                            "Classification & sensitivity labels",
                                            "Access policy management"]})

    # ═══════════════════════════════════════════════════════════════════════
    #  DOMAIN — AI / ML
    # ═══════════════════════════════════════════════════════════════════════
    is_ai = _has("azure openai", "openai", "gpt", "azure ai foundry", "foundry", "claude", "llm",
                 "azure machine learning", "azure ml", " aml ", "mlflow", "cognitive services")

    if is_ai:
        if _has("azure machine learning", "azure ml", " aml "):
            components.append({"name": "Azure ML Platform", "type": "ML Engineering",
                               "azure_service": "Azure Machine Learning",
                               "services": ["Model training & experiments",
                                            "MLflow tracking & model registry",
                                            "Inference endpoints (managed online / batch)",
                                            "Feature store & dataset versioning"]})
            data_flow.append("Azure ML")
        if _has("azure openai", "openai", "gpt", "azure ai foundry", "foundry", "claude"):
            ai_svc = "Azure AI Foundry" if _has("foundry", "claude") else "Azure OpenAI"
            components.append({"name": "AI / LLM Engine", "type": "Intelligence",
                               "azure_service": ai_svc,
                               "services": ["LLM inference (GPT-4o / Claude)",
                                            "Prompt orchestration",
                                            "RAG pipeline" if _has("rag", "vector search", "ai search") else "Chat completion API",
                                            "Responsible AI content filtering"]})
            data_flow.append("AI Engine")
        if _has("ai search", "cognitive search", "vector search"):
            components.append({"name": "Knowledge Index", "type": "Search",
                               "azure_service": "Azure AI Search",
                               "services": ["Vector + hybrid search",
                                            "Semantic ranking",
                                            "Indexer pipelines",
                                            "Skillsets for enrichment"]})

    # ═══════════════════════════════════════════════════════════════════════
    #  DOMAIN — Custom Application / Web
    # ═══════════════════════════════════════════════════════════════════════
    is_app = (_has("react", "angular", "vue", "blazor", "app service", "fastapi",
                   "flask", ".net", "node", "python") and not is_data_platform)

    if is_app or (not is_data_platform and not is_ai):
        if _has("react", "angular", "vue", "blazor"):
            fe_svcs = [t for t in all_tech if any(k in t.lower() for k in ["react", "angular", "vue", "blazor"])]
            components.append({"name": "Frontend", "type": "Web App",
                               "azure_service": "Azure Static Web Apps / App Service",
                               "services": fe_svcs or ["Single-page application", "CDN-hosted assets"]})
            data_flow.append("Frontend")
        if _has("api management", "apim"):
            components.append({"name": "API Gateway", "type": "Integration",
                               "azure_service": "Azure API Management",
                               "services": ["REST / GraphQL APIs", "Rate limiting", "OAuth 2.0 validation"]})
            data_flow.append("API Gateway")
        if _has("app service", "fastapi", "flask", ".net", "node", "python"):
            be_svcs = [t for t in all_tech if any(k in t.lower() for k in ["python", ".net", "node", "fastapi", "flask"])]
            components.append({"name": "Backend Services", "type": "Microservices",
                               "azure_service": "Azure App Service / Functions",
                               "services": be_svcs or ["Business logic layer", "REST API"]})
            data_flow.append("Backend")
        db_svcs = []
        if _has("azure sql", "sql database", "sql server"):
            db_svcs.append("Azure SQL Database")
        if _has("cosmos db", "cosmosdb"):
            db_svcs.append("Cosmos DB")
        if _has("redis", "cache"):
            db_svcs.append("Redis Cache")
        if _has("blob", "storage"):
            db_svcs.append("Blob Storage")
        if db_svcs:
            components.append({"name": "Data Layer", "type": "Database",
                               "azure_service": " + ".join(db_svcs[:2]),
                               "services": db_svcs})
            data_flow.append("Database")

    # ═══════════════════════════════════════════════════════════════════════
    #  DOMAIN — SharePoint & M365
    # ═══════════════════════════════════════════════════════════════════════
    if _has("sharepoint", "sharepoint online") or "SharePoint & M365" in domains:
        sp_svcs = ["SharePoint Online document libraries", "Power Apps model-driven app"]
        if _has("power automate"):
            sp_svcs.append("Power Automate workflows")
        if _has("microsoft teams", "teams"):
            sp_svcs.append("Teams integration / tabs")
        components.append({"name": "SharePoint & Power Platform", "type": "Collaboration",
                           "azure_service": "SharePoint Online + Power Platform",
                           "services": sp_svcs})
        if "SharePoint" not in " ".join(data_flow):
            data_flow.append("SharePoint / M365")

    # ═══════════════════════════════════════════════════════════════════════
    #  CROSS-CUTTING — Integration, Security, DevOps (always)
    # ═══════════════════════════════════════════════════════════════════════
    int_svcs = []
    if _has("service bus"):
        int_svcs.append("Azure Service Bus (async messaging)")
    if _has("event hub"):
        int_svcs.append("Azure Event Hubs (streaming ingest)")
    if _has("logic app"):
        int_svcs.append("Logic Apps (workflow automation)")
    if _has("azure functions", "function app", "serverless"):
        int_svcs.append("Azure Functions (event-driven compute)")
    if int_svcs:
        components.append({"name": "Integration Layer", "type": "Messaging",
                           "azure_service": "Service Bus / Event Hubs / Logic Apps",
                           "services": int_svcs})

    # Security (always present)
    security = ["Azure AD / Entra ID — SSO & RBAC", "Azure Key Vault — secrets & certificates",
                "TLS 1.3 encryption in transit", "Encryption at rest (ADE / TDE)",
                "Azure Monitor + Log Analytics — audit & alerting",
                "RBAC least-privilege access model"]
    if _has("azure firewall", "ddos", "front door"):
        security.append("Azure Firewall + DDoS Protection Standard")
    if _has("purview", "data governance"):
        security.append("Microsoft Purview — data classification & compliance")

    components.append({"name": "Security & Identity", "type": "Security",
                       "azure_service": "Azure AD + Key Vault",
                       "services": ["Entra ID (SSO / MFA / RBAC)",
                                    "Azure Key Vault",
                                    "Managed Identity for service-to-service",
                                    "Azure Policy for compliance"]})

    # DevOps
    devops_svcs = ["CI/CD pipelines", "Infrastructure as Code (Bicep / Terraform)",
                   "Application Insights (APM)", "Azure Monitor dashboards & alerts"]
    if _has("github actions"):
        devops_svcs.insert(0, "GitHub Actions")
    if _has("kubernetes", "aks", "container"):
        devops_svcs.append("Azure Container Registry + AKS")
    components.append({"name": "DevOps & Observability", "type": "Operations",
                       "azure_service": "Azure DevOps / GitHub Actions + Monitor",
                       "services": devops_svcs})

    if not data_flow:
        data_flow = ["Sources", "Ingestion", "Processing", "Storage", "Consumption"]

    # ── Pattern label ─────────────────────────────────────────────────────
    if _has("microsoft fabric"):
        pattern = "Microsoft Fabric Unified Data Platform"
    elif _has("azure synapse") and _has("azure databricks"):
        pattern = "Modern Data Lakehouse (Synapse + Databricks)"
    elif _has("azure databricks"):
        pattern = "Databricks Delta Lakehouse Architecture"
    elif _has("azure synapse"):
        pattern = "Azure Synapse Analytics Platform"
    elif _has("azure data factory") and _has("adls", "data lake"):
        pattern = "Cloud Data Platform (ADF + ADLS Gen2)"
    elif _has("rag", "vector", "embedding") and is_ai:
        pattern = "AI-Powered RAG Architecture"
    elif _has("sharepoint") and not is_data_platform:
        pattern = "SharePoint & Power Platform Solution"
    elif _has("service bus", "event hub") and is_app:
        pattern = "Event-Driven Microservices Architecture"
    else:
        pattern = "Cloud-Native Application Architecture"

    # ── Scalability / Availability strings ───────────────────────────────
    if is_data_platform and _has("microsoft fabric"):
        scalability = "Microsoft Fabric auto-scales compute capacity (F-SKU). OneLake scales storage independently."
        availability = "Fabric SLA 99.9%. OneLake geo-redundant. Power BI Premium HA."
    elif _has("azure databricks"):
        scalability = "Databricks autoscaling clusters. Delta Lake ACID transactions. Serverless SQL for ad-hoc queries."
        availability = "Databricks 99.95% SLA. ADLS Gen2 RA-GRS 99.99% durability."
    else:
        scalability = "Auto-scaling based on workload demand. Serverless compute where applicable."
        availability = "99.9%+ SLA target. Multi-zone deployment for critical components."

    return {
        "pattern": pattern,
        "components": components,
        "data_flow": data_flow,
        "security": security,
        "scalability": scalability,
        "availability": availability,
    }


def _build_dynamic_scope(semantic, time_est):
    """Build structured SOW-quality scope from actual requirements (fallback)."""
    reqs = safe_list(semantic.get("requirements"))
    tech = safe_list(semantic.get("technology_stack"))
    tech_lower = " ".join(tech).lower()

    in_scope = []
    for i, r in enumerate(reqs[:10]):
        r = safe_dict(r)
        title = safe_str(r.get("title", "Requirement"))
        desc = safe_str(r.get("description", title))
        in_scope.append({
            "id": f"SC-{i+1:03d}",
            "title": title,
            "description": desc,
            "deliverable": f"Implemented and tested {title} feature",
            "acceptance_criteria": f"{title} meets all defined requirements and passes UAT sign-off",
        })
    base_idx = len(in_scope)
    for j, (title, deliverable, ac) in enumerate([
        ("Architecture Design & Documentation",
         "Architecture Decision Records, component diagrams, data flow documentation",
         "Architecture reviewed and approved by client technical lead"),
        ("Testing — Unit, Integration, Performance, and UAT",
         "Test plans, test cases, test execution reports, defect log",
         "All critical and high-priority defects resolved; UAT sign-off obtained"),
        ("Production Deployment",
         "Application deployed to production Azure environment",
         "Smoke tests pass; application accessible to end users"),
        ("30-Day Hypercare Support",
         "Dedicated support channel; incident response SLA; daily health checks",
         "All P1/P2 incidents resolved within agreed SLA during hypercare period"),
    ]):
        in_scope.append({
            "id": f"SC-{base_idx+j+1:03d}",
            "title": title,
            "description": title,
            "deliverable": deliverable,
            "acceptance_criteria": ac,
        })

    out_of_scope = []
    oos_items = []
    if "react" not in tech_lower and "angular" not in tech_lower and "vue" not in tech_lower:
        oos_items.append(("Custom Frontend / Mobile Application Development",
                          "Frontend development is not part of this engagement scope",
                          "If the Client requires a custom frontend, a formal Change Request shall be raised"))
    if "ci/cd" not in tech_lower and "devops" not in tech_lower:
        oos_items.append(("CI/CD Pipeline Automation",
                          "Manual deployment approach adopted for MVP; CI/CD not in initial scope",
                          "If the Client requires automated pipelines, a Change Request shall be raised"))
    oos_items.extend([
        ("Legacy System Decommissioning",
         "Decommissioning of existing systems is outside ECI's delivery responsibility",
         "If required, a separate decommissioning engagement shall be scoped and priced"),
        ("End-User Training Programme",
         "Formal training delivery (beyond knowledge-transfer sessions) is not included",
         "A training engagement can be scoped separately upon Change Request"),
        ("Hardware Procurement",
         "Physical hardware procurement is the Client's responsibility",
         "If ECI assistance is required, a Change Request shall be raised"),
        ("Software Licence Procurement",
         "Third-party licence procurement, negotiation, and payment are the Client's responsibility",
         "ECI can advise on licence requirements; procurement remains with the Client"),
        ("Penetration Testing",
         "Formal penetration testing is recommended as a separate specialist engagement",
         "If the Client requires ECI to arrange penetration testing, a Change Request shall be raised"),
        ("Ongoing Managed Support (Post-Hypercare)",
         "Support beyond the 30-day hypercare period is not included in this SOW",
         "A managed service agreement can be established via a separate Change Request"),
    ])
    for i, (excl, rationale, cr) in enumerate(oos_items):
        out_of_scope.append({
            "id": f"EX-{i+1:03d}",
            "exclusion": excl,
            "rationale": rationale,
            "change_request_condition": cr,
        })

    assumptions = []
    assump_items = []
    if any("azure" in t.lower() for t in tech):
        assump_items.append(("Client", "the Client shall provide an active Azure subscription with "
                             "Contributor or Owner access for the duration of the project",
                             "If access is not provided, project timelines and costs may be affected",
                             "Client to provision subscription and grant access prior to project kick-off"))
    if any("sharepoint" in t.lower() for t in tech):
        assump_items.append(("Client", "SharePoint Online with Read/Write access to the target document library "
                             "is available and accessible",
                             "Delayed or restricted access will impact integration delivery timelines",
                             "Client to configure SharePoint permissions prior to integration phase"))
    if any("teams" in t.lower() for t in tech):
        assump_items.append(("Client", "Microsoft Teams admin consent for bot registration and deployment "
                             "will be granted",
                             "Without admin consent, the Teams integration cannot be deployed",
                             "Client Teams administrator to approve consent during development phase"))
    assump_items.extend([
        ("Client", "a dedicated product owner is available for requirements sign-off and UAT approval",
         "Absence of a product owner will delay sign-off and may require re-scoping",
         "Client to nominate a product owner with authority to approve deliverables before project start"),
        ("Client", "subject matter experts (SMEs) are available for a minimum of 10 hours per week "
         "during the development phase",
         "Insufficient SME availability will increase risk of requirements misalignment and rework",
         "Client to confirm SME availability calendar prior to sprint planning"),
        ("ECI", "all source documents provided by the Client are in standard formats (PDF, Word, Excel) "
         "without password protection or DRM restrictions",
         "Protected or non-standard documents will require additional pre-processing effort",
         "Client to provide documents in accessible formats prior to discovery phase"),
        ("Client", "the Client's technical environment (network, firewalls, VPNs) allows connectivity "
         "to Azure services required by this solution",
         "Network restrictions may delay integration and testing activities",
         "Client IT team to confirm connectivity requirements during design phase"),
    ])
    for i, (party, stmt, consequence, obligation) in enumerate(assump_items):
        assumptions.append({
            "id": f"AS-{i+1:03d}",
            "party": party,
            "statement": f"It is assumed that {stmt}.",
            "consequence": f"Should this assumption prove incorrect, {consequence}.",
            "obligation": obligation,
        })

    prerequisites = []
    prereq_items = []
    if any("azure" in t.lower() for t in tech):
        prereq_items.append(("Active Azure Subscription", "Client", "Project Kick-Off",
                              "Project cannot commence; start date will be deferred until access is granted"))
    if any("ad" in t.lower() or "entra" in t.lower() for t in tech):
        prereq_items.append(("Azure AD / Entra ID Tenant with User Accounts", "Client", "Design Phase",
                              "Identity and access management components cannot be configured or tested"))
    if any("sharepoint" in t.lower() for t in tech):
        prereq_items.append(("SharePoint Site with Document Library Access Configured", "Client",
                              "Integration Development Phase",
                              "SharePoint integration delivery will be blocked and sprint re-planned"))
    prereq_items.extend([
        ("Signed Statement of Work (SOW)", "Client", "Project Kick-Off",
         "ECI cannot mobilise the project team; all activities are on hold"),
        ("Sample and Representative Test Data / Documents", "Client", "Development Phase — Sprint 1",
         "Development and testing will proceed with synthetic data, increasing re-work risk at UAT"),
        ("Nominated Project Stakeholders and RACI", "Client", "Project Kick-Off",
         "Decision-making will be impaired; ECI will escalate to Client project sponsor"),
    ])
    for i, (item, provided_by, milestone, consequence) in enumerate(prereq_items):
        prerequisites.append({
            "id": f"PR-{i+1:03d}",
            "item": item,
            "provided_by": provided_by,
            "milestone": milestone,
            "consequence_if_delayed": consequence,
        })

    return {
        "in_scope": in_scope,
        "out_of_scope": out_of_scope,
        "assumptions": assumptions,
        "prerequisites": prerequisites,
    }
