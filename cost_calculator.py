"""Cost Calculator Agent — Multi-cloud resource allocation and pricing.

Dynamically detects the target cloud platform (Azure / AWS / GCP / multi-cloud)
from the project's tech stack and requirements, then uses the correct service
catalog and pricing for that provider.
"""

from __future__ import annotations
from typing import Any


class CostCalculatorAgent:
    """Calculates detailed project cost breakdowns for any cloud platform."""

    # ECI Standard Rate Card (per hour)
    RATE_CARD = {
        "Architect":            200,
        "Lead Developer":       175,
        "Senior Developer":     155,
        "Developer":            130,
        "Frontend Developer":   135,
        "Integration Developer":140,
        "Data Architect":       185,
        "Data Engineer":        150,
        "UX Designer":          120,
        "QA Engineer":          110,
        "DevOps":               155,
        "Security Lead":        190,
        "Security Engineer":    150,
        "Business Analyst":     130,
        "Project Manager":      160,
        "Technical Writer":     90,
        "Support Team":         100,
    }

    # ── Azure catalog (East US, Pay-As-You-Go, 2026) ─────────────────
    AZURE_CATALOG = [
        {"service": "Azure App Service",        "tier": "P1v3 Linux",          "monthly_cost": 97,  "description": "2 vCPU 8 GB; $0.133/hr × 730 hrs"},
        {"service": "Azure Functions",          "tier": "Consumption",          "monthly_cost": 5,   "description": "First 1M executions free; typical light workload"},
        {"service": "Azure SQL Database",       "tier": "Standard S2",          "monthly_cost": 75,  "description": "50 DTUs; right-sized for typical workload"},
        {"service": "Azure Cosmos DB",          "tier": "Serverless",           "monthly_cost": 50,  "description": "$0.25/million RU + $0.25/GB; PoC sizing"},
        {"service": "Azure API Management",     "tier": "Basic",                "monthly_cost": 147, "description": "$0.201/hr × 730 hrs; 1 unit"},
        {"service": "Azure Blob Storage",       "tier": "Hot LRS 500 GB",       "monthly_cost": 9,   "description": "$0.018/GB/mo; Locally Redundant Storage"},
        {"service": "Azure Cache for Redis",    "tier": "Standard C1",          "monthly_cost": 55,  "description": "1 GB cache; SLA 99.9%"},
        {"service": "Azure DevOps",             "tier": "Basic",                "monthly_cost": 30,  "description": "First 5 users free; $6/user/mo additional"},
        {"service": "Azure Monitor",            "tier": "Pay-as-you-go",        "monthly_cost": 23,  "description": "$2.30/GB ingested; 10 GB/mo estimate"},
        {"service": "Azure Key Vault",          "tier": "Standard",             "monthly_cost": 5,   "description": "$0.03/10K operations"},
        {"service": "Microsoft Entra ID",       "tier": "Included M365",        "monthly_cost": 0,   "description": "Managed Identity — included in Microsoft 365 E3"},
    ]

    # ── AWS catalog (us-east-1, On-Demand, 2026) ─────────────────────
    AWS_CATALOG = [
        {"service": "EC2 t3.large (App Server)",    "tier": "t3.large On-Demand",      "monthly_cost": 60,  "description": "2 vCPU 8 GB; $0.0832/hr × 730 hrs"},
        {"service": "RDS MySQL db.t3.medium",       "tier": "db.t3.medium On-Demand",  "monthly_cost": 55,  "description": "2 vCPU 4 GB; $0.068/hr Single-AZ"},
        {"service": "AWS Lambda",                   "tier": "Compute + Requests",       "monthly_cost": 8,   "description": "1M req/mo; $0.20/million after free tier"},
        {"service": "S3 Standard (500 GB)",         "tier": "Standard Storage",         "monthly_cost": 12,  "description": "$0.023/GB/mo; 500 GB estimate"},
        {"service": "API Gateway (REST)",           "tier": "REST API",                 "monthly_cost": 35,  "description": "$3.50/million calls; 10M calls/mo estimate"},
        {"service": "ElastiCache r6g.medium",       "tier": "r6g.medium Redis",         "monthly_cost": 75,  "description": "13 GB; $0.103/hr × 730 hrs"},
        {"service": "CloudFront CDN",               "tier": "On-Demand",                "monthly_cost": 20,  "description": "10 TB transfer; $0.0085/GB after 10 TB"},
        {"service": "Amazon CloudWatch",            "tier": "Pay-as-you-go",            "monthly_cost": 15,  "description": "Metrics, logs, dashboards; $0.30/metric/mo"},
        {"service": "Amazon Cognito (50k MAU)",     "tier": "50,000 MAU",               "monthly_cost": 14,  "description": "First 50k free; $0.0055/MAU thereafter"},
        {"service": "SQS Standard Queue",           "tier": "Standard",                 "monthly_cost": 5,   "description": "First 1M free; $0.40/million after"},
        {"service": "AWS WAF",                      "tier": "Pay-per-use",              "monthly_cost": 30,  "description": "$5/web ACL/mo + $1/million requests"},
        {"service": "AWS CodePipeline / CodeBuild", "tier": "Pay-per-use",              "monthly_cost": 10,  "description": "CI/CD; $1/active pipeline/mo + build minutes"},
    ]

    # ── GCP catalog (us-central1, On-Demand, 2026) ───────────────────
    GCP_CATALOG = [
        {"service": "Cloud Run (standard)",         "tier": "Fully managed",            "monthly_cost": 35,  "description": "2 vCPU 4 GB; usage-based; typical small app"},
        {"service": "Cloud SQL PostgreSQL",         "tier": "db-standard-2",            "monthly_cost": 50,  "description": "2 vCPU 7.5 GB; $0.068/vCPU/hr"},
        {"service": "Cloud Storage (500 GB Std)",   "tier": "Standard Multi-region",    "monthly_cost": 10,  "description": "$0.020/GB/mo; multi-region US"},
        {"service": "Cloud Functions (2nd gen)",    "tier": "Compute + Requests",       "monthly_cost": 8,   "description": "2M invocations/mo; $0.40/million after free"},
        {"service": "Cloud Endpoints / API Gateway","tier": "Pay-per-call",             "monthly_cost": 30,  "description": "$3/million calls; 10M calls/mo estimate"},
        {"service": "Memorystore Redis (M1 Basic)", "tier": "M1 Basic",                 "monthly_cost": 55,  "description": "1 GB cache; $0.075/GB/hr × 730 hrs"},
        {"service": "GKE Standard Cluster",         "tier": "Standard mode",            "monthly_cost": 150, "description": "Cluster mgmt $0.10/hr + node costs"},
        {"service": "BigQuery (on-demand)",         "tier": "On-demand",                "monthly_cost": 25,  "description": "$6.25/TB queried; 4 TB/mo estimate"},
        {"service": "Cloud Pub/Sub",                "tier": "Pay-per-message",          "monthly_cost": 10,  "description": "$0.04/million messages; 250M/mo"},
        {"service": "Cloud Armor (Standard)",       "tier": "Standard",                 "monthly_cost": 25,  "description": "$5/policy/mo + $1/million requests"},
        {"service": "Cloud Logging",                "tier": "Pay-per-use",              "monthly_cost": 15,  "description": "$0.01/GB beyond 50 GB free/mo"},
        {"service": "Identity Platform",            "tier": "Spark plan",               "monthly_cost": 10,  "description": "10k MAU free; $0.0055/MAU after"},
    ]

    # ── Provider detection keywords ───────────────────────────────────
    _AWS_KEYWORDS = [
        "aws", "amazon web services", "ec2", " s3 ", "lambda", "rds ",
        "ecs ", "eks ", "cloudfront", "dynamodb", "cloudwatch", "cognito",
        "route 53", "elasticache", "kinesis", "sagemaker", "bedrock",
        "amazon aurora", "aws glue",
    ]
    _GCP_KEYWORDS = [
        "gcp", "google cloud", "bigquery", "cloud run", "gke ",
        "pub/sub", "pubsub", "firestore", "dataflow", "vertex ai",
        "cloud functions", "cloud storage gcp", "google kubernetes",
        "alloydb", "cloud spanner",
    ]
    _AZURE_KEYWORDS = [
        "azure", "microsoft azure", "cosmos db", "azure sql", "blob storage",
        "azure functions", "app service", "azure devops", "entra id",
        "azure kubernetes", "aks ", "azure openai", "copilot studio",
        "power bi", "sharepoint", "microsoft 365",
    ]

    # ── System prompt templates ───────────────────────────────────────
    _PROMPT_TMPL = (
        "You are an expert cost estimator for ECI, an IT consulting company. "
        "The project targets {provider_upper} as the primary cloud platform. "
        "Calculate comprehensive project costs including: ECI resource allocation by role, "
        "{cloud_desc} infrastructure services, third-party license costs, and profit margins. "
        "Use accurate {year} pay-as-you-go / on-demand pricing for {region_hint}. "
        "Example prices for this cloud: {examples}. "
        "Always include the tier and a brief justification in each service entry. "
        "Use ECI pricing tiers: Fixed Price, Time & Materials, Retainer. "
        "Respond in valid JSON with keys: "
        "total_cost (number), margin (string), pricing_model (string), "
        "breakdown (list of {{category, cost, percentage}}), "
        "resources (list of {{role, count, rate, hours, cost}}), "
        "'{cost_key}' (list of {{service, tier, monthly_cost, description}}), "
        "third_party_costs (list of {{name, monthly_cost, description}}), "
        "cloud_provider (string = '{provider}'), "
        "roi_estimate (string)."
    )

    _CLOUD_META: dict[str, dict] = {
        "azure": {
            "cost_key":    "azure_costs",
            "upper":       "Azure",
            "desc":        "Microsoft Azure",
            "region_hint": "East US region",
            "year":        "2026",
            "examples":    "App Service P1v3 $97/mo, SQL Database S2 $75/mo, API Management Basic $147/mo, Redis C1 $55/mo",
        },
        "aws": {
            "cost_key":    "aws_costs",
            "upper":       "AWS",
            "desc":        "Amazon Web Services",
            "region_hint": "us-east-1 region",
            "year":        "2026",
            "examples":    "EC2 t3.large $60/mo, RDS MySQL db.t3.medium $55/mo, Lambda $8/mo, ElastiCache r6g.medium $75/mo, S3 500GB $12/mo",
        },
        "gcp": {
            "cost_key":    "gcp_costs",
            "upper":       "GCP",
            "desc":        "Google Cloud Platform",
            "region_hint": "us-central1 region",
            "year":        "2026",
            "examples":    "Cloud Run $35/mo, Cloud SQL PostgreSQL $50/mo, Cloud Storage 500GB $10/mo, Memorystore Redis $55/mo, BigQuery $25/mo",
        },
        "multi-cloud": {
            "cost_key":    "aws_costs",
            "upper":       "Multi-Cloud (AWS + Azure)",
            "desc":        "AWS and Azure",
            "region_hint": "us-east-1 and East US",
            "year":        "2026",
            "examples":    "EC2 t3.large $60/mo, Azure SQL S2 $75/mo, S3 500GB $12/mo, Azure Redis C1 $55/mo",
        },
    }

    def __init__(self, azure_client: Any):
        self.client = azure_client

    # ── Provider detection ────────────────────────────────────────────
    @staticmethod
    def detect_provider(semantic: dict) -> str:
        """
        Inspect technology_stack and requirements to determine the target
        cloud platform.  Returns one of: 'azure' | 'aws' | 'gcp' | 'multi-cloud'.
        Defaults to 'azure' when no signals are found.
        """
        def _join(lst: list) -> str:
            parts = []
            for item in lst[:20]:
                if isinstance(item, dict):
                    parts.append(item.get("description", "") + " " + item.get("title", ""))
                else:
                    parts.append(str(item))
            return " ".join(parts).lower()

        tech_str = _join(semantic.get("technology_stack") or [])
        req_str  = _join(semantic.get("requirements") or [])
        text     = f" {tech_str} {req_str} "

        def _score(keywords: list[str]) -> int:
            return sum(1 for kw in keywords if kw in text)

        aws_score   = _score(CostCalculatorAgent._AWS_KEYWORDS)
        gcp_score   = _score(CostCalculatorAgent._GCP_KEYWORDS)
        azure_score = _score(CostCalculatorAgent._AZURE_KEYWORDS)

        # Require at least 2 hits to claim a provider
        top = sorted(
            [("aws", aws_score), ("gcp", gcp_score), ("azure", azure_score)],
            key=lambda x: x[1], reverse=True,
        )
        if top[0][1] < 2:
            return "azure"  # no strong signal — default
        if top[1][1] >= 2 and top[0][1] >= 2:
            return "multi-cloud"
        return top[0][0]

    # ── Main entry ────────────────────────────────────────────────────
    def calculate(self, semantic: dict, time_est: dict, rag_results: dict) -> dict:
        provider = self.detect_provider(semantic)
        meta     = self._CLOUD_META.get(provider, self._CLOUD_META["azure"])

        system_prompt = self._PROMPT_TMPL.format(
            provider_upper=meta["upper"],
            cloud_desc=meta["desc"],
            year=meta["year"],
            region_hint=meta["region_hint"],
            examples=meta["examples"],
            cost_key=meta["cost_key"],
            provider=provider,
        )

        context = {
            "requirements":      (semantic.get("requirements") or [])[:20],
            "complexity_score":  semantic.get("complexity_score", 5),
            "technology_stack":  semantic.get("technology_stack") or [],
            "cloud_provider":    provider,
            "time_estimate": {
                "total_hours": time_est.get("total_hours", 0),
                "phases": [
                    {"name": p.get("name", ""), "hours": p.get("hours", 0)}
                    for p in (time_est.get("phases") or [])
                ],
            },
            "benchmark_cost": rag_results.get("benchmark_cost", 0),
        }

        result = self.client.agent_completion("CostCalculator", system_prompt, context)
        if result and isinstance(result, dict):
            result.setdefault("cloud_provider", provider)
            # Ensure backward-compat azure_costs key is always present
            if provider != "azure" and "azure_costs" not in result:
                result["azure_costs"] = []
            return result

        return self._generate_cost(semantic, time_est, rag_results, provider)

    # ── Fallback cost generator ───────────────────────────────────────
    def _generate_cost(
        self,
        semantic:    dict,
        time_est:    dict,
        rag_results: dict,
        provider:    str = "azure",
    ) -> dict:
        phases      = time_est.get("phases") or []
        total_hours = time_est.get("total_hours") or 2000

        # ── Labor from phase tasks ────────────────────────────────────
        role_hours: dict[str, int] = {}
        for phase in phases:
            for task in (phase.get("tasks") or []):
                role  = task.get("role", "Developer")
                hours = int(task.get("hours") or 0)
                role_hours[role] = role_hours.get(role, 0) + hours

        resources  = []
        labor_cost = 0
        for role, hours in sorted(role_hours.items(), key=lambda x: x[1], reverse=True):
            rate = self.RATE_CARD.get(role, 130)
            cost = rate * hours
            labor_cost += cost
            resources.append({
                "role":  role,
                "count": max(1, hours // 320),
                "rate":  rate,
                "hours": hours,
                "cost":  cost,
            })

        # ── Select cloud catalog ──────────────────────────────────────
        catalog_map = {
            "azure":       self.AZURE_CATALOG,
            "aws":         self.AWS_CATALOG,
            "gcp":         self.GCP_CATALOG,
            "multi-cloud": self.AWS_CATALOG + self.AZURE_CATALOG[:4],
        }
        cloud_services = [dict(s) for s in catalog_map.get(provider, self.AZURE_CATALOG)]

        cost_key_map = {
            "azure":       "azure_costs",
            "aws":         "aws_costs",
            "gcp":         "gcp_costs",
            "multi-cloud": "aws_costs",
        }
        cost_key = cost_key_map.get(provider, "azure_costs")

        # ── Infrastructure total ──────────────────────────────────────
        project_months = max(3, total_hours // 640)
        infra_total    = sum(s.get("monthly_cost", 0) for s in cloud_services) * project_months

        # ── Third-party ───────────────────────────────────────────────
        third_party = [
            {"name": "Monitoring / APM (Datadog/New Relic)", "monthly_cost": 120, "description": "Full-stack observability"},
            {"name": "SSL/TLS Certificates",                 "monthly_cost": 10,  "description": "Wildcard SSL cert"},
            {"name": "Project Management (Jira/Linear)",     "monthly_cost": 50,  "description": "Team of ~8 users"},
        ]
        third_total = sum(t.get("monthly_cost", 0) for t in third_party) * project_months

        # ── Totals ────────────────────────────────────────────────────
        subtotal     = labor_cost + infra_total + third_total
        margin_rate  = 0.25
        margin_amt   = int(subtotal * margin_rate)
        total        = subtotal + margin_amt

        breakdown = [
            {"category": "Labor / Professional Services",  "cost": labor_cost,  "percentage": f"{labor_cost/max(total,1)*100:.0f}%"},
            {"category": f"{provider.upper()} Infrastructure", "cost": int(infra_total), "percentage": f"{infra_total/max(total,1)*100:.0f}%"},
            {"category": "Third-Party Licenses",           "cost": int(third_total), "percentage": f"{third_total/max(total,1)*100:.0f}%"},
            {"category": "Project Management & Overhead",  "cost": int(labor_cost * 0.08), "percentage": "8%"},
            {"category": "Profit Margin",                  "cost": margin_amt,  "percentage": f"{margin_rate*100:.0f}%"},
        ]

        complexity = semantic.get("complexity_score", 5)
        pricing    = "Time & Materials" if complexity >= 7 else "Fixed Price"

        result: dict = {
            "total_cost":       total,
            "margin":           f"{margin_rate*100:.0f}%",
            "pricing_model":    pricing,
            "breakdown":        breakdown,
            "resources":        resources,
            cost_key:           cloud_services,
            "third_party_costs":third_party,
            "cloud_provider":   provider,
            "roi_estimate":     (
                f"Projected ROI: 3.2× over 3 years based on "
                f"${int(total * 0.6):,} annual operational savings"
            ),
        }

        # Always include azure_costs key for backward compatibility
        if cost_key != "azure_costs":
            result["azure_costs"] = [] if provider != "multi-cloud" else self.AZURE_CATALOG[:4]

        return result
