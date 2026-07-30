# ═══════════════════════════════════════════════════════════════════════
#  DYNAMIC TEXT ANALYSIS ENGINE (No AI — pure NLP/regex)
# ═══════════════════════════════════════════════════════════════════════
import re
import json
import time as _tm
import concurrent.futures as _cf
import urllib.request
import urllib.error
import urllib.parse

_AZURE_PRICING_CACHE: dict = {"ts": 0.0, "data": {}}
_AZURE_PRICING_TTL   = 1800  # 30-minute module-level cache

_TECH_CATALOG = {
    # ── App Hosting ──────────────────────────────────────────────────────────
    "Azure App Service":          ["app service", "web app hosting", "azure web app"],
    "Azure Functions":            ["azure function", "serverless", "function app"],
    "Azure Container Apps":       ["container app", "docker", "kubernetes", "k8s", "aks",
                                   "azure kubernetes"],
    "Azure Static Web Apps":      ["static web app", "static webapp", "spa hosting"],
    # ── Data Platform ────────────────────────────────────────────────────────
    "Microsoft Fabric":           ["microsoft fabric", "fabric workspace", "fabric lakehouse",
                                   "fabric pipeline", "fabric dataflow", "fabric capacity",
                                   "fabric notebook", "onelake", "one lake",
                                   "fabric real-time", "fabric semantic model",
                                   "fabric eventhouse", "fabric kql"],
    "Azure Data Factory":         ["azure data factory", "data factory", "adf pipeline",
                                   " adf ", "data integration pipeline", "data ingestion pipeline"],
    "Azure Synapse Analytics":    ["azure synapse", "synapse analytics", "synapse workspace",
                                   "dedicated sql pool", "serverless sql pool",
                                   "synapse pipeline", "synapse spark"],
    "Azure Databricks":           ["azure databricks", "databricks", "spark notebook",
                                   "delta lake", "delta table", "databricks cluster",
                                   "databricks mlflow", "unity catalog"],
    "ADLS Gen2":                  ["adls gen2", "adls", "azure data lake storage",
                                   "data lake storage gen2", "hierarchical namespace", "datalake"],
    "Azure Stream Analytics":     ["stream analytics", "azure stream analytics",
                                   "real-time analytics job", "streaming job"],
    "Azure SQL Database":         ["azure sql", "sql database", "sql server", "azure sql db"],
    "Cosmos DB":                  ["cosmos db", "cosmosdb", "nosql"],
    "Azure Blob Storage":         ["blob storage", "file storage", "azure storage account"],
    "Azure Redis Cache":          ["redis", "redis cache", "in-memory cache"],
    "Azure PostgreSQL":           ["postgresql", "postgres", "azure postgres"],
    "Azure MySQL":                ["mysql", "azure mysql"],
    # ── AI / ML ──────────────────────────────────────────────────────────────
    "Azure OpenAI":               ["azure openai", "openai", "gpt-4", "gpt4", "gpt-4o",
                                   "gpt-35", "chat completion", "azure gpt"],
    "Azure AI Foundry":           ["ai foundry", "foundry", "claude"],
    "Azure Machine Learning":     ["azure machine learning", "azure ml", "aml workspace",
                                   "mlflow", "model registry", "ml training", "ml pipeline",
                                   "inference endpoint", "ml studio", "automl"],
    "Azure AI Search":            ["ai search", "cognitive search", "azure search",
                                   "vector search", "semantic search"],
    "Azure Cognitive Services":   ["cognitive services", "azure cognitive", "computer vision",
                                   "text analytics", "form recognizer", "document intelligence",
                                   "speech service", "translator", "language service"],
    "Azure Bot Service":          ["bot service", "azure bot", "bot framework", "chatbot"],
    # ── Integration / Messaging ──────────────────────────────────────────────
    "Azure Service Bus":          ["service bus", "message queue", "event-driven messaging"],
    "Azure Event Hubs":           ["event hub", "eventhub", "event streaming", "kafka",
                                   "real-time ingestion"],
    "Azure Event Grid":           ["event grid"],
    "Azure Logic Apps":           ["logic app", "workflow automation"],
    "Azure API Management":       ["api management", "apim", "api gateway"],
    # ── Identity / Security ──────────────────────────────────────────────────
    "Azure AD / Entra ID":        ["azure ad", "entra id", "active directory", "sso", "mfa",
                                   "identity", "entra", "b2c"],
    "Azure Key Vault":            ["key vault", "keyvault", "secrets management"],
    # ── Power Platform ───────────────────────────────────────────────────────
    "Power BI":                   ["power bi", "powerbi", "analytics dashboard", "pbi"],
    "Power Apps":                 ["power apps", "powerapps", "canvas app", "model-driven app"],
    "Power Automate":             ["power automate", "power automate flow", "automated flow"],
    # ── Microsoft 365 / Collab ───────────────────────────────────────────────
    "SharePoint":                 ["sharepoint", "sharepoint online", "document library",
                                   "sp site", "sharepoint site"],
    "Microsoft Teams":            ["microsoft teams", "teams bot", "teams app", "teams channel"],
    "Copilot Studio":             ["copilot studio", "copilot", "bot framework"],
    # ── DevOps / Infra ───────────────────────────────────────────────────────
    "Azure DevOps":               ["devops", "ci/cd", "azure pipeline", "azure boards",
                                   "azure repos"],
    "GitHub Actions":             ["github actions", "github ci", "github workflow"],
    "Azure Monitor":              ["azure monitor", "application insights", "app insights",
                                   "log analytics", "monitoring"],
    "Azure Front Door":           ["front door", "cdn", "azure cdn", "load balancing"],
    "Azure Purview":              ["azure purview", "microsoft purview", "data catalog",
                                   "data governance", "data lineage"],
    "SignalR":                    ["signalr", "real-time websocket", "websocket"],
}

# Technologies matched by explicit mandate phrases in the document
_MANDATE_PATTERNS = [
    r'\buse\s+(microsoft\s+fabric|microsoft\s+\w+|azure\s+[\w\s]+?(?=\b(?:for|to|as|and|,|\.)))',
    r'\busing\s+(microsoft\s+fabric|microsoft\s+\w+|azure\s+[\w\s]+?(?=\b(?:for|to|as|and|,|\.|$)))',
    r'\bwill\s+(?:be\s+)?(?:using|use|leverage|utilize)\s+(microsoft\s+\w+|azure\s+[\w\s]+?(?=\b(?:for|to|as|and|,|\.)))',
    r'\bmust\s+(?:use|leverage|utilize)\s+(microsoft\s+\w+|azure\s+[\w\s]+?)',
    r'\bbuilt\s+on\s+(microsoft\s+\w+|azure\s+[\w\s]+?(?=\b(?:for|to|and|,|\.)))',
    r'\bbased\s+on\s+(microsoft\s+\w+|azure\s+[\w\s]+?(?=\b(?:for|to|and|,|\.)))',
    r'\bplatform\s*[:\-]\s*(microsoft\s+\w+|azure\s+[\w\s]+?(?=\n|,|\.))',
    r'\btechnology\s+stack\s*[:\-]\s*([\w\s,]+?)(?=\n)',
    r'\bmandatory\s+technology\s*[:\-]\s*([\w\s,]+?)(?=\n)',
]


def _extract_mandated_tech(text_lower: str, detected_tech: list) -> list:
    """Return technologies that are explicitly mandated/required in the document,
    matched back against the known catalog entries."""
    mandated = set()
    # Pattern-based mandate extraction
    for pat in _MANDATE_PATTERNS:
        for m in re.finditer(pat, text_lower, re.IGNORECASE):
            phrase = m.group(1).strip().lower()
            for tech_name, keywords in _TECH_CATALOG.items():
                if any(kw in phrase for kw in keywords):
                    mandated.add(tech_name)
    # Also flag any detected tech that appears near mandate-signal words
    mandate_signals = ["use ", "using ", "will use", "platform:", "built on", "based on",
                       "required", "mandated", "specified", "chosen", "selected", "must use"]
    for tech_name, keywords in _TECH_CATALOG.items():
        for kw in keywords:
            if len(kw) < 5:
                continue
            idx = text_lower.find(kw)
            while idx != -1:
                window = text_lower[max(0, idx - 60):idx + len(kw) + 30]
                if any(sig in window for sig in mandate_signals):
                    mandated.add(tech_name)
                    break
                idx = text_lower.find(kw, idx + 1)
    return [t for t in mandated if t in detected_tech or len(detected_tech) == 0]

_LANG_CATALOG = {
    "Python": ["python", "flask", "django", "fastapi", "pytest"],
    ".NET / C#": [".net", "c#", "csharp", "asp.net", "blazor"],
    "Node.js": ["node.js", "nodejs", "express", "npm"],
    "React": ["react", "reactjs", "jsx", "next.js"],
    "Angular": ["angular"],
    "Vue.js": ["vue", "vuejs", "nuxt"],
    "Java / Spring": ["java", "spring", "springboot"],
    "TypeScript": ["typescript"],
}

# Azure Retail Prices — East US region, Pay-As-You-Go, April 2026
# Source: https://prices.azure.com/api/retail/prices
_INFRA_COST_CATALOG = {
    # ── App Hosting ─────────────────────────────────────────────────────────
    "Azure App Service":      ("P1v3 Linux",            97,  "2 vCPU 8 GB RAM; $0.133/hr x 730 hrs"),
    "Azure Functions":        ("Consumption",            5,   "First 1M executions/mo free; ~500K exec typical"),
    "Azure Container Apps":   ("Consumption",            45,  "$0.000024/vCPU-s + $0.000003/GB-s; small app"),
    "Azure Static Web Apps":  ("Standard",               9,   "$9/mo; custom domains, SSL, staging slots"),
    # ── Data Platform ────────────────────────────────────────────────────────
    "Microsoft Fabric":       ("F2 Capacity (2 CUs)",   526,  "2 CUs × $0.36/CU-hr × 730 hrs; covers Lakehouse, Notebooks, Pipelines, Warehouse, Power BI"),
    "Azure Data Factory":     ("Standard",              75,   "~15K activity runs/mo; data movement + transformation"),
    "Azure Synapse Analytics":("Serverless SQL Pool",   120,  "$5/TB queried; 24 TB/mo typical + DWH 100 DWUs"),
    "Azure Databricks":       ("Standard DS3_v2 cluster",300,  "4-node job cluster × 8h/day × 30 days; auto-terminate"),
    "ADLS Gen2":              ("Hot LRS 500 GB",        15,   "$0.018/GB + $0.004/10K write + $0.0004/10K read"),
    "Azure SQL Database":     ("Standard S2 (50 DTU)",  75,   "50 DTUs; right-sized for typical workload"),
    "Cosmos DB":              ("Autoscale 4000 RU/s",   240,  "Min 10% charge = 400 RU/s; $0.012/100RU-hr"),
    "Azure Blob Storage":     ("Hot LRS 500 GB",        9,    "$0.018/GB/mo; Hot tier, Locally Redundant Storage"),
    "Azure Redis Cache":      ("Standard C1 1 GB",      55,   "$55.48/mo; Standard tier, 1 GB, SLA 99.9%"),
    "Azure PostgreSQL":       ("Burstable B2ms",        70,   "2 vCPU 8 GB RAM; $0.096/hr x 730 hrs"),
    # ── AI / ML ──────────────────────────────────────────────────────────────
    "Azure AI Search":        ("Standard S1",           245,  "$0.336/hr x 730 hrs; 1 replica, 1 partition"),
    "Azure OpenAI":           ("GPT-4o Pay-per-token",  75,   "~15M input + 5M output tokens/mo; $2.50/$10 per 1M"),
    "Azure AI Foundry":       ("Claude 3.5 Sonnet",     100,  "~5M input + 2M output tokens/mo; $3/$15 per 1M"),
    "Azure Machine Learning": ("Compute cluster D2s_v3",150,  "2 vCPU 7 GB; ~200 training hrs/mo; workspace free"),
    "Azure Cognitive Services":("S0 Standard",          50,   "Document Intelligence + Language; ~50K pages/mo"),
    # ── Governance ────────────────────────────────────────────────────────────
    "Azure Purview":          ("Data Map 100 resources",75,   "$0.75/resource/mo × 100 resources; data catalog + lineage"),
    # ── Identity / Security ──────────────────────────────────────────────────
    "Azure Key Vault":        ("Standard",              1,    "$0.03/10K operations; secrets + managed identities"),
    "Azure AD / Entra ID":    ("Premium P1",            6,    "$6/user/mo; conditional access + MFA"),
    # ── Integration / Messaging ──────────────────────────────────────────────
    "Azure API Management":   ("Basic",                 147,  "$0.201/hr x 730 hrs; Basic tier, 1 unit"),
    "Azure Service Bus":      ("Standard",              10,   "$10/mo base; first 13M operations/mo included"),
    "Azure Event Hubs":       ("Standard 1 TU",         40,   "$10/TU/mo + $0.028/million events; 1 TU standard"),
    "Azure Logic Apps":       ("Consumption",           15,   "$0.000025/action; ~600K actions/mo typical"),
    "Azure Event Grid":       ("Per-operation",         5,    "$0.60/1M operations; first 100K free"),
    # ── DevOps / Infra ────────────────────────────────────────────────────────
    "Azure DevOps":           ("Basic",                 30,   "First 5 users free; $6/user/mo additional"),
    "Azure Monitor":          ("Pay-as-you-go",         23,   "Log Analytics $2.30/GB; 10 GB/mo ingestion"),
    "Azure Front Door":       ("Standard",              40,   "$35/mo base + $0.008/GB data transfer"),
    # ── Power Platform / M365 ────────────────────────────────────────────────
    "SharePoint":             ("Included M365",         0,    "Document storage — included in Microsoft 365"),
    "Microsoft Teams":        ("Included M365",         0,    "Collaboration — included in Microsoft 365"),
    "Copilot Studio":         ("Pay-as-you-go",         130,  "$0.01/message; ~13K messages/mo"),
    "Power BI":               ("Pro",                   10,   "$9.99/user/mo — Power BI Pro per user"),
    "Power Apps":             ("Per-app plan",          10,   "$10/user/mo × 1 app per user"),
    # ── Misc ─────────────────────────────────────────────────────────────────
    "SignalR":                ("Standard S1",           50,   "$50/mo; 1 unit, 1K concurrent connections"),
}

# Tier upgrade rules: when scope text contains any signal keyword, use higher tier + price.
# Format: service_name → [(signals_list, tier_label, monthly_usd, description), ...]
# First matching rule wins (ordered high→low tier).
_TIER_UPGRADE_SIGNALS: dict = {
    "Azure API Management": [
        (["premium", "zone redundan", "multi-region", "vnet injection", "internal mode",
          "private endpoint apim", "apim premium"],
         "Premium", 936, "~$1.28/hr × 730 hrs; Premium, zone-redundant, VNet-injected"),
        (["standard tier", "apim standard"],
         "Standard", 224, "~$0.307/hr × 730 hrs; Standard tier, 1 unit"),
    ],
    "Azure AI Search": [
        (["s2 ", "standard s2", "semantic ranker high", "high throughput search"],
         "Standard S2", 982, "~$1.34/hr × 730 hrs; S2 high-throughput"),
        (["basic search", "small index"],
         "Basic", 82, "~$0.113/hr × 730 hrs; Basic tier"),
    ],
    "Azure SQL Database": [
        (["business critical", "mission critical", "zone redundant sql", "in-memory oltp"],
         "Business Critical Gen5 2vC", 756, "~$1.035/hr × 730 hrs; BC, zone-redundant, in-memory OLTP"),
        (["premium sql", "premium tier sql", " p1 "],
         "Premium P1 (125 DTU)", 465, "$465/mo; Premium P1, SLA 99.99%"),
        (["hyperscale sql"],
         "Hyperscale Gen5 2vC", 370, "~$0.507/hr × 730 hrs; Hyperscale, auto-scale storage"),
    ],
    "Azure Databricks": [
        (["unity catalog", "delta live table", "databricks premium", "ml feature"],
         "Premium DS3_v2 cluster", 420, "4-node Premium cluster; Unity Catalog, ML features"),
    ],
    "Microsoft Fabric": [
        (["f4 ", "f8 ", "f16", "enterprise fabric", "large fabric"],
         "F4 Capacity (4 CUs)", 1052, "4 CUs × $0.36/CU-hr × 730 hrs"),
    ],
    "Azure Machine Learning": [
        (["gpu training", "a100", "v100", "nc6", "gpu cluster"],
         "NC6s_v3 GPU cluster", 490, "GPU compute; ~100 hrs/mo training workloads"),
    ],
    "Azure Container Apps": [
        (["dedicated plan", "high throughput container", "always-on"],
         "Dedicated D4", 280, "Dedicated D4 plan; always-on, predictable scaling"),
    ],
}

# Technologies that typically appear as EXISTING CLIENT SOURCE SYSTEMS, not built components.
# When detected near "source", "existing", "client has", "on-premises", etc., they are excluded from build costs.
_SOURCE_SYSTEM_SIGNALS = [
    "client's existing", "client has", "currently using", "currently resides",
    "existing database", "existing sql", "on-premises", "on premise", "on-prem",
    "local file server", "local server", "file server", "provide access to the",
    "provide access to an", "data inventory", "profiling summary", "legacy system",
    "source database", "source system", "data currently", "already exists",
    "data resides", "stored on", "access to existing",
]


def _detect_source_systems(text_lower: str, detected_tech: list) -> list:
    """Identify technologies that are the client's EXISTING/SOURCE systems, not to be built."""
    source_systems = set()
    for tech_name, keywords in _TECH_CATALOG.items():
        for kw in keywords:
            if len(kw) < 5:
                continue
            idx = text_lower.find(kw)
            while idx != -1:
                window = text_lower[max(0, idx - 120):idx + len(kw) + 60]
                if any(sig in window for sig in _SOURCE_SYSTEM_SIGNALS):
                    source_systems.add(tech_name)
                    break
                idx = text_lower.find(kw, idx + 1)
    return [t for t in source_systems if t in detected_tech]


def _fetch_live_azure_pricing() -> dict:
    """Fetch live monthly cost estimates (USD) from the Azure Retail Prices API.

    Requests fire in parallel (ThreadPoolExecutor) so all 15 services resolve
    in ~one RTT instead of 15 sequential round-trips.  Results are cached for
    30 minutes at module level so repeated calls within the same process are free.
    Falls back to empty dict on network error.
    """
    global _AZURE_PRICING_CACHE
    if _tm.time() - _AZURE_PRICING_CACHE["ts"] < _AZURE_PRICING_TTL and _AZURE_PRICING_CACHE["data"]:
        return _AZURE_PRICING_CACHE["data"]

    _SEARCH_TERMS = {
        "Azure App Service":    "App Service Premium",
        "Azure Functions":      "Azure Functions",
        "Azure SQL Database":   "SQL Database General Purpose",
        "Cosmos DB":            "Azure Cosmos DB",
        "Azure Blob Storage":   "General Block Blob",
        "Azure Key Vault":      "Key Vault",
        "Azure AI Search":      "Azure AI Search",
        "Azure Monitor":        "Log Analytics",
        "Azure Redis Cache":    "Azure Cache for Redis",
        "Azure Service Bus":    "Service Bus",
        "API Management":       "API Management",
        "Azure Container Apps": "Azure Container Apps",
        "Azure DevOps":         "Azure DevOps",
        "SignalR":              "SignalR Service",
        "Azure Event Grid":     "Event Grid",
    }

    def _fetch_one(svc_search):
        svc, search = svc_search
        try:
            qs = urllib.parse.urlencode({
                "api-version": "2023-01-01",
                "$filter":     (
                    f"contains(productName, '{search}') "
                    "and currencyCode eq 'USD' "
                    "and priceType eq 'Consumption'"
                ),
                "$top": "10",
            })
            url = "https://prices.azure.com/api/retail/prices?" + qs
            req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data  = json.loads(resp.read().decode("utf-8"))
                items = data.get("Items") or []
                if not items:
                    return svc, None
                hourly = [
                    it["retailPrice"]
                    for it in items
                    if it.get("unitOfMeasure", "").endswith("Hour") and it.get("retailPrice", 0) > 0
                ]
                monthly = [
                    it["retailPrice"]
                    for it in items
                    if "month" in it.get("unitOfMeasure", "").lower() and it.get("retailPrice", 0) > 0
                ]
                if hourly:
                    return svc, int(min(hourly[:3]) * 730)
                elif monthly:
                    return svc, int(min(monthly[:3]))
                return svc, None
        except Exception:
            return svc, None

    live_prices = {}
    try:
        with _cf.ThreadPoolExecutor(max_workers=8) as ex:
            for svc, price in ex.map(_fetch_one, _SEARCH_TERMS.items(), timeout=12):
                if price is not None:
                    live_prices[svc] = price
    except Exception:
        pass

    _AZURE_PRICING_CACHE = {"ts": _tm.time(), "data": live_prices}
    return live_prices


def _analyze_text_dynamic(text):
    """Analyze raw document text and extract requirements, tech stack, etc. without AI."""
    text_lower = text.lower() if text else ""
    words = text_lower.split()
    word_count = len(words)

    # ── Detect technologies ──
    detected_tech = []
    for tech_name, keywords in _TECH_CATALOG.items():
        for kw in keywords:
            if kw in text_lower:
                detected_tech.append(tech_name)
                break
    detected_langs = []
    for lang_name, keywords in _LANG_CATALOG.items():
        for kw in keywords:
            if kw in text_lower:
                detected_langs.append(lang_name)
                break

    # Always include baseline infra if any Azure detected
    baseline = ["Azure Key Vault", "Azure Monitor", "Azure Blob Storage"]
    for b in baseline:
        if b not in detected_tech and any("azure" in t.lower() for t in detected_tech):
            detected_tech.append(b)

    tech_stack = detected_tech + detected_langs

    # ── Extract requirements from sentences ──
    sentences = re.split(r'[.!?\n]+', text)
    req_keywords_func = ["implement", "develop", "build", "create", "process", "generate", "deploy",
                         "configure", "manage", "handle", "support", "enable", "provide", "upload",
                         "download", "ingest", "extract", "parse", "index", "retrieve", "query",
                         "orchestrat", "automat"]
    req_keywords_nf = ["performance", "security", "scalab", "availab", "complian", "reliab",
                       "latency", "throughput", "encrypt", "audit", "soc2", "gdpr", "sla",
                       "backup", "disaster", "recovery", "uptime"]
    req_keywords_int = ["integrat", "connect", "sync", "api", "sso", "webhook", "sharepoint",
                        "teams", "graph api", "rest api", "copilot", "power bi"]
    complex_indicators = ["multi-model", "orchestrat", "failover", "hybrid", "vector",
                          "embedding", "rag", "pipeline", "authentication", "authorization"]

    requirements = []
    seen_titles = set()
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 15 or len(sent) > 500:
            continue
        sent_lower = sent.lower()

        req_type = None
        # Check non-functional first — security/compliance sentences often contain
        # integration keywords (e.g. "API must use OAuth 2.0 encryption") and would
        # be misclassified if integration is checked first.
        if any(kw in sent_lower for kw in req_keywords_nf):
            req_type = "non-functional"
        elif any(kw in sent_lower for kw in req_keywords_int):
            req_type = "integration"
        elif any(kw in sent_lower for kw in req_keywords_func):
            req_type = "functional"

        if not req_type:
            continue

        title = sent[:80].strip()
        if title.startswith(("- ", "• ", "* ")):
            title = title[2:]
        title = title.split(",")[0].split(";")[0].strip()
        if len(title) < 5:
            continue
        title_key = title[:40].lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        complex_count = sum(1 for kw in complex_indicators if kw in sent_lower)
        complexity = "High" if complex_count >= 2 or len(sent) > 200 else "Medium" if complex_count >= 1 else "Low"
        priority = "P1" if complexity == "High" or any(w in sent_lower for w in ["critical", "must", "essential", "required"]) else "P2"

        requirements.append({
            "title": title,
            "description": sent.strip(),
            "type": req_type,
            "complexity": complexity,
            "priority": priority,
        })

    # Ensure minimum requirements if text is substantial
    if word_count > 100 and len(requirements) < 3:
        for tech in detected_tech[:5]:
            requirements.append({
                "title": tech + " setup and configuration",
                "description": "Setup and configure " + tech + " as identified in scope document.",
                "type": "functional" if "Service" in tech or "Function" in tech else "integration",
                "complexity": "Medium",
                "priority": "P2",
            })

    # ── Mandated technologies (explicitly required in doc) ──
    mandated_tech = _extract_mandated_tech(text_lower, detected_tech)

    # ── Source systems (client's existing/pre-existing systems — not to be built) ──
    source_systems = _detect_source_systems(text_lower, detected_tech)

    # ── Project domains (multi-value, specific) ──
    fabric_detected   = any("fabric" in t.lower() for t in detected_tech)
    synapse_detected  = any("synapse" in t.lower() for t in detected_tech)
    databricks_detect = any("databricks" in t.lower() for t in detected_tech)
    adf_detected      = any("data factory" in t.lower() for t in detected_tech)
    adls_detected     = any("adls" in t.lower() or "data lake" in t.lower() for t in detected_tech)
    aml_detected      = any("machine learning" in t.lower() for t in detected_tech)
    ai_count = sum(1 for t in detected_tech if any(k in t.lower() for k in ["ai", "openai", "foundry", "cognitive"]))
    int_count = sum(1 for t in detected_tech if any(k in t.lower() for k in ["sharepoint", "teams", "service bus", "logic", "event"]))
    sp_detected  = any("sharepoint" in t.lower() for t in detected_tech)
    app_detected = any(l in detected_langs for l in ["React", "Angular", "Vue.js"])

    project_domains = []
    if fabric_detected or synapse_detected or databricks_detect or adf_detected or adls_detected:
        project_domains.append("Data Engineering & Analytics")
    if ai_count >= 1 or aml_detected:
        project_domains.append("AI / ML")
    if sp_detected or int_count >= 2:
        project_domains.append("Integration & Collaboration")
    if app_detected:
        project_domains.append("Custom Application")
    if "migration" in text_lower or "migrate" in text_lower:
        project_domains.append("Cloud Migration")
    if any(k in text_lower for k in ["devops", "ci/cd", "kubernetes", "aks", "container"]):
        project_domains.append("DevOps & Platform")
    if not project_domains:
        project_domains.append("Enterprise Application")

    # ── Project type (primary, for backward compat) ──
    if fabric_detected or (synapse_detected and adf_detected):
        project_type = "Modern Data Platform"
    elif ai_count >= 2:
        project_type = "Data/Cloud/AI"
    elif int_count >= 3:
        project_type = "Integration Platform"
    elif sp_detected:
        project_type = "SharePoint Solution"
    elif app_detected:
        project_type = "Web Application"
    elif "migration" in text_lower or "migrate" in text_lower:
        project_type = "Cloud Migration"
    else:
        project_type = "Enterprise Application"

    # ── Complexity score ──
    score = 3
    score += min(3, len(detected_tech) * 0.4)
    score += min(2, len(requirements) * 0.15)
    if ai_count >= 1:
        score += 1.5
    if fabric_detected or synapse_detected:
        score += 1.0
    score += min(1.5, int_count * 0.3)
    score = min(10, max(1, int(round(score))))

    # ── Business objectives ──
    obj_keywords = ["goal", "objective", "achieve", "improve", "reduce", "increase",
                    "enhance", "optimize", "streamline", "automate", "enable"]
    objectives = []
    for sent in sentences:
        sent = sent.strip()
        if any(kw in sent.lower() for kw in obj_keywords) and 20 < len(sent) < 300:
            objectives.append(sent[:150].strip())
            if len(objectives) >= 5:
                break

    return {
        "requirements": requirements,
        "technology_stack": tech_stack if tech_stack else ["Azure App Service", "Python"],
        "mandated_technologies": mandated_tech,
        "source_systems": source_systems,
        "project_domains": project_domains,
        "business_objectives": objectives if objectives else ["Deliver project on time and within budget"],
        "complexity_score": score,
        "project_type": project_type,
    }
