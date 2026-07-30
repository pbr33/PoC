# ═══════════════════════════════════════════════════════════════════════
#  PIPELINE — main Streamlit tabs and workflow
# ═══════════════════════════════════════════════════════════════════════
import io
import os
import json
import time
import threading
import re
import copy as _copy
import hashlib
import zipfile
import sqlite3
import concurrent.futures as _cf
from datetime import datetime, timedelta

_AZURE_PRICING_CACHE: dict = {"ts": 0.0, "data": {}, "region": ""}

import streamlit as st

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    go = None
    px = None

from .utils import safe_int, safe_str, safe_list, safe_dict, sc_text
from .database import (save_run, load_runs, delete_run,
                       db_save_run, db_load_runs, db_load_results,
                       db_delete_run, db_mark_reviewed, db_category_counts,
                       db_set_review_status, db_archive_run, db_unarchive_run,
                       db_log_activity, db_get_activity_log,
                       db_update_outcome, db_check_duplicate, db_get_lineage,
                       db_get_version_chain, db_mark_submitted,
                       db_mark_winning_version, db_get_next_version_number,
                       _db_save_run, _db_load_runs, _db_load_results,
                       _db_delete_run, _db_mark_reviewed, _db_category_counts,
                       _DB_PATH)
from .styles import inject_css
from .ui_helpers import show_toast
from .command_palette import inject_command_palette
from .diagrams import (render_mermaid, render_mermaid_tabs, render_dot_to_svg,
                       render_dot_to_png, render_dot_to_html,
                       generate_3d_flythrough_html, generate_architecture_diagram,
                       generate_flow_diagram, extract_audio_transcript,
                       render_architecture_tab)
from .text_analysis import _analyze_text_dynamic
from .document_processor import DocProcessor
from .ai_clients import AnthropicAI, AzureAI, CodexAI, DeepSeekAI, GeminiAI, GrokAI, NanoAI, QwenAI, VertexAnthropicAI
from .external_services import SP, Mailer, ArchitectNarrator
from .excel_generators import generate_time_excel, generate_cost_excel, generate_lenox_excel, generate_monogram_excel
from .pdf_generators import generate_proposal_pdf, generate_sow_pdf, HAS_REPORTLAB
from .pptx_generator import generate_proposal_pptx, HAS_PPTX, build_premium_pptx_preview_html
from .final_estimation import generate_final_estimation
from .live_demo import log_agent, render_live_demo_tab
from .notifications import notify
from .config_loader import get_model_for_feature, is_any_ai_configured
from .scenario_builder import render_scenario_tab
from .cost_engine import render_team_roles_tab
from .review_feedback import (render_review_feedback_tab, render_feedback_admin_panel,
                               render_pending_review_banner, render_version_history_tab,
                               get_delivery_version_data)
from .animated_explainer import render_animated_explainer_tab
from .template_library import (
    CATEGORIES, PROJECT_TYPES, RISK_CATEGORIES, ROLES, TECHNOLOGIES,
    get_templates, add_template, update_template, delete_template,
    find_matching_templates, format_templates_for_prompt,
)


# ───────────────────────────────────────────────────────────────────────
#  Infrastructure cost catalog + live Azure pricing
# ───────────────────────────────────────────────────────────────────────

# Azure Retail Prices — East US region, Pay-As-You-Go, April 2026
# Source: https://prices.azure.com/api/retail/prices
_INFRA_COST_CATALOG = {
    "Azure App Service":    ("P1v3 Linux",           97,  "2 vCPU 8 GB RAM; $0.133/hr x 730 hrs"),
    "Azure Functions":      ("Consumption",           5,   "First 1M executions/mo free; ~500K exec typical"),
    "Azure Container Apps": ("Consumption",           45,  "$0.000024/vCPU-s + $0.000003/GB-s; small app"),
    "Azure SQL Database":   ("Standard S2 (50 DTU)",  75,  "50 DTUs; right-sized for typical workload"),
    "Cosmos DB":            ("Autoscale 4000 RU/s",   240, "Min 10% charge = 400 RU/s; $0.012/100RU-hr"),
    "Azure Blob Storage":   ("Hot LRS 500 GB",        9,   "$0.018/GB/mo; Hot tier, Locally Redundant Storage"),
    "Azure Redis Cache":    ("Standard C1 1 GB",      55,  "$55.48/mo; Standard tier, 1 GB, SLA 99.9%"),
    "Azure AI Search":      ("Standard S1",           245, "$0.336/hr x 730 hrs; 1 replica, 1 partition"),
    "Azure OpenAI":         ("GPT-4o Pay-per-token",  75,  "~15M input + 5M output tokens/mo; $2.50/$10 per 1M"),
    "Azure AI Foundry":     ("Claude 3.5 Sonnet",     100, "~5M input + 2M output tokens/mo; $3/$15 per 1M"),
    "Azure Key Vault":      ("Standard",              1,   "$0.03/10K operations; secrets + managed identities"),
    "Azure AD / Entra ID":  ("Premium P1",            6,   "$6/user/mo; conditional access + MFA"),
    "API Management":       ("Basic",                 147, "$0.201/hr x 730 hrs; Basic tier, 1 unit"),
    "Azure Front Door":     ("Standard",              40,  "$35/mo base + $0.008/GB data transfer"),
    "Azure Service Bus":    ("Standard",              10,  "$10/mo base; first 13M operations/mo included"),
    "Azure Logic Apps":     ("Consumption",           15,  "$0.000025/action; ~600K actions/mo typical"),
    "Azure Event Grid":     ("Per-operation",         5,   "$0.60/1M operations; first 100K free"),
    "SignalR":              ("Standard S1",           50,  "$50/mo; 1 unit, 1K concurrent connections"),
    "Azure DevOps":         ("Basic",                 30,  "First 5 users free; $6/user/mo additional"),
    "Azure Monitor":        ("Pay-as-you-go",         23,  "Log Analytics $2.30/GB; 10 GB/mo ingestion"),
    "SharePoint":           ("Included M365",         0,   "Document storage — included in Microsoft 365"),
    "Microsoft Teams":      ("Included M365",         0,   "Collaboration — included in Microsoft 365"),
    "Copilot Studio":       ("Pay-as-you-go",         130, "$0.01/message; ~13K messages/mo"),
    "Power BI":             ("Pro",                   10,  "$9.99/user/mo — Power BI Pro per user"),
}


def _detect_cloud_provider(ce: dict, se: dict | None = None) -> str:
    """
    Detect cloud provider from cost_estimate + optional semantic_analysis.

    Priority:
      1. Explicit 'cloud_provider' field on cost_estimate
      2. Semantic tech-stack / requirements keyword scan  ← most reliable
      3. Populated cost keys (aws_costs / gcp_costs present)
      4. Default: 'azure'
    """
    # 1. Explicit declaration
    declared = str(ce.get("cloud_provider", "")).lower().strip()
    if declared in ("azure", "aws", "gcp", "multi-cloud"):
        return declared

    # 2. Scan semantic analysis — the user wrote this, so it's ground truth
    if se:
        tech_items = safe_list(se.get("technology_stack") or [])
        req_items  = safe_list(se.get("requirements")     or [])

        tech_text = " ".join(str(t) for t in tech_items).lower()
        req_text  = " ".join(
            (r.get("description", "") + " " + r.get("title", "")
             if isinstance(r, dict) else str(r))
            for r in req_items[:20]
        ).lower()
        full = tech_text + " " + req_text

        _AWS_KW = [
            "aws", "amazon web services", "amazon s3", "s3 glacier", "s3 standard",
            "s3 intelligent", "amazon ec2", "ec2 ", " ec2", "aws lambda", " lambda",
            "amazon rds", " rds ", "amazon ecs", " ecs ", "amazon eks", " eks ",
            "cloudfront", "dynamodb", "amazon dynamodb", "cloudwatch", "amazon cloudwatch",
            "elasticache", "kinesis", "sagemaker", "aws bedrock", "aurora",
            "aws glue", "route53", "route 53", "amazon cognito", "aws waf",
            "amazon redshift", "aws fargate", "elastic beanstalk", "aws codecommit",
        ]
        _GCP_KW = [
            "gcp", "google cloud", "bigquery", "cloud run", "gke",
            "pub/sub", "pubsub", "google pub/sub", "firestore", "dataflow",
            "vertex ai", "google kubernetes", "alloydb", "cloud spanner",
            "cloud sql", "google cloud storage", "cloud build", "cloud armor gcp",
            "cloud functions", "memorystore", "anthos",
        ]
        _AZ_KW = [
            "azure", "microsoft azure", "cosmos db", "azure sql", "azure blob",
            "azure functions", "app service", "azure devops", "entra id", "azure ad",
            "azure kubernetes", " aks ", "azure openai", "copilot studio",
            "azure monitor", "azure key vault", "azure service bus",
        ]

        aws_score = sum(1 for kw in _AWS_KW if kw in full)
        gcp_score = sum(1 for kw in _GCP_KW if kw in full)
        az_score  = sum(1 for kw in _AZ_KW  if kw in full)

        top = sorted(
            [("aws", aws_score), ("gcp", gcp_score), ("azure", az_score)],
            key=lambda x: x[1], reverse=True,
        )
        if top[0][1] >= 1:                              # at least one hit
            if top[0][1] >= 2 and top[1][1] >= 2:      # two providers both strong
                return "multi-cloud"
            return top[0][0]

    # 3. Populated cost keys
    if ce.get("aws_costs"):
        return "aws"
    if ce.get("gcp_costs"):
        return "gcp"

    return "azure"


def _get_all_cloud_costs(ce: dict) -> list:
    """Return ALL cloud service entries regardless of which key they live under."""
    out = []
    for key in ("azure_costs", "aws_costs", "gcp_costs", "cloud_costs",
                "services", "infrastructure_costs", "cost_breakdown",
                "monthly_breakdown", "cloud_services"):
        for item in (ce.get(key) or []):
            if isinstance(item, dict) and item:
                out.append(item)
    # De-duplicate by service name (keep first occurrence)
    seen, deduped = set(), []
    for item in out:
        nm = str(item.get("service", "") or item.get("name", "")).strip().lower()
        if nm and nm not in seen:
            seen.add(nm)
            deduped.append(item)
    return deduped


# Broad keyword catalog for fuzzy fallback when the AI omits per-service costs.
# Keys are lowercase substrings; first match wins (most specific first).
_AZURE_BROAD_CATALOG: dict[str, int] = {
    "app service plan":      73,   "app service":           73,
    "azure functions":       20,   "function app":          20,   "functions":         15,
    "azure sql":            185,   "sql database":         185,   "sql managed":       250,
    "cosmos db":             25,   "cosmos":                25,
    "postgresql":            55,   "mysql":                 45,   "mariadb":           40,
    "blob storage":          20,   "azure storage":         20,   "storage account":   20,
    "data lake":             35,   "adls":                  35,
    "azure key vault":        5,   "key vault":              5,
    "azure ai search":       75,   "cognitive search":      75,   "ai search":         60,
    "azure monitor":         30,   "log analytics":         30,   "application insights": 20,
    "azure redis cache":     55,   "redis cache":           55,   "redis":             40,
    "azure service bus":     10,   "service bus":           10,
    "api management":        48,   "apim":                  48,
    "container apps":        40,   "container instances":   30,
    "azure kubernetes":     150,   "aks":                  150,   "kubernetes":        120,
    "azure devops":          30,   "devops":                25,
    "signalr":               50,
    "event grid":             5,   "event hub":             20,
    "microsoft 365":         50,   "office 365":            50,   "microsoft365":      50,
    "teams":                 15,   "sharepoint":            20,   "power bi":          15,
    "azure active directory": 12,  "active directory":      12,   "entra":             12,
    "azure ad":              12,
    "virtual machine":       70,   " vm ":                  60,   "vmss":              80,
    "azure vpn":             25,   "vpn gateway":           25,
    "azure firewall":        80,   "firewall":              60,
    "front door":            40,   "cdn":                   20,   "content delivery":  20,
    "load balancer":         20,   "application gateway":   60,
    "azure backup":          15,   "site recovery":         25,   "backup":            15,
    "azure databricks":     200,   "databricks":           180,
    "azure synapse":        100,   "synapse":               80,
    "data factory":          50,   "azure data factory":    50,
    "logic apps":            15,   "logic app":             15,
    "azure openai":         120,   "openai":               100,
    "cognitive services":    30,   "azure ai":              40,
    "machine learning":      60,   "azure ml":              60,
    "bot service":           10,   "bot":                   10,
    "communication services": 10,  "azure communication":   10,
    "notification hubs":      5,   "notification":           5,
    "azure stream analytics": 25,  "stream analytics":      25,
    "power automate":        15,   "power apps":            20,
    "azure purview":         60,   "purview":               60,
    "azure sentinel":        50,   "sentinel":              50,   "defender":          40,
    "azure dns":              5,   "dns":                    5,
    "traffic manager":       10,
}


def _broad_catalog_cost(service_name: str) -> int:
    """Fuzzy-match service_name against _AZURE_BROAD_CATALOG; return monthly cost or 0."""
    nl = " " + service_name.lower() + " "
    for kw, cost in _AZURE_BROAD_CATALOG.items():
        if kw in nl:
            return cost
    return 0


# Provider UI config: (display_name, accent_color, region_label, default_region)
_PROVIDER_UI = {
    "azure":       ("Azure",       "#00d4aa", "Azure Region",     "East US (Virginia)"),
    "aws":         ("AWS",         "#FF9900", "AWS Region",       "US East (N. Virginia)"),
    "gcp":         ("GCP",         "#4285F4", "GCP Region",       "us-central1 (Iowa)"),
    "multi-cloud": ("Multi-Cloud", "#a78bfa", "Primary Region",   "East US (Virginia)"),
}

# Static AWS catalog for live-pricing fallback (us-east-1, On-Demand, Apr-2026)
_AWS_STATIC_CATALOG: dict[str, int] = {
    "EC2 t3.large (App Server)":     60,
    "RDS MySQL db.t3.medium":        55,
    "AWS Lambda":                    8,
    "S3 Standard (500 GB)":          12,
    "API Gateway (REST)":            35,
    "ElastiCache r6g.medium":        75,
    "CloudFront CDN":                20,
    "Amazon CloudWatch":             15,
    "Amazon Cognito (50k MAU)":      14,
    "SQS Standard Queue":            5,
    "AWS WAF":                       30,
    "AWS CodePipeline / CodeBuild":  10,
    "DynamoDB (on-demand)":          25,
    "EKS Cluster":                   150,
    "Amazon SES":                    5,
}

# Static GCP catalog (us-central1, On-Demand, Apr-2026)
_GCP_STATIC_CATALOG: dict[str, int] = {
    "Cloud Run (standard)":          35,
    "Cloud SQL PostgreSQL":          50,
    "Cloud Storage (500 GB Std)":    10,
    "Cloud Functions (2nd gen)":     8,
    "Cloud Endpoints / API Gateway": 30,
    "Memorystore Redis (M1 Basic)":  55,
    "GKE Standard Cluster":          150,
    "BigQuery (on-demand)":          25,
    "Cloud Pub/Sub":                 10,
    "Cloud Armor (Standard)":        25,
    "Cloud Logging":                 15,
    "Identity Platform":             10,
}

# Full service list-of-dicts for AWS/GCP catalog fallback (used when AI returned wrong provider)
_AWS_CATALOG_SERVICES: list[dict] = [
    {"service": "EC2 t3.large (App Server)",    "category": "Compute",   "monthly_cost": 60,  "description": "Application server (2 vCPU, 8 GB RAM)"},
    {"service": "RDS MySQL db.t3.medium",        "category": "Database",  "monthly_cost": 55,  "description": "Managed relational DB (2 vCPU, 4 GB)"},
    {"service": "AWS Lambda",                    "category": "Compute",   "monthly_cost": 8,   "description": "Serverless functions (1M req/mo)"},
    {"service": "S3 Standard (500 GB)",          "category": "Storage",   "monthly_cost": 12,  "description": "Object storage — standard tier"},
    {"service": "API Gateway (REST)",            "category": "Networking","monthly_cost": 35,  "description": "Managed REST API gateway"},
    {"service": "ElastiCache r6g.medium",        "category": "Cache",     "monthly_cost": 75,  "description": "In-memory cache (Redis)"},
    {"service": "CloudFront CDN",                "category": "Networking","monthly_cost": 20,  "description": "Global content delivery network"},
    {"service": "Amazon CloudWatch",             "category": "Monitoring","monthly_cost": 15,  "description": "Metrics, logs, and alarms"},
    {"service": "Amazon Cognito (50k MAU)",      "category": "Security",  "monthly_cost": 14,  "description": "User identity and auth pool"},
    {"service": "SQS Standard Queue",            "category": "Messaging", "monthly_cost": 5,   "description": "Managed message queue"},
    {"service": "AWS WAF",                       "category": "Security",  "monthly_cost": 30,  "description": "Web application firewall"},
    {"service": "AWS CodePipeline / CodeBuild",  "category": "DevOps",    "monthly_cost": 10,  "description": "CI/CD pipeline"},
    {"service": "DynamoDB (on-demand)",          "category": "Database",  "monthly_cost": 25,  "description": "Serverless NoSQL database"},
    {"service": "EKS Cluster",                   "category": "Compute",   "monthly_cost": 150, "description": "Managed Kubernetes cluster"},
    {"service": "Amazon SES",                    "category": "Messaging", "monthly_cost": 5,   "description": "Transactional email service"},
]

_GCP_CATALOG_SERVICES: list[dict] = [
    {"service": "Cloud Run (standard)",          "category": "Compute",   "monthly_cost": 35,  "description": "Serverless containers"},
    {"service": "Cloud SQL PostgreSQL",          "category": "Database",  "monthly_cost": 50,  "description": "Managed PostgreSQL (2 vCPU, 7.5 GB)"},
    {"service": "Cloud Storage (500 GB Std)",    "category": "Storage",   "monthly_cost": 10,  "description": "Object storage — standard tier"},
    {"service": "Cloud Functions (2nd gen)",     "category": "Compute",   "monthly_cost": 8,   "description": "Serverless functions"},
    {"service": "Cloud Endpoints / API Gateway", "category": "Networking","monthly_cost": 30,  "description": "Managed API gateway"},
    {"service": "Memorystore Redis (M1 Basic)",  "category": "Cache",     "monthly_cost": 55,  "description": "In-memory Redis cache"},
    {"service": "GKE Standard Cluster",          "category": "Compute",   "monthly_cost": 150, "description": "Managed Kubernetes cluster"},
    {"service": "BigQuery (on-demand)",          "category": "Database",  "monthly_cost": 25,  "description": "Serverless analytics warehouse"},
    {"service": "Cloud Pub/Sub",                 "category": "Messaging", "monthly_cost": 10,  "description": "Managed message broker"},
    {"service": "Cloud Armor (Standard)",        "category": "Security",  "monthly_cost": 25,  "description": "Web application firewall + DDoS protection"},
    {"service": "Cloud Logging",                 "category": "Monitoring","monthly_cost": 15,  "description": "Centralised log management"},
    {"service": "Identity Platform",             "category": "Security",  "monthly_cost": 10,  "description": "User identity and auth"},
]

# AWS regions for the region selector
_AWS_REGIONS = {
    "US East (N. Virginia)":        "us-east-1",
    "US East (Ohio)":               "us-east-2",
    "US West (N. California)":      "us-west-1",
    "US West (Oregon)":             "us-west-2",
    "Canada (Central)":             "ca-central-1",
    "EU (Ireland)":                 "eu-west-1",
    "EU (London)":                  "eu-west-2",
    "EU (Frankfurt)":               "eu-central-1",
    "EU (Paris)":                   "eu-west-3",
    "Asia Pacific (Singapore)":     "ap-southeast-1",
    "Asia Pacific (Sydney)":        "ap-southeast-2",
    "Asia Pacific (Tokyo)":         "ap-northeast-1",
    "Asia Pacific (Mumbai)":        "ap-south-1",
    "South America (São Paulo)":    "sa-east-1",
}

# GCP regions
_GCP_REGIONS = {
    "us-central1 (Iowa)":           "us-central1",
    "us-east1 (S. Carolina)":       "us-east1",
    "us-east4 (N. Virginia)":       "us-east4",
    "us-west1 (Oregon)":            "us-west1",
    "us-west2 (Los Angeles)":       "us-west2",
    "northamerica-northeast1 (Montréal)": "northamerica-northeast1",
    "europe-west1 (Belgium)":       "europe-west1",
    "europe-west2 (London)":        "europe-west2",
    "europe-west3 (Frankfurt)":     "europe-west3",
    "asia-east1 (Taiwan)":          "asia-east1",
    "asia-northeast1 (Tokyo)":      "asia-northeast1",
    "asia-south1 (Mumbai)":         "asia-south1",
    "australia-southeast1 (Sydney)":"australia-southeast1",
}


def _fetch_live_azure_pricing(region: str = "eastus") -> dict:
    """Fetch live monthly cost estimates (USD) from the Azure Retail Prices API.

    All 15 service requests fire in parallel via ThreadPoolExecutor — reducing
    wall-clock time from ~15×RTT to ~1×RTT.  Results are cached for 30 minutes
    at module level; region changes flush the cache automatically.
    Falls back to static catalog prices on any network failure.
    """
    import urllib.request, urllib.parse

    global _AZURE_PRICING_CACHE
    _TTL = 1800
    if (time.time() - _AZURE_PRICING_CACHE["ts"] < _TTL
            and _AZURE_PRICING_CACHE["data"]
            and _AZURE_PRICING_CACHE.get("region") == region):
        return _AZURE_PRICING_CACHE["data"]

    # (catalog_name, azure_serviceName, preferred_sku_keywords)
    _SERVICES = [
        ("Azure App Service",    "Azure App Service",      ["Standard", "S2", "S1"]),
        ("Azure Functions",      "Azure Functions",        ["Consumption", "Execution"]),
        ("Azure SQL Database",   "SQL Database",           ["General Purpose", "2 vCore"]),
        ("Cosmos DB",            "Azure Cosmos DB",        ["Request Unit", "RU"]),
        ("Azure Blob Storage",   "Storage",                ["Hot LRS", "LRS", "Block Blob"]),
        ("Azure Key Vault",      "Key Vault",              ["Standard"]),
        ("Azure AI Search",      "Azure AI Search",        ["Basic", "Standard S1"]),
        ("Azure Monitor",        "Log Analytics",          ["Analytics Logs"]),
        ("Azure Redis Cache",    "Azure Cache for Redis",  ["C1", "Basic", "Standard"]),
        ("Azure Service Bus",    "Service Bus",            ["Standard"]),
        ("API Management",       "API Management",         ["Basic", "Developer"]),
        ("Azure Container Apps", "Azure Container Apps",   ["Dedicated", "Consumption"]),
        ("Azure DevOps",         "Azure DevOps",           ["Basic", "User"]),
        ("SignalR",              "SignalR Service",         ["Standard", "Unit 1"]),
        ("Azure Event Grid",     "Event Grid",             ["Standard"]),
    ]

    _STATIC_FALLBACK = {
        "Azure App Service":    73,
        "Azure Functions":      20,
        "Azure SQL Database":   185,
        "Cosmos DB":            25,
        "Azure Blob Storage":   20,
        "Azure Key Vault":      5,
        "Azure AI Search":      75,
        "Azure Monitor":        30,
        "Azure Redis Cache":    55,
        "Azure Service Bus":    10,
        "API Management":       48,
        "Azure Container Apps": 40,
        "Azure DevOps":         30,
        "SignalR":              50,
        "Azure Event Grid":     5,
    }

    _SKIP = ("Spot", "Low Priority", "Dev/Test", "Managed HSM", " HSM")

    def _fetch_one(svc_tuple):
        catalog_name, svc_name, sku_keywords = svc_tuple
        try:
            filt = (
                f"serviceName eq '{svc_name}' "
                "and currencyCode eq 'USD' "
                f"and armRegionName eq '{region}'"
            )
            filt_enc = urllib.parse.quote(filt)
            url = f"https://prices.azure.com/api/retail/prices?$filter={filt_enc}&$top=50"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                items = json.loads(resp.read().decode("utf-8")).get("Items") or []

            items = [
                i for i in items
                if not any(x in (i.get("skuName", "") + " " + i.get("productName", "")) for x in _SKIP)
                and i.get("retailPrice", 0) > 0
            ]
            if not items:
                return catalog_name, _STATIC_FALLBACK.get(catalog_name, 0)

            def _score(item):
                sku = (item.get("skuName", "") + " " + item.get("productName", "")).lower()
                for idx, kw in enumerate(sku_keywords):
                    if kw.lower() in sku:
                        return idx
                return len(sku_keywords)

            items.sort(key=_score)
            best = items[:5]
            hourly  = [i["retailPrice"] for i in best if "Hour"  in i.get("unitOfMeasure", "")]
            monthly = [i["retailPrice"] for i in best if "Month" in i.get("unitOfMeasure", "")]
            static_ref = _STATIC_FALLBACK.get(catalog_name, 500)

            if hourly:
                computed = int(min(hourly) * 730)
                return catalog_name, static_ref if computed > static_ref * 5 else max(5, computed)
            elif monthly:
                return catalog_name, max(1, int(min(monthly)))
            return catalog_name, static_ref

        except Exception:
            return catalog_name, _STATIC_FALLBACK.get(catalog_name, 0)

    live_prices = {}
    try:
        with _cf.ThreadPoolExecutor(max_workers=8) as ex:
            for name, price in ex.map(_fetch_one, _SERVICES, timeout=15):
                if price:
                    live_prices[name] = price
    except Exception:
        live_prices = {k: v for k, (_, v, _d) in zip(
            [s[0] for s in _SERVICES], _SERVICES) if v}
        live_prices = {n: _STATIC_FALLBACK.get(n, 0) for n, _, _ in _SERVICES}

    _AZURE_PRICING_CACHE = {"ts": time.time(), "data": live_prices, "region": region}
    return {k: v for k, v in live_prices.items() if v > 0}


# ───────────────────────────────────────────────────────────────────────
#  Pipeline stepper + KPI card helpers
# ───────────────────────────────────────────────────────────────────────

def _pipeline_stepper_html(steps: list, current_idx: int) -> str:
    """Return HTML for a horizontal animated pipeline stepper."""
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
    """Return an HTML KPI card. When animated=True, add the living gradient border."""
    extra_cls = " kpi-glow" if animated else ""
    return (
        f'<div class="kpi{extra_cls}">'
        f'<div class="kpi-i">{icon}</div>'
        f'<div class="kpi-v">{value}</div>'
        f'<div class="kpi-t">{title}</div>'
        f'<div class="kpi-s">{subtitle}</div>'
        f"</div>"
    )


# ───────────────────────────────────────────────────────────────────────
#  Home stats banner (live DB counts)
# ───────────────────────────────────────────────────────────────────────

def _home_stats_banner():
    """Render a live stats strip at the top of the Business Estimation tab."""
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


# ───────────────────────────────────────────────────────────────────────
#  Animated empty-state components
# ───────────────────────────────────────────────────────────────────────

def _empty_upload():
    """Animated empty state for the home screen (no file uploaded yet)."""
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


# ═══════════════════════════════════════════════════════════════════════
#  BELLA — Business Estimation & Lifecycle Learning Advisor
#  Powered by Claude Opus 4.8 · Streaming · Full proposal awareness
# ═══════════════════════════════════════════════════════════════════════

_BELLA_CSS = """
<style>
@keyframes bella-pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.55;transform:scale(.82)}}
@keyframes bella-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes bella-glow{0%,100%{box-shadow:0 0 22px rgba(99,102,241,.35),0 0 48px rgba(99,102,241,.1)}50%{box-shadow:0 0 34px rgba(99,102,241,.6),0 0 70px rgba(99,102,241,.22)}}
@keyframes bella-scan{0%{background-position:-100% 0}100%{background-position:220% 0}}
@keyframes bella-fadein{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes bella-slidel{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:translateX(0)}}
@keyframes bella-slider{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}
@keyframes bella-typing{0%,60%,100%{transform:translateY(0);opacity:.35}30%{transform:translateY(-7px);opacity:1}}
@keyframes bella-ctxpop{from{opacity:0;transform:scale(.88)}to{opacity:1;transform:scale(1)}}

/* ── Header ──────────────────────────────────────────── */
.bella-hdr{
  background:linear-gradient(135deg,#05091a 0%,#0d1229 45%,#150b2e 100%);
  border:1px solid rgba(99,102,241,.28);border-radius:20px 20px 0 0;
  padding:22px 28px;display:flex;align-items:center;gap:18px;
  position:relative;overflow:hidden;
}
.bella-hdr::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent 0%,rgba(99,102,241,.055) 35%,rgba(168,85,247,.07) 65%,transparent 100%);
  background-size:200% 100%;animation:bella-scan 5s linear infinite;pointer-events:none;
}
.bella-av{
  width:54px;height:54px;flex-shrink:0;
  background:linear-gradient(135deg,#4338ca 0%,#7c3aed 55%,#a855f7 100%);
  border-radius:17px;display:flex;align-items:center;justify-content:center;
  font-size:1.55rem;animation:bella-glow 3.5s ease-in-out infinite;
  box-shadow:0 6px 28px rgba(99,102,241,.45);
}
.bella-idn{flex:1;min-width:0;}
.bella-name{
  font-size:1.12rem;font-weight:800;letter-spacing:-.015em;
  background:linear-gradient(135deg,#e0e7ff,#c4b5fd,#a78bfa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.bella-title{font-size:.68rem;color:#5b5fdb;font-weight:700;text-transform:uppercase;letter-spacing:.13em;margin-top:3px;}
.bella-badges{display:flex;gap:5px;margin-top:9px;flex-wrap:wrap;}
.ab{font-size:.6rem;font-weight:700;border-radius:20px;padding:2px 10px;letter-spacing:.04em;white-space:nowrap;}
.ab-live{background:rgba(16,185,129,.13);color:#10b981;border:1px solid rgba(16,185,129,.28);display:flex;align-items:center;gap:4px;}
.ab-live::before{content:'';width:6px;height:6px;border-radius:50%;background:#10b981;animation:bella-pulse 1.6s ease-in-out infinite;}
.ab-std{background:rgba(100,116,139,.12);color:#64748b;border:1px solid rgba(100,116,139,.2);}
.ab-cnt{background:rgba(99,102,241,.1);color:#818cf8;border:1px solid rgba(99,102,241,.18);}
.ab-scen{background:rgba(52,211,153,.1);color:#34d399;border:1px solid rgba(52,211,153,.2);}
.bella-hdr-stats{display:flex;flex-direction:column;align-items:flex-end;gap:4px;min-width:140px;}
.bella-hdr-stat{font-size:.66rem;color:#334155;display:flex;align-items:center;gap:5px;white-space:nowrap;}
.bella-hdr-val{color:#94a3b8;font-weight:600;}

/* ── Context pill bar ─────────────────────────────────── */
.bella-ctx{
  background:rgba(8,13,26,.9);border:1px solid rgba(30,41,59,.8);border-top:none;
  padding:11px 18px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;
}
.bella-ctx-lbl{font-size:.58rem;font-weight:800;color:#253040;text-transform:uppercase;letter-spacing:.12em;margin-right:3px;flex-shrink:0;}
.ctx-pill{
  font-size:.64rem;font-weight:600;border-radius:20px;padding:3px 10px;white-space:nowrap;
  animation:bella-ctxpop .28s ease both;cursor:default;
}
.ctx-on{background:rgba(16,185,129,.09);color:#34d399;border:1px solid rgba(16,185,129,.2);}
.ctx-warn{background:rgba(245,158,11,.09);color:#fbbf24;border:1px solid rgba(245,158,11,.2);}
.ctx-off{background:rgba(30,41,59,.4);color:#334155;border:1px solid rgba(30,41,59,.6);}

/* ── Scrollable message box ───────────────────────────── */
.bella-scroll-box{
  height:520px;overflow-y:auto;overflow-x:hidden;
  background:linear-gradient(180deg,#070c1a 0%,#09101f 100%);
  border:1px solid rgba(30,41,59,.8);border-top:none;
  padding:22px 20px 14px;scroll-behavior:smooth;
  position:relative;
}
.bella-scroll-box::-webkit-scrollbar{width:5px;}
.bella-scroll-box::-webkit-scrollbar-track{background:transparent;}
.bella-scroll-box::-webkit-scrollbar-thumb{background:rgba(99,102,241,.28);border-radius:4px;}
.bella-scroll-box::-webkit-scrollbar-thumb:hover{background:rgba(99,102,241,.52);}

/* ── Message rows ─────────────────────────────────────── */
.bella-row{display:flex;margin-bottom:22px;}
.bella-row.user{justify-content:flex-end;animation:bella-slider .32s ease both;}
.bella-row.ai  {justify-content:flex-start;animation:bella-slidel .32s ease both;}

.bella-av-sm{
  width:36px;height:36px;flex-shrink:0;
  background:linear-gradient(135deg,#4338ca,#7c3aed);
  border-radius:12px;display:flex;align-items:center;justify-content:center;
  font-size:.95rem;margin-right:10px;margin-top:2px;
  box-shadow:0 4px 14px rgba(99,102,241,.32);
  animation:bella-glow 4s ease-in-out infinite;
}

.bella-bub{max-width:80%;padding:15px 19px;line-height:1.68;font-size:.875rem;position:relative;}
.bella-bub.user{
  background:linear-gradient(135deg,#1d4ed8 0%,#4f46e5 55%,#7c3aed 100%);
  color:#e0e7ff;border-radius:20px 20px 5px 20px;font-weight:500;
  box-shadow:0 8px 26px rgba(79,70,229,.38),0 2px 8px rgba(79,70,229,.22);
}
.bella-bub.ai{
  background:linear-gradient(155deg,rgba(13,20,40,.99),rgba(22,32,55,.93));
  color:#dde4f0;border-radius:20px 20px 20px 5px;
  border:1px solid rgba(99,102,241,.16);
  box-shadow:0 8px 34px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.03);
}
.bella-bub.ai::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(99,102,241,.42),transparent);
  border-radius:20px 20px 0 0;
}
.bella-meta{font-size:.58rem;color:#253040;margin-top:7px;display:flex;align-items:center;gap:7px;}
.bella-row.user .bella-meta{justify-content:flex-end;}

/* ── Follow-up bar (below scrollbox, visually flush) ─── */
.bella-fu-bar{
  background:linear-gradient(180deg,#080f1e 0%,#09101f 100%);
  border:1px solid rgba(30,41,59,.8);border-top:1px solid rgba(99,102,241,.12);
  padding:9px 16px 11px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
}
.bella-fu-lbl{font-size:.58rem;font-weight:800;color:#4338ca;text-transform:uppercase;letter-spacing:.1em;white-space:nowrap;flex-shrink:0;}

/* ── Welcome screen ───────────────────────────────────── */
.bella-welcome{
  text-align:center;padding:40px 20px 28px;
  animation:bella-fadein .5s ease both;
}
.bella-wlc-av{
  width:76px;height:76px;
  background:linear-gradient(135deg,#4338ca 0%,#7c3aed 55%,#a855f7 100%);
  border-radius:24px;margin:0 auto 18px;
  display:flex;align-items:center;justify-content:center;font-size:2.1rem;
  box-shadow:0 0 44px rgba(99,102,241,.45);
  animation:bella-glow 3.5s ease-in-out infinite,bella-float 5s ease-in-out infinite;
}
.bella-wlc-name{
  font-size:1.4rem;font-weight:800;margin-bottom:7px;
  background:linear-gradient(135deg,#e0e7ff,#c4b5fd,#a78bfa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.bella-wlc-sub{font-size:.82rem;color:#3d4d60;max-width:500px;margin:0 auto 22px;line-height:1.65;}
.bella-wlc-caps{display:flex;justify-content:center;gap:7px;flex-wrap:wrap;}
.bella-cap{
  background:rgba(99,102,241,.07);border:1px solid rgba(99,102,241,.18);
  border-radius:20px;padding:5px 14px;font-size:.68rem;color:#6366f1;font-weight:600;
  animation:bella-ctxpop .3s ease both;
}

/* ── Typing indicator ────────────────────────────────── */
.bella-typing{
  display:inline-flex;align-items:center;gap:9px;
  padding:11px 16px;background:rgba(13,20,40,.85);
  border:1px solid rgba(99,102,241,.12);border-radius:16px 16px 16px 4px;
  animation:bella-fadein .25s ease both;
}
.bella-td{display:flex;gap:4px;}
.bella-dot{width:7px;height:7px;border-radius:50%;background:#5b5fdb;animation:bella-typing 1.3s ease-in-out infinite;}
.bella-dot:nth-child(2){animation-delay:.22s;}
.bella-dot:nth-child(3){animation-delay:.44s;}
.bella-ttxt{font-size:.7rem;color:#4338ca;font-weight:600;}

/* ── Chip area ───────────────────────────────────────── */
.bella-chiprow{display:flex;gap:6px;flex-wrap:wrap;padding:2px 2px 8px;}
.bella-chip{
  background:rgba(13,20,38,.75);border:1px solid rgba(30,41,59,.9);
  border-radius:20px;padding:6px 14px;font-size:.71rem;color:#475569;font-weight:500;
  transition:all .14s ease;cursor:pointer;white-space:nowrap;
}
.bella-chip:hover{background:rgba(99,102,241,.09);color:#a5b4fc;border-color:rgba(99,102,241,.28);transform:translateY(-1px);}

/* ── Input bar ───────────────────────────────────────── */
.bella-input-bar{
  background:rgba(8,13,26,.96);border:1px solid rgba(30,41,59,.8);
  border-top:1px solid rgba(99,102,241,.13);
  border-radius:0 0 20px 20px;padding:12px 16px 16px;
}
.bella-footer{display:flex;justify-content:space-between;align-items:center;padding-top:6px;}
.bella-footer-l{font-size:.62rem;color:#1a2535;}
.bella-footer-r{display:flex;gap:7px;}
.bella-fbtn{
  background:rgba(20,30,52,.7);border:1px solid rgba(30,41,59,.8);border-radius:8px;
  padding:4px 12px;font-size:.65rem;color:#334155;font-weight:600;cursor:pointer;
  transition:all .12s ease;
}
.bella-fbtn:hover{color:#64748b;border-color:#334155;}

/* ── Hide auto-scroll iframe injected by components.html ── */
iframe[title="st.components.v1.html"]{display:none!important;height:0!important;}
</style>
"""

_BELLA_CHIPS: dict = {
    "📐 Scope": [
        "What's in scope for this project?",
        "What's explicitly excluded?",
        "Which requirements are most complex?",
        "What assumptions were made?",
    ],
    "⏱ Timeline": [
        "Which phase takes the longest and why?",
        "How is the total duration calculated?",
        "What's the critical path?",
        "How can we compress the timeline by 20%?",
    ],
    "💰 Cost": [
        "Break down the total cost for me",
        "What's driving the infrastructure cost?",
        "Where can we cut cost without losing scope?",
        "How does this compare to industry norms?",
    ],
    "⚠️ Risk": [
        "What's the single biggest risk?",
        "Which risks have the highest severity?",
        "How do we reduce the overall risk score?",
        "Are there any hidden integration risks?",
    ],
    "🎯 Strategy": [
        "What should we highlight in the exec summary?",
        "What questions will the client ask?",
        "What's the recommended team composition?",
        "How do we position this vs competitors?",
    ],
}


def _build_bella_prompt(r: dict, se: dict, te: dict, ce: dict, ri: dict) -> str:
    ar  = safe_dict(r.get("architecture"))
    sc  = safe_dict(r.get("scope"))
    pro = safe_dict(r.get("proposal", {}))

    _reqs = [
        {"id": i+1, "title": safe_str(q.get("title","")),
         "type": safe_str(q.get("type","")), "complexity": safe_str(q.get("complexity","")),
         "description": safe_str(q.get("description",""))[:240]}
        for i, q in enumerate(safe_list(se.get("requirements",[])))
    ]
    _phases = [
        {"name": safe_str(p.get("name","")), "domain": safe_str(p.get("domain","")),
         "hours": p.get("hours",0), "weeks": p.get("duration_weeks",0),
         "tasks": [{"title": safe_str(t.get("title","")), "role": safe_str(t.get("role","")),
                    "hours": t.get("hours",0)} for t in safe_list(p.get("tasks",[]))[:10]]}
        for p in safe_list(te.get("phases",[]))
    ]
    _risks = [
        {"title": safe_str(x.get("title","")), "severity": safe_str(x.get("severity","")),
         "probability": safe_str(x.get("probability","")), "impact": safe_str(x.get("impact","")),
         "mitigation": safe_str(x.get("mitigation","")), "category": safe_str(x.get("category",""))}
        for x in safe_list(ri.get("risks",[]))[:12]
    ]
    _arch = [
        {"name": safe_str(c.get("name","")), "service": safe_str(c.get("azure_service","")),
         "purpose": safe_str(c.get("purpose",""))}
        for c in safe_list(ar.get("components",[]))[:15]
    ]
    _all_cloud = []
    for _ck in ("azure_costs","aws_costs","gcp_costs","cloud_costs"):
        _all_cloud.extend(safe_list(ce.get(_ck,[])))
    _scenarios = [
        {"name": s.get("name",""),
         "total_cost": s.get("kpi",{}).get("total_cost"),
         "duration_weeks": s.get("kpi",{}).get("duration_weeks"),
         "risk_level": s.get("kpi",{}).get("risk_level"),
         "scope_pct": s.get("params",{}).get("feature_scope"),
         "seniority": s.get("params",{}).get("seniority"),
         "contract_type": s.get("params",{}).get("contract_type")}
        for s in st.session_state.get("scenarios",[])[:3]
    ]
    _exec = safe_str(pro.get("executive_summary",""))[:1500] if pro else ""
    _doc  = str(st.session_state.get("_extracted_text",""))[:40000].strip()

    ctx = json.dumps({
        "project_type": se.get("project_type",""), "client_name": se.get("client_name",""),
        "complexity_score": se.get("complexity_score",""),
        "project_domains": safe_list(se.get("project_domains",[]))[:8],
        "technology_stack": safe_list(se.get("technology_stack",[]))[:18],
        "mandated_technologies": safe_list(se.get("mandated_technologies",[]))[:10],
        "source_systems": safe_list(se.get("source_systems",[]))[:10],
        "business_objectives": safe_list(se.get("business_objectives",[]))[:8],
        "requirements": _reqs,
        "in_scope":  [safe_str(x) for x in safe_list(sc.get("in_scope",[]))[:25]],
        "out_of_scope": [safe_str(x) for x in safe_list(sc.get("out_of_scope",[]))[:15]],
        "assumptions": [safe_str(x) for x in safe_list(sc.get("assumptions",[]))[:10]],
        "total_hours": te.get("total_hours",""), "duration_weeks": te.get("duration_weeks",""),
        "three_point": safe_dict(te.get("three_point")),
        "milestones": [safe_str(m) for m in safe_list(te.get("milestones",[]))[:8]],
        "phases": _phases,
        "team_roles": [{"role": safe_str(ro.get("role","")), "hours": ro.get("hours",0)}
                       for ro in safe_list(te.get("roles",[]))[:15]],
        "total_monthly_cost": ce.get("total_monthly_cost",""),
        "total_annual_cost": ce.get("total_annual_cost",""),
        "cloud_provider": ce.get("cloud_provider","azure"),
        "cloud_services": [{"service": s.get("service",""), "monthly_cost": s.get("monthly_cost",0)}
                           for s in _all_cloud[:12]],
        "third_party_costs": [{"service": s.get("service",""), "monthly_cost": s.get("monthly_cost",0)}
                              for s in safe_list(ce.get("third_party_costs",[]))[:8]],
        "risk_level": ri.get("overall_level",""), "risk_score": ri.get("overall_score",""),
        "risks": _risks,
        "architecture_pattern": ar.get("pattern",""),
        "architecture_components": _arch,
        "availability_target": ar.get("availability",""),
        "scenarios_modelled": _scenarios,
    }, indent=2)

    prop_section = f"\n\n─── PROPOSAL EXECUTIVE SUMMARY ───\n{_exec}" if _exec else ""
    doc_section  = f"\n\n─── SOURCE DOCUMENT (uploaded scope) ───\n{_doc}" if _doc else ""

    return (
        "You are BELLA — ECI's Presales Intelligence Advisor. You combine the expertise of a senior "
        "architect, commercial strategist, and delivery consultant. You know this proposal inside-out.\n\n"
        "PERSONALITY:\n"
        "• Sharp, warm, confident — like a brilliant senior colleague, not a chatbot\n"
        "• Lead with the answer, then explain — never bury the key number\n"
        "• Use **bold** for key figures, bullet points for lists, `code` for tech terms\n"
        "• When asked WHERE something came from, trace it to the exact requirement, phase, or document line\n"
        "• Cite ACTUAL numbers — never round or approximate unless you must\n"
        "• End detailed answers with 2–3 follow-ups prefixed exactly: 💡 FOLLOW-UP:\n"
        "  (one per line, e.g. '💡 FOLLOW-UP:\\n- Which risk has the highest probability?\\n- ...')\n"
        "• Never say 'Great question!', never pad, never hedge unnecessarily\n"
        "• If data is missing, say 'Re-run the pipeline for a fresher answer on that'\n\n"
        "FULL PROPOSAL DATA:\n" + ctx
        + prop_section + doc_section
    )


def _ctx_pills(se: dict, te: dict, ce: dict, ri: dict, ar: dict) -> str:
    n_req  = len(safe_list(se.get("requirements",[])))
    th     = safe_int(te.get("total_hours",0))
    tw     = safe_str(te.get("duration_weeks",""))
    tc     = safe_int(ce.get("total_monthly_cost",0))
    rl     = safe_str(ri.get("overall_level",""))
    rs     = safe_int(ri.get("overall_score",0))
    na     = len(safe_list(ar.get("components",[])))
    nr     = len(safe_list(ri.get("risks",[])))
    ns     = len(st.session_state.get("scenarios",[]))
    has_doc= bool(st.session_state.get("_extracted_text"))
    rw_cls = "ctx-warn" if rl in ("High","Critical") else "ctx-on"

    def p(icon, label, cls="ctx-on", i=0):
        return f'<span class="ctx-pill {cls}" style="animation-delay:{i*.04}s" title="{label}">{icon} {label}</span>'

    pills = ""
    i = 0
    if n_req:   pills += p("📋", f"{n_req} Requirements", i=i); i+=1
    if th:      pills += p("⏱", f"{th:,}h · {tw}wks", i=i); i+=1
    if tc:      pills += p("💰", f"${tc:,}/mo", i=i); i+=1
    if rl:      pills += p("⚠️", f"Risk {rs}/10 · {rl}", rw_cls, i); i+=1
    if na:      pills += p("🏗", f"{na} Components", i=i); i+=1
    if nr:      pills += p("🛡", f"{nr} Risks", i=i); i+=1
    if ns:      pills += p("🔀", f"{ns} Scenario{'s' if ns!=1 else ''}", "ctx-on", i); i+=1
    if has_doc: pills += p("📄", "Source Doc", i=i); i+=1
    if not pills: pills = '<span class="ctx-pill ctx-off">No data yet — run the pipeline first</span>'

    return f'<div class="bella-ctx"><span class="bella-ctx-lbl">BELLA sees:</span>{pills}</div>'


def _msg_html(role: str, content: str, ts: str = "") -> str:
    import html as _html, re as _re

    if role == "user":
        safe = _html.escape(content)
        return (
            f'<div class="bella-row user">'
            f'<div class="bella-bub user">{safe}'
            f'<div class="bella-meta">{ts}</div>'
            f'</div></div>'
        )

    # Strip follow-up block from bubble — shown as interactive buttons below the chatbox
    main = content.split("💡 FOLLOW-UP:", 1)[0].strip() if "💡 FOLLOW-UP:" in content else content

    safe = _html.escape(main)
    safe = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe)
    safe = _re.sub(r'`([^`]+)`', r'<code style="background:rgba(99,102,241,.13);padding:1px 5px;border-radius:4px;font-size:.82em">\1</code>', safe)
    safe = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', safe)
    safe = safe.replace("\n\n", "</p><p style='margin:8px 0 0'>").replace("\n", "<br>")
    safe = f"<p style='margin:0'>{safe}</p>"

    return (
        f'<div class="bella-row ai">'
        f'<div class="bella-av-sm">✦</div>'
        f'<div class="bella-bub ai">{safe}'
        f'<div class="bella-meta">{ts} · BELLA</div>'
        f'</div></div>'
    )


@st.fragment
def _render_proposal_chat(r: dict, se: dict, te: dict, ce: dict, ri: dict):
    """BELLA — ECI Presales Intelligence Advisor. Fixed-height chatbox, streaming inside."""
    import streamlit.components.v1 as _comp
    from datetime import datetime as _dt
    ar = safe_dict(r.get("architecture"))

    _chat_provider = get_model_for_feature("chat")
    _ant  = AnthropicAI.opus_from_session() if _chat_provider == "claude_opus" else AnthropicAI.from_session()
    _live = _ant.is_live and hasattr(_ant, "stream_chat") and not st.session_state.get("_claude_blocked")

    # Cache the (expensive) system prompt; invalidate when proposal data changes
    _fp = f"{len(str(se))}_{len(str(te))}_{len(str(ce))}_{len(str(ri))}"
    if st.session_state.get("_bella_sys_fp") != _fp:
        st.session_state["_bella_sys"]    = _build_bella_prompt(r, se, te, ce, ri)
        st.session_state["_bella_sys_fp"] = _fp
    _sys: str = st.session_state["_bella_sys"]

    msgs: list = st.session_state.setdefault("chat_messages", [])
    _n_ex = len(msgs) // 2

    # ── CSS ───────────────────────────────────────────────────────────────
    st.markdown(_BELLA_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────
    _pt  = safe_str(se.get("project_type","—"))[:30]
    _tw  = safe_str(te.get("duration_weeks","—"))
    _rl  = safe_str(ri.get("overall_level","—"))
    _ns  = len(st.session_state.get("scenarios",[]))
    _dc  = sum([bool(safe_list(se.get("requirements"))), bool(safe_int(te.get("total_hours"))),
                bool(safe_int(ce.get("total_monthly_cost"))), bool(ri.get("overall_level")),
                bool(safe_list(ar.get("components"))), bool(st.session_state.get("_extracted_text"))])

    _opus_badge = '<span class="ab ab-scen">Opus 4.8</span>' if _chat_provider == "claude_opus" else ""
    _sbadge = '<span class="ab ab-live">LIVE STREAM</span>' if _live else '<span class="ab ab-std">AI CHAT</span>'
    _scen_b = f'<span class="ab ab-scen">🔀 {_ns} scenarios</span>' if _ns else ""
    _ex_b   = f'<span class="ab ab-cnt">💬 {_n_ex} exchange{"s" if _n_ex!=1 else ""}</span>' if _n_ex else ""

    st.markdown(
        f'<div class="bella-hdr">'
        f'<div class="bella-av">✦</div>'
        f'<div class="bella-idn">'
        f'<div class="bella-name">BELLA</div>'
        f'<div class="bella-title">Presales Intelligence Advisor · ECI AI</div>'
        f'<div class="bella-badges">{_sbadge}{_opus_badge}<span class="ab ab-cnt">⚡ {_dc} sources</span>{_scen_b}{_ex_b}</div>'
        f'</div>'
        f'<div class="bella-hdr-stats">'
        f'<div class="bella-hdr-stat">Project: <span class="bella-hdr-val">{_pt}</span></div>'
        + (f'<div class="bella-hdr-stat">Duration: <span class="bella-hdr-val">{_tw} wks</span></div>' if te.get("duration_weeks") else "")
        + (f'<div class="bella-hdr-stat">Risk: <span class="bella-hdr-val">{_rl}</span></div>' if ri.get("overall_level") else "")
        + f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Context pills ─────────────────────────────────────────────────────
    st.markdown(_ctx_pills(se, te, ce, ri, ar), unsafe_allow_html=True)

    # ── Welcome HTML (shown when no messages yet) ─────────────────────────
    _WELCOME = (
        '<div class="bella-welcome">'
        '<div class="bella-wlc-av">✦</div>'
        '<div class="bella-wlc-name">I\'m BELLA</div>'
        '<div class="bella-wlc-sub">Your senior consultant for this proposal. Ask me anything — '
        'I\'ve analysed every requirement, phase, cost, risk, and architecture decision. '
        'I\'ll give you straight answers with the exact numbers.</div>'
        '<div class="bella-wlc-caps">'
        + "".join(f'<span class="bella-cap">{c}</span>' for c in
                  ["📋 Scope & Requirements", "⏱ Hours & Phases", "💰 Cost Breakdown",
                   "⚠️ Risks & Mitigations", "🏗 Architecture", "🔀 Scenarios & What-ifs"])
        + '</div></div>'
    )

    _TYPING = (
        '<div class="bella-row ai">'
        '<div class="bella-av-sm" style="animation:bella-glow .8s ease-in-out infinite">✦</div>'
        '<div class="bella-typing">'
        '<div class="bella-td"><div class="bella-dot"></div>'
        '<div class="bella-dot"></div><div class="bella-dot"></div></div>'
        '<span class="bella-ttxt">BELLA is thinking…</span>'
        '</div></div>'
    )

    def _box_inner(extra: str = "") -> str:
        if not msgs and not extra:
            return _WELCOME
        parts = [_msg_html(m["role"], m["content"], m.get("ts", "")) for m in msgs]
        if extra:
            parts.append(extra)
        return "".join(parts)

    def _set_box(extra: str = "") -> None:
        _box_slot.markdown(
            f'<div class="bella-scroll-box">{_box_inner(extra)}</div>',
            unsafe_allow_html=True,
        )

    # ── Render scrollable box (single st.empty slot — updated during stream) ──
    _box_slot = st.empty()
    _set_box()

    # Auto-scroll to latest message after each full fragment rerun
    if msgs:
        _comp.html(
            '<script>'
            'try{var b=window.parent.document.querySelector(".bella-scroll-box");'
            'if(b)b.scrollTop=b.scrollHeight;}catch(e){}'
            '</script>',
            height=0,
        )

    # ── Follow-up chips — flush bar below scrollbox (single, interactive) ──
    _fu_items: list[str] = []
    if msgs and msgs[-1]["role"] == "assistant" and "💡 FOLLOW-UP:" in msgs[-1]["content"]:
        _fu_raw = msgs[-1]["content"].split("💡 FOLLOW-UP:", 1)[1].splitlines()
        _fu_items = [ln.strip().lstrip("-•").strip() for ln in _fu_raw
                     if ln.strip().lstrip("-•").strip()][:3]

    if _fu_items:
        st.markdown(
            '<div class="bella-fu-bar">'
            '<span class="bella-fu-lbl">💡 Ask next</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        _fu_cols = st.columns(len(_fu_items))
        for _fi, (_fc, _fq) in enumerate(zip(_fu_cols, _fu_items)):
            with _fc:
                if st.button(_fq, key=f"bellafu_{_fi}", width="stretch"):
                    st.session_state["bella_pending"] = _fq
                    st.rerun(scope="fragment")

    # ── Category selector + suggestion chips ─────────────────────────────
    if "bella_cat" not in st.session_state:
        st.session_state.bella_cat = list(_BELLA_CHIPS.keys())[0]

    cat_cols = st.columns(len(_BELLA_CHIPS))
    for ci, cat in enumerate(_BELLA_CHIPS.keys()):
        with cat_cols[ci]:
            if st.button(cat, key=f"bellat_{ci}", width="stretch",
                         type="primary" if st.session_state.bella_cat == cat else "secondary"):
                st.session_state.bella_cat = cat
                st.rerun(scope="fragment")

    active_chips = _BELLA_CHIPS[st.session_state.bella_cat]
    cc = st.columns(2)
    for ci, chip in enumerate(active_chips):
        with cc[ci % 2]:
            if st.button(chip, key=f"bellac_{ci}", width="stretch"):
                st.session_state["bella_pending"] = chip
                st.rerun(scope="fragment")

    # ── Pending chip injection ────────────────────────────────────────────
    _pending = st.session_state.pop("bella_pending", None)

    # ── Chat input ────────────────────────────────────────────────────────
    _user_input = st.chat_input("Ask BELLA anything about this proposal…", key="bella_input") or _pending

    # ── Process message ───────────────────────────────────────────────────
    if _user_input:
        _now = _dt.now().strftime("%H:%M")
        msgs.append({"role": "user", "content": _user_input, "ts": _now})
        _log_act("bella_chat", f"BELLA: {_user_input[:120]}", "Chat")
        _api_msgs = [{"role": m["role"], "content": m["content"]} for m in msgs]
        _answer = ""

        # INSTANT feedback — show user message + typing dots before any API call
        _set_box(_TYPING)

        # ── Live streaming — updates the box on every token ───────────────
        if _live:
            _chunks: list[str] = []
            try:
                for _chunk in _ant.stream_chat(_sys, _api_msgs, max_tokens=2048):
                    _chunks.append(_chunk)
                    _set_box(_msg_html("assistant", "".join(_chunks) + " ▋"))
                _answer = "".join(_chunks)
                _set_box(_msg_html("assistant", _answer))
            except Exception as _se:
                st.warning(f"Streaming error: {str(_se)[:120]} — retrying…")
                _live = False

        # ── Blocking fallback (typing dots already showing) ───────────────
        if not _live and not _answer:
            _hist = "\n".join(
                ("User" if m["role"] == "user" else "BELLA") + ": " + m["content"]
                for m in msgs[:-1]
            )
            _last_msg = msgs[-1]["content"] if msgs else ""
            _full = (f"Conversation history:\n{_hist}\n\n" if _hist else "") + f"User: {_last_msg}"
            _answer = _ant._call(_sys, _full, max_tokens=2048) or ""

        if _answer:
            msgs.append({"role": "assistant", "content": _answer,
                         "ts": _dt.now().strftime("%H:%M")})

        st.rerun(scope="fragment")

    # ── Footer ────────────────────────────────────────────────────────────
    if msgs:
        fc1, fc2, fc3 = st.columns([5, 1.5, 1.8])
        with fc2:
            if st.button("🗑 Clear", key="bella_clr", width="stretch"):
                st.session_state["chat_messages"] = []
                st.session_state.pop("bella_cat", None)
                st.rerun(scope="fragment")
        with fc3:
            _lines = [f"[{m.get('ts','')}] {'You' if m['role']=='user' else 'BELLA'}:\n{m['content']}\n"
                      for m in msgs]
            st.download_button("💾 Export", data="\n".join(_lines).encode(),
                               file_name="bella_chat.txt", mime="text/plain",
                               width="stretch", key="bella_exp")


def _empty_chat():
    """Fallback empty state (kept for compatibility)."""
    st.markdown(
        '<div style="text-align:center;padding:60px 20px">'
        '<div style="font-size:3rem;margin-bottom:12px">✦</div>'
        '<div style="font-size:1rem;font-weight:700;color:#334155">BELLA is ready</div>'
        '<div style="font-size:.8rem;color:#253040;margin-top:6px">Run the pipeline to unlock the full experience.</div>'
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
    import time
    words = text.split()
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.022)


# ═══════════════════════════════════════════════════════════════════════
#  DELIVERY INTELLIGENCE SUMMARY  (Time Estimate tab — top card)
# ═══════════════════════════════════════════════════════════════════════

_DOMAIN_META = {
    "Data Engineering": {"color": "#00d4aa", "icon": "🗄️",  "role": "Data Engineer"},
    "AI / ML":          {"color": "#7b61ff", "icon": "🤖",  "role": "AI Engineer"},
    "DevOps":           {"color": "#14A0B9", "icon": "☁️",  "role": "DevOps Engineer"},
    "QA":               {"color": "#ffd166", "icon": "🧪",  "role": "QA Engineer"},
    "Discovery":        {"color": "#06d6a0", "icon": "🔍",  "role": "All Team"},
    "Documentation":    {"color": "#f4845f", "icon": "📄",  "role": "Tech Writer"},
    "PM":               {"color": "#e9c46a", "icon": "📋",  "role": "Project Manager"},
    "Custom App":       {"color": "#f87171", "icon": "💻",  "role": "Developer"},
    "SharePoint":       {"color": "#0078d4", "icon": "📑",  "role": "SharePoint Dev"},
    "Integration":      {"color": "#94a3b8", "icon": "🔗",  "role": "Integration Dev"},
    "Feature Development": {"color": "#06b6d4", "icon": "⚙️", "role": "Developer"},
}
_DOMAIN_META_DEFAULT = {"color": "#94a3b8", "icon": "📦", "role": "Engineer"}


def _infer_domain(name: str) -> str:
    """Infer domain from stream name when the domain field is empty/missing."""
    n = name.lower()
    if any(k in n for k in ("data eng", "dataeng", "lakehouse", "etl", "pipeline", "fabric",
                             "databricks", "synapse", "warehouse", "data lake", "medallion")):
        return "Data Engineering"
    if any(k in n for k in ("ai/ml", "ai & ml", "ai/", "/ml", "machine learn", "rag",
                             "llm", "nlp", "openai", "cognitive", "langchain", "copilot")):
        return "AI / ML"
    if any(k in n for k in ("devops", "dev ops", "& platform", "platform", "deploy",
                             "infrastructure", "ci/cd", "kubernetes", "aks", "docker",
                             "terraform", "cloud infra")):
        return "DevOps"
    if any(k in n for k in ("qa", "test", "quality assur", "uat", "validation")):
        return "QA"
    if any(k in n for k in ("discovery", "design", "architect", "kickoff", "workshop",
                             "requirement", "inception")):
        return "Discovery"
    if any(k in n for k in ("document", "tech writ", "knowledge transfer", "training material")):
        return "Documentation"
    if any(k in n for k in ("project manag", "program manag", "scrum master", "agile coach",
                             "governance")):
        return "PM"
    if any(k in n for k in ("sharepoint", "m365", "teams", "power app", "office 365",
                             "spo", "viva", "power automate", "power bi")):
        return "SharePoint"
    if any(k in n for k in ("integrat", "connector", "webhook", "middleware",
                             "mulesoft", "interface layer")):
        return "Integration"
    if any(k in n for k in ("custom app", "application", "react", "angular", "frontend",
                             "backend", ".net", "blazor", "mvc", "web app", "portal")):
        return "Custom App"
    if any(k in n for k in ("feature dev", "implementation", "sprint", "iteration")):
        return "Feature Development"
    return ""


def _render_delivery_summary(te: dict) -> None:
    """Render the Delivery Intelligence Summary card at the top of the Time tab."""
    phases = safe_list(te.get("phases", []))
    if not phases:
        return

    _ph_list = [safe_dict(p) for p in phases if isinstance(p, dict)]
    total_h = sum(safe_int(p.get("hours", 0)) for p in _ph_list) or safe_int(te.get("total_hours", 0))
    if not total_h:
        return

    # Always recompute from phases — AI-generated duration_weeks is often stale/wrong
    _OVERHEAD_D = {"Discovery", "PM", "Documentation", "QA"}
    _par_ph   = [p for p in _ph_list if safe_str(p.get("domain","")) not in _OVERHEAD_D and safe_int(p.get("hours",0)) > 0]
    def _pw(p):  # phase weeks: prefer stored, fallback to hours/40
        return float(p.get("duration_weeks") or 0) or round(safe_int(p.get("hours",0)) / 40, 1)
    _disc_w_d = next((_pw(p) for p in _ph_list if p.get("domain") == "Discovery"), 0.0)
    _doc_w_d  = next((_pw(p) for p in _ph_list if p.get("domain") == "Documentation"), 0.0)
    _crit_w_d = max((_pw(p) for p in _par_ph), default=0.0) or round(total_h / 40, 1)
    total_weeks = max(1.0, round(_disc_w_d + _crit_w_d + _doc_w_d + 0.5))
    dur_str = f"{int(total_weeks)} weeks"

    # Build stream list — infer domain when field is empty
    streams = []
    for pd in _ph_list:
        dom = safe_str(pd.get("domain", ""))
        if not dom:
            dom = _infer_domain(safe_str(pd.get("name", "")))
        meta = _DOMAIN_META.get(dom, _DOMAIN_META_DEFAULT)
        h    = safe_int(pd.get("hours", 0))
        w    = float(pd.get("duration_weeks") or 0)
        if w <= 0 and h > 0:
            w = round(h / 40, 1)
        streams.append({
            "name":   safe_str(pd.get("name", dom or "Phase")),
            "domain": dom,
            "hours":  h,
            "weeks":  w,
            "color":  meta["color"],
            "icon":   meta["icon"],
            "role":   meta["role"],
        })

    # Critical path: longest parallel stream (overhead streams excluded)
    _overhead = {"Discovery", "PM", "Documentation", "QA"}
    par_streams = [s for s in streams if s["domain"] not in _overhead and s["hours"] > 0]
    critical    = max(par_streams, key=lambda s: s["weeks"]) if par_streams else (
        max(streams, key=lambda s: s["hours"]) if streams else None)
    disc_weeks  = next((s["weeks"] for s in streams if s["domain"] == "Discovery"), 0.0)

    # Sequential vs parallel saving
    seq_weeks   = sum(s["weeks"] for s in par_streams) + disc_weeks
    time_saved  = max(0.0, round(seq_weeks - total_weeks, 1))
    n_parallel  = len(par_streams)

    # ── KPI header ──────────────────────────────────────────────────────
    kpi_html = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:22px">
      <div style="background:rgba(0,212,170,.07);border:1px solid rgba(0,212,170,.18);
          border-top:3px solid #00d4aa;border-radius:10px;padding:14px 10px;text-align:center">
        <div style="font-size:1.55rem;font-weight:800;color:#00d4aa;line-height:1.1">{total_h}h</div>
        <div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:5px">Total Effort</div>
      </div>
      <div style="background:rgba(20,160,185,.07);border:1px solid rgba(20,160,185,.18);
          border-top:3px solid #14A0B9;border-radius:10px;padding:14px 10px;text-align:center">
        <div style="font-size:1.55rem;font-weight:800;color:#14A0B9;line-height:1.1">{dur_str}</div>
        <div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:5px">Delivery Timeline</div>
      </div>
      <div style="background:rgba(123,97,255,.07);border:1px solid rgba(123,97,255,.18);
          border-top:3px solid #7b61ff;border-radius:10px;padding:14px 10px;text-align:center">
        <div style="font-size:1.55rem;font-weight:800;color:#7b61ff;line-height:1.1">{n_parallel}</div>
        <div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:5px">Parallel Streams</div>
      </div>
      <div style="background:rgba(6,214,160,.07);border:1px solid rgba(6,214,160,.18);
          border-top:3px solid #06d6a0;border-radius:10px;padding:14px 10px;text-align:center">
        <div style="font-size:1.55rem;font-weight:800;color:#06d6a0;line-height:1.1">{time_saved}w</div>
        <div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:5px">Saved vs Sequential</div>
      </div>
    </div>"""

    # ── Effort bars ──────────────────────────────────────────────────────
    bars_html = ""
    _crit_name = critical["name"] if critical else ""
    for s in sorted(streams, key=lambda x: -x["hours"]):
        if not s["hours"]:
            continue
        pct = round(s["hours"] / total_h * 100)
        # Use stream name for identity (domain may be "" when inferred; name is always unique)
        is_crit  = bool(critical and s["name"] == _crit_name)
        badge    = (
            '<span style="background:rgba(239,68,68,.15);color:#fca5a5;font-size:.58rem;'
            'padding:1px 7px;border-radius:8px;margin-left:7px;font-weight:700">CRITICAL PATH</span>'
            if is_crit else ""
        )
        bar_glow = f"box-shadow:0 0 8px {s['color']}55;" if is_crit else ""
        bars_html += f"""
        <div style="margin-bottom:9px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
            <span style="font-size:.76rem;color:#e2e8f0;font-weight:600">{s['icon']} {s['name']}{badge}</span>
            <span style="font-size:.72rem;color:{s['color']};font-weight:700;white-space:nowrap;margin-left:8px">{s['hours']}h &nbsp;·&nbsp; {s['weeks']:.1f}w</span>
          </div>
          <div style="background:rgba(255,255,255,.05);border-radius:5px;height:9px;overflow:visible">
            <div style="width:{pct}%;height:100%;border-radius:5px;{bar_glow}
              background:linear-gradient(90deg,{s['color']},{s['color']}77)"></div>
          </div>
        </div>"""

    # ── Gantt timeline ───────────────────────────────────────────────────
    # Compute dev_end: when parallel dev finishes (disc + critical_path)
    crit_weeks = critical["weeks"] if critical else 0.0
    dev_end    = disc_weeks + crit_weeks
    # Extend total_weeks if needed to fit all streams
    _max_w     = max(total_weeks, dev_end, 1.0)

    gantt_rows = ""
    for s in streams:
        if not s["hours"]:
            continue
        dom = s["domain"]
        w   = s["weeks"]
        if dom == "Discovery":
            start, end = 0.0, max(w, disc_weeks)
        elif dom == "PM":
            start, end = 0.0, _max_w
        elif dom == "QA":
            end   = _max_w
            start = max(dev_end, _max_w - w)
        elif dom == "Documentation":
            start = dev_end
            end   = min(_max_w, dev_end + w)
        else:
            # Parallel dev stream: starts after discovery window
            start = disc_weeks
            end   = min(_max_w, disc_weeks + w)

        l_pct   = round(start / _max_w * 100, 1)
        w_pct   = max(3.0, round((end - start) / _max_w * 100, 1))
        is_crit = bool(critical and s["name"] == _crit_name)
        ring    = f"outline:2px solid {s['color']};outline-offset:1px;" if is_crit else ""
        opacity = "1" if is_crit else "0.78"
        label   = s["name"][:26]

        gantt_rows += f"""
        <div style="display:grid;grid-template-columns:130px 1fr;gap:6px;align-items:center;margin-bottom:5px">
          <div style="font-size:.64rem;color:#94a3b8;text-align:right;padding-right:8px;
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{s['icon']} {s['role']}</div>
          <div style="background:rgba(255,255,255,.04);border-radius:4px;height:24px;position:relative">
            <div style="position:absolute;left:{l_pct}%;width:{w_pct}%;height:100%;border-radius:4px;
                background:linear-gradient(90deg,{s['color']}ee,{s['color']}88);
                opacity:{opacity};{ring}
                display:flex;align-items:center;padding:0 7px;overflow:hidden;white-space:nowrap;min-width:6px">
              <span style="font-size:.63rem;color:#fff;font-weight:600;text-shadow:0 1px 3px rgba(0,0,0,.6)">{label}</span>
            </div>
          </div>
        </div>"""

    # Week-marker ruler — always spans W0 → W{ceil(_max_w)}
    n_ticks  = min(9, int(_max_w) + 2)
    tick_gap = _max_w / max(n_ticks - 1, 1)
    ruler    = ""
    for i in range(n_ticks):
        wk = round(i * tick_gap, 1)
        lp = round(wk / _max_w * 100, 1)
        if lp > 100:
            break
        ruler += (f'<div style="position:absolute;left:{lp}%;font-size:.58rem;color:#475569;'
                  f'transform:translateX(-50%);white-space:nowrap">W{int(wk)}</div>')

    # Critical path callout
    crit_html = ""
    if critical:
        crit_html = f"""
        <div style="background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.2);
            border-left:3px solid #ef4444;border-radius:8px;padding:10px 14px;margin-top:18px">
          <span style="font-size:.78rem;color:#fca5a5">
            ⚡ <strong>Critical Path — {critical['name']}</strong> ({critical['weeks']:.1f} weeks) sets the project delivery date.
            Adding capacity to this stream is the fastest way to shorten the timeline.
          </span>
        </div>"""

    full_html = f"""
    <div style="background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);
        border-radius:14px;padding:22px 24px;margin-bottom:22px">
      <div style="font-size:.65rem;font-weight:700;color:#475569;text-transform:uppercase;
          letter-spacing:1.2px;margin-bottom:18px">⚡ Delivery Intelligence</div>
      {kpi_html}
      <div style="display:grid;grid-template-columns:1fr 1.2fr;gap:28px">
        <div>
          <div style="font-size:.62rem;color:#475569;text-transform:uppercase;
              letter-spacing:.7px;margin-bottom:12px">Effort by Work Stream</div>
          {bars_html}
        </div>
        <div>
          <div style="font-size:.62rem;color:#475569;text-transform:uppercase;
              letter-spacing:.7px;margin-bottom:8px">Team Delivery Plan — Parallel Execution</div>
          <div style="position:relative;margin-left:130px;height:16px;margin-bottom:3px">{ruler}</div>
          {gantt_rows}
        </div>
      </div>
      {crit_html}
    </div>"""

    # Strip line-level indentation so Markdown doesn't treat 4-space-indented
    # lines as code blocks
    full_html = "\n".join(line.strip() for line in full_html.splitlines() if line.strip())
    st.markdown(full_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  REQUIREMENTS COMPLETENESS CHECKER  (Agent 0)
# ═══════════════════════════════════════════════════════════════════════

_CONFIDENCE_META = {
    "High":   {"color": "#22c55e", "icon": "✅", "label": "High Confidence"},
    "Medium": {"color": "#ffd166", "icon": "⚠️", "label": "Medium Confidence"},
    "Low":    {"color": "#ff6b6b", "icon": "❌", "label": "Low Confidence"},
}


def _render_completeness_checker(files):
    """
    Shown between file upload and the main pipeline run.
    Step 1: Show "Check Completeness" + "Skip & Process" buttons.
    Step 2: After check → show structured question checklist.
    Step 3: User proceeds to full pipeline.
    """
    cc = st.session_state.get("_completeness_check")   # cached result
    dismissed = st.session_state.get("_completeness_dismissed", False)

    # ── Test mode toggle ───────────────────────────────────────────────
    _tm_col, _ = st.columns([3, 5])
    with _tm_col:
        st.session_state["time_test_mode"] = st.toggle(
            "⏱️ Time Estimate Test Mode (skip other agents)",
            value=st.session_state.get("time_test_mode", False),
            key="k_time_test_mode",
            help="Runs only Requirements + Time Estimate — results in ~10s. Disable to run the full pipeline.",
        )

    # ── Action bar (always visible while files are loaded) ─────────────
    b1, b2, b3 = st.columns([2, 2, 2])
    with b1:
        do_check = st.button(
            "🔍 Check Requirements Completeness",
            width="stretch",
            key="btn_completeness",
            help="Run Agent 0: analyse the scope document for gaps and generate a clarification checklist.",
        )
    with b2:
        do_run = st.button(
            "⚡ PROCESS & GENERATE ESTIMATES",
            width="stretch",
            type="primary",
            key="go",
            help="Skip completeness check and run the full 10-agent pipeline now.",
        )
    with b3:
        if cc:
            if st.button("🗑️ Clear Completeness Check", width="stretch", key="btn_clear_cc"):
                st.session_state.pop("_completeness_check", None)
                st.session_state.pop("_completeness_dismissed", None)
                st.session_state.pop("_completeness_acked", None)
                st.rerun()

    # ── Run completeness check ──────────────────────────────────────────
    if do_check:
        st.session_state["_az_err_shown"] = False   # reset per call
        with st.spinner("🔍 Agent analysing scope document for gaps…"):
            dp = DocProcessor()
            text = ""
            for f in files:
                text += dp.extract(f) + "\n\n"
            st.session_state["_completeness_text"] = text   # saved for Scope Validator
            st.session_state.pop("scope_validation_result", None)  # force fresh scope scan
            st.session_state.pop("scope_template_scan_result", None)  # force fresh template scan
            ai = _pick_ai_for("completeness")
            result = ai.check_requirements_completeness(text)
            st.session_state["_completeness_check"] = result
            st.session_state["_completeness_dismissed"] = False
            st.session_state["_completeness_acked"] = set()
        st.rerun()

    # ── Run main pipeline (skip or post-check) ──────────────────────────
    if do_run:
        run_pipeline(files)
        return

    # ── Display completeness results ────────────────────────────────────
    if cc:
        _cc_tab1, _cc_tab2, _cc_tab3 = st.tabs(["📋 Completeness Check", "🔍 Scope Validator", "📄 Template Scan"])

        # ── TAB 2: Scope Validator ──────────────────────────────────────
        with _cc_tab2:
            _sv_doc_text = safe_str(st.session_state.get("_completeness_text", "")
                                    or st.session_state.get("_extracted_text", ""))
            _sv2_key = "scope_validation_result"
            _sv2_col1, _sv2_col2 = st.columns([4, 1])
            with _sv2_col2:
                if st.button("🔄 Re-analyse", key="btn_sv2_rerun", width="stretch"):
                    st.session_state.pop(_sv2_key, None)
                    st.rerun()
            with _sv2_col1:
                st.markdown(
                    '<div style="font-size:.8rem;color:#64748b;padding-top:8px">'
                    'AI reviews the scope document for critical gaps, assumptions and missing '
                    'information — generates a client-ready clarification email.</div>',
                    unsafe_allow_html=True,
                )

            if not st.session_state.get(_sv2_key):
                with st.spinner("Analysing scope for gaps and assumptions…"):
                    _sv2_result = _run_scope_validation({}, _sv_doc_text)
            else:
                _sv2_result = st.session_state[_sv2_key]

            _sv2_score     = safe_int(_sv2_result.get("completeness_score", 0))
            _sv2_summary   = safe_str(_sv2_result.get("summary", ""))
            _sv2_blockers  = safe_list(_sv2_result.get("blockers", []))
            _sv2_assumes   = safe_list(_sv2_result.get("assumptions", []))
            _sv2_confirmed = safe_list(_sv2_result.get("confirmed", []))
            _sv2_email_sub = safe_str(_sv2_result.get("email_subject", ""))
            _sv2_email_bod = safe_str(_sv2_result.get("email_body", ""))
            _sv2_clr = "#06d6a0" if _sv2_score >= 75 else "#ffd166" if _sv2_score >= 50 else "#f87171"

            # Score banner
            st.markdown(
                f'<div style="background:linear-gradient(135deg,rgba(15,23,42,.9),rgba(30,42,68,.8));'
                f'border:1px solid {_sv2_clr}44;border-radius:16px;padding:20px 24px;margin:14px 0 20px">'
                f'<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
                f'<div style="text-align:center;min-width:90px">'
                f'<div style="font-size:2.4rem;font-weight:900;color:{_sv2_clr};line-height:1">{_sv2_score}</div>'
                f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:4px">Score / 100</div>'
                f'</div>'
                f'<div style="flex:1;min-width:200px">'
                f'<div style="background:rgba(255,255,255,.07);border-radius:8px;height:10px;overflow:hidden;margin-bottom:10px">'
                f'<div style="height:100%;width:{min(100,_sv2_score)}%;border-radius:8px;'
                f'background:linear-gradient(90deg,{_sv2_clr},{_sv2_clr}99);box-shadow:0 0 10px {_sv2_clr}66"></div>'
                f'</div>'
                f'<div style="font-size:.85rem;color:#e2e8f0;font-weight:500">{_sv2_summary}</div>'
                f'</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                f'<div style="background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#f87171">{len(_sv2_blockers)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Blockers</div></div>'
                f'<div style="background:rgba(255,209,102,.1);border:1px solid rgba(255,209,102,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#ffd166">{len(_sv2_assumes)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Assumptions</div></div>'
                f'<div style="background:rgba(6,214,160,.1);border:1px solid rgba(6,214,160,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#06d6a0">{len(_sv2_confirmed)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Confirmed</div></div>'
                f'</div></div></div>',
                unsafe_allow_html=True,
            )

            # Blockers
            if _sv2_blockers:
                st.markdown('<div style="font-size:.78rem;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:.8px;margin:4px 0 10px">🔴 Blockers — Resolve Before Committing</div>', unsafe_allow_html=True)
                for _b in _sv2_blockers:
                    if not isinstance(_b, dict): continue
                    st.markdown(
                        f'<div style="background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.25);'
                        f'border-left:4px solid #f87171;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                        f'<span style="background:rgba(248,113,113,.2);color:#f87171;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:8px;text-transform:uppercase">{safe_str(_b.get("category",""))}</span>'
                        f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">{safe_str(_b.get("issue",""))}</span></div>'
                        f'<div style="font-size:.75rem;color:#94a3b8;margin-bottom:8px">⚠ Impact: {safe_str(_b.get("impact",""))}</div>'
                        + (f'<div style="background:rgba(248,113,113,.08);border-radius:6px;padding:8px 12px;font-size:.76rem;color:#fca5a5;font-style:italic">💬 "{safe_str(_b.get("question",""))}"</div>' if _b.get("question") else "")
                        + '</div>', unsafe_allow_html=True,
                    )

            # Assumptions
            if _sv2_assumes:
                st.markdown('<div style="font-size:.78rem;font-weight:700;color:#ffd166;text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px">🟡 Assumptions Made — Affect Estimate Accuracy</div>', unsafe_allow_html=True)
                for _a in _sv2_assumes:
                    if not isinstance(_a, dict): continue
                    st.markdown(
                        f'<div style="background:rgba(255,209,102,.05);border:1px solid rgba(255,209,102,.22);'
                        f'border-left:4px solid #ffd166;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                        f'<span style="background:rgba(255,209,102,.18);color:#ffd166;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:8px;text-transform:uppercase">{safe_str(_a.get("category",""))}</span>'
                        f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">{safe_str(_a.get("assumption",""))}</span></div>'
                        f'<div style="font-size:.75rem;color:#94a3b8;margin-bottom:8px">📊 Impact: {safe_str(_a.get("impact",""))}</div>'
                        + (f'<div style="background:rgba(255,209,102,.07);border-radius:6px;padding:8px 12px;font-size:.76rem;color:#fde68a;font-style:italic">💬 "{safe_str(_a.get("question",""))}"</div>' if _a.get("question") else "")
                        + '</div>', unsafe_allow_html=True,
                    )

            # Confirmed
            if _sv2_confirmed:
                st.markdown('<div style="font-size:.78rem;font-weight:700;color:#06d6a0;text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px">🟢 Confirmed — Clearly Defined</div>', unsafe_allow_html=True)
                _conf2_html = "".join(
                    f'<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">'
                    f'<span style="background:rgba(6,214,160,.15);color:#06d6a0;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:8px;white-space:nowrap;margin-top:1px">{safe_str(_c.get("category",""))}</span>'
                    f'<span style="font-size:.78rem;color:#cbd5e1">{safe_str(_c.get("detail",""))}</span></div>'
                    for _c in _sv2_confirmed if isinstance(_c, dict)
                )
                st.markdown(f'<div style="background:rgba(6,214,160,.04);border:1px solid rgba(6,214,160,.18);border-radius:10px;padding:14px 18px">{_conf2_html}</div>', unsafe_allow_html=True)

            # Client Q&A email
            if _sv2_email_bod:
                st.markdown('<div style="font-size:.78rem;font-weight:700;color:#7b61ff;text-transform:uppercase;letter-spacing:.8px;margin:22px 0 10px">📧 Client Clarification Email — Ready to Send</div>', unsafe_allow_html=True)
                _email2_full = f"Subject: {_sv2_email_sub}\n\n{_sv2_email_bod}"
                st.text_area("", value=_email2_full, height=260, key="sv2_email_area", label_visibility="collapsed")
                st.download_button(
                    "📋 Download Q&A as .txt",
                    data=_email2_full.encode("utf-8"),
                    file_name="Scope_Clarification.txt",
                    mime="text/plain",
                    key="sv2_email_dl",
                )

        # ── TAB 3: Template Scan ─────────────────────────────────────────
        with _cc_tab3:
            import html as _html_mod

            _ts_doc = safe_str(st.session_state.get("_completeness_text", "")
                               or st.session_state.get("_extracted_text", ""))
            _ts_key = "scope_template_scan_result"

            _ts_c1, _ts_c2 = st.columns([4, 1])
            with _ts_c1:
                st.markdown(
                    '<div style="font-size:.8rem;color:#64748b;padding-top:8px">'
                    'AI scans your scope document against the standard ECI template and flags every '
                    'section that is missing, incomplete, or still contains placeholder text — '
                    'highlighted in red directly in the document.</div>',
                    unsafe_allow_html=True,
                )
            with _ts_c2:
                if st.button("🔄 Re-scan", key="btn_ts_rerun", width="stretch"):
                    st.session_state.pop(_ts_key, None)
                    st.rerun()

            if not _ts_doc.strip():
                st.info("Upload a scope document and run the completeness check first.")
            else:
                if not st.session_state.get(_ts_key):
                    with st.spinner("Scanning scope document against ECI template…"):
                        _ts_ai = _pick_ai_for("completeness")
                        _ts_result = _ts_ai.scan_scope_template(_ts_doc)
                        st.session_state[_ts_key] = _ts_result
                else:
                    _ts_result = st.session_state[_ts_key]

                _ts_score   = safe_int(_ts_result.get("overall_score", 0))
                _ts_issues  = [i for i in safe_list(_ts_result.get("issues", [])) if isinstance(i, dict)]
                _ts_good    = safe_list(_ts_result.get("good_sections", []))
                _ts_crits   = [i for i in _ts_issues if safe_str(i.get("severity")) == "critical"]
                _ts_warns   = [i for i in _ts_issues if safe_str(i.get("severity")) != "critical"]
                _ts_col     = "#f87171" if _ts_score < 50 else "#ffd166" if _ts_score < 75 else "#06d6a0"

                # Score banner
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,rgba(15,23,42,.9),rgba(30,42,68,.8));'
                    f'border:1px solid {_ts_col}44;border-radius:16px;padding:18px 22px;margin:12px 0 18px;'
                    f'display:flex;align-items:center;gap:24px;flex-wrap:wrap">'
                    f'<div style="text-align:center;min-width:80px">'
                    f'<div style="font-size:2.4rem;font-weight:900;color:{_ts_col};line-height:1">{_ts_score}</div>'
                    f'<div style="font-size:.6rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">Quality Score</div>'
                    f'</div>'
                    f'<div style="flex:1;min-width:180px">'
                    f'<div style="background:rgba(255,255,255,.07);border-radius:6px;height:8px;overflow:hidden;margin-bottom:8px">'
                    f'<div style="height:100%;width:{min(100,_ts_score)}%;background:linear-gradient(90deg,{_ts_col},{_ts_col}99);border-radius:6px"></div>'
                    f'</div>'
                    f'<div style="font-size:.82rem;color:#94a3b8">'
                    f'{len(_ts_crits)} critical issue{"s" if len(_ts_crits)!=1 else ""}  ·  '
                    f'{len(_ts_warns)} warning{"s" if len(_ts_warns)!=1 else ""}  ·  '
                    f'{len(_ts_good)} section{"s" if len(_ts_good)!=1 else ""} look good</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Annotated document view ───────────────────────────
                st.markdown(
                    '<div style="font-size:.78rem;font-weight:700;color:#e2e8f0;'
                    'text-transform:uppercase;letter-spacing:.8px;margin:4px 0 10px">'
                    '📄 Scope Document — Issues Highlighted</div>',
                    unsafe_allow_html=True,
                )

                # Build highlighted HTML from the raw document text
                _ts_escaped = _html_mod.escape(_ts_doc)
                for _iss in sorted(_ts_issues, key=lambda x: len(safe_str(x.get("excerpt",""))), reverse=True):
                    _exc = safe_str(_iss.get("excerpt", "")).strip()
                    if not _exc:
                        continue
                    _exc_esc = _html_mod.escape(_exc)
                    if _exc_esc not in _ts_escaped:
                        continue
                    _sev = safe_str(_iss.get("severity", "warning"))
                    if _sev == "critical":
                        _mark = (
                            f'<mark style="background:rgba(248,113,113,0.28);'
                            f'border-bottom:2px solid #f87171;border-radius:3px;'
                            f'padding:1px 2px;color:#fca5a5;font-weight:600" '
                            f'title="🔴 {_html_mod.escape(safe_str(_iss.get("problem","")))}">'
                            f'{_exc_esc}</mark>'
                        )
                    else:
                        _mark = (
                            f'<mark style="background:rgba(252,211,77,0.20);'
                            f'border-bottom:2px solid #fcd34d;border-radius:3px;'
                            f'padding:1px 2px;color:#fde68a;font-weight:500" '
                            f'title="⚠️ {_html_mod.escape(safe_str(_iss.get("problem","")))}">'
                            f'{_exc_esc}</mark>'
                        )
                    _ts_escaped = _ts_escaped.replace(_exc_esc, _mark, 1)

                st.markdown(
                    f'<div style="background:#0a0e1a;border:1px solid rgba(255,255,255,.08);'
                    f'border-radius:12px;padding:20px 24px;font-family:monospace;'
                    f'font-size:.78rem;line-height:1.75;color:#cbd5e1;'
                    f'white-space:pre-wrap;max-height:480px;overflow-y:auto">'
                    f'{_ts_escaped}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div style="font-size:.68rem;color:#475569;margin-top:6px">'
                    '🔴 red = critical (blocks estimation) &nbsp;·&nbsp; '
                    '🟡 amber = warning (reduces accuracy) &nbsp;·&nbsp; '
                    'Hover highlighted text to see the issue.</div>',
                    unsafe_allow_html=True,
                )

                # ── Issue list ────────────────────────────────────────
                if _ts_crits:
                    st.markdown(
                        '<div style="font-size:.78rem;font-weight:700;color:#f87171;'
                        'text-transform:uppercase;letter-spacing:.8px;margin:22px 0 10px">'
                        '🔴 Critical Issues — Must Fix Before Estimating</div>',
                        unsafe_allow_html=True,
                    )
                    for _iss in _ts_crits:
                        st.markdown(
                            f'<div style="background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.25);'
                            f'border-left:4px solid #f87171;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                            f'<span style="background:rgba(248,113,113,.2);color:#f87171;font-size:.62rem;'
                            f'font-weight:700;padding:2px 8px;border-radius:8px">'
                            f'{safe_str(_iss.get("section",""))}</span>'
                            f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">'
                            f'{safe_str(_iss.get("problem",""))}</span></div>'
                            f'<div style="background:rgba(248,113,113,.08);border-radius:6px;'
                            f'padding:7px 12px;font-size:.75rem;color:#fca5a5;font-style:italic;margin-bottom:8px">'
                            f'"{safe_str(_iss.get("excerpt",""))}"</div>'
                            f'<div style="font-size:.75rem;color:#94a3b8">'
                            f'✏️ {safe_str(_iss.get("suggestion",""))}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if _ts_warns:
                    st.markdown(
                        '<div style="font-size:.78rem;font-weight:700;color:#fcd34d;'
                        'text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px">'
                        '⚠️ Warnings — Will Reduce Estimate Accuracy</div>',
                        unsafe_allow_html=True,
                    )
                    for _iss in _ts_warns:
                        st.markdown(
                            f'<div style="background:rgba(252,211,77,.05);border:1px solid rgba(252,211,77,.22);'
                            f'border-left:4px solid #fcd34d;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                            f'<span style="background:rgba(252,211,77,.18);color:#fcd34d;font-size:.62rem;'
                            f'font-weight:700;padding:2px 8px;border-radius:8px">'
                            f'{safe_str(_iss.get("section",""))}</span>'
                            f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">'
                            f'{safe_str(_iss.get("problem",""))}</span></div>'
                            f'<div style="background:rgba(252,211,77,.07);border-radius:6px;'
                            f'padding:7px 12px;font-size:.75rem;color:#fde68a;font-style:italic;margin-bottom:8px">'
                            f'"{safe_str(_iss.get("excerpt",""))}"</div>'
                            f'<div style="font-size:.75rem;color:#94a3b8">'
                            f'✏️ {safe_str(_iss.get("suggestion",""))}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                if _ts_good:
                    st.markdown(
                        '<div style="font-size:.78rem;font-weight:700;color:#06d6a0;'
                        'text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px">'
                        '✅ Sections That Look Good</div>',
                        unsafe_allow_html=True,
                    )
                    _good_html = "".join(
                        f'<span style="background:rgba(6,214,160,.12);border:1px solid rgba(6,214,160,.3);'
                        f'color:#06d6a0;font-size:.75rem;font-weight:600;padding:4px 14px;'
                        f'border-radius:20px;margin:3px 4px;display:inline-block">{_html_mod.escape(safe_str(g))}</span>'
                        for g in _ts_good
                    )
                    st.markdown(f'<div style="margin:4px 0 8px">{_good_html}</div>', unsafe_allow_html=True)

        # ── TAB 1: Completeness Check (existing content) ────────────────
        with _cc_tab1:
            confidence = cc.get("confidence", "Medium")
            meta = _CONFIDENCE_META.get(confidence, _CONFIDENCE_META["Medium"])
            total_q = sum(len(cat.get("questions", [])) for cat in cc.get("categories", []))
            acked: set = st.session_state.get("_completeness_acked", set())

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.markdown(
                f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);'
                f'border-radius:14px;padding:18px 22px;margin-bottom:14px">'
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
                f'<span style="font-size:1.5rem">{meta["icon"]}</span>'
                f'<span style="font-weight:700;font-size:1.05rem;color:#e2e8f0">Requirements Completeness Check</span>'
                f'<span style="background:{meta["color"]}22;color:{meta["color"]};border:1px solid {meta["color"]}44;'
                f'border-radius:20px;padding:2px 12px;font-size:.75rem;font-weight:700">{meta["label"]}</span>'
                f'</div>'
                f'<div style="color:#94a3b8;font-size:.85rem;line-height:1.6">{cc.get("summary", "")}</div>'
                f'<div style="margin-top:10px;font-size:.78rem;color:#64748b">'
                f'{len(acked)} of {total_q} questions acknowledged</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── What IS clear ───────────────────────────────────────────
            clear_items = cc.get("what_is_clear", [])
            if clear_items:
                with st.expander("✅ What the document makes clear", expanded=False):
                    for item in clear_items:
                        st.markdown(
                            f'<div style="display:flex;align-items:flex-start;gap:8px;'
                            f'padding:5px 0;color:#86efac;font-size:.84rem">'
                            f'<span style="flex-shrink:0">✓</span><span>{item}</span></div>',
                            unsafe_allow_html=True,
                        )

            # ── Questions by category ────────────────────────────────────
            st.markdown(
                '<div style="font-weight:700;color:#e2e8f0;font-size:.9rem;'
                'margin:16px 0 10px">📋 Clarification Questions for the Presales Team</div>',
                unsafe_allow_html=True,
            )

            for cat in cc.get("categories", []):
                cat_name = cat.get("name", "General")
                cat_icon = cat.get("icon", "❓")
                questions = cat.get("questions", [])
                if not questions:
                    continue

                with st.expander(f"{cat_icon} {cat_name}  ({len(questions)})", expanded=True):
                    for qi, q in enumerate(questions):
                        q_id = f"{cat_name}::{qi}"
                        is_acked = q_id in acked
                        ck_col, txt_col = st.columns([0.5, 9.5])
                        with ck_col:
                            checked = st.checkbox(
                                "",
                                value=is_acked,
                                key=f"cc_{cat_name}_{qi}",
                                label_visibility="collapsed",
                            )
                            if checked and q_id not in acked:
                                acked.add(q_id)
                                st.session_state["_completeness_acked"] = acked
                            elif not checked and q_id in acked:
                                acked.discard(q_id)
                                st.session_state["_completeness_acked"] = acked
                        with txt_col:
                            opacity = ".45" if is_acked else "1"
                            st.markdown(
                                f'<div style="opacity:{opacity};padding:4px 0">'
                                f'<div style="font-size:.84rem;color:#e2e8f0;font-weight:500">'
                                f'{q.get("question", "")}</div>'
                                f'<div style="font-size:.74rem;color:#64748b;margin-top:2px">'
                                f'Why: {q.get("why", "")}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

            # ── Proceed banner ───────────────────────────────────────────
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            all_acked = len(acked) == total_q
            pct = int(len(acked) / total_q * 100) if total_q else 100
            st.progress(pct / 100, text=f"{pct}% questions reviewed")

            prc1, prc2 = st.columns(2)
            with prc1:
                if st.button(
                    "⚡ Proceed to Full Analysis",
                    width="stretch",
                    type="primary",
                    key="go_after_cc",
                    help="Run the 10-agent pipeline now.",
                ):
                    run_pipeline(files)
            with prc2:
                st.caption(
                    "✅ All questions reviewed — ready to proceed!" if all_acked
                    else f"Tip: tick each question once discussed with the client. ({total_q - len(acked)} remaining)"
                )


# ═══════════════════════════════════════════════════════════════════════
#  3D ARCHITECTURE VIEW HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _generate_3d_tour_script(r, ai_client):
    """Call the AI to generate a narration map {component_name: text} for the 3D tour.
    Returns a dict or {} on failure.
    """
    import re as _re
    import json as _json

    arch = safe_dict(safe_dict(r).get("architecture", {}))
    components = safe_list(arch.get("components", []))
    if not components:
        return {}

    comp_lines = []
    for c in components:
        c = safe_dict(c)
        name = safe_str(c.get("name", ""))
        svc = safe_str(c.get("azure_service", ""))
        ctype = safe_str(c.get("type", ""))
        if name:
            comp_lines.append(f"- {name} ({svc or ctype})")

    comp_text = "\n".join(comp_lines)
    system = (
        "You are a solution architect narrator. Given a list of Azure architecture components, "
        "generate a JSON object where each key is the exact component name and each value is "
        "a 2-sentence narration under 50 words, suitable for text-to-speech during a 3D tour. "
        "Be concise, professional, and highlight the component's role and value. "
        "Return ONLY valid JSON, no markdown, no explanation."
    )
    user = (
        "Generate tour narration for these components:\n\n"
        + comp_text
        + "\n\nReturn JSON: {\"Component Name\": \"narration text\", ...}"
    )

    try:
        if ai_client is None:
            return {}
        response = ai_client.call_raw_text(system, user)
        if not response:
            return {}
        m = _re.search(r'\{[\s\S]+\}', response)
        if not m:
            return {}
        return _json.loads(m.group(0))
    except Exception:
        return {}


def _render_narrator_tab(r: dict, se: dict, te: dict, ce: dict, ri: dict, ar: dict):
    """Architect Narrator — ElevenLabs voice + HeyGen/D-ID avatar video."""
    st.markdown("### 🎬 Architect Narrator — AI Video Presenter")
    st.markdown(
        "Transform your proposal into a **personalised architect presenter video**. "
        "The pipeline is:\n\n"
        "1. **Script** — AI summarises the proposal into a conversational ~200-word pitch\n"
        "2. **Voice** — ElevenLabs synthesises the script in the architect's cloned voice\n"
        "3. **Video** — HeyGen or D-ID animates the avatar with perfect lip-sync\n\n"
        "Configure ElevenLabs & HeyGen/D-ID keys in the sidebar, then click **Generate Script**."
    )
    st.markdown("---")

    narrator = ArchitectNarrator.from_session()

    # ── Status pills ──────────────────────────────────────────────────
    pill_cols = st.columns(3)
    with pill_cols[0]:
        ai_ok = AzureAI.from_session().is_live
        st.markdown(
            '<span style="background:' + ('rgba(0,212,170,.15);color:#00d4aa;border:1px solid #00d4aa'
            if ai_ok else 'rgba(255,107,107,.12);color:#ff6b6b;border:1px solid #ff6b6b') +
            ';padding:4px 14px;border-radius:20px;font-size:.75rem;font-weight:600">' +
            ('✓ Azure OpenAI ready' if ai_ok else '✗ Azure OpenAI not configured') + '</span>',
            unsafe_allow_html=True,
        )
    with pill_cols[1]:
        st.markdown(
            '<span style="background:' + ('rgba(0,212,170,.15);color:#00d4aa;border:1px solid #00d4aa'
            if narrator.el_ready else 'rgba(255,107,107,.12);color:#ff6b6b;border:1px solid #ff6b6b') +
            ';padding:4px 14px;border-radius:20px;font-size:.75rem;font-weight:600">' +
            ('✓ ElevenLabs ready' if narrator.el_ready else '✗ ElevenLabs key missing') + '</span>',
            unsafe_allow_html=True,
        )
    with pill_cols[2]:
        st.markdown(
            '<span style="background:' + ('rgba(0,212,170,.15);color:#00d4aa;border:1px solid #00d4aa'
            if narrator.hg_ready else 'rgba(255,107,107,.12);color:#ff6b6b;border:1px solid #ff6b6b') +
            ';padding:4px 14px;border-radius:20px;font-size:.75rem;font-weight:600">' +
            ('✓ HeyGen ready' if narrator.hg_ready else '✗ HeyGen key missing') + '</span>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Step 1: Script ────────────────────────────────────────────────
    if "narrator_script" not in st.session_state:
        st.session_state.narrator_script = ""

    gen_cols = st.columns([3, 1])
    with gen_cols[1]:
        if st.button("✍️ Generate Script", width="stretch", key="btn_gen_script"):
            with st.spinner("Writing architect pitch script…"):
                st.session_state.narrator_script = narrator.generate_script(r)
            st.success("Script ready — review and edit below before generating audio/video.")
    with gen_cols[0]:
        st.markdown("**Step 1 — Architect Pitch Script**")

    script_text = st.text_area(
        "Script (edit freely before generating voice/video)",
        value=st.session_state.narrator_script,
        height=220,
        key="narrator_script_area",
        placeholder="Click 'Generate Script' to create a personalised pitch from the proposal data…",
    )
    st.session_state.narrator_script = script_text
    word_count = len(script_text.split()) if script_text.strip() else 0
    st.caption(f"{word_count} words · ≈{max(1, word_count // 130)} min spoken")
    st.markdown("---")

    # ── Step 2: Voice Synthesis ───────────────────────────────────────
    st.markdown("**Step 2 — Voice Synthesis (ElevenLabs)**")
    voice_cols = st.columns([3, 1])
    with voice_cols[1]:
        gen_voice = st.button("🎙️ Synthesise Voice", width="stretch",
                              key="btn_voice",
                              disabled=not (script_text.strip() and narrator.el_ready))
    with voice_cols[0]:
        if not narrator.el_ready:
            st.info("Add your ElevenLabs API key in the sidebar to enable voice synthesis.")
        else:
            st.caption("Calls ElevenLabs multilingual-v2 TTS with your configured voice ID.")

    if gen_voice and script_text.strip():
        with st.spinner("Calling ElevenLabs TTS — synthesising voice…"):
            mp3_bytes, err = narrator.synthesize_voice(script_text)
        if err:
            st.error("Voice synthesis failed: " + err)
            st.session_state["narrator_mp3"] = None
        else:
            st.session_state["narrator_mp3"] = mp3_bytes
            st.success(f"Voice synthesised — {len(mp3_bytes):,} bytes of audio.")

    if st.session_state.get("narrator_mp3"):
        st.audio(st.session_state["narrator_mp3"], format="audio/mp3")
        st.download_button(
            "💾 Download MP3",
            data=st.session_state["narrator_mp3"],
            file_name="ECI_Architect_Narration_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp3",
            mime="audio/mpeg",
            key="dl_mp3",
        )

    st.markdown("---")

    # ── Step 3: Video Generation ──────────────────────────────────────
    st.markdown("**Step 3 — Avatar Video Generation (HeyGen / D-ID)**")

    if narrator.did_ready:
        st.info(
            "✨ **D-ID Free Tier detected** — generate talking-head videos for FREE "
            "(free trial: ~5 videos, then affordable pay-as-you-go). No HeyGen credits consumed."
        )
        did_mode_label = "🆓 D-ID (Free)"
    else:
        did_mode_label = None

    platform_options = ["HeyGen (Premium)"]
    if did_mode_label:
        platform_options.insert(0, did_mode_label)
    narrator_platform = st.radio(
        "Video platform", platform_options, horizontal=True, key="narrator_platform_radio",
    )
    use_did = (narrator_platform == did_mode_label)
    st.markdown("---")

    # ── D-ID flow ─────────────────────────────────────────────────────
    if use_did:
        st.markdown("**D-ID — Free Talking Avatar Video**")
        st.caption(
            "D-ID animates any portrait photo to match the voice. "
            "Upload a headshot or paste a public image URL."
        )
        did_img_cols = st.columns([3, 1])
        with did_img_cols[0]:
            did_photo = st.file_uploader(
                "Upload avatar photo (JPG/PNG)", type=["jpg","jpeg","png"], key="did_photo_upload"
            )
            did_url_input = st.text_input(
                "Or paste a public photo URL",
                value=st.session_state.get("narrator_did_image_url",""),
                placeholder="https://example.com/headshot.jpg",
                key="did_url_input",
            )
            if did_url_input.strip():
                st.session_state.narrator_did_image_url = did_url_input.strip()
        with did_img_cols[1]:
            upload_did_btn = st.button(
                "⬆️ Upload to D-ID", width="stretch",
                key="btn_did_upload", disabled=did_photo is None,
            )
        if upload_did_btn and did_photo is not None:
            img_bytes = did_photo.read()
            ctype = "image/png" if did_photo.name.lower().endswith(".png") else "image/jpeg"
            with st.spinner("Uploading photo to D-ID…"):
                img_url, img_err = narrator.did_upload_image(img_bytes, ctype)
            if img_err:
                st.error("D-ID upload failed: " + img_err)
            else:
                st.session_state.narrator_did_image_url = img_url
                st.success(f"Photo uploaded to D-ID! URL: `{img_url[:60]}…`")

        effective_did_image = st.session_state.get("narrator_did_image_url","")
        if effective_did_image:
            st.caption(f"Avatar image: `{effective_did_image[:70]}…`")

        mp3_ready = bool(st.session_state.get("narrator_mp3"))
        if mp3_ready:
            st.caption("ElevenLabs audio ready — D-ID will lip-sync to your voice clone.")
        elif narrator.el_ready:
            st.caption("ElevenLabs key set — D-ID will use it as the TTS provider.")
        else:
            st.caption("No voice configured — D-ID will use Microsoft Neural TTS (en-US-GuyNeural).")

        can_did = bool(script_text.strip() and effective_did_image)
        did_btn = st.button(
            "🆓 Generate Free Video (D-ID)", disabled=not can_did,
            type="primary", key="btn_did_generate",
        )
        if did_btn and can_did:
            mp3_bytes_for_did = st.session_state.get("narrator_mp3")
            with st.spinner("Submitting to D-ID — usually completes in 30–90 seconds…"):
                talk_id, did_err = narrator.generate_did_video(
                    script_text, mp3_bytes_for_did, effective_did_image
                )
            if did_err:
                st.error("D-ID submission failed: " + did_err)
            else:
                st.info(f"D-ID job submitted (talk_id: `{talk_id}`). Polling…")
                pb = st.progress(0)
                stat_ph = st.empty()
                waited, max_wait, interval = 0, 240, 8
                did_video_url = None
                did_poll_err  = None
                while waited < max_wait:
                    pb.progress(min(int(waited / max_wait * 100), 95))
                    time.sleep(interval)
                    waited += interval
                    url, status, perr = narrator.poll_did_video(talk_id)
                    stat_ph.caption(f"D-ID status: **{status}** ({waited}s elapsed)")
                    if status == "done" and url:
                        did_video_url = url; break
                    if status == "error":
                        did_poll_err = perr or "D-ID generation failed"; break
                pb.progress(100)
                if did_poll_err:
                    st.error(did_poll_err)
                elif did_video_url:
                    st.session_state["narrator_result"] = {
                        "video_url": did_video_url, "video_id": talk_id,
                        "script": script_text, "platform": "D-ID (Free)",
                    }
                    st.success("D-ID video ready!")
                else:
                    st.warning(
                        f"D-ID did not complete within {max_wait}s. "
                        f"Check your D-ID dashboard for talk_id `{talk_id}`."
                    )

    # ── HeyGen flow ───────────────────────────────────────────────────
    else:
        if not narrator.hg_ready:
            st.info("Add your HeyGen API Key in the sidebar to enable video generation.")
        else:
            rem, plan_cr, cr_err = narrator.check_credits()
            if cr_err:
                st.caption(f"Credit check failed: {cr_err}")
            elif rem == 0:
                st.warning(
                    f"⚠️ HeyGen account has **0 remaining credits** (plan: {plan_cr}/month). "
                    "Add D-ID key (sidebar) for free video generation, or top up at "
                    "[heygen.com/pricing](https://www.heygen.com/pricing)."
                )
            else:
                st.success(f"HeyGen credits: **{rem}** remaining (plan: {plan_cr}/month)")

            mode_labels = [
                "🎨 Custom Avatar ID",
                "🎭 Free Stock Avatar",
                "📸 Talking Photo (upload a photo)",
            ]
            mode_map = {
                "🎨 Custom Avatar ID":               "custom",
                "🎭 Free Stock Avatar":              "stock",
                "📸 Talking Photo (upload a photo)": "talking_photo",
            }
            if "narrator_mode" not in st.session_state:
                st.session_state.narrator_mode = "custom"
            current_mode_label = next(
                (lbl for lbl, v in mode_map.items() if v == st.session_state.narrator_mode),
                mode_labels[0],
            )
            chosen_label = st.radio(
                "Avatar mode", mode_labels,
                index=mode_labels.index(current_mode_label),
                horizontal=True, key="narrator_mode_radio",
            )
            st.session_state.narrator_mode = mode_map[chosen_label]
            talking_photo_id_to_use = ""

            if st.session_state.narrator_mode == "custom":
                st.caption("Paste the Avatar ID of the custom avatar you created in HeyGen.")
                if "narrator_custom_avatar_id" not in st.session_state:
                    st.session_state.narrator_custom_avatar_id = narrator.avatar_id
                custom_id_input = st.text_input(
                    "Your HeyGen Custom Avatar ID",
                    value=st.session_state.narrator_custom_avatar_id,
                    placeholder="e.g. 6a15f2e40c234b1e81f51f096924305f",
                    key="narrator_custom_id_field",
                )
                st.session_state.narrator_custom_avatar_id = custom_id_input.strip()

            elif st.session_state.narrator_mode == "stock":
                av_cols = st.columns([2, 1, 1])
                with av_cols[1]:
                    fetch_avs = st.button("🔍 Fetch Avatars", width="stretch", key="btn_fetch_avs")
                if fetch_avs:
                    with st.spinner("Fetching HeyGen avatars…"):
                        avs, av_err = narrator.list_free_avatars()
                    if av_err:
                        st.error(av_err)
                    else:
                        st.session_state.narrator_free_avatars = avs
                        st.success(f"Found {len(avs)} avatar(s).")
                if st.session_state.get("narrator_free_avatars"):
                    av_options = {
                        (a["avatar_name"] or a["avatar_id"]) + (f"  [{a['gender']}]" if a.get("gender") else ""): a["avatar_id"]
                        for a in st.session_state.narrator_free_avatars
                    }
                    chosen_name = st.selectbox("Select avatar", list(av_options.keys()), key="narrator_av_select")
                    st.session_state.narrator_selected_avatar = av_options[chosen_name]
                    st.caption(f"Avatar ID: `{st.session_state.narrator_selected_avatar}`")
                    chosen_av = next(
                        (a for a in st.session_state.narrator_free_avatars
                         if a["avatar_id"] == st.session_state.get("narrator_selected_avatar","")), None
                    )
                    if chosen_av and chosen_av.get("preview_image_url"):
                        st.image(chosen_av["preview_image_url"], width=120)
                else:
                    st.info("Click **Fetch Avatars** to browse available avatars.")

            else:  # talking_photo
                tp_cols = st.columns([3, 1])
                with tp_cols[0]:
                    uploaded_photo = st.file_uploader(
                        "Upload architect photo (JPG/PNG, max 5 MB)",
                        type=["jpg","jpeg","png"], key="narrator_photo_upload",
                    )
                with tp_cols[1]:
                    upload_btn = st.button(
                        "⬆️ Upload Photo", width="stretch",
                        key="btn_upload_photo", disabled=uploaded_photo is None,
                    )
                if upload_btn and uploaded_photo is not None:
                    img_bytes = uploaded_photo.read()
                    ctype = "image/png" if uploaded_photo.name.lower().endswith(".png") else "image/jpeg"
                    with st.spinner("Uploading photo to HeyGen…"):
                        tp_id, tp_err = narrator.upload_talking_photo(img_bytes, ctype)
                    if tp_err:
                        st.error("Photo upload failed: " + tp_err)
                    else:
                        st.session_state.narrator_photo_id = tp_id
                        st.success(f"Talking Photo ready. ID: `{tp_id}`")
                if "narrator_photo_id" not in st.session_state:
                    st.session_state.narrator_photo_id = ""
                manual_tp_id = st.text_input(
                    "Or paste an existing Talking Photo ID",
                    value=st.session_state.narrator_photo_id,
                    placeholder="e.g. f5e3d2a1b4c6…",
                    key="narrator_tp_id_input",
                )
                if manual_tp_id.strip():
                    st.session_state.narrator_photo_id = manual_tp_id.strip()
                talking_photo_id_to_use = st.session_state.narrator_photo_id
                if not talking_photo_id_to_use:
                    st.warning("Upload a photo or paste an existing Talking Photo ID to continue.")

            st.markdown("")
            mp3_ready = bool(st.session_state.get("narrator_mp3"))
            if mp3_ready:
                st.caption("Voice audio ready — the avatar will lip-sync to the ElevenLabs voice.")
            else:
                st.caption("No ElevenLabs audio — HeyGen TTS will be used. Run Step 2 for best results.")

            if st.session_state.narrator_mode == "custom":
                effective_avatar_id = st.session_state.get("narrator_custom_avatar_id","")
                effective_tp_id     = ""
            elif st.session_state.narrator_mode == "stock":
                effective_avatar_id = st.session_state.get("narrator_selected_avatar","")
                effective_tp_id     = ""
            else:
                effective_avatar_id = ""
                effective_tp_id     = talking_photo_id_to_use

            can_generate = bool(script_text.strip() and (effective_avatar_id or effective_tp_id))
            gen_video_btn = st.button(
                "🎥 Generate Video", width="content",
                key="btn_video", disabled=not can_generate, type="primary",
            )
            if gen_video_btn and can_generate:
                import urllib.request as _ur
                mp3_bytes_for_hg = st.session_state.get("narrator_mp3")
                _orig_av = narrator.avatar_id
                narrator.avatar_id = effective_avatar_id or narrator.avatar_id
                with st.spinner("Submitting to HeyGen — may take 2–4 minutes…"):
                    video_id, err = narrator.generate_video(
                        script_text, mp3_bytes_for_hg,
                        talking_photo_id=effective_tp_id,
                        test_mode=False,
                    )
                narrator.avatar_id = _orig_av
                if err:
                    st.error("Video generation failed: " + err)
                else:
                    st.info(f"HeyGen job submitted (video_id: `{video_id}`). Polling for completion…")
                    progress_bar = st.progress(0)
                    status_ph = st.empty()
                    waited, max_wait, interval = 0, 300, 10
                    video_url = None
                    poll_err  = None
                    while waited < max_wait:
                        progress_bar.progress(min(int(waited / max_wait * 100), 95))
                        status_ph.caption(f"Waiting for HeyGen… {waited}s / {max_wait}s")
                        time.sleep(interval)
                        waited += interval
                        try:
                            req = _ur.Request(
                                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                                headers={"X-Api-Key": narrator.hg_key, "Accept": "application/json"},
                                method="GET",
                            )
                            with _ur.urlopen(req, timeout=15) as resp:
                                data = json.loads(resp.read().decode("utf-8"))
                                status = (data.get("data") or {}).get("status", "")
                                status_ph.caption(f"HeyGen status: **{status}** ({waited}s elapsed)")
                                if status == "completed":
                                    video_url = (data.get("data") or {}).get("video_url",""); break
                                if status in ("failed","error"):
                                    err_obj  = (data.get("data") or {}).get("error") or {}
                                    err_code = err_obj.get("code","") if isinstance(err_obj, dict) else str(err_obj)
                                    err_msg  = err_obj.get("message","generation failed") if isinstance(err_obj, dict) else str(err_obj)
                                    poll_err = (
                                        "INSUFFICIENT_CREDIT — top up at heygen.com/pricing or use D-ID (free)."
                                        if "INSUFFICIENT_CREDIT" in err_code or "credit" in err_msg.lower()
                                        else f"HeyGen [{err_code}]: {err_msg}"
                                    ); break
                        except Exception as pe:
                            poll_err = str(pe)[:200]; break
                    progress_bar.progress(100)
                    if poll_err:
                        st.error(poll_err)
                    elif video_url:
                        st.session_state["narrator_result"] = {
                            "video_url": video_url, "video_id": video_id,
                            "script": script_text, "platform": "HeyGen",
                        }
                        st.success("Video ready!")
                    else:
                        st.warning(f"HeyGen did not complete within {max_wait}s. Check your HeyGen dashboard for video_id `{video_id}`.")
                        st.session_state["narrator_result"] = {
                            "video_id": video_id, "script": script_text, "platform": "HeyGen"
                        }

    # ── Result display ────────────────────────────────────────────────
    nr = st.session_state.get("narrator_result")
    if nr:
        st.markdown("---")
        st.markdown("**Result**")
        if nr.get("video_url"):
            r_cols = st.columns([2, 1])
            with r_cols[0]:
                st.video(nr["video_url"])
            with r_cols[1]:
                st.markdown("**Video Details**")
                st.markdown(f"- Video ID: `{nr.get('video_id','N/A')}`")
                badge_icon = "🆓" if "D-ID" in nr.get("platform","") else "🎬"
                st.markdown(f"- Platform: {badge_icon} {nr.get('platform','HeyGen')}")
                st.markdown(f"- Words: {len(safe_str(nr.get('script','')).split())}")
                st.markdown("")
                st.markdown(f"[Open in browser]({nr['video_url']})")
                st.download_button(
                    "📋 Copy Script",
                    data=safe_str(nr.get("script","")),
                    file_name="ECI_Narrator_Script_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt",
                    mime="text/plain",
                    key="dl_script",
                )
        elif nr.get("video_id"):
            st.info(
                f"Video is processing. Video ID: `{nr['video_id']}`\n\n"
                "Check your [HeyGen dashboard](https://app.heygen.com) for the completed video."
            )

    st.markdown("---")
    st.markdown(
        '<div style="background:rgba(0,212,170,.07);border:1px solid rgba(0,212,170,.2);'
        'border-radius:10px;padding:16px 20px;font-size:.8rem;color:#94a3b8;line-height:1.7">'
        '<strong style="color:#00d4aa">How it works</strong><br>'
        'Each proposal takes ~3 minutes end-to-end: AI writes the script from the live proposal data, '
        'ElevenLabs clones the architect\'s voice, and HeyGen/D-ID animates the avatar with '
        'frame-perfect lip-sync. The result is a polished presenter video you can embed directly '
        'in SharePoint, Teams notifications, or client email — with zero recording time from the architect.'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_3d_view_tab(ar, ce, r):
    """Render the 3D Architecture Fly-Through tab content."""
    import streamlit.components.v1 as _stcomp
    from datetime import datetime as _dt
    from .diagrams import generate_3d_flythrough_html

    st.info(
        "\U0001f4a1 Hover inside the 3D canvas to orbit/zoom. "
        "Scroll outside the canvas to navigate back to other tabs.",
        icon="\u2139\ufe0f",
    )

    # Pre-flight stats row
    arch = safe_dict(ar)
    components = safe_list(arch.get("components", []))
    data_flow = safe_list(arch.get("data_flow", []))
    tiers_used = set()
    _type_to_tier = {
        "web app": "presentation", "frontend": "presentation", "ui": "presentation",
        "cdn": "presentation", "portal": "presentation",
        "integration": "application", "microservices": "application", "api": "application",
        "messaging": "application", "backend": "application", "compute": "application",
        "function": "application", "logic": "application", "app service": "application",
        "database": "data", "storage": "data", "data": "data",
        "cache": "data", "redis": "data", "cosmos": "data", "sql": "data",
        "identity": "security", "security": "security",
        "auth": "security", "firewall": "security", "keyvault": "security",
        "key vault": "security",
        "operations": "operations", "devops": "operations",
        "monitoring": "operations", "logging": "operations", "insights": "operations",
    }
    for c in components:
        c = safe_dict(c)
        ctype = safe_str(c.get("type", "")).lower()
        tier = _type_to_tier.get(ctype)
        if tier is None:
            cname_lower = safe_str(c.get("name", "")).lower()
            for kw, t in _type_to_tier.items():
                if kw in cname_lower:
                    tier = t
                    break
        tiers_used.add(tier or "application")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("Components", len(components) or "Demo")
    with sc2:
        st.metric("Data Flows", max(len(data_flow) - 1, 0) if data_flow else 0)
    with sc3:
        st.metric("Tiers Used", len(tiers_used) if tiers_used else 5)

    st.markdown("---")

    # AI tour script generation
    if st.button("\U0001f399\ufe0f Generate Tour Script", key="btn_3d_narr"):
        with st.spinner("Generating AI narration for each component\u2026"):
            ai = _pick_ai_for("architecture")
            narr = _generate_3d_tour_script(r, ai)
            st.session_state["_3d_narration"] = narr
        if narr:
            st.success(
                f"Tour script generated for {len(narr)} component(s). "
                "Voice narration will play automatically during the fly-through."
            )
        else:
            st.warning("Could not generate tour script. Default narration will be used.")

    narr_map = st.session_state.get("_3d_narration", {})
    if narr_map:
        with st.expander("\U0001f4cb View Tour Script", expanded=False):
            for comp_name, text in narr_map.items():
                st.markdown(f"**{comp_name}**: {text}")

    flythrough_html = generate_3d_flythrough_html(ar, ce, narration_map=narr_map)

    if flythrough_html:
        _stcomp.html(flythrough_html, height=700, scrolling=False)

        st.markdown("---")
        ft_dl_cols = st.columns([2, 1])
        with ft_dl_cols[0]:
            st.markdown(
                "**Tip for client meetings:** Download the standalone HTML and open it in any browser "
                "for a full-screen, shareable experience \u2014 no installation required."
            )
        with ft_dl_cols[1]:
            st.download_button(
                "\U0001f4e5 Download 3D View (HTML)",
                data=flythrough_html.encode("utf-8"),
                file_name="ECI_3D_Architecture_" + _dt.now().strftime("%Y%m%d_%H%M%S") + ".html",
                mime="text/html",
                width="stretch",
                type="primary",
                key="dl_3d_html",
            )
    else:
        st.info("No architecture components found. Run the pipeline to generate the 3D view.")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 1: PRESALE
# ═══════════════════════════════════════════════════════════════════════

def tab_presale():
    # ── Revision mode — detect if user clicked "Revise" from Run Library ──────
    _rev_parent_id = st.session_state.get("_revision_parent_id")
    _rev_parent    = None
    _rev_parent_results = {}

    if _rev_parent_id:
        with st.spinner("Loading revision details…"):
            try:
                import sqlite3 as _sq
                from .database import _DB_PATH as _DBPATH
                _con = _sq.connect(_DBPATH); _con.row_factory = _sq.Row
                _row = _con.execute(
                    "SELECT id, client_name, project_type, total_hours, monthly_cost, "
                    "risk_level, risk_score, req_count, ts, version_number, "
                    "negotiation_stage, version_status "
                    "FROM proposals WHERE id=?", (_rev_parent_id,)
                ).fetchone()
                _con.close()
                if _row:
                    _rev_parent = dict(_row)
                    try:
                        _rev_parent_results = db_load_results(_rev_parent_id) or {}
                    except Exception:
                        pass
            except Exception:
                pass

    # ── Revision Banner ───────────────────────────────────────────────────────
    if _rev_parent:
        _vn   = _rev_parent.get("version_number", 1)
        _cln  = _rev_parent.get("client_name", "")
        _pt   = _rev_parent.get("project_type", "")
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a1040,#0d1f3c);border:1.5px solid #7b61ff;
             border-radius:12px;padding:18px 22px;margin-bottom:18px;display:flex;
             align-items:center;justify-content:space-between;gap:16px">
          <div>
            <div style="font-size:.75rem;color:#a78bfa;letter-spacing:.12em;text-transform:uppercase;margin-bottom:4px">
              ✏️ Revision Mode
            </div>
            <div style="font-size:1.05rem;font-weight:700;color:#e2e8f0">
              Revising V{_vn}: {_cln} — {_pt}
            </div>
            <div style="font-size:.78rem;color:#94a3b8;margin-top:4px">
              Upload revised scope, set revision details, then run estimation.
              Result saves as <strong style="color:#7b61ff">V{_vn+1}</strong> linked to this baseline.
            </div>
          </div>
          <div style="text-align:right">
            <div style="font-size:2rem;font-weight:800;color:#7b61ff;opacity:.35">V{_vn}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Revision metadata form
        _rm_c1, _rm_c2, _rm_c3 = st.columns(3)
        with _rm_c1:
            _REASON_TYPES = {
                "scope_reduction":    "📉 Scope Reduction",
                "scope_expansion":    "📈 Scope Expansion",
                "approach_change":    "🔄 Approach Change",
                "pricing_negotiation":"💰 Pricing Negotiation",
                "timeline_change":    "📅 Timeline Change",
                "team_change":        "👥 Team Change",
                "client_feedback":    "💬 Client Feedback",
                "other":              "📝 Other",
            }
            _reason = st.selectbox(
                "Revision Reason",
                list(_REASON_TYPES.keys()),
                format_func=lambda k: _REASON_TYPES.get(k, k),
                key="_rev_reason_type",
            )
        with _rm_c2:
            _NEG_STAGES = {
                "initial":     "1️⃣ Initial Proposal",
                "negotiation": "2️⃣ Negotiation",
                "bafo":        "3️⃣ Best & Final Offer",
                "closed_won":  "✅ Closed Won",
                "closed_lost": "❌ Closed Lost",
            }
            _neg_stage = st.selectbox(
                "Negotiation Stage",
                list(_NEG_STAGES.keys()),
                format_func=lambda k: _NEG_STAGES.get(k, k),
                index=list(_NEG_STAGES.keys()).index(
                    _rev_parent.get("negotiation_stage", "initial")
                    if _rev_parent.get("negotiation_stage") in _NEG_STAGES else "initial"
                ),
                key="_rev_neg_stage",
            )
        with _rm_c3:
            _VER_STATUS = {
                "draft":     "📝 Draft (Internal)",
                "submitted": "📤 Submitted to Client",
                "bafo":      "🏆 BAFO",
                "internal":  "🔒 Internal Only",
            }
            _ver_status = st.selectbox(
                "Version Status",
                list(_VER_STATUS.keys()),
                format_func=lambda k: _VER_STATUS.get(k, k),
                key="_rev_ver_status",
            )

        _rev_notes = st.text_area(
            "Revision Notes / Negotiation Context",
            placeholder="e.g. Client pushed back on timeline. Removed Phase 3 to reduce cost by 20%...",
            key="_rev_notes",
            height=80,
        )
        # Competitor context hidden for now (kept in session state for DB save)
        st.session_state.setdefault("_rev_competitor_ctx", "")

        # Pre-fill client name from parent
        if not st.session_state.get("client_name") and _cln:
            st.session_state["client_name"]          = _cln
            st.session_state["proposal_client_name"] = _cln

        # ── Margin floor warning ──────────────────────────────────────
        try:
            _p_cost = int(_rev_parent.get("monthly_cost") or 0)
            if _p_cost > 0:
                _floor_pct = 80  # warn if new version might drop below 80% of V1
                _floor_val = int(_p_cost * _floor_pct / 100)
                st.markdown(
                    f'<div style="background:#7c2d1222;border:1px solid #f8717144;'
                    f'border-radius:8px;padding:10px 14px;margin-bottom:12px;'
                    f'font-size:.8rem;color:#fca5a5">'
                    f'⚠️ <strong>Margin floor:</strong> V{_vn} baseline is '
                    f'<strong>${_p_cost:,}/mo</strong>. '
                    f'If this revision drops below <strong>${_floor_val:,}/mo</strong> '
                    f'({_floor_pct}% of baseline), flag for pricing review.</div>',
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        # ── Parking lot — defer requirements ─────────────────────────
        if _rev_parent_results:
            try:
                _parent_reqs = safe_list(
                    safe_dict(_rev_parent_results.get("semantic_analysis")).get("requirements", [])
                )
                if _parent_reqs:
                    with st.expander(f"🅿️ Parking Lot — defer requirements from V{_vn} ({len(_parent_reqs)} total)", expanded=False):
                        st.caption("Check any requirements the client agreed to defer to a later phase. These will be saved to the parking lot and shown in the delta view.")
                        # Load previously saved parking lot for this parent
                        with st.spinner("Loading requirements…"):
                            try:
                                import sqlite3 as _sq2
                                from .database import _DB_PATH as _DBPATH2
                                _con2 = _sq2.connect(_DBPATH2); _con2.row_factory = _sq2.Row
                                _pl_row = _con2.execute("SELECT parking_lot FROM proposals WHERE id=?", (_rev_parent_id,)).fetchone()
                                _con2.close()
                                _existing_lot = json.loads((_pl_row["parking_lot"] if _pl_row else None) or "[]")
                            except Exception:
                                _existing_lot = []
                        _existing_lot_lc = {str(x).strip().lower() for x in _existing_lot}

                        _parked = []
                        for _pr in _parent_reqs:
                            _pr_title = safe_str(_pr.get("title","") if isinstance(_pr, dict) else str(_pr))
                            _pr_type  = safe_str(_pr.get("type","")  if isinstance(_pr, dict) else "")
                            _pr_cx    = safe_str(_pr.get("complexity","") if isinstance(_pr, dict) else "")
                            _cx_col   = {"high":"#f87171","medium":"#ffd166","low":"#4ade80"}.get(_pr_cx.lower(),"#94a3b8")
                            _key      = f"_lot_{hash(_pr_title) & 0xFFFFFF}"
                            _default  = _pr_title.strip().lower() in _existing_lot_lc
                            _checked  = st.checkbox(
                                f"{_pr_title}",
                                value=_default,
                                key=_key,
                                help=f"Type: {_pr_type}  ·  Complexity: {_pr_cx}",
                            )
                            if _checked:
                                _parked.append(_pr_title)
                        if _parked:
                            st.markdown(
                                f'<div style="font-size:.78rem;color:#a78bfa;margin-top:6px">'
                                f'🅿️ {len(_parked)} requirement{"s" if len(_parked)!=1 else ""} will be parked</div>',
                                unsafe_allow_html=True,
                            )
                        st.session_state["_rev_parking_lot"] = _parked
            except Exception:
                pass

        # Cancel button
        if st.button("✖ Cancel Revision", key="_cancel_revision", type="secondary"):
            st.session_state.pop("_revision_parent_id", None)
            st.session_state.pop("_rev_reason_type", None)
            st.session_state.pop("_rev_neg_stage", None)
            st.session_state.pop("_rev_ver_status", None)
            st.session_state.pop("_rev_notes", None)
            st.session_state.pop("_rev_competitor_ctx", None)
            st.session_state.pop("_rev_parking_lot", None)
            st.rerun()

        st.markdown("---")

    # _home_stats_banner()  # hidden
    _shdr_label = "📄 Upload Revised Scope Document" if _rev_parent else "📄 Document Ingestion"
    st.markdown(f'<div class="shdr"><span class="shdr-i">{"✏️" if _rev_parent else "📄"}</span> {_shdr_label.split(" ",1)[1]}</div>', unsafe_allow_html=True)

    # ── Client name + Engagement Type + Project Type ─────────────────────
    _cn_col, _et_col, _pt_col = st.columns([1.5, 2, 2])
    with _cn_col:
        _cn_default = (
            st.session_state.get("client_name")
            or st.session_state.get("proposal_client_name")
            or ""
        )
        _client_name = st.text_input(
            "Client Name",
            value=_cn_default,
            placeholder="e.g. Acme Corp",
            key="_client_name_input",
        )
        if _client_name:
            st.session_state["client_name"]          = _client_name
            st.session_state["proposal_client_name"] = _client_name

    with _et_col:
        _et_opts = ["Implementation", "Discovery", "Discovery + Build"]
        _et_default = st.session_state.get("engagement_type", "Implementation")
        _et_idx = _et_opts.index(_et_default) if _et_default in _et_opts else 0
        _engagement = st.radio(
            "Engagement Type",
            _et_opts,
            index=_et_idx,
            horizontal=True,
            key="_engagement_type_radio",
            help="Discovery = workshops + architecture only. Implementation = full build. Discovery + Build = both phases.",
        )
        st.session_state["engagement_type"] = _engagement

    with _pt_col:
        _PT_BASE = ["AI", "Data", "SharePoint", "Cloud", "Custom App"]
        _pt_default = st.session_state.get("project_type_tags", [])
        _project_type_tags = st.multiselect(
            "Project Type",
            _PT_BASE,
            default=_pt_default,
            key="_project_type_tags_ms",
            help=(
                "Select one or more types — combinations are supported (e.g. AI + Data, AI + SharePoint). "
                "This scopes training instructions and guides effort estimation."
            ),
        )
        st.session_state["project_type_tags"] = _project_type_tags

    # ── Instruction box ───────────────────────────────────────────────────
    _ri_col, _ri_btn_col = st.columns([5, 1])
    with _ri_col:
        _run_instr_default = st.session_state.get("run_instruction", "")
        _run_instruction = st.text_area(
            "📝 Additional Instructions for this Estimation",
            value=_run_instr_default,
            placeholder=(
                "e.g. This is a fixed-price engagement. Focus on Azure-native services only. "
                "Client has offshore delivery preference. Do not include front-end development. "
                "Budget ceiling is $150k. Delivery must complete within 3 months."
            ),
            key="_run_instruction_input",
            height=70,
            help=(
                "Passed to every AI agent for this run only — highest priority. "
                "For rules that should apply to ALL future runs, use the Training tab instead."
            ),
        )
        st.session_state["run_instruction"] = _run_instruction
    with _ri_btn_col:
        st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
        if st.button(
            "💾 Save to Training",
            key="_save_run_instr_btn",
            help="Save this instruction permanently to Agent Training (applies to all future runs)",
            disabled=not (st.session_state.get("run_instruction", "")).strip(),
        ):
            try:
                from .training import add_instruction as _add_ti
                _ti_tags = st.session_state.get("project_type_tags", [])
                _ti_id = _add_ti(
                    st.session_state["run_instruction"].strip(),
                    category="general",
                    created_by="admin",
                    project_types=_ti_tags,
                )
                st.success(f"Saved as training instruction #{_ti_id}")
            except Exception as _ti_err:
                st.error(f"Could not save: {_ti_err}")

    uc, tc = st.columns([3, 2])
    with uc:
        _upload_hint = "Upload REVISED scope document" if _rev_parent else "Upload Scope Documents"
        st.markdown(f'<div class="crd"><div class="crd-t">{_upload_hint}</div><div class="crd-d">PDF, DOCX, XLSX, PPTX, TXT, CSV</div>', unsafe_allow_html=True)
        files = st.file_uploader("Drop files", type=["pdf", "docx", "xlsx", "pptx", "txt", "csv"], accept_multiple_files=True, key="fu", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
    with tc:
        pass  # SharePoint Auto-Trigger hidden

    if not files and not st.session_state.processing_results:
        _empty_upload()

    if files:
        st.markdown("---")
        _render_completeness_checker(files)

    # ── Multimodal Discovery — HIDDEN (remove `if False:` block to re-enable) ──
    if False:  # noqa
        st.markdown("---")
        st.markdown('<div class="shdr"><span class="shdr-i">🎙️</span> Multimodal Discovery Extraction</div>', unsafe_allow_html=True)
        st.markdown('<div class="crd"><div class="crd-t">Upload Meeting Transcripts & Voice Notes</div><div class="crd-d">Extract requirements, pain points, stakeholders & auto-generate WBS from Zoom/Teams transcripts, voice memos, or meeting notes.</div>', unsafe_allow_html=True)
        disc_col1, disc_col2 = st.columns([3, 2])
        with disc_col1:
            disc_files = st.file_uploader(
                "Upload transcripts",
                type=["txt", "srt", "vtt", "json", "docx", "csv"],
                accept_multiple_files=True,
                key="disc_fu",
                label_visibility="collapsed",
                help="Supported: TXT, SRT, VTT (subtitles), JSON (Teams/Zoom/Otter.ai exports), DOCX (meeting notes), CSV",
            )
        with disc_col2:
            st.markdown("**Supported Formats:**")
            st.markdown("- `.txt` `.srt` `.vtt` — Subtitle / transcript files")
            st.markdown("- `.json` — Teams, Zoom exports")
            st.markdown("- `.docx` — Meeting notes / minutes")
            st.markdown("- `.csv` — Tabular transcript exports")
        st.markdown("</div>", unsafe_allow_html=True)

        if disc_files:
            _, dbc, _ = st.columns([1, 2, 1])
            with dbc:
                if st.button("🎙️ ANALYZE TRANSCRIPTS & GENERATE WBS", width="stretch", type="primary", key="disc_go"):
                    st.session_state["_az_err_shown"] = False
                    ai = _pick_ai_for("discovery")
                    dpb = st.progress(0)
                    dstatus = st.empty()
                    dstatus.markdown("**1/3** Extracting transcripts...")
                    dpb.progress(10)
                    all_text = ""
                    for df in disc_files:
                        all_text += extract_audio_transcript(df) + "\n\n"
                    st.session_state.discovery_transcript = all_text
                    dstatus.markdown("**2/3** Analyzing content & extracting insights...")
                    dpb.progress(50)
                    disc_result = ai.analyze_transcript(all_text)
                    _log_act("discovery_run", "Ran transcript discovery analysis", "Pipeline")
                    dstatus.markdown("**3/3** Generating Work Breakdown Structure...")
                    dpb.progress(90)
                    st.session_state.discovery_results = disc_result
                    dpb.progress(100)
                    dstatus.markdown("**Done!** Discovery analysis complete.")
                    time.sleep(0.5)
                    dstatus.empty()
                    dpb.empty()
                    st.rerun()

        # ── Discovery Results ──
        if st.session_state.discovery_results:
            dr = st.session_state.discovery_results
            st.markdown("---")
            st.markdown('<div class="shdr"><span class="shdr-i">📋</span> Discovery Insights</div>', unsafe_allow_html=True)

            st.markdown('<div class="crd">', unsafe_allow_html=True)
            st.markdown("**Meeting Summary:** " + safe_str(dr.get("meeting_summary")))
            st.markdown("**Sentiment:** " + safe_str(dr.get("sentiment")))
            themes = safe_list(dr.get("key_themes"))
            if themes:
                tags_html = " ".join('<span class="tt">' + safe_str(t) + '</span>' for t in themes)
                st.markdown('<div class="ttag">' + tags_html + '</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            disc_tabs = st.tabs(["🔥 Pain Points", "📝 Requirements", "👥 Stakeholders", "📊 WBS", "✅ Action Items"])

            with disc_tabs[0]:
                for pp in safe_list(dr.get("pain_points")):
                    pp = safe_dict(pp)
                    sev = safe_str(pp.get("severity"))
                    sc = "#ff6b6b" if sev == "High" else "#ffd166" if sev == "Medium" else "#06d6a0"
                    st.markdown(
                        '<div class="rc" style="border-left:3px solid ' + sc + ';">'
                        '<div class="rch2"><strong>' + safe_str(pp.get("issue")) + '</strong>'
                        '<span class="rsev" style="color:' + sc + ';">' + sev + '</span></div>'
                        '<p style="font-style:italic;color:var(--t2);">"' + safe_str(pp.get("quote")) + '"</p>'
                        '<div class="rmit"><strong>Stakeholder:</strong> ' + safe_str(pp.get("stakeholder")) + '</div>'
                        '</div>', unsafe_allow_html=True
                    )

            with disc_tabs[1]:
                reqs = safe_list(dr.get("requirements_extracted"))
                fn_r = [x for x in reqs if isinstance(x, dict) and x.get("type") == "functional"]
                nf_r = [x for x in reqs if isinstance(x, dict) and x.get("type") == "non-functional"]
                ig_r = [x for x in reqs if isinstance(x, dict) and x.get("type") == "integration"]
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    st.markdown('<div class="rch fn">Functional (' + str(len(fn_r)) + ')</div>', unsafe_allow_html=True)
                    for q in fn_r:
                        q = safe_dict(q)
                        st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><p>' + safe_str(q.get("description")) + '</p><div class="ri-c">Source: ' + safe_str(q.get("source")) + '</div></div>', unsafe_allow_html=True)
                with rc2:
                    st.markdown('<div class="rch nf">Non-Functional (' + str(len(nf_r)) + ')</div>', unsafe_allow_html=True)
                    for q in nf_r:
                        q = safe_dict(q)
                        st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><p>' + safe_str(q.get("description")) + '</p><div class="ri-c">Source: ' + safe_str(q.get("source")) + '</div></div>', unsafe_allow_html=True)
                with rc3:
                    st.markdown('<div class="rch ig">Integration (' + str(len(ig_r)) + ')</div>', unsafe_allow_html=True)
                    for q in ig_r:
                        q = safe_dict(q)
                        st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><p>' + safe_str(q.get("description")) + '</p><div class="ri-c">Source: ' + safe_str(q.get("source")) + '</div></div>', unsafe_allow_html=True)

            with disc_tabs[2]:
                stake_cols = st.columns(2)
                for i, sh in enumerate(safe_list(dr.get("stakeholders"))):
                    sh = safe_dict(sh)
                    with stake_cols[i % 2]:
                        concerns = "".join("<li>" + safe_str(c) + "</li>" for c in safe_list(sh.get("concerns")))
                        st.markdown(
                            '<div class="crd"><div class="crd-t">👤 ' + safe_str(sh.get("name")) + '</div>'
                            '<div class="crd-d" style="color:var(--c2);">' + safe_str(sh.get("role")) + '</div>'
                            '<ul style="color:var(--t2);font-size:.85rem;">' + concerns + '</ul></div>',
                            unsafe_allow_html=True
                        )

            with disc_tabs[3]:
                st.markdown("**Work Breakdown Structure**")
                wbs = safe_list(dr.get("wbs"))
                for phase_idx, phase in enumerate(wbs):
                    phase = safe_dict(phase)
                    phase_name = safe_str(phase.get("phase"))
                    with st.expander("📁 " + str(phase_idx + 1) + ". " + phase_name, expanded=True):
                        for d in safe_list(phase.get("deliverables")):
                            d = safe_dict(d)
                            st.markdown("**📦 " + safe_str(d.get("name")) + "**")
                            for t in safe_list(d.get("tasks")):
                                t = safe_dict(t)
                                st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;🔹 " + safe_str(t.get("name")) + " — _" + safe_str(t.get("effort")) + "_")
                decisions = safe_list(dr.get("decisions"))
                if decisions:
                    st.markdown("---")
                    st.markdown("**Key Decisions:**")
                    for dec in decisions:
                        st.markdown("- ✅ " + safe_str(dec))

            with disc_tabs[4]:
                for ai_item in safe_list(dr.get("action_items")):
                    ai_item = safe_dict(ai_item)
                    pri = safe_str(ai_item.get("priority"))
                    pc = "#ff6b6b" if pri == "High" else "#ffd166" if pri == "Medium" else "#06d6a0"
                    st.markdown(
                        '<div class="rc" style="border-left:3px solid ' + pc + ';">'
                        '<div class="rch2"><strong>' + safe_str(ai_item.get("item")) + '</strong>'
                        '<span class="rsev" style="color:' + pc + ';">' + pri + '</span></div>'
                        '<div class="rmit"><strong>Owner:</strong> ' + safe_str(ai_item.get("owner")) + '</div>'
                        '</div>', unsafe_allow_html=True
                    )

            st.markdown("---")
            dl_disc_cols = st.columns(2)
            with dl_disc_cols[0]:
                st.download_button(
                    "📥 Download Discovery Report (JSON)",
                    data=json.dumps(dr, indent=2, default=str),
                    file_name="ECI_Discovery_Report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json",
                    mime="application/json",
                    width="stretch", key="dl_disc_json",
                )
            with dl_disc_cols[1]:
                if st.session_state.discovery_transcript:
                    st.download_button(
                        "📥 Download Cleaned Transcript (TXT)",
                        data=st.session_state.discovery_transcript,
                        file_name="ECI_Transcript_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt",
                        mime="text/plain",
                        width="stretch", key="dl_disc_txt",
                    )

            # ── Full 11-agent pipeline from transcript ──────────────────
            if st.session_state.discovery_transcript:
                st.markdown("---")
                st.markdown(
                    '<div style="background:linear-gradient(135deg,#0d1627,#13072e);'
                    'border:1.5px solid #7c3aed;border-radius:14px;padding:18px 22px;margin-bottom:12px;">'
                    '<div style="font-size:1rem;font-weight:800;color:#a78bfa;margin-bottom:4px;">'
                    '🚀 Generate Full Proposal from Transcript</div>'
                    '<div style="font-size:.82rem;color:#64748b;line-height:1.6;">'
                    'Run the complete 11-agent pipeline — the same analysis you get from a scope document. '
                    'Produces time estimates, cost models, risk assessment, architecture design, '
                    'scope of work, and a full proposal document — all from the transcript above.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                _, _fc, _ = st.columns([1, 2, 1])
                with _fc:
                    if st.button(
                        "🚀 RUN FULL 11-AGENT ANALYSIS FROM TRANSCRIPT",
                        width="stretch", type="primary",
                        key="disc_full_pipeline",
                    ):
                        _disc_src = ", ".join(
                            getattr(f, "name", "transcript") for f in (disc_files or [])
                        ) or "Discovery Transcript"
                        run_pipeline(
                            [],
                            pre_extracted_text=st.session_state.discovery_transcript,
                            source_label=_disc_src,
                        )
                        return

    if st.session_state.processing_results:
        # ── Delta view after revision re-run ────────────────────────────────
        _rv_parent = st.session_state.get("_revision_completed_parent")
        _rv_child  = st.session_state.get("_revision_completed_child")
        if _rv_parent and _rv_child:
            with st.spinner("Calculating version delta…"):
                _render_revision_delta(_rv_parent, _rv_child)
        show_results()


def _render_revision_delta(parent_id: int, child_id: int):
    """Render a side-by-side delta comparison card between two proposal versions,
    including a requirements diff (added / removed / kept)."""
    try:
        import sqlite3 as _sq
        from .database import _DB_PATH as _DBPATH
        _con = _sq.connect(_DBPATH); _con.row_factory = _sq.Row
        _p = dict(_con.execute(
            "SELECT client_name, project_type, total_hours, monthly_cost, annual_cost, "
            "risk_score, req_count, duration_weeks, version_number, "
            "revision_reason_type, revision_notes, negotiation_stage, results_json, parking_lot "
            "FROM proposals WHERE id=?", (parent_id,)
        ).fetchone() or {})
        _c = dict(_con.execute(
            "SELECT client_name, project_type, total_hours, monthly_cost, annual_cost, "
            "risk_score, req_count, duration_weeks, version_number, "
            "revision_reason_type, revision_notes, negotiation_stage, results_json, parking_lot "
            "FROM proposals WHERE id=?", (child_id,)
        ).fetchone() or {})
        _con.close()
        if not _p or not _c:
            return
    except Exception:
        return

    # ── Extract requirements from each version ───────────────────────────
    def _get_reqs(row: dict) -> list:
        try:
            rj = json.loads(row.get("results_json") or "{}")
            return safe_list(safe_dict(rj.get("semantic_analysis")).get("requirements", []))
        except Exception:
            return []

    def _req_key(r) -> str:
        return safe_str(r.get("title", "")).strip().lower() if isinstance(r, dict) else str(r).lower()

    _p_reqs  = _get_reqs(_p)
    _c_reqs  = _get_reqs(_c)
    _p_titles = {_req_key(r): r for r in _p_reqs if _req_key(r)}
    _c_titles = {_req_key(r): r for r in _c_reqs if _req_key(r)}

    # Parking lot titles from parent (those that were deferred last time)
    try:
        _p_lot = json.loads(_p.get("parking_lot") or "[]")
    except Exception:
        _p_lot = []
    _p_lot_keys = {str(x).strip().lower() for x in _p_lot if x}

    _kept   = [r for k, r in _c_titles.items() if k in _p_titles]
    _added  = [r for k, r in _c_titles.items() if k not in _p_titles]
    _removed = [r for k, r in _p_titles.items() if k not in _c_titles]

    def _delta_html(label: str, old_val, new_val, fmt: str = "{}",
                    lower_is_better: bool = False):
        """Return a single delta row HTML."""
        try:
            diff    = float(new_val) - float(old_val)
            pct     = (diff / float(old_val) * 100) if float(old_val) != 0 else 0
            up      = diff > 0
            is_good = (up and not lower_is_better) or (not up and lower_is_better)
            arrow   = "▲" if up else "▼"
            col     = "#4ade80" if is_good else "#f87171"
            pct_str = f"{arrow} {abs(pct):.1f}%"
            old_s   = fmt.format(int(old_val))
            new_s   = fmt.format(int(new_val))
            diff_block = (
                f'<span style="color:{col};font-size:.78rem;margin-left:8px">'
                f'{pct_str}</span>'
            )
        except Exception:
            old_s, new_s, diff_block = str(old_val), str(new_val), ""
        return (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:8px 0;border-bottom:1px solid #1e2a3a">'
            f'  <div style="font-size:.82rem;color:#94a3b8">{label}</div>'
            f'  <div style="text-align:right">'
            f'    <span style="color:#64748b;font-size:.8rem;text-decoration:line-through">{old_s}</span>'
            f'    <span style="color:#e2e8f0;font-weight:700;margin-left:8px">{new_s}</span>'
            f'    {diff_block}'
            f'  </div>'
            f'</div>'
        )

    _pv = _p.get("version_number", 1)
    _cv = _c.get("version_number", _pv + 1)
    _REASON_LABELS = {
        "scope_reduction": "Scope Reduction", "scope_expansion": "Scope Expansion",
        "approach_change": "Approach Change", "pricing_negotiation": "Pricing Negotiation",
        "timeline_change": "Timeline Change", "team_change": "Team Change",
        "client_feedback": "Client Feedback", "other": "Other",
    }
    _NEG_LABELS = {
        "initial": "Initial", "negotiation": "Negotiation",
        "bafo": "BAFO", "closed_won": "Closed Won", "closed_lost": "Closed Lost",
    }
    _reason_lbl = _REASON_LABELS.get(_c.get("revision_reason_type",""), _c.get("revision_reason_type",""))
    _stage_lbl  = _NEG_LABELS.get(_c.get("negotiation_stage",""), _c.get("negotiation_stage",""))

    _rows_html = (
        _delta_html("Total Hours",      _p["total_hours"], _c["total_hours"],    "{:,}h",  lower_is_better=True)
        + _delta_html("Monthly Cost",   _p["monthly_cost"], _c["monthly_cost"], "${:,}",   lower_is_better=True)
        + _delta_html("Annual Cost",    _p["annual_cost"],  _c["annual_cost"],  "${:,}",   lower_is_better=True)
        + _delta_html("Risk Score",     _p["risk_score"],   _c["risk_score"],   "{}/10",   lower_is_better=True)
        + _delta_html("Requirements",   _p["req_count"],    _c["req_count"],    "{} reqs", lower_is_better=False)
    )
    _notes_html = (
        f'<div style="font-size:.78rem;color:#a78bfa;margin-top:12px;padding-top:10px;'
        f'border-top:1px solid #1e2a3a">'
        f'📝 {_c.get("revision_notes","")}'
        f'</div>'
    ) if _c.get("revision_notes") else ""

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1120,#131929);border:1.5px solid #7b61ff55;
         border-radius:14px;padding:20px 24px;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
        <div style="font-size:1.5rem">🔀</div>
        <div>
          <div style="font-size:.72rem;color:#a78bfa;letter-spacing:.12em;text-transform:uppercase">Version Delta</div>
          <div style="font-size:1rem;font-weight:700;color:#e2e8f0">
            V{_pv} → V{_cv} · {_c.get("client_name","")} — {_c.get("project_type","")}
          </div>
        </div>
        <div style="margin-left:auto;display:flex;gap:8px">
          <span style="background:#1e1040;border:1px solid #7b61ff44;border-radius:6px;
                padding:3px 10px;font-size:.72rem;color:#a78bfa">{_reason_lbl or "Revision"}</span>
          <span style="background:#0a1f2e;border:1px solid #00b4d844;border-radius:6px;
                padding:3px 10px;font-size:.72rem;color:#00b4d8">{_stage_lbl}</span>
        </div>
      </div>
      {_rows_html}
      {_notes_html}
    </div>
    """, unsafe_allow_html=True)

    # ── Requirements diff expander ───────────────────────────────────────
    if _p_reqs or _c_reqs:
        _diff_label = (
            f"📋 Requirements Diff — "
            f"{'↑' if len(_added) else ''}{'↓' if len(_removed) else ''} "
            f"{len(_added)} added · {len(_removed)} removed · {len(_kept)} kept"
        )
        with st.expander(_diff_label, expanded=(len(_added) > 0 or len(_removed) > 0)):
            # Summary pills
            _pill = lambda txt, col, bg: (
                f'<span style="background:{bg};color:{col};border:1px solid {col}44;'
                f'border-radius:12px;padding:3px 10px;font-size:.75rem;font-weight:600;margin-right:6px">'
                f'{txt}</span>'
            )
            st.markdown(
                _pill(f"✅ {len(_kept)} kept",   "#4ade80","#4ade8012")
                + _pill(f"➕ {len(_added)} added",  "#00d4aa","#00d4aa12")
                + _pill(f"➖ {len(_removed)} removed","#f87171","#f8717112"),
                unsafe_allow_html=True,
            )
            st.markdown("")

            def _req_pill(r, badge_col, badge_bg, icon):
                _t  = safe_str(r.get("title","") if isinstance(r,dict) else str(r))
                _tp = safe_str(r.get("type","")  if isinstance(r,dict) else "")
                _cx = safe_str(r.get("complexity","") if isinstance(r,dict) else "")
                _cx_col = {"high":"#f87171","medium":"#ffd166","low":"#4ade80"}.get(_cx.lower(),"#94a3b8")
                return (
                    f'<div style="background:{badge_bg};border-left:3px solid {badge_col};'
                    f'border-radius:0 6px 6px 0;padding:6px 10px;margin-bottom:5px">'
                    f'  <span style="color:{badge_col};font-weight:700;margin-right:6px">{icon}</span>'
                    f'  <span style="color:#e2e8f0;font-size:.82rem">{_t}</span>'
                    + (f'  <span style="color:#64748b;font-size:.7rem;margin-left:8px">{_tp}</span>' if _tp else "")
                    + (f'  <span style="color:{_cx_col};font-size:.7rem;margin-left:6px">● {_cx}</span>' if _cx else "")
                    + f'</div>'
                )

            rc1, rc2 = st.columns(2)
            with rc1:
                if _added:
                    st.markdown("**Added in this version**")
                    st.markdown(
                        "".join(_req_pill(r, "#00d4aa", "#00d4aa0a", "➕") for r in _added),
                        unsafe_allow_html=True,
                    )
            with rc2:
                if _removed:
                    st.markdown("**Removed from previous version**")
                    st.markdown(
                        "".join(_req_pill(r, "#f87171", "#f871710a", "➖") for r in _removed),
                        unsafe_allow_html=True,
                    )
            if _kept and st.checkbox("Show kept requirements", key=f"_delta_kept_{child_id}"):
                st.markdown("**Carried forward unchanged**")
                st.markdown(
                    "".join(_req_pill(r, "#4ade80", "#4ade800a", "✓") for r in _kept),
                    unsafe_allow_html=True,
                )
    st.markdown("")


_MODEL_CLASSES = {
    "azure":       AzureAI,
    "claude":      AnthropicAI,
    "claude_opus": AnthropicAI,
    "codex":       CodexAI,
    "deepseek":    DeepSeekAI,
    "gemini":      GeminiAI,
    "grok":        GrokAI,
    "nano":        NanoAI,
    "qwen":        QwenAI,
    "vertex":      VertexAnthropicAI,
}


def _pick_ai_for(feature: str = "default"):
    """Return a live AI client for the given feature, using config.yaml routing.

    Falls back through all available providers if the configured one isn't live.
    """
    model_key = get_model_for_feature(feature)
    # claude_opus uses a dedicated factory to load Opus session keys
    if model_key == "claude_opus":
        client = AnthropicAI.opus_from_session()
        if client and client.is_live:
            return client
    else:
        cls = _MODEL_CLASSES.get(model_key)
        if cls:
            client = cls.from_session()
            if client and client.is_live:
                return client
    # Fallback: try any live client
    for _key, _cls in _MODEL_CLASSES.items():
        if _key == "claude_opus":
            c = AnthropicAI.opus_from_session()
        else:
            c = _cls.from_session()
        if c and c.is_live:
            return c
    return AzureAI.from_session()


def _pick_ai():
    """Legacy wrapper — uses default routing."""
    return _pick_ai_for("default")


def _ai_chat(system: str, messages: list) -> str:
    """Run a free-form conversational AI call; returns plain text.

    Uses the provider configured for the 'chat' feature in config.yaml routing,
    then falls back through all available providers.
    messages: list of {"role": "user"|"assistant", "content": str}
    """
    history = "\n".join(
        ("User" if m["role"] == "user" else "Assistant") + ": " + m["content"]
        for m in messages[:-1]
    )
    last_msg = messages[-1]["content"] if messages else ""
    full_user = ((f"Conversation history:\n{history}\n\n") if history else "") + f"User: {last_msg}"

    # Build ordered provider list: chat-routed first, then remaining
    chat_key = get_model_for_feature("chat")
    _order = [chat_key] + [k for k in ["claude_opus", "claude", "gemini", "qwen", "vertex", "azure"] if k != chat_key]

    for _key in _order:
        if _key == "claude_opus":
            ant = AnthropicAI.opus_from_session()
            if ant.is_live:
                result = ant._call(system, full_user, max_tokens=1024)
                if result is not None:
                    return result if isinstance(result, str) else json.dumps(result, indent=2)
        elif _key in ("claude",):
            ant = AnthropicAI.from_session()
            if ant.is_live:
                result = ant._call(system, full_user, max_tokens=1024)
                if result is not None:
                    return result if isinstance(result, str) else json.dumps(result, indent=2)
        elif _key == "gemini":
            gm = GeminiAI.from_session()
            if gm.is_live:
                txt = gm._call_text(system, full_user, max_tokens=1024)
                if txt:
                    return txt
        elif _key == "deepseek":
            ds = DeepSeekAI.from_session()
            if ds.is_live:
                txt = ds._call_text(system, full_user, max_tokens=1024)
                if txt:
                    return txt
        elif _key == "grok":
            gk = GrokAI.from_session()
            if gk.is_live:
                txt = gk._call_text(system, full_user, max_tokens=1024)
                if txt:
                    return txt
        elif _key == "qwen":
            qw = QwenAI.from_session()
            if qw.is_live:
                txt = qw._call_text(system, full_user, max_tokens=1024)
                if txt:
                    return txt
        elif _key == "vertex":
            vx = VertexAnthropicAI.from_session()
            if vx.is_live:
                txt = vx.call_raw_text(system, full_user, max_tokens=1024)
                if txt:
                    return txt
        elif _key == "azure":
            az = AzureAI.from_session()
            if az.is_live and az._client:
                try:
                    resp = az._client.chat.completions.create(
                        model=az.deployment,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": full_user}],
                        **az._token_kwargs(1024),
                        temperature=0.4,
                    )
                    return resp.choices[0].message.content
                except Exception as e:
                    return f"AI error: {str(e)[:200]}"

    return (
        "No AI model is configured. Fill in `config.yaml` with at least one "
        "provider (Azure, Claude, Gemini, Qwen, or Vertex) to enable Proposal Chat."
    )


def _run_scope_validation(se: dict, doc_text: str) -> dict:
    """Call AI to validate scope completeness. Returns structured gaps report. Cached per run."""
    _cache_key = "scope_validation_result"
    if st.session_state.get(_cache_key):
        return st.session_state[_cache_key]

    ai = _pick_ai_for("default")
    reqs    = safe_list(se.get("requirements", []))
    tech    = safe_list(se.get("technology_stack", []))
    domains = safe_list(se.get("project_domains", []))
    proj    = safe_str(se.get("project_type", ""))
    client  = safe_str(se.get("client_name", ""))

    req_summary = "\n".join(
        f'- [{r.get("type","?")}] {r.get("title","")}: {r.get("description","")[:120]}'
        for r in reqs[:30] if isinstance(r, dict)
    )
    system_prompt = (
        "You are a senior IT presales consultant at ECI reviewing a client scope document. "
        "Your job is to identify gaps and ambiguities BEFORE the team commits to an estimate. "
        "Be specific, practical, and professional. Every question you generate must be ready to send to the client in an email.\n\n"
        "Return ONLY valid JSON with this exact structure:\n"
        "{\n"
        '  "completeness_score": int (0-100, based on how complete and unambiguous the scope is),\n'
        '  "summary": "one-line summary of the scope quality",\n'
        '  "blockers": [\n'
        '    {"category": str, "issue": str, "impact": str, "question": str}\n'
        '  ],\n'
        '  "assumptions": [\n'
        '    {"category": str, "assumption": str, "impact": str, "question": str}\n'
        '  ],\n'
        '  "confirmed": [\n'
        '    {"category": str, "detail": str}\n'
        '  ],\n'
        '  "email_subject": str,\n'
        '  "email_body": str\n'
        "}\n\n"
        "BLOCKERS = critical unknowns that create high estimation risk. Must clarify before committing.\n"
        "ASSUMPTIONS = gaps where you had to assume something. State what you assumed and the cost impact if wrong.\n"
        "CONFIRMED = things clearly and unambiguously stated in the document.\n"
        "The email_body should be a professional, ready-to-send client email with all clarification questions numbered."
    )
    user_prompt = (
        f"Project: {proj} | Client: {client}\n"
        f"Tech stack: {', '.join(tech[:15])}\n"
        f"Domains: {', '.join(domains)}\n\n"
        f"Extracted requirements ({len(reqs)} total):\n{req_summary}\n\n"
        f"Original document excerpt (first 8000 chars):\n{doc_text[:8000]}"
    )
    try:
        result = ai._call(system_prompt, user_prompt)
        if isinstance(result, dict) and "completeness_score" in result:
            st.session_state[_cache_key] = result
            return result
    except Exception:
        pass

    # Fallback — minimal structure so UI doesn't crash
    fallback = {
        "completeness_score": 60,
        "summary": "Scope partially defined — some gaps require client clarification.",
        "blockers": [],
        "assumptions": [{"category": "General", "assumption": "Scope appears sufficient for initial estimate", "impact": "Low", "question": ""}],
        "confirmed": [{"category": "Requirements", "detail": f"{len(reqs)} requirements extracted from document"}],
        "email_subject": f"Clarification Required — {proj or 'Project'} Scope Review",
        "email_body": "Please review the attached scope document and provide clarification on any open items.",
    }
    st.session_state[_cache_key] = fallback
    return fallback


def run_pipeline(files, pre_extracted_text: str = "", source_label: str = ""):
    st.session_state.agent_logs = []

    # ── Reset per-run flags ───────────────────────────────────────────────
    st.session_state["_az_err_shown"]   = False  # show Azure errors fresh each run
    st.session_state["_claude_err_shown"] = False  # show Claude errors fresh each run
    st.session_state["_claude_blocked"]   = False  # re-test Claude on each new run

    # ── Show progress UI immediately so user sees action right away ───────
    _PIPE_STEPS = [
        "Ingest", "Intelligence", "Semantic", "RAG",
        "Time", "Cost", "Risk", "Architecture",
        "Scope", "Proposal", "Diagrams", "Discovery", "Finalize",
    ]
    pb      = st.progress(0)
    stepper = st.empty()
    status  = st.empty()

    def _upd(idx: int, msg: str, pct: int):
        stepper.markdown(_pipeline_stepper_html(_PIPE_STEPS, idx), unsafe_allow_html=True)
        status.markdown(
            f'<div style="font-family:\'DM Sans\',sans-serif;font-size:.82rem;'
            f'color:var(--t2);padding:4px 0">{msg}</div>',
            unsafe_allow_html=True,
        )
        pb.progress(pct)

    _upd(0, "Initialising…", 2)

    # ── Guard: require at least one AI provider ───────────────────────────
    if not is_any_ai_configured():
        pb.empty(); stepper.empty(); status.empty()
        st.error(
            "**No AI provider is configured.** Cannot run the pipeline.\n\n"
            "Add your Azure OpenAI credentials to `config.yaml`:\n"
            "```yaml\nproviders:\n  azure:\n    api_key: \"your-key\"\n"
            "    endpoint: \"https://your-resource.openai.azure.com\"\n"
            "    deployment: \"your-deployment-name\"\n```",
            icon="🔑",
        )
        return

    # ── Pick per-feature AI clients — reuse a single instance per provider ─
    # Build one client per routing key to avoid creating 10+ identical objects.
    _default_key = get_model_for_feature("default")
    _client_cache: dict = {}

    def _ai(feature: str):
        key = get_model_for_feature(feature)
        if key not in _client_cache:
            _client_cache[key] = _pick_ai_for(feature)
        return _client_cache[key]

    ai      = _ai("default")
    ai_req  = _ai("requirements")
    ai_rag  = ai_req                       # RAG reuses requirements client
    ai_time = _ai("time")
    ai_cost = _ai("cost")
    ai_risk = _ai("risk")
    ai_arch = _ai("architecture")
    ai_scope = _ai("sow")
    ai_prop  = _ai("proposal")
    ai_disc  = _ai("discovery")
    ai_compl = _ai("completeness")

    live = ai.is_live
    _model_labels = {
        "azure":    "Azure OpenAI",
        "claude":   "Anthropic Claude",
        "codex":    "GPT-5.3 Codex",
        "deepseek": "DeepSeek",
        "gemini":   "Google Gemini",
        "grok":     "xAI Grok",
        "nano":     "GPT-5.4 Nano",
        "qwen":     "Alibaba Qwen",
        "vertex":   "Vertex AI (Claude)",
    }
    model_name = _model_labels.get(_default_key, "AI")
    _provider_display = _model_labels.get(_default_key, _default_key.title())
    _banner_slot = st.empty()
    if live:
        _LIVE_BANNER = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#0a0e1a;overflow:hidden;width:100%;height:138px}
.banner{width:100%;height:138px;position:relative;overflow:hidden;border-radius:12px;background:linear-gradient(135deg,#080d1a 0%,#0d1627 50%,#080d1a 100%)}
.banner::before{content:'';position:absolute;inset:0;border-radius:12px;padding:1px;background:linear-gradient(90deg,#00d4aa,#7b61ff,#00b4d8,#ff6b9d,#00d4aa);background-size:400% 100%;-webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:bdrAnim 4s linear infinite;pointer-events:none;z-index:20}
@keyframes bdrAnim{to{background-position:400% 0}}
.aur{position:absolute;inset:0;background:radial-gradient(ellipse 60% 90% at 12% 50%,rgba(0,212,170,.14) 0%,transparent 60%),radial-gradient(ellipse 60% 90% at 88% 50%,rgba(123,97,255,.14) 0%,transparent 60%),radial-gradient(ellipse 50% 70% at 50% 5%,rgba(0,180,216,.09) 0%,transparent 50%);animation:aurAnim 5s ease-in-out infinite alternate}
@keyframes aurAnim{0%{opacity:.7;transform:scale(1)}100%{opacity:1;transform:scale(1.04)}}
.scan{position:absolute;top:0;left:-80%;width:38%;height:100%;background:linear-gradient(90deg,transparent,rgba(0,212,170,.07),rgba(0,212,170,.03),transparent);animation:scanAnim 3.8s linear infinite;z-index:1}
@keyframes scanAnim{to{left:145%}}
.inner{position:relative;z-index:10;height:100%;display:flex;align-items:center;padding:0 24px;gap:26px}
.orb-wrap{position:relative;width:60px;height:60px;flex-shrink:0}
.orb-ring{position:absolute;border-radius:50%;border-style:solid;animation:spinRing linear infinite}
.orb-ring.r1{inset:0;border-width:1.5px;border-color:rgba(0,212,170,.65) transparent rgba(0,212,170,.65) transparent;animation-duration:3s}
.orb-ring.r2{inset:7px;border-width:1.5px;border-color:transparent rgba(123,97,255,.7) transparent rgba(123,97,255,.7);animation-duration:2.1s;animation-direction:reverse}
.orb-ring.r3{inset:14px;border-width:1px;border-color:rgba(0,180,216,.55) transparent rgba(0,180,216,.55) transparent;animation-duration:1.4s}
@keyframes spinRing{to{transform:rotate(360deg)}}
.orb-core{position:absolute;inset:20px;border-radius:50%;background:linear-gradient(135deg,#00d4aa,#7b61ff);display:flex;align-items:center;justify-content:center;font-size:12px;box-shadow:0 0 18px rgba(0,212,170,.75),0 0 36px rgba(0,212,170,.4);animation:corePls 2s ease-in-out infinite}
@keyframes corePls{0%,100%{box-shadow:0 0 18px rgba(0,212,170,.75),0 0 36px rgba(0,212,170,.4)}50%{box-shadow:0 0 28px rgba(0,212,170,1),0 0 56px rgba(0,212,170,.65),0 0 72px rgba(0,212,170,.2)}}
.text-col{flex:1;display:flex;flex-direction:column;gap:8px}
.headline{font-family:'Segoe UI',system-ui,sans-serif;font-size:20px;font-weight:800;letter-spacing:4px;text-transform:uppercase;background:linear-gradient(90deg,#00d4aa,#00b4d8,#7b61ff,#ff6b9d,#00d4aa);background-size:300% 100%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:txtShimmer 3.8s linear infinite;white-space:nowrap}
@keyframes txtShimmer{to{background-position:300% 0}}
.sub-row{display:flex;align-items:center;gap:10px}
.ag-wrap{display:flex;gap:4px;align-items:center}
.ag{width:7px;height:7px;border-radius:50%;background:rgba(0,212,170,.22);border:1px solid rgba(0,212,170,.4);animation:agPls 1.65s ease infinite}
@keyframes agPls{0%,65%,100%{background:rgba(0,212,170,.22);transform:scale(1)}32%{background:#00d4aa;transform:scale(1.7);box-shadow:0 0 8px #00d4aa}}
.sub-txt{font-family:'Segoe UI',monospace,sans-serif;font-size:9px;color:rgba(148,163,184,.75);letter-spacing:2.5px;text-transform:uppercase}
.right-col{display:flex;flex-direction:column;align-items:flex-end;gap:9px;flex-shrink:0}
.spill{display:flex;align-items:center;gap:7px;padding:5px 14px;background:rgba(0,212,170,.08);border:1px solid rgba(0,212,170,.28);border-radius:20px}
.sdot{width:8px;height:8px;border-radius:50%;background:#00d4aa;box-shadow:0 0 9px #00d4aa;animation:sdBlink 1.1s ease-in-out infinite}
@keyframes sdBlink{0%,100%{opacity:1}50%{opacity:.15}}
.stxt{font-family:'Segoe UI',sans-serif;font-size:10px;color:#00d4aa;font-weight:700;letter-spacing:1.5px;text-transform:uppercase}
.pbar{width:92px;height:3px;background:rgba(255,255,255,.07);border-radius:3px;overflow:hidden}
.pfill{height:100%;width:25%;background:linear-gradient(90deg,#00d4aa,#7b61ff,#ff6b9d);border-radius:3px;animation:barAnim 2.3s ease-in-out infinite}
@keyframes barAnim{0%{width:5%;margin-left:0}50%{width:55%;margin-left:0}100%{width:5%;margin-left:90%}}
.ekg{position:absolute;bottom:9px;left:50%;transform:translateX(-50%);opacity:.5}
.ekgp{fill:none;stroke:#00d4aa;stroke-width:1.5;stroke-dasharray:280;stroke-dashoffset:280;animation:drawEkg 2.6s ease-in-out infinite}
@keyframes drawEkg{0%{stroke-dashoffset:280;opacity:0}12%{opacity:1}78%{stroke-dashoffset:0;opacity:1}100%{stroke-dashoffset:-280;opacity:0}}
.ptcl{position:absolute;border-radius:50%;pointer-events:none;z-index:2}
@keyframes ptFloat{0%{transform:translateY(0) scale(1);opacity:.65}50%{opacity:1}100%{transform:translateY(-130px) scale(0);opacity:0}}
</style></head>
<body><div class="banner">
<div class="aur"></div><div class="scan"></div><div id="pc"></div>
<div class="inner">
<div class="orb-wrap"><div class="orb-ring r1"></div><div class="orb-ring r2"></div><div class="orb-ring r3"></div><div class="orb-core">🧠</div></div>
<div class="text-col">
<div class="headline">Intelligence Engine</div>
<div class="sub-row"><div class="ag-wrap" id="agd"></div><div class="sub-txt">&nbsp;11 Agents Activated</div></div>
</div>
<div class="right-col">
<div class="spill"><div class="sdot"></div><div class="stxt">Processing</div></div>
<div class="pbar"><div class="pfill"></div></div>
</div>
</div>
<svg class="ekg" width="240" height="22" viewBox="0 0 240 22">
<path class="ekgp" d="M0,11 L46,11 L58,3 L70,19 L82,3 L94,11 L106,11 L116,7 L126,15 L136,11 L155,11 L165,4 L175,18 L185,11 L205,11 L215,8 L225,14 L240,11"/>
</svg>
</div>
<script>
var c=document.getElementById('pc');
for(var i=0;i<22;i++){
var p=document.createElement('div');p.className='ptcl';
var s=1+Math.random()*2.5;
p.style.cssText='width:'+s+'px;height:'+s+'px;left:'+Math.random()*100+'%;bottom:'+Math.random()*80+'%;background:'+(Math.random()>.5?'rgba(0,212,170,':'rgba(123,97,255,')+(.3+Math.random()*.55)+');animation:ptFloat '+(2+Math.random()*3.5)+'s linear '+(Math.random()*5)+'s infinite';
c.appendChild(p);}
var ag=document.getElementById('agd');
for(var j=0;j<11;j++){
var d=document.createElement('div');d.className='ag';d.style.animationDelay=(j*.148)+'s';ag.appendChild(d);}
</script>
</body></html>"""
        with _banner_slot:
            st.components.v1.html(_LIVE_BANNER, height=142, scrolling=False)
    else:
        pb.empty(); stepper.empty(); status.empty()
        st.markdown(
            '<div class="phdr" style="background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.2)">'
            '⚠️ No live AI client found — check config.yaml credentials and restart.</div>',
            unsafe_allow_html=True,
        )
        return   # don't run pipeline with no AI

    # ── Live reasoning log — updates after each agent step ────────────────
    log_area = st.empty()
    _LOG_ICONS = {
        "Ingestion": "📥", "Intelligence": "🔍", "Semantic": "🧠", "RAG": "📚",
        "Time": "⏱️", "Cost": "💰", "Risk": "⚠️", "Architecture": "🏗️",
        "Scope": "📌", "Proposal": "📄", "Visualizer": "🎨", "Discovery": "🔎",
    }

    def _render_live_log():
        logs = st.session_state.agent_logs
        if not logs:
            return
        rows = ""
        for entry in logs:
            icon = _LOG_ICONS.get(entry["agent"], "🔷")
            ts = entry.get("time", "")[-8:-3] if entry.get("time") else ""
            rows += (
                f'<div class="alog">'
                f'<span class="abadge">{icon} {entry["agent"]}</span>'
                f'<span class="aok">✓ Done</span>'
                f'<span class="adet">{entry["detail"]}</span>'
                f'<span style="margin-left:auto;font-family:\'JetBrains Mono\',monospace;'
                f'font-size:.7rem;color:var(--t3)">{ts}</span>'
                f'</div>'
            )
        log_area.markdown(
            f'<div style="max-height:220px;overflow-y:auto;padding:10px 12px;'
            f'background:var(--bg2);border-radius:8px;border:1px solid var(--bd);margin-top:8px">'
            f'<div style="font-family:\'Space Grotesk\',sans-serif;font-size:.72rem;font-weight:600;'
            f'color:var(--t3);margin-bottom:8px;letter-spacing:.06em;text-transform:uppercase">'
            f'Agent Reasoning Log</div>{rows}</div>',
            unsafe_allow_html=True,
        )

    _upd(0, "Ingesting documents…", 5)
    dp = DocProcessor()
    if pre_extracted_text:
        # Transcript / pre-extracted path — skip DocProcessor file parsing
        text = (
            "DISCOVERY CALL TRANSCRIPT — REQUIREMENTS SOURCE\n\n"
            "The following is an edited meeting/discovery call transcript. "
            "Extract all business requirements, technical requirements, stakeholders, "
            "pain points, and project scope from the discussion below.\n\n"
            + pre_extracted_text
        )
        _label = source_label or "Transcript"
        st.session_state["_extracted_text"]     = text
        st.session_state["_extracted_filenames"] = [_label]
        log_agent("Ingestion", f"Transcript source — {len(text):,} chars")
    else:
        text = ""
        for f in files:
            text += dp.extract(f) + "\n\n"
        st.session_state["_extracted_text"] = text   # stored for feedback reruns
        st.session_state["_extracted_filenames"] = [f.name for f in files]
        log_agent("Ingestion", str(len(files)) + " file(s), " + str(len(text)) + " chars")
    st.session_state["feedback_items"] = {}       # reset feedback on fresh run
    st.session_state.pop("scope_validation_result", None)  # clear so validator re-runs on new doc
    # Clear gantt figure cache so new estimates rebuild both charts
    for _k in [k for k in st.session_state if k.startswith("_gfigs_")]:
        st.session_state.pop(_k, None)
    _render_live_log(); time.sleep(0.2)

    _upd(1, "Analysing document structure…", 10)
    intel = dp.analyze(text)
    log_agent("Intelligence", str(intel["section_count"]) + " sections, " + str(intel["word_count"]) + " words")
    _render_live_log(); time.sleep(0.2)

    _upd(2, "Semantic analysis (deep extraction)…", 20)
    # Use Opus for scope analysis — larger context, deeper extraction.
    # Falls back to the configured requirements client if Opus isn't available.
    _opus_client = AnthropicAI.opus_from_session()
    _ai_for_scope = _opus_client if (_opus_client and _opus_client.is_live) else ai_req
    semantic = _ai_for_scope.analyze_requirements(text)

    # Apply user-supplied hints to override AI extraction
    _eng_hint = st.session_state.get("engagement_type", "Implementation")
    semantic["engagement_type"] = _eng_hint

    # Project type: user selection overrides / supplements AI-detected type
    _user_pt_tags = safe_list(st.session_state.get("project_type_tags", []))
    if _user_pt_tags:
        _pt_label = " & ".join(_user_pt_tags)
        semantic["project_type"] = _pt_label
        semantic["project_type_tags"] = _user_pt_tags
        log_agent("Semantic", f"Project type set by user: {_pt_label}")

    # Store run-specific instruction for training context injection
    _run_instr = (st.session_state.get("run_instruction", "") or "").strip()

    st.session_state["_last_semantic"] = semantic
    log_agent("Semantic", str(len(safe_list(semantic.get("requirements")))) + " requirements, " + str(len(safe_list(semantic.get("technology_stack")))) + " technologies detected")
    _render_live_log(); time.sleep(0.2)

    _upd(3, "Historical RAG similarity search…", 30)
    # Merge manually-added projects with past DB runs so RAG always has data
    _hist = list(st.session_state.historical_projects)
    if not _hist:
        _db_past = _db_load_runs("All")   # full collection — no cap
        # Score every run for similarity to the current scope
        _sem_type   = (semantic.get("project_type") or "").lower()
        _sem_tech   = set(t.lower() for t in safe_list(semantic.get("technology_stack", [])))
        def _run_score(r):
            s = 0.0
            rtype = (r.get("project_type") or "").lower()
            if rtype and _sem_type:
                rw, sw = set(rtype.split()), set(_sem_type.split())
                if rtype == _sem_type:
                    s += 0.50
                elif rw & sw:
                    s += 0.25
            rtech = set(t.lower() for t in (r.get("tech_stack") or []))
            if rtech and _sem_tech:
                s += len(rtech & _sem_tech) / max(len(rtech | _sem_tech), 1) * 0.45
            if r.get("total_hours", 0) > 0:
                s += 0.05      # slight preference for runs that have usable hours
            return s
        # Sort all runs by similarity; deduplicate by name, keep best match per unique project
        _ranked = sorted(_db_past, key=_run_score, reverse=True)
        _seen_names: set = set()
        _top: list = []
        for _r in _ranked:
            _key = (
                (_r.get("client_name") or _r.get("project_title") or _r.get("project_type") or "")
                .strip().lower()
            )
            if not _key or _key in _seen_names:
                continue
            _seen_names.add(_key)
            if _r.get("total_hours", 0) > 0:
                _top.append(_r)
            if len(_top) >= 15:
                break
        # If not enough with hours, backfill from unique runs without hours
        if len(_top) < 5:
            for _r in _ranked:
                _key = (
                    (_r.get("client_name") or _r.get("project_title") or _r.get("project_type") or "")
                    .strip().lower()
                )
                if _key and _key not in _seen_names:
                    _seen_names.add(_key)
                    _top.append(_r)
                if len(_top) >= 15:
                    break
        _hist = [
            {
                "name":            r.get("client_name") or r.get("project_title") or r.get("project_type") or "Past Project",
                "type":            r.get("project_type", ""),
                "estimated_hours": r.get("total_hours", 0),
                "actual_hours":    r.get("actual_hours") or r.get("total_hours", 0),
                "estimated_cost":  r.get("monthly_cost", 0),
                "actual_cost":     r.get("actual_cost")  or r.get("monthly_cost", 0),
                "outcome":         r.get("project_outcome") or r.get("risk_level", "Completed"),
                "tech_stack":      r.get("tech_stack", []),
                "ts":              r.get("ts", ""),
                "similarity":      round(_run_score(r), 3),
            }
            for r in _top
        ]
    rag = ai_rag.search_historical(text, _hist)
    # ── Milvus vector RAG — enrich with past scope documents ──────────────
    try:
        from .milvus_client import MilvusRAG as _MilvusRAG
        _mv = _MilvusRAG.from_session()
        if _mv.is_configured:
            _upd(3, "Searching Milvus knowledge base…", 32)
            _mv_rag = _mv.search(text[:6000])
            if _mv_rag.get("similar_projects"):
                rag["similar_projects"] = (
                    _mv_rag["similar_projects"] + rag.get("similar_projects", [])
                )[:10]
            if _mv_rag.get("milvus_context"):
                rag["milvus_context"] = _mv_rag["milvus_context"]
                rag["milvus_hits"] = _mv_rag.get("milvus_hits", 0)
            if _mv_rag.get("benchmark_cost", 0):
                rag["benchmark_cost"] = _mv_rag["benchmark_cost"]
            if _mv_rag.get("benchmark_cost_services"):
                rag["benchmark_cost_services"] = _mv_rag["benchmark_cost_services"]
    except Exception as _mv_exc:
        log_agent("RAG", f"Milvus error: {_mv_exc}")
    # ─────────────────────────────────────────────────────────────────────
    _mv_hits = rag.get("milvus_hits", 0)
    _mv_names = ", ".join(p["name"] for p in rag.get("similar_projects", [])[:_mv_hits]) if _mv_hits else ""
    log_agent("RAG", str(len(safe_list(rag.get("similar_projects")))) + " matches"
              + (f" — {_mv_hits} from Milvus: {_mv_names}" if _mv_hits else ""))
    # ── Training context injection ─────────────────────────────────────────
    try:
        from .training import load_training_context as _ltc
        # Prefer user-selected project types; fall back to AI-detected types from semantic
        _user_tags = safe_list(st.session_state.get("project_type_tags", []))
        if _user_tags:
            _detected_types = _user_tags
        else:
            _sem_pt   = (semantic.get("project_type") or "").lower()
            _sem_ts   = " ".join(str(t).lower() for t in safe_list(semantic.get("technology_stack", [])))
            _combined = f"{_sem_pt} {_sem_ts}"
            _detected_types = []
            if any(k in _combined for k in ["ai", "openai", "gpt", "claude", "llm", "ml", "machine learning", "copilot", "rag", "chatbot", "foundry"]):
                _detected_types.append("AI")
            if any(k in _combined for k in ["sharepoint", "teams", "m365", "office 365", "o365", "power automate", "power apps", "viva"]):
                _detected_types.append("SharePoint")
            if any(k in _combined for k in ["data", "databricks", "synapse", "fabric", "etl", "pipeline", "analytics", "bi", "warehouse", "lakehouse"]):
                _detected_types.append("Data")
            if any(k in _combined for k in ["cloud", "azure", "aws", "gcp", "kubernetes", "docker", "devops", "terraform", "migration", "infrastructure"]):
                _detected_types.append("Cloud")
            if any(k in _combined for k in ["custom", "web app", "portal", "application", "mobile", "react", "angular", ".net", "java"]):
                _detected_types.append("Custom App")

        _tc = _ltc(project_types=_detected_types or None)

        # Prepend run-specific instruction (highest priority — this run only)
        if _run_instr:
            _run_block = (
                "═" * 60 + "\n"
                "RUN-SPECIFIC INSTRUCTION (highest priority — follow exactly for this estimation):\n"
                f"{_run_instr}\n"
                + "═" * 60
            )
            _tc = _run_block + ("\n\n" + _tc if _tc else "")

        # Prepend project-type context hint so agents know the type explicitly
        if _detected_types:
            _type_hint = (
                f"PROJECT TYPE FOR THIS ESTIMATION: {' & '.join(_detected_types)}\n"
                "Apply all estimation rules, work streams, and cost assumptions appropriate for this type. "
                "Load only training instructions tagged for this project type or marked as general.\n"
            )
            _tc = _type_hint + ("\n" + _tc if _tc else "")

        if _tc:
            rag["training_context"] = _tc
            st.session_state["_training_context"] = _tc
            st.session_state["_training_types"] = _detected_types
            log_agent("Training", f"Loaded {len(_tc)} chars of training context (types: {_detected_types or ['All']})")
    except Exception as _tc_exc:
        log_agent("Training", f"Training context skipped: {_tc_exc}")
    _render_live_log(); time.sleep(0.2)

    _upd(4, "Estimating time & effort…", 40)
    time_est = ai_time.estimate_time(semantic, rag)
    st.session_state["_last_time_est"] = time_est
    log_agent("Time", str(time_est.get("total_hours", 0)) + " hours across " + str(len(safe_list(time_est.get("phases")))) + " phases")
    _render_live_log(); time.sleep(0.2)

    # ── TEST MODE: stop here so time estimate can be reviewed immediately ──
    if st.session_state.get("time_test_mode", False):
        pb.progress(100)
        stepper.markdown(_pipeline_stepper_html(_PIPE_STEPS, len(_PIPE_STEPS)), unsafe_allow_html=True)
        status.empty(); log_area.empty(); _banner_slot.empty()
        show_toast("⏱️ Time Estimate ready — test mode (other agents skipped)", "success")
        st.session_state.processing_results = {
            "semantic_analysis": semantic, "rag": rag, "time_estimate": time_est,
            "cost_estimate": {}, "risk_assessment": {}, "architecture": {},
            "scope": {}, "proposal": {}, "mermaid_diagrams": [],
            "discovery_questions": {}, "rich_arch_html": None,
        }
        st.session_state.model_metrics["proposals_processed"] += 1
        return

    _upd(5, "Calculating infrastructure cost…", 50)
    cost_est = ai_cost.estimate_cost(semantic, time_est, rag)
    st.session_state["_last_cost_est"] = cost_est
    log_agent("Cost", "$" + str(cost_est.get("total_monthly_cost", 0)) + "/mo (" + str(len(safe_list(cost_est.get("azure_costs")))) + " services)")
    _render_live_log(); time.sleep(0.2)

    _upd(6, "Analysing risks…", 60)
    risk = ai_risk.analyze_risk(semantic, time_est, cost_est)
    log_agent("Risk", str(risk.get("overall_score", 0)) + "/10 — " + str(len(safe_list(risk.get("risks")))) + " risks identified")
    _render_live_log(); time.sleep(0.2)

    _upd(7, "Designing solution architecture…", 70)
    arch = ai_arch.design_architecture(semantic, rag)
    log_agent("Architecture", str(len(safe_list(arch.get("components")))) + " components")
    _render_live_log(); time.sleep(0.2)

    _upd(8, "Defining scope & assumptions…", 78)
    # Fetch matching templates to ground scope + proposal generation
    _tpl_matched = find_matching_templates(
        project_type=safe_str(semantic.get("project_type", "")),
        tech_stack=safe_list(semantic.get("technology_stack", [])),
    )
    _tpl_context = format_templates_for_prompt(_tpl_matched)
    scope = ai_scope.define_scope(semantic, time_est, cost_est, template_context=_tpl_context)
    log_agent("Scope", "Boundaries defined")
    _render_live_log(); time.sleep(0.2)

    _upd(9, "Writing proposal document…", 84)
    proposal = ai_prop.write_proposal(semantic, time_est, cost_est, risk, arch, scope, template_context=_tpl_context)
    log_agent("Proposal", "Document generated")
    _render_live_log(); time.sleep(0.2)

    _upd(10, "Generating architecture diagrams…", 90)
    # Always use Azure OpenAI for diagrams — it produces clean flowchart syntax
    # that the Mermaid renderer handles reliably. Qwen produces unstable Mermaid.
    _az_diag = AzureAI.from_session()
    mermaid_diagrams = _az_diag.generate_mermaid_diagrams(semantic, arch)
    log_agent("Visualizer", str(len(mermaid_diagrams)) + " diagrams generated")
    # Rich HTML arch diagram is generated on-demand when user clicks the button
    rich_arch_html = None
    _render_live_log(); time.sleep(0.2)

    _upd(11, "Generating discovery questions…", 93)
    discovery_questions = ai_disc.generate_discovery_questions(semantic, scope, risk)
    total_q = discovery_questions.get("total_questions", 0)
    log_agent("Discovery", f"{total_q} prioritised discovery questions generated")
    _render_live_log(); time.sleep(0.2)

    # ── Step 12: Finalize — pre-compute heavy deliverables while user waits ──
    _upd(12, "Finalizing deliverables & pre-computing visuals…", 97)
    import hashlib as _hl2, json as _jc2
    try:
        # Pre-compute AI Vision Architecture (most expensive render-time call)
        _cv_key = "claude_vision_arch_" + _hl2.md5(
            _jc2.dumps(arch, sort_keys=True, default=str).encode()
        ).hexdigest()[:10]
        if not st.session_state.get(_cv_key):
            _ant2 = AnthropicAI.from_session()
            _vis_html = None
            if _ant2.is_live and not st.session_state.get("_claude_blocked"):
                _vis_html = _ant2.generate_claude_premium_diagram(arch, semantic, cost_est)
            if not _vis_html:
                _az2 = AzureAI.from_session()
                if _az2.is_live:
                    _vis_html = _az2.generate_ai_arch_svg(arch, semantic)
            if _vis_html:
                st.session_state[_cv_key] = _vis_html
                log_agent("AI Vision", "Pre-computed during pipeline — renders instantly")

        # Pre-generate architecture drawio XML (cached by arch signature)
        from .diagrams import generate_drawio_xml as _gen_drawio
        _arch_sig = _hl2.md5(_jc2.dumps(arch, sort_keys=True, default=str).encode()).hexdigest()[:12]
        _drawio_key = f"_drawio_v3_{_arch_sig}"
        if _drawio_key not in st.session_state:
            st.session_state[_drawio_key] = _gen_drawio(arch, semantic).encode("utf-8")

        # Azure pricing is fetched lazily on Cost tab open — not here (avoids 12s HTTP block)

    except Exception as _fin_ex:
        log_agent("Finalize", f"Pre-computation partial: {str(_fin_ex)[:120]}")

    _render_live_log(); time.sleep(0.2)

    pb.progress(100)
    stepper.markdown(_pipeline_stepper_html(_PIPE_STEPS, len(_PIPE_STEPS)), unsafe_allow_html=True)
    status.empty()
    log_area.empty()
    _banner_slot.empty()
    show_toast("🚀 Proposal ready — all 12 agents completed!", "success")
    st.session_state.processing_results = {
        "semantic_analysis": semantic, "rag": rag, "time_estimate": time_est,
        "cost_estimate": cost_est, "risk_assessment": risk, "architecture": arch,
        "scope": scope, "proposal": proposal, "mermaid_diagrams": mermaid_diagrams,
        "discovery_questions": discovery_questions,
        "rich_arch_html": rich_arch_html,
    }
    st.session_state.model_metrics["proposals_processed"] += 1

    # Auto-populate client name from semantic analysis if not already set by user
    _sem_client = safe_str(semantic.get("client_name", ""))
    if _sem_client and not st.session_state.get("client_name"):
        st.session_state["client_name"]          = _sem_client
        st.session_state["proposal_client_name"] = _sem_client

    # ── Save to persistent SQLite DB + in-memory versions ──
    # Revision mode: use _revision_parent_id as parent and carry versioning metadata
    _rev_pid = st.session_state.get("_revision_parent_id")
    _v_parent_id = _rev_pid or st.session_state.get("_parent_run_id")
    _v_number = db_get_next_version_number(_v_parent_id) if _v_parent_id else 1

    snapshot = {
        "ts":                   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project_type":         safe_str(semantic.get("project_type", "")),
        "client_name":          safe_str(
                                    st.session_state.get("client_name", "")    # user-typed always wins
                                    or st.session_state.get("proposal_client_name", "")
                                    or semantic.get("client_name", "")         # AI fallback only if user left it blank
                                ),
        "project_title":        safe_str(semantic.get("project_title", "")),
        "total_hours":          safe_int(time_est.get("total_hours", 0)),
        "duration_weeks":       safe_str(time_est.get("duration_weeks", "")),
        "monthly_cost":         safe_int(cost_est.get("total_monthly_cost", 0)),
        "annual_cost":          safe_int(cost_est.get("total_annual_cost", 0)),
        "risk_level":           safe_str(risk.get("overall_level", "")),
        "risk_score":           safe_int(risk.get("overall_score", 0)),
        "req_count":            len(safe_list(semantic.get("requirements", []))),
        "tech_stack":           safe_list(semantic.get("technology_stack", []))[:10],
        "model_used":           model_name,
        "three_point":          time_est.get("three_point", {}),
        "created_by":           st.session_state.get("auth_user", ""),
        "created_by_email":     st.session_state.get("auth_email", ""),
        "parent_run_id":        _v_parent_id,
        # Versioning metadata
        "version_number":       _v_number,
        "version_status":       st.session_state.get("_rev_ver_status", "draft"),
        "negotiation_stage":    st.session_state.get("_rev_neg_stage", "initial"),
        "revision_reason_type": st.session_state.get("_rev_reason_type", ""),
        "revision_notes":       st.session_state.get("_rev_notes", ""),
        "competitor_context":   st.session_state.get("_rev_competitor_ctx", ""),
        "parking_lot":          st.session_state.get("_rev_parking_lot", []),
    }
    # Persist to disk
    try:
        run_id = _db_save_run(snapshot, st.session_state.processing_results)
        st.session_state["_last_run_id"] = run_id
        # Store parent_id for delta view display after this run
        if _rev_pid:
            st.session_state["_revision_completed_parent"] = _rev_pid
            st.session_state["_revision_completed_child"]  = run_id
        # Clear revision & restore state
        for _rk in ["_revision_parent_id", "_rev_reason_type", "_rev_neg_stage",
                     "_rev_ver_status", "_rev_notes", "_rev_competitor_ctx", "_rev_parking_lot"]:
            st.session_state.pop(_rk, None)
        st.session_state.pop("_parent_run_id", None)   # consumed — clear after save
        try:
            db_log_activity(
                snapshot.get("created_by_email", ""),
                snapshot.get("created_by", ""),
                "pipeline_run",
                f"Estimation: {snapshot.get('client_name','Client')} — {snapshot.get('project_type','')} "
                f"({snapshot.get('total_hours',0):,}h · ${snapshot.get('monthly_cost',0):,}/mo · "
                f"{snapshot.get('risk_level','?')} risk) · Run #{run_id}",
                "Pipeline",
            )
        except Exception:
            pass
        notify(
            "run_saved",
            f"Estimate saved: {snapshot.get('project_type', 'Project')}",
            f"{snapshot.get('total_hours', 0):,}h · {snapshot.get('risk_level', '')} risk · Run #{run_id}",
            {"run_id": run_id},
        )
        # Duplicate detection — warn if same client+project ran recently
        try:
            _cn = snapshot.get("client_name", "").strip()
            _pt = snapshot.get("project_type", "").strip()
            if _cn and _pt:
                _dups = [d for d in db_check_duplicate(_cn, _pt, days=7)
                         if d["id"] != run_id]
                if _dups:
                    st.session_state["_dup_warning"] = {
                        "run_id":  run_id,
                        "dup_ids": [d["id"] for d in _dups],
                        "label":   f"{_cn} / {_pt}",
                    }
                    notify("run_duplicate",
                           f"⚠️ Possible duplicate — {_cn}",
                           f"Similar run(s) already exist: #{', #'.join(str(d['id']) for d in _dups)}",
                           {"dup_ids": [d["id"] for d in _dups]})
        except Exception:
            pass
    except Exception as _db_err:
        st.warning(f"DB save warning: {_db_err}")
    # Keep last 20 in-memory for History tab comparison
    if "proposal_versions" not in st.session_state:
        st.session_state.proposal_versions = []
    st.session_state.proposal_versions.append(snapshot)
    st.session_state.proposal_versions = st.session_state.proposal_versions[-20:]
    # Reset chat context for new proposal
    st.session_state.chat_messages = []

    # ── Store uploaded document in Milvus for future RAG ──────────────────
    try:
        from .milvus_client import MilvusRAG as _MilvusRAG
        _mv_store = _MilvusRAG.from_session()
        if _mv_store.is_configured:
            _src = ", ".join(getattr(f, "name", str(f)) for f in files) if files else "uploaded_document"
            _mv_store.store(
                text=text[:65000],
                source=_src,
                doc_type=safe_str(semantic.get("project_type", "")),
            )
    except Exception:
        pass  # Milvus store is best-effort; never block the pipeline
    # ─────────────────────────────────────────────────────────────────────


_FEEDBACK_SECTIONS = [
    ("requirements",  "📋 Requirements",  "Add/remove requirements, change project type, fix misunderstood scope"),
    ("time",          "⏱️ Time Estimate", "Adjust hours up/down, change phase durations, add missing tasks"),
    ("cost",          "💰 Infra Cost",    "Change Azure tiers, add/remove services, adjust monthly budget"),
    ("risk",          "⚠️ Risk",          "Update risk score, add risks, change mitigations"),
    ("architecture",  "🏗️ Architecture", "Add/remove components, change Azure services, update data flow"),
    ("scope",         "📌 Scope",         "Update in-scope/out-of-scope items, assumptions, exclusions"),
    ("proposal",      "📄 Proposal",      "Rewrite sections, change tone, update executive summary"),
    ("diagrams",      "📐 Diagrams",      "Regenerate Mermaid diagrams with updated architecture"),
]


def _quick_feedback(section_key: str, placeholder: str):
    """Compact inline feedback widget placed at the bottom of a result tab.
    Writes directly into st.session_state.feedback_items so the main
    feedback panel reflects it immediately.
    """
    st.markdown("---")
    qc1, qc2 = st.columns([5, 1])
    with qc1:
        val = st.text_input(
            f"Feedback on {section_key.replace('_',' ').title()}",
            placeholder=placeholder,
            key=f"qfb_{section_key}",
            label_visibility="collapsed",
        )
    with qc2:
        if st.button("Add ➕", key=f"qfb_add_{section_key}", width="stretch"):
            if val.strip():
                if "feedback_items" not in st.session_state:
                    st.session_state.feedback_items = {}
                st.session_state.feedback_items[section_key] = val.strip()
                show_toast(f"Feedback queued for {section_key}. Open 'Review & Improve' to apply.", "info")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  PROPOSAL TAB — helpers
# ═══════════════════════════════════════════════════════════════════════

def _build_r_with_edits(r: dict) -> dict:
    """Return a shallow copy of r with proposal sections patched from user edits."""
    edits = st.session_state.get("proposal_edits", {})
    if not edits:
        return r
    r2 = dict(r)
    prop = _copy.deepcopy(safe_dict(r.get("proposal")))
    sections = safe_list(prop.get("sections"))
    for sec in sections:
        title = safe_str(sec.get("title"))
        if title in edits:
            sec["content"] = edits[title]
    prop["sections"] = sections
    r2["proposal"] = prop
    return r2


def _proposal_personalization_bar():
    p1, p2, p3 = st.columns(3)
    with p1:
        val = st.text_input("🏢 Client Name", value=st.session_state.get("proposal_client_name", ""),
                            placeholder="e.g. Contoso Ltd.", key="prop_client_name_inp",
                            label_visibility="visible")
        st.session_state["proposal_client_name"] = val
    with p2:
        val = st.text_input("👤 Contact", value=st.session_state.get("proposal_contact_name", ""),
                            placeholder="e.g. Jane Smith", key="prop_contact_name_inp",
                            label_visibility="visible")
        st.session_state["proposal_contact_name"] = val
    with p3:
        val = st.text_input("📅 Proposal Date", value=st.session_state.get("proposal_proposal_date", ""),
                            placeholder=datetime.now().strftime("%B %d, %Y"), key="prop_date_inp",
                            label_visibility="visible")
        st.session_state["proposal_proposal_date"] = val


def _proposal_stats_bar(sections: list):
    edits = st.session_state.get("proposal_edits", {})
    total_words = 0
    for sec in sections:
        content = edits.get(safe_str(sec.get("title")), safe_str(sec.get("content", "")))
        total_words += len(content.split())
    read_time = max(1, round(total_words / 200))
    pages = max(1, round(total_words / 400))
    st.markdown(
        f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;'
        f'padding:10px 20px;margin-bottom:16px;display:flex;gap:28px;align-items:center;flex-wrap:wrap;">'
        f'<span style="color:#64748b;font-size:.78rem;">📄 <b style="color:#94a3b8">{len(sections)}</b> sections</span>'
        f'<span style="color:#64748b;font-size:.78rem;">🔤 <b style="color:#94a3b8">~{total_words:,}</b> words</span>'
        f'<span style="color:#64748b;font-size:.78rem;">⏱ <b style="color:#94a3b8">~{read_time} min</b> read</span>'
        f'<span style="color:#64748b;font-size:.78rem;">📋 <b style="color:#94a3b8">~{pages} pages</b></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _proposal_quality_scorecard(quality_checks: dict):
    if not quality_checks:
        return
    total = len(quality_checks)
    passed = sum(1 for v in quality_checks.values() if v)
    score = round(passed / total * 100) if total else 0
    color = "#00d4aa" if score >= 80 else ("#f59e0b" if score >= 50 else "#ef4444")
    # CSS conic-gradient gauge
    st.markdown(
        f'<div style="text-align:center;padding:16px 0 8px;">'
        f'<div style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:90px;height:90px;border-radius:50%;'
        f'background:conic-gradient({color} {score * 3.6}deg, #1e293b 0deg);'
        f'margin-bottom:8px;">'
        f'<div style="width:66px;height:66px;border-radius:50%;background:#0f172a;'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:1.1rem;font-weight:800;color:{color};">{score}%</div>'
        f'</div>'
        f'<div style="font-size:.72rem;font-weight:600;color:#64748b;letter-spacing:1px;text-transform:uppercase;">Quality Score</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Pills
    pills_html = '<div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;padding-bottom:12px;">'
    for k, v in quality_checks.items():
        bg = "rgba(0,212,170,.15)" if v else "rgba(245,158,11,.15)"
        border = "#00d4aa" if v else "#f59e0b"
        icon = "✅" if v else "⚠️"
        pills_html += (
            f'<span style="background:{bg};border:1px solid {border};'
            f'border-radius:20px;padding:3px 10px;font-size:.7rem;color:#e2e8f0;">'
            f'{icon} {k}</span>'
        )
    pills_html += '</div>'
    st.markdown(pills_html, unsafe_allow_html=True)


def _reference_doc_html(ref_text: str, section_content: str, filename: str) -> str:
    """Render an uploaded reference document with relevance-highlighted paragraphs."""
    import re as _re
    # Significant words from the current section content
    sig_words = set(w.lower() for w in _re.findall(r'\b\w{5,}\b', section_content))

    raw_paras = [p.strip() for p in ref_text.replace('\r', '').split('\n') if p.strip()]
    word_count = len(ref_text.split())

    paras_html = ""
    for para in raw_paras:
        words_in_para = set(w.lower() for w in _re.findall(r'\b\w{5,}\b', para))
        overlap = len(words_in_para & sig_words)
        is_heading = (
            (para.isupper() and 3 < len(para) < 90)
            or para.startswith('#')
            or _re.match(r'^(\d+[\.\)]|\-\-\-|===)', para)
        )
        if is_heading:
            paras_html += f'<div class="rh">{para}</div>'
        elif overlap >= 4:
            badge = f'<span class="bdg">● {overlap} matches</span>'
            paras_html += f'<div class="rp hi">{badge}{para}</div>'
        elif overlap >= 2:
            paras_html += f'<div class="rp md">{para}</div>'
        else:
            paras_html += f'<div class="rp">{para}</div>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box;}}
    body{{font-family:'Segoe UI',Arial,sans-serif;background:#070d1a;color:#e2e8f0;margin:0;padding:0;font-size:12px;line-height:1.6;}}
    .dh{{background:linear-gradient(135deg,#0f172a,#1a1035);border-bottom:2px solid #7c3aed;padding:12px 16px;position:sticky;top:0;z-index:10;}}
    .dh .fn{{font-size:13px;font-weight:800;color:#a78bfa;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
    .dh .st{{font-size:10px;color:#64748b;margin-bottom:6px;}}
    .leg{{display:flex;gap:14px;}}
    .li{{font-size:9px;color:#64748b;display:flex;align-items:center;gap:4px;}}
    .dot{{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0;}}
    .db{{padding:14px 16px 20px;}}
    .rh{{font-size:12px;font-weight:800;color:#7c3aed;margin:14px 0 5px;padding:4px 10px;border-left:3px solid #7c3aed;background:rgba(124,58,237,.07);border-radius:0 4px 4px 0;}}
    .rp{{font-size:11px;line-height:1.75;color:#64748b;margin-bottom:6px;padding:7px 10px;border-radius:6px;border-left:2px solid transparent;transition:background .2s;}}
    .rp:hover{{background:rgba(255,255,255,.03);}}
    .rp.md{{background:rgba(0,180,216,.05);border-left:2px solid #0e4a6b;color:#94a3b8;}}
    .rp.hi{{background:rgba(0,212,170,.09);border-left:2px solid #00d4aa;color:#cbd5e1;}}
    .bdg{{font-size:9px;font-weight:700;padding:1px 7px;border-radius:8px;margin-right:8px;background:rgba(0,212,170,.2);color:#00d4aa;display:inline-block;vertical-align:middle;}}
    </style></head><body>
    <div class="dh">
      <div class="fn">📎 {filename}</div>
      <div class="st">{word_count:,} words · {len(raw_paras)} paragraphs · green = relevant to this section</div>
      <div class="leg">
        <div class="li"><span class="dot" style="background:#00d4aa"></span>High relevance (4+ word matches)</div>
        <div class="li"><span class="dot" style="background:#0e4a6b"></span>Some relevance</div>
        <div class="li"><span class="dot" style="background:#1e293b"></span>Other content</div>
      </div>
    </div>
    <div class="db">{paras_html}</div>
    </body></html>"""


# ── on_click callbacks for proposal section cards ──────────────────────────
# These run BEFORE the fragment reruns, so state is correct on the very first
# rerun — no second st.rerun(scope="fragment") is ever needed.

def _cb_enter_edit(title: str):
    st.session_state.setdefault("proposal_section_edit_mode", set()).add(title)
    st.session_state.setdefault("proposal_regen_show", set()).discard(title)
    st.session_state.setdefault("proposal_ref_show",   set()).discard(title)

def _cb_cancel_edit(title: str):
    st.session_state.setdefault("proposal_section_edit_mode", set()).discard(title)

def _cb_save_edit(title: str, area_key: str):
    new_text = st.session_state.get(area_key, "")
    st.session_state.setdefault("proposal_edits", {})[title] = new_text
    st.session_state.setdefault("proposal_section_edit_mode", set()).discard(title)
    for _k in list(st.session_state):
        if _k.startswith("_prop_html_"):
            del st.session_state[_k]

def _cb_toggle_ai_studio(title: str):
    rs = st.session_state.setdefault("proposal_regen_show", set())
    if title in rs:
        rs.discard(title)
    else:
        rs.add(title)
        st.session_state.setdefault("proposal_section_edit_mode", set()).discard(title)

def _cb_toggle_ref(title: str):
    rs = st.session_state.setdefault("proposal_ref_show", set())
    if title in rs:
        rs.discard(title)
    else:
        rs.add(title)
        st.session_state.setdefault("proposal_section_edit_mode", set()).discard(title)

def _cb_reset_section(title: str):
    st.session_state.setdefault("proposal_edits",        {}).pop(title, None)
    st.session_state.setdefault("proposal_regen_prompt", {}).pop(title, None)
    for _k in list(st.session_state):
        if _k.startswith("_prop_html_"):
            del st.session_state[_k]

def _cb_set_chip(title: str, prompt: str):
    st.session_state.setdefault("proposal_regen_prompt", {})[title] = prompt

def _cb_close_ai_studio(title: str):
    st.session_state.setdefault("proposal_regen_show", set()).discard(title)

def _cb_generate(title: str, area_key: str):
    prompt = st.session_state.get(area_key, "")
    st.session_state.setdefault("proposal_regen_prompt", {})[title] = prompt
    st.session_state.setdefault("proposal_regen_loading", set()).add(title)

def _cb_reset_all_edits():
    st.session_state["proposal_edits"]             = {}
    st.session_state["proposal_section_edit_mode"] = set()
    st.session_state["proposal_regen_show"]        = set()
    for _k in list(st.session_state):
        if _k.startswith("_prop_html_"):
            del st.session_state[_k]


_REGEN_CHIPS = [
    ("📊 Add a table",          "Add a professional comparison or summary table that organises the key information clearly."),
    ("📈 Add metrics & stats",  "Include relevant statistics, percentages, benchmarks or metrics to strengthen the case."),
    ("📋 Use bullet points",    "Reformat the content as clear, scannable bullet points grouped by theme."),
    ("✂️ Make concise",         "Make this section more concise and punchy — keep only the most impactful points."),
    ("📝 Expand with detail",   "Expand this section with more detail, sub-points, and thorough explanation."),
    ("💡 Add examples",         "Add concrete real-world examples and use cases relevant to this topic."),
    ("🎯 Strengthen value prop","Rewrite to clearly articulate business value, ROI, and client benefits."),
    ("🔢 Numbered steps",       "Restructure as a numbered step-by-step process or action plan."),
    ("⚡ More impactful tone",  "Rewrite in a more confident, assertive, executive-level tone."),
    ("🏆 Add client benefits",  "Add a dedicated section highlighting specific benefits for the client."),
    ("🔒 Add risk mitigation",  "Include how risks are identified and mitigated in this area."),
    ("🌐 Add tech context",     "Add relevant technical context, standards, or best practices."),
]


def _proposal_section_card(sec: dict, idx: int, ai_client, r: dict):
    title = safe_str(sec.get("title", f"Section {idx + 1}"))
    edits         = st.session_state.setdefault("proposal_edits", {})
    edit_mode     = st.session_state.setdefault("proposal_section_edit_mode", set())
    regen_set     = st.session_state.setdefault("proposal_regen_loading", set())
    regen_show    = st.session_state.setdefault("proposal_regen_show", set())
    regen_prompts = st.session_state.setdefault("proposal_regen_prompt", {})
    ref_show      = st.session_state.setdefault("proposal_ref_show", set())
    ref_texts     = st.session_state.setdefault("proposal_ref_text", {})
    ref_names     = st.session_state.setdefault("proposal_ref_name", {})
    ref_use_ctx   = st.session_state.setdefault("proposal_ref_use_ctx", {})

    content       = edits.get(title, safe_str(sec.get("content", "")))
    is_editing    = title in edit_mode
    is_regen_open = title in regen_show
    is_ref_open   = title in ref_show
    word_count    = len(content.split())
    is_edited     = title in edits

    # ── Card border colour ───────────────────────────────────────────────
    # priority: edited=teal > ref open=orange > regen open=purple > default
    if is_edited:
        border_color = "#00d4aa"
    elif is_ref_open:
        border_color = "#f97316"
    elif is_regen_open:
        border_color = "#7c3aed"
    else:
        border_color = "#1e293b"

    badge_html = (
        '<span style="background:#00d4aa22;color:#00d4aa;font-size:.65rem;font-weight:700;'
        'border-radius:8px;padding:1px 8px;margin-left:6px;letter-spacing:.5px">EDITED</span>'
    ) if is_edited else ""

    st.markdown(
        f'<div style="background:#0b1120;border:1.5px solid {border_color};border-radius:14px;'
        f'padding:16px 20px 12px;margin-bottom:12px;transition:border-color .2s;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
        f'<div><span style="font-size:.78rem;font-weight:800;color:#00b4d8;letter-spacing:.3px">{title}</span>{badge_html}</div>'
        f'<span style="font-size:.65rem;color:#334155">{word_count} words</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── EDIT MODE ──────────────────────────────────────────────────────
    if is_editing:
        _area_key = f"prop_edit_area_{idx}"
        st.text_area(
            "Edit content", value=content, height=200,
            key=_area_key, label_visibility="collapsed",
        )
        _wc_live = len(st.session_state.get(_area_key, content).split())
        sc1, sc2, sc3 = st.columns([2, 2, 1])
        with sc1:
            st.button(
                "💾 Save Changes", key=f"prop_save_{idx}",
                type="primary", width="stretch",
                on_click=_cb_save_edit, args=(title, _area_key),
            )
        with sc2:
            st.button(
                "✖ Cancel", key=f"prop_cancel_{idx}",
                width="stretch",
                on_click=_cb_cancel_edit, args=(title,),
            )
        with sc3:
            st.markdown(
                f'<div style="text-align:center;font-size:.7rem;color:#64748b;padding-top:8px">'
                f'{_wc_live}w</div>',
                unsafe_allow_html=True,
            )

    # ── READ MODE ──────────────────────────────────────────────────────
    else:
        preview = content[:320] + ("..." if len(content) > 320 else "")
        st.markdown(
            f'<div style="font-size:.8rem;line-height:1.7;color:#94a3b8;'
            f'border-left:2px solid #1e293b;padding-left:10px;margin-bottom:10px;">'
            f'{preview}</div>',
            unsafe_allow_html=True,
        )

        # ── Action row: 4 buttons ───────────────────────────────────
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1:
            st.button(
                "✏️ Edit", key=f"prop_edit_{idx}",
                width="stretch",
                on_click=_cb_enter_edit, args=(title,),
            )
        with ac2:
            ai_label = "✨ AI Studio ▲" if is_regen_open else "✨ AI Studio"
            ai_type  = "primary" if is_regen_open else "secondary"
            if ai_client:
                st.button(
                    ai_label, key=f"prop_ai_studio_{idx}",
                    type=ai_type, width="stretch",
                    on_click=_cb_toggle_ai_studio, args=(title,),
                )
        with ac3:
            ref_label = "📎 Reference ▲" if is_ref_open else "📎 Reference"
            ref_type  = "primary" if is_ref_open else "secondary"
            st.button(
                ref_label, key=f"prop_ref_{idx}",
                type=ref_type, width="stretch",
                on_click=_cb_toggle_ref, args=(title,),
            )
        with ac4:
            st.button(
                "↩️ Reset", key=f"prop_reset_{idx}",
                width="stretch", disabled=not is_edited,
                on_click=_cb_reset_section, args=(title,),
            )

    # ── AI STUDIO PANEL ────────────────────────────────────────────────
    if is_regen_open and not is_editing:
        _ai_model  = st.session_state.get("claude_model", "claude-sonnet-4-6")
        _use_claude = (
            isinstance(ai_client, AnthropicAI)
            and not st.session_state.get("_claude_blocked")
        )
        _model_badge = (
            f'<span style="background:rgba(123,97,255,.18);color:#c4b5fd;font-size:.62rem;'
            f'font-weight:700;border-radius:6px;padding:1px 8px;margin-left:8px;letter-spacing:.3px">'
            f'{"⚡ " + _ai_model if _use_claude else "AI"}</span>'
        )
        _stream_badge = (
            '<span style="background:rgba(0,212,170,.12);color:#00d4aa;font-size:.62rem;'
            'font-weight:700;border-radius:6px;padding:1px 8px;margin-left:6px">LIVE STREAM</span>'
            if _use_claude else ""
        )
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#13072e,#1a0533,#0f172a);'
            f'border:1.5px solid #7c3aed;border-radius:12px;padding:16px 18px;margin-top:8px;">'
            f'<div style="display:flex;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:.82rem;font-weight:800;color:#a78bfa;letter-spacing:.5px">✨ AI Studio</span>'
            f'{_model_badge}{_stream_badge}</div>'
            f'<div style="font-size:.72rem;color:#64748b;margin-bottom:12px">'
            f'Describe any change — tables, tone, structure, content — Claude rewrites it live, word by word</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="font-size:.7rem;font-weight:700;color:#7c3aed;letter-spacing:.5px;text-transform:uppercase;margin-bottom:6px">Quick Instructions</div>', unsafe_allow_html=True)

        chip_cols = st.columns(3)
        for ci, (chip_label, chip_prompt) in enumerate(_REGEN_CHIPS):
            with chip_cols[ci % 3]:
                is_active = regen_prompts.get(title, "") == chip_prompt
                btn_style = "primary" if is_active else "secondary"
                st.button(
                    chip_label, key=f"chip_{idx}_{ci}",
                    width="stretch", type=btn_style,
                    on_click=_cb_set_chip, args=(title, chip_prompt),
                )

        st.markdown('<div style="margin-top:12px;font-size:.7rem;font-weight:700;color:#7c3aed;letter-spacing:.5px;text-transform:uppercase;margin-bottom:4px">Or Write Your Own</div>', unsafe_allow_html=True)

        current_prompt = regen_prompts.get(title, "")
        new_prompt = st.text_area(
            "Instructions",
            value=current_prompt,
            height=90,
            placeholder='e.g. "Add a table comparing on-premises vs cloud costs" or "Include 3 bullet points about security compliance" or "Rewrite for a healthcare client audience"',
            key=f"regen_prompt_area_{idx}",
            label_visibility="collapsed",
        )
        regen_prompts[title] = new_prompt

        # If reference doc is loaded, offer inject checkbox
        if ref_texts.get(title):
            ref_filename = ref_names.get(title, "reference doc")
            use_ref = st.checkbox(
                f'📎 Inject "{ref_filename}" as AI context',
                value=ref_use_ctx.get(title, False),
                key=f"ref_use_{idx}",
            )
            ref_use_ctx[title] = use_ref
            if use_ref:
                st.markdown(
                    '<div style="font-size:.68rem;color:#f97316;margin-top:2px;margin-bottom:6px">'
                    '📎 Reference content will be passed to AI along with your instructions</div>',
                    unsafe_allow_html=True,
                )

        _prompt_area_key = f"regen_prompt_area_{idx}"
        gc1, gc2, gc3 = st.columns([3, 2, 2])
        with gc1:
            _live_prompt = st.session_state.get(_prompt_area_key, new_prompt)
            char_count = len(_live_prompt)
            hint = f"{char_count} chars · Will rewrite \"{title[:28]}{'...' if len(title)>28 else ''}\""
            st.markdown(f'<div style="font-size:.68rem;color:#475569;padding-top:10px">{hint}</div>', unsafe_allow_html=True)
        with gc2:
            st.button(
                "✖ Close", key=f"regen_close_{idx}",
                width="stretch",
                on_click=_cb_close_ai_studio, args=(title,),
            )
        with gc3:
            gen_disabled = not new_prompt.strip()
            _already_queued = title in st.session_state.get("proposal_regen_loading", set())
            _gen_label = "⏳ Queued…" if _already_queued else "✨ Generate"
            st.button(
                _gen_label, key=f"regen_go_{idx}",
                type="primary", width="stretch",
                disabled=gen_disabled or _already_queued,
                on_click=_cb_generate, args=(title, _prompt_area_key),
            )

        if not new_prompt.strip():
            st.markdown('<div style="font-size:.7rem;color:#f59e0b;margin-top:4px">👆 Select a quick instruction or type your own, then click Generate</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── REFERENCE PANEL ────────────────────────────────────────────────
    if is_ref_open and not is_editing:
        import streamlit.components.v1 as _comp

        # Grab original source document from session state
        _orig_text      = st.session_state.get("_extracted_text", "")
        _orig_filenames = st.session_state.get("_extracted_filenames", [])
        _orig_fname     = ", ".join(_orig_filenames) if _orig_filenames else "Source Document"

        st.markdown(
            '<div style="background:linear-gradient(135deg,#1a0d00,#1c1000,#0f172a);'
            'border:1.5px solid #f97316;border-radius:12px;padding:16px 18px;margin-top:8px;">'
            '<div style="font-size:.82rem;font-weight:800;color:#fb923c;margin-bottom:2px;letter-spacing:.5px">📎 Reference Document</div>'
            '<div style="font-size:.72rem;color:#64748b;margin-bottom:14px">'
            'Paragraphs that match this section are highlighted — green = high relevance, blue = some relevance'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Source selector: original doc OR custom upload ───────────
        _ref_source_key = f"_ref_source_{idx}"
        _ref_source = st.session_state.get(_ref_source_key, "original")

        src_col1, src_col2 = st.columns(2)
        with src_col1:
            orig_disabled = not bool(_orig_text)
            orig_btn_type = "primary" if _ref_source == "original" else "secondary"
            if st.button(
                f'📄 Original Doc{(" · " + _orig_filenames[0][:20] + "…") if _orig_filenames else ""}',
                key=f"ref_src_orig_{idx}",
                type=orig_btn_type,
                width="stretch",
                disabled=orig_disabled,
            ):
                st.session_state[_ref_source_key] = "original"
                # Clear any custom upload so we show original
                ref_texts.pop(title, None)
                ref_names.pop(title, None)
                st.rerun(scope="fragment")
        with src_col2:
            custom_btn_type = "primary" if _ref_source == "custom" else "secondary"
            if st.button(
                "📂 Upload Different Doc",
                key=f"ref_src_custom_{idx}",
                type=custom_btn_type,
                width="stretch",
            ):
                st.session_state[_ref_source_key] = "custom"
                st.rerun(scope="fragment")

        # ── Resolve which text/name to display ───────────────────────
        _active_source = st.session_state.get(_ref_source_key, "original")

        if _active_source == "custom":
            uploaded = st.file_uploader(
                "Upload reference document",
                type=["pdf", "docx", "pptx", "xlsx", "xls", "txt", "md"],
                key=f"ref_upload_{idx}",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                try:
                    from modules.document_processor import DocProcessor as _DocProc
                    extracted = _DocProc().extract(uploaded)
                    ref_texts[title] = extracted
                    ref_names[title] = uploaded.name
                except Exception as ex:
                    st.error(f"Could not extract text: {ex}")
            display_text = ref_texts.get(title, "")
            display_name = ref_names.get(title, "Uploaded Document")
        else:
            # Use the original proposal source document
            display_text = _orig_text
            display_name = _orig_fname
            # Also keep ref_texts populated so AI Studio inject works
            if display_text:
                ref_texts[title] = display_text
                ref_names[title] = display_name

        # ── Show the document viewer ──────────────────────────────────
        if display_text:
            wc_ref = len(display_text.split())
            pc_ref = len([p for p in display_text.replace('\r', '').split('\n') if p.strip()])

            # Source document tag
            src_tag = (
                '<span style="background:rgba(249,115,22,.15);color:#f97316;font-size:.65rem;'
                'font-weight:700;border-radius:8px;padding:1px 8px;margin-left:8px">SOURCE</span>'
                if _active_source == "original" else
                '<span style="background:rgba(0,180,216,.15);color:#00b4d8;font-size:.65rem;'
                'font-weight:700;border-radius:8px;padding:1px 8px;margin-left:8px">CUSTOM</span>'
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin:10px 0 8px;">'
                f'<span style="font-size:.75rem;color:#fb923c;font-weight:700;max-width:260px;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">📄 {display_name}</span>'
                f'{src_tag}'
                f'<span style="font-size:.7rem;color:#475569;margin-left:auto">{wc_ref:,} words · {pc_ref} paragraphs</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            html_ref = _reference_doc_html(display_text, content, display_name)
            _comp.html(html_ref, height=520, scrolling=True)

            if is_regen_open:
                st.markdown(
                    '<div style="margin-top:8px;font-size:.72rem;color:#fb923c;">'
                    '💡 AI Studio is open — tick "Inject as AI context" there to use this document in regeneration'
                    '</div>',
                    unsafe_allow_html=True,
                )
        else:
            if _active_source == "original":
                st.markdown(
                    '<div style="text-align:center;padding:24px 0;font-size:.78rem;color:#475569;">'
                    '⚠️ No source document found. Run the pipeline first or switch to "Upload Different Doc".'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="text-align:center;padding:24px 0;font-size:.78rem;color:#334155;">'
                    '📂 Upload a document above to see relevance-highlighted content'
                    '</div>',
                    unsafe_allow_html=True,
                )

        # Close button
        if st.button("✖ Close Reference", key=f"ref_close_{idx}", width="stretch"):
            ref_show.discard(title)
            st.rerun(scope="fragment")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def _md_to_html(text: str) -> str:
    """Convert simple markdown text to HTML paragraphs/lists."""
    lines = text.strip().split("\n")
    html = ""
    in_list = False
    for line in lines:
        s = line.strip()
        if s.startswith("- ") or s.startswith("• "):
            if not in_list:
                html += "<ul>"
                in_list = True
            html += f"<li>{s[2:]}</li>"
        else:
            if in_list:
                html += "</ul>"
                in_list = False
            if s:
                html += f"<p>{s}</p>"
    if in_list:
        html += "</ul>"
    return html


def _html_tbl(headers, rows, col_widths=None) -> str:
    """Build an HTML table with ECI styling."""
    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="tbl"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'


def _proposal_live_preview_html(sections: list, r: dict = None):
    """Full HTML document matching the PDF: narrative sections + Requirements + Time + Cost + Risk + Architecture + Scope."""
    edits = st.session_state.get("proposal_edits", {})
    client_name = (st.session_state.get("proposal_client_name", "")
                   or st.session_state.get("client_name", "")
                   or "Client")
    contact_name = st.session_state.get("proposal_contact_name", "") or ""
    date_str = st.session_state.get("proposal_proposal_date", "") or datetime.now().strftime("%B %d, %Y")

    r = r or {}
    se = safe_dict(r.get("semantic_analysis"))
    te = safe_dict(r.get("time_estimate"))
    ce = safe_dict(r.get("cost_estimate"))
    ri = safe_dict(r.get("risk_assessment"))
    ar = safe_dict(r.get("architecture"))
    sc = safe_dict(r.get("scope"))

    # ── KPI banner (cover) ──
    kpis = [
        (str(len(safe_list(se.get("requirements")))), "Requirements"),
        (str(safe_int(te.get("total_hours"))), "Total Hours"),
        ("$" + str(safe_int(ce.get("total_monthly_cost"))) + "/mo", "Infra Cost"),
        (safe_str(ri.get("overall_level", "N/A")), "Risk Level"),
    ]
    kpi_html = "".join(
        f'<div style="background:rgba(255,255,255,.15);border-radius:8px;padding:10px 18px;text-align:center;min-width:90px">'
        f'<div style="font-size:18px;font-weight:800;color:#fff">{v}</div>'
        f'<div style="font-size:10px;color:rgba(255,255,255,.7);margin-top:2px">{l}</div></div>'
        for v, l in kpis
    )

    # ── AI narrative sections (editable) ──
    narrative_html = ""
    for sec in sections:
        title = safe_str(sec.get("title", ""))
        content = edits.get(title, safe_str(sec.get("content", "")))
        narrative_html += f'<div class="sec"><h2>{title}</h2><div class="cnt">{_md_to_html(content)}</div></div>'

    # ── Requirements Summary ──
    reqs = safe_list(se.get("requirements"))
    fn = [x for x in reqs if isinstance(x, dict) and x.get("type") == "functional"]
    nf = [x for x in reqs if isinstance(x, dict) and x.get("type") == "non-functional"]
    ig = [x for x in reqs if isinstance(x, dict) and x.get("type") == "integration"]
    req_summary = f'<p style="font-size:12px;color:#64748b;margin-bottom:8px">Functional: <strong>{len(fn)}</strong> &nbsp;·&nbsp; Non-Functional: <strong>{len(nf)}</strong> &nbsp;·&nbsp; Integration: <strong>{len(ig)}</strong></p>'
    req_rows = [[safe_str(req.get("title")), safe_str(req.get("type")), safe_str(req.get("complexity")), safe_str(req.get("priority", ""))] for req in reqs if isinstance(req, dict)]
    req_section = f'<div class="sec"><h2>Requirements Summary</h2>{req_summary}{_html_tbl(["Requirement", "Type", "Complexity", "Priority"], req_rows[:30]) if req_rows else "<p>No requirements data.</p>"}</div>'

    # ── Time Estimation ──
    time_meta = (
        f'<p><strong>Total Hours:</strong> {safe_int(te.get("total_hours"))} &nbsp;·&nbsp; '
        f'<strong>Duration:</strong> {safe_str(te.get("duration_weeks"))} &nbsp;·&nbsp; '
        f'<strong>Confidence:</strong> {safe_str(te.get("confidence"))} &nbsp;·&nbsp; '
        f'<strong>Buffer:</strong> {safe_str(te.get("buffer"))}</p>'
    )
    phase_rows = [[safe_str(safe_dict(p).get("name")), str(safe_int(safe_dict(p).get("hours"))), safe_str(safe_dict(p).get("percentage")), safe_str(safe_dict(p).get("week_label", ""))] for p in safe_list(te.get("phases")) if isinstance(p, dict)]
    ms_rows = [[safe_str(safe_dict(m).get("name")), "Week " + str(safe_int(safe_dict(m).get("week"))), safe_str(safe_dict(m).get("description", ""))] for m in safe_list(te.get("milestones")) if isinstance(m, dict)]
    time_section = (
        f'<div class="sec"><h2>Time Estimation</h2>{time_meta}'
        + (_html_tbl(["Phase", "Hours", "% of Total", "Timeline"], phase_rows) if phase_rows else "")
        + ('<h3 style="font-size:12px;color:#0078d4;margin:14px 0 6px">Key Milestones</h3>' + _html_tbl(["Milestone", "Week", "Description"], ms_rows) if ms_rows else "")
        + '</div>'
    )

    # ── Infrastructure Cost ──
    cost_meta = (
        f'<p><strong>Monthly:</strong> ${safe_int(ce.get("total_monthly_cost"))} &nbsp;·&nbsp; '
        f'<strong>Annual:</strong> ${safe_int(ce.get("total_annual_cost"))}</p>'
    )
    cost_rows = [[safe_str(safe_dict(s).get("service")), safe_str(safe_dict(s).get("tier", "")), "$" + str(safe_int(safe_dict(s).get("monthly_cost"))), safe_str(safe_dict(s).get("description", ""))[:60]] for s in safe_list(ce.get("azure_costs")) if isinstance(s, dict)]
    cost_section = f'<div class="sec"><h2>Infrastructure Cost Estimate</h2>{cost_meta}{_html_tbl(["Service", "Tier", "Monthly Cost", "Notes"], cost_rows) if cost_rows else "<p>No cost data.</p>"}</div>'

    # ── Risk Assessment ──
    risk_meta = f'<p><strong>Overall Score:</strong> {safe_int(ri.get("overall_score"))}/10 &nbsp;·&nbsp; <strong>Level:</strong> {safe_str(ri.get("overall_level"))}</p>'
    risk_rows = [[safe_str(safe_dict(rk).get("category")), safe_str(safe_dict(rk).get("title")), safe_str(safe_dict(rk).get("severity")), safe_str(safe_dict(rk).get("mitigation", ""))] for rk in safe_list(ri.get("risks")) if isinstance(rk, dict)]
    risk_section = f'<div class="sec"><h2>Risk Assessment</h2>{risk_meta}{_html_tbl(["Category", "Risk", "Severity", "Mitigation"], risk_rows) if risk_rows else "<p>No risk data.</p>"}</div>'

    # ── Architecture Overview ──
    arch_meta = f'<p><strong>Pattern:</strong> {safe_str(ar.get("pattern"))}</p>'
    comp_rows = [[safe_str(safe_dict(c).get("name")), safe_str(safe_dict(c).get("type", "")), safe_str(safe_dict(c).get("azure_service", "")), ", ".join(safe_list(safe_dict(c).get("services", [])))] for c in safe_list(ar.get("components")) if isinstance(c, dict)]
    df = safe_list(ar.get("data_flow"))
    df_html = f'<p style="margin-top:10px"><strong>Data Flow:</strong> {" → ".join(safe_str(x) for x in df)}</p>' if df else ""
    arch_section = f'<div class="sec"><h2>Architecture Overview</h2>{arch_meta}{_html_tbl(["Component", "Type", "Azure Service", "Details"], comp_rows) if comp_rows else ""}{df_html}</div>'

    # ── Scope Definition ──
    def _fmt_scope(item, section="in_scope"):
        if not isinstance(item, dict):
            return safe_str(item)
        if section == "in_scope":
            title = safe_str(item.get("title", "")).strip()
            desc  = safe_str(item.get("description", "")).strip()
            deliv = safe_str(item.get("deliverable", "")).strip()
            main  = (f"<strong>{title}</strong> — {desc}" if title and desc
                     else f"<strong>{title}</strong>" if title else desc)
            sub   = (f"<br><span style='font-size:10.5px;color:#64748b;font-style:italic'>"
                     f"Deliverable: {deliv}</span>") if deliv else ""
            return main + sub
        if section == "out_of_scope":
            return safe_str(item.get("exclusion", item.get("description", item.get("title", "")))).strip() or safe_str(item)
        if section == "assumptions":
            return safe_str(item.get("statement", item.get("description", ""))).strip() or safe_str(item)
        if section == "prerequisites":
            return safe_str(item.get("item", item.get("description", ""))).strip() or safe_str(item)
        return sc_text(item, section)

    def _scope_list(items, section="in_scope"):
        return "<ul>" + "".join(f"<li>{_fmt_scope(x, section)}</li>" for x in items) + "</ul>" if items else "<p>—</p>"

    scope_section = (
        f'<div class="sec"><h2>Scope Definition</h2>'
        f'<p><strong>In Scope:</strong></p>{_scope_list(safe_list(sc.get("in_scope")), "in_scope")}'
        f'<p><strong>Out of Scope:</strong></p>{_scope_list(safe_list(sc.get("out_of_scope")), "out_of_scope")}'
        f'<p><strong>Assumptions:</strong></p>{_scope_list(safe_list(sc.get("assumptions")), "assumptions")}'
        f'<p><strong>Prerequisites:</strong></p>{_scope_list(safe_list(sc.get("prerequisites")), "prerequisites")}'
        f'</div>'
    )

    contact_line = f'Prepared for: <strong>{client_name}</strong>' + (f' &nbsp;·&nbsp; {contact_name}' if contact_name else '')
    project_type = safe_str(se.get("project_type", "Technology Solution"))

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#fff;color:#1e293b;margin:0;padding:0;}}
  .hdr{{background:linear-gradient(135deg,#0078d4,#005a9e);color:#fff;padding:32px 44px 24px;}}
  .hdr h1{{margin:0 0 4px;font-size:22px;font-weight:800;}}
  .hdr .meta{{font-size:12px;opacity:.8;margin-bottom:16px;}}
  .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px;}}
  .body{{padding:28px 44px 40px;}}
  .sec{{margin-bottom:26px;border-bottom:1px solid #e2e8f0;padding-bottom:20px;}}
  .sec:last-child{{border-bottom:none;}}
  h2{{font-size:13px;font-weight:700;color:#0078d4;margin:0 0 10px;text-transform:uppercase;letter-spacing:.5px;border-left:3px solid #0078d4;padding-left:9px;}}
  .cnt p{{margin:0 0 7px;font-size:12px;line-height:1.7;color:#334155;}}
  .cnt ul{{margin:4px 0 8px 18px;padding:0;}}
  .cnt li{{font-size:12px;line-height:1.65;color:#334155;margin-bottom:3px;}}
  p{{margin:0 0 7px;font-size:12px;line-height:1.7;color:#334155;}}
  ul{{margin:4px 0 8px 18px;padding:0;}}
  li{{font-size:12px;line-height:1.65;color:#334155;margin-bottom:3px;}}
  .tbl{{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px;}}
  .tbl th{{background:#0078d4;color:#fff;padding:6px 10px;text-align:left;}}
  .tbl td{{padding:5px 10px;border-bottom:1px solid #e2e8f0;color:#334155;}}
  .tbl tr:nth-child(even){{background:#f8fafc;}}
  .foot{{background:#f8fafc;border-top:1px solid #e2e8f0;padding:12px 44px;text-align:center;font-size:10px;color:#94a3b8;}}
</style></head><body>
<div class="hdr">
  <h1>Business Proposal</h1>
  <div class="meta">{project_type} &nbsp;·&nbsp; {contact_line} &nbsp;·&nbsp; {date_str}</div>
  <div class="kpis">{kpi_html}</div>
</div>
<div class="body">
  {narrative_html}
  {req_section}
  {time_section}
  {cost_section}
  {risk_section}
  {arch_section}
  {scope_section}
</div>
</body></html>"""


def _proposal_download_strip(r: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    r_with_edits = _build_r_with_edits(r)
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        if HAS_REPORTLAB:
            pdf_data = generate_proposal_pdf(r_with_edits)
            if pdf_data:
                st.download_button("📄 Download PDF", data=pdf_data,
                    file_name=f"ECI_Proposal_{ts}.pdf", mime="application/pdf",
                    width="stretch", type="primary", key="prop_dl_pdf")
        else:
            st.button("📄 PDF (install reportlab)", disabled=True, width="stretch", key="prop_dl_pdf_dis")
    with dc2:
        if HAS_PPTX:
            pptx_data = generate_proposal_pptx(r_with_edits)
            if pptx_data:
                st.download_button("📊 Download PPTX", data=pptx_data,
                    file_name=f"ECI_Proposal_{ts}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    width="stretch", type="primary", key="prop_dl_pptx")
        else:
            st.button("📊 PPTX (install python-pptx)", disabled=True, width="stretch", key="prop_dl_pptx_dis")
    with dc3:
        if HAS_REPORTLAB:
            sow_data = generate_sow_pdf(r_with_edits)
            if sow_data:
                st.download_button("📝 Download SOW", data=sow_data,
                    file_name=f"ECI_SOW_{ts}.pdf", mime="application/pdf",
                    width="stretch", type="primary", key="prop_dl_sow")
        else:
            st.button("📝 SOW (install reportlab)", disabled=True, width="stretch", key="prop_dl_sow_dis")


def _ppt_slides_html(r: dict) -> str:
    """World-class HTML presentation — pixel-matched to HS Group ECI template."""
    import json as _json

    se       = safe_dict(r.get("semantic_analysis", {}))
    te       = safe_dict(r.get("time_estimate",     {}))
    ce       = safe_dict(r.get("cost_estimate",     {}))
    ri       = safe_dict(r.get("risk_assessment",   {}))
    ar       = safe_dict(r.get("architecture",      {}))
    sc       = safe_dict(r.get("scope",             {}))
    proposal = safe_dict(r.get("proposal",          {}))
    edits    = st.session_state.get("proposal_edits", {})

    client_name  = (st.session_state.get("proposal_client_name", "")
                    or st.session_state.get("client_name", "")
                    or "Client").strip()
    date_str     = st.session_state.get("proposal_proposal_date","") or datetime.now().strftime("%b %d, %Y")
    project_type = safe_str(se.get("project_type","Enterprise AI Solution"))
    sections_raw = safe_list(proposal.get("sections",[]))

    # ── brand tokens ──────────────────────────────────────────────────────
    C = {
        "navy":  "#161E56",
        "teal":  "#14A0B9",
        "lime":  "#94C11C",
        "near":  "#2A356E",
        "close": "#26284F",
        "wm":    "rgba(155,162,205,0.13)",
        "dot":   "rgba(148,193,28,0.85)",
    }

    def _e(s): return safe_str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

    def _sec_text(kw):
        for s in sections_raw:
            t = safe_str(s.get("title",""))
            if kw.lower() in t.lower():
                return edits.get(t, safe_str(s.get("content","")))
        return ""

    # ══════════════════════════════════════════════════════════════════════
    #  SHARED FRAGMENTS
    # ══════════════════════════════════════════════════════════════════════

    def wm():
        """ECI⁺ watermark grid: 6 cols × 5 rows with cross marks between."""
        out = '<div class="wm">'
        for row in range(5):
            for col in range(6):
                x = col * 19.5 - 1
                y = row * 20 - 1
                # ECI text
                out += (f'<span style="position:absolute;left:{x:.1f}%;top:{y:.1f}%;'
                        f'font-size:clamp(14px,2.8vw,40px);font-weight:900;'
                        f'color:{C["wm"]};letter-spacing:2px;user-select:none;'
                        f'white-space:nowrap;line-height:1">ECI</span>')
                # cross mark between instances
                cx = x + 9.5
                cy = y + 7
                out += (f'<span style="position:absolute;left:{cx:.1f}%;top:{cy:.1f}%;'
                        f'font-size:clamp(7px,1.3vw,18px);color:rgba(148,193,28,0.10);'
                        f'user-select:none;line-height:1">✚</span>')
        return out + '</div>'

    def cluster(side="right"):
        """Top-left colored square cluster. side = logo side (right or left)."""
        logo_x = "right:1.2%" if side == "right" else "left:1.2%"
        logo_c = C["navy"]
        return (
            # teal small
            f'<div style="position:absolute;left:0.4%;top:6%;'
            f'width:4.2%;padding-top:5.8%;background:{C["teal"]};z-index:4"></div>'
            # lime medium
            f'<div style="position:absolute;left:5%;top:8%;'
            f'width:7.8%;padding-top:11.2%;background:{C["lime"]};z-index:4"></div>'
            # navy square
            f'<div style="position:absolute;left:13%;top:0.5%;'
            f'width:13.5%;padding-top:19%;background:{C["navy"]};z-index:4"></div>'
            # navy wide rect
            f'<div style="position:absolute;left:26.5%;top:0%;'
            f'width:18.5%;padding-top:19%;background:{C["navy"]};z-index:4"></div>'
            # ECI+ logo
            f'<div style="position:absolute;{logo_x};top:1%;z-index:7;'
            f'font-size:clamp(12px,1.6vw,24px);font-weight:900;color:{logo_c};'
            f'font-family:inherit;letter-spacing:-0.5px;line-height:1">'
            f'ECI<sup style="font-size:52%;color:{C["teal"]}">+</sup></div>'
        )

    def cluster_logo_left():
        return (
            f'<div style="position:absolute;left:0.4%;top:6%;'
            f'width:4.2%;padding-top:5.8%;background:{C["teal"]};z-index:4"></div>'
            f'<div style="position:absolute;left:5%;top:8%;'
            f'width:7.8%;padding-top:11.2%;background:{C["lime"]};z-index:4"></div>'
            f'<div style="position:absolute;left:13%;top:0.5%;'
            f'width:13.5%;padding-top:19%;background:{C["navy"]};z-index:4"></div>'
            f'<div style="position:absolute;left:26.5%;top:0%;'
            f'width:18.5%;padding-top:19%;background:{C["navy"]};z-index:4"></div>'
            f'<div style="position:absolute;left:1.5%;top:1.2%;z-index:7;'
            f'font-size:clamp(12px,1.6vw,24px);font-weight:900;color:{C["navy"]};'
            f'font-family:inherit;letter-spacing:-0.5px;line-height:1">'
            f'ECI<sup style="font-size:52%;color:{C["teal"]}">+</sup></div>'
        )

    def bot_deco():
        return (
            f'<div style="position:absolute;left:0.4%;bottom:3.5%;'
            f'width:2.8%;padding-top:4%;background:{C["teal"]};z-index:4"></div>'
            f'<div style="position:absolute;left:3.6%;bottom:1.2%;'
            f'width:5.5%;padding-top:8%;background:{C["navy"]};z-index:4"></div>'
            f'<div style="position:absolute;left:36.5%;bottom:5.5%;'
            f'width:5%;padding-top:7.5%;background:{C["lime"]};z-index:4"></div>'
        )

    def right_deco():
        """Dark navy panels on right — section divider slides."""
        return (
            f'<div style="position:absolute;right:0%;top:3%;'
            f'width:27%;padding-top:44%;background:{C["navy"]};z-index:2"></div>'
            f'<div style="position:absolute;right:0%;top:48%;'
            f'width:18%;padding-top:38%;background:{C["near"]};z-index:2"></div>'
        )

    def circle_base(title_html):
        """Large navy circle (left) + small lime circle."""
        return (
            # big navy circle
            f'<div style="position:absolute;left:0.8%;top:11%;'
            f'width:39%;padding-top:39%;background:{C["navy"]};border-radius:50%;z-index:3"></div>'
            # lime accent circle
            f'<div style="position:absolute;left:1.5%;bottom:5.5%;'
            f'width:7%;padding-top:7%;background:{C["lime"]};border-radius:50%;z-index:5"></div>'
            # circle title overlay
            f'<div style="position:absolute;left:0.8%;top:11%;width:39%;height:39%;z-index:6;'
            f'display:flex;align-items:center;justify-content:center;text-align:center;padding:0 3.5%">'
            f'<span style="font-size:clamp(14px,2.6vw,36px);font-weight:900;color:#fff;'
            f'line-height:1.2;font-family:inherit">{title_html}</span></div>'
        )

    def arrow_item(text, bold_part=None, size="clamp(9px,1.05vw,14px)"):
        txt = _e(safe_str(text))
        # Auto-detect "Bold part – rest" pattern
        if " – " in txt:
            parts = txt.split(" – ", 1)
            inner = f'<b style="font-weight:700">{parts[0]}</b> &ndash; {parts[1]}'
        elif " - " in txt:
            parts = txt.split(" - ", 1)
            inner = f'<b style="font-weight:700">{parts[0]}</b> - {parts[1]}'
        else:
            inner = txt
        return (f'<div style="display:flex;gap:9px;align-items:flex-start;margin-bottom:8px">'
                f'<span style="color:{C["lime"]};font-size:1.1em;flex-shrink:0;margin-top:1px;'
                f'line-height:1.4">&#x27A4;</span>'
                f'<span style="font-size:{size};color:#222;line-height:1.55">{inner}</span>'
                f'</div>')

    def check_item(text, size="clamp(9px,1.05vw,14px)"):
        txt = _e(safe_str(text))
        return (f'<div style="display:flex;gap:9px;align-items:flex-start;margin-bottom:9px">'
                f'<span style="color:{C["lime"]};font-size:1.15em;flex-shrink:0;margin-top:0px;'
                f'line-height:1.45">&#x2610;</span>'
                f'<span style="font-size:{size};color:#222;line-height:1.55">{txt}</span>'
                f'</div>')

    # ══════════════════════════════════════════════════════════════════════
    #  SLIDE BUILDERS
    # ══════════════════════════════════════════════════════════════════════

    def S_COVER():
        display_name = _e(client_name) if client_name not in ("", "Client") else _e(project_type)
        subtitle2    = _e(project_type) if client_name not in ("", "Client") else "AI Solution Proposal"
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}
            <!-- ECI logo top-left -->
            <div style="position:absolute;left:2%;top:2%;z-index:7;
                 font-size:clamp(14px,1.9vw,28px);font-weight:900;color:{C['navy']};letter-spacing:-0.5px">
              ECI<sup style="font-size:52%;color:{C['teal']}">+</sup>
            </div>
            <!-- checkerboard right -->
            <div style="position:absolute;right:0%;top:20%;width:17%;padding-top:29%;background:{C['navy']};z-index:2"></div>
            <div style="position:absolute;right:17%;top:20%;width:17%;padding-top:29%;background:#fff;z-index:2;border:1.5px solid #e8eaf0"></div>
            <div style="position:absolute;right:0%;top:50%;width:17%;padding-top:29%;background:#fff;z-index:2;border:1.5px solid #e8eaf0"></div>
            <div style="position:absolute;right:17%;top:50%;width:17%;padding-top:29%;background:{C['navy']};z-index:2"></div>
            <!-- Main heading block -->
            <div style="position:absolute;left:3.5%;top:20%;width:60%;z-index:5">
              <div style="font-size:clamp(24px,4.8vw,66px);font-weight:900;color:{C['navy']};
                   line-height:1.08;letter-spacing:-1px;font-family:inherit">{display_name}</div>
              <div style="width:10%;height:3.5px;background:{C['navy']};margin:4% 0 2%"></div>
              <div style="font-size:clamp(11px,1.35vw,19px);font-weight:700;color:{C['lime']};
                   margin-bottom:3px;letter-spacing:0.2px">AI Solution Proposal</div>
              <div style="font-size:clamp(11px,1.35vw,19px);font-weight:700;color:{C['lime']};
                   letter-spacing:0.2px">{subtitle2}</div>
              <div style="font-size:clamp(10px,1.1vw,15px);color:#555;margin-top:4%;
                   font-weight:400">{_e(date_str)}</div>
            </div>
          </div>
        </div>"""

    def S_AGENDA(items):
        rows = "".join(
            f'<div style="display:flex;gap:14px;padding:6px 0;border-bottom:1px solid #eef0f4;align-items:baseline">'
            f'<span style="font-size:clamp(11px,1.3vw,17px);font-weight:800;color:{C["navy"]};'
            f'min-width:22px;flex-shrink:0">{i+1}.</span>'
            f'<span style="font-size:clamp(11px,1.2vw,16px);color:#1a1a2e;font-weight:500;'
            f'letter-spacing:0.1px">{_e(item)}</span>'
            f'</div>'
            for i, item in enumerate(items)
        )
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{cluster()}{bot_deco()}
            <!-- Square navy box left -->
            <div style="position:absolute;left:4.5%;top:17%;width:35%;padding-top:57%;
                 background:{C['navy']};z-index:3"></div>
            <div style="position:absolute;left:4.5%;top:17%;width:35%;height:57%;z-index:6;
                 display:flex;align-items:center;justify-content:center">
              <span style="font-size:clamp(20px,3.8vw,52px);font-weight:900;color:#fff;
                   font-family:inherit;letter-spacing:-0.5px">Agenda</span>
            </div>
            <!-- Right: numbered list -->
            <div style="position:absolute;left:43%;top:17%;width:53%;z-index:5;padding-right:3%">
              {rows}
            </div>
          </div>
        </div>"""

    def S_SECTION(title):
        title_html = _e(title).replace("\\n","<br>").replace("\n","<br>").replace("&amp;","&amp;")
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{cluster()}{bot_deco()}{right_deco()}
            <!-- Main navy content block -->
            <div style="position:absolute;left:4.5%;top:17%;width:64%;padding-top:55%;
                 background:{C['navy']};z-index:3"></div>
            <div style="position:absolute;left:6.5%;top:17%;width:60%;height:55%;z-index:5;
                 display:flex;align-items:center;padding:0 2%">
              <span style="font-size:clamp(20px,4vw,56px);font-weight:900;color:#fff;
                   line-height:1.15;font-family:inherit">{title_html}</span>
            </div>
          </div>
        </div>"""

    def S_CIRCLE(title, items, checkbox=True):
        t_html = _e(title).replace("\n","<br>")
        content = "".join(
            check_item(safe_str(x)) if checkbox else arrow_item(safe_str(x))
            for x in items[:9]
        )
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{cluster_logo_left()}
            {circle_base(t_html)}
            <div style="position:absolute;left:43%;top:9%;width:54%;height:86%;
                 overflow:hidden;z-index:5;padding-right:2%">
              {content}
            </div>
          </div>
        </div>"""

    def S_CIRCLE_HEADER(title, header, items, challenges=None):
        t_html     = _e(title).replace("\n","<br>")
        hdr_html   = _e(header)
        arrow_rows = "".join(arrow_item(safe_str(x)) for x in items[:5])
        ch_block   = ""
        if challenges:
            ch_rows = "".join(arrow_item(safe_str(x),size="clamp(9px,1vw,13px)") for x in challenges[:4])
            ch_block = (
                f'<div style="font-size:clamp(10px,1.1vw,15px);font-weight:700;color:{C["navy"]};'
                f'margin:9px 0 5px;display:flex;gap:8px;align-items:center">'
                f'<span style="color:{C["lime"]}">&#x2022;</span> Existing Challenges</div>'
                + ch_rows
            )
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{cluster_logo_left()}
            {circle_base(t_html)}
            <div style="position:absolute;left:43%;top:7%;width:54%;height:90%;
                 overflow:hidden;z-index:5;padding-right:2%">
              <div style="font-size:clamp(10px,1.1vw,15px);color:#333;line-height:1.55;
                   margin-bottom:9px;font-weight:400">{hdr_html}</div>
              {arrow_rows}{ch_block}
            </div>
          </div>
        </div>"""

    def S_TEAM(team_items, dur_items, cost_total):
        def col(hdr, items):
            rows = "".join(check_item(safe_str(x), size="clamp(9px,1.1vw,14px)") for x in items)
            return (
                f'<div style="flex:1;padding:0 3%;border-right:1px solid #eef0f4;text-align:center">'
                f'<div style="font-size:clamp(14px,2.1vw,28px);font-weight:900;color:{C["navy"]};'
                f'margin-bottom:4px">{_e(hdr)}</div>'
                f'<div style="height:3px;background:{C["lime"]};width:65%;margin:0 auto 14px"></div>'
                f'<div style="text-align:left">{rows}</div>'
                f'</div>'
            )
        cols = (col("Team", team_items)
                + col("Duration", dur_items)
                + f'<div style="flex:1;padding:0 3%;text-align:center">'
                  f'<div style="font-size:clamp(14px,2.1vw,28px);font-weight:900;color:{C["navy"]};margin-bottom:4px">Cost</div>'
                  f'<div style="height:3px;background:{C["lime"]};width:65%;margin:0 auto 14px"></div>'
                  f'<div style="font-size:clamp(11px,1.3vw,17px);color:{C["navy"]};font-weight:700;'
                  f'line-height:1.5;text-align:center">{_e(safe_str(cost_total)).replace(chr(10),"<br>")}</div>'
                  f'</div>')
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}
            <div style="position:absolute;left:1.5%;top:1%;z-index:7;
                 font-size:clamp(12px,1.6vw,24px);font-weight:900;color:{C['navy']}">
              ECI<sup style="font-size:52%;color:{C['teal']}">+</sup>
            </div>
            <div style="position:absolute;left:1%;top:28%;width:98%;z-index:5;
                 display:flex;gap:0">
              {cols}
            </div>
          </div>
        </div>"""

    def S_INFRA_COST(monthly, annual, svcs):
        svc_rows = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
            f'border-bottom:1px solid #f0f2f5">'
            f'<span style="font-size:clamp(9px,1.02vw,13px);color:#333;'
            f'font-weight:500">{_e(safe_str(safe_dict(s).get("service","")))}</span>'
            f'<span style="font-size:clamp(9px,1.02vw,13px);font-weight:700;'
            f'color:{C["navy"]}">${safe_int(safe_dict(s).get("monthly_cost",0)):,}/mo</span>'
            f'</div>'
            for s in svcs[:8]
        )
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{cluster_logo_left()}
            <div style="position:absolute;left:0.8%;top:11%;width:39%;padding-top:39%;
                 background:{C['navy']};border-radius:50%;z-index:3"></div>
            <div style="position:absolute;left:1.5%;bottom:5.5%;width:7%;padding-top:7%;
                 background:{C['lime']};border-radius:50%;z-index:5"></div>
            <div style="position:absolute;left:0.8%;top:11%;width:39%;height:39%;z-index:6;
                 display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 4%">
              <div style="font-size:clamp(12px,2vw,26px);font-weight:900;color:#fff;line-height:1.2;margin-bottom:8px">Infrastructure<br>Cost</div>
              <div style="font-size:clamp(16px,2.8vw,38px);font-weight:900;color:{C['lime']}">${monthly:,}</div>
              <div style="font-size:clamp(8px,0.9vw,12px);color:rgba(255,255,255,0.75);margin-bottom:4px">per month</div>
              <div style="font-size:clamp(11px,1.3vw,17px);font-weight:700;color:rgba(255,255,255,0.85)">${annual:,} / year</div>
            </div>
            <div style="position:absolute;left:43%;top:9%;width:54%;z-index:5;padding-right:2%">
              {svc_rows}
            </div>
          </div>
        </div>"""

    def S_NEXT_STEPS(items):
        rows = "".join(check_item(safe_str(x), size="clamp(11px,1.3vw,17px)") for x in items)
        dots = "".join(
            f'<div style="position:absolute;left:{51+dx*5.8}%;top:{7+dy*9.5}%;'
            f'width:1.2%;padding-top:1.7%;background:#dde1e8;border-radius:50%;z-index:1"></div>'
            for dy in range(10) for dx in range(9)
        )
        return f"""
        <div class="sl" style="background:#fff">
          <div class="inner">
            {wm()}{dots}
            <div style="position:absolute;left:1.5%;top:1%;z-index:7;
                 font-size:clamp(12px,1.6vw,24px);font-weight:900;color:{C['navy']}">
              ECI<sup style="font-size:52%;color:{C['teal']}">+</sup>
            </div>
            <div style="position:absolute;left:3%;top:12%;width:46%;z-index:5">
              <div style="font-size:clamp(20px,3.8vw,52px);font-weight:900;color:{C['navy']};
                   letter-spacing:-0.5px;margin-bottom:3%">Next Steps</div>
              <div style="width:20%;height:3.5px;background:{C['navy']};margin-bottom:6%"></div>
              {rows}
            </div>
          </div>
        </div>"""

    def S_CONTACT():
        bg = C["close"]
        return f"""
        <div class="sl" style="background:{bg}">
          <div class="inner">
            <!-- decorative quad right -->
            <div style="position:absolute;right:2%;top:16%;width:16%;padding-top:26%;background:{C['navy']};z-index:2"></div>
            <div style="position:absolute;right:18.5%;top:16%;width:16%;padding-top:26%;background:{bg};z-index:2;outline:1px solid #3a3c6a"></div>
            <div style="position:absolute;right:2%;top:44%;width:16%;padding-top:26%;background:{bg};z-index:2;outline:1px solid #3a3c6a"></div>
            <div style="position:absolute;right:18.5%;top:44%;width:16%;padding-top:26%;background:{C['navy']};z-index:2"></div>
            <!-- ECI logo top-right -->
            <div style="position:absolute;right:1.8%;top:1.5%;z-index:7;
                 font-size:clamp(12px,1.6vw,24px);font-weight:900;color:#fff">
              ECI<sup style="font-size:52%;color:{C['teal']}">+</sup>
            </div>
            <!-- vertical divider -->
            <div style="position:absolute;left:18%;top:16%;width:0.25%;height:68%;
                 background:rgba(150,155,210,0.4);z-index:3"></div>
            <!-- contact content -->
            <div style="position:absolute;left:21%;top:18%;width:55%;z-index:5">
              <div style="font-size:clamp(13px,1.7vw,24px);font-weight:700;color:#fff;
                   margin-bottom:6px;letter-spacing:0.2px">Corporate Headquarters</div>
              <div style="font-size:clamp(9px,1.05vw,14px);color:rgba(255,255,255,0.72);
                   line-height:1.8;margin-bottom:18px">
                529 Fifth Avenue, 7th Floor<br>New York, New York 10017
              </div>
              <div style="font-size:clamp(13px,1.7vw,24px);font-weight:700;color:#fff;
                   margin-bottom:6px;letter-spacing:0.2px">Global Sales</div>
              <div style="font-size:clamp(9px,1.05vw,14px);color:rgba(255,255,255,0.72);
                   line-height:2">
                US: +1 800 752 1382 &nbsp;&nbsp;&bull;&nbsp;&nbsp; UK: +44 207 0716802<br>
                Singapore: +65 66222345 &nbsp;&nbsp;&bull;&nbsp;&nbsp; Hong Kong: +852 3189 0101
              </div>
              <div style="margin-top:18px;display:flex;gap:10px">
                <div style="background:{C['teal']};color:#fff;font-size:clamp(8px,0.9vw,12px);
                     padding:4px 14px;border-radius:20px;font-weight:600">www.ecitechnology.com</div>
                <div style="background:{C['lime']};color:#fff;font-size:clamp(8px,0.9vw,12px);
                     padding:4px 14px;border-radius:20px;font-weight:600">info@ecitechnology.com</div>
              </div>
            </div>
          </div>
        </div>"""

    # ══════════════════════════════════════════════════════════════════════
    #  BUILD CONTENT DATA
    # ══════════════════════════════════════════════════════════════════════

    reqs       = safe_list(se.get("requirements", []))
    objectives = safe_list(se.get("business_objectives", []))
    in_scope   = safe_list(sc.get("in_scope", []))
    assumptions= safe_list(sc.get("assumptions", [])) or [
        "Client provides system access and credentials within Week 1",
        "Azure subscription is active with required service quotas allocated",
        "Stakeholders available for sprint reviews and formal UAT sign-off",
        "All requirement changes submitted through formal change-management",
        "Representative sample data provided before development begins",
    ]
    prereqs    = safe_list(sc.get("prerequisites", [])) or [
        "Active Azure subscription with Contributor-level access for ECI",
        "Network/VPN access provisioned for remote development team",
        "Representative sample data available for validation and testing",
        "Signed Statement of Work and project kick-off approval",
        "Key stakeholder contacts and RACI matrix confirmed",
    ]
    comps      = safe_list(ar.get("components", []))
    phases     = safe_list(te.get("phases", []))
    risk_list  = safe_list(ri.get("risks", []))
    svcs       = safe_list(ce.get("azure_costs", []))
    monthly    = safe_int(ce.get("total_monthly_cost", 0))
    annual     = safe_int(ce.get("total_annual_cost", monthly * 12))
    dur_str    = safe_str(te.get("duration_weeks", "")) + " weeks"
    pattern    = safe_str(ar.get("pattern", ""))

    # Scope items — full sentences
    scope_items = [safe_str(x) for x in (objectives[:5] if objectives else in_scope[:6])]
    if not scope_items:
        scope_items = ["Deliver an enterprise-grade AI solution on time and within budget"]

    # Objective items — title + description
    obj_items = []
    for rq in reqs[:4]:
        rd  = safe_dict(rq)
        nm  = safe_str(rd.get("title",""))
        ds  = safe_str(rd.get("description",""))
        obj_items.append((nm + " – " + ds) if ds and ds != nm else nm)

    challenges = [
        "Limited Learning from Documents – Systems summarize but don't extract analytical patterns",
        "Comparative Analysis – Hard to benchmark new submissions against historical data",
        "Missing Data Detection – Identifying gaps in new submissions is manual and error-prone",
        "Trend Extraction – Processing large document volumes for pattern shifts is time-intensive",
    ]

    # Architecture items
    arch_items = []
    for c in comps[:5]:
        cd = safe_dict(c)
        nm = safe_str(cd.get("name",""))
        ds = safe_str(cd.get("description",""))
        arch_items.append((nm + " – " + ds) if ds else nm)

    # Timeline items — with hours and description
    ph_items = []
    for p in phases[:6]:
        pd  = safe_dict(p)
        nm  = safe_str(pd.get("name","Phase"))
        hrs = safe_int(pd.get("hours",0))
        ds  = safe_str(pd.get("description",""))
        ph_items.append(f"{nm} – {hrs} hrs" + (f" · {ds}" if ds else ""))

    # Risk items — with mitigation
    risk_items = []
    for rk in risk_list[:7]:
        rd  = safe_dict(rk)
        nm  = safe_str(rd.get("title",""))
        sev = safe_str(rd.get("severity",""))
        mit = safe_str(rd.get("mitigation",""))
        risk_items.append(f"{nm} [{sev}]" + (f" – {mit}" if mit else ""))
    if not risk_items:
        risk_items = [
            "Integration Complexity [High] – Mitigate with phased rollout and early PoC validation",
            "Timeline Overruns [Medium] – Weekly progress reviews with clear milestone gates",
            "Data Quality Issues [Medium] – Data profiling sprint before core development",
            "Scope Creep [Medium] – Formal change-management and locked sprint backlog",
        ]

    team_items = ["Project Manager", "AI Solutions Architect", "AI/ML Engineer",
                  "Frontend Developer", "QA / Test Engineer"]
    dur_items  = [dur_str, "Discovery → Design → Build → Test → UAT → Go-Live"]
    cost_total = f"Total: US ${annual:,}\n(Infra: ${monthly:,}/mo)"

    # ══════════════════════════════════════════════════════════════════════
    #  ASSEMBLE SLIDES
    # ══════════════════════════════════════════════════════════════════════

    slides = [
        S_COVER(),
        S_AGENDA(["Introduction","Proposed Solution","Implementation Plan",
                  "Assumptions & Risks","Pre-Requisites","Cost","Q&A Session"]),
        S_SECTION("Introduction"),
        S_CIRCLE("Scope", scope_items, checkbox=True),
        S_CIRCLE_HEADER("Objective",
                        "Design and deploy an integrated AI solution:",
                        obj_items, challenges=challenges),
        S_SECTION("Proposed\nSolution"),
        S_CIRCLE_HEADER("Solution\nArchitecture",
                        "Architecture pattern: " + (pattern or project_type),
                        arch_items),
        S_SECTION("Implementation\nPlan"),
        S_CIRCLE_HEADER("Project\nTimeline",
                        f"Total duration: {dur_str} &nbsp;|&nbsp; Key phases &amp; milestones:",
                        ph_items),
        S_SECTION("Assumptions\n&amp; Risks"),
        S_CIRCLE("Assumptions", assumptions, checkbox=True),
        S_CIRCLE("Risks", risk_items, checkbox=False),
        S_SECTION("Pre-Requisites"),
        S_CIRCLE("Pre-Requisites", prereqs, checkbox=True),
        S_SECTION("Defining\nthe How"),
        S_TEAM(team_items, dur_items, cost_total),
        S_INFRA_COST(monthly, annual, svcs),
        S_SECTION("Q&amp;A Session"),
        S_SECTION("Next Steps"),
        S_NEXT_STEPS(["Review proposal and provide written feedback",
                      "Agree on Statement of Work and commercial terms",
                      "Confirm project start date and resource availability",
                      "Project kick-off meeting and team introductions"]),
        S_CONTACT(),
    ]

    n = len(slides)
    slides_markup = "\n".join(
        f'<div id="s{i}" class="sf{"" if i else " active"}">{sl}</div>'
        for i, sl in enumerate(slides)
    )
    dots_markup = "".join(
        f'<div class="dot{"" if i else " active"}" onclick="jump({i})" title="Slide {i+1}"></div>'
        for i in range(n)
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif;
     background:linear-gradient(135deg,#c8d0da,#d8dce6);
     padding:12px 14px;min-height:100vh}}
.sf{{display:none;border-radius:10px;overflow:hidden;
    box-shadow:0 16px 56px rgba(22,30,86,.22),0 4px 18px rgba(0,0,0,.14);
    margin-bottom:5px}}
.sf.active{{display:block;animation:fi .32s ease}}
@keyframes fi{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:translateY(0)}}}}
.sl{{position:relative;width:100%;padding-top:56.25%;overflow:hidden}}
.inner{{position:absolute;inset:0;overflow:hidden}}
.wm{{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:0}}
.nav-bar{{display:flex;align-items:center;justify-content:center;gap:14px;
          margin-top:11px;flex-wrap:wrap}}
.nav-btn{{background:{C["navy"]};color:#fff;border:none;border-radius:8px;
          padding:9px 26px;font-size:13px;font-weight:700;cursor:pointer;
          font-family:inherit;letter-spacing:.3px;transition:background .18s}}
.nav-btn:hover{{background:{C["near"]}}}
.slide-num{{color:#4a5568;font-size:13px;font-weight:700;
            min-width:75px;text-align:center}}
.dots{{display:flex;gap:5px;align-items:center;flex-wrap:wrap;
       justify-content:center;max-width:460px}}
.dot{{width:7px;height:7px;border-radius:50%;background:#c4cadc;
      cursor:pointer;transition:background .2s,transform .2s,width .2s}}
.dot.active{{background:{C["navy"]};width:20px;border-radius:4px}}
.dot:hover:not(.active){{background:{C["teal"]}}}
</style>
</head><body>
{slides_markup}
<div class="nav-bar">
  <button class="nav-btn" onclick="go(-1)">&#8592; Prev</button>
  <span class="slide-num" id="num">1 / {n}</span>
  <button class="nav-btn" onclick="go(1)">Next &#8594;</button>
</div>
<div class="nav-bar" style="margin-top:8px">
  <div class="dots" id="dots">{dots_markup}</div>
</div>
<script>
var c=0,tot={n};
var dots=document.querySelectorAll('.dot');
function go(d){{nav(c,((c+d)%tot+tot)%tot)}}
function jump(i){{nav(c,i)}}
function nav(from,to){{
  document.getElementById('s'+from).classList.remove('active');
  document.getElementById('s'+to).classList.add('active');
  dots[from].classList.remove('active');
  dots[to].classList.add('active');
  c=to;
  document.getElementById('num').textContent=(c+1)+' / '+tot;
}}
document.addEventListener('keydown',function(e){{
  if(e.key==='ArrowRight'||e.key==='ArrowDown')go(1);
  if(e.key==='ArrowLeft'||e.key==='ArrowUp')go(-1);
}});
</script>
</body></html>"""

def _sow_preview_html(r: dict) -> str:
    """Generate a full styled HTML preview of the Statement of Work."""
    se = safe_dict(r.get("semantic_analysis"))
    te = safe_dict(r.get("time_estimate"))
    ce = safe_dict(r.get("cost_estimate"))
    ri = safe_dict(r.get("risk_assessment"))
    sc = safe_dict(r.get("scope"))
    proposal = safe_dict(r.get("proposal"))
    edits = st.session_state.get("proposal_edits", {})

    client_name = st.session_state.get("proposal_client_name", "") or "[Client Name]"
    contact_name = st.session_state.get("proposal_contact_name", "") or ""
    date_str = st.session_state.get("proposal_proposal_date", "") or datetime.now().strftime("%B %d, %Y")
    project_type = safe_str(se.get("project_type", "Technology Solution"))

    exec_summary = ""
    for sec in safe_list(proposal.get("sections")):
        t = safe_str(sec.get("title", ""))
        if "executive" in t.lower() or "overview" in t.lower():
            exec_summary = edits.get(t, safe_str(sec.get("content", "")))
            break

    def _fmt_sc(item, section="in_scope"):
        if not isinstance(item, dict):
            return safe_str(item)
        if section == "in_scope":
            title = safe_str(item.get("title", "")).strip()
            desc  = safe_str(item.get("description", "")).strip()
            deliv = safe_str(item.get("deliverable", "")).strip()
            main  = (f"<strong>{title}</strong> — {desc}" if title and desc
                     else f"<strong>{title}</strong>" if title else desc)
            sub   = (f"<br><span style='font-size:10.5px;color:#64748b;font-style:italic'>"
                     f"Deliverable: {deliv}</span>") if deliv else ""
            return main + sub
        if section == "out_of_scope":
            return safe_str(item.get("exclusion", item.get("description", item.get("title", "")))).strip() or safe_str(item)
        if section in ("assumptions", "prerequisites"):
            return safe_str(item.get("statement", item.get("item", item.get("description", "")))).strip() or safe_str(item)
        return sc_text(item, section)

    def _ul(items, section=""): return "<ul>" + "".join(f"<li>{_fmt_sc(x, section) if section else safe_str(x)}</li>" for x in items) + "</ul>" if items else "<p>—</p>"
    def _tbl(headers, rows): return '<table class="tbl"><thead><tr>' + "".join(f"<th>{h}</th>" for h in headers) + '</tr></thead><tbody>' + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows) + "</tbody></table>"

    kpi_html = "".join(f'<div class="kc"><div class="kv">{v}</div><div class="kl">{l}</div></div>' for v, l in [
        (str(len(safe_list(se.get("requirements")))), "Requirements"),
        (str(safe_int(te.get("total_hours"))), "Hours"),
        (safe_str(te.get("duration_weeks")), "Duration"),
        ("$" + str(safe_int(ce.get("total_monthly_cost"))) + "/mo", "Infra Cost"),
    ])

    assump = safe_list(sc.get("assumptions")) or ["Client will provide timely access to required systems", "Key stakeholders available for reviews", "Requirements are baselined — changes via change management"]
    prereqs = safe_list(sc.get("prerequisites")) or ["Signed Statement of Work", "Azure subscription provisioned", "VPN/network access for development team"]

    phase_rows = [[safe_str(safe_dict(p).get("name")), safe_str(safe_dict(p).get("week_label", "")), str(safe_int(safe_dict(p).get("hours"))) + "h"] for p in safe_list(te.get("phases"))]
    ms_rows = [[safe_str(safe_dict(m).get("name")), "Week " + str(safe_int(safe_dict(m).get("week"))), safe_str(safe_dict(m).get("description", ""))] for m in safe_list(te.get("milestones"))]
    role_rows = [[safe_str(safe_dict(rl).get("name")), str(int(float(safe_dict(rl).get("allocation_pct", 0)) * 100)) + "%", "$" + str(safe_int(safe_dict(rl).get("rate", 100))) + "/hr"] for rl in safe_list(te.get("roles"))]
    cost_rows = [[safe_str(safe_dict(s).get("service")), safe_str(safe_dict(s).get("tier", "")), "$" + str(safe_int(safe_dict(s).get("monthly_cost"))) + "/mo"] for s in safe_list(ce.get("azure_costs"))]
    risk_rows = [[safe_str(safe_dict(rk).get("category")), safe_str(safe_dict(rk).get("title")), safe_str(safe_dict(rk).get("severity")), safe_str(safe_dict(rk).get("mitigation", ""))[:70]] for rk in safe_list(ri.get("risks"))]

    sow_secs = [
        ("1. Project Overview",
         f'<p>{exec_summary or ("This SOW defines scope, deliverables, timeline, and terms for the " + project_type + " project.")}</p>'
         f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:10px 0">{kpi_html}</div>'),
        ("2. Scope of Work",
         f'<strong>In Scope:</strong>{_ul(safe_list(sc.get("in_scope")), "in_scope")}<strong>Out of Scope:</strong>{_ul(safe_list(sc.get("out_of_scope")), "out_of_scope")}'),
        ("3. Deliverables", _tbl(["Phase", "Timeline", "Hours"], phase_rows) if phase_rows else "<p>—</p>"),
        ("4. Timeline & Milestones",
         f'<p>Total: <strong>{safe_int(te.get("total_hours"))}h</strong> · {safe_str(te.get("duration_weeks"))} · Confidence: {safe_str(te.get("confidence"))}</p>'
         + (_tbl(["Milestone", "Week", "Description"], ms_rows) if ms_rows else "")),
        ("5. Team Composition", _tbl(["Role", "Allocation", "Rate"], role_rows) if role_rows else "<p>—</p>"),
        ("6. Infrastructure & Cost",
         f'<p>Monthly: <strong>${safe_int(ce.get("total_monthly_cost"))}</strong> · Annual: <strong>${safe_int(ce.get("total_annual_cost"))}</strong></p>'
         + (_tbl(["Service", "Tier", "Monthly Cost"], cost_rows) if cost_rows else "")),
        ("7. Risk Assessment",
         f'<p>Score: <strong>{safe_int(ri.get("overall_score"))}/10 — {safe_str(ri.get("overall_level"))}</strong></p>'
         + (_tbl(["Category", "Risk", "Severity", "Mitigation"], risk_rows) if risk_rows else "")),
        ("8. Assumptions & Dependencies",
         f'<strong>Assumptions:</strong>{_ul(assump, "assumptions")}<strong>Prerequisites:</strong>{_ul(prereqs, "prerequisites")}'),
        ("9. Acceptance Criteria", _ul([
            "All functional requirements implemented and verified",
            "All integration points tested end-to-end",
            "UAT completed with formal client sign-off",
            "All critical defects resolved prior to go-live",
            "Technical documentation and knowledge transfer complete",
        ])),
        ("10. Change Management",
         "<p>Changes to scope, timeline or deliverables must be submitted in writing. ECI will assess impact within 3 business days. Approved changes tracked in project change log.</p>"),
        ("11. Payment Terms", _tbl(["Milestone", "Trigger", "% of Total"], [
            ["Project Kickoff", "SOW signing", "20%"],
            ["Development Complete", "Core features delivered", "30%"],
            ["UAT Sign-off", "UAT approved by client", "30%"],
            ["Go-Live", "Production deployment", "20%"],
        ])),
        ("12. Signatures", f"""<p>By signing, both parties agree to the terms of this Statement of Work.</p>
        <div style="display:flex;gap:80px;margin-top:24px">
          <div><div style="font-weight:700;color:#1b3a5c;font-size:12px">For: ECI Consulting</div><div style="margin-top:36px;border-top:1px solid #cbd5e1;padding-top:6px;font-size:10px;color:#64748b">Authorised Signature / Date</div></div>
          <div><div style="font-weight:700;color:#1b3a5c;font-size:12px">For: {client_name}</div><div style="margin-top:36px;border-top:1px solid #cbd5e1;padding-top:6px;font-size:10px;color:#64748b">Authorised Signature / Date</div></div>
        </div>"""),
    ]

    sections_html = "".join(f'<div class="sec"><h2>{t}</h2><div class="body">{b}</div></div>' for t, b in sow_secs)
    toc = "<ol>" + "".join(f"<li>{t}</li>" for t, _ in sow_secs) + "</ol>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{{font-family:'Segoe UI',Arial,sans-serif;background:#fff;color:#1e293b;margin:0;padding:0;}}
    .hdr{{background:linear-gradient(135deg,#1b3a5c,#0d2035);color:#fff;padding:28px 44px;}}
    .hdr h1{{margin:0 0 4px;font-size:18px;font-weight:800;}}
    .hdr .meta{{font-size:11px;opacity:.65;}}
    .toc-box{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:14px 22px;margin:18px 44px;}}
    .toc-box .lbl{{font-size:12px;font-weight:700;color:#1b3a5c;margin-bottom:6px;}}
    ol{{margin:0;padding-left:18px;font-size:11px;color:#475569;line-height:1.9;}}
    .dbody{{padding:16px 44px 40px;}}
    .sec{{margin-bottom:24px;border-bottom:1px solid #e2e8f0;padding-bottom:18px;}}
    .sec:last-child{{border-bottom:none;}}
    h2{{font-size:12px;font-weight:700;color:#1b3a5c;margin:0 0 8px;text-transform:uppercase;letter-spacing:.5px;border-left:3px solid #00b4d8;padding-left:9px;}}
    .body p{{font-size:11px;line-height:1.7;color:#334155;margin:0 0 7px;}}
    .body ul{{margin:4px 0 8px 18px;padding:0;}}
    .body li{{font-size:11px;line-height:1.6;color:#334155;margin-bottom:2px;}}
    .tbl{{width:100%;border-collapse:collapse;font-size:10px;margin-top:6px;}}
    .tbl th{{background:#1b3a5c;color:#fff;padding:5px 9px;text-align:left;}}
    .tbl td{{padding:4px 9px;border-bottom:1px solid #e2e8f0;color:#334155;}}
    .tbl tr:nth-child(even){{background:#f8fafc;}}
    .kc{{background:#e8f4fd;border:1px solid #bde4f4;border-radius:6px;padding:8px 14px;text-align:center;}}
    .kv{{font-size:16px;font-weight:800;color:#1b3a5c;}}
    .kl{{font-size:9px;color:#64748b;margin-top:1px;}}
    .foot{{background:#f8fafc;border-top:1px solid #e2e8f0;padding:10px 44px;text-align:center;font-size:10px;color:#94a3b8;}}
    </style></head><body>
    <div class="hdr"><h1>Statement of Work</h1>
    <div class="meta">{project_type}{(" · " + client_name) if client_name != "[Client Name]" else ""}{(" · " + contact_name) if contact_name else ""} · {date_str} · v1.0 · DRAFT</div></div>
    <div class="toc-box"><div class="lbl">Table of Contents</div>{toc}</div>
    <div class="dbody">{sections_html}</div>
    </body></html>"""


@st.fragment
def _proposal_studio_fragment(r: dict, ai_client, sections: list, quality_checks: dict):
    """Entire proposal studio in ONE fragment.

    All Edit / AI Studio / Save / Reset / Generate / tab-switch interactions
    rerun ONLY this fragment — the rest of the app (14 other result tabs, pipeline
    output, etc.) is never touched. Preview, PPTX and SOW caches live here and
    update within the same fragment rerun.
    """
    import streamlit.components.v1 as _stcomp

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  FAST PATH — AI generation in progress
    #  Renders ONLY the generation UI — skips all cards, tabs, preview.
    #  try/finally always clears the loading flag so app can never get stuck.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _regen_loading = st.session_state.setdefault("proposal_regen_loading", set())
    if _regen_loading:
        _gtitle      = next(iter(_regen_loading))
        _gedits      = st.session_state.setdefault("proposal_edits", {})
        _gprompts    = st.session_state.setdefault("proposal_regen_prompt", {})
        _gref_use    = st.session_state.setdefault("proposal_ref_use_ctx", {})
        _gref_text   = st.session_state.setdefault("proposal_ref_text", {})
        _gregen_show = st.session_state.setdefault("proposal_regen_show", set())

        # Resolve section's current content
        _gcontent = _gedits.get(_gtitle, "")
        for _gs in sections:
            _gsd = safe_dict(_gs)
            if safe_str(_gsd.get("title")) == _gtitle:
                _gcontent = _gedits.get(_gtitle, safe_str(_gsd.get("content", "")))
                break

        _ginstr = (
            _gprompts.get(_gtitle, "").strip()
            or f"Rewrite '{_gtitle}' to be more compelling, detailed, and client-focused."
        )
        _gref_ctx = (
            _gref_text.get(_gtitle, "")[:1500]
            if _gref_use.get(_gtitle) and _gref_text.get(_gtitle)
            else ""
        )

        # Determine streaming capability — works for both AnthropicAI and AzureAI
        _claude_ok = isinstance(ai_client, AnthropicAI) and not st.session_state.get("_claude_blocked")
        _can_stream = (
            getattr(ai_client, "is_live", False)
            and hasattr(ai_client, "stream_section_rewrite")
            and (_claude_ok if isinstance(ai_client, AnthropicAI) else True)
        )

        # ── Generation banner + Cancel button ─────────────────────────
        _gmdl = st.session_state.get("claude_model", "claude-sonnet-4-6")
        _bc1, _bc2 = st.columns([5, 1])
        with _bc1:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#13072e,#1a0535,#0f172a);'
                f'border:2px solid #7c3aed;border-radius:14px;padding:16px 20px 12px;">'
                f'<div style="font-size:1rem;font-weight:800;color:#a78bfa;margin-bottom:4px">✨ Rewriting…</div>'
                f'<div style="font-size:.82rem;color:#94a3b8;">'
                f'<span style="color:#e2e8f0;font-weight:700">&ldquo;{_gtitle}&rdquo;</span></div>'
                f'<div style="font-size:.7rem;color:#475569;margin-top:4px">'
                f'{_ginstr[:100]}{"…" if len(_ginstr)>100 else ""}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _bc2:
            if st.button("✖ Cancel", key="_regen_cancel", width="stretch"):
                _regen_loading.discard(_gtitle)
                st.rerun(scope="fragment")
                return

        # ── Generate ───────────────────────────────────────────────────
        _gnew = None
        _rewrite_system = (
            "You are a senior ECI presales consultant and technical writer. "
            "Rewrite the proposal section based on the instructions. "
            "Return ONLY the rewritten text — no JSON, no code fences, no section headings. "
            "Use formal, client-focused, boardroom-quality English."
        )
        _rewrite_parts = [
            f"SECTION: {_gtitle}",
            f"CURRENT CONTENT:\n{_gcontent[:2500]}",
            f"INSTRUCTIONS: {_ginstr}",
        ]
        if _gref_ctx:
            _rewrite_parts.append(f"REFERENCE:\n{_gref_ctx}")
        _rewrite_user = "\n\n".join(_rewrite_parts)

        try:
            if _can_stream:
                # Live streaming — tokens appear as they arrive
                _gnew = st.write_stream(
                    ai_client.stream_section_rewrite(_gtitle, _gcontent, _ginstr, _gref_ctx)
                )
            elif hasattr(ai_client, "call_raw_text") and getattr(ai_client, "is_live", False):
                # Any other AI client — direct focused rewrite, 45s max
                import streamlit.components.v1 as _stcomp_fb
                _stcomp_fb.html(
                    '<div style="display:flex;align-items:center;gap:10px;padding:16px 0;">'
                    '<span style="display:inline-flex;gap:5px">'
                    + "".join(
                        f'<span style="width:9px;height:9px;border-radius:50%;background:#7c3aed;'
                        f'display:inline-block;animation:bp 1.1s ease-in-out {d}s infinite"></span>'
                        for d in ["0", ".18", ".36"]
                    )
                    + '</span><span style="color:#a78bfa;font-size:.8rem;font-family:Segoe UI,sans-serif">'
                    'Generating…</span></div>'
                    '<style>@keyframes bp{0%,100%{transform:scale(.5);opacity:.3}'
                    '50%{transform:scale(1.2);opacity:1}}body{margin:0;background:transparent}</style>',
                    height=56,
                )
                _gnew = ai_client.call_raw_text(_rewrite_system, _rewrite_user, max_tokens=1500)
            else:
                st.warning("No AI provider is configured. Please add an API key in Settings.")
        except Exception as _gex:
            st.error(f"Generation failed: {str(_gex)[:250]}")
        finally:
            _regen_loading.discard(_gtitle)   # ALWAYS clear — never get stuck

        if _gnew and str(_gnew).strip():
            _gedits[_gtitle] = str(_gnew).strip()
            _gprompts.pop(_gtitle, None)
            _gregen_show.discard(_gtitle)
            for _ck in list(st.session_state):
                if _ck.startswith("_prop_html_"):
                    del st.session_state[_ck]
            st.toast(f'"{_gtitle}" rewritten!', icon="✨")
        else:
            if _gnew is not None:
                st.warning("AI returned empty — check API key or try a different prompt.")

        st.rerun(scope="fragment")
        return  # never falls through

    # ── Personalisation & stats (text inputs trigger fragment rerun, not full app) ──
    _proposal_personalization_bar()
    _proposal_stats_bar(sections)

    doc_t1, doc_t2, doc_t3, doc_t4 = st.tabs(
        ["📄 Proposal Document", "📑 Presentation (PPT)", "📝 Statement of Work", "✨ Animated Explainer"]
    )

    # ═══════════════════════════════════════════════════════════════
    #  TAB 1 — Proposal Document
    # ═══════════════════════════════════════════════════════════════
    with doc_t1:
        col_preview, col_edit = st.columns([55, 45])

        with col_preview:
            st.markdown(
                '<div style="font-size:.8rem;font-weight:700;color:#64748b;letter-spacing:1px;'
                'text-transform:uppercase;margin-bottom:8px;">📄 Full Document Preview</div>',
                unsafe_allow_html=True,
            )
            # ── Preview is paused while editing to keep the UI instant ──
            _any_editing = bool(st.session_state.get("proposal_section_edit_mode"))
            if _any_editing:
                st.markdown(
                    '<div style="display:flex;align-items:center;justify-content:center;'
                    'height:220px;border:1.5px dashed #334155;border-radius:14px;'
                    'background:#0b1120;color:#475569;font-size:.82rem;gap:10px;">'
                    '<span style="font-size:1.2rem">✏️</span>'
                    '<span>Preview paused while editing — <b style="color:#64748b">Save</b> or '
                    '<b style="color:#64748b">Cancel</b> to refresh</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                _edit_hash = str(sorted(st.session_state.get("proposal_edits", {}).items()))
                _pers_hash = (
                    str(st.session_state.get("proposal_client_name", ""))
                    + str(st.session_state.get("proposal_contact_name", ""))
                    + str(st.session_state.get("proposal_proposal_date", ""))
                )
                _cache_key = f"_prop_html_{hash(_edit_hash + _pers_hash)}"
                if st.session_state.get(_cache_key) is None:
                    st.session_state[_cache_key] = _proposal_live_preview_html(sections, r)
                html_preview = st.session_state[_cache_key]
                _extra_rows = (
                    len(safe_list(safe_dict(r.get("semantic_analysis")).get("requirements", [])))
                    + len(safe_list(safe_dict(r.get("time_estimate")).get("phases", [])))
                    + len(safe_list(safe_dict(r.get("cost_estimate")).get("azure_costs", [])))
                    + len(safe_list(safe_dict(r.get("risk_assessment")).get("risks", [])))
                )
                preview_h = max(1400, min(3600, len(sections) * 260 + _extra_rows * 22 + 800))
                _stcomp.html(html_preview, height=preview_h, scrolling=True)
                st.download_button(
                    "⬇️ Download HTML Preview",
                    data=html_preview.encode("utf-8"),
                    file_name=f"ECI_Proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    width="stretch",
                    key="prop_dl_html",
                )

        with col_edit:
            st.markdown(
                '<div style="font-size:.8rem;font-weight:700;color:#64748b;letter-spacing:1px;'
                'text-transform:uppercase;margin-bottom:8px;">✏️ Edit &amp; Regenerate Sections</div>',
                unsafe_allow_html=True,
            )
            for i, sec in enumerate(sections):
                _proposal_section_card(safe_dict(sec), i, ai_client, r)
            if st.session_state.get("proposal_edits"):
                st.button(
                    "↩️ Reset All Edits", width="stretch",
                    key="prop_reset_all", on_click=_cb_reset_all_edits,
                )

        st.markdown("---")
        st.markdown(
            '<div style="font-size:.8rem;font-weight:700;color:#64748b;letter-spacing:1px;'
            'text-transform:uppercase;margin-bottom:8px;">⬇️ Download Proposal</div>',
            unsafe_allow_html=True,
        )
        _proposal_download_strip(r)

    # ═══════════════════════════════════════════════════════════════
    #  TAB 2 — Presentation (PPTX)
    # ═══════════════════════════════════════════════════════════════
    with doc_t2:
        st.markdown(
            '<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;'
            'padding:14px 20px;margin-bottom:14px;">'
            '<div style="font-size:.95rem;font-weight:700;color:#e2e8f0;">📑 Presentation Preview</div>'
            '<div style="font-size:.75rem;color:#64748b;margin-top:3px;">'
            'Use Prev / Next to navigate · Arrow keys supported · Generated automatically from your proposal'
            '</div></div>',
            unsafe_allow_html=True,
        )
        import hashlib as _pph, json as _ppj
        _r_edits_ppt = _build_r_with_edits(r)
        _pph_src = _ppj.dumps({
            "se": r.get("semantic_analysis", {}),
            "te": r.get("time_estimate",     {}),
            "ce": r.get("cost_estimate",     {}),
            "ri": r.get("risk_assessment",   {}),
            "sc": r.get("scope",             {}),
            "ar": r.get("architecture",      {}),
            "ed": st.session_state.get("proposal_edits", {}),
        }, sort_keys=True, default=str).encode()
        _ppt_hash  = _pph.md5(_pph_src).hexdigest()[:12]
        _pptx_key  = "_prem_pptx_bytes_" + _ppt_hash
        _html_key  = "_prem_ppt_html_"   + _ppt_hash

        _ref_col, _ = st.columns([1, 5])
        with _ref_col:
            if st.button("🔄 Refresh", key="ppt_tab_refresh",
                         help="Regenerate after editing proposal"):
                for _k in list(st.session_state.keys()):
                    if _k.startswith("_prem_ppt") or _k.startswith("_prem_pptx"):
                        del st.session_state[_k]
                st.rerun(scope="fragment")

        if HAS_PPTX and st.session_state.get(_pptx_key) is None:
            with st.spinner("Building presentation…"):
                try:
                    st.session_state[_pptx_key] = generate_proposal_pptx(_r_edits_ppt)
                except Exception as _pe2:
                    st.session_state[_pptx_key] = b""
                    st.warning(f"PPTX build error: {str(_pe2)[:200]}", icon="⚠️")
        _pptx_bytes_cached = st.session_state.get(_pptx_key) or None

        if st.session_state.get(_html_key) is None:
            try:
                st.session_state[_html_key] = build_premium_pptx_preview_html(
                    r, pptx_bytes=_pptx_bytes_cached)
            except Exception as _pex:
                st.session_state[_html_key] = (
                    "<body style='background:#0a0a1e;color:#f87171;padding:30px;"
                    f"font-family:sans-serif'><b>Preview error:</b> {str(_pex)[:300]}</body>"
                )
        ppt_html = st.session_state[_html_key]
        _stcomp.html(ppt_html, height=660, scrolling=False)

    # ═══════════════════════════════════════════════════════════════
    #  TAB 3 — Statement of Work (with full caching)
    # ═══════════════════════════════════════════════════════════════
    with doc_t3:
        st.markdown(
            '<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;'
            'padding:14px 20px;margin-bottom:14px;">'
            '<div style="font-size:.95rem;font-weight:700;color:#e2e8f0;">'
            '📝 Statement of Work — 12 Sections</div>'
            '<div style="font-size:.75rem;color:#64748b;margin-top:3px;">'
            'Full SOW preview with scope, deliverables, timeline, risk, payment terms &amp; signatures'
            '</div></div>',
            unsafe_allow_html=True,
        )
        # Cache SOW HTML — expensive to regenerate
        _sow_key = f"_sow_html_{id(r)}"
        if st.session_state.get(_sow_key) is None:
            st.session_state[_sow_key] = _sow_preview_html(r)
        sow_html = st.session_state[_sow_key]
        sow_h = max(1100, min(3500,
            len(safe_list(r.get("time_estimate", {}).get("phases", []))) * 120 + 1600))
        _stcomp.html(sow_html, height=sow_h, scrolling=True)

        st.markdown("---")
        st.markdown(
            '<div style="font-size:.8rem;font-weight:700;color:#64748b;letter-spacing:1px;'
            'text-transform:uppercase;margin-bottom:8px;">⬇️ Download SOW</div>',
            unsafe_allow_html=True,
        )
        ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        sc1, sc2 = st.columns(2)
        with sc1:
            if HAS_REPORTLAB:
                # Cache SOW PDF — expensive to generate
                _sow_pdf_key = f"_sow_pdf_{id(r)}"
                if st.session_state.get(_sow_pdf_key) is None:
                    st.session_state[_sow_pdf_key] = generate_sow_pdf(_build_r_with_edits(r))
                sow_pdf = st.session_state.get(_sow_pdf_key)
                if sow_pdf:
                    st.download_button(
                        "📄 Download SOW PDF",
                        data=sow_pdf,
                        file_name=f"ECI_SOW_{ts2}.pdf",
                        mime="application/pdf",
                        width="stretch",
                        type="primary",
                        key="sow_dl_pdf",
                    )
            else:
                st.info("Install `reportlab` to enable PDF download.")
        with sc2:
            st.download_button(
                "🌐 Download SOW HTML",
                data=sow_html.encode("utf-8"),
                file_name=f"ECI_SOW_{ts2}.html",
                mime="text/html",
                width="stretch",
                key="sow_dl_html",
            )

    # ═══════════════════════════════════════════════════════════════
    #  TAB 4 — Animated Explainer
    # ═══════════════════════════════════════════════════════════════
    with doc_t4:
        _se = safe_dict(r.get("semantic_analysis"))
        _te = safe_dict(r.get("time_estimate"))
        _ce = safe_dict(r.get("cost_estimate"))
        _ri = safe_dict(r.get("risk_assessment"))
        _ar = safe_dict(r.get("architecture"))
        render_animated_explainer_tab(r, _se, _te, _ce, _ri, _ar, ai_client)

    # ── Feedback (inside fragment — only reruns fragment) ──────────
    _quick_feedback("proposal", 'e.g. "rewrite executive summary, make it more concise"')


def _render_proposal_tab(r: dict, ai_client):
    proposal = safe_dict(r.get("proposal"))
    sections = safe_list(proposal.get("sections"))
    quality_checks = safe_dict(proposal.get("quality_checks"))

    if not sections:
        _tab_placeholder("📄", "Proposal not generated yet",
                         "Run the full pipeline to generate the client proposal document.")
        return

    st.markdown(
        '<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;'
        'border-radius:14px;padding:20px 28px;margin-bottom:18px;">'
        '<div style="font-size:1.3rem;font-weight:700;color:#e2e8f0;">📄 Proposal Studio</div>'
        '<div style="font-size:.8rem;color:#64748b;margin-top:4px;">'
        'Full preview · Edit · Regenerate · Present · SOW — all in one place</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    _proposal_studio_fragment(r, ai_client, sections, quality_checks)


def _show_regen_diff():
    """Show a Before/After diff panel after a feedback regeneration.
    Includes Accept and Discard buttons — discarding rolls back to the
    snapshot saved in results_before_regen.
    """
    before   = st.session_state.get("results_before_regen")
    sections = st.session_state.get("regen_sections", [])
    if not before or not sections:
        return

    KEY_FIELDS = {
        "time_estimate":   [("total_hours", "Total Hours"), ("duration_weeks", "Duration"), ("confidence", "Confidence")],
        "cost_estimate":   [("total_monthly_cost", "Monthly Cost ($)"), ("total_annual_cost", "Annual Cost ($)")],
        "risk_assessment": [("overall_score", "Risk Score"), ("overall_level", "Risk Level")],
        "architecture":    [("pattern", "Pattern"), ("components", "Components (count)")],
        "scope":           [("in_scope", "In-Scope items"), ("out_of_scope", "Out-of-Scope items")],
        "proposal":        [("sections", "Proposal sections")],
        "semantic_analysis": [("project_type", "Project Type"), ("complexity_score", "Complexity"), ("requirements", "Requirements (count)")],
        "mermaid_diagrams":  [],
    }
    SECTION_RESULT_KEY = {
        "requirements": "semantic_analysis", "time": "time_estimate",
        "cost": "cost_estimate", "risk": "risk_assessment",
        "architecture": "architecture", "scope": "scope",
        "proposal": "proposal", "diagrams": "mermaid_diagrams",
    }

    r_now = st.session_state.processing_results
    with st.expander("🔍 **What Changed — Review & Accept**", expanded=True):
        st.markdown(
            '<div style="background:rgba(0,180,216,.08);border:1px solid #00b4d855;'
            'border-radius:8px;padding:10px 16px;margin-bottom:12px">'
            f'<strong style="color:#00b4d8">Revision complete</strong> — '
            f'{len(sections)} section(s) updated. Review the changes below, then Accept or Discard.</div>',
            unsafe_allow_html=True,
        )

        any_shown = False
        for sec_key in sections:
            rkey   = SECTION_RESULT_KEY.get(sec_key, sec_key)
            fields = KEY_FIELDS.get(rkey, [])
            if not fields:
                continue
            old_data = before.get(rkey, {})
            new_data = r_now.get(rkey, {})
            any_shown = True
            st.markdown(f"**{sec_key.replace('_',' ').title()}**")
            col_b, col_a = st.columns(2)
            with col_b:
                st.markdown("_Before_")
                for fkey, flabel in fields:
                    v = old_data.get(fkey)
                    disp = len(v) if isinstance(v, list) else v
                    st.markdown(f"- {flabel}: `{disp}`")
            with col_a:
                st.markdown("_After_")
                for fkey, flabel in fields:
                    v_new = new_data.get(fkey)
                    v_old = old_data.get(fkey)
                    d_new = len(v_new) if isinstance(v_new, list) else v_new
                    d_old = len(v_old) if isinstance(v_old, list) else v_old
                    changed = d_new != d_old
                    colour  = "#00d4aa" if changed else "#94a3b8"
                    arrow   = "  ◀ changed" if changed else ""
                    st.markdown(
                        f'- {flabel}: <span style="color:{colour};font-weight:bold">`{d_new}`</span>{arrow}',
                        unsafe_allow_html=True,
                    )
            st.markdown("---")

        if not any_shown:
            st.info("Diagrams regenerated — click the Diagrams tab to view.")

        ac1, ac2 = st.columns(2)
        with ac1:
            if st.button("✅ Accept Changes", type="primary", width="stretch", key="fb_accept"):
                st.session_state["results_before_regen"] = None
                st.session_state["regen_sections"]       = []
                show_toast("Changes accepted!", "success")
                st.rerun()
        with ac2:
            if st.button("↩️ Discard — Restore Original", width="stretch", key="fb_discard"):
                st.session_state.processing_results  = before
                st.session_state["results_before_regen"] = None
                st.session_state["regen_sections"]       = []
                show_toast("Changes discarded — original results restored.", "info")
                st.rerun()


def _render_feedback_panel(r):
    """Collapsible feedback panel — Review & Improve with per-section feedback,
    revision history log, and Architect Review badge.
    """
    fl     = [e for e in st.session_state.get("feedback_log", []) if "round" in e]  # round-level entries only
    n_rnds = len(fl)
    badge  = f" `{n_rnds} revision(s) applied`" if n_rnds else ""

    # Pre-populate from quick-feedback widgets (queued via _quick_feedback)
    queued = st.session_state.get("feedback_items", {})

    with st.expander(f"✏️ **Review & Improve** — Give feedback to revise any section{badge}", expanded=bool(queued)):
        st.markdown(
            "Check a section, write your feedback, then click **Apply Feedback**. "
            "Only selected sections are re-generated — everything else stays as-is. "
            "Downstream sections update automatically to stay consistent."
        )

        # ── Per-section inputs ─────────────────────────────────────────
        pending = {}
        cols_left, cols_right = st.columns(2)
        for idx, (key, label, hint) in enumerate(_FEEDBACK_SECTIONS):
            col = cols_left if idx % 2 == 0 else cols_right
            with col:
                # Pre-tick if already queued via quick-feedback
                pre_checked = key in queued
                include = st.checkbox(label, value=pre_checked, key=f"fb_chk_{key}")
                if include:
                    pre_val = queued.get(key, "")
                    val = st.text_area(
                        f"Feedback for {label}",
                        value=pre_val,
                        placeholder=hint,
                        key=f"fb_txt_{key}",
                        height=80,
                        label_visibility="collapsed",
                    )
                    if val.strip():
                        pending[key] = val.strip()

        st.markdown("---")

        # ── Action row ────────────────────────────────────────────────
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            if pending:
                cascade_count = sum(
                    1 for k in {
                        "requirements": ["time","cost","risk","architecture","scope","proposal","diagrams"],
                        "time":         ["cost","risk","scope","proposal"],
                        "cost":         ["risk","proposal"],
                        "risk":         ["proposal"],
                        "architecture": ["proposal","diagrams"],
                        "scope":        ["proposal"],
                        "proposal":     [],
                        "diagrams":     [],
                    }.items()
                    if k[0] in pending
                    for d in k[1]
                    if d not in pending
                )
                st.info(
                    f"**{len(pending)} selected** + ~{cascade_count} auto-cascade "
                    f"→ {', '.join(pending.keys())}"
                )
            else:
                st.caption("Tick a section above and write feedback to enable regeneration.")
        with c2:
            if fl and st.button("📋 Revision Log", width="stretch", key="fb_log_btn"):
                st.session_state["_show_fb_log"] = not st.session_state.get("_show_fb_log", False)
        with c3:
            if st.button(
                "🔄 Apply Feedback",
                disabled=not pending,
                width="stretch",
                type="primary",
                key="fb_apply_btn",
            ) and pending:
                # Clear quick-feedback queue so text areas are fresh after rerun
                st.session_state.feedback_items = {}
                run_pipeline_with_feedback(pending)

        # ── Revision log viewer ───────────────────────────────────────
        if st.session_state.get("_show_fb_log") and fl:
            st.markdown("**Revision History:**")
            for i, entry in enumerate(reversed(fl)):
                rnd    = entry.get("round", n_rnds - i)
                ts     = entry.get("ts", "")
                n_exp  = entry.get("n_explicit", 0)
                n_cas  = entry.get("n_cascade", 0)
                secs   = ", ".join(entry.get("explicit_sections", []))
                st.markdown(
                    f"- **Round {rnd}** ({ts}): "
                    f"{n_exp} explicit ({secs})"
                    + (f" + {n_cas} cascaded" if n_cas else "")
                )

        # ── Architect review badge for the current session ────────────
        run_id = st.session_state.get("_last_run_id")
        if run_id:
            st.markdown("---")
            rev_col1, rev_col2 = st.columns([3, 1])
            with rev_col1:
                rev_notes = st.text_input(
                    "Architect review notes (optional)",
                    placeholder="e.g. 'Reviewed and approved by J. Smith — proceed to client'",
                    key="rev_notes_input",
                )
            with rev_col2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✅ Mark as Architect Reviewed", width="stretch",
                             type="primary", key="btn_mark_reviewed"):
                    _db_mark_reviewed(run_id, notes=rev_notes)
                    notify("run_reviewed", f"Run #{run_id} marked as Architect Reviewed",
                           rev_notes or "Architect sign-off complete", {"run_id": run_id})
                    show_toast("Proposal marked as Architect Reviewed ✅", "success")
                    st.rerun()


def run_pipeline_with_feedback(feedback_items: dict):
    """Re-run affected sections with human reviewer feedback + cascade to dependents.

    feedback_items: {section_key: feedback_text}
    Keys: requirements, time, cost, risk, architecture, scope, proposal, diagrams

    Dependency expansion (e.g. feedback on 'time' also re-runs cost, risk, scope, proposal).
    Uses ai.regenerate_section() so each AI call receives the previous output +
    reviewer note + current dependency context — produces precise, targeted revisions.
    """
    import copy as _copy

    if not st.session_state.get("_extracted_text"):
        st.error("Original document text not found. Please re-upload and process the documents first.")
        return

    # ── Downstream dependency map ──────────────────────────────────────
    DOWNSTREAM = {
        "requirements": ["time", "cost", "risk", "architecture", "scope", "proposal", "diagrams"],
        "time":         ["cost", "risk", "scope", "proposal"],
        "cost":         ["risk", "proposal"],
        "risk":         ["proposal"],
        "architecture": ["diagrams", "proposal"],
        "scope":        ["time", "cost", "risk", "architecture", "diagrams", "proposal"],
        "proposal":     [],
        "diagrams":     [],
    }
    PIPELINE_ORDER = ["requirements", "time", "cost", "risk", "architecture", "scope", "proposal", "diagrams"]

    # Expand: collect all sections that must re-run (explicit + downstream)
    dirty: dict = dict(feedback_items)
    for key in list(feedback_items.keys()):
        for downstream_key in DOWNSTREAM.get(key, []):
            if downstream_key not in dirty:
                # Downstream section — note which upstream change triggered it
                dirty[downstream_key] = f"[auto] upstream '{key}' was revised — ensure consistency"

    # ── Snapshot originals for diff/rollback ──────────────────────────
    r = _copy.deepcopy(st.session_state.processing_results)
    # Normalise total_hours in snapshot to phase-sum so "before" matches what KPIs displayed
    _snap_te = r.get("time_estimate") or {}
    _snap_phases = [p for p in safe_list(_snap_te.get("phases")) if isinstance(p, dict)]
    if _snap_phases:
        _snap_h = sum(int(p.get("hours", 0) or 0) for p in _snap_phases)
        if _snap_h > 0:
            _snap_te["total_hours"] = _snap_h
    st.session_state["results_before_regen"] = _copy.deepcopy(r)
    st.session_state["regen_sections"]       = list(dirty.keys())

    ai     = _pick_ai()
    pb     = st.progress(0)
    status = st.empty()
    total  = len(dirty)
    done   = 0

    # Live dependency refs — updated as each section is revised in order
    semantic = r["semantic_analysis"]
    rag      = r["rag"]
    time_est = r["time_estimate"]
    cost_est = r["cost_estimate"]
    risk     = r["risk_assessment"]
    arch     = r["architecture"]
    scope    = r["scope"]

    for key in PIPELINE_ORDER:
        if key not in dirty:
            continue
        done += 1
        pb.progress(int(done / total * 90))
        label = key.replace("_", " ").title()
        fb    = dirty[key]

        # Build context dict for this section from current (possibly revised) deps
        ctx = {
            "extracted_text_excerpt": st.session_state.get("_extracted_text", "")[:2000],
            "semantic":  semantic,
            "rag":       rag,
            "time_est":  time_est,
            "cost_est":  cost_est,
            "risk":      risk,
            "arch":      arch,
            "scope":     scope,
        }

        # Map section key → current output in results dict
        result_key_map = {
            "requirements": "semantic_analysis",
            "time":         "time_estimate",
            "cost":         "cost_estimate",
            "risk":         "risk_assessment",
            "architecture": "architecture",
            "scope":        "scope",
            "proposal":     "proposal",
            "diagrams":     "mermaid_diagrams",
        }
        rkey    = result_key_map[key]
        original = r.get(rkey, {})

        if "[auto]" in fb:
            status.markdown(f"**Updating {label}** to stay consistent with upstream changes…")
        else:
            status.markdown(f"**Revising {label}** based on your feedback…")

        revised = ai.regenerate_section(key, original, fb, ctx)

        # Apply time sanitizer then recompute all derived fields (duration_weeks, week_label, etc.)
        if key == "time" and isinstance(revised, dict):
            revised = ai._sanitize_time(revised)
            _rev_phases = safe_list(revised.get("phases", []))
            if _rev_phases:
                _rev_rc = _recalc_estimate([dict(p) for p in _rev_phases if isinstance(p, dict)])
                revised.update(_rev_rc)

        r[rkey] = revised

        # Update live refs so downstream sections see the latest values
        if key == "requirements": semantic = revised
        elif key == "time":       time_est = revised
        elif key == "cost":       cost_est = revised
        elif key == "risk":       risk     = revised
        elif key == "architecture": arch   = revised
        elif key == "scope":      scope    = revised

    pb.progress(100)
    status.empty()
    pb.empty()

    # ── Single clean round entry in feedback_log ──────────────────────
    n_explicit = len(feedback_items)
    n_cascade  = len(dirty) - n_explicit
    existing_rounds = [e for e in st.session_state.feedback_log if "round" in e]
    st.session_state.feedback_log.append({
        "round":            len(existing_rounds) + 1,
        "ts":               datetime.now().strftime("%Y-%m-%d %H:%M"),
        "explicit_sections": list(feedback_items.keys()),
        "cascade_sections": [k for k in dirty if k not in feedback_items],
        "n_explicit":       n_explicit,
        "n_cascade":        n_cascade,
        "feedbacks":        dict(feedback_items),
    })

    st.session_state.processing_results  = r
    st.session_state.feedback_items      = {}
    st.session_state["show_diagrams"]    = False
    msg = f"✅ {n_explicit} section(s) revised"
    if n_cascade:
        msg += f" + {n_cascade} cascaded automatically"
    # Store toast message for the calling fragment to display after st.status() completes.
    # Do NOT call st.rerun() here — it would trigger a full-page rerun and gray out the
    # entire page, interrupting the st.status() widget before it can transition to "complete".
    st.session_state["_rfb_pipeline_toast"] = msg


_DISC_PRIORITY_META = {
    "High":   {"color": "#ff6b6b", "bg": "rgba(255,107,107,.12)", "label": "High"},
    "Medium": {"color": "#ffd166", "bg": "rgba(255,209,102,.12)", "label": "Medium"},
    "Low":    {"color": "#06d6a0", "bg": "rgba(6,214,160,.12)",   "label": "Low"},
}


def _render_discovery_tab(results: dict):
    from .pdf_generators import generate_discovery_pdf, HAS_REPORTLAB
    from .pptx_generator import generate_discovery_pptx, HAS_PPTX

    dq = safe_dict(results.get("discovery_questions"))
    if not dq:
        st.info("Discovery questions will appear here after the next pipeline run.")
        return

    project_type = safe_str(dq.get("project_type", ""))
    total_q      = safe_int(dq.get("total_questions", 0))
    summary      = safe_str(dq.get("priority_summary", ""))
    categories   = safe_list(dq.get("categories"))

    # ── Header ─────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:rgba(0,180,216,.07);border:1px solid rgba(0,180,216,.2);'
        f'border-radius:14px;padding:18px 22px;margin-bottom:18px">'
        f'<div style="font-weight:700;font-size:1.1rem;color:#e2e8f0;margin-bottom:6px">'
        f'🎯 Discovery Prep Deck — {project_type}</div>'
        f'<div style="color:#94a3b8;font-size:.85rem;line-height:1.6">{summary}</div>'
        f'<div style="margin-top:10px;display:flex;gap:16px">'
        f'<span style="font-size:.78rem;color:#00b4d8;font-weight:600">{total_q} questions</span>'
        f'<span style="font-size:.78rem;color:#94a3b8">{len(categories)} categories</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Category pills for quick navigation ────────────────────────────
    pill_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px">'
    for cat in categories:
        c_name  = safe_str(cat.get("name", ""))
        c_icon  = safe_str(cat.get("icon", "❓"))
        c_color = safe_str(cat.get("color", "#94a3b8"))
        c_count = len(safe_list(cat.get("questions")))
        pill_html += (
            f'<span style="background:{c_color}18;color:{c_color};border:1px solid {c_color}44;'
            f'border-radius:20px;padding:4px 12px;font-size:.78rem;font-weight:600">'
            f'{c_icon} {c_name} ({c_count})</span>'
        )
    pill_html += "</div>"
    st.markdown(pill_html, unsafe_allow_html=True)

    # ── Questions by category ───────────────────────────────────────────
    # Track which questions the user has marked as "covered"
    covered: set = st.session_state.get("_disc_covered", set())

    for cat in categories:
        c_name  = safe_str(cat.get("name", ""))
        c_icon  = safe_str(cat.get("icon", "❓"))
        c_color = safe_str(cat.get("color", "#94a3b8"))
        questions = safe_list(cat.get("questions"))
        if not questions:
            continue

        high_count = sum(1 for q in questions if safe_str(safe_dict(q).get("priority")) == "High")
        badge = f'<span style="background:{c_color}20;color:{c_color};border-radius:4px;padding:1px 8px;font-size:.72rem;margin-left:6px">{len(questions)} questions</span>'
        if high_count:
            badge += f'<span style="background:rgba(255,107,107,.15);color:#ff6b6b;border-radius:4px;padding:1px 8px;font-size:.72rem;margin-left:4px">{high_count} High priority</span>'

        with st.expander(f"{c_icon} {c_name}", expanded=True):
            for qi, q in enumerate(questions):
                q       = safe_dict(q)
                q_id    = f"{c_name}::{qi}"
                is_cov  = q_id in covered
                pri     = safe_str(q.get("priority", "Medium"))
                pm      = _DISC_PRIORITY_META.get(pri, _DISC_PRIORITY_META["Medium"])
                question_text = safe_str(q.get("question", ""))
                why_text      = safe_str(q.get("why", ""))
                followup_text = safe_str(q.get("follow_up", ""))

                ck_col, content_col = st.columns([0.5, 9.5])
                with ck_col:
                    checked = st.checkbox(
                        "", value=is_cov, key=f"disc_{c_name}_{qi}",
                        label_visibility="collapsed",
                        help="Mark as covered in the meeting",
                    )
                    if checked != is_cov:
                        if checked:
                            covered.add(q_id)
                        else:
                            covered.discard(q_id)
                        st.session_state["_disc_covered"] = covered

                with content_col:
                    opacity = ".4" if is_cov else "1"
                    _covered_badge = '<span style="font-size:.72rem;color:#06d6a0;margin-left:8px">✓ Covered</span>' if is_cov else ""
                    _followup_html = '<div style="font-size:.75rem;color:#7b61ff;margin-top:4px;padding-left:2px">➤ Follow-up: ' + followup_text + '</div>' if followup_text else ""
                    st.markdown(
                        f'<div style="opacity:{opacity};padding:4px 0 10px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                        f'<span style="background:{pm["bg"]};color:{pm["color"]};border-radius:4px;'
                        f'padding:1px 8px;font-size:.7rem;font-weight:700">{pm["label"]}</span>'
                        f'<span style="font-size:.87rem;color:#e2e8f0;font-weight:600">{question_text}</span>'
                        f'{_covered_badge}'
                        f'</div>'
                        f'<div style="font-size:.75rem;color:#64748b;padding-left:2px">Why: {why_text}</div>'
                        f'{_followup_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── Meeting prep progress ────────────────────────────────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    pct = int(len(covered) / total_q * 100) if total_q else 0
    st.progress(pct / 100, text=f"{len(covered)} of {total_q} questions covered in meeting prep")

    if covered:
        if st.button("🔄 Reset Coverage", key="disc_reset_cov"):
            st.session_state["_disc_covered"] = set()
            st.rerun()

    # ── Export buttons ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**📥 Export Discovery Prep Deck**")
    ec1, ec2, ec3 = st.columns(3)

    with ec1:
        if HAS_REPORTLAB:
            pdf_bytes = generate_discovery_pdf(dq)
            if pdf_bytes:
                st.download_button(
                    "📄 Download PDF",
                    data=pdf_bytes,
                    file_name="ECI_Discovery_Prep_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".pdf",
                    mime="application/pdf",
                    width="stretch",
                    type="primary",
                    key="dl_disc_pdf",
                )
        else:
            st.caption("Install reportlab for PDF export")

    with ec2:
        if HAS_PPTX:
            pptx_bytes = generate_discovery_pptx(dq)
            if pptx_bytes:
                st.download_button(
                    "📊 Download PPTX",
                    data=pptx_bytes,
                    file_name="ECI_Discovery_Prep_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    width="stretch",
                    key="dl_disc_pptx",
                )
        else:
            st.caption("Install python-pptx for PPTX export")

    with ec3:
        st.download_button(
            "📋 Download JSON",
            data=json.dumps(dq, indent=2, default=str),
            file_name="ECI_Discovery_Questions_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json",
            mime="application/json",
            width="stretch",
            key="dl_disc_json2",
        )


# ═══════════════════════════════════════════════════════════════════════
#  SCOPE & RISK REGISTER — SOW-quality, Claude-powered
# ═══════════════════════════════════════════════════════════════════════

def _scope_risk_loading_html() -> str:
    return (
        '<div style="background:linear-gradient(135deg,#051a30,#0a2540);'
        'border:3px solid #14A0B9;border-radius:16px;padding:44px;text-align:center;'
        'font-family:Segoe UI,system-ui,sans-serif;'
        'box-shadow:0 0 55px rgba(20,160,185,.75),0 0 110px rgba(20,160,185,.35)">'
        '<div style="display:inline-block;width:62px;height:62px;border-radius:50%;'
        'border:4px solid rgba(20,160,185,.3);border-top:4px solid #14A0B9;border-right:4px solid #94C11C;'
        'animation:srSpin .75s linear infinite;margin-bottom:18px;'
        'filter:drop-shadow(0 0 12px rgba(20,160,185,.8))"></div>'
        '<div style="font-size:1.15rem;font-weight:800;color:#fff;margin-bottom:8px;'
        'text-shadow:0 0 20px rgba(20,160,185,.8)">📋 Generating SOW-Quality Analysis...</div>'
        '<div style="font-size:.82rem;color:#7dd3e8;margin-bottom:26px">'
        'AI Agent is crafting legally precise scope definitions &amp; formal risk register</div>'
        '<div style="display:flex;flex-direction:column;gap:9px;max-width:460px;margin:0 auto">'
        '<div style="padding:10px 15px;background:rgba(20,160,185,.18);border:1px solid #14A0B9;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#38bdf8;font-weight:700">● DRAFTING</span>'
        '<span style="font-size:.75rem;color:#bae6fd;margin-left:10px">Scope items SC-001… with acceptance criteria</span></div>'
        '<div style="padding:10px 15px;background:rgba(148,193,28,.15);border:1px solid #94C11C;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#a3e635;font-weight:700;animation:srPulse .9s infinite">● BUILDING</span>'
        '<span style="font-size:.75rem;color:#d9f99d;margin-left:10px">Formal risk register RK-001… with probability × impact matrix</span></div>'
        '<div style="padding:10px 15px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.25);border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.6);font-weight:700">○ WRITING</span>'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.5);margin-left:10px">Change control framework &amp; legal notices</span></div>'
        '</div>'
        '<div style="margin-top:20px;font-size:.72rem;color:#7dd3e8">⏱ Up to 90 seconds · Do not close this tab</div>'
        '<style>@keyframes srSpin{to{transform:rotate(360deg)}}'
        '@keyframes srPulse{0%,100%{opacity:.5}50%{opacity:1}}</style></div>'
    )


def _generate_scope_risk_html(ant, se: dict, te: dict, ar: dict, ri: dict, r: dict) -> "str | None":
    """Call Claude to generate a SOW-quality Scope & Risk Register HTML document."""
    from datetime import datetime as _dt

    client  = (safe_str(se.get("client_name", ""))
               or safe_str(st.session_state.get("client_name", ""))
               or "Client")
    project = safe_str(se.get("project_type", "Solution"))
    weeks   = safe_str(te.get("duration_weeks", "16"))
    hours   = safe_int(te.get("total_hours", 1000))
    phases  = safe_list(te.get("phases", []))
    tech    = safe_list(se.get("technology_stack", []))
    reqs    = safe_list(se.get("requirements", []))

    sc       = safe_dict(r.get("scope", {}))
    in_sc    = safe_list(sc.get("in_scope", []))
    out_sc   = safe_list(sc.get("out_of_scope", []))
    assumps  = safe_list(sc.get("assumptions", []))
    prereqs  = safe_list(sc.get("prerequisites", []))
    risks    = safe_list(ri.get("risks", []))
    ov_score = safe_int(ri.get("overall_score", 5))
    ov_level = safe_str(ri.get("overall_level", "Medium"))

    phase_s  = "; ".join(
        f"{safe_str(safe_dict(p).get('name',''))} ({safe_int(safe_dict(p).get('hours',0))}h)"
        for p in phases[:6]
    )
    req_s = "; ".join(
        safe_str(safe_dict(q).get("title", q) if isinstance(q, dict) else q)
        for q in reqs[:10]
    )
    risks_s = "\n".join(
        f"  [{safe_str(safe_dict(rk).get('id', f'RK-{i+1:03d}'))}] "
        f"[{safe_str(safe_dict(rk).get('severity','M'))}] "
        f"{safe_str(safe_dict(rk).get('category',''))}: "
        f"{safe_str(safe_dict(rk).get('title',''))} — {safe_str(safe_dict(rk).get('description',''))} | "
        f"Prob: {safe_str(safe_dict(rk).get('probability',''))} | "
        f"Impact: {safe_str(safe_dict(rk).get('impact',''))} | "
        f"Mitigation: {safe_str(safe_dict(rk).get('mitigation',''))} | "
        f"Contingency: {safe_str(safe_dict(rk).get('contingency_plan',''))} | "
        f"Owner: {safe_str(safe_dict(rk).get('risk_owner',''))}"
        for i, rk in enumerate(risks[:15])
    )

    def _fmt_scope_items(items, section_type):
        lines = []
        for i, x in enumerate(items):
            if isinstance(x, dict):
                if section_type == "in_scope":
                    lines.append(
                        f"  [{safe_str(x.get('id', f'SC-{i+1:03d}'))}] {safe_str(x.get('title',''))} — "
                        f"{safe_str(x.get('description',''))} | "
                        f"Deliverable: {safe_str(x.get('deliverable',''))} | "
                        f"AC: {safe_str(x.get('acceptance_criteria',''))}"
                    )
                elif section_type == "out_of_scope":
                    lines.append(
                        f"  [{safe_str(x.get('id', f'EX-{i+1:03d}'))}] {safe_str(x.get('exclusion',''))} | "
                        f"Rationale: {safe_str(x.get('rationale',''))} | "
                        f"CR: {safe_str(x.get('change_request_condition',''))}"
                    )
                elif section_type == "assumptions":
                    lines.append(
                        f"  [{safe_str(x.get('id', f'AS-{i+1:03d}'))}] [{safe_str(x.get('party',''))}] "
                        f"{safe_str(x.get('statement',''))} | "
                        f"Consequence: {safe_str(x.get('consequence',''))} | "
                        f"Obligation: {safe_str(x.get('obligation',''))}"
                    )
                elif section_type == "prerequisites":
                    lines.append(
                        f"  [{safe_str(x.get('id', f'PR-{i+1:03d}'))}] {safe_str(x.get('item',''))} | "
                        f"By: {safe_str(x.get('provided_by',''))} | "
                        f"Milestone: {safe_str(x.get('milestone',''))} | "
                        f"If Delayed: {safe_str(x.get('consequence_if_delayed',''))}"
                    )
                else:
                    lines.append(f"  - {safe_str(x)}")
            else:
                lines.append(f"  - {safe_str(x)}")
        return "\n".join(lines)

    today = _dt.now().strftime("%d %B %Y")

    SYSTEM = (
        "You are a senior professional services architect and technology contracts specialist. "
        "Generate a complete, self-contained HTML/CSS/JS document: a professional "
        "Statement of Work — Scope & Risk Register, suitable for executive review, legal sign-off, and client acceptance.\n\n"
        "LEGAL WRITING STANDARDS (non-negotiable):\n"
        "- Use 'shall' for mandatory obligations; 'will' for planned/intended actions\n"
        "- Every scope item must be specific, measurable, and verifiable — zero vague language\n"
        "- In-Scope: each item numbered SC-001, SC-002… Include: Description, Deliverable, and Acceptance Criteria\n"
        "- Out-of-Scope: numbered EX-001, EX-002… Include: Exclusion statement, Business rationale, "
        "  Change Request condition ('If the Client requires this, a formal Change Request shall be raised')\n"
        "- Assumptions: numbered AS-001, AS-002… Format: 'It is assumed that [Client/Supplier] shall [action]. "
        "  Should this assumption prove incorrect, [specific consequence and change trigger].'\n"
        "- Prerequisites: numbered PR-001, PR-002… Format: 'Client shall provide [item] by [relative milestone]. "
        "  Failure to provide this by the agreed date may result in [impact to timeline/cost].'\n"
        "- Risk items: numbered RK-001, RK-002… Each with: Category, Description (specific event), "
        "  Probability (High/Medium/Low), Impact (High/Medium/Low), Risk Rating (Critical/High/Medium/Low), "
        "  Mitigation Strategy (actions taken before risk materialises), "
        "  Contingency Plan (actions taken if risk materialises), Risk Owner, Status (Open/Mitigated/Accepted)\n"
        "- Change Control: define PRECISELY what triggers a Change Request — no ambiguity\n\n"
        "DESIGN: dark background #05090f, dot-grid via CSS radial-gradient, glassmorphism cards "
        "(background rgba(255,255,255,0.04), border rgba(255,255,255,0.1), backdrop-filter:blur(12px)), "
        "accent teal #14A0B9, lime #94C11C, navy #161E56. "
        "Professional document aesthetic — clean tables, section dividers, typography hierarchy. "
        "Fully self-contained HTML, no external resources.\n\n"
        "MANDATORY PAGE STRUCTURE:\n"
        "1. DOCUMENT HEADER: Title 'Statement of Work — Scope & Risk Register', client name badge, "
        "   project name, Date: [today], Version: v1.0 — DRAFT, Prepared By: ECI, Status: FOR REVIEW. "
        "   Horizontal accent bar (teal→lime gradient shimmer).\n"
        "2. EXECUTIVE SUMMARY: 1-paragraph project overview + 4 metric cards "
        "   (Scope Items, Exclusions, Risk Rating badge, Total Risks).\n"
        "3. SCOPE DEFINITION — 4 collapsible/tabbed sub-sections styled as glass cards:\n"
        "   a. ✅ IN SCOPE: table with columns SC-ID | Deliverable | Full Description | Acceptance Criteria\n"
        "   b. 🚫 OUT OF SCOPE: table with EX-ID | Exclusion | Rationale | Change Request Condition\n"
        "   c. 📐 ASSUMPTIONS: table with AS-ID | Assumption Statement | Risk if False | Client Obligation\n"
        "   d. ⚙️ PREREQUISITES: table with PR-ID | Item | Provided By | Required By Milestone | Consequence if Delayed\n"
        "4. RISK REGISTER — 3 parts:\n"
        "   a. Risk Summary: 3 metric cards (Total Risks, High/Critical count, Risks Requiring Immediate Action)\n"
        "   b. 3×3 Risk Matrix visual: rows=Probability (Low/Med/High), cols=Impact (Low/Med/High). "
        "      Cells colored: Low×Low=green, crossing to High×High=red. Plot risk IDs inside each cell.\n"
        "   c. Formal Risk Register: scrollable table with RK-ID | Category | Risk Description | "
        "      Probability | Impact | Rating | Mitigation Strategy | Contingency Plan | Owner | Status. "
        "      Rating cells color-coded: Critical=red, High=orange, Medium=yellow, Low=green.\n"
        "5. CHANGE CONTROL FRAMEWORK:\n"
        "   a. 'A Change Request shall be raised whenever any of the following occur:' — numbered list (CR-1…CR-N), "
        "      specific and exhaustive\n"
        "   b. Change Request Process: numbered steps from submission to approval to implementation\n"
        "   c. Commercial impact statement\n"
        "6. LEGAL NOTICES: IP ownership (all deliverables remain property of Client upon full payment), "
        "   confidentiality, limitation of liability, governing law placeholder.\n"
        "7. SIGN-OFF BLOCK: 2-column table — Supplier (ECI) / Client ([client name]). "
        "   Fields: Name, Title, Signature (line), Date. Both columns identical structure.\n"
        "Return ONLY the complete HTML, no markdown fences, no explanations."
    )

    USER = (
        f"PROJECT:\n"
        f"  Client: {client}\n"
        f"  Project Type: {project}\n"
        f"  Duration: {weeks} weeks to go-live\n"
        f"  Total Effort: {hours:,} person-hours\n"
        f"  Technology: {', '.join(safe_str(t) for t in tech[:10])}\n"
        f"  Phases: {phase_s}\n"
        f"  Key Requirements: {req_s}\n"
        f"  Document Date: {today}\n\n"
        f"EXISTING IN-SCOPE ITEMS (each already has title, deliverable, acceptance criteria — "
        f"elevate to SOW-standard and add any missing items typical for {project}):\n"
        + _fmt_scope_items(in_sc, "in_scope") + "\n\n"
        f"EXISTING OUT-OF-SCOPE EXCLUSIONS (already have rationale and CR conditions — "
        f"enhance and add any missing scope-creep protections):\n"
        + _fmt_scope_items(out_sc, "out_of_scope") + "\n\n"
        f"EXISTING ASSUMPTIONS (already in 'It is assumed that...' format with consequences — "
        f"preserve structure, enhance language, add any missing):\n"
        + _fmt_scope_items(assumps, "assumptions") + "\n\n"
        f"EXISTING PREREQUISITES (already have provider, milestone, and consequence — "
        f"preserve and enhance):\n"
        + _fmt_scope_items(prereqs, "prerequisites") + "\n\n"
        f"EXISTING RISKS (already have probability, impact, mitigation, contingency, owner — "
        f"preserve all fields and add commercial, compliance, and integration risks not yet listed):\n"
        f"{risks_s or '  (generate comprehensive risks for this type of project)'}\n"
        f"  Overall Risk Score: {ov_score}/10 ({ov_level})\n\n"
        f"CONTENT REQUIREMENTS:\n"
        f"1. Every scope statement shall be unambiguous — a reader must know exactly what is and is not included\n"
        f"2. Out-of-scope exclusions must protect against the most common scope creep scenarios for {project}\n"
        f"3. Assumptions must name the responsible party and the exact consequence if the assumption is wrong\n"
        f"4. Risk register must include: Technical, Commercial, Operational, Data/Security, and Compliance risk categories\n"
        f"5. Change control triggers must be specific enough that no reasonable person could dispute whether a CR is needed\n"
        f"6. Use '{client}' as the client name throughout all text, not a placeholder\n\n"
        f"Generate the complete, beautiful, SOW-quality HTML document now."
    )

    try:
        raw = ant._make_request(SYSTEM, USER, max_tokens=16000, timeout=360)
        if not raw:
            return None
        html = raw.strip()
        for fence in ["```html", "```"]:
            if fence in html:
                html = html.split(fence, 1)[1].split("```")[0].strip()
                break
        if not html.lower().startswith("<!"):
            for tag in ["<!doctype", "<html"]:
                idx = html.lower().find(tag)
                if idx >= 0:
                    html = html[idx:]
                    break
        return html if len(html) > 1000 else None
    except Exception as _e:
        st.error(f"AI Agent error: {_e}")
        return None


def _scope_native_render(sc: dict, ri: dict, se: dict) -> None:
    """Native Streamlit default view — formatted scope + risk before Claude enhancement."""
    client  = (safe_str(se.get("client_name", ""))
               or safe_str(st.session_state.get("client_name", ""))
               or "Client")
    project = safe_str(se.get("project_type", "Solution"))

    inner = st.tabs(["✅ Scope Definition", "⚠️ Risk Register"])

    with inner[0]:
        c1, c2 = st.columns(2)

        def _item_row(i, x, id_prefix, text_color, section_type):
            if isinstance(x, dict):
                item_id = safe_str(x.get("id", f"{id_prefix}-{i+1:03d}"))
                if section_type == "in_scope":
                    main_txt = safe_str(x.get("title", ""))
                    detail_pairs = [
                        ("Description", safe_str(x.get("description", ""))),
                        ("Deliverable", safe_str(x.get("deliverable", ""))),
                        ("Acceptance Criteria", safe_str(x.get("acceptance_criteria", ""))),
                    ]
                elif section_type == "out_of_scope":
                    main_txt = safe_str(x.get("exclusion", ""))
                    detail_pairs = [
                        ("Rationale", safe_str(x.get("rationale", ""))),
                        ("CR Condition", safe_str(x.get("change_request_condition", ""))),
                    ]
                elif section_type == "assumptions":
                    party = safe_str(x.get("party", ""))
                    main_txt = (f"[{party}] " if party else "") + safe_str(x.get("statement", ""))
                    detail_pairs = [
                        ("Consequence", safe_str(x.get("consequence", ""))),
                        ("Obligation", safe_str(x.get("obligation", ""))),
                    ]
                elif section_type == "prerequisites":
                    main_txt = safe_str(x.get("item", ""))
                    detail_pairs = [
                        ("Provided By", safe_str(x.get("provided_by", ""))),
                        ("Due Milestone", safe_str(x.get("milestone", ""))),
                        ("If Delayed", safe_str(x.get("consequence_if_delayed", ""))),
                    ]
                else:
                    main_txt = safe_str(x)
                    detail_pairs = []
                details_html = "".join(
                    f'<div style="margin-top:3px;font-size:.7rem;color:#64748b">'
                    f'<b style="color:#94a3b8">{lbl}:</b> {val}</div>'
                    for lbl, val in detail_pairs if val
                )
                return (
                    f'<div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05)">'
                    f'<div style="display:flex;gap:10px;align-items:flex-start">'
                    f'<span style="font-size:.62rem;color:{text_color};font-weight:700;white-space:nowrap;'
                    f'background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;flex-shrink:0">{item_id}</span>'
                    f'<div style="flex:1">'
                    f'<div style="font-size:.78rem;color:#e2e8f0;font-weight:600;line-height:1.4">{main_txt}</div>'
                    f'{details_html}</div></div></div>'
                )
            return (
                f'<div style="display:flex;gap:10px;padding:9px 0;'
                f'border-bottom:1px solid rgba(255,255,255,.05);align-items:flex-start">'
                f'<span style="font-size:.65rem;color:{text_color};font-weight:700;white-space:nowrap;'
                f'background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px">{id_prefix}-{i+1:03d}</span>'
                f'<span style="font-size:.8rem;color:#e2e8f0;line-height:1.5">{safe_str(x)}</span></div>'
            )

        def _items_card(items, id_prefix, title, bg_color, border_color, text_color, section_type="generic"):
            rows = "".join(
                _item_row(i, x, id_prefix, text_color, section_type)
                for i, x in enumerate(items)
            ) or '<div style="font-size:.8rem;color:#475569;padding:8px 0">No items — run pipeline first</div>'
            return (
                f'<div style="background:{bg_color};border:1px solid {border_color};'
                f'border-radius:12px;padding:16px 18px;margin-bottom:16px">'
                f'<div style="font-size:.68rem;font-weight:700;color:{text_color};letter-spacing:1px;'
                f'text-transform:uppercase;margin-bottom:12px">{title} ({len(items)})</div>'
                f'{rows}</div>'
            )

        with c1:
            st.markdown(_items_card(
                safe_list(sc.get("in_scope", [])), "SC", "✅ In Scope",
                "rgba(148,193,28,.07)", "rgba(148,193,28,.35)", "#94C11C", "in_scope",
            ), unsafe_allow_html=True)
            st.markdown(_items_card(
                safe_list(sc.get("assumptions", [])), "AS", "📐 Assumptions",
                "rgba(20,160,185,.07)", "rgba(20,160,185,.35)", "#14A0B9", "assumptions",
            ), unsafe_allow_html=True)

        with c2:
            st.markdown(_items_card(
                safe_list(sc.get("out_of_scope", [])), "EX", "🚫 Out of Scope",
                "rgba(248,113,113,.07)", "rgba(248,113,113,.35)", "#f87171", "out_of_scope",
            ), unsafe_allow_html=True)
            st.markdown(_items_card(
                safe_list(sc.get("prerequisites", [])), "PR", "⚙️ Prerequisites",
                "rgba(255,209,102,.07)", "rgba(255,209,102,.35)", "#ffd166", "prerequisites",
            ), unsafe_allow_html=True)

        # SOW-quality hint hidden (feature temporarily disabled)

    with inner[1]:
        risks = safe_list(ri.get("risks", []))
        ov_sc = safe_int(ri.get("overall_score", 0))
        ov_lv = safe_str(ri.get("overall_level", "Medium"))
        ov_cl = "#06d6a0" if ov_sc <= 3 else "#ffd166" if ov_sc <= 6 else "#ff6b6b"

        crit = sum(1 for rk in risks if safe_str(safe_dict(rk).get("severity","")).lower() == "critical")
        hi   = sum(1 for rk in risks if safe_str(safe_dict(rk).get("severity","")).lower() == "high")
        med  = sum(1 for rk in risks if safe_str(safe_dict(rk).get("severity","")).lower() == "medium")
        lo   = len(risks) - crit - hi - med

        m1, m2, m3, m4, m5 = st.columns(5)
        for col, icon, lbl, val, clr in [
            (m1, "🎯", "Overall Risk",  f"{ov_sc}/10 {ov_lv}", ov_cl),
            (m2, "🔴", "Critical",      str(crit),              "#ef4444"),
            (m3, "🟠", "High",          str(hi),                "#f87171"),
            (m4, "🟡", "Medium",        str(med),               "#ffd166"),
            (m5, "🟢", "Low",           str(lo),                "#06d6a0"),
        ]:
            with col:
                st.markdown(
                    f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);'
                    f'border-top:3px solid {clr};border-radius:12px;padding:14px;text-align:center">'
                    f'<div style="font-size:1.35rem;font-weight:800;color:{clr}">{val}</div>'
                    f'<div style="font-size:.65rem;color:#64748b;letter-spacing:.8px;'
                    f'text-transform:uppercase;margin-top:4px">{icon} {lbl}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("")
        for i, rk in enumerate(risks):
            rk  = safe_dict(rk)
            rk_id = safe_str(rk.get("id", f"RK-{i+1:03d}"))
            sev = safe_str(rk.get("severity", "Medium"))
            sev_lower = sev.lower()
            clr = ("#ef4444" if "critical" in sev_lower else
                   "#f87171" if "high" in sev_lower else
                   "#ffd166" if "medium" in sev_lower else "#06d6a0")
            prob    = safe_str(rk.get("probability", ""))
            impact  = safe_str(rk.get("impact", ""))
            rating  = safe_int(rk.get("rating", 0))
            owner   = safe_str(rk.get("risk_owner", ""))
            status  = safe_str(rk.get("status", "Open"))
            cont    = safe_str(rk.get("contingency_plan", ""))
            status_clr = "#06d6a0" if status.lower() in ("mitigated", "accepted") else "#ffd166"
            rating_html = (
                f'<span style="font-size:.62rem;color:#94a3b8;background:rgba(255,255,255,.05);'
                f'padding:2px 8px;border-radius:10px;margin-left:6px">Rating: {rating}/9</span>'
                if rating else ""
            )
            meta_html = "".join(
                f'<span style="font-size:.68rem;color:#64748b;background:rgba(255,255,255,.04);'
                f'padding:2px 8px;border-radius:10px;margin-right:6px">{lbl}: <b style="color:#94a3b8">{val}</b></span>'
                for lbl, val in [("Prob", prob), ("Impact", impact), ("Owner", owner)]
                if val
            )
            cont_html = (
                f'<div style="font-size:.75rem;margin-top:6px">'
                f'<b style="color:#ffd166">Contingency:</b> '
                f'<span style="color:#fde68a">{cont}</span></div>'
                if cont else ""
            )
            st.markdown(
                f'<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);'
                f'border-left:4px solid {clr};border-radius:10px;padding:14px 16px;margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px">'
                f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
                f'<span style="font-size:.65rem;color:{clr};font-weight:700;background:rgba(255,255,255,.06);'
                f'padding:2px 8px;border-radius:4px">{rk_id}</span>'
                f'<span style="font-size:.65rem;color:#94a3b8;font-weight:600">{safe_str(rk.get("category",""))}</span>'
                f'{rating_html}'
                f'</div>'
                f'<div style="display:flex;gap:6px;align-items:center">'
                f'<span style="font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:10px;'
                f'background:rgba(255,255,255,.04);color:{status_clr}">{status}</span>'
                f'<span style="font-size:.68rem;font-weight:700;padding:3px 10px;border-radius:12px;'
                f'background:rgba(255,255,255,.05);color:{clr}">{sev}</span>'
                f'</div></div>'
                f'<div style="font-size:.85rem;font-weight:600;color:#e2e8f0;margin-bottom:5px">'
                f'{safe_str(rk.get("title",""))}</div>'
                f'<div style="font-size:.76rem;color:#94a3b8;margin-bottom:7px;line-height:1.5">'
                f'{safe_str(rk.get("description",""))}</div>'
                f'<div style="margin-bottom:4px">{meta_html}</div>'
                f'<div style="font-size:.75rem;margin-top:4px"><b style="color:#14A0B9">Mitigation:</b> '
                f'<span style="color:#7dd3e8">{safe_str(rk.get("mitigation",""))}</span></div>'
                f'{cont_html}'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_scope_risk_tab(se: dict, te: dict, ar: dict, ri: dict, r: dict) -> None:
    """Render the combined Scope & Risk Register — SOW-quality, Claude-powered."""
    import hashlib as _hl, json as _js

    _key = "scope_risk_" + _hl.md5(
        _js.dumps(
            [se, ri, r.get("scope", {}), te.get("total_hours")],
            sort_keys=True, default=str,
        ).encode()
    ).hexdigest()[:10]
    cached = st.session_state.get(_key)
    client  = (safe_str(se.get("client_name", ""))
               or safe_str(st.session_state.get("client_name", ""))
               or "Client")
    sc      = safe_dict(r.get("scope", {}))
    risks   = safe_list(ri.get("risks", []))
    ov_sc   = safe_int(ri.get("overall_score", 0))
    ov_lv   = safe_str(ri.get("overall_level", "Medium"))
    ov_cl   = "#06d6a0" if ov_sc <= 3 else "#ffd166" if ov_sc <= 6 else "#f87171"
    in_ct   = len(safe_list(sc.get("in_scope", [])))
    out_ct  = len(safe_list(sc.get("out_of_scope", [])))

    # ── Hero card ────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(20,160,185,.10),rgba(148,193,28,.06));'
        f'border:1px solid rgba(20,160,185,.28);border-radius:14px;padding:18px 22px;margin-bottom:14px">'
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f'<span style="font-size:2.2rem">📋</span>'
        f'<div style="flex:1;min-width:180px">'
        f'<div style="font-size:.95rem;font-weight:700;color:#e2e8f0">Scope &amp; Risk Register</div>'
        f'<div style="font-size:.76rem;color:#94a3b8;margin-top:3px">'
        f'SOW-quality scope definition &amp; formal risk register — '
        f'<b style="color:#14A0B9">{client}</b></div></div>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
        f'<div style="text-align:center;background:rgba(148,193,28,.1);border:1px solid rgba(148,193,28,.35);'
        f'border-radius:10px;padding:7px 13px">'
        f'<div style="font-size:1.1rem;font-weight:800;color:#94C11C">{in_ct}</div>'
        f'<div style="font-size:.6rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">In Scope</div></div>'
        f'<div style="text-align:center;background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.35);'
        f'border-radius:10px;padding:7px 13px">'
        f'<div style="font-size:1.1rem;font-weight:800;color:#f87171">{out_ct}</div>'
        f'<div style="font-size:.6rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">Excluded</div></div>'
        f'<div style="text-align:center;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);'
        f'border-radius:10px;padding:7px 13px">'
        f'<div style="font-size:1.1rem;font-weight:800;color:{ov_cl}">{ov_sc}/10</div>'
        f'<div style="font-size:.6rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">{ov_lv} Risk</div></div>'
        f'<div style="text-align:center;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);'
        f'border-radius:10px;padding:7px 13px">'
        f'<div style="font-size:1.1rem;font-weight:800;color:#94a3b8">{len(risks)}</div>'
        f'<div style="font-size:.6rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">Risks</div></div>'
        f'<span style="font-size:.7rem;color:#94C11C;font-weight:700;background:rgba(148,193,28,.1);'
        f'padding:4px 11px;border-radius:20px;white-space:nowrap">⚡ AI Agent</span>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    gen_clicked = False

    if cached:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            from datetime import datetime as _dt
            st.download_button(
                "📥 Download SOW Scope & Risk Register (HTML)",
                data=cached.encode("utf-8"),
                file_name=f"SOW_Scope_Risk_{client.replace(' ','_')}_{_dt.now().strftime('%Y%m%d')}.html",
                mime="text/html", width="stretch", key="dl_scope_risk_html",
            )
        with c2:
            if st.button("🔄 Reset", key="sr_rst", width="stretch"):
                st.session_state.pop(_key, None)
                st.rerun()
        with c3:
            gen_clicked = st.button("✨ Regen", key="sr_regen", width="stretch", type="primary")
        if not gen_clicked:
            st.components.v1.html(cached, height=1250, scrolling=True)
    else:
        # SOW-quality generation button hidden (feature temporarily disabled)
        gen_clicked = False
        _scope_native_render(sc, ri, se)

    if gen_clicked:
        try:
            st.toast("📋 AI Agent is generating your SOW-quality Scope & Risk Register...", icon="⚖️")
        except Exception:
            pass
        _slot = st.empty()
        _slot.markdown(_scope_risk_loading_html(), unsafe_allow_html=True)
        from .ai_clients import AnthropicAI as _Ant
        _ant = _Ant.from_session()
        if not _ant.is_live:
            _slot.empty()
            st.error("No Anthropic API key configured. Add it in Settings → AI Clients.")
            return
        _html = _generate_scope_risk_html(_ant, se, te, ar, ri, r)
        _slot.empty()
        if _html:
            st.session_state[_key] = _html
            st.rerun()
        else:
            st.error("AI Agent could not generate the Scope & Risk Register. Please try again.")

    # _quick_feedback("scope_risk", ...)  # hidden temporarily


@st.fragment
def _render_estimate_chat(te: dict, se: dict) -> None:
    """Small inline chat embedded in the Time Estimate tab."""
    with st.expander("💬 Ask about this estimate", expanded=False):
        st.markdown(
            '<div style="font-size:.75rem;color:#64748b;margin-bottom:10px">'
            'Ask anything — where hours came from, why a stream exists, how to reduce timeline, etc.'
            '</div>',
            unsafe_allow_html=True,
        )

        # Build context from time estimate + requirements
        _all_reqs = [
            {
                "title":       safe_str(rq.get("title", "")),
                "type":        safe_str(rq.get("type", "")),
                "complexity":  safe_str(rq.get("complexity", "")),
                "description": safe_str(rq.get("description", ""))[:150],
            }
            for rq in safe_list(se.get("requirements", []))
        ]
        _phases_detail = [
            {
                "name":   safe_str(p.get("name", "")),
                "domain": safe_str(p.get("domain", "")),
                "hours":  p.get("hours", 0),
                "weeks":  p.get("duration_weeks", 0),
                "tasks":  [
                    {"title": safe_str(t.get("title", "")), "role": safe_str(t.get("role", "")), "hours": t.get("hours", 0)}
                    for t in safe_list(p.get("tasks", []))
                ],
            }
            for p in safe_list(te.get("phases", []))
        ]
        _doc_text = str(st.session_state.get("_extracted_text", ""))[:3000].strip()
        _ctx = json.dumps({
            "project_type":          se.get("project_type", ""),
            "project_domains":       safe_list(se.get("project_domains", [])),
            "mandated_technologies": safe_list(se.get("mandated_technologies", [])),
            "total_hours":           te.get("total_hours", ""),
            "duration_weeks":        te.get("duration_weeks", ""),
            "three_point":           te.get("three_point", {}),
            "phases":                _phases_detail,
            "requirements":          _all_reqs,
        }, indent=2)
        _doc_section = ("\n\nSOURCE DOCUMENT EXCERPT:\n" + _doc_text) if _doc_text else ""
        _system = (
            "You are an expert delivery consultant reviewing a project time estimate. "
            "Answer questions about hours, streams, requirements, and timeline — concisely and directly. "
            "When asked where something came from, cite the specific requirement type/title. "
            "If a stream has no matching requirement and the user questions it, acknowledge it clearly. "
            "Do NOT return JSON.\n\nESTIMATE DATA:\n" + _ctx + _doc_section
        )

        _key_prefix = "est_chat"
        if st.session_state.get(f"{_key_prefix}_clear"):
            st.session_state[f"{_key_prefix}_msgs"] = []
            st.session_state[f"{_key_prefix}_clear"] = False

        _msgs = st.session_state.setdefault(f"{_key_prefix}_msgs", [])

        # Suggestion chips
        if not _msgs:
            _chip_cols = st.columns(3)
            _chips = [
                "Where did AI/ML stream come from?",
                "Which requirement has the most hours?",
                "How to cut timeline by 20%?",
            ]
            for _ci, _chip in enumerate(_chips):
                with _chip_cols[_ci]:
                    if st.button(_chip, key=f"{_key_prefix}_chip_{_ci}", width="stretch"):
                        st.session_state[f"{_key_prefix}_pending"] = _chip
                        st.rerun(scope="fragment")

        # History
        for _m in _msgs:
            with st.chat_message(_m["role"]):
                st.markdown(_m["content"])

        _pending = st.session_state.pop(f"{_key_prefix}_pending", None)
        _user_in = st.chat_input("Ask about the estimate…", key=f"{_key_prefix}_input") or _pending

        if _user_in:
            _msgs.append({"role": "user", "content": _user_in})
            with st.chat_message("user"):
                st.markdown(_user_in)

            _ant = AnthropicAI.from_session()
            with st.chat_message("assistant"):
                if _ant.is_live and hasattr(_ant, "stream_chat"):
                    _ans = st.write_stream(_ant.stream_chat(_system, _msgs))
                else:
                    with st.status("Thinking…", expanded=False) as _s:
                        _ans = _ai_chat(_system, _msgs)
                        _s.update(label="Done", state="complete")
                    st.markdown(_ans)
            if _ans:
                _msgs.append({"role": "assistant", "content": _ans})

        if _msgs:
            if st.button("🗑️ Clear", key=f"{_key_prefix}_clr", type="secondary"):
                st.session_state[f"{_key_prefix}_clear"] = True
                st.rerun(scope="fragment")


def _recalc_estimate(phases: list) -> dict:
    """Recompute all derived fields from a phases list — same formulas as _build_dynamic_time."""
    _OVERHEAD = {"Discovery", "Documentation", "PM", "QA"}

    # 1. Per-phase: rescale hours, duration_weeks, low/high, tasks low/high
    for p in phases:
        h = safe_int(p.get("hours", 0))
        p["low_hours"]      = round(h * 0.75)
        p["high_hours"]     = round(h * 1.40)
        p["duration_weeks"] = round(h / 40, 1) if h else 0
        p["week_label"]     = f"{p['duration_weeks']:.0f}w"
        for t in safe_list(p.get("tasks", [])):
            th = safe_int(t.get("hours", 0))
            t["low_hours"]  = round(th * 0.75)
            t["high_hours"] = round(th * 1.40)

    # 2. Total hours / three-point
    total      = sum(safe_int(p.get("hours",      0)) for p in phases)
    total_low  = sum(safe_int(p.get("low_hours",  0)) for p in phases)
    total_high = sum(safe_int(p.get("high_hours", 0)) for p in phases)

    # 3. Critical-path duration (same formula as dynamic_builders)
    par_streams = [p for p in phases if safe_str(p.get("domain", "")) not in _OVERHEAD]
    disc_w   = next((p["duration_weeks"] for p in phases if p.get("domain") == "Discovery"), 1.0)
    doc_w    = next((p["duration_weeks"] for p in phases if p.get("domain") == "Documentation"), 1.0)
    crit_w   = max((p["duration_weeks"] for p in par_streams), default=4.0)
    # QA runs parallel (30% rule) — use 35% of critical-path as duration proxy
    qa_w     = round(crit_w * 0.35, 1)
    total_weeks = round(disc_w + crit_w + (qa_w * 0.5) + doc_w + 1.0)

    # 4. Phase percentages
    for p in phases:
        p["percentage"] = f"{round(safe_int(p.get('hours',0)) / max(total,1) * 100)}%" if total else "0%"

    return {
        "total_hours":    total,
        "duration_weeks": f"{total_weeks} weeks",
        "three_point":    {"optimistic": total_low, "most_likely": total, "pessimistic": total_high},
        "phases":         phases,
    }


def _apply_estimate_fix(fix_type: str, fix_data: dict) -> None:
    """Surgically patch the live time_estimate in session state, then recompute all derived fields."""
    _te     = dict(st.session_state.processing_results.get("time_estimate", {}))
    _phases = [dict(safe_dict(p)) for p in safe_list(_te.get("phases", []))]

    if fix_type == "remove_stream":
        _name   = safe_str(fix_data.get("stream_name", "")).lower()
        _phases = [
            p for p in _phases
            if safe_str(p.get("name", "")).lower() != _name
            and safe_str(p.get("domain", "")).lower() != _name
        ]

    elif fix_type == "adjust_hours":
        _name   = safe_str(fix_data.get("stream_name", "")).lower()
        _factor = float(fix_data.get("factor", 1.0))
        for p in _phases:
            if safe_str(p.get("name", "")).lower() == _name or safe_str(p.get("domain", "")).lower() == _name:
                p["hours"] = round(safe_int(p.get("hours", 0)) * _factor)
                for t in safe_list(p.get("tasks", [])):
                    t["hours"] = round(safe_int(t.get("hours", 0)) * _factor)

    elif fix_type == "add_tasks":
        _name   = safe_str(fix_data.get("stream_name", "")).lower()
        _rtitle = safe_str(fix_data.get("requirement_title", ""))
        _rtitle_lower = _rtitle.lower()
        for p in _phases:
            if safe_str(p.get("name", "")).lower() == _name or safe_str(p.get("domain", "")).lower() == _name:
                # Dedup: skip if any existing task already covers this requirement
                _existing_text = " ".join(
                    safe_str(safe_dict(t).get("name", "") or safe_dict(t).get("title", "")) + " " +
                    safe_str(safe_dict(t).get("justification", ""))
                    for t in safe_list(p.get("tasks", []))
                ).lower()
                _sig_words = [w for w in _rtitle_lower.split() if len(w) > 4]
                if _sig_words and any(w in _existing_text for w in _sig_words):
                    continue  # already covered — skip to prevent duplicate
                p.setdefault("tasks", []).append({
                    "name":          f"Implement: {_rtitle[:50]}",
                    "role":          "Engineer",
                    "hours":         8,
                    "low_hours":     6,
                    "high_hours":    11,
                    "justification": f"Added to cover requirement: {_rtitle}",
                })
                p["hours"] = sum(safe_int(safe_dict(t).get("hours", 0)) for t in safe_list(p.get("tasks", [])))

    # Recompute ALL derived fields
    _recalc   = _recalc_estimate(_phases)
    _te.update(_recalc)

    # Preserve fields not owned by recalc
    _te["confidence"]  = _te.get("confidence", "Medium")
    _te["buffer"]      = _te.get("buffer", "15%")
    _te["milestones"]  = _te.get("milestones", [])
    _te["roles"]       = _te.get("roles", [])

    st.session_state.processing_results["time_estimate"] = _te


def _generate_explainer_content(client: str, proj_type: str, domains: list,
                                fn_list: list, objectives: list) -> "dict | None":
    """Call AI to generate vivid analogies + real-world outcome examples for the Project Explainer.

    Results are cached in session state keyed by a content hash so re-renders are instant.
    Returns {'features': [...], 'outcomes': [...]} or None on failure / no AI configured.
    """
    import hashlib

    _hash_src = (client + proj_type
                 + "".join(safe_str(safe_dict(r).get("title", "")) for r in fn_list[:6])
                 + "".join(safe_str(o) for o in objectives[:5]))
    _cache_key = f"_explainer_ai_{hashlib.md5(_hash_src.encode()).hexdigest()[:10]}"

    if _cache_key in st.session_state:
        return st.session_state[_cache_key]

    ai = _pick_ai_for("default")
    if not ai or not ai.is_live:
        return None

    feat_lines = "\n".join(
        f"- {safe_str(safe_dict(r).get('title', ''))[:60]}: {safe_str(safe_dict(r).get('description', ''))[:130]}"
        for r in fn_list[:4]
    ) or "- General digital platform features"
    obj_lines = "\n".join(f"- {safe_str(o)[:100]}" for o in objectives[:4]) or "- Improve operational efficiency"

    system = (
        "You are a business storyteller who explains complex software in simple, vivid, memorable language "
        "for non-technical executives and business stakeholders. Always respond with valid JSON only — "
        "no markdown fences, no extra text."
    )
    prompt = f"""Project: {client} — {proj_type}
Domains: {", ".join(safe_str(d) for d in domains[:4]) or "Enterprise Software"}

Features being built:
{feat_lines}

Business objectives:
{obj_lines}

Return ONLY this JSON (no ```json fences, no extra text outside the braces):
{{
  "features": [
    {{"icon": "emoji", "title": "3-5 word feature name", "analogy": "vivid real-world analogy in 22-30 words starting with Like, Think of it as, or Imagine"}},
    {{"icon": "emoji", "title": "3-5 word feature name", "analogy": "..."}},
    {{"icon": "emoji", "title": "3-5 word feature name", "analogy": "..."}}
  ],
  "outcomes": [
    {{"icon": "emoji", "title": "3-5 word outcome title", "example": "concrete day-to-day change in 22-30 words, name the specific team affected (e.g. Your finance team...)"}},
    {{"icon": "emoji", "title": "3-5 word outcome title", "example": "..."}},
    {{"icon": "emoji", "title": "3-5 word outcome title", "example": "..."}}
  ]
}}

Rules: max 3 items each. Plain words, zero jargon. Analogies must use everyday objects. Outcomes must describe the before/after for a specific person or team. Icon guide: 🔐 auth, 📊 analytics, 🔗 integration, 🤖 AI/ML, 📬 alerts, ⏱ time saving, 📈 growth, ✅ accuracy, 🛡 compliance, 💰 cost, 🤝 teamwork, 🔍 search."""

    try:
        raw = None
        ai_cls = type(ai).__name__
        if "Anthropic" in ai_cls:
            raw = ai._call(system, prompt, max_tokens=700)
            if isinstance(raw, dict):
                raw = json.dumps(raw)
        elif "Azure" in ai_cls and getattr(ai, "_client", None):
            resp = ai._client.chat.completions.create(
                model=ai.deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                **ai._token_kwargs(700),
                temperature=0.55,
            )
            raw = resp.choices[0].message.content
        elif hasattr(ai, "_call_text"):
            raw = ai._call_text(system, prompt, max_tokens=700)

        if not raw:
            return None

        raw = raw.strip()
        # Strip markdown fences if the model added them anyway
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        parsed = json.loads(raw)
        if isinstance(parsed.get("features"), list) and isinstance(parsed.get("outcomes"), list):
            st.session_state[_cache_key] = parsed
            return parsed
    except Exception:
        pass

    return None


def _render_project_explainer(se: dict, r: dict, fn_list: list, nf_list: list, ig_list: list) -> None:
    """Single-canvas animated project explainer — all data visible at once, industry-quality UI."""
    import streamlit.components.v1 as _cv1

    client     = (safe_str(se.get("client_name", ""))
                  or safe_str(st.session_state.get("client_name", ""))
                  or "Your Client")
    proj_type  = safe_str(se.get("project_type", "")) or "Digital Transformation"
    cplx       = safe_int(se.get("complexity_score", 5))
    domains    = safe_list(se.get("project_domains", []))
    tech       = safe_list(se.get("technology_stack", []))[:12]
    mandated   = safe_list(se.get("mandated_technologies", []))[:8]
    src_sys    = safe_list(se.get("source_systems", []))[:5]
    objectives = safe_list(se.get("business_objectives", []))[:5]
    scope_d    = safe_dict(r.get("scope", {}))
    in_scope   = safe_list(scope_d.get("in_scope", []))[:5]
    out_scope  = safe_list(scope_d.get("out_of_scope", []))[:4]
    all_tech   = list(dict.fromkeys([safe_str(t) for t in (mandated + tech) if t]))[:14]

    _disc    = safe_dict(st.session_state.get("discovery_results") or {})
    pain_pts = safe_list(_disc.get("pain_points", []))
    if not pain_pts:
        pain_pts = [
            {"issue": safe_str(rq.get("title", "")), "severity": safe_str(rq.get("complexity", "Medium")),
             "quote": safe_str(rq.get("description", ""))[:100]}
            for rq in fn_list[:4] if safe_str(rq.get("description", "")).strip()
        ]

    cplx_lbl = "Low" if cplx <= 3 else "Medium" if cplx <= 6 else "High"
    cplx_clr = "#22c55e" if cplx <= 3 else "#f59e0b" if cplx <= 6 else "#ef4444"
    cplx_rgb = "34,197,94" if cplx <= 3 else "245,158,11" if cplx <= 6 else "239,68,68"

    def _esc(s):
        return safe_str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("'","&#39;").replace('"',"&quot;")

    def _si(s):
        return safe_str(s.get("item", s) if isinstance(s, dict) else s)

    domain_badges = "".join(
        f'<span style="background:rgba(0,212,170,.1);color:#00d4aa;border:1px solid rgba(0,212,170,.25);'
        f'border-radius:16px;padding:3px 12px;font-size:.63rem;font-weight:700">{_esc(d)}</span>'
        for d in domains[:5]
    )

    obj_html = "".join(
        f'<div class="oi"><div class="chk">✓</div><span>{_esc(safe_str(obj))}</span></div>'
        for obj in objectives
    ) or '<div style="color:#475569;font-size:.72rem;padding:8px 0">No objectives extracted yet.</div>'

    SEV_C = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
    pain_html = ""
    for pp in pain_pts[:4]:
        pp  = safe_dict(pp) if isinstance(pp, dict) else {"issue": safe_str(pp)}
        sev = safe_str(pp.get("severity", "Medium"))
        sc  = SEV_C.get(sev, "#f59e0b")
        pain_html += (
            f'<div class="pi" style="border-left-color:{sc}">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px">'
            f'<div class="ptitle" style="min-width:0;flex:1;white-space:normal;word-break:break-word">'
            f'{_esc(pp.get("issue",""))}</div>'
            f'<span style="font-size:.56rem;padding:2px 7px;border-radius:5px;font-weight:700;'
            f'white-space:nowrap;flex-shrink:0;background:rgba(239,68,68,.1);color:{sc}">{sev}</span>'
            f'</div>'
            + (f'<div style="font-size:.64rem;color:#64748b;margin-top:3px;line-height:1.5;'
               f'white-space:normal;word-break:break-word;overflow-wrap:break-word">'
               f'{_esc(pp.get("quote","") or pp.get("description",""))}</div>'
               if (pp.get("quote") or pp.get("description")) else "")
            + '</div>'
        )
    if not pain_html:
        pain_html = '<div style="color:#475569;font-size:.72rem;padding:8px 0">No pain points extracted.</div>'

    # Maps keywords → (icon, analogy/example sentence)
    _FEAT_MAP = [
        (("auth","login","sign","sso","password","access","role","permission"),
         "🔐", "Like a hotel key card — staff tap once and get exactly the access they need, nothing more."),
        (("dashboard","report","chart","analytic","kpi","metric","insight","visual","bi"),
         "📊", "Like a live news ticker for your business — see real numbers right now, not last week's PDF."),
        (("integrat","api","connect","sync","webhook","interface","interop","feed"),
         "🔗", "Like WhatsApp between your systems — data flows automatically, nobody types the same thing twice."),
        (("ai","ml","predict","intelligence","smart","nlp","recommend","detect","classif"),
         "🤖", "Like a tireless analyst reading every row and flagging what matters — before you even ask."),
        (("notif","alert","email","sms","message","push","remind","escalat"),
         "📬", "Like a PA tapping your shoulder at exactly the right moment — never miss a critical update."),
        (("search","filter","query","find","lookup","discover","retriev"),
         "🔍", "Like Google for your own data — any record, any date, found in under 2 seconds."),
        (("upload","document","file","export","import","pdf","attach","storage"),
         "📁", "Like a smart filing cabinet that sorts itself — documents land in the right place automatically."),
        (("workflow","process","approval","task","pipeline","automat","schedul","routing"),
         "⚙️", "Like an automated assembly line — work moves from step to step without anyone chasing emails."),
        (("payment","invoice","billing","price","cost","fee","financ","reconcil"),
         "💳", "Like a 24/7 accountant who never misses a number, never forgets to bill, never makes typos."),
        (("mobile","responsive","phone","device","app","ios","android","tablet"),
         "📱", "Like giving every team member a Swiss Army knife — full power from any device, anywhere."),
        (("secur","audit","compliance","monitor","log","govern","regulat","access log"),
         "🛡", "Like CCTV for your data — every action recorded, every anomaly flagged immediately."),
        (("inventor","stock","warehouse","product","catalog","item","supply","sku"),
         "📦", "Like a smart stockroom that reorders before you run out — no more emergency calls to suppliers."),
        (("chat","support","ticket","helpdesk","customer","crm","service desk"),
         "💬", "Like a receptionist who never sleeps — every customer query answered immediately, logged automatically."),
        (("map","location","geo","address","region","zone","track","fleet"),
         "🗺", "Like GPS for your assets — always know where things are, where they've been, where they're going."),
    ]

    def _feat_info(title: str, desc: str):
        t = (title + " " + desc).lower()
        for keywords, icon, example in _FEAT_MAP:
            if any(w in t for w in keywords):
                return icon, example
        return "⚡", f"Automates what your team does manually today — faster, more accurate, zero effort."

    feat_html = ""
    for req in fn_list[:4]:
        req   = safe_dict(req)
        ttl   = safe_str(req.get("title", ""))
        dsc   = safe_str(req.get("description", ""))
        icon, example = _feat_info(ttl, dsc)
        feat_html += (
            f'<div class="fi">'
            f'<div class="fi-ico">{icon}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div class="fi-ttl">{_esc(ttl)}</div>'
            f'<div class="fi-eg">{_esc(example)}</div>'
            f'</div></div>'
        )
    if not feat_html:
        feat_html = '<div style="color:#475569;font-size:.7rem;padding:6px 0">No features extracted yet.</div>'

    # Maps objective/pain keywords → (icon, before→after real-world outcome)
    _BEN_MAP = [
        (("reduc","eliminat","remov","cut","sav","less","decreas","no more","stop"),
         "⏱", "What takes your team hours today will happen automatically in seconds."),
        (("automat","streamlin","workflow","process","manual","repetit"),
         "⚡", "Staff stop re-doing the same tasks and spend time on work that actually moves the business."),
        (("real-time","live","instant","current","now","up-to-date","latest"),
         "📡", "See what's happening right now — not yesterday's numbers in a spreadsheet attachment."),
        (("visibil","insight","report","analyt","dashboard","single source","one view"),
         "📊", "Your manager opens one screen Monday morning and sees the full picture — no digging, no calls."),
        (("accur","reliab","error","consistent","correct","trust","single version"),
         "✅", "No more 'which version of the file is right?' — one truth, everyone aligned."),
        (("custom","client","user experience","satisf","experienc","happier","faster response"),
         "😊", "Customers get answers in seconds instead of waiting for someone to check manually."),
        (("grow","scal","expand","increas","revenue","more volume","more customer"),
         "📈", "Handle 10× more volume without hiring 10× more people — the system scales with you."),
        (("compli","audit","govern","regulat","secur","risk","certif"),
         "🛡", "Auditors get clean, complete reports in minutes — not after weeks of manual gathering."),
        (("collaborat","team","coordinat","communicat","align","together","same page"),
         "🤝", "Everyone works from the same data — no conflicting versions, no lost email threads."),
        (("integrat","connect","unif","consolidat","centrali","single platform","one system"),
         "🔗", "All your tools finally talk to each other — data stops living in silos."),
        (("decision","strateg","forecast","plan","predict","smart","intellig"),
         "🎯", "Decisions backed by data, not gut feel — spot trends before they become problems."),
        (("cost","saving","budget","cheaper","efficient","roi","return"),
         "💰", "Reduce operational costs — the system does the work that currently needs extra headcount."),
    ]

    def _benefit_info(obj_text: str):
        t = obj_text.lower()
        for keywords, icon, example in _BEN_MAP:
            if any(w in t for w in keywords):
                return icon, example
        return "✦", "A measurable improvement your business will feel from day one."

    benefits_html = ""
    for obj in objectives[:4]:
        icon, example = _benefit_info(safe_str(obj))
        benefits_html += (
            f'<div class="bi">'
            f'<div class="bi-ico">{icon}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div class="bi-ttl">{_esc(safe_str(obj))}</div>'
            f'<div class="bi-eg">{_esc(example)}</div>'
            f'</div></div>'
        )
    if not benefits_html:
        benefits_html = '<div style="color:#475569;font-size:.7rem;padding:6px 0">No objectives extracted yet.</div>'

    # ── AI-generated content (cached per project hash) ───────────────
    with st.spinner("✨ Generating project insights..."):
        _ai = _generate_explainer_content(client, proj_type, domains, fn_list, objectives)

    if _ai:
        _af = _ai.get("features", [])
        _ao = _ai.get("outcomes", [])
        if _af:
            feat_html = "".join(
                f'<div class="fi">'
                f'<div class="fi-ico">{_esc(safe_str(f.get("icon","⚡")))}</div>'
                f'<div style="flex:1;min-width:0">'
                f'<div class="fi-ttl">{_esc(safe_str(f.get("title","")))}</div>'
                f'<div class="fi-eg">{_esc(safe_str(f.get("analogy","")))}</div>'
                f'</div></div>'
                for f in _af[:3]
            )
        if _ao:
            benefits_html = "".join(
                f'<div class="bi">'
                f'<div class="bi-ico">{_esc(safe_str(o.get("icon","✦")))}</div>'
                f'<div style="flex:1;min-width:0">'
                f'<div class="bi-ttl">{_esc(safe_str(o.get("title","")))}</div>'
                f'<div class="bi-eg">{_esc(safe_str(o.get("example","")))}</div>'
                f'</div></div>'
                for o in _ao[:3]
            )

    src_pills = "".join(
        f'<span style="background:rgba(123,97,255,.09);color:#a78bfa;border:1px solid rgba(123,97,255,.2);'
        f'border-radius:12px;padding:3px 9px;font-size:.6rem;font-weight:600">{_esc(safe_str(s))}</span>'
        for s in src_sys
    )
    tech_html = "".join(f'<span class="tp">{_esc(safe_str(t))}</span>' for t in all_tech) or '<span style="color:#475569;font-size:.7rem">Not specified</span>'

    fn_c  = len(fn_list)
    nf_c  = len(nf_list)
    ig_c  = len(ig_list)
    tc_c  = len(all_tech)
    ob_c  = len(objectives)
    isc_c = len(in_scope)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:760px;overflow:hidden;
  background:#060c1a;
  font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;
  color:#e2e8f0;-webkit-font-smoothing:antialiased}}

/* ═══ BACKGROUND ═══ */
.bg{{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0}}
.orb{{position:absolute;border-radius:50%;filter:blur(100px);animation:drift 25s ease-in-out infinite alternate}}
.o1{{width:550px;height:550px;opacity:.13;background:radial-gradient(circle,#00d4aa,transparent 70%);top:-200px;left:-160px;animation-duration:22s}}
.o2{{width:480px;height:480px;opacity:.12;background:radial-gradient(circle,#7b61ff,transparent 70%);bottom:-140px;right:-140px;animation-duration:28s;animation-delay:-11s}}
.o3{{width:340px;height:340px;opacity:.1;background:radial-gradient(circle,#00b4d8,transparent 70%);top:40%;left:50%;animation-duration:20s;animation-delay:-7s}}
.o4{{width:260px;height:260px;opacity:.07;background:radial-gradient(circle,#ffd166,transparent 70%);bottom:20%;left:5%;animation-duration:18s;animation-delay:-15s}}
@keyframes drift{{
  0%  {{transform:translate(0,0)    scale(1)   }}
  25% {{transform:translate(28px,-32px) scale(1.04)}}
  50% {{transform:translate(-18px,22px) scale(.97) }}
  75% {{transform:translate(32px,16px)  scale(1.03)}}
  100%{{transform:translate(-12px,-22px) scale(1.01)}}
}}
.dots{{position:absolute;inset:0;
  background-image:radial-gradient(rgba(255,255,255,.022) 1px,transparent 1px);
  background-size:30px 30px}}
.scan{{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(to bottom,transparent,rgba(0,212,170,.055) 50%,transparent);
  animation:scan 2s cubic-bezier(0.4,0,.2,1) forwards}}
@keyframes scan{{0%{{transform:translateY(-100%)}}100%{{transform:translateY(120%)}}}}

/* ═══ STAGE ═══ */
.stage{{position:relative;z-index:1;height:760px;
  display:flex;flex-direction:column;gap:7px;padding:13px 18px 9px}}

/* ═══ HEADER ═══ */
.hdr{{flex-shrink:0;display:flex;align-items:flex-start;justify-content:space-between;gap:14px}}
.cname{{font-size:1.6rem;font-weight:900;line-height:1.1;letter-spacing:-.5px;
  background:linear-gradient(120deg,#f8fafc 0%,#e2e8f0 20%,#00d4aa 58%,#7b61ff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  opacity:0;animation:aD .75s cubic-bezier(0.16,1,0.3,1) .05s both}}
.ptype{{font-size:.73rem;color:#64748b;margin-top:4px;
  opacity:0;animation:aD .6s cubic-bezier(0.16,1,0.3,1) .22s both}}
.dbadges{{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px;
  opacity:0;animation:aD .5s cubic-bezier(0.16,1,0.3,1) .34s both}}
.cxbadge{{flex-shrink:0;background:rgba({cplx_rgb},.11);color:{cplx_clr};
  border:1px solid rgba({cplx_rgb},.28);border-radius:10px;padding:8px 15px;
  font-size:.7rem;font-weight:800;display:flex;align-items:center;gap:9px;
  box-shadow:0 0 28px rgba({cplx_rgb},.12);
  opacity:0;animation:aR .6s cubic-bezier(0.16,1,0.3,1) .38s both}}

/* ═══ KPI ROW ═══ */
.krow{{display:flex;gap:7px;flex-shrink:0}}
.kc{{flex:1;background:rgba(255,255,255,.032);border:1px solid rgba(255,255,255,.07);
  border-radius:13px;padding:10px 5px 8px;text-align:center;position:relative;
  overflow:hidden;opacity:0;cursor:default;
  transition:transform .28s cubic-bezier(0.16,1,0.3,1),box-shadow .28s ease}}
.kc:hover{{transform:translateY(-5px)}}
.kbar{{position:absolute;bottom:0;left:0;height:2.5px;width:0;border-radius:0 2px 2px 0;
  transition:width 1.6s cubic-bezier(0.16,1,0.3,1)}}
.kglow{{position:absolute;bottom:-14px;left:50%;transform:translateX(-50%);
  width:60%;height:38px;border-radius:50%;filter:blur(16px);opacity:.38;pointer-events:none}}
.knum{{font-size:1.7rem;font-weight:900;line-height:1;display:block}}
.klbl{{font-size:.52rem;color:#475569;text-transform:uppercase;letter-spacing:.65px;margin-top:4px}}

/* ═══ SECTION LABEL ═══ */
.slbl{{font-size:.57rem;font-weight:800;text-transform:uppercase;letter-spacing:2px;
  margin-bottom:7px;display:flex;align-items:center;gap:7px;flex-shrink:0;line-height:1}}
.slbl::after{{content:'';flex:1;height:1px;background:rgba(255,255,255,.065)}}

/* ═══ MID ROW ═══ */
.mid{{display:grid;grid-template-columns:1fr 1fr;gap:7px;flex:1;min-height:0}}
.mc{{background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:10px 13px;display:flex;flex-direction:column;
  overflow:hidden;opacity:0}}

/* objectives */
.oi{{display:flex;align-items:flex-start;gap:8px;padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,.04);
  font-size:.69rem;color:#cbd5e1;line-height:1.45;opacity:0}}
.oi:last-child{{border-bottom:none}}
.chk{{width:17px;height:17px;border-radius:5px;flex-shrink:0;margin-top:1px;
  background:rgba(34,197,94,.14);border:1px solid rgba(34,197,94,.3);
  display:flex;align-items:center;justify-content:center;font-size:.6rem;color:#22c55e}}

/* pain points */
.pi{{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
  border-left:3px solid #ef4444;border-radius:8px;padding:7px 10px;margin-bottom:5px;opacity:0}}
.ptitle{{font-size:.7rem;font-weight:700;color:#fca5a5;margin-bottom:2px}}

/* ═══ BOTTOM ROW ═══ */
.bot{{display:grid;grid-template-columns:1fr 1fr 1.35fr;gap:7px;flex-shrink:0;min-height:210px}}
.bc{{background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:9px 12px;overflow:hidden;display:flex;flex-direction:column}}

/* ── FEATURE ITEMS (what we're building) ── */
.fi{{display:flex;align-items:flex-start;gap:10px;padding:6px 0;
  border-bottom:1px solid rgba(255,255,255,.04);opacity:0}}
.fi:last-child{{border-bottom:none}}
.fi-ico{{width:28px;height:28px;border-radius:8px;flex-shrink:0;
  background:rgba(0,180,216,.1);border:1px solid rgba(0,180,216,.18);
  display:flex;align-items:center;justify-content:center;font-size:.9rem;margin-top:1px}}
.fi-ttl{{font-size:.69rem;font-weight:700;color:#e2e8f0;margin-bottom:3px;line-height:1.3}}
.fi-eg{{font-size:.62rem;color:#475569;line-height:1.45;font-style:italic}}

/* ── BENEFIT ITEMS (what you'll achieve) ── */
.bi{{display:flex;align-items:flex-start;gap:10px;padding:6px 0;
  border-bottom:1px solid rgba(255,255,255,.04);opacity:0}}
.bi:last-child{{border-bottom:none}}
.bi-ico{{width:28px;height:28px;border-radius:8px;flex-shrink:0;
  background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.18);
  display:flex;align-items:center;justify-content:center;font-size:.9rem;margin-top:1px}}
.bi-ttl{{font-size:.69rem;font-weight:700;color:#fcd34d;margin-bottom:3px;line-height:1.3}}
.bi-eg{{font-size:.62rem;color:#475569;line-height:1.45;font-style:italic}}

/* tech pills */
.tw{{display:flex;flex-wrap:wrap;gap:5px;overflow:hidden;align-content:flex-start}}
.tp{{background:rgba(20,160,185,.09);color:#67c8e0;border:1px solid rgba(20,160,185,.2);
  border-radius:14px;padding:4px 10px;font-size:.62rem;font-weight:600;opacity:0;
  cursor:default;transition:background .2s,transform .2s,box-shadow .2s}}
.tp:hover{{background:rgba(20,160,185,.23);transform:scale(1.08);box-shadow:0 0 12px rgba(20,160,185,.28)}}
.src-row{{margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,.06);
  display:flex;flex-wrap:wrap;gap:4px;opacity:0;animation:aU .5s cubic-bezier(0.16,1,0.3,1) 1.4s both}}
.src-lbl{{font-size:.52rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;
  color:#7b61ff;width:100%;margin-bottom:3px}}

/* ═══ KEYFRAMES ═══ */
@keyframes aD  {{from{{opacity:0;transform:translateY(-13px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes aU  {{from{{opacity:0;transform:translateY(16px)}} to{{opacity:1;transform:translateY(0)}}}}
@keyframes aL  {{from{{opacity:0;transform:translateX(-18px)}}to{{opacity:1;transform:translateX(0)}}}}
@keyframes aR  {{from{{opacity:0;transform:translateX(18px)}} to{{opacity:1;transform:translateX(0)}}}}
@keyframes aSc {{from{{opacity:0;transform:scale(.72)}}        to{{opacity:1;transform:scale(1)}}}}
</style>
</head>
<body>

<div class="bg">
  <div class="dots"></div>
  <div class="orb o1"></div><div class="orb o2"></div>
  <div class="orb o3"></div><div class="orb o4"></div>
  <div class="scan"></div>
</div>

<div class="stage">

  <!-- HEADER -->
  <div class="hdr">
    <div style="flex:1">
      <div class="cname">{_esc(client)}</div>
      <div class="ptype">{_esc(proj_type)}</div>
      <div class="dbadges">{domain_badges}</div>
    </div>
    <div class="cxbadge">
      <span style="font-size:1.2rem">⚡</span>
      <div>
        <div>{cplx_lbl} Complexity</div>
        <div style="font-size:.57rem;opacity:.5;margin-top:2px;font-weight:600">{cplx} / 10</div>
      </div>
    </div>
  </div>

  <!-- KPI ROW -->
  <div class="krow">
    <div class="kc"><div class="kglow" style="background:#00d4aa"></div><div class="kbar" style="background:#00d4aa"></div><span class="knum" data-target="{fn_c}" style="color:#00d4aa">0</span><div class="klbl">Functional</div></div>
    <div class="kc"><div class="kglow" style="background:#7b61ff"></div><div class="kbar" style="background:#7b61ff"></div><span class="knum" data-target="{nf_c}" style="color:#7b61ff">0</span><div class="klbl">Non-Functional</div></div>
    <div class="kc"><div class="kglow" style="background:#00b4d8"></div><div class="kbar" style="background:#00b4d8"></div><span class="knum" data-target="{ig_c}" style="color:#00b4d8">0</span><div class="klbl">Integrations</div></div>
    <div class="kc"><div class="kglow" style="background:#ffd166"></div><div class="kbar" style="background:#ffd166"></div><span class="knum" data-target="{tc_c}" style="color:#ffd166">0</span><div class="klbl">Technologies</div></div>
    <div class="kc"><div class="kglow" style="background:{cplx_clr}"></div><div class="kbar" style="background:{cplx_clr}"></div><span class="knum" data-target="{cplx}" style="color:{cplx_clr}">0</span><div class="klbl">Complexity /10</div></div>
    <div class="kc"><div class="kglow" style="background:#22c55e"></div><div class="kbar" style="background:#22c55e"></div><span class="knum" data-target="{ob_c}" style="color:#22c55e">0</span><div class="klbl">Objectives</div></div>
  </div>

  <!-- MID ROW -->
  <div class="mid">
    <div class="mc" style="border-color:rgba(34,197,94,.18);border-top:2px solid rgba(34,197,94,.35)">
      <div class="slbl" style="color:#22c55e">🎯 Strategic Objectives</div>
      {obj_html}
    </div>
    <div class="mc" style="border-color:rgba(239,68,68,.18);border-top:2px solid rgba(239,68,68,.35)">
      <div class="slbl" style="color:#ef4444">😣 Pain Points &amp; Challenges</div>
      {pain_html}
    </div>
  </div>

  <!-- BOTTOM ROW -->
  <div class="bot">
    <div class="bc" style="border-color:rgba(0,180,216,.16);border-top:2px solid rgba(0,180,216,.32)">
      <div class="slbl" style="color:#00b4d8">🔨 What We're Building</div>
      <div style="overflow:hidden;flex:1">{feat_html}</div>
    </div>
    <div class="bc" style="border-color:rgba(245,158,11,.16);border-top:2px solid rgba(245,158,11,.32)">
      <div class="slbl" style="color:#f59e0b">✨ What You'll Achieve</div>
      <div style="overflow:hidden;flex:1">{benefits_html}</div>
    </div>
    <div class="bc" style="border-color:rgba(20,160,185,.16);border-top:2px solid rgba(20,160,185,.3)">
      <div class="slbl" style="color:#14A0B9">⚙️ Tech Stack</div>
      <div class="tw">{tech_html}</div>
      {"<div class='src-row'><div class='src-lbl'>🔗 Source Systems</div>" + src_pills + "</div>" if src_pills else ""}
    </div>
  </div>

</div>

<script>
// KPI cards — spring pop in
document.querySelectorAll('.kc').forEach((el,i) => {{
  el.style.animation = `aSc .52s cubic-bezier(0.34,1.56,0.64,1) ${{.38+i*.07}}s both`;
  setTimeout(() => {{ el.querySelector('.kbar').style.width='100%'; }}, (.56+i*.07)*1000+250);
}});

// Mid cols — fade up
document.querySelectorAll('.mc').forEach((el,i) => {{
  el.style.animation = `aU .65s cubic-bezier(0.16,1,0.3,1) ${{.6+i*.1}}s both`;
}});

// Number counters
document.querySelectorAll('[data-target]').forEach(el => {{
  const tgt = +el.dataset.target;
  if (!tgt) {{ el.textContent = tgt; return; }}
  let v = 0;
  const step = Math.max(1, Math.ceil(tgt / 28));
  const id = setInterval(() => {{ v = Math.min(v+step, tgt); el.textContent = v; if(v>=tgt) clearInterval(id); }}, 42);
}});

// Objective items — slide from left
document.querySelectorAll('.oi').forEach((el,i) => {{
  el.style.animation = `aL .5s cubic-bezier(0.16,1,0.3,1) ${{.68+i*.09}}s both`;
}});

// Pain items — slide from right
document.querySelectorAll('.pi').forEach((el,i) => {{
  el.style.animation = `aR .5s cubic-bezier(0.16,1,0.3,1) ${{.68+i*.11}}s both`;
}});

// Feature items — slide from left
document.querySelectorAll('.fi').forEach((el,i) => {{
  el.style.animation = `aL .45s cubic-bezier(0.16,1,0.3,1) ${{.86+i*.09}}s both`;
}});

// Benefit items — slide from right
document.querySelectorAll('.bi').forEach((el,i) => {{
  el.style.animation = `aR .45s cubic-bezier(0.16,1,0.3,1) ${{.86+i*.09}}s both`;
}});

// Tech pills — spring pop
document.querySelectorAll('.tp').forEach((el,i) => {{
  el.style.animation = `aSc .38s cubic-bezier(0.34,1.56,0.64,1) ${{.82+i*.042}}s both`;
}});
</script>
</body>
</html>"""

    _cv1.html(html, height=772, scrolling=False)


def _auto_correct_estimate(te: dict, se: dict) -> None:
    """Run once per estimate: Claude reviews and auto-applies all high-severity,
    non-manual findings. Skips if already run for this estimate or Claude not live."""
    _total = safe_int(te.get("total_hours", 0))
    _cache_key = f"_autocorr_done_{_total}"
    if st.session_state.get(_cache_key):
        return

    _ai = AnthropicAI.from_session()
    if not (_ai and _ai.is_live):
        st.session_state[_cache_key] = True
        return

    try:
        _prompt = _build_review_prompt(te, se)
        _raw = (_ai.call_raw_text(
            "You are a senior delivery estimator auditing a project estimate. "
            "Return ONLY valid JSON, no markdown fences.",
            _prompt, max_tokens=4000,
        ) or "").strip()
        if _raw.startswith("```"):
            _raw = "\n".join(_raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        _parsed = json.loads(_raw)
    except Exception:
        st.session_state[_cache_key] = True
        return

    _findings = safe_list(_parsed.get("findings", []))
    # Only auto-apply high-severity, actionable (non-manual) findings
    _to_apply = [
        f for f in _findings
        if safe_dict(f).get("severity") == "high"
        and safe_dict(f).get("fix_type") not in ("manual", "", None)
        and safe_dict(f).get("fix_data")
    ]

    if _to_apply:
        # Snapshot for undo before touching anything
        st.session_state["_autocorr_snapshot"] = json.dumps(
            st.session_state.processing_results.get("time_estimate", {})
        )
        _corrections = []
        for _fd in _to_apply:
            _fd = safe_dict(_fd)
            try:
                _apply_estimate_fix(
                    safe_str(_fd.get("fix_type", "")),
                    safe_dict(_fd.get("fix_data", {})),
                )
                _corrections.append({
                    "title":      safe_str(_fd.get("title", "")),
                    "detail":     safe_str(_fd.get("detail", "")),
                    "fix_type":   safe_str(_fd.get("fix_type", "")),
                    "suggestion": safe_str(_fd.get("suggestion", "")),
                })
            except Exception:
                pass
        st.session_state["_auto_corrections"] = _corrections

    st.session_state[_cache_key] = True


def _render_auto_corrections_badge() -> None:
    """Collapsible badge showing what Claude auto-corrected, with an Undo All button."""
    _corrections = safe_list(st.session_state.get("_auto_corrections", []))
    if not _corrections:
        return

    _n = len(_corrections)
    _FT_L = {
        "remove_stream": "Removed stream",
        "add_tasks":     "Added missing tasks",
        "adjust_hours":  "Adjusted hours",
    }

    # Undo handler — must run before any rendering
    if st.session_state.pop("_autocorr_undo_clicked", False):
        _snap = st.session_state.get("_autocorr_snapshot")
        if _snap:
            try:
                _restored = json.loads(_snap)
                st.session_state.processing_results["time_estimate"] = _restored
                _total_r = safe_int(_restored.get("total_hours", 0))
                st.session_state[f"_autocorr_done_{_total_r}"] = False
            except Exception:
                pass
        st.session_state.pop("_auto_corrections", None)
        st.session_state.pop("_autocorr_snapshot", None)
        show_toast("↩️ Auto-corrections undone — estimate restored.", "info")
        st.rerun()

    with st.expander(
        f"⚡ Agent auto-corrected {_n} issue{'s' if _n > 1 else ''} — click to review",
        expanded=False,
    ):
        for _c in _corrections:
            _label = _FT_L.get(_c.get("fix_type", ""), "Fixed")
            st.markdown(
                f'<div style="border-left:3px solid #22c55e;padding:8px 14px;margin-bottom:6px;'
                f'background:rgba(34,197,94,.05);border-radius:0 8px 8px 0">'
                f'<div style="font-size:.78rem;font-weight:700;color:#e2e8f0">{_c.get("title","")}</div>'
                f'<div style="font-size:.7rem;color:#64748b;margin-top:2px">'
                f'<span style="color:#22c55e;font-weight:600">{_label}</span>'
                f' — {_c.get("suggestion","")[:130]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        _ba, _bb = st.columns([5, 1])
        with _bb:
            if st.button("↩️ Undo All", key="_autocorr_undo", width="stretch"):
                st.session_state["_autocorr_undo_clicked"] = True
                st.rerun()


def _build_review_prompt(te: dict, se: dict) -> str:
    """Build the agent review prompt from current session-state estimate data."""
    # Always read the LIVE estimate from session state so post-fix reviews use updated data
    _live_te = safe_dict(
        st.session_state.get("processing_results", {}).get("time_estimate") or te
    )
    _all_reqs = [
        {
            "title":       safe_str(rq.get("title", "")),
            "type":        safe_str(rq.get("type", "")),
            "complexity":  safe_str(rq.get("complexity", "")),
            "description": safe_str(rq.get("description", ""))[:200],
        }
        for rq in safe_list(se.get("requirements", []))
    ]
    _phases_detail = [
        {
            "name":   safe_str(p.get("name", "")),
            "domain": safe_str(p.get("domain", "")),
            "hours":  safe_int(p.get("hours", 0)),
            "weeks":  p.get("duration_weeks", 0),
            "tasks": [
                {
                    "title":       safe_str(t.get("title", "")),
                    "role":        safe_str(t.get("role", "")),
                    "hours":       safe_int(t.get("hours", 0)),
                    "description": safe_str(t.get("description", ""))[:100],
                }
                for t in safe_list(p.get("tasks", []))
            ],
        }
        for p in safe_list(_live_te.get("phases", []))
    ]
    _doc_text = str(st.session_state.get("_extracted_text", ""))[:4000].strip()
    return (
        "You are a senior delivery estimator auditing a project time estimate.\n\n"
        f"REQUIREMENTS (from scope document):\n{json.dumps(_all_reqs, indent=2)}\n\n"
        f"TIME ESTIMATE STREAMS & TASKS (current, after any applied fixes):\n{json.dumps(_phases_detail, indent=2)}\n\n"
        f"PROJECT:\n"
        f"  type: {se.get('project_type','')}\n"
        f"  domains detected: {json.dumps(safe_list(se.get('project_domains',[])))}\n"
        f"  technologies: {json.dumps(safe_list(se.get('mandated_technologies',[]))[:10])}\n"
        f"  total_hours: {_live_te.get('total_hours',0)}\n"
        f"  duration: {_live_te.get('duration_weeks','')}\n\n"
        + (f"SCOPE DOCUMENT EXCERPT:\n{_doc_text}\n\n" if _doc_text else "")
        + "Audit thoroughly across 5 dimensions:\n"
        "1. STREAM JUSTIFICATION — does each stream have ≥1 requirement justifying it?\n"
        "2. REQUIREMENTS COVERAGE — does each functional requirement have tasks covering it?\n"
        "3. HOURS SANITY — are hours reasonable? any stream disproportionate (>60% of total)?\n"
        "4. SCOPE ALIGNMENT — things in the document not estimated?\n"
        "5. MISSING WORK — standard work for this project type that is absent?\n\n"
        "Return ONLY valid JSON, no markdown fences:\n"
        '{"verdict":"ok|warning|critical","verdict_summary":"one sentence","score":0-100,'
        '"findings":[{"id":"f1","severity":"high|medium|low",'
        '"category":"stream_justification|requirements_coverage|hours_sanity|scope_alignment|missing_work",'
        '"title":"<60 chars","detail":"specific numbers and names","suggestion":"actionable",'
        '"fix_type":"remove_stream|add_tasks|adjust_hours|manual","fix_data":{}}]}\n\n'
        "fix_data keys: remove_stream→{stream_name}, add_tasks→{stream_name,requirement_title}, "
        "adjust_hours→{stream_name,factor}. Only include high-confidence findings."
    )


@st.fragment
def _render_estimate_review(te: dict, se: dict) -> None:
    """On-demand Agent review of the estimate with actionable fix buttons.

    State machine:
      idle          — waiting for user action
      reviewing     — running AI review call  (shows animated loader)
      fixing        — applying a single fix   (shows fix loader → full rerun)
      fix_selected  — applying N selected fixes sequentially
      ask_agent     — running Ask Agent call  (shows spinner)
    """
    _RK = "est_review"
    _state = st.session_state.get(f"{_RK}_state", "idle")
    _busy  = _state in ("reviewing", "fixing", "fix_selected", "ask_agent")

    # ── Header row (always visible) ───────────────────────────────────
    _h1, _h2 = st.columns([5, 2])
    with _h1:
        st.markdown(
            '<div style="margin:20px 0 0;padding:14px 18px;'
            'background:rgba(123,97,255,.06);border:1px solid rgba(123,97,255,.18);'
            'border-radius:12px 12px 0 0">'
            '<div style="font-size:.8rem;font-weight:800;color:#a78bfa;letter-spacing:.5px">'
            '🔍 AGENT ESTIMATE REVIEW</div>'
            '<div style="font-size:.7rem;color:#64748b;margin-top:2px">'
            'Agent audits every stream, requirement, and hour against your scope document.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with _h2:
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        _run_clicked = st.button(
            "▶ Review Now",
            key=f"{_RK}_run",
            type="primary",
            width="stretch",
            disabled=_busy,
        )

    # Trigger transitions — update _state locally so the reviewing block
    # below runs in THIS SAME rerun (button-click rerun), rendering the
    # loader immediately without an extra round-trip to the browser.
    if _run_clicked and not _busy:
        _state = "reviewing"
        st.session_state[f"{_RK}_state"] = "reviewing"
        st.session_state.pop(f"{_RK}_result",        None)
        st.session_state.pop(f"{_RK}_error",         None)
        st.session_state.pop(f"{_RK}_ask_active",    None)
        st.session_state.pop(f"{_RK}_thread_active", None)
        st.session_state.pop(f"{_RK}_result_holder", None)

    # ── STATE: reviewing — loader + background thread ──
    _REVIEW_LOADER = (
        '<div style="background:rgba(123,97,255,.08);border:1px solid rgba(123,97,255,.22);'
        'border-radius:0 0 12px 12px;padding:32px 24px;text-align:center;margin-bottom:16px">'
        '<div style="font-size:2rem;margin-bottom:10px">🔍</div>'
        '<div style="font-size:.9rem;font-weight:800;color:#a78bfa;margin-bottom:6px">'
        'Agent Reviewing Estimate…</div>'
        '<div style="font-size:.73rem;color:#64748b;margin-bottom:22px">'
        'Auditing streams, requirements coverage, hours sanity, and scope alignment</div>'
        '<div style="display:flex;justify-content:center;gap:10px;margin-bottom:18px">'
        '<div style="width:10px;height:10px;border-radius:50%;background:#7b61ff;'
        'animation:erv_b 1.2s ease-in-out infinite 0s"></div>'
        '<div style="width:10px;height:10px;border-radius:50%;background:#7b61ff;'
        'animation:erv_b 1.2s ease-in-out infinite .2s"></div>'
        '<div style="width:10px;height:10px;border-radius:50%;background:#7b61ff;'
        'animation:erv_b 1.2s ease-in-out infinite .4s"></div>'
        '</div>'
        '<div style="font-size:.65rem;color:#475569">This usually takes 10–20 seconds</div>'
        '<style>@keyframes erv_b{0%,60%,100%{transform:translateY(0);opacity:.4}'
        '30%{transform:translateY(-10px);opacity:1}}</style>'
        '</div>'
    )

    # ── STATE: reviewing — "Review Now" button path (always fragment context) ──
    # Uses background thread + 300ms polls so the loader appears instantly
    # without blocking the fragment render or the asyncio event loop.
    if _state == "reviewing":
        st.markdown(_REVIEW_LOADER, unsafe_allow_html=True)

        # Start thread once (idempotent — guarded by _thread_active flag)
        if not st.session_state.get(f"{_RK}_thread_active"):
            _ai_key   = st.session_state.get("anthropic_api_key", "")
            _ai_model = st.session_state.get("claude_model", "claude-sonnet-4-6")
            _ai_ep    = st.session_state.get("claude_endpoint", "")
            _ai_live  = bool(_ai_key) and not st.session_state.get("_claude_blocked")
            _prompt   = _build_review_prompt(te, se)
            _holder   = [None, None]   # [status, payload] — written by thread
            st.session_state[f"{_RK}_result_holder"] = _holder
            st.session_state[f"{_RK}_thread_active"] = True

            from modules.ai_clients import AnthropicAI as _Ant

            def _repair_json(s: str):
                """Best-effort repair of a truncated JSON string from the API."""
                s = s.strip()
                # Strip markdown fences if present
                if s.startswith("```"):
                    s = "\n".join(s.split("\n")[1:]).rsplit("```", 1)[0].strip()
                # Try clean parse first
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    pass
                # Truncated — close any open structures then re-try
                # Count unmatched braces/brackets and open strings
                depth_brace = 0
                depth_bracket = 0
                in_str = False
                escape = False
                last_good = 0
                for i, ch in enumerate(s):
                    if escape:
                        escape = False
                        continue
                    if ch == "\\" and in_str:
                        escape = True
                        continue
                    if ch == '"' and not escape:
                        in_str = not in_str
                    if not in_str:
                        if ch == "{":
                            depth_brace += 1
                        elif ch == "}":
                            depth_brace -= 1
                        elif ch == "[":
                            depth_bracket += 1
                        elif ch == "]":
                            depth_bracket -= 1
                        if depth_brace > 0 or depth_bracket > 0:
                            last_good = i + 1
                # If we're mid-string, close it
                repaired = s[:last_good] if last_good else s
                if in_str:
                    repaired += '"'
                # Close open arrays/objects in reverse order
                repaired += "]" * max(depth_bracket, 0)
                repaired += "}" * max(depth_brace, 0)
                return json.loads(repaired)

            def _review_task():
                try:
                    if not _ai_live:
                        raise ValueError("Claude not configured — add your Anthropic API key in settings.")
                    _client = _Ant(_ai_key, _ai_model, _ai_ep)
                    _raw = _client.call_raw_text(
                        "You are a senior delivery estimator. Return ONLY valid JSON with no markdown fences.",
                        _prompt,
                        max_tokens=6000,
                    )
                    if not _raw:
                        raise ValueError("Agent returned empty response.")
                    _holder[0] = "ok"
                    _holder[1] = _repair_json(_raw)
                except Exception as _tex:
                    _holder[0] = "err"
                    _holder[1] = str(_tex)

            threading.Thread(target=_review_task, daemon=True).start()

        # Check whether the thread has finished
        _holder = st.session_state.get(f"{_RK}_result_holder")
        if _holder and _holder[0] is not None:
            if _holder[0] == "ok":
                st.session_state[f"{_RK}_result"] = _holder[1]
                st.session_state[f"{_RK}_state"]  = "done"
            else:
                st.session_state[f"{_RK}_error"] = _holder[1]
                st.session_state[f"{_RK}_state"] = "idle"
            st.session_state[f"{_RK}_thread_active"] = False
            st.session_state.pop(f"{_RK}_result_holder", None)
            st.rerun(scope="fragment")
            return

        # Thread still running — sleep(0.3) releases GIL so the asyncio
        # event loop can flush the loader delta to the browser before waking
        time.sleep(0.3)
        st.rerun(scope="fragment")
        return

    # ── STATE: fixing ─────────────────────────────────────────────────
    if _state == "fixing":
        _pf = safe_dict(st.session_state.get(f"{_RK}_pending_fix", {}))
        st.markdown(
            '<div style="background:rgba(0,212,170,.07);border:1px solid rgba(0,212,170,.2);'
            'border-radius:0 0 12px 12px;padding:28px 24px;text-align:center;margin-bottom:16px">'
            '<div style="font-size:1.6rem;margin-bottom:8px">⚡</div>'
            '<div style="font-size:.88rem;font-weight:800;color:#00d4aa;margin-bottom:5px">'
            'Applying Fix & Recalculating…</div>'
            '<div style="font-size:.72rem;color:#64748b;margin-bottom:18px">'
            'Updating hours, duration, critical path, Gantt, and all charts</div>'
            '<div style="background:rgba(0,212,170,.15);border-radius:6px;height:6px;overflow:hidden">'
            '<div style="height:100%;border-radius:6px;background:#00d4aa;'
            'animation:erv_p 1.5s ease-in-out infinite">'
            '</div></div>'
            '<style>@keyframes erv_p{0%{width:0%;margin-left:0}'
            '50%{width:70%;margin-left:15%}100%{width:0%;margin-left:100%}}</style>'
            '</div>',
            unsafe_allow_html=True,
        )
        _apply_estimate_fix(_pf.get("type", "manual"), _pf.get("data", {}))
        # Prevent auto-correct from re-firing on the updated total
        _fx_new_total = safe_int(
            st.session_state.processing_results.get("time_estimate", {}).get("total_hours", 0)
        )
        st.session_state[f"_autocorr_done_{_fx_new_total}"] = True
        # Clear old review — user clicks Review Now to re-audit
        st.session_state.pop(f"{_RK}_result",      None)
        st.session_state.pop(f"{_RK}_error",       None)
        st.session_state.pop(f"{_RK}_pending_fix", None)
        st.session_state[f"{_RK}_state"] = "idle"
        show_toast("✅ Fix applied — all charts updated. Click Review Now to re-audit.", "success")
        st.rerun()   # full app rerun — refreshes every chart/KPI above
        return

    # ── STATE: fix_selected ───────────────────────────────────────────
    # Two-phase per fix: "show" renders loader → rerun → "apply" runs the fix → rerun
    if _state == "fix_selected":
        _pending = safe_list(st.session_state.get(f"{_RK}_pending_selected", []))
        _idx     = safe_int(st.session_state.get(f"{_RK}_fix_sel_idx", 0))
        _phase   = st.session_state.get(f"{_RK}_fix_sel_phase", "show")
        _total_n = len(_pending)

        if _idx < _total_n:
            _pct   = int((_idx / max(_total_n, 1)) * 100)
            _label = safe_str(safe_dict(_pending[_idx]).get("label", ""))[:80]
            st.markdown(
                f'<div style="background:rgba(0,180,216,.07);border:1px solid rgba(0,180,216,.22);'
                f'border-radius:0 0 12px 12px;padding:28px 24px;text-align:center;margin-bottom:16px">'
                f'<div style="font-size:1.6rem;margin-bottom:8px">⚡</div>'
                f'<div style="font-size:.88rem;font-weight:800;color:#00b4d8;margin-bottom:5px">'
                f'Applying fix {_idx + 1} of {_total_n}…</div>'
                f'<div style="font-size:.72rem;color:#64748b;margin-bottom:18px">{_label}</div>'
                f'<div style="background:rgba(0,180,216,.15);border-radius:6px;height:6px;overflow:hidden">'
                f'<div style="height:100%;border-radius:6px;background:#00b4d8;width:{_pct}%;'
                f'transition:width .3s ease"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if _phase == "show":
                # Phase 1: loader is now flushed to browser — next rerun will apply the fix
                st.session_state[f"{_RK}_fix_sel_phase"] = "apply"
                st.rerun(scope="fragment")
            else:
                # Phase 2: apply this fix, advance index, go back to show phase
                _fix = safe_dict(_pending[_idx])
                _apply_estimate_fix(_fix.get("type", "manual"), safe_dict(_fix.get("data", {})))
                st.session_state[f"{_RK}_fix_sel_idx"]   = _idx + 1
                st.session_state[f"{_RK}_fix_sel_phase"] = "show"
                st.rerun(scope="fragment")
        else:
            # All fixes applied — clean up state
            st.session_state.pop(f"{_RK}_pending_selected",  None)
            st.session_state.pop(f"{_RK}_fix_sel_idx",       None)
            st.session_state.pop(f"{_RK}_fix_sel_phase",     None)
            for _k in list(st.session_state.keys()):
                if _k.startswith(f"{_RK}_chk_"):
                    del st.session_state[_k]

            # Prevent _auto_correct_estimate from re-firing on the new (post-fix) total
            _new_te    = st.session_state.processing_results.get("time_estimate", {})
            _new_total = safe_int(_new_te.get("total_hours", 0))
            st.session_state[f"_autocorr_done_{_new_total}"] = True

            # Reset to idle — full rerun updates all charts/KPI/Gantt,
            # then the user clicks Review Now for a fresh audit.
            st.session_state[f"{_RK}_state"] = "idle"
            st.session_state.pop(f"{_RK}_result",        None)
            st.session_state.pop(f"{_RK}_error",         None)
            st.session_state.pop(f"{_RK}_thread_active", None)
            st.session_state.pop(f"{_RK}_result_holder", None)

            show_toast(f"✅ {_total_n} fix{'es' if _total_n > 1 else ''} applied — click Review Now to re-audit.", "success")
            # Full rerun — refreshes every chart, KPI, Gantt, totals
            st.rerun()
        return

    # ── STATE: ask_agent ──────────────────────────────────────────────
    if _state == "ask_agent":
        _pask = safe_dict(st.session_state.get(f"{_RK}_pending_ask", {}))
        st.markdown(
            '<div style="background:rgba(20,160,185,.07);border:1px solid rgba(20,160,185,.2);'
            'border-radius:0 0 12px 12px;padding:28px 24px;text-align:center;margin-bottom:16px">'
            '<div style="font-size:1.6rem;margin-bottom:8px">✏️</div>'
            '<div style="font-size:.88rem;font-weight:800;color:#14A0B9;margin-bottom:5px">'
            'Agent Updating Estimate…</div>'
            '<div style="font-size:.72rem;color:#64748b;margin-bottom:14px">'
            f'{safe_str(_pask.get("instruction",""))[:80]}'
            '</div>'
            '<div style="display:flex;justify-content:center;gap:8px">'
            '<div style="width:8px;height:8px;border-radius:50%;background:#14A0B9;'
            'animation:erv_b 1.2s ease-in-out infinite 0s"></div>'
            '<div style="width:8px;height:8px;border-radius:50%;background:#14A0B9;'
            'animation:erv_b 1.2s ease-in-out infinite .2s"></div>'
            '<div style="width:8px;height:8px;border-radius:50%;background:#14A0B9;'
            'animation:erv_b 1.2s ease-in-out infinite .4s"></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        try:
            _cur_phases = safe_list(
                st.session_state.processing_results.get("time_estimate", {}).get("phases", [])
            )
            _ask_prompt = (
                f"Current estimate phases (JSON):\n{json.dumps(_cur_phases, indent=2)}\n\n"
                f"Issue: {safe_str(_pask.get('detail',''))}\n\n"
                f"Instruction: {safe_str(_pask.get('instruction',''))}\n\n"
                "Return ONLY the updated phases array as valid JSON with no markdown fences: "
                '{"phases":[...]}'
            )
            _ai2  = _pick_ai_for("default")
            _raw2 = (_ai2.call_raw_text(
                "You are a delivery estimator. Return ONLY valid JSON, no markdown fences.",
                _ask_prompt, max_tokens=4000,
            ) or "").strip()
            if _raw2.startswith("```"):
                _raw2 = "\n".join(_raw2.split("\n")[1:]).rsplit("```", 1)[0].strip()
            _upd = json.loads(_raw2)
            if "phases" in _upd:
                _cur_te = dict(st.session_state.processing_results.get("time_estimate", {}))
                _rc = _recalc_estimate([dict(safe_dict(p)) for p in _upd["phases"]])
                _cur_te.update(_rc)
                _cur_te.setdefault("confidence", "Medium")
                _cur_te.setdefault("buffer",     "15%")
                _cur_te.setdefault("milestones", [])
                _cur_te.setdefault("roles",      [])
                st.session_state.processing_results["time_estimate"] = _cur_te
                # Clear old review so user re-reviews on updated data
                st.session_state.pop(f"{_RK}_result", None)
                st.session_state.pop(f"{_RK}_error",  None)
            else:
                st.session_state[f"{_RK}_ask_err"] = "Agent response did not contain a phases array."
        except Exception as _ex3:
            st.session_state[f"{_RK}_ask_err"] = str(_ex3)[:200]
        st.session_state.pop(f"{_RK}_pending_ask", None)
        st.session_state[f"{_RK}_state"] = "idle"
        show_toast("✅ Estimate updated — click Review Now to re-audit.", "success")
        st.rerun()
        return

    # ── STATE: idle / done — render results ───────────────────────────
    _err    = st.session_state.get(f"{_RK}_error")
    _ask_err = st.session_state.pop(f"{_RK}_ask_err", None)
    _result = st.session_state.get(f"{_RK}_result")

    st.markdown(
        '<div style="background:rgba(123,97,255,.03);border:1px solid rgba(123,97,255,.1);'
        'border-radius:0 0 12px 12px;padding:14px 18px;margin-bottom:4px">',
        unsafe_allow_html=True,
    )

    if _err:
        st.error(f"Review failed: {_err[:250]}")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if _ask_err:
        st.error(f"Agent update failed: {_ask_err}")

    if not _result:
        st.markdown(
            '<div style="text-align:center;padding:18px 0;color:#475569;font-size:.78rem">'
            'Click <strong style="color:#a78bfa">▶ Review Now</strong> to audit this estimate.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Verdict banner
    _verdict  = safe_str(_result.get("verdict", "warning"))
    _score    = safe_int(_result.get("score", 0))
    _summary  = safe_str(_result.get("verdict_summary", ""))
    _findings = safe_list(_result.get("findings", []))
    _n_high   = sum(1 for f in _findings if safe_dict(f).get("severity") == "high")
    _n_med    = sum(1 for f in _findings if safe_dict(f).get("severity") == "medium")
    _n_low    = sum(1 for f in _findings if safe_dict(f).get("severity") == "low")
    _vc  = {"ok": "#22c55e", "warning": "#f59e0b", "critical": "#ef4444"}.get(_verdict, "#94a3b8")
    _vbg = {"ok": "34,197,94", "warning": "245,158,11", "critical": "239,68,68"}.get(_verdict, "148,163,184")
    _vi  = {"ok": "✅", "warning": "⚠️", "critical": "❌"}.get(_verdict, "🔍")
    _vl  = {"ok": "LOOKS SOLID", "warning": "ISSUES FOUND", "critical": "SIGNIFICANT ISSUES"}.get(_verdict, "REVIEWED")

    st.markdown(
        f'<div style="background:rgba({_vbg},.07);border:1px solid rgba({_vbg},.22);'
        f'border-left:4px solid {_vc};border-radius:10px;padding:14px 18px;margin-bottom:12px;'
        f'display:flex;justify-content:space-between;align-items:center;gap:16px">'
        f'<div style="flex:1">'
        f'<div style="font-size:.68rem;font-weight:800;color:{_vc};letter-spacing:1px;margin-bottom:4px">'
        f'{_vi} AGENT REVIEW — {_vl}</div>'
        f'<div style="font-size:.82rem;color:#e2e8f0;margin-bottom:6px">{_summary}</div>'
        f'<div style="font-size:.68rem;color:#64748b">'
        f'🔴 {_n_high} High &nbsp;·&nbsp; 🟡 {_n_med} Medium &nbsp;·&nbsp; 🟢 {_n_low} Low</div>'
        f'</div>'
        f'<div style="text-align:center;min-width:56px">'
        f'<div style="font-size:2rem;font-weight:900;color:{_vc};line-height:1">{_score}</div>'
        f'<div style="font-size:.58rem;color:#64748b;text-transform:uppercase;letter-spacing:.7px">/ 100</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if not _findings:
        st.success("No issues found — estimate looks accurate and complete.")
    else:
        _SEV_C = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}
        _SEV_I = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        _CAT_L = {
            "stream_justification":  "Stream Justification",
            "requirements_coverage": "Requirements Coverage",
            "hours_sanity":          "Hours Sanity",
            "scope_alignment":       "Scope Alignment",
            "missing_work":          "Missing Work",
        }
        _FIX_L = {
            "remove_stream": "⚡ Remove Stream",
            "add_tasks":     "⚡ Add Tasks",
            "adjust_hours":  "⚡ Adjust Hours",
        }

        # Count how many fixable findings are currently checked
        _fixable_ids = [
            safe_str(safe_dict(f).get("id", "f0"))
            for f in _findings
            if safe_dict(f).get("fix_type") not in ("manual", "", None)
        ]
        _checked_ids = [
            fid for fid in _fixable_ids
            if st.session_state.get(f"{_RK}_chk_{fid}", False)
        ]
        _n_checked = len(_checked_ids)

        # ── Fix Selected sticky bar (visible when ≥1 checkbox ticked) ──
        if _n_checked > 0:
            _fs_col1, _fs_col2 = st.columns([3, 1])
            with _fs_col1:
                st.markdown(
                    f'<div style="background:rgba(0,180,216,.08);border:1px solid rgba(0,180,216,.25);'
                    f'border-radius:10px;padding:10px 16px;font-size:.78rem;color:#e2e8f0;">'
                    f'<strong style="color:#00b4d8">{_n_checked} finding{"s" if _n_checked > 1 else ""} selected</strong>'
                    f' — click Fix Selected to apply all at once.</div>',
                    unsafe_allow_html=True,
                )
            with _fs_col2:
                if st.button(
                    f"⚡ Fix Selected ({_n_checked})",
                    key=f"{_RK}_fix_selected_btn",
                    type="primary",
                    width="stretch",
                ):
                    # Build ordered list of fixes from checked findings
                    _sel_fixes = []
                    for _f in _findings:
                        _f = safe_dict(_f)
                        _fid2 = safe_str(_f.get("id", ""))
                        if _fid2 in _checked_ids:
                            _sel_fixes.append({
                                "type":  safe_str(_f.get("fix_type", "")),
                                "data":  safe_dict(_f.get("fix_data", {})),
                                "label": safe_str(_f.get("title", "")),
                            })
                    st.session_state[f"{_RK}_pending_selected"] = _sel_fixes
                    st.session_state[f"{_RK}_fix_sel_idx"]      = 0
                    st.session_state[f"{_RK}_state"]            = "fix_selected"
                    st.rerun(scope="fragment")

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── Findings cards ────────────────────────────────────────────
        for _fd in _findings:
            _fd    = safe_dict(_fd)
            _sev   = safe_str(_fd.get("severity", "low"))
            _cat   = safe_str(_fd.get("category", ""))
            _fid   = safe_str(_fd.get("id", "f0"))
            _ft    = safe_str(_fd.get("fix_type", "manual"))
            _fdata = safe_dict(_fd.get("fix_data", {}))
            _sc    = _SEV_C.get(_sev, "#94a3b8")
            _is_fixable = _ft in _FIX_L

            # Card + checkbox in same row
            _card_col, _chk_col = st.columns([11, 1])
            with _card_col:
                st.markdown(
                    f'<div style="background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);'
                    f'border-left:3px solid {_sc};border-radius:8px;padding:12px 16px;margin-bottom:4px">'
                    f'<div style="font-size:.62rem;color:{_sc};font-weight:800;text-transform:uppercase;'
                    f'letter-spacing:.8px;margin-bottom:3px">'
                    f'{_SEV_I.get(_sev,"⚪")} {_CAT_L.get(_cat, _cat.replace("_"," ").title())}</div>'
                    f'<div style="font-size:.82rem;font-weight:700;color:#e2e8f0;margin-bottom:4px">'
                    f'{safe_str(_fd.get("title",""))}</div>'
                    f'<div style="font-size:.74rem;color:#94a3b8;margin-bottom:5px">'
                    f'{safe_str(_fd.get("detail",""))}</div>'
                    f'<div style="font-size:.7rem;color:#64748b">💡 {safe_str(_fd.get("suggestion",""))}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _chk_col:
                if _is_fixable:
                    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
                    st.checkbox(
                        "",
                        key=f"{_RK}_chk_{_fid}",
                        help="Select to include in Fix Selected",
                    )

            _ac1, _ac2, _ac3 = st.columns([2, 2, 5])
            with _ac1:
                if _is_fixable:
                    if st.button(_FIX_L[_ft], key=f"{_RK}_fix_{_fid}", type="primary", width="stretch"):
                        st.session_state[f"{_RK}_pending_fix"] = {"type": _ft, "data": _fdata}
                        st.session_state[f"{_RK}_state"]       = "fixing"
                        st.rerun(scope="fragment")
            with _ac2:
                if st.button("✏️ Ask Agent", key=f"{_RK}_ask_{_fid}", width="stretch"):
                    _cur = st.session_state.get(f"{_RK}_ask_active")
                    st.session_state[f"{_RK}_ask_active"] = None if _cur == _fid else _fid
                    st.rerun(scope="fragment")

            if st.session_state.get(f"{_RK}_ask_active") == _fid:
                _instr = st.text_area(
                    "Tell the agent what to change:",
                    value=safe_str(_fd.get("suggestion", "")),
                    height=68,
                    key=f"{_RK}_instr_{_fid}",
                )
                _pa, _pb = st.columns([1, 1])
                with _pa:
                    if st.button("▶ Apply", key=f"{_RK}_applyask_{_fid}", type="primary", width="stretch"):
                        st.session_state[f"{_RK}_pending_ask"] = {
                            "detail":      safe_str(_fd.get("detail", "")),
                            "instruction": _instr,
                        }
                        st.session_state[f"{_RK}_ask_active"] = None
                        st.session_state[f"{_RK}_state"]      = "ask_agent"
                        st.rerun(scope="fragment")
                with _pb:
                    if st.button("Cancel", key=f"{_RK}_cancel_{_fid}", width="stretch"):
                        st.session_state[f"{_RK}_ask_active"] = None
                        st.rerun(scope="fragment")

    # Re-review button
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _rr1, _rr2, _rr3 = st.columns([3, 2, 3])
    with _rr2:
        if st.button("🔄 Re-review", key=f"{_RK}_rerun", width="stretch"):
            st.session_state[f"{_RK}_state"] = "reviewing"
            st.session_state.pop(f"{_RK}_result",        None)
            st.session_state.pop(f"{_RK}_error",         None)
            st.session_state.pop(f"{_RK}_thread_active", None)
            st.session_state.pop(f"{_RK}_result_holder", None)
            st.rerun(scope="fragment")

    st.markdown("</div>", unsafe_allow_html=True)


def _tab_placeholder(icon: str, heading: str, detail: str = "") -> None:
    """Render a centred 'not yet available' card in a blank tab."""
    _detail_html = (
        f'<div style="font-size:.82rem;color:#475569;max-width:400px;line-height:1.65;margin-top:6px">'
        f'{detail}</div>'
    ) if detail else ""
    st.markdown(
        f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
        f'padding:72px 24px 90px;text-align:center;">'
        f'<div style="font-size:2.8rem;margin-bottom:18px;opacity:.45;filter:grayscale(40%)">{icon}</div>'
        f'<div style="font-size:1rem;font-weight:700;color:#64748b;letter-spacing:-.2px">{heading}</div>'
        f'{_detail_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_correct_and_train_tab(r: dict, se: dict, te: dict):
    """
    In-context estimation correction → training rule extraction.
    User sees what BELLA generated, types what's wrong, AI extracts rules,
    rules are saved and optionally the estimate is re-run immediately.
    """
    import json as _j

    st.markdown("""
<style>
.train-stream-row{display:flex;align-items:center;gap:8px;padding:7px 10px;
  border-radius:8px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  margin-bottom:6px}
.train-stream-name{flex:1;font-size:.85rem;color:#e2e8f0;font-weight:600}
.train-stream-hrs{font-size:.8rem;color:#7b61ff;font-weight:700;min-width:48px;text-align:right}
.train-rule-card{padding:10px 14px;border-radius:8px;background:rgba(123,97,255,.08);
  border:1px solid rgba(123,97,255,.25);margin-bottom:8px}
.train-section-hdr{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.8px;margin:14px 0 8px}
</style>""", unsafe_allow_html=True)

    phases      = safe_list(te.get("phases", []))
    proj_type   = safe_str(se.get("project_type", "Unknown"))
    saved_types = safe_list(se.get("project_type_tags") or st.session_state.get("project_type_tags", []))
    _PT_BASE    = ["AI", "Data", "SharePoint", "Cloud", "Custom App"]

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown("""
<div style="padding:16px 20px;border-radius:12px;background:linear-gradient(135deg,
  rgba(123,97,255,.12),rgba(0,212,170,.08));border:1px solid rgba(123,97,255,.25);margin-bottom:18px">
  <div style="font-size:1.1rem;font-weight:800;color:#e2e8f0">🎓 Correct This Estimate & Train BELLA</div>
  <div style="font-size:.82rem;color:#94a3b8;margin-top:4px">
    See what BELLA generated → describe what's wrong → AI extracts rules → save & re-run.
    No need to visit the Training tab. Every correction becomes a permanent rule.
  </div>
</div>""", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1], gap="large")

    # ══════════════════════════════════════════════════════════════════════
    # LEFT: What BELLA generated + inline hour adjustments
    # ══════════════════════════════════════════════════════════════════════
    with left_col:
        st.markdown('<div class="train-section-hdr">📊 What BELLA Generated</div>', unsafe_allow_html=True)
        st.caption(f"Project: **{proj_type}** — {len(phases)} work streams, "
                   f"{safe_int(te.get('total_hours', 0))}h total")

        _hour_changes = {}   # stream name → (original_hrs, corrected_hrs)
        _remove_flags = {}   # stream name → bool

        for i, phase in enumerate(phases):
            p = safe_dict(phase)
            name  = safe_str(p.get("name", f"Stream {i+1}"))
            hours = safe_int(p.get("hours", 0))
            domain = safe_str(p.get("domain", ""))

            row_col, hrs_col, del_col = st.columns([4, 2, 1])
            with row_col:
                st.markdown(
                    f'<div style="font-size:.85rem;font-weight:600;color:#e2e8f0;'
                    f'padding:4px 0">{name}</div>'
                    f'<div style="font-size:.7rem;color:#64748b">{domain}</div>',
                    unsafe_allow_html=True,
                )
            with hrs_col:
                new_hrs = st.number_input(
                    "h", value=hours, min_value=0, step=8,
                    key=f"_ct_hrs_{i}", label_visibility="collapsed",
                )
                if new_hrs != hours:
                    _hour_changes[name] = (hours, new_hrs)
            with del_col:
                if st.button("✕", key=f"_ct_rem_{i}", help="Mark: shouldn't exist for this project"):
                    _remove_flags[name] = True

        # Missing stream adder
        st.markdown('<div class="train-section-hdr" style="margin-top:18px">➕ Missing Stream?</div>',
                    unsafe_allow_html=True)
        _missing_options = [
            "(not missing)", "Data Engineering", "AI / ML Stream",
            "SharePoint / M365", "Custom Application", "Integration",
            "Security & Compliance", "Analytics & Reporting",
        ]
        _existing_names = {safe_str(safe_dict(p).get("name","")).lower() for p in phases}
        _missing_options = [o for o in _missing_options
                            if o == "(not missing)" or o.lower() not in _existing_names]
        _add_stream = st.selectbox("Select a stream that should have been included:",
                                   _missing_options, key="_ct_add_stream")

    # ══════════════════════════════════════════════════════════════════════
    # RIGHT: Free-text correction + rule extraction
    # ══════════════════════════════════════════════════════════════════════
    with right_col:
        st.markdown('<div class="train-section-hdr">✏️ Describe What\'s Wrong</div>',
                    unsafe_allow_html=True)
        correction_text = st.text_area(
            "correction_text",
            placeholder=(
                "Write corrections in plain English. Examples:\n\n"
                "• Data Engineering hours are too low — should be 200h+ for a data warehouse\n"
                "• Remove the AI / ML Stream — this is a pure data project with no AI component\n"
                "• DevOps hours should not exceed 60h for projects under 500h total\n"
                "• Always add a Synapse Analytics stream for data warehouse projects\n"
                "• Discovery phase needs a data profiling workshop (at least 16h)"
            ),
            height=190,
            key="_ct_correction_text",
            label_visibility="collapsed",
        )

        st.markdown('<div class="train-section-hdr">🏷️ Scope These Rules To</div>',
                    unsafe_allow_html=True)
        _ct_types = st.multiselect(
            "scope_types",
            _PT_BASE,
            default=saved_types,
            key="_ct_project_types",
            help="Rules are only applied to estimations of these project types. "
                 "Leave empty = applies to all projects.",
            label_visibility="collapsed",
        )

        # ── Generate Rules button ─────────────────────────────────────────
        _has_input = bool(correction_text.strip() or _hour_changes or
                          any(_remove_flags.values()) or
                          (_add_stream != "(not missing)"))

        if st.button("🤖 Generate Training Rules", key="_ct_extract_btn",
                     disabled=not _has_input, type="primary"):
            with st.spinner("Extracting rules from your corrections…"):

                # Build extra context from inline edits
                _inline_notes = []
                for sname, (orig, new) in _hour_changes.items():
                    _inline_notes.append(
                        f"User corrected '{sname}' from {orig}h to {new}h"
                    )
                for sname, flagged in _remove_flags.items():
                    if flagged:
                        _inline_notes.append(
                            f"User flagged '{sname}' as should NOT exist for this project"
                        )
                if _add_stream != "(not missing)":
                    _inline_notes.append(
                        f"User says '{_add_stream}' stream was MISSING and should have been included"
                    )
                _inline_ctx = ("\n".join(_inline_notes) + "\n\n") if _inline_notes else ""

                stream_summary = "\n".join(
                    f"  - {safe_str(safe_dict(p).get('name',''))} "
                    f"({safe_int(safe_dict(p).get('hours',0))}h)"
                    for p in phases
                )
                system = (
                    "You are a training data engineer for BELLA, an AI presales estimation tool at ECI. "
                    "Convert the user's corrections into clear, reusable training rules. "
                    "Rules must be specific and actionable — tell BELLA exactly what to do differently. "
                    "Use imperative language (DO / DO NOT / ALWAYS / NEVER / MINIMUM / MAXIMUM). "
                    "Return ONLY valid JSON:\n"
                    '{"rules": [{"instruction": "...", "category": "hours|streams|tasks|general"}, ...]}'
                )
                user_msg = (
                    f"Project type: {proj_type}\n"
                    f"Scoped to types: {', '.join(_ct_types) if _ct_types else 'All'}\n\n"
                    f"BELLA generated these work streams:\n{stream_summary}\n\n"
                    f"User inline corrections:\n{_inline_ctx}"
                    f"User free-text correction:\n{correction_text or '(none)'}\n\n"
                    "Extract 1-6 specific training rules. "
                    "Make each rule precise enough that BELLA can follow it on the next run."
                )
                raw = _claude_raw_call(system, [{"type": "text", "text": user_msg}], max_tokens=800)
                try:
                    extracted = _j.loads(raw)
                    rules = [r for r in extracted.get("rules", []) if r.get("instruction", "").strip()]
                except Exception:
                    rules = [{"instruction": raw.strip(), "category": "general"}] if raw.strip() else []

                st.session_state["_ct_extracted_rules"] = rules

        # ── Show + edit extracted rules ───────────────────────────────────
        extracted_rules = st.session_state.get("_ct_extracted_rules", [])
        if extracted_rules:
            st.markdown('<div class="train-section-hdr" style="margin-top:14px">'
                        '✅ Extracted Rules — Edit Before Saving</div>', unsafe_allow_html=True)

            final_rules = []
            _cats = ["general", "hours", "streams", "tasks"]
            for i, rule in enumerate(extracted_rules):
                with st.container():
                    edited_instr = st.text_area(
                        f"Rule {i + 1}",
                        value=safe_str(rule.get("instruction", "")),
                        key=f"_ct_rule_txt_{i}",
                        height=68,
                    )
                    edited_cat = st.selectbox(
                        "Category",
                        _cats,
                        index=_cats.index(rule.get("category", "general"))
                               if rule.get("category", "general") in _cats else 0,
                        key=f"_ct_rule_cat_{i}",
                        label_visibility="collapsed",
                    )
                    final_rules.append({"instruction": edited_instr, "category": edited_cat})
                    st.markdown("<hr style='margin:4px 0;border-color:rgba(255,255,255,.06)'>",
                                unsafe_allow_html=True)

            # ── Dedup warnings ────────────────────────────────────────────
            try:
                from .training import find_similar_instructions as _fsi
                _dedup_warnings = []
                for _fr in final_rules:
                    _instr = _fr.get("instruction", "").strip()
                    if _instr:
                        _matches = _fsi(_instr)
                        if _matches:
                            _dedup_warnings.append((_instr[:60] + "…", _matches[0]))
                if _dedup_warnings:
                    with st.expander(f"⚠️ {len(_dedup_warnings)} similar instruction(s) already exist — review before saving", expanded=True):
                        for _new_short, _match in _dedup_warnings:
                            st.markdown(
                                f"**New:** {_new_short}  \n"
                                f"**Existing (ID {_match['id']}, {int(_match['overlap']*100)}% overlap):** "
                                f"{_match['instruction'][:120]}",
                            )
                        st.caption("Saving will ADD alongside the existing one. Use the Training tab to delete the old rule if you want to replace it.")
            except Exception:
                pass

            # ── Save / Save+Rerun ─────────────────────────────────────────
            btn_save, btn_rerun = st.columns(2)
            with btn_save:
                if st.button("💾 Save Rules", key="_ct_save_btn", use_container_width=True):
                    try:
                        from .training import add_instruction as _add_ti
                        saved = 0
                        for rule in final_rules:
                            instr = rule.get("instruction", "").strip()
                            if instr:
                                _add_ti(instr, category=rule.get("category", "general"),
                                        created_by="admin", project_types=_ct_types)
                                saved += 1
                        st.success(f"✅ {saved} rule{'s' if saved != 1 else ''} saved to Agent Training.")
                        st.session_state["_ct_extracted_rules"] = []
                    except Exception as _e:
                        st.error(f"Save failed: {_e}")

            with btn_rerun:
                if st.button("🔄 Save & Re-run", key="_ct_rerun_btn",
                             use_container_width=True, type="primary"):
                    try:
                        from .training import add_instruction as _add_ti
                        for rule in final_rules:
                            instr = rule.get("instruction", "").strip()
                            if instr:
                                _add_ti(instr, category=rule.get("category", "general"),
                                        created_by="admin", project_types=_ct_types)
                        st.session_state["_ct_extracted_rules"] = []
                        if _ct_types:
                            st.session_state["project_type_tags"] = _ct_types
                        st.session_state["_ct_rerun_pending"] = True
                        st.success("Rules saved! Click **Run BELLA** to regenerate with these rules applied.")
                    except Exception as _e:
                        st.error(f"Failed: {_e}")

        # ── Pro-tip when nothing yet ──────────────────────────────────────
        elif not _has_input:
            st.info(
                "**How to use this tab:**\n\n"
                "1. On the left, adjust hours for any stream that's wrong, "
                "or click ✕ to mark a stream that shouldn't exist.\n"
                "2. Type corrections in plain English above — "
                "be specific about what should change and why.\n"
                "3. Click **Generate Training Rules** — BELLA converts your corrections into rules.\n"
                "4. Review and edit the extracted rules, then **Save & Re-run**.\n\n"
                "Every correction becomes a permanent training rule scoped to the project type you select.",
                icon="🎓",
            )

    # ══════════════════════════════════════════════════════════════════════
    # EXCEL UPLOAD — compare real estimate vs BELLA, extract learning rules
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📂 Upload Your Real Excel Estimate — Learn from the Gap", expanded=False):
        st.caption(
            "Upload the Excel you actually delivered to the client. "
            "BELLA will compare it phase-by-phase against what it generated, "
            "identify gaps, and propose training rules to close them."
        )
        _xl_file = st.file_uploader(
            "Real estimate Excel (.xlsx / .xls)",
            type=["xlsx", "xls"],
            key="_ct_xl_upload",
            label_visibility="collapsed",
        )
        if _xl_file:
            from .training import parse_excel_estimate as _pxl
            _xl_data = _pxl(_xl_file.read())
            _xl_phases = _xl_data.get("phases", [])
            _xl_total  = _xl_data.get("total_hours", 0)
            _bella_total = safe_int(te.get("total_hours", 0))

            if not _xl_phases:
                st.warning("Could not parse phases from this Excel. Make sure it has phase/task names and hour columns.")
            else:
                # ── Summary KPIs ──────────────────────────────────────
                kc1, kc2, kc3 = st.columns(3)
                _delta_total = _xl_total - _bella_total
                _delta_pct   = round(_delta_total / max(_bella_total, 1) * 100)
                _delta_clr   = "#f87171" if _delta_total > 0 else "#06d6a0" if _delta_total < 0 else "#94a3b8"
                with kc1:
                    st.metric("BELLA Estimated", f"{_bella_total}h")
                with kc2:
                    st.metric("You Actually Delivered", f"{_xl_total}h")
                with kc3:
                    st.metric("Gap", f"{'+' if _delta_total >= 0 else ''}{_delta_total}h ({_delta_pct:+}%)")

                # ── Phase comparison table ────────────────────────────
                st.markdown('<div class="train-section-hdr" style="margin-top:14px">Phase-by-Phase Comparison</div>',
                            unsafe_allow_html=True)

                # Fuzzy-match BELLA phases to real phases by name overlap
                _bella_phases_d = [safe_dict(p) for p in phases]

                def _best_match(real_name, bella_phases):
                    rw = set(real_name.lower().split())
                    best, best_score = None, 0.0
                    for bp in bella_phases:
                        bw = set(safe_str(bp.get("name","")).lower().split())
                        s  = len(rw & bw) / max(len(rw | bw), 1)
                        if s > best_score:
                            best, best_score = bp, s
                    return best, best_score

                _comp_rows = []
                for xp in _xl_phases:
                    rname = xp.get("phase", "")
                    rh    = safe_int(xp.get("actual_hours", 0))
                    bm, bscore = _best_match(rname, _bella_phases_d)
                    bh = safe_int(bm.get("hours", 0)) if bm and bscore > 0.20 else 0
                    bname = safe_str(bm.get("name", "—")) if bm and bscore > 0.20 else "— (not in BELLA)"
                    delta = rh - bh
                    _comp_rows.append({
                        "Real Phase": rname, "BELLA Match": bname,
                        "Real (h)": rh, "BELLA (h)": bh,
                        "Gap (h)": delta,
                    })

                # Highlight missing BELLA phases (in BELLA but not matched by any real phase)
                _matched_bella = {r["BELLA Match"] for r in _comp_rows if r["BELLA Match"] != "— (not in BELLA)"}
                for bp in _bella_phases_d:
                    bname = safe_str(bp.get("name",""))
                    if bname not in _matched_bella:
                        _comp_rows.append({
                            "Real Phase": "— (you didn't include this)",
                            "BELLA Match": bname,
                            "Real (h)": 0,
                            "BELLA (h)": safe_int(bp.get("hours", 0)),
                            "Gap (h)": -safe_int(bp.get("hours", 0)),
                        })

                import pandas as _pd
                _df = _pd.DataFrame(_comp_rows)

                def _color_gap(val):
                    if val > 0:   return "color:#f87171;font-weight:700"   # under-estimated
                    if val < 0:   return "color:#06d6a0;font-weight:700"   # over-estimated
                    return "color:#94a3b8"

                st.dataframe(
                    _df.style.applymap(_color_gap, subset=["Gap (h)"]),
                    use_container_width=True, hide_index=True,
                )

                # ── Auto-generate rules from the comparison ───────────
                st.markdown('<div class="train-section-hdr" style="margin-top:14px">🤖 Learn from This Gap</div>',
                            unsafe_allow_html=True)

                _xl_note = st.text_input(
                    "Optional context (e.g. 'Client added scope mid-project' or 'We used offshore team')",
                    key="_ct_xl_note",
                    placeholder="Any context that explains the gap…",
                )

                if st.button("🎓 Extract Rules from Gap", key="_ct_xl_learn_btn", type="primary"):
                    with st.spinner("Analysing gaps and extracting training rules…"):
                        _gap_summary = "\n".join(
                            f"  {r['Real Phase']} | BELLA: {r['BELLA (h)']}h | Actual: {r['Real (h)']}h | Gap: {r['Gap (h)']:+}h"
                            for r in _comp_rows
                        )
                        _system = (
                            "You are a training data engineer for BELLA, an AI presales estimation tool at ECI. "
                            "Given a comparison between BELLA's estimate and the real estimate delivered, "
                            "extract actionable training rules that would make BELLA more accurate next time. "
                            "Focus on patterns: consistent under/over-estimation, missing phases, wrong roles. "
                            "Rules must use DO / DO NOT / ALWAYS / MINIMUM / MAXIMUM language. "
                            "Return ONLY valid JSON:\n"
                            '{"rules": [{"instruction": "...", "category": "hours|streams|tasks|general"}]}'
                        )
                        _user_msg = (
                            f"Project type: {proj_type}\n"
                            f"Additional context: {_xl_note or 'none'}\n\n"
                            f"Phase comparison (Real vs BELLA):\n{_gap_summary}\n\n"
                            f"Overall gap: BELLA {_bella_total}h vs actual {_xl_total}h "
                            f"({_delta_pct:+}%).\n\n"
                            "Extract 2-6 specific training rules to improve future estimates."
                        )
                        _raw = _claude_raw_call(
                            _system, [{"type": "text", "text": _user_msg}], max_tokens=900
                        )
                        try:
                            _extracted = _j.loads(_raw)
                            _xl_rules = [r for r in _extracted.get("rules", [])
                                         if r.get("instruction", "").strip()]
                        except Exception:
                            _xl_rules = [{"instruction": _raw.strip(), "category": "general"}] if _raw.strip() else []

                        st.session_state["_ct_xl_rules"] = _xl_rules

                # ── Show extracted rules for review + save ────────────
                _xl_rules_out = st.session_state.get("_ct_xl_rules", [])
                if _xl_rules_out:
                    st.markdown("**Extracted Rules — edit, then save:**")
                    _xl_final = []
                    _cats = ["general", "hours", "streams", "tasks"]
                    for i, rule in enumerate(_xl_rules_out):
                        _e = st.text_area(f"Rule {i+1}", value=rule.get("instruction",""),
                                          key=f"_xl_rule_{i}", height=60)
                        _c = st.selectbox("Category", _cats,
                                          index=_cats.index(rule.get("category","general"))
                                                if rule.get("category","general") in _cats else 0,
                                          key=f"_xl_cat_{i}", label_visibility="collapsed")
                        _xl_final.append({"instruction": _e, "category": _c})

                    # Dedup check
                    try:
                        from .training import find_similar_instructions as _fsi
                        for _fr in _xl_final:
                            _ms = _fsi(_fr.get("instruction",""))
                            if _ms:
                                st.warning(
                                    f"Similar existing rule (ID {_ms[0]['id']}, "
                                    f"{int(_ms[0]['overlap']*100)}% overlap): "
                                    f"_{_ms[0]['instruction'][:100]}_"
                                )
                    except Exception:
                        pass

                    _xl_types = st.multiselect(
                        "Apply to project type:", _PT_BASE,
                        default=saved_types, key="_ct_xl_types",
                    )
                    if st.button("💾 Save Rules from Excel Comparison", key="_ct_xl_save",
                                 type="primary", use_container_width=True):
                        try:
                            from .training import add_instruction as _add_ti
                            _saved = 0
                            for rule in _xl_final:
                                _instr = rule.get("instruction","").strip()
                                if _instr:
                                    _add_ti(_instr, category=rule.get("category","general"),
                                            created_by="admin", project_types=_xl_types)
                                    _saved += 1
                            st.success(f"✅ {_saved} rules saved. Re-run BELLA to see the improvement.")
                            st.session_state["_ct_xl_rules"] = []
                        except Exception as _xe:
                            st.error(f"Save failed: {_xe}")


def show_results():
    r = st.session_state.processing_results
    st.markdown("---")
    st.markdown('<div class="shdr"><span class="shdr-i">📊</span> Results</div>', unsafe_allow_html=True)

    with st.expander("Agent Activity Log", expanded=False):
        for entry in st.session_state.agent_logs:
            st.markdown('<div class="alog"><span class="abadge">' + entry["agent"] + '</span><span class="aok">Done</span><span class="adet">' + entry["detail"] + '</span></div>', unsafe_allow_html=True)

    # ── Quick-Estimate mode notice ───────────────────────────────────────
    if st.session_state.get("time_test_mode"):
        st.info(
            "⚡ **Quick Estimate mode** — only the Time & Requirements tabs have data. "
            "Run the **full pipeline** to populate all other tabs.",
            icon="ℹ️",
        )

    # ── Show slim banner when a recalibration is awaiting review ────────
    render_pending_review_banner()

    # ── CSS: shimmer skeleton animation used by tab loading cards ────────
    st.markdown("""
<style>
@keyframes _eci_shimmer {
  0%   { background-position: -600px 0 }
  100% { background-position:  600px 0 }
}
.eci-tab-hdr {
  display:flex;align-items:center;gap:10px;padding:10px 16px;
  border-radius:10px;margin-bottom:14px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
}
.eci-tab-hdr-icon { font-size:1.4rem }
.eci-tab-hdr-title { font-size:.92rem;font-weight:700;color:#94a3b8;letter-spacing:-.2px }
.eci-skel {
  border-radius:8px;height:13px;margin:7px 0;
  background:linear-gradient(90deg,rgba(255,255,255,.05) 25%,rgba(255,255,255,.10) 50%,rgba(255,255,255,.05) 75%);
  background-size:600px 100%;
  animation:_eci_shimmer 1.4s infinite linear;
}
</style>""", unsafe_allow_html=True)

    se = safe_dict(r.get("semantic_analysis"))
    te = safe_dict(r.get("time_estimate"))
    ce = safe_dict(r.get("cost_estimate"))
    ri = safe_dict(r.get("risk_assessment"))
    ar = safe_dict(r.get("architecture"))

    # Keep total_hours in sync with phase sums so KPI matches Time tab and before/after panels
    _kpi_phases = safe_list(te.get("phases", []))
    _kpi_phase_sum = sum(safe_int(safe_dict(p).get("hours", 0)) for p in _kpi_phases if isinstance(p, dict))
    if _kpi_phase_sum > 0:
        te["total_hours"] = _kpi_phase_sum

    # ── Compute live infra total BEFORE KPI cards render ──────────────
    _all_cloud_kpi  = _get_all_cloud_costs(ce)
    _tp_costs_kpi   = safe_list(ce.get("third_party_costs"))
    _live_cache_kpi = st.session_state.get("live_pricing_cache", {})
    # If tech stack implies AWS/GCP but cost_estimate only has Azure data, use catalog
    _kpi_provider = _detect_cloud_provider(ce, se)
    if _kpi_provider == "aws" and not ce.get("aws_costs") and not any(
        str(safe_dict(s).get("service", "")).lower().startswith(("ec2", "rds", "s3", "lambda", "eks"))
        for s in _all_cloud_kpi
    ):
        _all_cloud_kpi = list(_AWS_CATALOG_SERVICES)
    elif _kpi_provider == "gcp" and not ce.get("gcp_costs") and not any(
        str(safe_dict(s).get("service", "")).lower().startswith(("cloud run", "cloud sql", "gke", "bigquery"))
        for s in _all_cloud_kpi
    ):
        _all_cloud_kpi = list(_GCP_CATALOG_SERVICES)
    _kpi_monthly = sum(
        safe_int(
            _live_cache_kpi.get(safe_str(safe_dict(s).get("service", "")))
            or safe_dict(s).get("monthly_cost", 0)
        )
        for s in _all_cloud_kpi
    ) + sum(safe_int(safe_dict(t).get("monthly_cost", 0)) for t in _tp_costs_kpi)
    if _kpi_monthly == 0:
        _kpi_monthly = safe_int(ce.get("total_monthly_cost", 0))
    st.session_state["_live_infra_total"] = _kpi_monthly
    # ─────────────────────────────────────────────────────────────────

    _kpi_hours = safe_int(te.get("total_hours"))
    _kpi_reqs  = len(safe_list(se.get("requirements")))
    _kpi_risk  = safe_int(ri.get("overall_score"))
    # Save exact displayed values so the Review tab "before" panel matches what user saw
    st.session_state["_last_rendered_kpi"] = {
        "hours": _kpi_hours, "cost": _kpi_monthly,
        "risk": _kpi_risk, "reqs": _kpi_reqs,
    }
    kpis = [
        ("📝", "Requirements", str(_kpi_reqs), "Identified"),
        ("⏱️", "Hours", str(_kpi_hours), "Person-hours"),
        ("💰", "Infra Cost", "$" + str(_kpi_monthly) + "/mo", "Cloud Infrastructure"),
        ("⚠️", "Risk", str(_kpi_risk) + "/10", safe_str(ri.get("overall_level"))),
        ("🏗️", "Components", str(len(safe_list(ar.get("components")))), "Designed"),
    ]
    cols = st.columns(5)
    for i, (ic, t, v, s) in enumerate(kpis):
        with cols[i]:
            st.markdown(_kpi_card(ic, t, v, s, animated=True), unsafe_allow_html=True)
    # ── Human Review & Feedback Panel hidden (duplicate of inline feedback) ──
    # _render_feedback_panel(r)

    tab_list = st.tabs(["📋 Requirements", "⏱️ Time", "💰 Infra Cost", "📋 Scope & Risk", "🏗️ Architecture", "📐 Diagrams", "📄 Proposal", "👥 Team & Roles", "🎯 Discovery Prep", "🔀 Scenarios", "🎮 3D View", "💬 Chat", "📚 History", "🎯 Live Demo", "📦 Delivery", "🔄 Review", "🎓 Train"])

    # ── INSTANT PRE-RENDER ────────────────────────────────────────────────────
    # Write a placeholder into every tab RIGHT NOW before any heavy computation.
    # This means clicking any tab will always show something instead of blank.
    # Each tab's actual block calls _pre[i].empty() to clear it before rendering.
    _pre = {}
    _pre_info = [
        (bool(se),                            "📋 Requirements"),
        (bool(te),                            "⏱️ Time Estimation"),
        (bool(ce),                            "💰 Infrastructure Cost"),
        (bool(ri or ar),                      "📋 Scope & Risk"),
        (bool(ar),                            "🏗️ Architecture"),
        (bool(r.get("mermaid_diagrams")),     "📐 Diagrams"),
        (bool(r.get("proposal")),             "📄 Proposal"),
        (True,                                "👥 Team & Roles"),
        (bool(r.get("discovery_questions")), "🎯 Discovery Prep"),
        (True,                                "🔀 Scenarios"),
        (bool(ar),                            "🎮 3D View"),
        (True,                                "💬 Chat"),
        (True,                                "📚 History"),
        (bool(se),                            "🎯 Live Demo"),
        (True,                                "📦 Delivery"),
        (True,                                "🔄 Review"),
        (bool(te),                            "🎓 Correct & Train"),
    ]
    for _pi, (_has, _lbl) in enumerate(_pre_info):
        with tab_list[_pi]:
            _pre[_pi] = st.empty()
            if _has:
                _pre[_pi].markdown(
                    f'<div style="padding:18px 4px 0;color:#475569;font-size:.8rem;'
                    f'font-style:italic">⏳ {_lbl} — loading…</div>',
                    unsafe_allow_html=True,
                )
            else:
                _pre[_pi].warning(
                    f"**{_lbl}** — not available. Run the full pipeline to generate this section.",
                    icon="ℹ️",
                )
    # ─────────────────────────────────────────────────────────────────────────

    # ── Requirements ──
    with tab_list[0]:
        _pre[0].empty()
        reqs = safe_list(se.get("requirements"))
        fn_list = [x for x in reqs if isinstance(x, dict) and x.get("type") == "functional"]
        nf_list = [x for x in reqs if isinstance(x, dict) and x.get("type") == "non-functional"]
        ig_list = [x for x in reqs if isinstance(x, dict) and x.get("type") == "integration"]
        tech       = safe_list(se.get("technology_stack"))
        objectives = safe_list(se.get("business_objectives"))
        cplx_score = safe_int(se.get("complexity_score", 0))
        proj_type  = safe_str(se.get("project_type", ""))
        cli_name   = safe_str(se.get("client_name", ""))

        _req_sub1, _req_sub2, _req_sub3 = st.tabs(["🎬 Project Explainer", "📋 Requirements Detail", "🔍 Scope Validator"])

        with _req_sub1:
            _render_project_explainer(se, r, fn_list, nf_list, ig_list)

        with _req_sub3:
            _doc_text = safe_str(st.session_state.get("_extracted_text", ""))
            _sv_key   = "scope_validation_result"

            # Clear cache when user clicks re-run
            _sv_col1, _sv_col2 = st.columns([4, 1])
            with _sv_col2:
                if st.button("🔄 Re-analyse", key="btn_sv_rerun", width="stretch"):
                    st.session_state.pop(_sv_key, None)
                    st.rerun()

            with _sv_col1:
                st.markdown(
                    '<div style="font-size:.8rem;color:#64748b;padding-top:8px">'
                    'AI reviews your scope document for gaps, ambiguities and missing information '
                    'before estimates are committed.</div>',
                    unsafe_allow_html=True,
                )

            if not st.session_state.get(_sv_key):
                with st.spinner("Analysing scope for gaps and assumptions…"):
                    _sv_result = _run_scope_validation(se, _doc_text)
            else:
                _sv_result = st.session_state[_sv_key]

            _sv_score    = safe_int(_sv_result.get("completeness_score", 0))
            _sv_summary  = safe_str(_sv_result.get("summary", ""))
            _sv_blockers = safe_list(_sv_result.get("blockers", []))
            _sv_assumes  = safe_list(_sv_result.get("assumptions", []))
            _sv_confirmed= safe_list(_sv_result.get("confirmed", []))
            _sv_email_sub= safe_str(_sv_result.get("email_subject", ""))
            _sv_email_bod= safe_str(_sv_result.get("email_body", ""))

            _sv_score_clr = "#06d6a0" if _sv_score >= 75 else "#ffd166" if _sv_score >= 50 else "#f87171"
            _sv_score_pct = min(100, _sv_score)

            # ── Score banner ─────────────────────────────────────────────
            st.markdown(
                f'<div style="background:linear-gradient(135deg,rgba(15,23,42,.9),rgba(30,42,68,.8));'
                f'border:1px solid {_sv_score_clr}44;border-radius:16px;padding:20px 24px;margin-bottom:20px">'
                f'<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
                f'<div style="text-align:center;min-width:90px">'
                f'<div style="font-size:2.4rem;font-weight:900;color:{_sv_score_clr};line-height:1">{_sv_score}</div>'
                f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-top:4px">Score / 100</div>'
                f'</div>'
                f'<div style="flex:1;min-width:200px">'
                f'<div style="background:rgba(255,255,255,.07);border-radius:8px;height:10px;overflow:hidden;margin-bottom:10px">'
                f'<div style="height:100%;width:{_sv_score_pct}%;border-radius:8px;'
                f'background:linear-gradient(90deg,{_sv_score_clr},{_sv_score_clr}99);'
                f'box-shadow:0 0 10px {_sv_score_clr}66;transition:width .8s ease"></div>'
                f'</div>'
                f'<div style="font-size:.85rem;color:#e2e8f0;font-weight:500">{_sv_summary}</div>'
                f'</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                f'<div style="background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#f87171">{len(_sv_blockers)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Blockers</div>'
                f'</div>'
                f'<div style="background:rgba(255,209,102,.1);border:1px solid rgba(255,209,102,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#ffd166">{len(_sv_assumes)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Assumptions</div>'
                f'</div>'
                f'<div style="background:rgba(6,214,160,.1);border:1px solid rgba(6,214,160,.3);border-radius:10px;padding:8px 14px;text-align:center">'
                f'<div style="font-size:1.3rem;font-weight:800;color:#06d6a0">{len(_sv_confirmed)}</div>'
                f'<div style="font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.6px">Confirmed</div>'
                f'</div>'
                f'</div></div></div>',
                unsafe_allow_html=True,
            )

            # ── Blockers ─────────────────────────────────────────────────
            if _sv_blockers:
                st.markdown(
                    '<div style="font-size:.78rem;font-weight:700;color:#f87171;'
                    'text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px;'
                    'display:flex;align-items:center;gap:8px">'
                    '🔴 Blockers — Resolve Before Committing to Estimate</div>',
                    unsafe_allow_html=True,
                )
                for _b in _sv_blockers:
                    if not isinstance(_b, dict): continue
                    _b_cat  = safe_str(_b.get("category", ""))
                    _b_iss  = safe_str(_b.get("issue", ""))
                    _b_imp  = safe_str(_b.get("impact", ""))
                    _b_q    = safe_str(_b.get("question", ""))
                    st.markdown(
                        f'<div style="background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.25);'
                        f'border-left:4px solid #f87171;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                        f'<span style="background:rgba(248,113,113,.2);color:#f87171;font-size:.62rem;'
                        f'font-weight:700;padding:2px 8px;border-radius:8px;text-transform:uppercase">{_b_cat}</span>'
                        f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">{_b_iss}</span>'
                        f'</div>'
                        f'<div style="font-size:.75rem;color:#94a3b8;margin-bottom:8px">⚠ Impact: {_b_imp}</div>'
                        + (f'<div style="background:rgba(248,113,113,.08);border-radius:6px;padding:8px 12px;'
                           f'font-size:.76rem;color:#fca5a5;font-style:italic">💬 "{_b_q}"</div>' if _b_q else '')
                        + '</div>',
                        unsafe_allow_html=True,
                    )

            # ── Assumptions ──────────────────────────────────────────────
            if _sv_assumes:
                st.markdown(
                    '<div style="font-size:.78rem;font-weight:700;color:#ffd166;'
                    'text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px;'
                    'display:flex;align-items:center;gap:8px">'
                    '🟡 Assumptions Made — Affect Estimate Accuracy</div>',
                    unsafe_allow_html=True,
                )
                for _a in _sv_assumes:
                    if not isinstance(_a, dict): continue
                    _a_cat  = safe_str(_a.get("category", ""))
                    _a_ass  = safe_str(_a.get("assumption", ""))
                    _a_imp  = safe_str(_a.get("impact", ""))
                    _a_q    = safe_str(_a.get("question", ""))
                    st.markdown(
                        f'<div style="background:rgba(255,209,102,.05);border:1px solid rgba(255,209,102,.22);'
                        f'border-left:4px solid #ffd166;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                        f'<span style="background:rgba(255,209,102,.18);color:#ffd166;font-size:.62rem;'
                        f'font-weight:700;padding:2px 8px;border-radius:8px;text-transform:uppercase">{_a_cat}</span>'
                        f'<span style="font-size:.82rem;color:#e2e8f0;font-weight:600">{_a_ass}</span>'
                        f'</div>'
                        f'<div style="font-size:.75rem;color:#94a3b8;margin-bottom:8px">📊 Impact: {_a_imp}</div>'
                        + (f'<div style="background:rgba(255,209,102,.07);border-radius:6px;padding:8px 12px;'
                           f'font-size:.76rem;color:#fde68a;font-style:italic">💬 "{_a_q}"</div>' if _a_q else '')
                        + '</div>',
                        unsafe_allow_html=True,
                    )

            # ── Confirmed ────────────────────────────────────────────────
            if _sv_confirmed:
                st.markdown(
                    '<div style="font-size:.78rem;font-weight:700;color:#06d6a0;'
                    'text-transform:uppercase;letter-spacing:.8px;margin:18px 0 10px">'
                    '🟢 Confirmed — Clearly Defined</div>',
                    unsafe_allow_html=True,
                )
                _conf_html = "".join(
                    f'<div style="display:flex;align-items:flex-start;gap:10px;'
                    f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">'
                    f'<span style="background:rgba(6,214,160,.15);color:#06d6a0;font-size:.62rem;'
                    f'font-weight:700;padding:2px 8px;border-radius:8px;white-space:nowrap;margin-top:1px">'
                    f'{safe_str(_c.get("category",""))}</span>'
                    f'<span style="font-size:.78rem;color:#cbd5e1">{safe_str(_c.get("detail",""))}</span>'
                    f'</div>'
                    for _c in _sv_confirmed if isinstance(_c, dict)
                )
                st.markdown(
                    f'<div style="background:rgba(6,214,160,.04);border:1px solid rgba(6,214,160,.18);'
                    f'border-radius:10px;padding:14px 18px">{_conf_html}</div>',
                    unsafe_allow_html=True,
                )

            # ── Client Q&A email ─────────────────────────────────────────
            if _sv_email_bod:
                st.markdown(
                    '<div style="font-size:.78rem;font-weight:700;color:#7b61ff;'
                    'text-transform:uppercase;letter-spacing:.8px;margin:22px 0 10px">'
                    '📧 Client Clarification Email — Ready to Send</div>',
                    unsafe_allow_html=True,
                )
                _email_full = f"Subject: {_sv_email_sub}\n\n{_sv_email_bod}"
                st.text_area(
                    "Copy and send to client",
                    value=_email_full,
                    height=260,
                    key="sv_email_area",
                    label_visibility="collapsed",
                )
                st.download_button(
                    "📋 Download Q&A as .txt",
                    data=_email_full.encode("utf-8"),
                    file_name=f"Scope_Clarification_{safe_str(se.get('client_name','Client')).replace(' ','_')}.txt",
                    mime="text/plain",
                    width="content",
                    key="sv_email_dl",
                )

        with _req_sub2:
            # ── Project Brief summary card ─────────────────────────────
            cplx_clr = "#06d6a0" if cplx_score <= 3 else "#ffd166" if cplx_score <= 6 else "#f87171"
            cplx_pct = int(cplx_score / 10 * 100)

            _tech_pills = "".join(
                f'<span style="background:rgba(20,160,185,.15);color:#7dd3e8;border:1px solid rgba(20,160,185,.3);'
                f'border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:600;white-space:nowrap">{safe_str(t)}</span>'
                for t in tech[:12]
            )
            _obj_pills = "".join(
                f'<span style="background:rgba(148,193,28,.12);color:#bef264;border:1px solid rgba(148,193,28,.3);'
                f'border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:500;white-space:nowrap">{safe_str(o)}</span>'
                for o in objectives[:6]
            )
            _req_counts = (
                f'<span style="background:rgba(99,179,237,.12);color:#63b3ed;border:1px solid rgba(99,179,237,.25);'
                f'border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:600">⚡ {len(fn_list)} Functional</span>'
                f'<span style="background:rgba(252,211,77,.12);color:#fcd34d;border:1px solid rgba(252,211,77,.25);'
                f'border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:600">🛡 {len(nf_list)} Non-Functional</span>'
                f'<span style="background:rgba(167,139,250,.12);color:#a78bfa;border:1px solid rgba(167,139,250,.25);'
                f'border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:600">🔗 {len(ig_list)} Integration</span>'
            )
            st.markdown(
                f'<div style="background:linear-gradient(135deg,rgba(20,160,185,.08),rgba(148,193,28,.04));'
                f'border:1px solid rgba(20,160,185,.22);border-radius:16px;padding:20px 24px;margin-bottom:18px">'
                f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px">'
                f'<span style="font-size:1.6rem">📋</span>'
                f'<div style="flex:1;min-width:180px">'
                + (f'<div style="font-size:1rem;font-weight:700;color:#e2e8f0">{cli_name}</div>' if cli_name else '')
                + (f'<div style="font-size:.78rem;color:#94a3b8;margin-top:2px">{proj_type}</div>' if proj_type else '')
                + f'</div>'
                f'<div style="min-width:160px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">'
                f'<span style="font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.6px">Complexity</span>'
                f'<span style="font-size:.9rem;font-weight:800;color:{cplx_clr}">{cplx_score}/10</span>'
                f'</div>'
                f'<div style="background:rgba(255,255,255,.08);border-radius:6px;height:7px;overflow:hidden">'
                f'<div style="height:100%;width:{cplx_pct}%;border-radius:6px;'
                f'background:linear-gradient(90deg,#14A0B9,{cplx_clr});'
                f'box-shadow:0 0 8px {cplx_clr}88;transition:width .6s ease"></div>'
                f'</div></div>'
                f'<div style="display:flex;gap:6px;flex-wrap:wrap">{_req_counts}</div>'
                f'</div>'
                + (f'<div style="margin-bottom:12px"><div style="font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.7px;margin-bottom:7px">Tech Stack</div><div style="display:flex;flex-wrap:wrap;gap:6px">{_tech_pills}</div></div>' if tech else '')
                + (f'<div><div style="font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.7px;margin-bottom:7px">Business Objectives</div><div style="display:flex;flex-wrap:wrap;gap:6px">{_obj_pills}</div></div>' if objectives else '')
                + f'</div>',
                unsafe_allow_html=True,
            )
            # ── Requirements columns ───────────────────────────────────
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                st.markdown('<div class="rch fn">Functional (' + str(len(fn_list)) + ')</div>', unsafe_allow_html=True)
                for q in fn_list:
                    st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><div class="ri-c">Complexity: ' + safe_str(q.get("complexity")) + '</div><p>' + safe_str(q.get("description")) + '</p></div>', unsafe_allow_html=True)
            with rc2:
                st.markdown('<div class="rch nf">Non-Functional (' + str(len(nf_list)) + ')</div>', unsafe_allow_html=True)
                for q in nf_list:
                    st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><p>' + safe_str(q.get("description")) + '</p></div>', unsafe_allow_html=True)
            with rc3:
                st.markdown('<div class="rch ig">Integration (' + str(len(ig_list)) + ')</div>', unsafe_allow_html=True)
                for q in ig_list:
                    st.markdown('<div class="ri"><strong>' + safe_str(q.get("title")) + '</strong><p>' + safe_str(q.get("description")) + '</p></div>', unsafe_allow_html=True)

    # ── Time ──
    with tab_list[1]:
        _pre[1].empty()
        phases    = safe_list(te.get("phases"))
        three_pt  = safe_dict(te.get("three_point"))
        milestones = safe_list(te.get("milestones"))

        _render_delivery_summary(te)

        _opt  = safe_int(three_pt.get("optimistic",  0))
        _ml   = safe_int(three_pt.get("most_likely",  safe_int(te.get("total_hours", 0))))
        _pes  = safe_int(three_pt.get("pessimistic", 0))
        _conf = safe_str(te.get("confidence", ""))
        _conf_clr = "#06d6a0" if "high" in _conf.lower() else "#ffd166" if "med" in _conf.lower() else "#f87171"

        # ── Row 1: 7 KPI cards ────────────────────────────────────────
        mc = st.columns(7)
        _kpi_items = [
            ("Total Hours",  str(safe_int(te.get("total_hours"))) + "h", "#00d4aa"),
            ("Duration",     safe_str(te.get("duration_weeks")),          "#14A0B9"),
            ("Optimistic",   str(_opt) + "h",                             "#06d6a0"),
            ("Most Likely",  str(_ml)  + "h",                             "#7b61ff"),
            ("Pessimistic",  str(_pes) + "h",                             "#f87171"),
            ("Confidence",   _conf,                                        _conf_clr),
            ("Buffer",       safe_str(te.get("buffer")),                  "#ffd166"),
        ]
        for col, (lbl, val, clr) in zip(mc, _kpi_items):
            with col:
                st.markdown(
                    f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);'
                    f'border-top:3px solid {clr};border-radius:10px;padding:12px 10px;text-align:center">'
                    f'<div style="font-size:1.05rem;font-weight:800;color:{clr};line-height:1.2">{val}</div>'
                    f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:.7px;margin-top:4px">{lbl}</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        if phases:
            _phase_colors = ["#00d4aa","#14A0B9","#7b61ff","#f87171","#ffd166","#06d6a0","#e9c46a","#f4845f"]

            # ── Row 2: Phase donut + three-point bar chart side by side ──
            ch1, ch2 = st.columns([1, 2])

            with ch1:
                # Phase effort donut
                _pnames = [safe_str(safe_dict(p).get("name","Phase")) for p in phases]
                _phours = [safe_int(safe_dict(p).get("hours", 0)) for p in phases]
                _total  = max(sum(_phours), 1)
                _pcts   = [round(h / _total * 100, 1) for h in _phours]
                fig_donut = go.Figure(go.Pie(
                    labels=_pnames, values=_phours,
                    hole=.55,
                    marker_colors=_phase_colors[:len(_pnames)],
                    textinfo="percent",
                    hovertemplate="<b>%{label}</b><br>%{value}h — %{percent}<extra></extra>",
                ))
                fig_donut.update_layout(
                    title=dict(text="Effort Split by Phase", font=dict(size=13, color="#94a3b8")),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                    showlegend=True,
                    legend=dict(font=dict(size=10, color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
                    annotations=[dict(
                        text=f"<b>{safe_int(te.get('total_hours'))}h</b>",
                        x=0.5, y=0.5, font=dict(size=16, color="#e2e8f0"), showarrow=False,
                    )],
                    margin=dict(t=40, b=10, l=10, r=10),
                )
                st.plotly_chart(fig_donut, width="stretch")

            with ch2:
                # Three-point horizontal bar chart
                _low_v  = [safe_int(safe_dict(p).get("low_hours",  int(safe_int(safe_dict(p).get("hours",0))*.8)))  for p in phases]
                _avg_v  = [safe_int(safe_dict(p).get("hours", 0)) for p in phases]
                _high_v = [safe_int(safe_dict(p).get("high_hours", int(safe_int(safe_dict(p).get("hours",0))*1.35))) for p in phases]
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(name="Optimistic",  x=_low_v,  y=_pnames, orientation="h", marker_color="#06d6a0", text=[str(v)+"h" for v in _low_v],  textposition="auto"))
                fig_bar.add_trace(go.Bar(name="Most Likely", x=_avg_v,  y=_pnames, orientation="h", marker_color="#7b61ff", text=[str(v)+"h" for v in _avg_v],  textposition="auto"))
                fig_bar.add_trace(go.Bar(name="Pessimistic", x=_high_v, y=_pnames, orientation="h", marker_color="#f87171", text=[str(v)+"h" for v in _high_v], textposition="auto"))
                fig_bar.update_layout(
                    title=dict(text="Three-Point Estimate by Phase", font=dict(size=13, color="#94a3b8")),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=300, barmode="group", xaxis_title="Hours",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                                font=dict(size=10, color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(t=40, b=10, l=10, r=10),
                )
                st.plotly_chart(fig_bar, width="stretch")

            # ── Gantt charts — @st.fragment for instant toggle ─────────────
            _qa_ref_wks = safe_int(te.get("qa_weeks", 3))
            _qa_ref_hrs = max(40, round(_qa_ref_wks * 40 * 0.30))

            # Cache key — changes when estimate data changes
            _gcache_key = f"_gfigs_v5_{safe_int(te.get('total_hours',0))}_{len(phases)}"

            if _gcache_key not in st.session_state:
                import plotly.graph_objects as _go2

                # ── Phase positions ───────────────────────────────────────
                _p_disc = [safe_dict(p) for p in phases if safe_str(safe_dict(p).get("domain")) == "Discovery"]
                _p_pm   = [safe_dict(p) for p in phases if safe_str(safe_dict(p).get("domain")) == "PM"]
                _p_doc  = [safe_dict(p) for p in phases if safe_str(safe_dict(p).get("domain")) == "Documentation"]
                _p_dev  = [safe_dict(p) for p in phases
                           if safe_str(safe_dict(p).get("domain")) not in ("Discovery", "PM", "Documentation")]

                _disc_dw = max(1, round(float(_p_disc[0].get("duration_weeks", 2)))) if _p_disc else 2
                _disc_s, _disc_e = 1, _disc_dw
                _dev_s = _disc_e + 1

                _dev_colors = ["#14A0B9","#7b61ff","#9b59b6","#f4845f","#ffd166","#e9c46a","#06d6a0"]
                _gph_dev = []
                for idx, p in enumerate(_p_dev):
                    dw = max(1, round(float(p.get("duration_weeks", 2))))
                    _gph_dev.append({
                        "name":   safe_str(p.get("name", f"Stream {idx+1}")),
                        "start":  _dev_s, "end": _dev_s + dw - 1,
                        "hours":  safe_int(p.get("hours", 0)),
                        "pct":    safe_str(p.get("percentage", "")),
                        "color":  _dev_colors[idx % len(_dev_colors)],
                        "domain": safe_str(p.get("domain", "")),
                    })

                _max_dev_e = max((g["end"] for g in _gph_dev), default=_dev_s + 4)
                _doc_dw  = max(1, round(float(_p_doc[0].get("duration_weeks", 1)))) if _p_doc else 1
                _doc_s   = _max_dev_e + 1
                _doc_e   = _doc_s + _doc_dw - 1
                _proj_end = _doc_e + 1
                _qa_s_g  = _dev_s
                _qa_e_g  = _max_dev_e
                _max_week = _proj_end

                # ── Y-axis order for phase Gantt ──────────────────────────
                _y_order = []
                if _p_disc: _y_order.append(safe_str(_p_disc[0].get("name","Discovery & Design")))
                for g in _gph_dev: _y_order.append(g["name"])
                _y_order.append("QA & Testing")
                if _p_doc: _y_order.append(safe_str(_p_doc[0].get("name","Documentation & Training")))
                if _p_pm:  _y_order.append(safe_str(_p_pm[0].get("name","Project Management")))

                # ── Build Phase Gantt figure ──────────────────────────────
                fig_gantt = _go2.Figure()

                if _p_disc:
                    _dn = safe_str(_p_disc[0].get("name","Discovery & Design"))
                    fig_gantt.add_trace(_go2.Bar(
                        name=_dn, x=[_disc_e - _disc_s + 1], y=[_dn],
                        base=[_disc_s - 1], orientation="h",
                        marker=dict(color="#00d4aa", opacity=0.9,
                                    line=dict(color="rgba(255,255,255,.2)", width=1)),
                        text=f"  {_dn}  {safe_int(_p_disc[0].get('hours',0))}h  {safe_str(_p_disc[0].get('percentage',''))}",
                        textposition="inside", insidetextanchor="start",
                        hovertemplate=f"<b>{_dn}</b><br>Wk {_disc_s}–{_disc_e}<br>"
                                      f"{safe_int(_p_disc[0].get('hours',0))}h · {safe_str(_p_disc[0].get('percentage',''))}<extra></extra>",
                    ))

                for g in _gph_dev:
                    fig_gantt.add_trace(_go2.Bar(
                        name=g["name"], x=[g["end"] - g["start"] + 1], y=[g["name"]],
                        base=[g["start"] - 1], orientation="h",
                        marker=dict(color=g["color"], opacity=0.88,
                                    line=dict(color="rgba(255,255,255,.15)", width=1)),
                        text=f"  {g['name']}  {g['hours']}h  {g['pct']}",
                        textposition="inside", insidetextanchor="start",
                        hovertemplate=(
                            f"<b>{g['name']}</b><br>Wk {g['start']}–{g['end']} (parallel)<br>"
                            f"{g['hours']}h · {g['pct']}<extra></extra>"
                        ),
                    ))

                fig_gantt.add_trace(_go2.Bar(
                    name="QA & Testing", x=[_qa_e_g - _qa_s_g + 1], y=["QA & Testing"],
                    base=[_qa_s_g - 1], orientation="h",
                    marker=dict(color="rgba(0,212,170,0.28)", line=dict(color="#00D4AA", width=2)),
                    text=f"  QA & Testing  Wk {_qa_s_g}–{_qa_e_g}",
                    textposition="inside", insidetextanchor="start",
                    textfont=dict(color="#FFFFFF", size=12),
                    hovertemplate=(
                        "<b>QA & Testing</b><br>"
                        f"Wk {_qa_s_g}–{_qa_e_g} — runs parallel with development<br>"
                        "Included in delivery cost (30% of dev effort)<br>"
                        "Not shown in hour estimates<extra></extra>"
                    ),
                ))

                if _p_doc:
                    _docn = safe_str(_p_doc[0].get("name","Documentation & Training"))
                    fig_gantt.add_trace(_go2.Bar(
                        name=_docn, x=[_doc_e - _doc_s + 1], y=[_docn],
                        base=[_doc_s - 1], orientation="h",
                        marker=dict(color="#e9c46a", opacity=0.85,
                                    line=dict(color="rgba(255,255,255,.15)", width=1)),
                        text=f"  {_docn}  {safe_int(_p_doc[0].get('hours',0))}h  {safe_str(_p_doc[0].get('percentage',''))}",
                        textposition="inside", insidetextanchor="start",
                        hovertemplate=(
                            f"<b>{_docn}</b><br>Wk {_doc_s}–{_doc_e}<br>"
                            f"{safe_int(_p_doc[0].get('hours',0))}h<extra></extra>"
                        ),
                    ))

                if _p_pm:
                    _pmn = safe_str(_p_pm[0].get("name","Project Management"))
                    fig_gantt.add_trace(_go2.Bar(
                        name=_pmn, x=[_proj_end], y=[_pmn],
                        base=[0], orientation="h",
                        marker=dict(color="rgba(100,116,139,0.35)",
                                    line=dict(color="rgba(148,163,184,.7)", width=1.5)),
                        text=f"  {_pmn}  {safe_int(_p_pm[0].get('hours',0))}h  (ongoing throughout)",
                        textposition="inside", insidetextanchor="start",
                        textfont=dict(color="#FFFFFF", size=12),
                        hovertemplate=(
                            f"<b>{_pmn}</b><br>Wk 1–{_proj_end} (ongoing)<br>"
                            f"{safe_int(_p_pm[0].get('hours',0))}h<extra></extra>"
                        ),
                    ))

                for m in milestones:
                    m = safe_dict(m)
                    mw = safe_int(m.get("week", 0))
                    if 0 < mw <= _max_week + 2:
                        fig_gantt.add_vline(x=mw - 0.5, line_width=1.5,
                                            line_dash="dot", line_color="rgba(255,209,102,.7)")
                        fig_gantt.add_annotation(
                            x=mw - 0.5, y=0, text=f"◆ {safe_str(m.get('name',''))}",
                            showarrow=False, font=dict(size=9, color="#ffd166"),
                            bgcolor="rgba(0,0,0,.6)", bordercolor="rgba(255,209,102,.4)",
                            borderwidth=1, borderpad=3, yanchor="top", yref="paper",
                        )

                fig_gantt.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    barmode="overlay",
                    height=max(240, len(_y_order) * 48 + 90),
                    xaxis=dict(title=dict(text="Week", font=dict(size=11, color="#64748b")),
                               tickmode="linear", tick0=1, dtick=1,
                               range=[0, _max_week + 1],
                               gridcolor="rgba(255,255,255,.05)",
                               tickfont=dict(size=10, color="#64748b")),
                    yaxis=dict(categoryorder="array",
                               categoryarray=list(reversed(_y_order)),
                               gridcolor="rgba(255,255,255,.04)",
                               tickfont=dict(size=10, color="#94a3b8")),
                    showlegend=False,
                    margin=dict(t=10, b=45, l=10, r=10),
                )

                # ── Build Resource Gantt figure ───────────────────────────
                _ROLE_NORM = {
                    "PM": "Project Manager", "BA": "Business Analyst",
                    "Architect": "Solution Architect", "Security": "Security Consultant",
                    "Developer": "Developer", "Senior Dev": "Developer",
                    "Frontend Dev": "Frontend Developer", "DevOps": "DevOps Engineer",
                    "QA": "QA Engineer", "Writer": "Technical Writer",
                    "SharePoint Dev": "SharePoint Developer",
                    "Product Owner": "Product Owner",
                    "Data Engineer": "Data Engineer", "ML Engineer": "ML Engineer",
                }
                _ROLE_ORDER = [
                    "Project Manager", "Business Analyst", "Solution Architect",
                    "Security Consultant", "Data Engineer", "ML Engineer",
                    "Developer", "Frontend Developer", "SharePoint Developer",
                    "DevOps Engineer", "QA Engineer", "Technical Writer", "Product Owner",
                ]
                _DOM_COLOR = {
                    "Discovery": "#00e5bb", "Data Engineering": "#00c2ff",
                    "AI / ML": "#a78bfa",  "SharePoint": "#c084fc",
                    "Custom App": "#fb923c", "Integration": "#fcd34d",
                    "DevOps": "#86efac",   "Documentation": "#fba94c",
                    "PM": "#8899aa",       "QA": "#34d399",
                }
                _DOM_ABBREV = {
                    "Discovery": "DISC", "Data Engineering": "DE", "AI / ML": "AI",
                    "SharePoint": "SP", "Custom App": "APP", "Integration": "INT",
                    "DevOps": "OPS", "Documentation": "DOC", "PM": "PM", "QA": "QA",
                }
                _ph_wmap = {}
                for _rp in _p_disc:
                    _ph_wmap[safe_str(_rp.get("name",""))] = (_disc_s, _disc_e, safe_str(_rp.get("domain","Discovery")))
                for _rg in _gph_dev:
                    _rph2 = next((safe_dict(p) for p in phases if safe_str(safe_dict(p).get("name")) == _rg["name"]), {})
                    _ph_wmap[_rg["name"]] = (_rg["start"], _rg["end"], safe_str(_rph2.get("domain", "Dev")))
                if _p_doc:
                    _ph_wmap[safe_str(_p_doc[0].get("name",""))] = (_doc_s, _doc_e, "Documentation")
                if _p_pm:
                    _ph_wmap[safe_str(_p_pm[0].get("name",""))] = (1, _proj_end, "PM")

                _res = {}
                for _rphx in phases:
                    _rphx = safe_dict(_rphx)
                    _rpn  = safe_str(_rphx.get("name",""))
                    _rng  = _ph_wmap.get(_rpn)
                    if not _rng:
                        continue
                    _rsw, _rew, _rdom = _rng
                    for _rt in _rphx.get("tasks", []):
                        _rt  = safe_dict(_rt)
                        _rl  = _ROLE_NORM.get(safe_str(_rt.get("role","Developer")), safe_str(_rt.get("role","Developer")))
                        _rh  = safe_int(_rt.get("hours", 0))
                        _sk  = (_rsw, _rew, _rpn)
                        if _rl not in _res: _res[_rl] = {}
                        if _sk not in _res[_rl]: _res[_rl][_sk] = {"hours": 0, "tasks": [], "domain": _rdom}
                        _res[_rl][_sk]["hours"] += _rh
                        _res[_rl][_sk]["tasks"].append(safe_str(_rt.get("name","")))

                _qa_sk = (_qa_s_g, _qa_e_g, "QA & Testing")
                if "QA Engineer" not in _res: _res["QA Engineer"] = {}
                _res["QA Engineer"][_qa_sk] = {
                    "hours": _qa_ref_hrs,
                    "tasks": ["Test planning & case design", "Test environment setup",
                              "Parallel test execution", "Defect reporting & retesting", "UAT support"],
                    "domain": "QA",
                }

                _active_roles = [r for r in _ROLE_ORDER if r in _res]
                for _r in _res:
                    if _r not in _active_roles: _active_roles.append(_r)

                # Compute totals + utilisation % for each role
                _avail_h   = max(1, _max_week) * 40
                _role_tot  = {_rl: sum(s["hours"] for s in _res[_rl].values()) for _rl in _active_roles}
                _role_util = {_rl: round(_role_tot[_rl] / _avail_h * 100) for _rl in _active_roles}

                # Y-axis tick labels: "Role Name  ·  Nh"
                _ytick_t = [f"{_rl}  ·  {_role_tot[_rl]}h" for _rl in _active_roles]
                _ytick_v = _active_roles[:]

                # One trace per role — array colors for multi-segment bars
                fig_res = _go2.Figure()
                for _rl in _active_roles:
                    _xs, _ys, _bs, _cs, _ts, _hovs = [], [], [], [], [], []
                    for (_rsw, _rew, _rpn), _seg in _res[_rl].items():
                        _dur  = max(1, _rew - _rsw + 1)
                        _rdom = _seg["domain"]
                        _rh   = _seg["hours"]
                        _abbr = _DOM_ABBREV.get(_rdom, _rdom[:4].upper())
                        _wkly = round(_rh / _dur, 1)
                        _t5   = _seg["tasks"][:5]
                        _more = max(0, len(_seg["tasks"]) - 5)
                        _xs.append(_dur)
                        _ys.append(_rl)
                        _bs.append(_rsw - 1)
                        _cs.append(_DOM_COLOR.get(_rdom, "#7b61ff"))
                        _ts.append(f"  {_abbr}  ·  {_rh}h")
                        _hovs.append(
                            f"<b>{_rl}</b>  ·  <i>{_rpn}</i><br>"
                            f"Wk {_rsw}–{_rew}  ·  <b>{_rh}h</b>  ·  ~{_wkly}h/wk<br>"
                            + "".join(f"▸ {t}<br>" for t in _t5)
                            + (f"…+{_more} more tasks" if _more else "")
                        )
                    fig_res.add_trace(_go2.Bar(
                        name=_rl, x=_xs, y=_ys, base=_bs, orientation="h",
                        marker=dict(color=_cs, opacity=0.92,
                                    line=dict(color="rgba(0,0,0,0)", width=0)),
                        text=_ts, textposition="inside", insidetextanchor="start",
                        textfont=dict(size=11, color="#ffffff",
                                      family="'DM Sans',sans-serif"),
                        customdata=_hovs,
                        hovertemplate="%{customdata}<extra></extra>",
                        showlegend=False,
                    ))

                # Utilisation % annotations on right side, colour-coded
                for _rl in _active_roles:
                    _upct = _role_util[_rl]
                    _ucol = ("#475569" if _upct < 20 else
                             "#00d4aa" if _upct < 65 else
                             "#ffd166" if _upct < 90 else "#f87171")
                    fig_res.add_annotation(
                        x=_max_week + 0.5, y=_rl, xref="x", yref="y",
                        text=f"<b>{_upct}%</b>",
                        showarrow=False, font=dict(size=11, color=_ucol),
                        xanchor="left", yanchor="middle",
                    )

                for m in milestones:
                    m = safe_dict(m)
                    mw = safe_int(m.get("week", 0))
                    if 0 < mw <= _max_week + 2:
                        fig_res.add_vline(x=mw - 0.5, line_width=1.5,
                                          line_dash="dot", line_color="rgba(255,209,102,.6)")
                        fig_res.add_annotation(
                            x=mw - 0.5, y=0, text=f"◆ {safe_str(m.get('name',''))}",
                            showarrow=False, font=dict(size=9, color="#ffd166"),
                            bgcolor="rgba(10,14,26,.8)", bordercolor="rgba(255,209,102,.45)",
                            borderwidth=1, borderpad=3, yanchor="top", yref="paper",
                        )

                fig_res.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(21,28,46,0.55)",
                    barmode="overlay",
                    height=max(340, len(_active_roles) * 58 + 110),
                    xaxis=dict(title=dict(text="Week", font=dict(size=11, color="#64748b")),
                               tickmode="linear", tick0=1, dtick=1,
                               range=[0, _max_week + 2.8],
                               gridcolor="rgba(255,255,255,.06)",
                               tickfont=dict(size=10, color="#64748b"),
                               showline=True, linecolor="rgba(255,255,255,.1)"),
                    yaxis=dict(categoryorder="array",
                               categoryarray=list(reversed(_active_roles)),
                               ticktext=list(reversed(_ytick_t)),
                               tickvals=list(reversed(_ytick_v)),
                               gridcolor="rgba(255,255,255,.05)",
                               tickfont=dict(size=11, color="#94a3b8",
                                             family="'DM Sans',sans-serif")),
                    showlegend=False,
                    margin=dict(t=16, b=50, l=0, r=75),
                    hoverlabel=dict(
                        bgcolor="#0f1928", bordercolor="#1e2a4a",
                        font=dict(size=12, color="#e2e8f0", family="'DM Sans',sans-serif"),
                    ),
                )

                st.session_state[_gcache_key] = (fig_gantt, fig_res, _DOM_COLOR)

            _cached = st.session_state.get(_gcache_key, (None, None, {}))
            _fph = _cached[0]
            _frs = _cached[1]
            _dcol = safe_dict(_cached[2]) if len(_cached) > 2 else {}

            if _fph is not None:
                # ── Phase Gantt ───────────────────────────────────────
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:10px;margin:18px 0 8px">'
                    '<div style="width:3px;height:18px;background:linear-gradient'
                    '(180deg,#00d4aa,#14A0B9);border-radius:2px"></div>'
                    '<span style="font-size:.95rem;font-weight:700;color:#e2e8f0">'
                    '📅 Project Timeline</span></div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(_fph, width="stretch",
                                config={"displayModeBar": False})

                # ── Resource Utilisation Gantt ────────────────────────
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:10px;margin:28px 0 8px">'
                    '<div style="width:3px;height:18px;background:linear-gradient'
                    '(180deg,#7b61ff,#a78bfa);border-radius:2px"></div>'
                    '<span style="font-size:.95rem;font-weight:700;color:#e2e8f0">'
                    '👤 Resource Utilisation</span></div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(_frs, width="stretch",
                                config={"displayModeBar": False})

                # Domain legend + utilisation key
                _lg = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 5px">'
                for _d, _c in _dcol.items():
                    _lg += (
                        f'<span style="background:{_c}22;border:1px solid {_c}66;'
                        f'color:{_c};font-size:.7rem;font-weight:600;'
                        f'padding:3px 12px;border-radius:20px">{_d}</span>'
                    )
                _lg += (
                    '</div>'
                    '<div style="display:flex;gap:14px;margin:5px 0 4px;flex-wrap:wrap">'
                    '<span style="font-size:.7rem;color:#64748b">⬛ &lt;20% underutilised</span>'
                    '<span style="font-size:.7rem;color:#00d4aa">⬛ 20–65% optimal</span>'
                    '<span style="font-size:.7rem;color:#ffd166">⬛ 65–90% busy</span>'
                    '<span style="font-size:.7rem;color:#f87171">⬛ &gt;90% overloaded</span>'
                    '</div>'
                    '<div style="font-size:.73rem;color:#64748b;margin-top:2px">'
                    '💡 Y-axis: role name · total allocated hours.  '
                    '% on the right = utilisation over full project duration.  '
                    'Hover bars for task details and weekly load.</div>'
                )
                st.markdown(_lg, unsafe_allow_html=True)

            # ── Detailed task breakdown per phase ─────────────────────
            st.markdown(
                '<div style="font-size:.8rem;font-weight:700;color:#94a3b8;'
                'border-left:3px solid #7b61ff;padding-left:10px;margin:16px 0 10px">'
                '🔍 Detailed Task Breakdown</div>',
                unsafe_allow_html=True,
            )
            for pi, phase in enumerate(phases):
                phase = safe_dict(phase)
                ph_name = safe_str(phase.get("name", "Phase"))
                ph_week = safe_str(phase.get("week_label", ""))
                ph_low  = safe_int(phase.get("low_hours", 0))
                ph_avg  = safe_int(phase.get("hours", 0))
                ph_high = safe_int(phase.get("high_hours", 0))
                ph_pct  = safe_str(phase.get("percentage", ""))
                header_txt = ph_name
                if ph_week:
                    header_txt += " (" + ph_week + ")"
                header_txt += " — " + str(ph_avg) + "h [" + str(ph_low) + "–" + str(ph_high) + "h]  " + ph_pct
                with st.expander(header_txt, expanded=(pi < 2)):
                    tasks = safe_list(phase.get("tasks"))
                    if tasks:
                        st.markdown(
                            '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
                            '<tr style="background:#1B3A5C;color:white;">'
                            '<th style="padding:6px 8px;text-align:left;">Sub-task</th>'
                            '<th style="padding:6px 8px;text-align:center;">Role</th>'
                            '<th style="padding:6px 8px;text-align:center;">Low (hrs)</th>'
                            '<th style="padding:6px 8px;text-align:center;">Avg (hrs)</th>'
                            '<th style="padding:6px 8px;text-align:center;">High (hrs)</th>'
                            '<th style="padding:6px 8px;text-align:left;">Justification</th>'
                            '</tr>' +
                            "".join(
                                '<tr style="background:' + ("#1a2a4a" if ti % 2 == 0 else "#0f1928") + ';color:#e2e8f0;">'
                                '<td style="padding:5px 8px;color:#e2e8f0;">'  + safe_str(safe_dict(tk).get("name")) + '</td>'
                                '<td style="padding:5px 8px;text-align:center;color:#00b4d8;">' + safe_str(safe_dict(tk).get("role")) + '</td>'
                                '<td style="padding:5px 8px;text-align:center;color:#94a3b8;">' + str(safe_int(safe_dict(tk).get("low_hours", 0))) + '</td>'
                                '<td style="padding:5px 8px;text-align:center;font-weight:bold;color:#00d4aa;">' + str(safe_int(safe_dict(tk).get("hours", 0))) + '</td>'
                                '<td style="padding:5px 8px;text-align:center;color:#94a3b8;">' + str(safe_int(safe_dict(tk).get("high_hours", 0))) + '</td>'
                                '<td style="padding:5px 8px;font-style:italic;color:#94a3b8;">'  + safe_str(safe_dict(tk).get("justification", "")) + '</td>'
                                '</tr>'
                                for ti, tk in enumerate(tasks)
                            ) +
                            '<tr style="background:rgba(0,212,170,.15);color:#00d4aa;font-weight:bold;">'
                            '<td style="padding:5px 8px;" colspan="2">Phase Total</td>'
                            '<td style="padding:5px 8px;text-align:center;">' + str(ph_low)  + '</td>'
                            '<td style="padding:5px 8px;text-align:center;">' + str(ph_avg)  + '</td>'
                            '<td style="padding:5px 8px;text-align:center;">' + str(ph_high) + '</td>'
                            '<td></td></tr>'
                            '</table>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("No sub-tasks for this phase.")

        # ── Milestone visual timeline ─────────────────────────────────
        if milestones:
            st.markdown(
                '<div style="font-size:.8rem;font-weight:700;color:#94a3b8;'
                'border-left:3px solid #ffd166;padding-left:10px;margin:20px 0 14px">'
                '🏁 Milestone Timeline</div>',
                unsafe_allow_html=True,
            )
            _ms_sorted = sorted(milestones, key=lambda m: safe_int(safe_dict(m).get("week", 0)))
            _ms_count  = len(_ms_sorted)
            _node_html = ""
            for idx, m in enumerate(_ms_sorted):
                m       = safe_dict(m)
                mw      = safe_int(m.get("week", 0))
                mname   = safe_str(m.get("name", ""))
                mdesc   = safe_str(m.get("description", ""))
                is_last = (idx == _ms_count - 1)
                dot_clr = "#ffd166" if idx == 0 else "#00d4aa" if is_last else "#14A0B9"
                _node_html += (
                    f'<div style="display:flex;flex-direction:column;align-items:center;'
                    f'flex:1;min-width:90px;max-width:160px;position:relative">'
                    # connector line (not on last)
                    + (
                        f'<div style="position:absolute;top:14px;left:50%;width:100%;height:2px;'
                        f'background:linear-gradient(90deg,{dot_clr}66,rgba(255,255,255,.1));z-index:0"></div>'
                        if not is_last else ''
                    )
                    # dot
                    + f'<div style="width:28px;height:28px;border-radius:50%;background:{dot_clr};'
                    f'border:3px solid rgba(255,255,255,.15);'
                    f'box-shadow:0 0 12px {dot_clr}88;z-index:1;flex-shrink:0;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:.65rem;font-weight:800;color:#000">W{mw}</div>'
                    # label
                    + f'<div style="margin-top:8px;text-align:center;padding:0 4px">'
                    f'<div style="font-size:.72rem;font-weight:700;color:#e2e8f0;line-height:1.3">{mname}</div>'
                    f'<div style="font-size:.65rem;color:#64748b;margin-top:3px;line-height:1.4">{mdesc}</div>'
                    f'</div></div>'
                )
            st.markdown(
                f'<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);'
                f'border-radius:14px;padding:24px 20px;overflow-x:auto">'
                f'<div style="display:flex;align-items:flex-start;justify-content:space-between;'
                f'gap:0;min-width:{max(500, _ms_count * 120)}px">'
                f'{_node_html}</div></div>',
                unsafe_allow_html=True,
            )

        # _quick_feedback("time", 'e.g. "hours are too low, add 20% for integration testing"')

        # ── RAG Historical Context ─────────────────────────────────────
        _rag_data  = safe_dict(r.get("rag", {}))
        # Deduplicate by name before displaying
        _seen_sp: set = set()
        _sim_projs = []
        for _sp in safe_list(_rag_data.get("similar_projects", [])):
            _sp_key = safe_str(safe_dict(_sp).get("name", "")).strip().lower()
            if _sp_key and _sp_key not in _seen_sp:
                _seen_sp.add(_sp_key)
                _sim_projs.append(_sp)
        _calib     = safe_dict(te.get("rag_calibration") or {})
        if _sim_projs or _calib:
            st.markdown(
                '<div style="font-size:.8rem;font-weight:700;color:#94a3b8;'
                'border-left:3px solid #00d4aa;padding-left:10px;margin:22px 0 10px">'
                '🔍 Historical Context Used for This Estimate</div>',
                unsafe_allow_html=True,
            )
            # Calibration banner — only shown when historical data actually shifted the number
            if _calib:
                _f_h  = safe_int(_calib.get("formula_hours", 0))
                _hi_h = safe_int(_calib.get("historical_hours", 0))
                _sc   = safe_int(_calib.get("similar_count", 0))
                _asim = float(_calib.get("avg_similarity", 0))
                _hw   = safe_str(_calib.get("hist_weight", ""))
                _ch   = safe_int(_calib.get("calibrated_hours", 0))
                st.markdown(
                    f'<div style="background:rgba(0,212,170,.07);border:1px solid rgba(0,212,170,.22);'
                    f'border-radius:10px;padding:14px 18px;margin-bottom:12px;'
                    f'display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
                    f'<div style="text-align:center">'
                    f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">Formula</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:#e2e8f0">{_f_h}h</div></div>'
                    f'<div style="color:#475569;font-size:1.2rem">⊕</div>'
                    f'<div style="text-align:center">'
                    f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">{_sc} similar · {_hw} weight</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:#00d4aa">{_hi_h}h historical</div></div>'
                    f'<div style="color:#475569;font-size:1.2rem">→</div>'
                    f'<div style="text-align:center">'
                    f'<div style="font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px">Calibrated Total</div>'
                    f'<div style="font-size:1.1rem;font-weight:700;color:#7b61ff">{_ch}h</div></div>'
                    f'<div style="margin-left:auto;font-size:.68rem;color:#64748b">'
                    f'Avg similarity {round(_asim*100)}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            # Matched project list
            if _sim_projs:
                _proj_rows = ""
                for _p in _sim_projs[:10]:
                    _p = safe_dict(_p)
                    _pn   = safe_str(_p.get("name") or "Unknown")
                    _psim = float(_p.get("similarity") or 0)
                    _phr  = safe_int(_p.get("hours", 0))
                    _bw   = int(_psim * 100)
                    _sc2  = "#06d6a0" if _psim >= 0.65 else "#ffd166" if _psim >= 0.40 else "#94a3b8"
                    _proj_rows += (
                        f'<div style="display:flex;align-items:center;gap:12px;padding:7px 0;'
                        f'border-bottom:1px solid rgba(255,255,255,.05)">'
                        f'<div style="flex:1;min-width:0">'
                        f'<div style="font-size:.8rem;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_pn}</div>'
                        f'<div style="background:rgba(255,255,255,.06);border-radius:3px;height:3px;margin-top:4px;overflow:hidden">'
                        f'<div style="height:100%;width:{_bw}%;background:{_sc2};border-radius:3px"></div></div></div>'
                        f'<div style="font-size:.72rem;color:{_sc2};font-weight:600;min-width:52px;text-align:right">{_bw}% match</div>'
                        + (f'<div style="font-size:.72rem;color:#94a3b8;min-width:44px;text-align:right">{_phr}h</div>' if _phr else '<div style="min-width:44px"></div>')
                        + f'</div>'
                    )
                st.markdown(
                    f'<div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.07);'
                    f'border-radius:10px;padding:12px 16px">'
                    f'<div style="font-size:.68rem;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:.5px;margin-bottom:10px">Matched Projects · {len(_sim_projs)} found</div>'
                    f'{_proj_rows}</div>',
                    unsafe_allow_html=True,
                )
        # ──────────────────────────────────────────────────────────────

        # ── Auto-correct pass (Claude, runs once per estimate) ────────
        _auto_correct_estimate(te, se)
        _render_auto_corrections_badge()

        # ── Agent review ──────────────────────────────────────────────
        _render_estimate_review(te, se)

        # _render_estimate_chat(te, se)  # hidden temporarily

    # ── Cost (Infrastructure) ──
    with tab_list[2]:
        _pre[2].empty()
        import pandas as pd

        # Show instant header immediately so the tab never looks blank
        st.markdown(
            '<div class="eci-tab-hdr">'
            '<span class="eci-tab-hdr-icon">💰</span>'
            '<span class="eci-tab-hdr-title">Infrastructure Cost Analysis</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Guard: if cost data isn't ready yet, show an appropriate state
        _ce_ready = bool(
            ce and isinstance(ce, dict) and any(
                ce.get(k) for k in ("azure_costs", "aws_costs", "gcp_costs",
                                    "infrastructure_costs", "monthly_total",
                                    "services", "third_party_costs")
            )
        )
        if not _ce_ready:
            if st.session_state.get("time_test_mode"):
                _tab_placeholder(
                    "💰", "Cost analysis not available in Quick Estimate mode",
                    "Run the full pipeline to generate detailed infrastructure cost estimates.",
                )
            else:
                st.markdown(
                    '<div style="border:1px solid rgba(255,209,102,.25);border-radius:14px;'
                    'padding:32px 28px;margin-top:8px;background:rgba(255,209,102,.04);">'
                    '<div style="display:flex;align-items:center;gap:14px;margin-bottom:18px">'
                    '<div style="font-size:2rem">⏳</div>'
                    '<div>'
                    '<div style="font-size:1rem;font-weight:700;color:#ffd166">'
                    'Cost analysis is being computed…</div>'
                    '<div style="font-size:.82rem;color:#94a3b8;margin-top:4px">'
                    'The AI agent is calculating infrastructure costs. '
                    'Switch back in a moment — this tab will populate automatically.</div>'
                    '</div></div>'
                    '<div class="eci-skel" style="width:100%;height:11px"></div>'
                    '<div class="eci-skel" style="width:75%;height:11px"></div>'
                    '<div class="eci-skel" style="width:88%;height:11px;margin-top:14px"></div>'
                    '<div class="eci-skel" style="width:60%;height:11px"></div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        # ── Detect cloud provider & gather all cost entries ────────────
        _provider      = _detect_cloud_provider(ce, se)          # pass semantic for keyword scan
        _prov_name, _prov_color, _region_label_txt, _default_region = _PROVIDER_UI.get(
            _provider, _PROVIDER_UI["azure"]
        )
        third_party    = safe_list(ce.get("third_party_costs"))
        _all_svc_costs = _get_all_cloud_costs(ce)

        # ── Mismatch guard: tech stack says AWS/GCP but cost estimate has wrong costs ──
        # This happens when cost_calculator ran before the provider fix was deployed,
        # or when the AI defaulted to Azure. Fall back to static catalog + show notice.
        _mismatch_note = False
        if _provider == "aws" and not ce.get("aws_costs") and not any(
            str(safe_dict(s).get("service", "")).lower().startswith(("ec2", "rds", "s3", "lambda", "eks", "dynamo", "sqs", "cognito", "cloudfront", "cloudwatch", "waf"))
            for s in _all_svc_costs
        ):
            _all_svc_costs = list(_AWS_CATALOG_SERVICES)
            _mismatch_note = True
        elif _provider == "gcp" and not ce.get("gcp_costs") and not any(
            str(safe_dict(s).get("service", "")).lower().startswith(("cloud run", "cloud sql", "cloud storage", "cloud functions", "gke", "bigquery", "pub/sub", "cloud armor", "memorystore"))
            for s in _all_svc_costs
        ):
            _all_svc_costs = list(_GCP_CATALOG_SERVICES)
            _mismatch_note = True

        # ── Provider badge ─────────────────────────────────────────────
        _prov_icons = {"azure": "☁️", "aws": "🟠", "gcp": "🔵", "multi-cloud": "🌐"}
        _prov_icon  = _prov_icons.get(_provider, "☁️")

        # ── Auto-fetch live pricing (Azure only; others use static catalog) ─
        if not _ce_ready:
            pass  # skip all rendering — loading card is already shown above
        elif _provider in ("azure", "multi-cloud"):
            if not st.session_state.get("live_pricing_cache"):
                with st.spinner("⚡ Fetching live Azure prices from prices.azure.com…"):
                    _live = _fetch_live_azure_pricing()
                if _live:
                    st.session_state.live_pricing_cache = _live
        elif _provider == "aws":
            # Use static catalog for AWS (AWS Pricing API requires auth + is 200 MB+)
            if "live_pricing_cache" not in st.session_state:
                st.session_state.live_pricing_cache = {}
            for _k, _v in _AWS_STATIC_CATALOG.items():
                st.session_state.live_pricing_cache.setdefault(_k, _v)
        elif _provider == "gcp":
            if "live_pricing_cache" not in st.session_state:
                st.session_state.live_pricing_cache = {}
            for _k, _v in _GCP_STATIC_CATALOG.items():
                st.session_state.live_pricing_cache.setdefault(_k, _v)

        live_cache = st.session_state.get("live_pricing_cache", {})

        # ── Patch service costs: live cache → broad catalog → AI value ───
        _patched_costs = []
        for _svc in _all_svc_costs:
            _s    = dict(safe_dict(_svc))
            # Normalise: some AI responses use "name" instead of "service"
            if not _s.get("service") and _s.get("name"):
                _s["service"] = _s["name"]
            _name = safe_str(_s.get("service", ""))
            if _name in live_cache:
                _s["monthly_cost"] = live_cache[_name]
                _s["_live"] = True
            else:
                _s["_live"] = False
                # If AI left the cost at 0 or missing, try broad catalog fallback
                if not safe_int(_s.get("monthly_cost", 0)):
                    _cat_val = _broad_catalog_cost(_name)
                    if _cat_val:
                        _s["monthly_cost"] = _cat_val
            _patched_costs.append(_s)

        _total_monthly  = sum(safe_int(_s.get("monthly_cost", 0)) for _s in _patched_costs)
        _total_monthly += sum(safe_int(safe_dict(t).get("monthly_cost", 0)) for t in third_party)

        # Last-resort fallback: AI has a total but per-service rows are still $0
        # Distribute the AI-computed total equally across services.
        if _total_monthly == 0 and _patched_costs:
            _ai_total = safe_int(ce.get("total_monthly_cost", 0))
            if _ai_total > 0:
                _per = max(1, _ai_total // len(_patched_costs))
                _remainder = _ai_total - _per * len(_patched_costs)
                for _idx, _s in enumerate(_patched_costs):
                    _s["monthly_cost"] = _per + (_remainder if _idx == 0 else 0)
                _total_monthly = _ai_total

        _total_annual   = _total_monthly * 12
        _live_count     = sum(1 for _s in _patched_costs if _s.get("_live"))
        st.session_state["_live_infra_total"] = _total_monthly

        # ── Hero KPI banner ───────────────────────────────────────────
        _price_src = "LIVE PRICES" if (_provider == "azure" and _live_count) else "CATALOG PRICES"
        _price_icon = "⚡" if (_provider == "azure" and _live_count) else "📋"
        _price_badge_color = "#00d4aa" if _live_count and _provider == "azure" else "#ffd166"
        _prov_badge = (
            f'<span style="background:{_prov_color}18;color:{_prov_color};'
            f'border:1px solid {_prov_color}44;border-radius:20px;padding:2px 10px;'
            f'font-size:.7rem;font-weight:700;margin-left:10px;vertical-align:middle;">'
            f'{_prov_icon} {_prov_name}</span>'
            f'<span style="background:{_price_badge_color}18;color:{_price_badge_color};'
            f'border:1px solid {_price_badge_color}44;border-radius:20px;padding:2px 10px;'
            f'font-size:.7rem;font-weight:700;margin-left:6px;vertical-align:middle;">'
            f'{_price_icon} {_price_src}</span>'
        )
        if _ce_ready:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#0f172a,#1e293b);'
                f'border:1px solid #334155;border-left:4px solid {_prov_color};'
                f'border-radius:14px;padding:20px 24px;margin-bottom:18px;">'
                f'<div style="font-size:.8rem;color:#64748b;margin-bottom:6px;">'
                f'Infrastructure Cost Estimate{_prov_badge}</div>'
                f'<div style="display:flex;gap:40px;align-items:flex-end;">'
                f'<div><div style="font-size:2.4rem;font-weight:800;color:{_prov_color};line-height:1;">'
                f'${_total_monthly:,}</div>'
                f'<div style="font-size:.72rem;color:#64748b;margin-top:3px;">per month</div></div>'
                f'<div><div style="font-size:1.5rem;font-weight:700;color:#94a3b8;">'
                f'${_total_annual:,}</div>'
                f'<div style="font-size:.72rem;color:#64748b;margin-top:3px;">per year</div></div>'
                f'<div><div style="font-size:1.4rem;font-weight:700;color:#7b61ff;">'
                f'{len(_patched_costs) + len(third_party)}</div>'
                f'<div style="font-size:.72rem;color:#64748b;margin-top:3px;">services</div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        # ── Mismatch notice: semantic says AWS/GCP but cost estimate was Azure ──
        if _mismatch_note:
            st.markdown(
                f'<div style="background:#ffd16618;border:1px solid #ffd16666;border-left:4px solid #ffd166;'
                f'border-radius:10px;padding:12px 18px;margin-bottom:14px;font-size:.82rem;color:#e2c84a;">'
                f'⚠️ <strong>Catalog estimate shown.</strong> '
                f'Your tech stack was identified as <strong>{_prov_name}</strong>, but the cost estimate '
                f'was generated for a different provider. Showing approximate {_prov_name} prices from the '
                f'built-in catalog. <strong>Re-run the pipeline</strong> to get an AI-generated estimate '
                f'calibrated for your exact {_prov_name} requirements.</div>',
                unsafe_allow_html=True,
            )

        # ── Region selector + Refresh (provider-aware) ─────────────────
        _AZURE_REGIONS = {
            "East US (Virginia)":               "eastus",
            "East US 2 (Virginia)":             "eastus2",
            "West US (California)":             "westus",
            "West US 2 (Washington)":           "westus2",
            "West US 3 (Arizona)":              "westus3",
            "Central US (Iowa)":                "centralus",
            "North Central US (Illinois)":      "northcentralus",
            "South Central US (Texas)":         "southcentralus",
            "Canada Central (Toronto)":         "canadacentral",
            "UK South (London)":                "uksouth",
            "UK West (Cardiff)":                "ukwest",
            "North Europe (Ireland)":           "northeurope",
            "West Europe (Netherlands)":        "westeurope",
            "France Central (Paris)":           "francecentral",
            "Germany West Central (Frankfurt)": "germanywestcentral",
            "Switzerland North (Zurich)":       "switzerlandnorth",
            "East Asia (Hong Kong)":            "eastasia",
            "Southeast Asia (Singapore)":       "southeastasia",
            "Japan East (Tokyo)":               "japaneast",
            "Korea Central (Seoul)":            "koreacentral",
            "Australia East (Sydney)":          "australiaeast",
            "Central India (Pune)":             "centralindia",
            "Brazil South (São Paulo)":         "brazilsouth",
            "UAE North (Dubai)":                "uaenorth",
        }

        # Pick the right region map and default
        if _provider == "aws":
            _region_map   = _AWS_REGIONS
            _region_key   = "_aws_region_label"
            _region_id_key = "_aws_region_id"
        elif _provider == "gcp":
            _region_map   = _GCP_REGIONS
            _region_key   = "_gcp_region_label"
            _region_id_key = "_gcp_region_id"
        else:
            _region_map   = _AZURE_REGIONS
            _region_key   = "_infra_region_label"
            _region_id_key = "_infra_region_arm"

        _region_labels       = list(_region_map.keys())
        _default_region_lbl  = st.session_state.get(_region_key, _default_region)
        if _default_region_lbl not in _region_labels:
            _default_region_lbl = _region_labels[0]

        if _ce_ready:
            _rc1, _rc2 = st.columns([3, 1])
            with _rc1:
                _sel_region_label = st.selectbox(
                    f"🌍 {_prov_name} Region",
                    _region_labels,
                    index=_region_labels.index(_default_region_lbl),
                    key="infra_region_select",
                    help=f"Prices vary by region. Select your target {_prov_name} deployment region.",
                )
            with _rc2:
                st.markdown('<div style="margin-top:28px"></div>', unsafe_allow_html=True)
                _do_refresh = st.button("🔄 Refresh Prices", key="btn_live_prices",
                                        type="secondary", width="stretch")
        else:
            _sel_region_label = _default_region_lbl
            _do_refresh = False

        if _do_refresh:
            _sel_region_id = _region_map[_sel_region_label]
            st.session_state[_region_key]   = _sel_region_label
            st.session_state[_region_id_key] = _sel_region_id
            if _provider in ("azure", "multi-cloud"):
                with st.spinner(f"Fetching live Azure prices for **{_sel_region_label}**…"):
                    _fresh = _fetch_live_azure_pricing(region=_sel_region_id)
                if _fresh:
                    st.session_state.live_pricing_cache = _fresh
                    st.toast(f"Prices updated for {_sel_region_label}", icon="✅")
                    st.rerun()
                else:
                    st.warning("Could not reach prices.azure.com — showing catalog prices.")
            else:
                # AWS / GCP: static catalog; just update region label and re-note
                st.toast(
                    f"Region set to {_sel_region_label}. "
                    f"{_prov_name} uses curated catalog prices (updated Apr-2026).",
                    icon="📋",
                )
                st.rerun()

        _active_region = st.session_state.get(_region_key, _default_region)
        if _ce_ready:
            if _provider == "aws":
                st.caption(f"📍 {_prov_name} catalog prices for: **{_active_region}** (on-demand, Apr-2026)")
            elif _provider == "gcp":
                st.caption(f"📍 {_prov_name} catalog prices for: **{_active_region}** (on-demand, Apr-2026)")
            else:
                st.caption(f"📍 Prices shown for: **{_active_region}**")

        # ── Cost breakdown by category (donut + table) ───────────────
        if _patched_costs or third_party:
            _CAT_RULES = [
                ("AI / ML",      ["openai","cognitive","machine learning","form recognizer","bot service",
                                  "language","vision","speech","ai","ml","anomaly","personalizer"]),
                ("Compute",      ["app service","function","container","kubernetes","aks","vm","virtual machine",
                                  "batch","spring","web app"]),
                ("Database",     ["sql","cosmos","postgresql","mysql","mariadb","redis","cache",
                                  "table storage","synapse","data warehouse"]),
                ("Storage",      ["blob","file","data lake","archive","disk","backup","recovery"]),
                ("Networking",   ["front door","api management","cdn","vpn","load balancer","firewall",
                                  "dns","private link","traffic manager","expressroute","bandwidth"]),
                ("Security",     ["key vault","active directory","sentinel","defender","security center",
                                  "identity","authentication","managed identity"]),
                ("Monitoring",   ["application insights","log analytics","monitor","diagnostic",
                                  "alert","metrics"]),
                ("Integration",  ["service bus","event hub","event grid","logic app","data factory",
                                  "integration","queue","relay","notification"]),
            ]
            _CAT_COLORS = {
                "AI / ML":      "#7b61ff",
                "Compute":      "#00d4aa",
                "Database":     "#14A0B9",
                "Storage":      "#ffd166",
                "Networking":   "#06d6a0",
                "Security":     "#f87171",
                "Monitoring":   "#e9c46a",
                "Integration":  "#f4845f",
                "Other":        "#475569",
            }

            def _categorise(name: str) -> str:
                nl = name.lower()
                for cat, keywords in _CAT_RULES:
                    if any(kw in nl for kw in keywords):
                        return cat
                return "Other"

            # Aggregate costs per category (azure + third-party)
            _cat_totals: dict = {}
            for _s in _patched_costs:
                cat = _categorise(safe_str(_s.get("service", "")))
                _cat_totals[cat] = _cat_totals.get(cat, 0) + safe_int(_s.get("monthly_cost", 0))
            for _t in third_party:
                cat = _categorise(safe_str(_t.get("name", "")))
                _cat_totals[cat] = _cat_totals.get(cat, 0) + safe_int(safe_dict(_t).get("monthly_cost", 0))

            _cat_totals = {k: v for k, v in _cat_totals.items() if v > 0}
            _cat_sorted = sorted(_cat_totals.items(), key=lambda x: x[1], reverse=True)

            if _cat_sorted:
                _cd1, _cd2 = st.columns([1, 1])

                with _cd1:
                    import plotly.graph_objects as _go_cat
                    _clbls = [c[0] for c in _cat_sorted]
                    _cvals = [c[1] for c in _cat_sorted]
                    _cclrs = [_CAT_COLORS.get(c[0], "#475569") for c in _cat_sorted]
                    _fig_cat = _go_cat.Figure(_go_cat.Pie(
                        labels=_clbls, values=_cvals, hole=.55,
                        marker=dict(colors=_cclrs, line=dict(color="rgba(0,0,0,.3)", width=2)),
                        textinfo="percent",
                        hovertemplate="<b>%{label}</b><br>$%{value:,}/mo — %{percent}<extra></extra>",
                        direction="clockwise",
                        sort=False,
                    ))
                    _fig_cat.update_layout(
                        title=dict(text="Spend by Category", font=dict(size=13, color="#94a3b8")),
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        height=300,
                        showlegend=True,
                        legend=dict(font=dict(size=10, color="#94a3b8"),
                                    bgcolor="rgba(0,0,0,0)", orientation="v",
                                    x=1.02, y=0.5, xanchor="left"),
                        annotations=[dict(
                            text=f"<b>${_total_monthly:,}</b><br><span style='font-size:10px'>/mo</span>",
                            x=0.5, y=0.5, font=dict(size=14, color="#e2e8f0"),
                            showarrow=False,
                        )],
                        margin=dict(t=40, b=10, l=10, r=120),
                    )
                    st.plotly_chart(_fig_cat, width="stretch")

                with _cd2:
                    st.markdown(
                        '<div style="font-size:.68rem;font-weight:700;color:#64748b;'
                        'text-transform:uppercase;letter-spacing:.7px;margin-bottom:10px;margin-top:8px">'
                        'Category Breakdown</div>',
                        unsafe_allow_html=True,
                    )
                    _cat_total_sum = max(sum(_cvals), 1)
                    for _cname, _cval in _cat_sorted:
                        _cpct  = int(_cval / _cat_total_sum * 100)
                        _cclr  = _CAT_COLORS.get(_cname, "#475569")
                        st.markdown(
                            f'<div style="margin-bottom:9px">'
                            f'<div style="display:flex;justify-content:space-between;'
                            f'align-items:center;margin-bottom:4px">'
                            f'<div style="display:flex;align-items:center;gap:7px">'
                            f'<div style="width:10px;height:10px;border-radius:50%;'
                            f'background:{_cclr};box-shadow:0 0 6px {_cclr}88;flex-shrink:0"></div>'
                            f'<span style="font-size:.78rem;color:#e2e8f0;font-weight:600">{_cname}</span>'
                            f'</div>'
                            f'<div style="text-align:right">'
                            f'<span style="font-size:.82rem;font-weight:700;color:{_cclr}">'
                            f'${_cval:,}</span>'
                            f'<span style="font-size:.68rem;color:#64748b;margin-left:4px">/mo</span>'
                            f'</div></div>'
                            f'<div style="background:rgba(255,255,255,.07);border-radius:4px;height:5px">'
                            f'<div style="height:100%;width:{_cpct}%;border-radius:4px;'
                            f'background:{_cclr};box-shadow:0 0 6px {_cclr}66;'
                            f'transition:width .5s ease"></div>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

        # ── Horizontal cost bar chart ──────────────────────────────────
        if _patched_costs and any(safe_int(_s.get("monthly_cost", 0)) for _s in _patched_costs):
            _bar_names  = [safe_str(_s.get("service", "Unknown")) or "Unknown" for _s in _patched_costs]
            _bar_vals   = [safe_int(_s.get("monthly_cost", 0)) for _s in _patched_costs]
            _bar_colors = [
                _prov_color if (_s.get("_live") or _provider != "azure") else "#7b61ff"
                for _s in _patched_costs
            ]
            _bar_text   = [
                f"${v:,}/mo {'⚡' if (_s.get('_live') and _provider == 'azure') else '📋'}"
                for v, _s in zip(_bar_vals, _patched_costs)
            ]
            # Sort descending for readability; filter out zero-cost rows
            _combined = [(v, n, c, t) for v, n, c, t in zip(_bar_vals, _bar_names, _bar_colors, _bar_text) if v > 0]
            if not _combined:
                _combined = list(zip(_bar_vals, _bar_names, _bar_colors, _bar_text))
            _sorted = sorted(_combined, reverse=True)
            _bar_vals, _bar_names, _bar_colors, _bar_text = zip(*_sorted) if _sorted else ([], [], [], [])

            import plotly.graph_objects as _go
            _fig = _go.Figure(_go.Bar(
                x=list(_bar_vals),
                y=list(_bar_names),
                orientation="h",
                marker_color=list(_bar_colors),
                text=list(_bar_text),
                textposition="outside",
                textfont=dict(size=11, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>$%{x:,.0f}/month<extra></extra>",
            ))
            _chart_legend = (
                f"<span style='font-size:11px;color:{_prov_color}'>⚡ Live</span>"
                f"  <span style='font-size:11px;color:#475569'>📋 Catalog</span>"
                if _provider == "azure" else
                f"<span style='font-size:11px;color:{_prov_color}'>📋 {_prov_name} Catalog (Apr-2026)</span>"
            )
            _fig.update_layout(
                title=dict(
                    text=f"Monthly Cost by Service  {_chart_legend}",
                    font=dict(size=14, color="#e2e8f0"),
                ),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=max(280, 36 * len(_bar_names) + 80),
                margin=dict(l=0, r=100, t=50, b=20),
                xaxis=dict(
                    showgrid=True, gridcolor="#1e293b",
                    tickprefix="$", tickformat=",",
                    color="#64748b",
                ),
                yaxis=dict(color="#e2e8f0", automargin=True),
                bargap=0.3,
            )
            st.plotly_chart(_fig, width="stretch")

        # ── Service cards table ───────────────────────────────────────
        _svc_section_label = {
            "azure":       "Azure Services",
            "aws":         "AWS Services",
            "gcp":         "GCP Services",
            "multi-cloud": "Cloud Services (Multi-Cloud)",
        }.get(_provider, "Cloud Services")

        st.markdown(
            f'<div style="font-size:.85rem;font-weight:700;color:#cbd5e1;'
            f'border-left:3px solid {_prov_color};padding-left:10px;margin:16px 0 10px;">'
            f'{_prov_icon} {_svc_section_label}</div>',
            unsafe_allow_html=True,
        )
        _max_cost = max((safe_int(_s.get("monthly_cost", 0)) for _s in _patched_costs), default=1) or 1
        for _s in sorted(_patched_costs, key=lambda x: safe_int(x.get("monthly_cost", 0)), reverse=True):
            _nm      = safe_str(_s.get("service", ""))
            _tr      = safe_str(_s.get("tier", ""))
            _dsc     = safe_str(_s.get("description", ""))
            _mc      = safe_int(_s.get("monthly_cost", 0))
            _pct     = min(100, int(_mc / _max_cost * 100))
            _is_live = _s.get("_live", False)
            _region  = safe_str(_s.get("region", _active_region))
            _cat     = safe_str(_s.get("category", "")) or _categorise(_nm)
            _cat_clr = _CAT_COLORS.get(_cat, "#475569")

            _price_src_label = "live" if (_is_live and _provider == "azure") else "catalog"
            _price_src_clr   = _prov_color if _is_live and _provider == "azure" else "#64748b"
            _live_badge = (
                f'<span style="font-size:.62rem;color:{_price_src_clr};'
                f'background:{_price_src_clr}15;border:1px solid {_price_src_clr}33;'
                f'border-radius:10px;padding:1px 7px;margin-left:6px;">'
                f'{"⚡" if _is_live and _provider == "azure" else "📋"} {_price_src_label}</span>'
            )
            _cat_badge = (
                f'<span style="font-size:.62rem;font-weight:600;color:{_cat_clr};'
                f'background:{_cat_clr}18;border:1px solid {_cat_clr}44;'
                f'border-radius:10px;padding:1px 8px;margin-left:6px;">{_cat}</span>'
            )
            _bar_clr  = _prov_color if _is_live else "#334155"
            _cost_clr = _prov_color if _is_live else "#94a3b8"
            st.markdown(
                f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;'
                f'padding:12px 16px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:2px">'
                f'<span style="font-weight:700;color:#e2e8f0;">{_nm}</span>'
                f'{_live_badge}{_cat_badge}'
                f'<span style="font-size:.68rem;color:#475569;margin-left:8px">{_tr}</span>'
                f'</div>'
                f'<div style="font-size:1.1rem;font-weight:800;color:{_cost_clr};'
                f'white-space:nowrap;margin-left:12px">'
                f'${_mc:,}<span style="font-size:.7rem;color:#475569;font-weight:400;">/mo</span></div>'
                f'</div>'
                f'<div style="background:#1e293b;border-radius:4px;height:4px;margin-bottom:6px;">'
                f'<div style="background:{_bar_clr};border-radius:4px;height:4px;width:{_pct}%;'
                f'transition:width .4s ease;"></div></div>'
                f'<div style="font-size:.75rem;color:#64748b;">{_dsc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if third_party:
            st.markdown(
                '<div style="font-size:.85rem;font-weight:700;color:#cbd5e1;'
                'border-left:3px solid #7b61ff;padding-left:10px;margin:16px 0 10px;">Third-Party Services</div>',
                unsafe_allow_html=True,
            )
            for tp in third_party:
                tp = safe_dict(tp)
                _nm  = safe_str(tp.get("name", ""))
                _mc  = safe_int(tp.get("monthly_cost", 0))
                _dsc = safe_str(tp.get("description", ""))
                st.markdown(
                    f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;'
                    f'padding:12px 16px;margin-bottom:8px;display:flex;'
                    f'justify-content:space-between;align-items:center;">'
                    f'<div><span style="font-weight:600;color:#e2e8f0;">{_nm}</span>'
                    f'<div style="font-size:.75rem;color:#64748b;margin-top:2px;">{_dsc}</div></div>'
                    f'<div style="font-size:1.05rem;font-weight:700;color:#7b61ff;">'
                    f'${_mc:,}<span style="font-size:.7rem;color:#475569;font-weight:400;">/mo</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Cost Optimization Tips ─────────────────────────────────────
        opt_tips = safe_list(ce.get("cost_optimization"))
        if opt_tips:
            st.markdown(
                '<div style="font-size:.85rem;font-weight:700;color:#cbd5e1;'
                'border-left:3px solid #ffd166;padding-left:10px;margin:16px 0 10px;">💡 Cost Optimization Tips</div>',
                unsafe_allow_html=True,
            )
            _tip_icons = ["🔵", "🟢", "🟡", "🟠", "🔴", "🟣"]
            for _i, tip in enumerate(opt_tips):
                st.markdown(
                    f'<div style="background:#0f172a;border:1px solid #1e293b;border-left:3px solid #ffd166;'
                    f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;'
                    f'font-size:.82rem;color:#cbd5e1;">'
                    f'{_tip_icons[_i % len(_tip_icons)]} {safe_str(tip)}</div>',
                    unsafe_allow_html=True,
                )

        if _ce_ready:
            notes = safe_str(ce.get("notes"))
            if notes:
                st.info(notes)
            _quick_feedback("cost", 'e.g. "switch SQL to Premium tier, add Redis Cache"')

    # ── Scope & Risk ──
    with tab_list[3]:
        _pre[3].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">📋</span>'
                    '<span class="eci-tab-hdr-title">Scope & Risk Analysis</span></div>', unsafe_allow_html=True)
        if ri or ar:
            _render_scope_risk_tab(se, te, ar, ri, r)
        else:
            _tab_placeholder("📋", "Scope & Risk not generated",
                             "Run the full pipeline to analyse risks and define scope.")

    # ── Architecture ──
    with tab_list[4]:
        _pre[4].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">🏗️</span>'
                    '<span class="eci-tab-hdr-title">Solution Architecture</span></div>', unsafe_allow_html=True)
        if ar and ar.get("components"):
            render_architecture_tab(ar, te, ce, mermaid_diagrams=safe_dict(r.get("mermaid_diagrams")), semantic=se, ai_client=_pick_ai_for("architecture"))
            # _quick_feedback("architecture", ...)  # hidden temporarily
        else:
            _tab_placeholder("🏗️", "Architecture not designed",
                             "Run the full pipeline to generate the solution architecture diagram.")

    # ── Diagrams (Mermaid.js) ──
    with tab_list[5]:
        _pre[5].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">📐</span>'
                    '<span class="eci-tab-hdr-title">Architecture Diagrams</span></div>', unsafe_allow_html=True)
        mermaid_data = safe_dict(r.get("mermaid_diagrams"))
        if mermaid_data:
            diagram_map = [
                ("infrastructure", "🏗️ Infrastructure",   safe_str(mermaid_data.get("infrastructure", ""))),
                ("data_flow",      "🔄 Data Flow",         safe_str(mermaid_data.get("data_flow", ""))),
                ("sequence",       "📨 Sequence",          safe_str(mermaid_data.get("sequence", ""))),
                ("deployment",     "🚀 Deployment",        safe_str(mermaid_data.get("deployment", ""))),
                ("security",       "🔒 Security",          safe_str(mermaid_data.get("security", ""))),
            ]
            render_mermaid_tabs(diagram_map)
        else:
            _tab_placeholder("📐", "Diagrams not generated",
                             "Run the full pipeline to generate Mermaid architecture diagrams.")

    # ── Proposal ──
    with tab_list[6]:
        _pre[6].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">📄</span>'
                    '<span class="eci-tab-hdr-title">Client Proposal</span></div>', unsafe_allow_html=True)
        _render_proposal_tab(r, _pick_ai_for("proposal"))

    # ── Team & Roles — Deal Cost Calculator (restricted to authorised users) ──
    with tab_list[7]:
        _pre[7].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">👥</span>'
                    '<span class="eci-tab-hdr-title">Team & Roles</span></div>', unsafe_allow_html=True)
        from .config_loader import can_view_team_roles as _can_view_tr
        if _can_view_tr():
            render_team_roles_tab(r, se, te, _pick_ai_for("proposal"))
        else:
            st.info(
                "🔒 **Access Restricted** — This section contains cost and pricing information "
                "and is only visible to authorised users.\n\n"
                "Contact your administrator to request access.",
                icon="🔐",
            )

    # ── Discovery Prep Deck ──
    with tab_list[8]:
        _pre[8].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">🎯</span>'
                    '<span class="eci-tab-hdr-title">Discovery Prep</span></div>', unsafe_allow_html=True)
        _has_discovery = bool(r.get("discovery_questions") and r.get("discovery_questions") != {})
        if _has_discovery:
            _render_discovery_tab(r)
        else:
            _tab_placeholder("🎯", "Discovery questions not generated",
                             "Run the full pipeline to generate a discovery preparation deck.")

    # ── Scenario Modelling ──
    with tab_list[9]:
        _pre[9].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">🔮</span>'
                    '<span class="eci-tab-hdr-title">Scenario Modelling</span></div>', unsafe_allow_html=True)
        render_scenario_tab()

    # ── 3D Architecture Fly-Through ──
    with tab_list[10]:
        _pre[10].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">🎮</span>'
                    '<span class="eci-tab-hdr-title">3D Architecture View</span></div>', unsafe_allow_html=True)
        if ar and ar.get("components"):
            _render_3d_view_tab(ar, ce, r)
        else:
            _tab_placeholder("🎮", "3D view not available",
                             "Architecture must be generated first. Run the full pipeline.")

    # ── Chat ──
    with tab_list[11]:
        _pre[11].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">💬</span>'
                    '<span class="eci-tab-hdr-title">BELLA Chat</span></div>', unsafe_allow_html=True)
        _render_proposal_chat(r, se, te, ce, ri)

    # ── History ──
    with tab_list[12]:
        _pre[12].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">📜</span>'
                    '<span class="eci-tab-hdr-title">Version History</span></div>', unsafe_allow_html=True)
        render_version_history_tab(r)

    # ── Live Demo ──
    with tab_list[13]:
        _pre[13].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">🎯</span>'
                    '<span class="eci-tab-hdr-title">Live Demo Generator</span></div>', unsafe_allow_html=True)
        from .config_loader import can_view_live_demo as _can_view_ld
        if not _can_view_ld():
            st.info(
                "🔒 **Access Restricted** — Live Demo is available to authorised users only.\n\n"
                "Contact your administrator to request access.",
                icon="🔐",
            )
        elif se and se.get("project_type"):
            render_live_demo_tab(se, te, ce, r)
        else:
            _tab_placeholder("🎯", "Live demo not available",
                             "Run the full pipeline to enable the live demo generator.")

    # ── Delivery ──
    with tab_list[14]:
        _pre[14].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">📦</span>'
                    '<span class="eci-tab-hdr-title">Delivery Package</span></div>', unsafe_allow_html=True)
        # ── Version selector ───────────────────────────────────────────
        _del_r, _del_se, _del_te, _del_ce, _del_ri, _del_ar, _del_ver = \
            get_delivery_version_data(r, se, te, ce, ri, ar)

        proj_name = _del_se.get("project_type", "Project") if isinstance(_del_se, dict) else "Project"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _ver_suffix = f"_v{_del_ver}" if _del_ver else ""

        # Pre-generate all deliverables once (proposal uses user edits if any)
        _r_edits         = _build_r_with_edits(_del_r)
        _final_est_bytes = generate_final_estimation(_del_r, project_name=proj_name)
        _xl_data         = generate_time_excel(_del_te, _del_se)
        _lenox_data      = generate_monogram_excel(_del_te, _del_se, _del_ce, _del_ri, _del_r)
        _cost_xl         = generate_cost_excel(_del_ce, _del_te, _del_se)
        _pdf_data        = generate_proposal_pdf(_r_edits)
        _pptx_dl         = generate_proposal_pptx(_r_edits)
        _sow_dl          = generate_sow_pdf(_r_edits)
        _arch_dot        = None
        _flow_dot        = None
        try:
            _arch_dot = generate_architecture_diagram(_del_ar)
        except Exception:
            pass
        try:
            _flow_dot = generate_flow_diagram(_del_te)
        except Exception:
            pass

        # Header
        st.markdown(
            '<div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);'
            'border:1px solid #334155;border-radius:16px;padding:28px 32px 20px;margin-bottom:24px;">'
            '<div style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:6px;">📦 Delivery Center</div>'
            '<div style="font-size:.875rem;color:#94a3b8;">All project deliverables in one place — download individually or grab everything as a ZIP bundle.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Hero: Final Estimation ──────────────────────────────────────
        if _final_est_bytes:
            st.markdown(
                '<div style="background:linear-gradient(90deg,#00d4aa22,#00b4d822);'
                'border:1px solid #00d4aa55;border-radius:12px;padding:20px 24px;margin-bottom:20px;">'
                '<div style="font-size:1.1rem;font-weight:700;color:#00d4aa;margin-bottom:4px;">⭐ Final Estimation Package</div>'
                '<div style="font-size:.8rem;color:#94a3b8;">Multi-sheet Excel: Summary · Development · DevOps & Cloud · Infra Cost · Version History</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download Final Estimation (Excel)",
                data=_final_est_bytes,
                file_name="Final_Estimation_" + proj_name.replace(" ", "_") + _ver_suffix + "_" + ts + ".xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch", type="primary", key="del_final_est",
                help="Multi-sheet estimation: Summary | Development | DevOps & Cloud | Infra Cost | Version History",
            )
            st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

        # ── Section label helper ──────────────────────────────────────
        def _sec(icon, title, subtitle=""):
            sub_html = f'<div style="font-size:.75rem;color:#64748b;margin-top:2px;">{subtitle}</div>' if subtitle else ""
            st.markdown(
                f'<div style="border-left:3px solid #334155;padding:6px 0 6px 14px;margin:18px 0 10px;">'
                f'<div style="font-size:.95rem;font-weight:600;color:#cbd5e1;">{icon} {title}</div>'
                f'{sub_html}</div>',
                unsafe_allow_html=True,
            )

        # ── Estimations ────────────────────────────────────────────────
        _sec("📊", "Estimations", "Time, cost and full-scope workbooks")
        est_cols = st.columns(3)
        with est_cols[0]:
            if _xl_data:
                st.download_button("⏱️ Time Estimate (Excel)", data=_xl_data,
                    file_name="ECI_Time_Estimate" + _ver_suffix + "_" + ts + ".xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch", type="primary", key="del_xl")
            else:
                st.button("⏱️ Time Estimate", disabled=True, width="stretch", key="del_xl_dis")
        with est_cols[1]:
            if _lenox_data:
                st.download_button("📊 Estimation (ECI Standard)", data=_lenox_data,
                    file_name="ECI_Estimation" + _ver_suffix + "_" + ts + ".xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch", type="primary", key="del_lenox")
            else:
                st.button("📊 Estimation (ECI Standard)", disabled=True, width="stretch", key="del_lenox_dis")
        with est_cols[2]:
            if _cost_xl:
                st.download_button("💰 Cost Estimate (Excel)", data=_cost_xl,
                    file_name="ECI_Cost_Estimate" + _ver_suffix + "_" + ts + ".xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch", type="primary", key="del_cost_xl")
            else:
                st.button("💰 Cost Estimate", disabled=True, width="stretch", key="del_cost_dis")

        # ── Proposal Documents ─────────────────────────────────────────
        _sec("📄", "Proposal Documents", "Client-ready deliverables")
        prop_cols = st.columns(3)
        with prop_cols[0]:
            if _pdf_data:
                if st.download_button("📄 Proposal (PDF)", data=_pdf_data,
                    file_name="ECI_Proposal" + _ver_suffix + "_" + ts + ".pdf",
                    mime="application/pdf",
                    width="stretch", type="primary", key="del_pdf"):
                    _log_act("export_pdf", f"Downloaded Proposal PDF — {st.session_state.get('proposal_client_name','')}", "Export")
            else:
                st.button("📄 Proposal PDF", disabled=True, width="stretch", key="del_pdf_dis")
        with prop_cols[1]:
            if _pptx_dl:
                if st.download_button("📑 Proposal (PowerPoint)", data=_pptx_dl,
                    file_name="ECI_Proposal" + _ver_suffix + "_" + ts + ".pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    width="stretch", type="primary", key="del_pptx"):
                    _log_act("export_pptx", f"Downloaded Proposal PPTX — {st.session_state.get('proposal_client_name','')}", "Export")
            else:
                st.button("📑 Proposal PPTX", disabled=True, width="stretch", key="del_pptx_dis")
        with prop_cols[2]:
            if _sow_dl:
                st.download_button("📝 Statement of Work (PDF)", data=_sow_dl,
                    file_name="ECI_SOW" + _ver_suffix + "_" + ts + ".pdf",
                    mime="application/pdf",
                    width="stretch", type="primary", key="del_sow")
            else:
                st.button("📝 SOW PDF", disabled=True, width="stretch", key="del_sow_dis")

        # ── Architecture Diagrams ──────────────────────────────────────
        _sec("🏗️", "Architecture Diagrams", "SVG, PNG and DOT formats")
        arch_cols2 = st.columns(3)
        with arch_cols2[0]:
            if _arch_dot:
                _arch_svg2 = render_dot_to_svg(_arch_dot)
                if _arch_svg2:
                    st.download_button("🏗️ Architecture (SVG)", data=_arch_svg2,
                        file_name="ECI_Architecture" + _ver_suffix + "_" + ts + ".svg", mime="image/svg+xml",
                        width="stretch", type="primary", key="del_arch_svg")
                else:
                    _arch_html2 = render_dot_to_html(_arch_dot)
                    if _arch_html2:
                        st.download_button("🏗️ Architecture (HTML)", data=_arch_html2,
                            file_name="ECI_Architecture" + _ver_suffix + "_" + ts + ".html", mime="text/html",
                            width="stretch", type="primary", key="del_arch_html")
        with arch_cols2[1]:
            if _arch_dot:
                _arch_png2 = render_dot_to_png(_arch_dot)
                if _arch_png2:
                    st.download_button("🏗️ Architecture (PNG)", data=_arch_png2,
                        file_name="ECI_Architecture" + _ver_suffix + "_" + ts + ".png", mime="image/png",
                        width="stretch", type="primary", key="del_arch_png")
        with arch_cols2[2]:
            if _arch_dot:
                st.download_button("🏗️ Architecture (DOT)", data=_arch_dot.encode("utf-8"),
                    file_name="ECI_Architecture" + _ver_suffix + "_" + ts + ".dot", mime="text/plain",
                    width="stretch", key="del_arch_dot")

        flow_cols2 = st.columns(3)
        with flow_cols2[0]:
            if _flow_dot:
                _flow_svg2 = render_dot_to_svg(_flow_dot)
                if _flow_svg2:
                    st.download_button("🔄 Workflow (SVG)", data=_flow_svg2,
                        file_name="ECI_Workflow" + _ver_suffix + "_" + ts + ".svg", mime="image/svg+xml",
                        width="stretch", type="primary", key="del_flow_svg")
                else:
                    _flow_html2 = render_dot_to_html(_flow_dot)
                    if _flow_html2:
                        st.download_button("🔄 Workflow (HTML)", data=_flow_html2,
                            file_name="ECI_Workflow" + _ver_suffix + "_" + ts + ".html", mime="text/html",
                            width="stretch", type="primary", key="del_flow_html")
        with flow_cols2[1]:
            if _flow_dot:
                _flow_png2 = render_dot_to_png(_flow_dot)
                if _flow_png2:
                    st.download_button("🔄 Workflow (PNG)", data=_flow_png2,
                        file_name="ECI_Workflow" + _ver_suffix + "_" + ts + ".png", mime="image/png",
                        width="stretch", type="primary", key="del_flow_png")
        with flow_cols2[2]:
            if _flow_dot:
                st.download_button("🔄 Workflow (DOT)", data=_flow_dot.encode("utf-8"),
                    file_name="ECI_Workflow" + _ver_suffix + "_" + ts + ".dot", mime="text/plain",
                    width="stretch", key="del_flow_dot")

        # ── Mermaid Diagrams JSON ──────────────────────────────────────
        _mermaid_data2 = safe_dict(_del_r.get("mermaid_diagrams"))
        if _mermaid_data2:
            _sec("📐", "Mermaid Diagrams", "Raw diagram definitions (JSON)")
            st.download_button("📐 All Diagrams (JSON)", data=json.dumps(_mermaid_data2, indent=2),
                file_name="ECI_Diagrams" + _ver_suffix + "_" + ts + ".json", mime="application/json",
                width="stretch", key="del_diagrams_json")

        # ── Raw Data ───────────────────────────────────────────────────
        _sec("🗄️", "Raw Data", "Complete estimation data in JSON format")
        st.download_button("📋 Full Project Data (JSON)", data=json.dumps(_del_r, indent=2, default=str),
            file_name="ECI_Data" + _ver_suffix + "_" + ts + ".json", mime="application/json",
            width="stretch", key="del_json")

        # ── ZIP Bundle ─────────────────────────────────────────────────
        _sec("📦", "Complete Bundle", "All deliverables in a single ZIP archive")
        _zip_buf = io.BytesIO()
        with zipfile.ZipFile(_zip_buf, 'w', zipfile.ZIP_DEFLATED) as _zf:
            if _final_est_bytes:
                _zf.writestr("Final_Estimation.xlsx", _final_est_bytes)
            if _xl_data:
                _zf.writestr("ECI_Time_Estimate.xlsx", _xl_data)
            if _lenox_data:
                _zf.writestr("ECI_Estimation_Standard.xlsx", _lenox_data)
            if _cost_xl:
                _zf.writestr("ECI_Cost_Estimate.xlsx", _cost_xl)
            if _pdf_data:
                _zf.writestr("ECI_Proposal.pdf", _pdf_data)
            if _pptx_dl:
                _zf.writestr("ECI_Proposal.pptx", _pptx_dl)
            if _sow_dl:
                _zf.writestr("ECI_Statement_of_Work.pdf", _sow_dl)
            if _mermaid_data2:
                _zf.writestr("ECI_Diagrams.json", json.dumps(_mermaid_data2, indent=2))
            _zf.writestr("ECI_Data.json", json.dumps(_del_r, indent=2, default=str))
        _zip_buf.seek(0)
        st.download_button(
            "📦 Download All Deliverables (ZIP)",
            data=_zip_buf.getvalue(),
            file_name="ECI_Deliverables" + _ver_suffix + "_" + ts + ".zip",
            mime="application/zip",
            width="stretch",
            type="primary",
            key="del_zip",
        )

        # ── Actions ────────────────────────────────────────────────────
        _sec("⚡", "Actions", "Publish or share the estimation")
        ac_cols2 = st.columns(2)
        with ac_cols2[0]:
            if st.button("☁️ Upload to SharePoint", width="stretch", key="del_sp", type="secondary"):
                ok, msg = SP.from_session().upload(r)
                st.success(msg) if ok else st.error(msg)
        with ac_cols2[1]:
            if st.button("📧 Send Alert Email", width="stretch", key="del_email", type="secondary"):
                ok, msg = Mailer.from_session().send(r)
                st.success(msg) if ok else st.error(msg)

    # ── Review & Feedback ──
    with tab_list[15]:
        _pre[15].empty()
        st.markdown('<div class="eci-tab-hdr"><span class="eci-tab-hdr-icon">⭐</span>'
                    '<span class="eci-tab-hdr-title">Review & Feedback</span></div>', unsafe_allow_html=True)
        render_review_feedback_tab(r, se, te, ce, ri, ar, _pick_ai())

    with tab_list[16]:
        _pre[16].empty()
        _render_correct_and_train_tab(r, se, te)


# ═══════════════════════════════════════════════════════════════════════
#  TRAINING TAB helper (renders inside tab_admin at[1])
# ═══════════════════════════════════════════════════════════════════════

def _claude_raw_call(system: str, content_blocks: list, max_tokens: int = 500) -> str:
    """
    Shared helper: calls Claude via raw HTTP (supports vision content blocks).
    Mirrors AnthropicAI._make_request auth pattern.
    Returns response text or "" on any failure.
    """
    import json, urllib.request, urllib.error

    try:
        from .ai_clients import AnthropicAI as _AntAI
    except Exception:
        return ""

    client = _AntAI.from_session()
    if not client.is_live:
        return ""

    # Text-only optimisation: use the faster _call path
    if all(b.get("type") == "text" for b in content_blocks):
        user_text = "\n".join(b.get("text", "") for b in content_blocks)
        try:
            result = client._call(system, user_text, max_tokens=max_tokens)
            return (result or "").strip() if isinstance(result, str) else ""
        except Exception:
            return ""

    # Vision path: raw HTTP
    payload = json.dumps({
        "model":      client.model,
        "max_tokens": max_tokens,
        "system":     system,
        "messages":   [{"role": "user", "content": content_blocks}],
    }).encode("utf-8")

    if client._is_azure:
        url = client.endpoint
        auth_candidates = [{"api-key": client.key}, {"Authorization": f"Bearer {client.key}"}]
    else:
        url = "https://api.anthropic.com/v1/messages"
        auth_candidates = [{"x-api-key": client.key}]

    for auth_hdr in auth_candidates:
        req = urllib.request.Request(
            url, data=payload,
            headers={**auth_hdr, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return ((data.get("content") or [{}])[0].get("text", "") or "").strip()
        except urllib.error.HTTPError as he:
            if he.code == 401:
                continue
            return ""
        except Exception:
            return ""
    return ""


def _analyse_screenshot_feedback(images: list, wrong_desc: str, fix_desc: str) -> str:
    """
    Generate a training instruction from user feedback with optional screenshots.
    images: list of (bytes, filename) tuples — can be empty for text-only.
    """
    import base64

    system = (
        "You are a training data engineer for BELLA, an AI presales estimation tool used by ECI. "
        "Convert user feedback about a wrong estimation into a short, precise, actionable training "
        "instruction that will be prepended to the AI agents' system prompts. Rules:\n"
        "  • Name exact work streams, technologies, or conditions involved\n"
        "  • Use DO / DO NOT language clearly\n"
        "  • 2-5 sentences maximum\n"
        "  • Make it generalisable to future similar projects, not just this one\n"
        "Write ONLY the instruction text — no preamble, no bullets, no explanation."
    )

    user_text = f"PROBLEM WITH BELLA OUTPUT: {wrong_desc}\n\n"
    if fix_desc:
        user_text += f"CORRECT BEHAVIOUR: {fix_desc}\n\n"
    user_text += "Write a single, precise training instruction for the AI agent."

    content_blocks = []
    for img_bytes, filename in (images or []):
        ext = (filename or "screenshot.png").rsplit(".", 1)[-1].lower()
        media_type = "image/png" if ext == "png" else "image/jpeg"
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(img_bytes).decode("utf-8"),
            },
        })
    content_blocks.append({"type": "text", "text": user_text})

    return _claude_raw_call(system, content_blocks, max_tokens=400)


def _generate_instruction_from_delta(fb: dict) -> str:
    """
    Auto-generate a training instruction from a single Excel feedback record.
    fb: dict from list_feedback() — has bella_hours, actual_hours, phase_deltas, notes, client_name.
    """
    import json as _json
    h_delta = fb["actual_hours"] - fb["bella_hours"]
    pct = round(abs(h_delta) / max(fb["bella_hours"], 1) * 100)
    direction = "over-estimated" if h_delta < 0 else "under-estimated"

    phase_text = ""
    try:
        phases = _json.loads(fb.get("phase_deltas") or "[]")
        bad_phases = [p for p in phases if abs(p.get("actual_hours", 0) - p.get("bella_hours", 0)) > 10]
        if bad_phases:
            phase_text = "\nPhase-level deltas:\n"
            for p in bad_phases:
                d = p.get("actual_hours", 0) - p.get("bella_hours", 0)
                phase_text += f"  - {p.get('phase','?')}: BELLA {p.get('bella_hours',0)}h → Actual {p.get('actual_hours',0)}h ({d:+}h)\n"
    except Exception:
        pass

    system = (
        "You are a training engineer for BELLA, an AI presales estimation tool. "
        "Based on a gap between BELLA's estimate and actual delivery, write one concise "
        "training instruction that will improve future estimates for similar projects. "
        "Rules:\n"
        "  • Reference the specific phases or work streams that were wrong\n"
        "  • Use DO / DO NOT language\n"
        "  • Make it generalisable — a rule for future projects, not a correction for this one\n"
        "  • 2-4 sentences maximum\n"
        "Write ONLY the instruction — no preamble, no explanation."
    )
    user_text = (
        f"Project: {fb.get('client_name', 'Unknown')}\n"
        f"BELLA estimated: {fb['bella_hours']}h (${fb.get('bella_cost', 0):,}/mo)\n"
        f"Actual delivered: {fb['actual_hours']}h (${fb.get('actual_cost', 0):,}/mo)\n"
        f"BELLA {direction} by {abs(h_delta)}h ({pct}%)\n"
        f"{phase_text}"
        f"Notes from presales lead: {fb.get('notes', '') or 'None'}\n\n"
        "Write a single training instruction to prevent this type of estimation error in future."
    )
    return _claude_raw_call(system, [{"type": "text", "text": user_text}], max_tokens=300)


def _detect_systematic_patterns(feedback_list: list) -> str:
    """
    Analyse all Excel feedback records together and surface systemic estimation biases.
    Returns a formatted string with PATTERN / RULE blocks.
    """
    if not feedback_list:
        return ""

    import json as _json
    records = []
    for fb in feedback_list:
        h_delta = fb["actual_hours"] - fb["bella_hours"]
        pct = round(abs(h_delta) / max(fb["bella_hours"], 1) * 100)
        direction = "over-estimated" if h_delta < 0 else "under-estimated"
        phase_summary = ""
        try:
            phases = _json.loads(fb.get("phase_deltas") or "[]")
            bad = [(p.get("phase","?"), p.get("actual_hours",0) - p.get("bella_hours",0)) for p in phases if abs(p.get("actual_hours",0) - p.get("bella_hours",0)) > 20]
            if bad:
                phase_summary = " | Worst phases: " + ", ".join(f"{n} ({d:+}h)" for n, d in bad[:3])
        except Exception:
            pass
        records.append(
            f"• {fb.get('client_name','Client')}: {direction} by {abs(h_delta)}h ({pct}%){phase_summary}"
            + (f" | Note: {fb['notes']}" if fb.get("notes") else "")
        )

    system = (
        "You are a data analyst reviewing estimation accuracy for BELLA, an AI presales tool. "
        "Find systematic patterns (recurring mistakes, consistent over/under-estimation of specific phases) "
        "across multiple projects. Write 2-5 training rules to fix the most important patterns."
    )
    user_text = (
        f"Estimation accuracy across {len(feedback_list)} past projects:\n\n"
        + "\n".join(records)
        + "\n\nIdentify systemic patterns and write training rules. Format each as:\n"
        "PATTERN: <what BELLA consistently gets wrong>\n"
        "RULE: <precise training instruction to fix it>\n\n"
        "Focus on the 2-5 most impactful, actionable rules."
    )
    return _claude_raw_call(system, [{"type": "text", "text": user_text}], max_tokens=900)


def _detect_instruction_conflicts(instructions: list) -> str:
    """
    Send all active instructions to Claude and ask it to identify contradictions.
    Returns a markdown-formatted report with conflicts + suggested resolutions.
    """
    if not instructions:
        return ""

    instr_block = "\n".join(
        f"[#{i['id']} · {(i['category'] or 'general').upper()}] {i['instruction']}"
        for i in instructions
        if i.get("active")
    )
    if not instr_block.strip():
        return ""

    system = (
        "You are a quality engineer reviewing training instructions for BELLA, an AI presales estimation tool. "
        "Your job is to find contradictions, conflicts, or ambiguities between instructions that would confuse the AI agents."
    )
    user_text = (
        f"Here are the active training instructions:\n\n{instr_block}\n\n"
        "Identify every pair of instructions that contradict or conflict with each other. "
        "For each conflict:\n"
        "1. Name the conflicting instruction IDs\n"
        "2. Explain the contradiction in one sentence\n"
        "3. Write a single merged instruction that resolves the conflict\n\n"
        "Format each conflict as:\n"
        "CONFLICT: #ID1 vs #ID2\n"
        "ISSUE: <explanation>\n"
        "RESOLUTION: <merged instruction>\n\n"
        "If there are no conflicts, respond with exactly: NO CONFLICTS FOUND"
    )

    return _claude_raw_call(system, [{"type": "text", "text": user_text}], max_tokens=1000)


def _analyse_scope_vs_output(scope_text: str, bella_output: str, what_wrong: str) -> str:
    """
    Compare what the scope document says vs what BELLA generated.
    Produces a training instruction that captures the mismatch rule.
    """
    system = (
        "You are a training data engineer for BELLA, an AI presales estimation tool used by ECI. "
        "The user will show you what a scope document says and what BELLA estimated instead. "
        "Generate a precise, actionable training instruction that will prevent this mismatch in future. "
        "Rules:\n"
        "  • Reference the exact difference between scope and BELLA output\n"
        "  • Use DO / DO NOT language\n"
        "  • 2-5 sentences maximum\n"
        "  • Make it generalisable, not specific to one client\n"
        "Write ONLY the instruction text — no preamble, no explanation."
    )
    user_text = (
        f"SCOPE DOCUMENT SAYS:\n{scope_text}\n\n"
        f"WHAT BELLA GENERATED:\n{bella_output}\n\n"
    )
    if what_wrong:
        user_text += f"ADDITIONAL CONTEXT (what's specifically wrong):\n{what_wrong}\n\n"
    user_text += "Write a training instruction to fix this mismatch."

    return _claude_raw_call(system, [{"type": "text", "text": user_text}], max_tokens=400)


def _render_training_tab():
    """Agent training — 5-tab system for improving BELLA estimation accuracy."""
    import json as _json
    from .training import (
        add_instruction, list_instructions, toggle_instruction, delete_instruction,
        add_feedback, list_feedback, delete_feedback, parse_excel_estimate,
        extract_structural_patterns, generate_instructions_from_excel,
    )

    _PROJ_TYPES = ["AI", "SharePoint", "Data", "Cloud"]

    st.markdown("### 🧠 Agent Training")
    st.markdown(
        "Everything saved here is injected into every agent's system prompt before each estimation run. "
        "Instructions can be scoped to specific project types so AI rules don't fire on SharePoint projects and vice versa."
    )

    tr1, tr2, tr3, tr4, tr5 = st.tabs([
        "📋 Instructions",
        "📸 Visual Feedback",
        "📄 Scope vs Output",
        "📊 Excel Feedback",
        "📈 Insights",
    ])

    # ── TAB 1: Text instructions + Conflict Detector ──────────────────────
    with tr1:
        with st.form("add_instr_form", clear_on_submit=True):
            st.markdown("**Add a new instruction**")
            _if1, _if2 = st.columns(2)
            with _if1:
                i_cat = st.selectbox(
                    "Category",
                    ["general", "hours", "cost", "risk", "scope", "architecture"],
                    key="i_cat",
                )
            with _if2:
                i_types = st.multiselect(
                    "Project types (empty = all projects)",
                    _PROJ_TYPES,
                    key="i_types",
                    help="Scope this instruction to specific project types. Leave empty to apply to every estimation.",
                )
            i_txt = st.text_area(
                "Instruction",
                placeholder=(
                    "e.g. For AI-only projects, DO NOT add a Data Engineering stream unless "
                    "the scope explicitly mentions ETL, Fabric, or Databricks."
                ),
                key="i_txt",
                height=100,
            )
            if st.form_submit_button("➕ Save Instruction", type="primary"):
                if i_txt.strip():
                    _iid = add_instruction(
                        i_txt.strip(), category=i_cat,
                        created_by="admin", project_types=i_types,
                    )
                    st.success(f"Saved instruction #{_iid}")
                else:
                    st.warning("Enter an instruction first.")

        st.markdown("---")

        _all_instrs = list_instructions()
        _active_instrs = [i for i in _all_instrs if i.get("active")]

        # ── Toolbar: search / filter / bulk ops / conflict detector ──────
        _tb1, _tb2, _tb3, _tb4 = st.columns([3, 2, 1, 1])
        with _tb1:
            _search = st.text_input("🔍 Search", key="instr_search", placeholder="keyword…", label_visibility="collapsed")
        with _tb2:
            _cat_filter = st.selectbox(
                "Filter", ["All categories"] + ["general", "hours", "cost", "risk", "scope", "architecture"],
                key="instr_cat_filter", label_visibility="collapsed",
            )
        with _tb3:
            if st.button("✅ All On", key="bulk_enable", help="Enable all instructions"):
                for _bi in _all_instrs:
                    toggle_instruction(_bi["id"], True)
                st.rerun()
        with _tb4:
            if st.button("⭕ All Off", key="bulk_disable", help="Disable all instructions"):
                for _bi in _all_instrs:
                    toggle_instruction(_bi["id"], False)
                st.rerun()

        _type_filter = st.multiselect(
            "Project type filter",
            _PROJ_TYPES,
            key="instr_type_filter",
            help="Show only instructions tagged for these project types",
        )
        _show_inactive = st.checkbox("Show disabled instructions", key="instr_show_inactive", value=False)

        # Apply filters
        _filtered = _all_instrs if _show_inactive else _active_instrs
        if _search:
            _filtered = [i for i in _filtered if _search.lower() in (i.get("instruction") or "").lower()]
        if _cat_filter != "All categories":
            _filtered = [i for i in _filtered if (i.get("category") or "general") == _cat_filter]
        if _type_filter:
            _tmp = []
            for _fi in _filtered:
                try:
                    _ipt = _json.loads(_fi.get("project_types") or "[]")
                except Exception:
                    _ipt = []
                if not _ipt or any(pt in _ipt for pt in _type_filter):
                    _tmp.append(_fi)
            _filtered = _tmp

        # Conflict detector
        _cdc1, _cdc2, _cdc3 = st.columns([3, 1, 1])
        with _cdc1:
            st.caption(
                f"Showing **{len(_filtered)}** of {len(_all_instrs)} instructions · "
                f"{len(_active_instrs)} active"
            )
        with _cdc2:
            if st.button(
                "🔎 Check Conflicts",
                key="conflict_detect_btn",
                disabled=len(_active_instrs) < 2,
                help="Find contradictions between active instructions",
            ):
                with st.spinner("Analysing for conflicts…"):
                    _conflict_report = _detect_instruction_conflicts(_active_instrs)
        with _cdc3:
            if st.button(
                "🔄 Consolidate",
                key="_consolidate_btn",
                disabled=len(_active_instrs) < 6,
                help="AI merges similar/redundant instructions into one canonical rule per group. "
                     "Requires at least 6 active instructions.",
            ):
                with st.spinner("Consolidating similar instructions…"):
                    try:
                        from .training import consolidate_instructions as _consol
                        _cr = _consol()
                        if _cr.get("skipped"):
                            st.info("Not enough instructions to consolidate yet (need 6+).")
                        elif _cr.get("error"):
                            st.error(f"Consolidation failed: {_cr['error']}")
                        elif _cr.get("groups_merged", 0) == 0:
                            st.success("✅ No redundant groups found — instructions are already clean.")
                        else:
                            st.success(
                                f"✅ Consolidated: {_cr['before']} → {_cr['after']} instructions "
                                f"({_cr['groups_merged']} group{'s' if _cr['groups_merged'] != 1 else ''} merged)."
                            )
                            st.rerun()
                    except Exception as _ce:
                        st.error(f"Consolidation error: {_ce}")
                st.session_state["_conflict_report"] = _conflict_report

        if st.session_state.get("_conflict_report"):
            _report = st.session_state["_conflict_report"]
            if "NO CONFLICTS FOUND" in _report.upper():
                st.success("✅ No conflicts — all instructions are consistent.")
            else:
                st.warning("⚠️ Conflicts detected:")
                for _blk in [b.strip() for b in _report.split("\n\n") if b.strip()]:
                    _lines = _blk.splitlines()
                    _cid  = next((l for l in _lines if l.startswith("CONFLICT:")), "")
                    _iss  = next((l for l in _lines if l.startswith("ISSUE:")), "")
                    _res  = next((l for l in _lines if l.startswith("RESOLUTION:")), "")
                    if not _cid:
                        st.markdown(_blk); continue
                    with st.expander(_cid, expanded=True):
                        if _iss:
                            st.markdown(f"**Problem:** {_iss.replace('ISSUE:','').strip()}")
                        if _res:
                            _rt = _res.replace("RESOLUTION:", "").strip()
                            st.info(f"**Suggested fix:** {_rt}")
                            if st.button("✅ Save resolved instruction", key=f"resolve_{hash(_cid)%99999}"):
                                _iid = add_instruction(_rt, category="general", created_by="admin")
                                st.success(f"Saved as #{_iid}")
                                st.session_state.pop("_conflict_report", None)
                                st.rerun()
            if st.button("✖ Clear", key="clear_conflict_report"):
                st.session_state.pop("_conflict_report", None)
                st.rerun()

        st.markdown("---")
        if not _filtered:
            st.info("No instructions match the current filter." if _search or _cat_filter != "All categories" or _type_filter else "No instructions yet.")
        for _i in _filtered:
            with st.container():
                _ic1, _ic2, _ic3 = st.columns([6, 1, 1])
                with _ic1:
                    _badge = "🟢" if _i["active"] else "⚪"
                    _ipt_list = []
                    try: _ipt_list = _json.loads(_i.get("project_types") or "[]")
                    except Exception: pass
                    _type_str = " · ".join(f"`{t}`" for t in _ipt_list) if _ipt_list else "`ALL`"
                    st.markdown(
                        f"{_badge} **[{(_i['category'] or 'general').upper()}]** {_type_str}  \n"
                        f"{_i['instruction']}"
                    )
                    st.caption(f"#{_i['id']} · {_i['created_at'][:16]}")
                with _ic2:
                    _lbl = "Disable" if _i["active"] else "Enable"
                    if st.button(_lbl, key=f"tog_instr_{_i['id']}"):
                        toggle_instruction(_i["id"], not bool(_i["active"]))
                        st.rerun()
                with _ic3:
                    if st.button("🗑️", key=f"del_instr_{_i['id']}"):
                        delete_instruction(_i["id"])
                        st.rerun()

    # ── TAB 2: Visual Feedback (multiple screenshots) ─────────────────────
    with tr2:
        st.markdown("**Show BELLA screenshots of its output and tell it what's wrong.**")
        st.caption(
            "Upload one or more screenshots of a BELLA estimation result. "
            "Claude Vision reads all of them together and generates a precise training instruction."
        )
        st.markdown("---")

        _sc_imgs = st.file_uploader(
            "Screenshots of BELLA output (PNG or JPG) — multiple allowed",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="sc_imgs",
        )
        if _sc_imgs:
            _img_cols = st.columns(min(len(_sc_imgs), 3))
            for _idx, _f in enumerate(_sc_imgs):
                with _img_cols[_idx % 3]:
                    st.image(_f, caption=_f.name, use_container_width=True)

        _sc_wrong = st.text_area(
            "❌ What's wrong with this output?",
            placeholder=(
                "e.g. It added a Data Engineering stream (318h) — "
                "this AI scope doesn't need that, the AI engineer handles data work."
            ),
            key="sc_wrong",
            height=90,
        )
        _sc_fix = st.text_area(
            "✅ What should it do instead?",
            placeholder=(
                "e.g. For AI projects, keep all data work inside the AI/ML stream "
                "unless there is a full ETL platform like Fabric or Databricks."
            ),
            key="sc_fix",
            height=80,
        )
        _sc_cat = st.selectbox(
            "Category",
            ["hours", "general", "cost", "risk", "scope", "architecture"],
            key="sc_cat",
        )

        if st.button("🔍 Analyse & Generate Instruction", type="primary", key="sc_analyse"):
            if not _sc_wrong.strip():
                st.warning("Describe what's wrong before analysing.")
            else:
                _images = [(f.getvalue(), f.name) for f in (_sc_imgs or [])]
                with st.spinner(
                    f"Claude is reading {len(_images)} screenshot(s) and generating an instruction…"
                    if _images else "Claude is generating an instruction…"
                ):
                    _sc_gen = _analyse_screenshot_feedback(_images, _sc_wrong.strip(), _sc_fix.strip())
                if _sc_gen:
                    st.session_state["_sc_generated"] = _sc_gen
                    st.session_state["_sc_save_cat"] = _sc_cat
                else:
                    st.error(
                        "Could not generate instruction — check that Anthropic API key is configured in the sidebar."
                    )

        if st.session_state.get("_sc_generated"):
            st.markdown("---")
            st.markdown("**Generated instruction — review and edit before saving:**")
            _sc_final = st.text_area(
                "Instruction text",
                value=st.session_state["_sc_generated"],
                key="sc_final",
                height=130,
            )
            _cats = ["hours", "general", "cost", "risk", "scope", "architecture"]
            _sc_save_cat = st.selectbox(
                "Save under category",
                _cats,
                index=_cats.index(st.session_state.get("_sc_save_cat", "hours")),
                key="sc_save_cat_sel",
            )
            if st.button("✅ Save as Training Instruction", type="primary", key="sc_save"):
                _iid = add_instruction(_sc_final.strip(), category=_sc_save_cat, created_by="admin")
                st.success(f"✅ Saved as instruction #{_iid} — will be applied on every future estimation run.")
                st.session_state.pop("_sc_generated", None)
                st.rerun()

    # ── TAB 3: Scope vs Output ────────────────────────────────────────────
    with tr3:
        st.markdown("**Compare what the scope document says vs what BELLA generated.**")
        st.caption(
            "Paste the relevant section from your scope document and paste BELLA's incorrect output. "
            "Claude will identify the mismatch and write a training instruction to fix it."
        )
        st.markdown("---")

        _svo_col1, _svo_col2 = st.columns(2)
        with _svo_col1:
            _svo_scope = st.text_area(
                "📄 What the scope/SOW document says",
                placeholder=(
                    "e.g. 'The project requires integration with Salesforce CRM via REST API. "
                    "No ETL or data warehousing is in scope. The AI solution uses Azure OpenAI only.'"
                ),
                key="svo_scope",
                height=180,
            )
        with _svo_col2:
            _svo_bella = st.text_area(
                "🤖 What BELLA generated (copy from estimation output)",
                placeholder=(
                    "e.g. 'Custom Application Development: 240h, Data Engineering & ETL: 318h, "
                    "Salesforce Integration: 80h, AI/ML Development: 120h'"
                ),
                key="svo_bella",
                height=180,
            )

        _svo_context = st.text_area(
            "💬 Additional context (optional — what specifically is wrong?)",
            placeholder="e.g. Data Engineering stream should not be here at all — this is a pure AI project with no ETL.",
            key="svo_context",
            height=70,
        )
        _svo_cat = st.selectbox(
            "Category",
            ["scope", "hours", "general", "cost", "risk", "architecture"],
            key="svo_cat",
        )

        if st.button("🔍 Generate Training Instruction from Mismatch", type="primary", key="svo_analyse"):
            if not _svo_scope.strip() or not _svo_bella.strip():
                st.warning("Paste both the scope document text and BELLA's output before analysing.")
            else:
                with st.spinner("Claude is comparing scope vs BELLA output…"):
                    _svo_gen = _analyse_scope_vs_output(
                        _svo_scope.strip(),
                        _svo_bella.strip(),
                        _svo_context.strip(),
                    )
                if _svo_gen:
                    st.session_state["_svo_generated"] = _svo_gen
                    st.session_state["_svo_save_cat"] = _svo_cat
                else:
                    st.error(
                        "Could not generate instruction — check that Anthropic API key is configured in the sidebar."
                    )

        if st.session_state.get("_svo_generated"):
            st.markdown("---")
            st.markdown("**Generated instruction — review and edit before saving:**")
            _svo_final = st.text_area(
                "Instruction text",
                value=st.session_state["_svo_generated"],
                key="svo_final",
                height=130,
            )
            _svo_cats = ["scope", "hours", "general", "cost", "risk", "architecture"]
            _svo_save_cat = st.selectbox(
                "Save under category",
                _svo_cats,
                index=_svo_cats.index(st.session_state.get("_svo_save_cat", "scope")),
                key="svo_save_cat_sel",
            )
            if st.button("✅ Save as Training Instruction", type="primary", key="svo_save"):
                _iid = add_instruction(_svo_final.strip(), category=_svo_save_cat, created_by="admin")
                st.success(f"✅ Saved as instruction #{_iid} — will be applied on every future estimation run.")
                st.session_state.pop("_svo_generated", None)
                st.rerun()

    # ── TAB 4: Excel Feedback ──────────────────────────────────────────────
    with tr4:
        # ── NEW: Extract training instructions from a real client Excel ──
        with st.expander("📋 Extract Training Instructions from Real Excel", expanded=True):
            st.markdown(
                "Upload a real estimation Excel (like one you sent to a client). "
                "BELLA will scan the **role sheets, phase names, and technology keywords** "
                "and generate structural training rules — not hours."
            )
            _xi_c1, _xi_c2 = st.columns([2, 1])
            with _xi_c1:
                _xi_file = st.file_uploader(
                    "Estimation Excel", type=["xlsx", "xls"], key="xi_excel_upload",
                    help="Any real estimate you've built — sheet names are used as role/stream names",
                )
            with _xi_c2:
                _xi_ctx = st.text_input(
                    "Project type hint (optional)",
                    placeholder="e.g. Power BI, Data Platform, RPA",
                    key="xi_ctx",
                )

            _xi_btn = st.button(
                "🔍 Analyze Excel → Generate Instructions",
                type="primary",
                key="xi_analyze_btn",
                disabled=(_xi_file is None),
            )

            if _xi_btn and _xi_file:
                with st.spinner("Reading Excel structure — identifying roles, technologies, phases…"):
                    _xi_patterns = extract_structural_patterns(_xi_file.read())
                with st.spinner("Asking Claude to generate training instructions from patterns…"):
                    _xi_instrs = generate_instructions_from_excel(_xi_patterns, _xi_ctx)
                st.session_state["_xi_patterns"] = _xi_patterns
                st.session_state["_xi_instrs"] = _xi_instrs

            # Show results if available
            if st.session_state.get("_xi_patterns"):
                _xp = st.session_state["_xi_patterns"]
                _xic1, _xic2, _xic3 = st.columns(3)
                with _xic1:
                    st.metric("Role/Estimation sheets", len(_xp.get("estimation_sheets", [])))
                with _xic2:
                    st.metric("Roles identified", len(_xp.get("roles", [])))
                with _xic3:
                    st.metric("Technologies found", len(_xp.get("technologies", [])))

                if _xp.get("roles"):
                    st.markdown(f"**Roles:** {', '.join(_xp['roles'])}")
                if _xp.get("technologies"):
                    st.markdown(f"**Technologies:** {', '.join(_xp['technologies'])}")

                st.markdown("---")

            if st.session_state.get("_xi_instrs"):
                _xi_results = st.session_state["_xi_instrs"]
                st.markdown(f"**{len(_xi_results)} instructions extracted — select which to save:**")

                _xi_sel_types = st.multiselect(
                    "Tag all selected instructions with project types (optional)",
                    _PROJ_TYPES, key="xi_proj_types",
                )
                _xi_checks = {}
                for _ii, _instr in enumerate(_xi_results):
                    _cat_badge = f"`{_instr['category']}`"
                    _xi_checks[_ii] = st.checkbox(
                        f"{_cat_badge}  {_instr['text']}",
                        value=True,
                        key=f"xi_chk_{_ii}",
                    )

                if st.button("💾 Save Selected Instructions", type="primary", key="xi_save_btn"):
                    _xi_saved = 0
                    for _ii, _instr in enumerate(_xi_results):
                        if _xi_checks.get(_ii):
                            _iid = add_instruction(
                                _instr["text"],
                                category=_instr["category"],
                                created_by="admin",
                                project_types=_xi_sel_types,
                            )
                            _xi_saved += 1
                    st.success(f"✅ Saved {_xi_saved} instruction(s) — BELLA will apply them on every future run.")
                    st.session_state.pop("_xi_patterns", None)
                    st.session_state.pop("_xi_instrs", None)
                    st.rerun()

        st.markdown("---")
        st.markdown("**Record numerical feedback** (how many hours BELLA vs how many you actually used)")
        st.markdown(
            "Upload the final Excel you sent to the client. "
            "BELLA stores the delta and can auto-generate a training instruction from it."
        )
        with st.form("add_feedback_form", clear_on_submit=True):
            _fc1, _fc2 = st.columns(2)
            with _fc1:
                _fb_client = st.text_input("Client Name", placeholder="e.g. Contoso", key="fb_client")
                _fb_bella_h = st.number_input(
                    "BELLA Hours (from last run)", min_value=0, value=0, key="fb_bella_h"
                )
                _fb_bella_c = st.number_input(
                    "BELLA Cost $/mo (from last run)", min_value=0, value=0, key="fb_bella_c"
                )
            with _fc2:
                _fb_excel = st.file_uploader(
                    "Actual Excel (sent to client)", type=["xlsx", "xls"], key="fb_excel"
                )
                _fb_notes = st.text_area(
                    "Notes / Lessons Learned",
                    placeholder="e.g. We missed the integration testing phase entirely.",
                    key="fb_notes",
                    height=100,
                )

            if st.form_submit_button("📥 Parse & Save Feedback", type="primary"):
                if not _fb_client.strip():
                    st.warning("Enter client name.")
                elif not _fb_excel:
                    st.warning("Upload the actual Excel file.")
                else:
                    with st.spinner("Parsing Excel file…"):
                        _parsed = parse_excel_estimate(_fb_excel.read())
                    if _parsed["total_hours"] == 0 and not _parsed["phases"]:
                        st.warning(
                            "Could not auto-detect hours in the Excel. "
                            "The file may use an unusual layout — enter actual hours manually below."
                        )
                    _phase_deltas = []
                    for _ph in _parsed["phases"]:
                        _phase_deltas.append({
                            "phase": _ph["phase"],
                            "actual_hours": _ph["actual_hours"],
                            "actual_cost":  _ph["actual_cost"],
                            "bella_hours":  0,
                            "bella_cost":   0,
                        })
                    _fid = add_feedback(
                        client_name=_fb_client.strip(),
                        bella_hours=int(_fb_bella_h),
                        actual_hours=int(_parsed["total_hours"]) or int(_fb_bella_h),
                        bella_cost=int(_fb_bella_c),
                        actual_cost=int(_parsed["total_cost"]) or int(_fb_bella_c),
                        phase_deltas=_phase_deltas,
                        notes=_fb_notes.strip(),
                        created_by="admin",
                    )
                    st.success(
                        f"✅ Feedback #{_fid} saved — "
                        f"BELLA: {_fb_bella_h}h | Actual: {_parsed['total_hours']}h "
                        f"(delta: {_parsed['total_hours'] - int(_fb_bella_h):+}h)"
                    )

        st.markdown("---")
        st.markdown("**Past feedback records**")
        _fbs = list_feedback()
        if not _fbs:
            st.info("No feedback records yet. Upload your first actual client Excel above.")
        for _fb in _fbs:
            _dh = _fb["actual_hours"] - _fb["bella_hours"]
            _sign = "+" if _dh >= 0 else ""
            _pct  = round(abs(_dh) / max(_fb["bella_hours"], 1) * 100)
            _colour = "#ff6b6b" if abs(_dh) > _fb["bella_hours"] * 0.2 else "#00d4aa"
            with st.container():
                _fbc1, _fbc2, _fbc3 = st.columns([6, 2, 1])
                with _fbc1:
                    st.markdown(
                        f"**{_fb['client_name'] or 'Client'}** · "
                        f"BELLA {_fb['bella_hours']}h → Actual {_fb['actual_hours']}h "
                        f"<span style='color:{_colour};font-weight:700'>({_sign}{_dh}h / {_pct}%)</span>",
                        unsafe_allow_html=True,
                    )
                    if _fb.get("notes"):
                        st.caption(_fb["notes"])
                    st.caption(f"#{_fb['id']} · {_fb['created_at'][:16]}")
                with _fbc2:
                    if st.button("🤖 Auto-learn", key=f"autolearn_fb_{_fb['id']}",
                                 help="Generate a training instruction from this delta"):
                        with st.spinner("Claude is writing a rule from this delta…"):
                            _gen = _generate_instruction_from_delta(_fb)
                        if _gen:
                            st.session_state[f"_fb_gen_{_fb['id']}"] = _gen
                        else:
                            st.error("Could not generate — check API key in sidebar.")
                with _fbc3:
                    if st.button("🗑️", key=f"del_fb_{_fb['id']}"):
                        delete_feedback(_fb["id"])
                        st.rerun()
                # Inline generated instruction editor
                _gen_key = f"_fb_gen_{_fb['id']}"
                if st.session_state.get(_gen_key):
                    _fb_final = st.text_area(
                        "Review & edit generated instruction:",
                        value=st.session_state[_gen_key],
                        key=f"fb_final_{_fb['id']}",
                        height=100,
                    )
                    _fc_save1, _fc_save2 = st.columns([2, 1])
                    with _fc_save1:
                        _fb_save_types = st.multiselect(
                            "Project types", _PROJ_TYPES,
                            key=f"fb_save_types_{_fb['id']}",
                            help="Leave empty = applies to all projects",
                        )
                    with _fc_save2:
                        if st.button("✅ Save Instruction", key=f"fb_save_{_fb['id']}", type="primary"):
                            _iid = add_instruction(
                                _fb_final.strip(), category="hours",
                                created_by="admin", project_types=_fb_save_types,
                            )
                            st.success(f"Saved as instruction #{_iid}")
                            st.session_state.pop(_gen_key, None)
                            st.rerun()
                st.markdown("---")

    # ── TAB 5: Insights ───────────────────────────────────────────────────
    with tr5:
        st.markdown("**Training system health and estimation accuracy over time.**")

        _all_i   = list_instructions()
        _active_i = [i for i in _all_i if i.get("active")]
        _all_fb  = list_feedback()

        # ── Key metrics ──────────────────────────────────────────────────
        _m1, _m2, _m3, _m4 = st.columns(4)
        with _m1:
            st.metric("Active instructions", len(_active_i), delta=len(_active_i) - (len(_all_i) - len(_active_i)) or None)
        with _m2:
            st.metric("Feedback records", len(_all_fb))
        with _m3:
            if _all_fb:
                _avg_delta = round(sum(fb["actual_hours"] - fb["bella_hours"] for fb in _all_fb) / len(_all_fb))
                _bias_label = f"{_avg_delta:+}h avg"
                st.metric("Avg delta", _bias_label,
                          help="Positive = BELLA under-estimates; Negative = over-estimates")
            else:
                st.metric("Avg delta", "—")
        with _m4:
            if _all_fb:
                _over_count = sum(1 for fb in _all_fb if fb["actual_hours"] < fb["bella_hours"])
                st.metric("Over-estimates", f"{_over_count}/{len(_all_fb)}")
            else:
                st.metric("Over-estimates", "—")

        st.markdown("---")

        # ── Category breakdown ───────────────────────────────────────────
        if _active_i:
            from collections import Counter as _Ctr
            _cat_counts = _Ctr((i.get("category") or "general") for i in _active_i)
            _type_counts: dict = {}
            for _i in _active_i:
                try: _ipt = _json.loads(_i.get("project_types") or "[]")
                except Exception: _ipt = []
                for _t in (_ipt or ["ALL"]):
                    _type_counts[_t] = _type_counts.get(_t, 0) + 1

            _ins_c1, _ins_c2 = st.columns(2)
            with _ins_c1:
                st.markdown("**Instructions by category**")
                for _cat, _cnt in sorted(_cat_counts.items(), key=lambda x: -x[1]):
                    _bar = "█" * _cnt
                    st.markdown(f"`{_cat.upper()}` {_bar} {_cnt}")
            with _ins_c2:
                st.markdown("**Instructions by project type**")
                for _tp, _cnt in sorted(_type_counts.items(), key=lambda x: -x[1]):
                    _bar = "█" * _cnt
                    st.markdown(f"`{_tp}` {_bar} {_cnt}")
        else:
            st.info("Add instructions to see category and type breakdowns here.")

        st.markdown("---")

        # ── Feedback delta chart ─────────────────────────────────────────
        if _all_fb:
            st.markdown("**Estimation accuracy per project** (positive = under-estimated, negative = over-estimated)")
            _chart_data = {
                fb.get("client_name") or f"#{fb['id']}": fb["actual_hours"] - fb["bella_hours"]
                for fb in reversed(_all_fb[-10:])
            }
            st.bar_chart(_chart_data)

        st.markdown("---")

        # ── Pattern detection ────────────────────────────────────────────
        st.markdown("**Pattern Detection** — Let Claude analyse all your feedback records and surface systemic biases.")
        _pat_col1, _pat_col2 = st.columns([3, 1])
        with _pat_col2:
            if st.button(
                "🔍 Detect Patterns",
                key="detect_patterns_btn",
                type="primary",
                disabled=len(_all_fb) < 2,
                help="Requires at least 2 feedback records",
            ):
                with st.spinner(f"Analysing {len(_all_fb)} feedback records for patterns…"):
                    _pattern_report = _detect_systematic_patterns(_all_fb)
                st.session_state["_pattern_report"] = _pattern_report
        with _pat_col1:
            st.caption(
                f"Will analyse {len(_all_fb)} feedback record(s). "
                "Best results with 3+ projects."
                if _all_fb else "Add feedback records in the Excel Feedback tab first."
            )

        if st.session_state.get("_pattern_report"):
            _pr = st.session_state["_pattern_report"]
            st.markdown("**Detected patterns:**")
            _pblocks = [b.strip() for b in _pr.split("\n\n") if b.strip()]
            for _pb in _pblocks:
                _plines = _pb.splitlines()
                _patt_line = next((l for l in _plines if l.startswith("PATTERN:")), "")
                _rule_line  = next((l for l in _plines if l.startswith("RULE:")), "")
                if not _patt_line and not _rule_line:
                    st.markdown(_pb); continue
                with st.expander(
                    (_patt_line.replace("PATTERN:", "").strip() or "Pattern") if _patt_line else "Pattern",
                    expanded=True,
                ):
                    if _patt_line:
                        st.markdown(f"**Issue:** {_patt_line.replace('PATTERN:','').strip()}")
                    if _rule_line:
                        _rl = _rule_line.replace("RULE:", "").strip()
                        st.info(f"**Suggested rule:** {_rl}")
                        _pk = f"save_pattern_{hash(_rl)%99999}"
                        if st.button("✅ Save as Training Instruction", key=_pk):
                            _iid = add_instruction(_rl, category="hours", created_by="admin")
                            st.success(f"Saved as instruction #{_iid}")
                            st.session_state.pop("_pattern_report", None)
                            st.rerun()
            if st.button("✖ Clear report", key="clear_pattern_report"):
                st.session_state.pop("_pattern_report", None)
                st.rerun()

        st.markdown("---")

        # ── Last run context ─────────────────────────────────────────────
        _last_ctx = st.session_state.get("_training_context", "")
        _last_types = st.session_state.get("_training_types", [])
        with st.expander(
            f"Last estimation — training context applied (project types: {_last_types or ['All']})",
            expanded=False,
        ):
            if _last_ctx:
                st.code(_last_ctx, language=None)
            else:
                st.info("Run an estimation to see what training context was injected.")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 2: ADMIN
# ═══════════════════════════════════════════════════════════════════════

def tab_admin():
    st.markdown('<div class="shdr"><span class="shdr-i">🧠</span> Continuous Learning</div>', unsafe_allow_html=True)
    at = st.tabs(["📊 Dashboard", "📚 Training", "🔧 Config", "📁 Sync", "🔄 Loop", "📚 Templates", "💬 Feedback", "🧠 Knowledge Base"])

    with at[0]:
        m = st.session_state.model_metrics
        mc = st.columns(4)
        with mc[0]:
            st.metric("Proposals", m["proposals_processed"])
        with mc[1]:
            st.metric("Accuracy", str(m["accuracy"]) + "%")
        with mc[2]:
            st.metric("Win Rate", str(m["win_rate"]) + "%")
        with mc[3]:
            st.metric("Variance", str(m["variance"]) + "%")
        dates = [(datetime.now() - timedelta(days=30 * i)).strftime("%b %Y") for i in range(6, -1, -1)]
        fig = go.Figure(go.Scatter(x=dates, y=[65, 68, 72, 74, 76, 78, 80], mode="lines+markers",
                                   line=dict(color="#00d4aa", width=3), marker=dict(size=10)))
        fig.update_layout(title="Accuracy Trend", template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350)
        st.plotly_chart(fig, width="stretch")
        dc1, dc2 = st.columns(2)
        with dc1:
            fig2 = go.Figure(go.Bar(x=["Time", "Cost", "Risk", "Arch"], y=[85, 79, 82, 88],
                                    marker_color=["#00d4aa", "#00b4d8", "#ffd166", "#7b61ff"],
                                    text=["85%", "79%", "82%", "88%"], textposition="auto"))
            fig2.update_layout(title="Agent Accuracy", template="plotly_dark",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300)
            st.plotly_chart(fig2, width="stretch")
        with dc2:
            fig3 = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=m["accuracy"], delta={"reference": 72},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#00d4aa"},
                       "steps": [{"range": [0, 50], "color": "rgba(255,107,107,.2)"}, {"range": [50, 75], "color": "rgba(255,209,102,.2)"}, {"range": [75, 100], "color": "rgba(0,212,170,.2)"}]},
                title={"text": "Model Health"}))
            fig3.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", height=300)
            st.plotly_chart(fig3, width="stretch")

    with at[1]:
        _render_training_tab()

    with at[2]:
        cc1, cc2 = st.columns(2)
        with cc1:
            for ph in ["Discovery", "Design", "Development", "Deployment", "Support"]:
                st.checkbox(ph, True, key="p_" + ph)
            st.selectbox("Estimation", ["Three-Point", "Story Points", "Function Points"], key="em")
            st.slider("Buffer %", 0, 50, 20, key="bf")
        with cc2:
            for rn, rv in [("Architects", 1), ("Lead Devs", 1), ("Developers", 3), ("QA", 1), ("DevOps", 1), ("PMs", 1)]:
                st.number_input(rn, 0, 20, rv, key="r_" + rn)
            st.selectbox("Pricing", ["Fixed Price", "T&M", "Retainer"], key="pc")
        tc = st.columns(3)
        with tc[0]:
            if st.button("Train", width="stretch", type="primary", key="bt"):
                pb = st.progress(0)
                for i in range(100):
                    time.sleep(0.02)
                    pb.progress(i + 1)
                st.session_state.model_metrics["accuracy"] = min(st.session_state.model_metrics["accuracy"] + 2.5, 95)
                st.success("Training complete!")
        with tc[1]:
            if st.button("Retrain", width="stretch", key="br"):
                time.sleep(1)
                st.success("Retrained.")
        with tc[2]:
            if st.button("A/B Test", width="stretch", key="ba"):
                time.sleep(1)
                st.success("New model +8.3%")

    with at[3]:
        st.text_input("Library Path", placeholder="/sites/presales/Historical", key="ssp")
        st.multiselect("Types", ["Proposals", "Estimates", "Outcomes", "Templates"], default=["Proposals", "Estimates", "Outcomes"], key="sst")
        if st.button("Sync Now", width="stretch", type="primary", key="bs"):
            time.sleep(2)
            st.success("Synced 47 docs.")

    with at[4]:
        steps = [("1", "Outcome", "Win/loss + feedback", "#7b61ff"), ("2", "Enrichment", "Link to estimates", "#00b4d8"), ("3", "Retraining", "Fine-tune model", "#00d4aa"), ("4", "Validation", "A/B testing", "#ffd166"), ("5", "Deploy", "Push to prod", "#ff6b6b")]
        lc = st.columns(5)
        for i, (n, t, d, c) in enumerate(steps):
            with lc[i]:
                st.markdown('<div class="ls" style="border-top:3px solid ' + c + ';"><div class="ln" style="background:' + c + ';">' + n + '</div><div class="lt">' + t + '</div><div class="ld">' + d + '</div></div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### Record Outcome")
        with st.form("of"):
            oc1, oc2 = st.columns(2)
            with oc1:
                st.text_input("Project", key="on")
                st.selectbox("Result", ["Won", "Lost", "No Decision"], key="ores")
                st.number_input("Actual Hours", 0, key="oh")
            with oc2:
                st.text_area("Feedback", key="ofb")
                st.number_input("Actual Cost", 0, key="oc")
                st.text_area("Lessons", key="ol")
            if st.form_submit_button("Record", type="primary"):
                st.success("Recorded for next training cycle.")
        st.markdown("---")
        method_cols = st.columns(5)
        method_data = [("📋", "Phases", "Discovery Design Dev Deploy Support"), ("👥", "Team", "Arch Lead Dev QA DevOps PM"), ("📐", "Estimation", "Three-point + 20% buffer"), ("💲", "Pricing", "Fixed, T&M, Retainer"), ("⚠️", "Risk", "Tech Schedule Resource Budget External")]
        for i, (ic, t, d) in enumerate(method_data):
            with method_cols[i]:
                st.markdown('<div class="mc"><div class="mi">' + ic + '</div><div class="mt">' + t + '</div><div class="md2">' + d + '</div></div>', unsafe_allow_html=True)

    # ── Tab 6 : Template Library ──────────────────────────────────────────
    with at[5]:
        _render_template_library_tab()

    # ── Tab 7 : Presales Feedback ─────────────────────────────────────────
    with at[6]:
        render_feedback_admin_panel()

    with at[7]:
        _render_knowledge_base_tab()


# ── Knowledge Base Ingestion UI ──────────────────────────────────────────
def _render_knowledge_base_tab():
    import io, uuid as _uuid, time as _time
    st.markdown('<div class="shdr"><span class="shdr-i">🧠</span> Knowledge Base — Proposal Documents</div>', unsafe_allow_html=True)
    st.caption(
        "Upload past proposal / estimation documents (DOCX, PDF, PPTX). "
        "Each file is chunked, embedded, and stored in the **`collection_proposals_v1`** Milvus collection "
        "so the AI can reference them during future estimations."
    )

    # ── Collection status ────────────────────────────────────────────────
    with st.expander("📦 Collection Status", expanded=True):
        if st.button("🔍 Check / Create Collection", key="kb_check", type="primary"):
            with st.spinner("Connecting to Milvus…"):
                msg = _kb_ensure_collection()
            st.success(msg) if "ready" in msg.lower() or "created" in msg.lower() or "exists" in msg.lower() else st.error(msg)

    st.divider()

    # ── Upload & ingest ──────────────────────────────────────────────────
    st.markdown("#### Upload Documents")
    uploaded = st.file_uploader(
        "Select files from your Digital Proposals folder",
        type=["docx", "pdf", "pptx"],
        accept_multiple_files=True,
        key="kb_upload",
    )

    # ── Project category tags ────────────────────────────────────────────
    _KB_CATS = ["Data", "AI", "SharePoint", "Cloud", "Integration", "Mobile", "Web App", "DevOps"]
    _kb_tag_cols = st.columns([3, 2])
    with _kb_tag_cols[0]:
        _kb_selected = st.multiselect(
            "Project type tags",
            options=_KB_CATS,
            default=[],
            key="kb_tags",
            help="Select all that apply — stored as metadata in Milvus so the AI can filter by project type.",
        )
    with _kb_tag_cols[1]:
        _kb_custom = st.text_input(
            "Custom tags (comma-separated)",
            value="",
            placeholder="e.g. Fabric, RAG, Teams",
            key="kb_custom_tags",
        )
    _all_tags = ", ".join(
        t.strip() for t in (_kb_selected + [x.strip() for x in _kb_custom.split(",") if x.strip()])
    )[:100]  # Milvus field is VARCHAR(100)
    if _all_tags:
        st.caption(f"Tags that will be stored: **{_all_tags}**")

    if uploaded:
        st.markdown(f"**{len(uploaded)} file(s) ready to ingest**")
        for f in uploaded:
            size_kb = round(len(f.getvalue()) / 1024, 1)
            st.markdown(f"&nbsp;&nbsp;📄 `{f.name}` — {size_kb} KB")

        col_go, col_clr = st.columns([2, 1])
        with col_go:
            if st.button("⚡ Ingest All into Knowledge Base", type="primary", key="kb_ingest", width="stretch"):
                _kb_run_ingestion(uploaded, project_tags=_all_tags)

    st.divider()

    # ── Browse stored docs ───────────────────────────────────────────────
    st.markdown("#### Stored Documents")
    if st.button("📋 List Knowledge Base Contents", key="kb_list"):
        with st.spinner("Querying Milvus…"):
            rows = _kb_list_documents()
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=300)
            st.caption(f"{len(rows)} chunk(s) stored")
        else:
            st.info("No documents found in collection_proposals_v1 yet.")


def _kb_ensure_collection() -> str:
    """Create collection_proposals_v1 if it doesn't exist. Returns status string."""
    try:
        from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
        import streamlit as st
        ss = st.session_state
        alias = "milvus_kb"
        if not connections.has_connection(alias):
            connections.connect(
                alias=alias,
                host=ss.get("milvus_host", "20.62.9.198"),
                port=str(ss.get("milvus_port", "19530")),
                user=ss.get("milvus_user", ""),
                password=ss.get("milvus_password", ""),
                db_name=ss.get("milvus_db", ""),
            )
        col_name = "collection_proposals_v1"
        if utility.has_collection(col_name, using=alias):
            col = Collection(col_name, using=alias)
            col.load()
            cnt = col.num_entities
            return f"✅ Collection **{col_name}** already exists — {cnt} chunk(s) stored."
        # Create schema matching collection_demo_v1
        fields = [
            FieldSchema("id",                       DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema("document_id",              DataType.INT64),
            FieldSchema("vector",                   DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema("source",                   DataType.VARCHAR, max_length=500),
            FieldSchema("document_type",            DataType.VARCHAR, max_length=100),
            FieldSchema("text",                     DataType.VARCHAR, max_length=65535),
            FieldSchema("estimation_reference_url", DataType.VARCHAR, max_length=3000),
        ]
        schema = CollectionSchema(fields, "Digital Proposals knowledge base")
        col = Collection(col_name, schema=schema, using=alias)
        col.create_index("vector", {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
        col.load()
        return f"✅ Collection **{col_name}** created successfully with COSINE index."
    except Exception as e:
        return f"❌ Milvus error: {e}"


def _kb_extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract raw text from DOCX, PDF, or PPTX."""
    ext = filename.rsplit(".", 1)[-1].lower()
    import io
    try:
        if ext == "docx":
            from docx import Document as DocxDoc
            doc = DocxDoc(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == "pdf":
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == "pptx":
            from pptx import Presentation
            prs = Presentation(io.BytesIO(file_bytes))
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        parts.append(shape.text)
            return "\n".join(parts)
    except Exception as e:
        return ""
    return ""


def _kb_chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def _kb_embed(text: str) -> list:
    """Generate embedding via the configured Azure OpenAI embedding endpoint."""
    from openai import AzureOpenAI
    import streamlit as st
    ss = st.session_state
    client = AzureOpenAI(
        azure_endpoint=ss.get("milvus_embedding_endpoint", ""),
        api_key=ss.get("milvus_embedding_key", ""),
        api_version=ss.get("milvus_embedding_api_version", "2025-01-01-preview"),
    )
    resp = client.embeddings.create(
        model=ss.get("milvus_embedding_deployment", "text-embedding-3-small"),
        input=text[:8000],
    )
    return resp.data[0].embedding


def _kb_run_ingestion(uploaded_files, project_tags: str = ""):
    import streamlit as st
    import uuid as _uuid, time as _time
    from pymilvus import connections, Collection, utility

    ss = st.session_state
    alias = "milvus_kb"

    # Ensure connected
    ensure_msg = _kb_ensure_collection()
    if "❌" in ensure_msg:
        st.error(ensure_msg)
        return

    try:
        if not connections.has_connection(alias):
            connections.connect(alias=alias, host=ss.get("milvus_host","20.62.9.198"),
                                port=str(ss.get("milvus_port","19530")),
                                user=ss.get("milvus_user",""), password=ss.get("milvus_password",""),
                                db_name=ss.get("milvus_db",""))
        col = Collection("collection_proposals_v1", using=alias)
    except Exception as e:
        st.error(f"Cannot connect to Milvus: {e}")
        return

    total_chunks = 0
    for uf in uploaded_files:
        file_bytes = uf.getvalue()
        fname = uf.name
        with st.status(f"Processing **{fname}**…", expanded=True) as status:
            # Extract
            st.write("📖 Extracting text…")
            text = _kb_extract_text(file_bytes, fname)
            if not text.strip():
                st.warning(f"No text extracted from {fname} — skipping.")
                status.update(label=f"⚠️ {fname} — no text extracted", state="error")
                continue
            st.write(f"✅ Extracted {len(text.split())} words")

            # Chunk
            st.write("✂️ Chunking…")
            chunks = _kb_chunk_text(text)
            st.write(f"✅ {len(chunks)} chunk(s)")

            # Embed + store
            st.write("🔗 Embedding and storing…")
            stored = 0
            prog = st.progress(0)
            for idx, chunk in enumerate(chunks):
                try:
                    vec = _kb_embed(chunk)
                    row = {
                        "id":                       str(_uuid.uuid4())[:100],
                        "document_id":              int(_time.time()),
                        "vector":                   vec,
                        "source":                   fname[:250],
                        "document_type":            (project_tags or "proposal")[:100],
                        "text":                     chunk[:65000],
                        "estimation_reference_url": "",
                    }
                    col.insert([row])
                    stored += 1
                    prog.progress((idx + 1) / len(chunks))
                except Exception as e:
                    st.warning(f"Chunk {idx+1} error: {e}")
            col.flush()
            total_chunks += stored
            status.update(label=f"✅ {fname} — {stored} chunk(s) stored", state="complete")

    st.success(f"🎉 Ingestion complete — **{total_chunks} chunk(s)** stored across {len(uploaded_files)} file(s) in `collection_proposals_v1`")


def _kb_list_documents() -> list:
    """List distinct documents stored in collection_proposals_v1."""
    try:
        import streamlit as st
        from pymilvus import connections, Collection, utility
        ss = st.session_state
        alias = "milvus_kb"
        if not connections.has_connection(alias):
            connections.connect(alias=alias, host=ss.get("milvus_host","20.62.9.198"),
                                port=str(ss.get("milvus_port","19530")),
                                user=ss.get("milvus_user",""), password=ss.get("milvus_password",""),
                                db_name=ss.get("milvus_db",""))
        if not utility.has_collection("collection_proposals_v1", using=alias):
            return []
        col = Collection("collection_proposals_v1", using=alias)
        col.load()
        rows = col.query(expr='id != ""', output_fields=["id","source","document_type","text"], limit=500)
        # Summarise by source
        by_source = {}
        for r in rows:
            src = r.get("source","Unknown")
            by_source.setdefault(src, {"Document": src, "Chunks": 0, "Tags": r.get("document_type","")})
            by_source[src]["Chunks"] += 1
            if "Preview" not in by_source[src]:
                by_source[src]["Preview"] = (r.get("text") or "")[:120] + "…"
        return list(by_source.values())
    except Exception as e:
        return []


# ── Template Library admin UI ────────────────────────────────────────────
def _render_template_library_tab():
    st.markdown(
        '<div class="shdr"><span class="shdr-i">📚</span> Template Library</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Manage reusable content blocks. When a proposal is generated, the AI automatically "
        "selects matching templates based on project type and tech stack and uses them as "
        "grounding material — reducing hallucination and ensuring brand-consistent output."
    )

    # ── Summary pills ────────────────────────────────────────────────────
    all_tpls = get_templates(active_only=False)
    pill_cols = st.columns(len(CATEGORIES))
    for idx, (cat_key, cat_meta) in enumerate(CATEGORIES.items()):
        count = sum(1 for t in all_tpls if t["category"] == cat_key)
        with pill_cols[idx]:
            st.markdown(
                f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);'
                f'border-radius:10px;padding:10px 14px;text-align:center">'
                f'<div style="font-size:1.4rem">{cat_meta["icon"]}</div>'
                f'<div style="font-weight:700;font-size:1.1rem;color:{cat_meta["color"]}">{count}</div>'
                f'<div style="font-size:.75rem;color:#94a3b8">{cat_meta["label"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Action bar ───────────────────────────────────────────────────────
    tb_col1, tb_col2, tb_col3 = st.columns([3, 2, 2])
    with tb_col1:
        filter_cat = st.selectbox(
            "Filter by category",
            ["All"] + list(CATEGORIES.keys()),
            format_func=lambda x: "All Categories" if x == "All"
                                  else f"{CATEGORIES[x]['icon']} {CATEGORIES[x]['label']}",
            key="_tpl_filter_cat",
        )
    with tb_col2:
        show_inactive = st.checkbox("Show inactive templates", key="_tpl_show_inactive")
    with tb_col3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("➕ Add Template", width="stretch", type="primary", key="_tpl_add_btn"):
            st.session_state["_tpl_mode"] = "add"
            st.session_state["_tpl_edit_id"] = None

    # ── Add / Edit form ───────────────────────────────────────────────────
    mode = st.session_state.get("_tpl_mode")
    edit_id = st.session_state.get("_tpl_edit_id")

    if mode in ("add", "edit"):
        # Pre-fill for edit
        prefill = {}
        if mode == "edit" and edit_id:
            for t in all_tpls:
                if t["id"] == edit_id:
                    prefill = t
                    break

        with st.form("tpl_form", clear_on_submit=True):
            st.markdown(f"**{'Edit' if mode == 'edit' else 'New'} Template**")
            fc1, fc2 = st.columns(2)
            with fc1:
                f_cat = st.selectbox(
                    "Category",
                    list(CATEGORIES.keys()),
                    index=list(CATEGORIES.keys()).index(prefill.get("category", "scope_section")),
                    format_func=lambda x: f"{CATEGORIES[x]['icon']} {CATEGORIES[x]['label']}",
                    key="tpl_f_cat",
                )
                f_title = st.text_input("Title", value=prefill.get("title", ""), key="tpl_f_title")
            with fc2:
                # Tag options depend on category
                if f_cat == "scope_section":
                    tag_options = PROJECT_TYPES + TECHNOLOGIES
                elif f_cat == "assumption":
                    tag_options = PROJECT_TYPES + TECHNOLOGIES
                elif f_cat == "risk_mitigation":
                    tag_options = RISK_CATEGORIES
                else:  # team_bio
                    tag_options = ROLES

                f_tags = st.multiselect(
                    "Tags (used for auto-matching)",
                    tag_options,
                    default=[t for t in prefill.get("tags", []) if t in tag_options],
                    key="tpl_f_tags",
                )
                f_active = st.checkbox("Active", value=prefill.get("is_active", 1) == 1, key="tpl_f_active")

            f_content = st.text_area(
                "Content", value=prefill.get("content", ""),
                height=180, key="tpl_f_content",
                help="Write the pre-approved text for this template block.",
            )

            s1, s2, s3 = st.columns(3)
            with s1:
                submitted = st.form_submit_button("💾 Save", type="primary", width="stretch")
            with s2:
                cancelled = st.form_submit_button("Cancel", width="stretch")

            if submitted:
                if not f_title.strip():
                    st.error("Title is required.")
                elif not f_content.strip():
                    st.error("Content is required.")
                else:
                    user = st.session_state.get("auth_user", "Admin")
                    if mode == "edit" and edit_id:
                        update_template(edit_id, f_title.strip(), f_tags, f_content.strip(), f_active)
                        st.success(f"Template updated: {f_title}")
                    else:
                        add_template(f_cat, f_title.strip(), f_tags, f_content.strip(), created_by=user)
                        st.success(f"Template added: {f_title}")
                    st.session_state["_tpl_mode"] = None
                    st.session_state["_tpl_edit_id"] = None
                    st.rerun()
            if cancelled:
                st.session_state["_tpl_mode"] = None
                st.session_state["_tpl_edit_id"] = None
                st.rerun()

    # ── Template list ─────────────────────────────────────────────────────
    display_cat = None if filter_cat == "All" else filter_cat
    tpls = get_templates(category=display_cat, active_only=not show_inactive)

    if not tpls:
        st.info("No templates found. Click **➕ Add Template** to create the first one.")
    else:
        # Group by category for display
        from collections import defaultdict
        grouped: dict = defaultdict(list)
        for t in tpls:
            grouped[t["category"]].append(t)

        for cat_key, items in grouped.items():
            cat_meta = CATEGORIES.get(cat_key, {"icon": "📄", "label": cat_key, "color": "#94a3b8"})
            st.markdown(
                f'<div style="font-size:.8rem;font-weight:700;color:{cat_meta["color"]};'
                f'text-transform:uppercase;letter-spacing:.06em;margin:18px 0 8px">'
                f'{cat_meta["icon"]} {cat_meta["label"]}</div>',
                unsafe_allow_html=True,
            )
            for t in items:
                is_active = t.get("is_active", 1) == 1
                opacity = "1" if is_active else "0.45"
                tag_pills = "".join(
                    f'<span style="background:rgba(255,255,255,.07);border-radius:4px;'
                    f'padding:2px 7px;font-size:.68rem;color:#94a3b8;margin-right:4px">{tag}</span>'
                    for tag in t.get("tags", [])
                )
                with st.expander(
                    f"{'✅' if is_active else '⏸️'} {t['title']}",
                    expanded=False,
                ):
                    st.markdown(
                        f'<div style="opacity:{opacity}">'
                        f'<div style="margin-bottom:8px">{tag_pills}</div>'
                        f'<div style="font-size:.84rem;color:#cbd5e1;line-height:1.6;'
                        f'background:rgba(0,0,0,.2);border-radius:8px;padding:12px 14px">'
                        f'{t["content"]}'
                        f'</div>'
                        f'<div style="font-size:.68rem;color:#475569;margin-top:6px">'
                        f'Created by {t.get("created_by","—")} · Updated {t.get("updated_ts","—")[:10]}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    ea, da = st.columns(2)
                    with ea:
                        if st.button("✏️ Edit", key=f"tpl_edit_{t['id']}", width="stretch"):
                            st.session_state["_tpl_mode"] = "edit"
                            st.session_state["_tpl_edit_id"] = t["id"]
                            st.rerun()
                    with da:
                        if st.button("🗑️ Delete", key=f"tpl_del_{t['id']}", width="stretch"):
                            delete_template(t["id"])
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  TAB 3: RUN LIBRARY  (persistent across refreshes — SQLite backed)
# ═══════════════════════════════════════════════════════════════════════

_CAT_ICONS = {"AI": "🤖", "Data": "📊", "Cloud": "☁️", "General": "📁", "All": "🗂️"}
_CAT_COLORS = {
    "AI":      "#7b61ff",
    "Data":    "#00d4aa",
    "Cloud":   "#00b4d8",
    "General": "#94a3b8",
}


def _cat_badge(cat: str) -> str:
    icon  = _CAT_ICONS.get(cat, "📁")
    color = _CAT_COLORS.get(cat, "#94a3b8")
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'border-radius:6px;padding:2px 9px;font-size:.72rem;font-weight:700">'
        f'{icon} {cat}</span>'
    )


def _risk_badge(level: str) -> str:
    color = {"Low": "#06d6a0", "Medium": "#ffd166", "High": "#ff6b6b"}.get(level, "#94a3b8")
    return (
        f'<span style="color:{color};font-weight:700;font-size:.8rem">'
        f'{"🟢" if level=="Low" else "🟡" if level=="Medium" else "🔴" if level=="High" else "⚪"} {level}</span>'
    )


@st.cache_data(ttl=300, max_entries=100, show_spinner=False)
def _cached_run_json(run_id: int) -> str:
    """Cache the full results blob as a JSON string (5-min TTL, avoids DB hit on every rerun)."""
    return json.dumps(_db_load_results(run_id), indent=2, default=str)

@st.cache_data(ttl=30, show_spinner=False)
def _cached_category_counts() -> dict:
    return _db_category_counts()

@st.cache_data(ttl=30, show_spinner=False)
def _cached_load_runs(category: str, include_archived: bool) -> list:
    return _db_load_runs(category, include_archived=include_archived)

@st.cache_data(ttl=20, show_spinner=False)
def _cached_activity_log(limit: int) -> list:
    return db_get_activity_log(limit=limit)


def _log_act(action: str, details: str = "", module: str = ""):
    """Convenience: log a user event from any tab (silent on error)."""
    try:
        db_log_activity(
            st.session_state.get("auth_email", ""),
            st.session_state.get("auth_user", "Unknown"),
            action, details, module,
        )
        _cached_activity_log.clear()   # keep log tab live
    except Exception:
        pass


def _track_tab(tab_name: str):
    """Log a tab/feature visit once per unique run × tab combination."""
    _run_id = st.session_state.get("_last_run_id", "new")
    _key    = f"_tv_{tab_name.lower()[:20].replace(' ','_')}_{_run_id}"
    if not st.session_state.get(_key):
        st.session_state[_key] = True
        _log_act("tab_view", f"Opened: {tab_name}", "Navigation")


@st.fragment
def tab_run_library():
    import pandas as pd
    from datetime import date as _date, timedelta as _td

    _me_email = st.session_state.get("auth_email", "")
    _is_admin = st.session_state.get("auth_method") == "Admin"

    # ── My Runs / All Runs toggle ──────────────────────────────────────
    _lib_hdr_c, _lib_tog_c = st.columns([5, 3])
    with _lib_hdr_c:
        st.markdown('<div class="shdr"><span class="shdr-i">🗂️</span> Run Library</div>', unsafe_allow_html=True)
    with _lib_tog_c:
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        _view_mode = st.radio(
            "View",
            ["👤 My Runs", "🌐 All Runs"],
            horizontal=True,
            key="lib_view_mode",
            label_visibility="collapsed",
        )
    _show_my_only = (_view_mode == "👤 My Runs")

    st.markdown(
        ("Showing **your proposals only**. Switch to 🌐 All Runs to see the full team library."
         if _show_my_only else
         "Every pipeline run is **automatically saved here** and survives page refreshes, "
         "browser closes, and app restarts. Filter, compare, restore, or export any run."),
    )

    # ── Revision mode active banner ────────────────────────────────────
    _rev_pid = st.session_state.get("_revision_parent_id")
    if _rev_pid:
        try:
            import sqlite3 as _sqx; from .database import _DB_PATH as _DBPX
            _cx = _sqx.connect(_DBPX); _cx.row_factory = _sqx.Row
            _rx = dict(_cx.execute(
                "SELECT client_name, project_type, version_number FROM proposals WHERE id=?", (_rev_pid,)
            ).fetchone() or {})
            _cx.close()
            _rev_label = f"Run #{_rev_pid}" + (f" · {_rx['client_name']}" if _rx.get("client_name") else "") + (f" — {_rx['project_type']}" if _rx.get("project_type") else "")
        except Exception:
            _rev_label = f"Run #{_rev_pid}"
        st.markdown(
            f'<div style="background:linear-gradient(90deg,#1a1040,#0d1635);'
            f'border:1.5px solid #7b61ff;border-radius:10px;padding:14px 18px;'
            f'display:flex;align-items:center;justify-content:space-between;gap:12px">'
            f'  <div>'
            f'    <span style="color:#a78bfa;font-weight:700;font-size:.85rem">✏️ Revision mode active</span>'
            f'    <span style="color:#64748b;font-size:.8rem;margin-left:10px">{_rev_label}</span>'
            f'  </div>'
            f'  <div style="color:#7b61ff;font-size:.82rem;font-weight:600">'
            f'    → Click <strong style="color:#e2e8f0">⚡ Business Estimation</strong> tab to upload revised scope'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    st.markdown("---")

    # ── Category pill badges ───────────────────────────────────────────
    counts = _cached_category_counts()
    cats   = ["All", "AI", "Data", "Cloud", "General"]
    # For "My Runs" mode compute per-category counts from my runs only
    if _show_my_only and _me_email:
        _my_all = _cached_load_runs("All", include_archived=st.session_state.get("lib_show_archived", False))
        _my_runs_all = [r for r in _my_all if (r.get("created_by_email") or "").lower() == _me_email.lower()]
        _my_counts = {"All": len(_my_runs_all)}
        for _cat in ["AI","Data","Cloud","General"]:
            _my_counts[_cat] = sum(1 for r in _my_runs_all if r.get("category") == _cat)
        counts = _my_counts
    pill_html = ""
    for cat in cats:
        n     = counts.get(cat, 0)
        icon  = _CAT_ICONS.get(cat, "📁")
        color = _CAT_COLORS.get(cat, "#94a3b8") if cat != "All" else "#e2e8f0"
        pill_html += (
            f'<span style="background:{color}22;color:{color if cat!="All" else "#e2e8f0"};'
            f'border:1px solid {color}55;border-radius:20px;padding:4px 14px;'
            f'font-size:.78rem;font-weight:700;margin-right:6px">'
            f'{icon} {cat} ({n})</span>'
        )
    st.markdown(pill_html, unsafe_allow_html=True)
    st.markdown("")

    # ── Filters row 1 ─────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([2, 2, 2, 4])
    with f1:
        selected_cat = st.selectbox(
            "Category", cats,
            format_func=lambda c: f"{_CAT_ICONS.get(c,'📁')} {c} ({counts.get(c,0)})",
            key="lib_cat_filter",
        )
    with f2:
        sort_by = st.selectbox(
            "Sort by",
            ["Newest", "Oldest", "Highest Cost", "Most Hours", "Highest Risk"],
            key="lib_sort",
        )
    with f3:
        review_filter = st.selectbox(
            "Review status",
            ["All", "✅ Approved", "🔄 Needs Changes", "⏳ Pending"],
            key="lib_rev_filter",
        )
    with f4:
        search_q = st.text_input(
            "Search",
            placeholder="client, project, tech stack, or author…",
            key="lib_search",
        )

    # ── Filters row 2: date range + archived toggle ────────────────────
    dr1, dr2, dr3, dr4 = st.columns([2, 2, 2, 2])
    with dr1:
        date_preset = st.selectbox(
            "Date range",
            ["All Time", "Today", "This Week", "This Month", "Custom"],
            key="lib_date_preset",
        )
    today = _date.today()
    if date_preset == "Today":
        from_date, to_date = today, today
    elif date_preset == "This Week":
        from_date = today - _td(days=today.weekday())
        to_date   = today
    elif date_preset == "This Month":
        from_date = today.replace(day=1)
        to_date   = today
    elif date_preset == "Custom":
        with dr2:
            from_date = st.date_input("From", value=today - _td(days=30), key="lib_from_date")
        with dr3:
            to_date   = st.date_input("To",   value=today,                key="lib_to_date")
    else:
        from_date = to_date = None
    with dr4:
        show_archived = st.checkbox("Show archived runs", value=False, key="lib_show_archived")

    # ── Load ──────────────────────────────────────────────────────────
    runs = _cached_load_runs(selected_cat, include_archived=show_archived)

    # My Runs filter
    if _show_my_only and _me_email:
        runs = [r for r in runs if (r.get("created_by_email") or "").lower() == _me_email.lower()]

    # Date filter
    if from_date and to_date:
        from_str = from_date.strftime("%Y-%m-%d")
        to_str   = to_date.strftime("%Y-%m-%d")
        runs = [r for r in runs if from_str <= (r.get("ts") or "")[:10] <= to_str]

    # Text search (includes author)
    if search_q.strip():
        q = search_q.strip().lower()
        runs = [
            r for r in runs
            if q in (r.get("project_type")    or "").lower()
            or q in (r.get("client_name")      or "").lower()
            or q in (r.get("project_title")    or "").lower()
            or any(q in t.lower() for t in (r.get("tech_stack") or []))
            or q in (r.get("created_by")       or "").lower()
            or q in (r.get("created_by_email") or "").lower()
        ]

    # Review status filter
    def _rs(r):
        s = r.get("review_status") or ""
        if not s or s == "pending":
            return "approved" if r.get("architect_reviewed", 0) else "pending"
        return s

    _REV_MAP = {
        "✅ Approved":      lambda r: _rs(r) == "approved",
        "🔄 Needs Changes": lambda r: _rs(r) == "needs_changes",
        "⏳ Pending":       lambda r: _rs(r) == "pending",
    }
    if review_filter in _REV_MAP:
        runs = [r for r in runs if _REV_MAP[review_filter](r)]

    sort_key_map = {
        "Newest":       lambda r: -r["id"],
        "Oldest":       lambda r:  r["id"],
        "Highest Cost": lambda r: -(r.get("monthly_cost") or 0),
        "Most Hours":   lambda r: -(r.get("total_hours")  or 0),
        "Highest Risk": lambda r: -(r.get("risk_score")   or 0),
    }
    runs.sort(key=sort_key_map.get(sort_by, lambda r: -r["id"]))

    if not runs:
        _empty_library()
        return

    # ── Summary stats ──────────────────────────────────────────────────
    n_approved      = sum(1 for r in runs if _rs(r) == "approved")
    n_needs_changes = sum(1 for r in runs if _rs(r) == "needs_changes")
    n_pending       = len(runs) - n_approved - n_needs_changes
    st.markdown(
        f"**{len(runs)} proposal{'s' if len(runs)!=1 else ''}** found — "
        f'<span style="color:#06d6a0;font-weight:700">✅ {n_approved} approved</span> · '
        f'<span style="color:#ffd166;font-weight:700">⏳ {n_pending} pending</span> · '
        f'<span style="color:#ff9f43;font-weight:700">🔄 {n_needs_changes} needs changes</span>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Restore confirmation banner (two-click safety) ─────────────────
    pending_restore_id = st.session_state.get("lib_pending_restore_id")
    if pending_restore_id:
        _pr = next((r for r in runs if r["id"] == pending_restore_id), None)
        if not _pr:
            _all = _db_load_runs("All", include_archived=True)
            _pr  = next((r for r in _all if r["id"] == pending_restore_id), None)
        _label = (
            f"Run #{pending_restore_id} — "
            + ((_pr.get("client_name") or _pr.get("project_type", "")) if _pr else "")
        )
        st.warning(f"⚠️ **Restore {_label}?** This will overwrite your current proposal in the session.")
        _rc1, _rc2, _ = st.columns([1, 1, 6])
        with _rc1:
            if st.button("✅ Yes, Restore", key="lib_confirm_restore_yes",
                         type="primary", width="stretch"):
                with st.spinner("Restoring run…"):
                    full = json.loads(_cached_run_json(pending_restore_id))
                if full:
                    st.session_state.processing_results  = full
                    st.session_state["_last_run_id"]     = pending_restore_id
                    st.session_state["_parent_run_id"]   = pending_restore_id  # lineage: next run links back here
                    st.session_state.chat_messages       = []
                    st.session_state.feedback_log        = []
                    st.session_state.pop("lib_pending_restore_id", None)
                    st.success(f"Run #{pending_restore_id} restored — switch to ⚡ Business Estimation to view.")
                    st.rerun(scope="app")
                else:
                    st.error("Could not load results for this run.")
        with _rc2:
            if st.button("❌ Cancel", key="lib_confirm_restore_no", width="stretch"):
                st.session_state.pop("lib_pending_restore_id", None)
                st.rerun()
        st.markdown("---")

    # ── Duplicate run warning ──────────────────────────────────────────
    _dw = st.session_state.get("_dup_warning")
    if _dw:
        _dup_ids_str = ", #".join(str(i) for i in _dw.get("dup_ids", []))
        st.warning(
            f"⚠️ **Possible duplicate detected** for **{_dw.get('label','')}** — "
            f"similar run(s) already saved: **#{_dup_ids_str}**. "
            f"Check below before re-running."
        )
        if st.button("Dismiss", key="lib_dup_dismiss"):
            st.session_state.pop("_dup_warning", None)
            st.rerun()
        st.markdown("---")

    # ── Run comparison initialise ──────────────────────────────────────
    if "lib_compare_ids" not in st.session_state:
        st.session_state["lib_compare_ids"] = []

    # ── Table view ─────────────────────────────────────────────────────
    with st.expander("📋 Table View", expanded=False):
        tbl_rows = []
        for r in runs:
            rs_val = _rs(r)
            rev_icon = {"approved": "✅", "needs_changes": "🔄", "pending": "⏳"}.get(rs_val, "⏳")
            tbl_rows.append({
                "ID":          r["id"],
                "Status":      rev_icon + " " + rs_val.replace("_", " ").title(),
                "Time":        r.get("ts", ""),
                "Category":    _CAT_ICONS.get(r.get("category",""), "📁") + " " + r.get("category",""),
                "Client":      r.get("client_name", "") or "",
                "Project":     r.get("project_title", "") or r.get("project_type", ""),
                "Hours":       r.get("total_hours", 0),
                "Weeks":       r.get("duration_weeks", ""),
                "$/mo":        f"${r.get('monthly_cost',0):,}",
                "Risk":        r.get("risk_level", ""),
                "Reqs":        r.get("req_count", 0),
                "Created By":  r.get("created_by", "") or "—",
                "Reviewed By": r.get("reviewed_by", "") or "—",
                "Outcome":     {"won":"🏆 Won","lost":"❌ Lost","no_bid":"🚫 No Bid","pending":"⏳ Open"}.get(r.get("project_outcome","pending"),"⏳ Open"),
                "Act. Hours":  r.get("actual_hours") or "",
                "Parent Run":  f"#{r['parent_run_id']}" if r.get("parent_run_id") else "",
                "Archived":    "🗄️" if r.get("is_archived", 0) else "",
            })
        st.dataframe(pd.DataFrame(tbl_rows), width="stretch", hide_index=True)

    st.markdown("")

    # ── Pagination ─────────────────────────────────────────────────────
    PAGE_SIZE   = 20
    total_pages = max(1, (len(runs) + PAGE_SIZE - 1) // PAGE_SIZE)
    if "lib_page" not in st.session_state:
        st.session_state["lib_page"] = 0
    st.session_state["lib_page"] = min(st.session_state["lib_page"], total_pages - 1)
    cur_page  = st.session_state["lib_page"]
    page_runs = runs[cur_page * PAGE_SIZE : (cur_page + 1) * PAGE_SIZE]

    if total_pages > 1:
        pg1, pg2, pg3 = st.columns([1, 4, 1])
        with pg1:
            if st.button("◀ Prev", key="lib_prev", disabled=cur_page == 0, width="stretch"):
                st.session_state["lib_page"] -= 1
                st.rerun()
        with pg2:
            st.markdown(
                f'<div style="text-align:center;color:#94a3b8;font-size:.85rem;padding-top:8px">'
                f'Page {cur_page+1} of {total_pages} &nbsp;·&nbsp; {len(runs)} total proposals</div>',
                unsafe_allow_html=True,
            )
        with pg3:
            if st.button("Next ▶", key="lib_next", disabled=cur_page >= total_pages-1, width="stretch"):
                st.session_state["lib_page"] += 1
                st.rerun()
        st.markdown("")

    # ── Run comparison panel ───────────────────────────────────────────
    cmp_ids = st.session_state.get("lib_compare_ids", [])
    # Prune IDs that are no longer in the loaded run set
    all_ids = {r["id"] for r in runs}
    cmp_ids = [i for i in cmp_ids if i in all_ids]
    st.session_state["lib_compare_ids"] = cmp_ids

    if len(cmp_ids) == 2:
        _ra = next(r for r in runs if r["id"] == cmp_ids[0])
        _rb = next(r for r in runs if r["id"] == cmp_ids[1])
        st.markdown(
            f'<div style="background:#111827;border:1px solid #7b61ff55;border-radius:12px;'
            f'padding:18px 20px;margin-bottom:16px;border-left:3px solid #7b61ff">'
            f'<div style="font-size:1rem;font-weight:700;color:#7b61ff;margin-bottom:12px">'
            f'📊 Comparing Run #{_ra["id"]} vs Run #{_rb["id"]}</div></div>',
            unsafe_allow_html=True,
        )
        _METRICS = [
            ("Estimated Hours",  "total_hours",   lambda v: f"{v:,} h",      "#00d4aa"),
            ("Infra Cost/mo",    "monthly_cost",  lambda v: f"${v:,}",        "#00b4d8"),
            ("Risk Score",       "risk_score",    lambda v: str(v),           "#ff6b6b"),
            ("Duration",         "duration_weeks",lambda v: str(v) + " wks",  "#ffd166"),
            ("Requirements",     "req_count",     lambda v: str(v),           "#94a3b8"),
        ]
        _hdr, _va, _diff, _vb = st.columns([2, 2, 1, 2])
        _hdr.markdown("**Metric**")
        _va.markdown(f"**Run #{_ra['id']}** — {(_ra.get('client_name') or _ra.get('project_type',''))[:20]}")
        _diff.markdown("**Δ**")
        _vb.markdown(f"**Run #{_rb['id']}** — {(_rb.get('client_name') or _rb.get('project_type',''))[:20]}")
        for _label, _field, _fmt, _color in _METRICS:
            _va_val = _ra.get(_field) or 0
            _vb_val = _rb.get(_field) or 0
            try:
                _delta = int(_vb_val) - int(_va_val)
                _delta_str = (f"+{_delta}" if _delta > 0 else str(_delta))
                _delta_col = "#06d6a0" if _delta <= 0 else "#ff6b6b"
            except Exception:
                _delta_str, _delta_col = "—", "#64748b"
            _hdr2, _vva, _vdiff, _vvb = st.columns([2, 2, 1, 2])
            _hdr2.markdown(f'<span style="color:#94a3b8;font-size:.85rem">{_label}</span>', unsafe_allow_html=True)
            _vva.markdown(f'<span style="color:{_color};font-weight:600">{_fmt(_va_val)}</span>', unsafe_allow_html=True)
            _vdiff.markdown(f'<span style="color:{_delta_col};font-size:.8rem">{_delta_str}</span>', unsafe_allow_html=True)
            _vvb.markdown(f'<span style="color:{_color};font-weight:600">{_fmt(_vb_val)}</span>', unsafe_allow_html=True)
        # Tech-stack diff
        _ts_a = set(_ra.get("tech_stack") or [])
        _ts_b = set(_rb.get("tech_stack") or [])
        _only_a = _ts_a - _ts_b
        _only_b = _ts_b - _ts_a
        if _only_a or _only_b:
            st.markdown(
                f'<div style="font-size:.78rem;color:#94a3b8;margin-top:8px">'
                f'Only in #{_ra["id"]}: {", ".join(_only_a) or "—"} &nbsp;|&nbsp; '
                f'Only in #{_rb["id"]}: {", ".join(_only_b) or "—"}</div>',
                unsafe_allow_html=True,
            )
        if st.button("✖ Clear comparison", key="lib_cmp_clear"):
            st.session_state["lib_compare_ids"] = []
            st.rerun()
        st.markdown("---")
    elif len(cmp_ids) == 1:
        st.info(f"Run #{cmp_ids[0]} selected — pick one more card to compare.")
    elif len(cmp_ids) > 2:
        st.session_state["lib_compare_ids"] = cmp_ids[:2]

    # ── Card grid ──────────────────────────────────────────────────────
    COLS      = 2
    grid_cols = st.columns(COLS)
    cur_user  = st.session_state.get("auth_user", "")

    for idx, run in enumerate(page_runs):
        col   = grid_cols[idx % COLS]
        cat   = run.get("category", "General")
        c_col = _CAT_COLORS.get(cat, "#94a3b8")
        hours = run.get("total_hours", 0)
        cost  = run.get("monthly_cost", 0)
        risk  = run.get("risk_level", "")
        three = run.get("three_point", {}) or {}
        tech  = (run.get("tech_stack") or [])[:5]

        rs          = _rs(run)
        review_ts   = run.get("review_ts")    or ""
        rev_notes   = run.get("review_notes") or ""
        reviewed_by = run.get("reviewed_by")  or ""
        created_by  = run.get("created_by")   or ""
        parent_id   = run.get("parent_run_id")
        outcome     = run.get("project_outcome") or "pending"

        # Card heading
        _client = (run.get("client_name")  or "").strip()
        _ptitle = (run.get("project_title") or "").strip()
        _ptype  = (run.get("project_type")  or "Untitled Proposal").strip()
        if _client:
            _card_heading, _card_sub = _client, _ptitle or _ptype
        else:
            _card_heading, _card_sub = _ptitle or _ptype, ""

        # Review status badge
        _BADGES = {
            "approved":      ('<span style="background:#06d6a022;color:#06d6a0;border:1px solid #06d6a055;'
                              'border-radius:20px;padding:2px 10px;font-size:.7rem;font-weight:700">✅ Approved</span>'),
            "needs_changes": ('<span style="background:#ff9f4322;color:#ff9f43;border:1px solid #ff9f4355;'
                              'border-radius:20px;padding:2px 10px;font-size:.7rem;font-weight:700">🔄 Needs Changes</span>'),
            "pending":       ('<span style="background:#ffd16622;color:#ffd166;border:1px solid #ffd16655;'
                              'border-radius:20px;padding:2px 10px;font-size:.7rem;font-weight:700">⏳ Pending Review</span>'),
        }
        rev_badge = _BADGES.get(rs, _BADGES["pending"])

        rev_line = ""
        if rs != "pending" and review_ts:
            _by = f" by <strong>{reviewed_by}</strong>" if reviewed_by else ""
            rev_line = (
                f'<div style="font-size:.65rem;color:#94a3b8;margin-top:4px">'
                f'{review_ts}{_by}'
                + (f' — {rev_notes[:60]}{"…" if len(rev_notes)>60 else ""}' if rev_notes else "")
                + '</div>'
            )

        author_line = (
            f'<div style="font-size:.65rem;color:#64748b;margin-top:2px">👤 {created_by}</div>'
            if created_by else ""
        )
        sub_html = (
            f'<div style="font-size:.75rem;color:#94a3b8;margin-bottom:2px">{_card_sub}</div>'
            if _card_sub else ""
        )
        arch_banner = (
            '<div style="font-size:.65rem;color:#ff6b6b;background:#ff6b6b11;border-radius:4px;'
            'padding:2px 6px;display:inline-block;margin-bottom:4px">🗄️ Archived</div>'
            if run.get("is_archived", 0) else ""
        )
        tech_pills = " ".join(
            f'<span style="background:#1e293b;border:1px solid #334155;border-radius:4px;'
            f'padding:1px 6px;font-size:.68rem;color:#94a3b8">{t}</span>'
            for t in tech
        )
        # Version badge + lineage
        _v_num     = run.get("version_number", 1)
        _neg_stg   = run.get("negotiation_stage", "initial") or "initial"
        _ver_stat  = run.get("version_status", "draft") or "draft"
        _NEG_COLORS = {"initial":"#00b4d8","negotiation":"#ffd166","bafo":"#f87171",
                       "closed_won":"#4ade80","closed_lost":"#94a3b8"}
        _VER_STAT_COLORS = {"draft":"#64748b","submitted":"#00d4aa","bafo":"#f87171","internal":"#a78bfa"}
        _neg_col   = _NEG_COLORS.get(_neg_stg, "#64748b")
        _vstat_col = _VER_STAT_COLORS.get(_ver_stat, "#64748b")
        _neg_labels = {"initial":"Initial","negotiation":"Negotiation","bafo":"BAFO",
                       "closed_won":"Closed Won","closed_lost":"Closed Lost"}
        _vstat_labels = {"draft":"Draft","submitted":"Submitted","bafo":"BAFO","internal":"Internal"}
        version_badge = (
            f'<span style="background:#7b61ff22;color:#7b61ff;border:1px solid #7b61ff55;'
            f'border-radius:20px;padding:2px 9px;font-size:.65rem;font-weight:700">V{_v_num}</span>'
        )
        lineage_html = (
            f'<span style="background:#7b61ff11;color:#a78bfa;border:1px solid #7b61ff33;'
            f'border-radius:20px;padding:2px 8px;font-size:.65rem">↳ #{parent_id}</span>'
            if parent_id else ""
        )
        neg_stage_badge = (
            f'<span style="background:{_neg_col}18;color:{_neg_col};border:1px solid {_neg_col}44;'
            f'border-radius:20px;padding:2px 8px;font-size:.65rem">{_neg_labels.get(_neg_stg,_neg_stg)}</span>'
        ) if _neg_stg and _neg_stg != "initial" else ""
        submitted_badge = (
            f'<span style="background:{_vstat_col}18;color:{_vstat_col};border:1px solid {_vstat_col}44;'
            f'border-radius:20px;padding:2px 8px;font-size:.65rem">{_vstat_labels.get(_ver_stat,_ver_stat)}</span>'
        ) if _ver_stat and _ver_stat != "draft" else ""
        winning_badge = (
            '<span style="background:#ffd16622;color:#ffd166;border:1px solid #ffd16655;'
            'border-radius:20px;padding:2px 8px;font-size:.65rem;font-weight:700">🏆 Winning</span>'
        ) if run.get("is_winning_version") else ""
        _OUTCOME_STYLE = {
            "won":     ("🏆 Won",    "#06d6a0", "#06d6a022"),
            "lost":    ("❌ Lost",   "#ff6b6b", "#ff6b6b22"),
            "no_bid":  ("🚫 No Bid","#94a3b8", "#94a3b822"),
            "pending": ("⏳ Open",  "#ffd166", "#ffd16622"),
        }
        _oc_label, _oc_color, _oc_bg = _OUTCOME_STYLE.get(outcome, _OUTCOME_STYLE["pending"])
        outcome_badge = (
            f'<span style="background:{_oc_bg};color:{_oc_color};border:1px solid {_oc_color}55;'
            f'border-radius:20px;padding:2px 8px;font-size:.65rem;font-weight:700">{_oc_label}</span>'
        )
        _is_in_compare = run["id"] in st.session_state.get("lib_compare_ids", [])

        with col:
            st.markdown(
                f'<div style="background:#111827;border:1px solid {c_col}44;border-radius:12px;'
                f'padding:18px 20px;margin-bottom:6px;border-left:3px solid {c_col}">'
                f'{arch_banner}'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">'
                f'  <div style="display:flex;gap:5px;flex-wrap:wrap">'
                f'    {_cat_badge(cat)} {version_badge} {rev_badge} {outcome_badge}'
                f'    {lineage_html} {neg_stage_badge} {submitted_badge} {winning_badge}'
                f'  </div>'
                f'  <div style="font-size:.7rem;color:#64748b">#{run["id"]} · {run.get("ts","")}</div>'
                f'</div>'
                f'<div style="font-size:1rem;font-weight:700;color:#e2e8f0;margin-bottom:2px">{_card_heading}</div>'
                f'{sub_html}'
                f'{author_line}'
                f'<div style="display:flex;gap:20px;margin:10px 0">'
                f'  <div style="text-align:center">'
                f'    <div style="font-size:1.1rem;font-weight:700;color:#00d4aa">{hours:,}h</div>'
                f'    <div style="font-size:.65rem;color:#64748b">HOURS</div>'
                f'  </div>'
                f'  <div style="text-align:center">'
                f'    <div style="font-size:1.1rem;font-weight:700;color:#00b4d8">${cost:,}/mo</div>'
                f'    <div style="font-size:.65rem;color:#64748b">INFRA</div>'
                f'  </div>'
                f'  <div style="text-align:center">'
                f'    <div style="font-size:.9rem">{_risk_badge(risk)}</div>'
                f'    <div style="font-size:.65rem;color:#64748b">RISK</div>'
                f'  </div>'
                f'  <div style="text-align:center">'
                f'    <div style="font-size:.75rem;color:#94a3b8">'
                f'      {three.get("optimistic","?")}–{three.get("pessimistic","?")} h</div>'
                f'    <div style="font-size:.65rem;color:#64748b">3-PT RANGE</div>'
                f'  </div>'
                f'</div>'
                f'<div style="margin-bottom:8px">{tech_pills}</div>'
                f'{rev_line}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Action buttons
            a1, a2, a3, a4, a5 = st.columns(5)
            with a1:
                st.button("✏️ Revise", key=f"lib_revise_{run['id']}", width="stretch",
                          disabled=True,
                          help="Revision temporarily disabled")
            with a2:
                if st.button("📂 Restore", key=f"lib_restore_{run['id']}", width="stretch"):
                    st.session_state["lib_pending_restore_id"] = run["id"]
                    _log_act("restore", f"Restored Run #{run['id']} ({run.get('client_name','')} — {run.get('project_type','')})", "Library")
                    st.rerun()
            with a3:
                st.download_button(
                    "📥 JSON",
                    data=_cached_run_json(run["id"]),
                    file_name=f"ECI_Run_{run['id']}_{run.get('ts','').replace(':','-').replace(' ','_')}.json",
                    mime="application/json",
                    width="stretch",
                    key=f"lib_dl_{run['id']}",
                )
            with a4:
                if run.get("is_archived", 0):
                    if st.button("📤 Unarchive", key=f"lib_unarch_{run['id']}", width="stretch"):
                        db_unarchive_run(run["id"])
                        _cached_load_runs.clear(); _cached_category_counts.clear()
                        st.rerun()
                else:
                    if st.button("🗄️ Archive", key=f"lib_arch_{run['id']}", width="stretch"):
                        db_archive_run(run["id"])
                        try:
                            db_log_activity(
                                st.session_state.get("auth_email", ""),
                                st.session_state.get("auth_user", ""),
                                "archive",
                                f"Archived Run #{run['id']} ({run.get('client_name','')} — {run.get('project_type','')})",
                                "Library",
                            )
                        except Exception:
                            pass
                        notify("run_archived", f"Run #{run['id']} archived",
                               run.get("project_type", ""), {"run_id": run["id"]})
                        _cached_load_runs.clear(); _cached_category_counts.clear()
                        st.rerun()
            with a5:
                if st.button("🗑️ Delete", key=f"lib_del_{run['id']}", width="stretch"):
                    notify("run_deleted", f"Run #{run['id']} deleted",
                           run.get("project_type", ""), {"run_id": run["id"]})
                    _db_delete_run(run["id"])
                    _cached_load_runs.clear(); _cached_category_counts.clear()
                    st.rerun()

            # Review status selector
            _rs_opts  = ["pending", "approved", "needs_changes"]
            _rs_labels = {"pending": "⏳ Pending", "approved": "✅ Approved", "needs_changes": "🔄 Needs Changes"}
            _rs_idx   = _rs_opts.index(rs) if rs in _rs_opts else 0
            rs_c1, rs_c2 = st.columns([3, 1])
            with rs_c1:
                new_status = st.selectbox(
                    "Review",
                    _rs_opts,
                    index=_rs_idx,
                    format_func=lambda s: _rs_labels.get(s, s),
                    key=f"lib_rs_{run['id']}",
                    label_visibility="collapsed",
                )
            with rs_c2:
                if new_status != rs:
                    if st.button("Apply", key=f"lib_rs_apply_{run['id']}",
                                 width="stretch", type="primary"):
                        db_set_review_status(
                            run["id"], new_status,
                            notes=f"Set to {new_status} via Run Library",
                            reviewed_by=cur_user,
                        )
                        try:
                            db_log_activity(
                                st.session_state.get("auth_email", ""),
                                cur_user,
                                f"review_{new_status}",
                                f"Run #{run['id']} ({run.get('client_name','')} — {run.get('project_type','')}) → {new_status}",
                                "Library",
                            )
                        except Exception:
                            pass
                        notify("run_reviewed",
                               f"Run #{run['id']} → {new_status}",
                               run.get("project_type", ""), {"run_id": run["id"]})
                        _cached_load_runs.clear()
                        st.rerun()

            # Compare toggle
            _cmp_ids = st.session_state.get("lib_compare_ids", [])
            _cmp_label = "☑ In Comparison" if _is_in_compare else "📊 Compare"
            if st.button(_cmp_label, key=f"lib_cmp_{run['id']}", width="stretch"):
                if _is_in_compare:
                    st.session_state["lib_compare_ids"] = [i for i in _cmp_ids if i != run["id"]]
                elif len(_cmp_ids) < 2:
                    st.session_state["lib_compare_ids"] = _cmp_ids + [run["id"]]
                    _log_act("compare", f"Added Run #{run['id']} ({run.get('client_name','')}) to comparison", "Library")
                st.rerun()

            # Outcome expander
            with st.expander("📈 Outcome", expanded=(outcome != "pending")):
                _oc_opts   = ["pending", "won", "lost", "no_bid"]
                _oc_labels = {"pending": "⏳ Open / Pending", "won": "🏆 Won", "lost": "❌ Lost", "no_bid": "🚫 No Bid"}
                oc_c1, oc_c2 = st.columns(2)
                with oc_c1:
                    new_outcome = st.selectbox(
                        "Deal status",
                        _oc_opts,
                        index=_oc_opts.index(outcome) if outcome in _oc_opts else 0,
                        format_func=lambda s: _oc_labels.get(s, s),
                        key=f"lib_oc_sel_{run['id']}",
                    )
                with oc_c2:
                    actual_h = st.number_input(
                        "Actual hours", min_value=0,
                        value=int(run.get("actual_hours") or 0),
                        step=10, key=f"lib_oc_h_{run['id']}",
                    )
                oc_c3, oc_c4 = st.columns(2)
                with oc_c3:
                    actual_c = st.number_input(
                        "Actual cost/mo ($)", min_value=0,
                        value=int(run.get("actual_cost") or 0),
                        step=100, key=f"lib_oc_c_{run['id']}",
                    )
                with oc_c4:
                    oc_notes = st.text_input(
                        "Notes", value=run.get("outcome_notes") or "",
                        key=f"lib_oc_n_{run['id']}",
                    )
                if st.button("💾 Save Outcome", key=f"lib_oc_save_{run['id']}",
                             width="stretch", type="primary"):
                    db_update_outcome(
                        run["id"], new_outcome,
                        actual_hours=actual_h or None,
                        actual_cost=actual_c or None,
                        notes=oc_notes,
                    )
                    _log_act("outcome_update",
                             f"Run #{run['id']} ({run.get('client_name','')}) → {new_outcome}"
                             + (f" · actual {actual_h}h" if actual_h else ""),
                             "Library")
                    _cached_load_runs.clear()
                    st.rerun()
                # Accuracy hint when outcome is won
                if outcome == "won" and run.get("actual_hours"):
                    _est = run.get("total_hours") or 0
                    _act = run.get("actual_hours") or 0
                    _err = round((_act - _est) / _est * 100, 1) if _est else 0
                    _err_col = "#06d6a0" if abs(_err) <= 10 else "#ffd166" if abs(_err) <= 25 else "#ff6b6b"
                    st.markdown(
                        f'<div style="font-size:.72rem;color:{_err_col};margin-top:4px">'
                        f'Estimation accuracy: {_err:+.1f}% vs actual '
                        f'({_est:,}h estimated → {_act:,}h actual)</div>',
                        unsafe_allow_html=True,
                    )

            # Version chain expander — show only when there are multiple versions
            if parent_id or run.get("version_number", 1) > 1 or run.get("is_winning_version"):
                with st.expander(f"🔗 Version History (V{_v_num})", expanded=False):
                    try:
                        with st.spinner("Loading version history…"):
                            _chain = db_get_version_chain(run["id"])
                        if len(_chain) > 1:
                            _CHAIN_REASON = {
                                "scope_reduction":"📉","scope_expansion":"📈","approach_change":"🔄",
                                "pricing_negotiation":"💰","timeline_change":"📅",
                                "team_change":"👥","client_feedback":"💬","other":"📝","":""
                            }
                            _CHAIN_STAGE = {
                                "initial":"Initial","negotiation":"Negotiation",
                                "bafo":"BAFO","closed_won":"Won","closed_lost":"Lost"
                            }
                            _chain_html = ""
                            for _vi, _vr in enumerate(_chain):
                                _is_cur   = _vr["id"] == run["id"]
                                _is_win   = _vr.get("is_winning_version")
                                _vc       = "#7b61ff" if _is_cur else "#4ade80" if _is_win else "#334155"
                                _vbg      = "#1a1040" if _is_cur else "#0a1f2e" if _is_win else "#111827"
                                _r_icon   = _CHAIN_REASON.get(_vr.get("revision_reason_type",""), "📝")
                                _stg_lbl  = _CHAIN_STAGE.get(_vr.get("negotiation_stage","initial"), "")
                                _win_star = " ⭐" if _is_win else ""
                                _cur_dot  = " ◀" if _is_cur else ""
                                _vn_label = _vr.get("version_number", _vi+1)
                                _chain_html += (
                                    f'<div style="background:{_vbg};border:1px solid {_vc}55;'
                                    f'border-left:3px solid {_vc};border-radius:8px;'
                                    f'padding:8px 12px;margin-bottom:6px">'
                                    f'  <div style="display:flex;justify-content:space-between">'
                                    f'    <span style="color:{_vc};font-weight:700;font-size:.82rem">'
                                    f'      V{_vn_label}{_win_star}{_cur_dot}</span>'
                                    f'    <span style="color:#64748b;font-size:.72rem">#{_vr["id"]} · {_vr.get("ts","")}</span>'
                                    f'  </div>'
                                    f'  <div style="font-size:.75rem;color:#94a3b8;margin-top:3px">'
                                    f'    {_r_icon} {_vr.get("revision_reason_type","").replace("_"," ").title() or "Baseline"}'
                                    + (f' · {_stg_lbl}' if _stg_lbl else "")
                                    + f'  </div>'
                                    + (
                                        f'  <div style="font-size:.7rem;color:#64748b;margin-top:2px;'
                                        f'  font-style:italic">{_vr["revision_notes"][:80]}{"…" if len(_vr.get("revision_notes",""))>80 else ""}</div>'
                                        if _vr.get("revision_notes") else ""
                                    )
                                    + f'  <div style="margin-top:6px;display:flex;gap:6px;font-size:.7rem">'
                                    + f'    <span style="color:#00d4aa">{_vr.get("total_hours",0):,}h</span>'
                                    + f'    <span style="color:#00b4d8">${_vr.get("monthly_cost",0):,}/mo</span>'
                                    + f'  </div>'
                                    + f'</div>'
                                )
                            st.markdown(_chain_html, unsafe_allow_html=True)
                            _wb1, _wb2 = st.columns(2)
                            with _wb1:
                                # Mark winning version button
                                if not run.get("is_winning_version"):
                                    if st.button(f"⭐ Mark V{_v_num} as Winning",
                                                 key=f"lib_win_{run['id']}", width="stretch"):
                                        with st.spinner("Marking as winning version…"):
                                            db_mark_winning_version(run["id"])
                                            _cached_load_runs.clear()
                                        st.rerun()
                                else:
                                    st.markdown(
                                        '<div style="text-align:center;font-size:.78rem;color:#ffd166;'
                                        'padding:6px">⭐ This is the Winning Version</div>',
                                        unsafe_allow_html=True,
                                    )
                            with _wb2:
                                # Submit to client button
                                _cur_vstat = run.get("version_status","draft")
                                if _cur_vstat != "submitted":
                                    if st.button(f"📤 Submit V{_v_num} to Client",
                                                 key=f"lib_submit_{run['id']}", width="stretch",
                                                 help="Marks this version as formally submitted to the client"):
                                        with st.spinner("Submitting to client…"):
                                            db_mark_submitted(run["id"])
                                            _log_act("version_submitted",
                                                     f"V{_v_num} of Run #{run['id']} ({run.get('client_name','')}) submitted to client",
                                                     "Library")
                                            _cached_load_runs.clear()
                                        st.rerun()
                                else:
                                    _sub_ts = run.get("submitted_at","")
                                    st.markdown(
                                        f'<div style="text-align:center;font-size:.78rem;color:#00d4aa;'
                                        f'padding:6px">📤 Submitted{(" · "+_sub_ts) if _sub_ts else ""}</div>',
                                        unsafe_allow_html=True,
                                    )
                        else:
                            st.caption("No other versions yet. Use ✏️ Revise to create V2.")
                            if st.button(f"📤 Submit V1 to Client",
                                         key=f"lib_submit_v1_{run['id']}", width="stretch"):
                                with st.spinner("Submitting to client…"):
                                    db_mark_submitted(run["id"])
                                    _log_act("version_submitted",
                                             f"V1 of Run #{run['id']} ({run.get('client_name','')}) submitted to client",
                                         "Library")
                                    _cached_load_runs.clear()
                                st.rerun()
                    except Exception:
                        st.caption("Version history unavailable.")

            st.markdown("")

    # Bottom pagination
    if total_pages > 1:
        pg1b, pg2b, pg3b = st.columns([1, 4, 1])
        with pg1b:
            if st.button("◀ Prev", key="lib_prev_b", disabled=cur_page == 0, width="stretch"):
                st.session_state["lib_page"] -= 1
                st.rerun()
        with pg2b:
            st.markdown(
                f'<div style="text-align:center;color:#94a3b8;font-size:.85rem;padding-top:8px">'
                f'Page {cur_page+1} of {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with pg3b:
            if st.button("Next ▶", key="lib_next_b", disabled=cur_page >= total_pages-1, width="stretch"):
                st.session_state["lib_page"] += 1
                st.rerun()

    st.markdown("---")

    # ── Bulk actions ───────────────────────────────────────────────────
    bulk_cols = st.columns([2, 2, 2, 2])
    with bulk_cols[0]:
        if st.button("🗑️ Delete All Runs", width="stretch", type="secondary"):
            con = sqlite3.connect(_DB_PATH)
            con.execute("DELETE FROM proposals")
            con.commit()
            con.close()
            _cached_load_runs.clear(); _cached_category_counts.clear()
            st.success("All runs deleted.")
            st.rerun()
    with bulk_cols[1]:
        if runs:
            st.download_button(
                "📦 Export Filtered",
                data=json.dumps(runs, indent=2, default=str),
                file_name=f"ECI_Filtered_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                width="stretch",
                key="lib_export_filtered",
            )
    with bulk_cols[2]:
        all_runs_export = _db_load_runs("All")
        if all_runs_export:
            st.download_button(
                "📦 Export All",
                data=json.dumps(all_runs_export, indent=2, default=str),
                file_name=f"ECI_All_Runs_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                width="stretch",
                key="lib_export_all",
            )


# ════════════════════════════════════════════════════════════════════════════
#  ADMIN INTELLIGENCE DASHBOARD  (v2 — with Activity Log)
# ════════════════════════════════════════════════════════════════════════════

@st.fragment
def tab_dashboard():
    """Admin-only home dashboard — real-time presales intelligence + user activity log."""
    import collections, csv, io as _io

    _NOW       = datetime.now()
    _TODAY     = _NOW.strftime("%Y-%m-%d")
    _WEEK_AGO  = (_NOW - timedelta(days=7)).strftime("%Y-%m-%d")
    _MONTH_AGO = (_NOW - timedelta(days=30)).strftime("%Y-%m-%d")

    # ── Styles ────────────────────────────────────────────────────────────
    st.markdown("""
<style>
@keyframes fadeUp    { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
@keyframes numPop    { 0%{ opacity:0; transform:scale(.7); } 60%{ transform:scale(1.06); } 100%{ opacity:1; transform:scale(1); } }
@keyframes alertPulse{ 0%,100%{ opacity:1; } 50%{ opacity:.6; } }
@keyframes gradShift { 0%,100%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } }
@keyframes orbFloat  { 0%,100%{ transform:translateY(0);   } 50%{ transform:translateY(-6px); } }
@keyframes scanLine  { 0%{ top:-2px; } 100%{ top:100%; } }
@keyframes dotBlink  { 0%,100%{ opacity:1; } 50%{ opacity:.3; } }
@keyframes logSlide  { from{ opacity:0; transform:translateX(-8px); } to{ opacity:1; transform:translateX(0); } }

/* ── Dashboard header banner ─────────────────────────────────────── */
.dash-banner {
  position:relative; overflow:hidden;
  background:linear-gradient(135deg,#080d1a 0%,#0a1428 50%,#090c1f 100%);
  border:1px solid #1a2540; border-radius:18px;
  padding:22px 28px 18px; margin-bottom:20px;
}
.dash-banner::before {
  content:''; position:absolute; inset:0;
  background:linear-gradient(90deg,rgba(0,212,170,.04),rgba(123,97,255,.04),rgba(0,180,216,.04));
  background-size:300% 100%; animation:gradShift 8s ease infinite;
}
.dash-banner::after {
  content:''; position:absolute; top:-2px; left:0; right:0;
  height:2px; background:linear-gradient(90deg,#00d4aa,#7b61ff,#00b4d8);
  border-radius:18px 18px 0 0;
}
.dash-title {
  font-size:1.6rem; font-weight:900; letter-spacing:-.03em;
  background:linear-gradient(135deg,#e2e8f0 0%,#94a3b8 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  line-height:1.15;
}
.dash-sub   { font-size:.76rem; color:#475569; margin-top:4px; }
.live-dot   { display:inline-block; width:7px; height:7px; border-radius:50%;
              background:#00d4aa; margin-right:5px; animation:dotBlink 2s ease-in-out infinite; }

/* ── KPI card grid (gradient-border trick) ───────────────────────── */
.kpi-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:20px; }
.kpi-card {
  background:linear-gradient(#0b1424,#0b1424) padding-box,
             linear-gradient(145deg,var(--kc) 0%,rgba(10,20,40,0) 55%) border-box;
  border:1px solid transparent; border-radius:16px;
  padding:20px 16px 16px; position:relative; overflow:hidden;
  transition:transform .2s ease,box-shadow .2s ease;
  animation:fadeUp .45s ease both;
}
.kpi-card:hover {
  transform:translateY(-5px);
  box-shadow:0 16px 48px rgba(0,0,0,.4),0 0 0 1px var(--kc) inset;
}
.kpi-card::after {
  content:''; position:absolute; top:-60px; right:-60px;
  width:160px; height:160px; border-radius:50%;
  background:radial-gradient(circle,var(--kc) 0%,transparent 70%);
  opacity:.05; pointer-events:none;
}
.kpi-orb {
  position:absolute; bottom:-24px; left:-24px;
  width:90px; height:90px; border-radius:50%;
  background:radial-gradient(circle,var(--kc) 0%,transparent 70%);
  opacity:.08; pointer-events:none; animation:orbFloat 4s ease-in-out infinite;
}
.kpi-icon { font-size:1.35rem; margin-bottom:9px; line-height:1; }
.kpi-val  {
  font-size:2rem; font-weight:900; color:var(--kc);
  line-height:1; letter-spacing:-.04em;
  animation:numPop .5s cubic-bezier(.34,1.56,.64,1) both;
}
.kpi-lbl  { font-size:.65rem; color:#475569; text-transform:uppercase; letter-spacing:.14em; margin-top:6px; }
.kpi-sub  { font-size:.72rem; color:#64748b; margin-top:6px; line-height:1.45; }
.kpi-badge {
  display:inline-block; padding:2px 9px; border-radius:20px;
  font-size:.6rem; font-weight:700; margin-top:8px;
  background:rgba(0,212,170,.1); color:#00d4aa; letter-spacing:.04em;
}
.kpi-badge.warn   { background:rgba(255,209,102,.1); color:#ffd166; }
.kpi-badge.danger { background:rgba(248,113,113,.1); color:#f87171; }
.kpi-badge.purple { background:rgba(123,97,255,.1);  color:#7b61ff; }
.kpi-badge.cyan   { background:rgba(0,180,216,.1);   color:#00b4d8; }
.kpi-spark { margin-top:10px; }

/* ── Alert strip ─────────────────────────────────────────────────── */
.alert-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
.alert-card {
  border-radius:14px; padding:16px 18px; border:1px solid;
  display:flex; align-items:center; gap:14px; position:relative; overflow:hidden;
}
.alert-card::before {
  content:''; position:absolute; inset:0;
  background:linear-gradient(135deg,var(--ac) 0%,transparent 60%);
  opacity:.04; pointer-events:none;
}
.alert-card.red   { background:rgba(248,113,113,.06); border-color:rgba(248,113,113,.25); --ac:#f87171; animation:alertPulse 2.6s ease-in-out infinite; }
.alert-card.amber { background:rgba(255,209,102,.06); border-color:rgba(255,209,102,.25); --ac:#ffd166; animation:alertPulse 3s ease-in-out infinite; }
.alert-card.blue  { background:rgba(0,180,216,.06);   border-color:rgba(0,180,216,.22);   --ac:#00b4d8; }
.alert-card.teal  { background:rgba(0,212,170,.06);   border-color:rgba(0,212,170,.22);   --ac:#00d4aa; }
.alert-icon  { font-size:1.8rem; line-height:1; flex-shrink:0; }
.alert-count { font-size:1.6rem; font-weight:900; color:#e2e8f0; line-height:1.1; }
.alert-title { font-size:.71rem; color:#94a3b8; margin-top:3px; }

/* ── Section divider ─────────────────────────────────────────────── */
.dash-sec {
  font-size:.67rem; font-weight:800; text-transform:uppercase; letter-spacing:.16em;
  color:#334155; padding:18px 0 9px; border-bottom:1px solid #1a2540; margin-bottom:14px;
  display:flex; align-items:center; gap:8px;
}

/* ── Proposal feed cards ─────────────────────────────────────────── */
.pfd-card {
  background:#0b1424; border:1px solid #1a2540; border-radius:12px;
  padding:12px 15px; display:flex; align-items:center; gap:13px;
  margin-bottom:7px; transition:all .18s; position:relative; overflow:hidden;
}
.pfd-card:hover { background:#0f1929; border-color:#243050; transform:translateX(3px); }
.pfd-card::before {
  content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:var(--avc); border-radius:2px 0 0 2px;
}
.pfd-av {
  width:36px; height:36px; border-radius:50%; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-size:.68rem; font-weight:800; color:#0a0e1a; background:var(--avc);
}
.pfd-body { flex:1; min-width:0; }
.pfd-name { font-size:.82rem; font-weight:700; color:#e2e8f0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pfd-meta { font-size:.68rem; color:#64748b; margin-top:2px; }
.pfd-badge {
  padding:2px 9px; border-radius:20px; font-size:.6rem; font-weight:700;
  white-space:nowrap; flex-shrink:0; letter-spacing:.04em;
}
.pfd-badge.approved      { background:rgba(74,222,128,.12);  color:#4ade80; }
.pfd-badge.pending       { background:rgba(255,209,102,.12); color:#ffd166; }
.pfd-badge.needs_changes { background:rgba(248,113,113,.12); color:#f87171; }
.pfd-hrs { font-size:.7rem; color:#64748b; min-width:46px; text-align:right; flex-shrink:0; }

/* ── Leaderboard ─────────────────────────────────────────────────── */
.lb-row {
  display:flex; align-items:center; gap:10px; padding:11px 14px;
  background:#0b1424; border:1px solid #1a2540; border-radius:12px;
  margin-bottom:6px; transition:all .18s;
}
.lb-row:hover { background:#0f1929; transform:translateX(3px); border-color:#243050; }
.lb-rank { font-size:.85rem; font-weight:800; color:#475569; min-width:26px; }
.lb-info { flex:1; min-width:0; }
.lb-name { font-size:.82rem; font-weight:700; color:#e2e8f0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lb-bar  { height:3px; border-radius:2px; background:linear-gradient(90deg,#00d4aa,#7b61ff); margin-top:5px; max-width:100%; }
.lb-cnt  { font-size:.85rem; font-weight:800; color:#00d4aa; min-width:28px; text-align:right; }
.lb-wr   { font-size:.67rem; color:#64748b; min-width:55px; text-align:right; }

/* ── Technology pills ────────────────────────────────────────────── */
.tech-pill {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:20px; margin:3px;
  background:rgba(0,212,170,.06); border:1px solid rgba(0,212,170,.14);
  transition:all .2s; cursor:default;
}
.tech-pill:hover { background:rgba(0,212,170,.14); transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,212,170,.12); }

/* ── Activity log stats row ──────────────────────────────────────── */
.log-stats {
  display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:18px;
}
.log-stat {
  background:linear-gradient(#0b1424,#0b1424) padding-box,
             linear-gradient(145deg,var(--sc) 0%,rgba(10,20,40,0) 60%) border-box;
  border:1px solid transparent; border-radius:14px; padding:16px; position:relative; overflow:hidden;
}
.log-stat::after {
  content:''; position:absolute; top:-30px; right:-30px; width:80px; height:80px; border-radius:50%;
  background:radial-gradient(circle,var(--sc),transparent 70%); opacity:.06; pointer-events:none;
}
.log-stat-val  { font-size:1.7rem; font-weight:900; color:var(--sc); line-height:1; animation:numPop .5s cubic-bezier(.34,1.56,.64,1) both; }
.log-stat-lbl  { font-size:.66rem; color:#475569; text-transform:uppercase; letter-spacing:.12em; margin-top:5px; }
.log-stat-sub  { font-size:.7rem; color:#64748b; margin-top:4px; }

/* ── Activity timeline ───────────────────────────────────────────── */
.log-timeline  { display:flex; flex-direction:column; gap:0; }
.log-entry     { display:flex; align-items:flex-start; gap:0; animation:logSlide .3s ease both; }
.log-line-wrap { display:flex; flex-direction:column; align-items:center; width:32px; flex-shrink:0; }
.log-dot       { width:12px; height:12px; border-radius:50%; flex-shrink:0; margin-top:16px;
                 border:2px solid var(--lc); background:#060d1a;
                 box-shadow:0 0 8px var(--lc); }
.log-vline     { width:2px; flex:1; min-height:18px; opacity:.25;
                 background:linear-gradient(to bottom,var(--lc),rgba(26,37,64,0)); }
.log-body {
  flex:1; background:#0b1424; border:1px solid #1a2540; border-radius:12px;
  padding:12px 15px; margin:6px 0 4px 10px; transition:all .18s;
}
.log-body:hover { background:#0f1929; border-color:#243050; }
.log-head  { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.log-av    { width:28px; height:28px; border-radius:50%; flex-shrink:0;
             display:flex; align-items:center; justify-content:center;
             font-size:.6rem; font-weight:800; color:#0a0e1a; background:var(--lc); }
.log-user  { font-size:.78rem; font-weight:700; color:#e2e8f0; }
.log-act   { padding:2px 8px; border-radius:10px; font-size:.6rem; font-weight:700; letter-spacing:.04em; color:var(--lc); }
.log-time  { font-size:.67rem; color:#475569; margin-left:auto; white-space:nowrap; }
.log-detail{ font-size:.73rem; color:#94a3b8; margin-top:6px; line-height:1.5; }
.log-module{ display:inline-block; font-size:.58rem; color:#334155; margin-top:4px;
             letter-spacing:.07em; text-transform:uppercase;
             padding:1px 7px; border-radius:8px; background:#0f1929; border:1px solid #1a2540; }
.log-scroll { max-height:580px; overflow-y:auto; padding-right:4px; }
.log-scroll::-webkit-scrollbar       { width:4px; }
.log-scroll::-webkit-scrollbar-track { background:transparent; }
.log-scroll::-webkit-scrollbar-thumb { background:#1a2540; border-radius:4px; }
.log-scroll::-webkit-scrollbar-thumb:hover { background:#243050; }

/* ── Pulse / live-feed cards ─────────────────────────────────────── */
.pulse-feed { display:flex; flex-direction:column; gap:8px; }
.pulse-card {
  background:#0b1424; border:1px solid #1a2540; border-radius:12px;
  padding:11px 15px; display:flex; align-items:center; gap:12px;
  transition:all .2s; position:relative; overflow:hidden;
  animation:logSlide .3s ease both;
}
.pulse-card:hover { background:#0f1929; transform:translateX(3px); border-color:#243050; }
.pulse-card::before {
  content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:var(--pc); border-radius:2px 0 0 2px;
}
.pulse-icon { font-size:1.3rem; flex-shrink:0; }
.pulse-body { flex:1; min-width:0; }
.pulse-who  { font-size:.78rem; font-weight:700; color:#e2e8f0; }
.pulse-what { font-size:.68rem; color:#64748b; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pulse-ts   { font-size:.63rem; color:#334155; flex-shrink:0; }
.pulse-badge{ padding:2px 8px; border-radius:10px; font-size:.6rem; font-weight:700;
              background:rgba(from var(--pc) r g b / .1); color:var(--pc); flex-shrink:0; }

/* ── Feature usage bar ───────────────────────────────────────────── */
.feat-row   { display:flex; align-items:center; gap:10px; padding:8px 0; border-bottom:1px solid #1a2540; }
.feat-row:last-child { border-bottom:none; }
.feat-icon  { font-size:1.1rem; width:26px; text-align:center; flex-shrink:0; }
.feat-lbl   { font-size:.75rem; color:#94a3b8; flex:1; }
.feat-bar-wrap { width:120px; height:6px; background:#1a2540; border-radius:4px; overflow:hidden; flex-shrink:0; }
.feat-bar   { height:6px; border-radius:4px; background:linear-gradient(90deg,var(--fc),var(--fc2,var(--fc))); }
.feat-cnt   { font-size:.75rem; font-weight:700; color:var(--fc); min-width:32px; text-align:right; flex-shrink:0; }

/* ── Client heatmap grid ─────────────────────────────────────────── */
.client-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.client-row  { background:#0b1424; border:1px solid #1a2540; border-radius:10px; padding:10px 14px;
               display:flex; align-items:center; gap:10px; transition:all .18s; }
.client-row:hover { background:#0f1929; border-color:#243050; }
.client-name { font-size:.78rem; font-weight:700; color:#e2e8f0; flex:1; min-width:0;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.client-cnt  { font-size:.85rem; font-weight:800; color:#00d4aa; min-width:24px; text-align:right; }
.client-bar  { width:100%; height:3px; border-radius:2px; background:linear-gradient(90deg,#00d4aa,#7b61ff);
               margin-top:5px; }

/* ── Hour heatmap ────────────────────────────────────────────────── */
.hour-hm-wrap { display:flex; gap:3px; align-items:flex-end; flex-wrap:wrap; }
.hour-cell    { width:22px; height:22px; border-radius:4px; cursor:default;
                transition:transform .15s; display:flex; align-items:center; justify-content:center;
                font-size:.5rem; color:transparent; }
.hour-cell:hover { transform:scale(1.35); color:#e2e8f0; }

/* ── User session pill ───────────────────────────────────────────── */
.session-sep {
  display:flex; align-items:center; gap:10px; margin:14px 0 8px;
  padding:7px 13px; background:#080d1a; border-radius:8px; border:1px solid #1a2540;
}
.session-av  { width:26px; height:26px; border-radius:50%;
               display:flex; align-items:center; justify-content:center;
               font-size:.58rem; font-weight:800; color:#0a0e1a; background:var(--sac); flex-shrink:0; }
.session-name{ font-size:.75rem; font-weight:700; color:#e2e8f0; }
.session-meta{ font-size:.65rem; color:#475569; margin-left:auto; }
.session-dur { font-size:.65rem; color:#64748b; }
</style>
""", unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────
    all_runs   = _cached_load_runs("All", False)
    _acts      = _cached_activity_log(600)
    _N         = len(all_runs)

    # ── KPI computation ───────────────────────────────────────────────────
    _pend   = [r for r in all_runs if (r.get("review_status") or "pending") == "pending"]
    _needs  = [r for r in all_runs if (r.get("review_status") or "") == "needs_changes"]
    _approv = [r for r in all_runs if (r.get("review_status") or "") == "approved"]
    _won    = [r for r in all_runs if r.get("project_outcome") == "won"]
    _lost   = [r for r in all_runs if r.get("project_outcome") == "lost"]
    _nobid  = [r for r in all_runs if r.get("project_outcome") == "no_bid"]
    _open   = [r for r in all_runs if r.get("project_outcome") in (None, "", "pending")]
    _decided  = len(_won) + len(_lost)
    _win_rate = round(len(_won) / _decided * 100, 1) if _decided else None
    _acc_runs = [r for r in all_runs if r.get("actual_hours") and r.get("total_hours")]
    if _acc_runs:
        _errs    = [abs((r["actual_hours"] - r["total_hours"]) / r["total_hours"]) * 100 for r in _acc_runs]
        _avg_acc = round(100 - sum(_errs) / len(_errs), 1)
    else:
        _avg_acc = None
    _this_week  = [r for r in all_runs if (r.get("ts") or "")[:10] >= _WEEK_AGO]
    _this_month = [r for r in all_runs if (r.get("ts") or "")[:10] >= _MONTH_AGO]
    _pipe_val   = sum(r.get("monthly_cost", 0) or 0 for r in all_runs)
    _overdue    = [r for r in _pend if (r.get("ts") or "")[:10] < _WEEK_AGO]

    # ── Animated gradient header banner ───────────────────────────────────
    _ai_live = bool(st.session_state.get("azure_api_key") or st.session_state.get("anthropic_api_key"))
    _acts_today = [a for a in _acts if (a.get("ts") or "").startswith(_TODAY)]
    _users_today_set = set(a.get("user_email", "") for a in _acts_today if a.get("user_email"))

    _hdr_c, _ref_c = st.columns([8, 2])
    with _hdr_c:
        st.markdown(
            f'<div class="dash-banner">'
            f'<div style="display:flex;align-items:center;gap:12px">'
            f'<div class="dash-title">Intelligence Dashboard</div>'
            f'<span style="font-size:.68rem;padding:3px 10px;border-radius:20px;'
            f'background:{"rgba(0,212,170,.1)" if _ai_live else "rgba(248,113,113,.1)"};'
            f'color:{"#00d4aa" if _ai_live else "#f87171"};font-weight:700;letter-spacing:.05em">'
            f'{"● AI LIVE" if _ai_live else "● AI OFFLINE"}</span></div>'
            f'<div class="dash-sub">'
            f'ECI Presale Intelligence &nbsp;·&nbsp; {_N} active proposals &nbsp;·&nbsp; '
            f'{len(_acts_today)} events today &nbsp;·&nbsp; '
            f'{len(_users_today_set)} user{"s" if len(_users_today_set) != 1 else ""} active &nbsp;·&nbsp; '
            f'{_NOW.strftime("%a, %b %d %Y · %H:%M")}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with _ref_c:
        if st.button("↻  Refresh", key="dash_refresh_btn", width="stretch", type="secondary"):
            _cached_load_runs.clear()
            _cached_category_counts.clear()
            _cached_activity_log.clear()
            st.rerun()

    # ── Sub-tabs: Overview | Activity Log ─────────────────────────────────
    _dtab_ov, _dtab_log = st.tabs(["📊  Overview", "👁️  Activity Log"])

    # ── Shared action metadata (used in both tabs) ────────────────────────
    _ACT_META = {
        "login":                ("Sign In",        "#00d4aa", "🔐"),
        "pipeline_run":         ("Estimation",     "#7b61ff", "⚡"),
        "bella_chat":           ("BELLA Chat",     "#ffd166", "🤖"),
        "tab_view":             ("Feature Opened", "#64748b", "👁️"),
        "export_pdf":           ("PDF Export",     "#00b4d8", "📄"),
        "export_pptx":          ("PPTX Export",    "#00b4d8", "📑"),
        "export_excel":         ("Excel Export",   "#4ade80", "📊"),
        "export_json":          ("JSON Export",    "#94a3b8", "📥"),
        "review_approved":      ("Approved",       "#4ade80", "✅"),
        "review_needs_changes": ("Needs Changes",  "#f87171", "✏️"),
        "review_pending":       ("Reset Review",   "#ffd166", "🔄"),
        "archive":              ("Archived",       "#94a3b8", "🗄️"),
        "restore":              ("Restored",       "#a78bfa", "↩️"),
        "compare":              ("Compare",        "#00b4d8", "📊"),
        "outcome_update":       ("Outcome Logged", "#4ade80", "🏆"),
        "discovery_run":        ("Discovery Run",  "#fb923c", "🔍"),
    }

    def _act_meta(action):
        for _k, _v in _ACT_META.items():
            if _k in (action or ""):
                return _v
        return ((action or "event").replace("_", " ").title(), "#64748b", "•")

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 1 — OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════
    with _dtab_ov:

        # ── Needs Attention ───────────────────────────────────────────────
        if _overdue or _needs or _pend:
            st.markdown('<div class="dash-sec">⚠️ Needs Attention</div>', unsafe_allow_html=True)

            def _ac(cls, icon, cnt, lbl):
                return (
                    f'<div class="alert-card {cls}">'
                    f'<div class="alert-icon">{icon}</div>'
                    f'<div><div class="alert-count">{cnt if cnt else "✓"}</div>'
                    f'<div class="alert-title">{lbl}</div></div>'
                    f'</div>'
                )

            st.markdown(
                f'<div class="alert-grid">'
                + _ac("red" if _overdue else "teal",   "🕐", len(_overdue),    "Overdue reviews >7 days")
                + _ac("amber" if _pend else "teal",    "📋", len(_pend),        "Awaiting review")
                + _ac("red" if _needs else "teal",     "✏️", len(_needs),       "Needs changes")
                + _ac("blue",                           "🚀", len(_this_week),   "New this week")
                + '</div>',
                unsafe_allow_html=True,
            )

        # ── My Pending Reviews panel ──────────────────────────────────────
        _me       = st.session_state.get("auth_email", "")
        _me_name  = st.session_state.get("auth_user", "")
        _my_pend  = [r for r in all_runs if (r.get("review_status") or "pending") in ("pending", "needs_changes")]
        _my_won   = [r for r in all_runs if r.get("project_outcome") == "won"
                     and (r.get("created_by_email","").lower() == _me.lower() or not _me)]
        _my_lost  = [r for r in all_runs if r.get("project_outcome") == "lost"
                     and (r.get("created_by_email","").lower() == _me.lower() or not _me)]
        _my_total_dec = len(_my_won) + len(_my_lost)
        _my_wr    = round(len(_my_won) / _my_total_dec * 100, 1) if _my_total_dec else None

        _wr_c2    = "#4ade80" if (_my_wr or 0) >= 60 else "#ffd166" if (_my_wr or 0) >= 40 else "#f87171"

        # Personal win rate bar
        st.markdown(
            f'<div style="display:flex;align-items:stretch;gap:14px;margin-bottom:18px">'

            # My Win Rate card
            f'<div style="background:linear-gradient(#0b1424,#0b1424) padding-box,'
            f'linear-gradient(145deg,{_wr_c2},rgba(10,20,40,0) 60%) border-box;'
            f'border:1px solid transparent;border-radius:16px;padding:18px 22px;min-width:200px">'
            f'<div style="font-size:.62rem;color:#475569;text-transform:uppercase;letter-spacing:.12em;margin-bottom:6px">My Win Rate</div>'
            f'<div style="font-size:2.2rem;font-weight:900;color:{_wr_c2};line-height:1">'
            f'{"—" if _my_wr is None else f"{_my_wr}%"}</div>'
            f'<div style="font-size:.7rem;color:#64748b;margin-top:5px">'
            f'{len(_my_won)}W · {len(_my_lost)}L · {_my_total_dec} decided</div>'
            f'<div style="margin-top:10px;height:4px;background:#1a2540;border-radius:4px;overflow:hidden">'
            f'<div style="height:4px;width:{min(_my_wr or 0,100):.0f}%;background:{_wr_c2};border-radius:4px;transition:width .8s ease"></div>'
            f'</div></div>'

            # Pending reviews list
            f'<div style="flex:1;background:#080d1a;border:1px solid #1a2540;border-radius:16px;padding:18px 22px;overflow:hidden">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">'
            f'<span style="font-size:.62rem;color:#475569;text-transform:uppercase;letter-spacing:.12em">Pending Reviews ({len(_my_pend)})</span>'
            f'<span style="font-size:.62rem;color:#334155">'
            + (f'<span style="color:#f87171;font-weight:700">{len(_overdue)} overdue</span>' if _overdue else
               '<span style="color:#4ade80">All current ✓</span>')
            + f'</span></div>'
            + (
                "".join(
                    f'<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;'
                    f'background:#0b1424;border:1px solid #1a2540;border-radius:10px;margin-bottom:6px">'
                    f'<div style="width:8px;height:8px;border-radius:50%;flex-shrink:0;background:'
                    f'{"#f87171" if (r.get("ts") or "")[:10] < _WEEK_AGO else "#ffd166"}'
                    f';box-shadow:0 0 6px {"#f87171" if (r.get("ts") or "")[:10] < _WEEK_AGO else "#ffd166"}"></div>'
                    f'<div style="flex:1;min-width:0">'
                    f'<div style="font-size:.78rem;font-weight:700;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                    f'{r.get("client_name") or "Unnamed"} — {r.get("project_type") or "General"}</div>'
                    f'<div style="font-size:.66rem;color:#64748b;margin-top:1px">'
                    f'{(r.get("ts") or "")[:10]} · '
                    f'{r.get("total_hours",0):,}h · '
                    + (f'<span style="color:#f87171">Needs Changes</span>' if r.get("review_status") == "needs_changes" else '<span style="color:#ffd166">Awaiting Review</span>')
                    + f'</div></div>'
                    f'<span style="font-size:.62rem;color:#64748b;white-space:nowrap">#{r["id"]}</span>'
                    f'</div>'
                    for r in _my_pend[:5]
                )
                if _my_pend else
                '<div style="text-align:center;padding:20px;color:#334155;font-size:.8rem">🎉 All caught up — no pending reviews</div>'
            )
            + (f'<div style="font-size:.65rem;color:#334155;margin-top:6px;text-align:center">+{len(_my_pend)-5} more — go to Run Library</div>' if len(_my_pend) > 5 else "")
            + f'</div></div>',
            unsafe_allow_html=True,
        )

        # ── KPI Cards ─────────────────────────────────────────────────────
        st.markdown('<div class="dash-sec">📊 Key Performance Indicators</div>', unsafe_allow_html=True)

        def _spark(values, color, w=64, h=22):
            if not values or max(values) == 0:
                return ""
            _mx = max(values) or 1
            pts = " ".join(
                f'{round(i * w / max(len(values)-1,1))},{round(h - v/_mx*h)}'
                for i, v in enumerate(values)
            )
            return (
                f'<div class="kpi-spark">'
                f'<svg width="{w}" height="{h}" style="display:block">'
                f'<defs><linearGradient id="sg{abs(hash(color))%999}" x1="0" y1="0" x2="1" y2="0">'
                f'<stop offset="0" stop-color="{color}" stop-opacity=".3"/>'
                f'<stop offset="1" stop-color="{color}"/></linearGradient></defs>'
                f'<polyline points="{pts}" fill="none" stroke="url(#sg{abs(hash(color))%999})" '
                f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                f'</svg></div>'
            )

        # Build 6-month counts for sparklines
        _mo6   = [(_NOW - timedelta(days=30*i)).strftime("%Y-%m") for i in range(5,-1,-1)]
        _mo_c  = collections.defaultdict(int)
        _mo_w  = collections.defaultdict(int)
        for _r in all_runs:
            _mo = (_r.get("ts") or "")[:7]
            if _mo: _mo_c[_mo] += 1
            if _mo and _r.get("project_outcome") == "won": _mo_w[_mo] += 1
        _spark_all = [_mo_c.get(m,0) for m in _mo6]
        _spark_win = [_mo_w.get(m,0) for m in _mo6]

        def _kpi(icon, val, lbl, sub, color, badge=None, bcls="", spark=None):
            _b = f'<span class="kpi-badge {bcls}">{badge}</span>' if badge else ""
            _s = spark or ""
            return (
                f'<div class="kpi-card" style="--kc:{color}">'
                f'<div class="kpi-orb"></div>'
                f'<div class="kpi-icon">{icon}</div>'
                f'<div class="kpi-val">{val}</div>'
                f'<div class="kpi-lbl">{lbl}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'{_b}{_s}</div>'
            )

        _wr_c  = "#4ade80" if (_win_rate or 0) >= 60 else "#ffd166" if (_win_rate or 0) >= 40 else "#f87171"
        _ac_c  = "#4ade80" if (_avg_acc  or 0) >= 85 else "#7b61ff" if (_avg_acc  or 0) >= 70 else "#ffd166"

        st.markdown(
            f'<div class="kpi-grid">'
            + _kpi("📁", _N, "Active Proposals",
                   f"{len(_this_month)} this month · {len(_this_week)} this week",
                   "#00d4aa", f"+{len(_this_week)} new", "",
                   _spark(_spark_all, "#00d4aa"))
            + _kpi("🏆", f"{_win_rate}%" if _win_rate is not None else "—", "Win Rate",
                   f"{len(_won)} won · {len(_lost)} lost of {_decided} decided",
                   _wr_c, "On Track" if (_win_rate or 0) >= 60 else "Needs Work",
                   "" if (_win_rate or 0) >= 60 else "warn",
                   _spark(_spark_win, _wr_c))
            + _kpi("🎯", f"{_avg_acc}%" if _avg_acc is not None else "—", "Estimation Accuracy",
                   f"{len(_acc_runs)} validated against actuals",
                   _ac_c, f"{len(_acc_runs)} actuals" if _acc_runs else "No actuals yet",
                   "purple" if _avg_acc else "warn")
            + _kpi("⏳", len(_pend), "Pending Reviews",
                   f"{len(_needs)} need changes · {len(_approv)} approved",
                   "#f87171" if _overdue else "#ffd166" if _pend else "#4ade80",
                   f"{len(_overdue)} overdue!" if _overdue else "All recent",
                   "danger" if _overdue else "warn" if _pend else "")
            + _kpi("💰", f"${_pipe_val:,.0f}" if _pipe_val else "—", "Monthly Pipeline",
                   f"Annualised: ${_pipe_val*12/1_000:,.0f}K" if _pipe_val else "No cost data yet",
                   "#00b4d8", f"Across {_N} proposals", "cyan")
            + '</div>',
            unsafe_allow_html=True,
        )

        # ── Charts ────────────────────────────────────────────────────────
        _PL = dict(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#64748b", size=11),
            margin=dict(l=8, r=8, t=38, b=8),
        )

        st.markdown('<div class="dash-sec">📈 Pipeline Analytics</div>', unsafe_allow_html=True)
        _c1, _c2 = st.columns([3, 2])

        with _c1:
            _xlabels = [m[-5:].replace("-", "/") for m in _mo6]
            _ycnt    = _spark_all
            _ywin    = _spark_win
            _fig_t   = go.Figure()
            _fig_t.add_trace(go.Scatter(
                x=_xlabels, y=_ycnt, fill="tozeroy", mode="lines+markers", name="Proposals",
                line=dict(color="#00d4aa", width=2.5),
                marker=dict(size=7, color="#00d4aa", line=dict(color="#0a0e1a", width=2)),
                fillcolor="rgba(0,212,170,.09)",
            ))
            _fig_t.add_trace(go.Scatter(
                x=_xlabels, y=_ywin, mode="lines+markers", name="Won",
                line=dict(color="#4ade80", width=2, dash="dot"),
                marker=dict(size=5, color="#4ade80"),
            ))
            _fig_t.update_layout(
                **_PL,
                title=dict(text="Proposals & Wins — Last 6 Months", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#64748b"),
                yaxis=dict(showgrid=True, gridcolor="#1a2540", color="#64748b", zeroline=False),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8", size=10)),
                height=248,
            )
            st.plotly_chart(_fig_t, width="stretch", config={"displayModeBar": False})

        with _c2:
            _o_lbl = ["Won", "Lost", "No Bid", "Open"]
            _o_val = [len(_won), len(_lost), len(_nobid), len(_open)]
            _o_col = ["#4ade80", "#f87171", "#94a3b8", "#7b61ff"]
            _fig_d = go.Figure(go.Pie(
                labels=_o_lbl, values=_o_val, hole=0.64,
                marker=dict(colors=_o_col, line=dict(color="#0a0e1a", width=2)),
                textinfo="label+percent", textfont=dict(color="#94a3b8", size=10.5),
                hovertemplate="%{label}: <b>%{value}</b><extra></extra>",
            ))
            _fig_d.add_annotation(
                text=f"<b>{_win_rate}%</b><br>Win" if _win_rate else "—",
                font=dict(size=14, color="#e2e8f0"), showarrow=False,
            )
            _fig_d.update_layout(**_PL,
                title=dict(text="Outcome Distribution", font=dict(size=12, color="#94a3b8")),
                showlegend=False, height=248)
            st.plotly_chart(_fig_d, width="stretch", config={"displayModeBar": False})

        _c3, _c4, _c5 = st.columns(3)
        _cats  = collections.Counter(r.get("category", "General") for r in all_runs)
        _risks = collections.Counter(r.get("risk_level") or "Unknown" for r in all_runs if r.get("risk_level"))

        with _c3:
            _cat_col = {"AI": "#7b61ff", "Data": "#00d4aa", "Cloud": "#00b4d8", "General": "#94a3b8"}
            _cl = list(_cats.keys()); _cv = list(_cats.values())
            _fig_c = go.Figure(go.Bar(
                y=_cl, x=_cv, orientation="h",
                marker=dict(color=[_cat_col.get(c, "#64748b") for c in _cl], line=dict(color="rgba(0,0,0,0)")),
                text=_cv, textposition="outside", textfont=dict(color="#94a3b8", size=11),
            ))
            _fig_c.update_layout(**_PL, title=dict(text="By Category", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, color="#94a3b8"), height=210)
            st.plotly_chart(_fig_c, width="stretch", config={"displayModeBar": False})

        with _c4:
            _r_ord = ["Low","Medium","High","Critical"]
            _r_col = {"Low":"#4ade80","Medium":"#ffd166","High":"#f87171","Critical":"#dc2626"}
            _rl = [r for r in _r_ord if r in _risks]; _rv = [_risks[r] for r in _rl]
            _fig_r = go.Figure(go.Bar(
                x=_rl, y=_rv,
                marker=dict(color=[_r_col[r] for r in _rl], line=dict(color="rgba(0,0,0,0)")),
                text=_rv, textposition="outside", textfont=dict(color="#94a3b8", size=11),
            ))
            _fig_r.update_layout(**_PL, title=dict(text="Risk Distribution", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#94a3b8"),
                yaxis=dict(showgrid=True, gridcolor="#1a2540", showticklabels=False, zeroline=False), height=210)
            st.plotly_chart(_fig_r, width="stretch", config={"displayModeBar": False})

        with _c5:
            _rv_lbl = ["Approved","Pending","Needs Changes"]
            _rv_val = [len(_approv), len(_pend), len(_needs)]
            _rv_col = ["#4ade80","#ffd166","#f87171"]
            _fig_rv = go.Figure(go.Bar(
                y=_rv_lbl, x=_rv_val, orientation="h",
                marker=dict(color=_rv_col, line=dict(color="rgba(0,0,0,0)")),
                text=_rv_val, textposition="outside", textfont=dict(color="#94a3b8", size=11),
            ))
            _fig_rv.update_layout(**_PL, title=dict(text="Review Pipeline", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, color="#94a3b8"), height=210)
            st.plotly_chart(_fig_rv, width="stretch", config={"displayModeBar": False})

        # ── Activity Heatmap — GitHub-style calendar ───────────────────────
        st.markdown('<div class="dash-sec">📅 Proposal Activity — Last 12 Weeks</div>', unsafe_allow_html=True)
        try:
            from datetime import date as _date
            _hm_today = _date.today()
            _hm_start = _hm_today - timedelta(days=83)   # ~12 weeks
            _hm_cnt: dict = {}
            for _r in all_runs:
                _d = (_r.get("ts") or "")[:10]
                if _d: _hm_cnt[_d] = _hm_cnt.get(_d, 0) + 1
            _hm_max   = max(_hm_cnt.values()) if _hm_cnt else 1
            _hm_weeks = []
            _cur = _hm_start - timedelta(days=_hm_start.weekday())  # start on Monday
            while _cur <= _hm_today:
                week_col = []
                for _dow in range(7):
                    _day = _cur + timedelta(days=_dow)
                    _ds  = str(_day)
                    _cnt = _hm_cnt.get(_ds, 0)
                    _int = min(int(_cnt / _hm_max * 4), 4) if _cnt else 0
                    week_col.append((_ds, _cnt, _int))
                _hm_weeks.append(week_col)
                _cur += timedelta(days=7)
            _HEAT_COLS = ["#1a2540", "#00463a", "#006a54", "#00956e", "#00d4aa"]
            _cells = []
            for _wk in _hm_weeks:
                _col_cells = []
                for _ds, _cnt, _int in _wk:
                    _col = _HEAT_COLS[_int]
                    _tip = f"{_cnt} proposal{'s' if _cnt!=1 else ''} on {_ds}" if _cnt else _ds
                    _col_cells.append(
                        f'<div title="{_tip}" style="width:13px;height:13px;border-radius:3px;'
                        f'background:{_col};margin-bottom:2px;'
                        f'{"box-shadow:0 0 6px " + _col + "80;" if _int >= 3 else ""}"></div>'
                    )
                _cells.append('<div style="display:flex;flex-direction:column;margin-right:2px">' + "".join(_col_cells) + '</div>')
            _hm_html = (
                '<div style="display:flex;align-items:flex-start;gap:0;padding:8px 0;overflow-x:auto">'
                + "".join(_cells) + '</div>'
                + f'<div style="font-size:.66rem;color:#334155;margin-top:4px">'
                f'Less &nbsp; <span style="display:inline-flex;gap:3px">'
                + "".join(f'<span style="width:10px;height:10px;border-radius:2px;display:inline-block;background:{c}"></span>' for c in _HEAT_COLS)
                + f'</span> &nbsp; More &nbsp;·&nbsp; Total: {_N} proposals</div>'
            )
            st.markdown(_hm_html, unsafe_allow_html=True)
        except Exception:
            pass

        # ── Recent Proposals + Team Leaderboard ───────────────────────────
        st.markdown('<div class="dash-sec">🔄 Recent Proposals  &  Team Leaderboard</div>', unsafe_allow_html=True)
        _fa1, _fa2 = st.columns([3, 2])
        _AV_PAL = ["#00d4aa","#7b61ff","#f87171","#ffd166","#00b4d8","#4ade80","#fb923c","#a78bfa"]

        with _fa1:
            st.markdown('<div style="font-size:.76rem;font-weight:700;color:#64748b;margin-bottom:10px;letter-spacing:.06em;text-transform:uppercase">Last 15 Proposals</div>', unsafe_allow_html=True)
            _feed_html = []
            for _fi, _r in enumerate(all_runs[:15]):
                _ar = _r.get("created_by") or _r.get("created_by_email") or "Unknown"
                _ad = _ar.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _ar else _ar
                _init = "".join(p[0].upper() for p in _ad.split()[:2])
                _avc  = _AV_PAL[_fi % len(_AV_PAL)]
                _cli  = _r.get("client_name") or "Unnamed Client"
                _pty  = _r.get("project_type") or _r.get("category") or "General"
                _st   = _r.get("review_status") or "pending"
                _hrs  = _r.get("total_hours")
                _ts   = (_r.get("ts") or "")[:10]
                try:
                    _age = (_NOW.date() - datetime.strptime(_ts, "%Y-%m-%d").date()).days
                    _ago = "Today" if _age==0 else f"{_age}d ago" if _age<30 else f"{_age//30}mo ago"
                except Exception:
                    _ago = _ts
                _feed_html.append(
                    f'<div class="pfd-card" style="--avc:{_avc}">'
                    f'<div class="pfd-av">{_init}</div>'
                    f'<div class="pfd-body">'
                    f'<div class="pfd-name">{_cli}</div>'
                    f'<div class="pfd-meta">{_pty} · {_ad} · {_ago}</div>'
                    f'</div>'
                    f'<span class="pfd-badge {_st}">{_st.replace("_"," ").title()}</span>'
                    f'<div class="pfd-hrs">{"—" if not _hrs else f"{_hrs:,}h"}</div>'
                    f'</div>'
                )
            st.markdown("".join(_feed_html) or '<div style="color:#64748b;font-size:.8rem;padding:12px">No proposals yet.</div>',
                        unsafe_allow_html=True)

        with _fa2:
            st.markdown('<div style="font-size:.76rem;font-weight:700;color:#64748b;margin-bottom:10px;letter-spacing:.06em;text-transform:uppercase">Team Leaderboard</div>', unsafe_allow_html=True)
            _team: dict = {}
            for _r in all_runs:
                _nr = _r.get("created_by") or _r.get("created_by_email") or "Unknown"
                _nm = _nr.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _nr else _nr
                _team.setdefault(_nm, {"count":0,"won":0,"decided":0})
                _team[_nm]["count"] += 1
                if _r.get("project_outcome") == "won":   _team[_nm]["won"] += 1
                if _r.get("project_outcome") in ("won","lost"): _team[_nm]["decided"] += 1
            _lb = sorted(_team.items(), key=lambda x:(-x[1]["count"],-x[1]["won"]))[:8]
            _mcnt = _lb[0][1]["count"] if _lb else 1
            for _rk, (_nm, _st) in enumerate(_lb, 1):
                _wrs  = f'{round(_st["won"]/_st["decided"]*100)}% WR' if _st["decided"] else "—"
                _barw = round(_st["count"] / _mcnt * 100)
                _med  = "🥇" if _rk==1 else "🥈" if _rk==2 else "🥉" if _rk==3 else f"#{_rk}"
                st.markdown(
                    f'<div class="lb-row"><span class="lb-rank">{_med}</span>'
                    f'<div class="lb-info">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<span class="lb-name">{_nm}</span>'
                    f'<div style="display:flex;gap:8px"><span class="lb-wr">{_wrs}</span>'
                    f'<span class="lb-cnt">{_st["count"]}</span></div></div>'
                    f'<div class="lb-bar" style="width:{_barw}%"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            if not _lb:
                st.markdown('<div style="color:#64748b;font-size:.8rem;padding:12px">No team data yet.</div>', unsafe_allow_html=True)

        # ── Technology Adoption ───────────────────────────────────────────
        st.markdown('<div class="dash-sec">🔧 Technology Adoption</div>', unsafe_allow_html=True)
        _tc: collections.Counter = collections.Counter()
        for _r in all_runs:
            for _t in (_r.get("tech_stack") or []):
                if isinstance(_t, str) and _t.strip():
                    _tc[_t.strip().title()] += 1
        if _tc:
            _top20 = _tc.most_common(20)
            _mx_tc = _top20[0][1]
            _pills = []
            for _tn, _cnt in _top20:
                _sz  = 0.73 + (_cnt / _mx_tc) * 0.62
                _col = "#00d4aa" if _cnt == _mx_tc else "#7b61ff" if _cnt >= _mx_tc*.55 else "#94a3b8"
                _op  = 0.55 + (_cnt / _mx_tc) * 0.45
                _pills.append(
                    f'<span class="tech-pill" style="opacity:{_op:.2f}">'
                    f'<span style="color:{_col};font-size:{_sz:.2f}rem;font-weight:700">{_tn}</span>'
                    f'<span style="color:#334155;font-size:.63rem">{_cnt}</span></span>'
                )
            st.markdown('<div style="line-height:2.8">' + "".join(_pills) + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#64748b;font-size:.8rem;padding:8px 0">No technology data yet.</div>', unsafe_allow_html=True)

        # ── Analytics Row 2: Activity Volume + Feature Usage ──────────────
        st.markdown('<div class="dash-sec">📡 Platform Engagement</div>', unsafe_allow_html=True)
        _eng_c1, _eng_c2 = st.columns([3, 2])

        with _eng_c1:
            # Activity volume: events per day last 30 days
            from datetime import date as _d2
            _vol_days = [(_NOW - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(29, -1, -1)]
            _vol_cnt  = collections.Counter(
                (a.get("ts") or "")[:10] for a in _acts
                if (a.get("ts") or "")[:10] >= (_NOW - timedelta(days=30)).strftime("%Y-%m-%d")
            )
            _vol_y    = [_vol_cnt.get(d, 0) for d in _vol_days]
            _vol_lbl  = [d[-5:].replace("-", "/") for d in _vol_days]
            _vol_cols = ["#7b61ff" if v == max(_vol_y or [0]) else
                         "#00d4aa" if v >= (max(_vol_y or [0]) * 0.6) else
                         "#1a2540" for v in _vol_y]
            _fig_vol = go.Figure(go.Bar(
                x=_vol_lbl, y=_vol_y,
                marker=dict(color=_vol_cols, line=dict(color="rgba(0,0,0,0)")),
                hovertemplate="%{x}: <b>%{y} events</b><extra></extra>",
            ))
            _fig_vol.update_layout(
                **_PL,
                title=dict(text="Platform Events — Last 30 Days", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#475569", tickangle=-45,
                           tickmode="array",
                           tickvals=[_vol_lbl[i] for i in range(0, 30, 5)],
                           ticktext=[_vol_lbl[i] for i in range(0, 30, 5)]),
                yaxis=dict(showgrid=True, gridcolor="#1a2540", color="#64748b", zeroline=False),
                height=240,
            )
            st.plotly_chart(_fig_vol, width="stretch", config={"displayModeBar": False})

        with _eng_c2:
            # Feature usage breakdown
            _feat_ctr = collections.Counter(a.get("action", "other") for a in _acts)
            _feat_top = _feat_ctr.most_common(8)
            _feat_max = _feat_top[0][1] if _feat_top else 1
            _f_rows   = []
            for _fa, _fc in _feat_top:
                _flbl, _fcol, _fic = _act_meta(_fa)
                _fw = round(_fc / _feat_max * 100)
                _fc2 = "#7b61ff" if _fa == "pipeline_run" else _fcol
                _f_rows.append(
                    f'<div class="feat-row">'
                    f'<span class="feat-icon">{_fic}</span>'
                    f'<span class="feat-lbl">{_flbl}</span>'
                    f'<div class="feat-bar-wrap"><div class="feat-bar" style="width:{_fw}%;--fc:{_fcol};--fc2:{_fc2}"></div></div>'
                    f'<span class="feat-cnt" style="--fc:{_fcol}">{_fc}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px">Feature Usage</div>'
                + ("".join(_f_rows) if _f_rows else
                   '<div style="color:#334155;font-size:.8rem;padding:12px">No usage data yet.</div>'),
                unsafe_allow_html=True,
            )

        # ── Analytics Row 3: Win Rate by Category + Top Clients ───────────
        st.markdown('<div class="dash-sec">🏆 Win Intelligence &  Top Clients</div>', unsafe_allow_html=True)
        _int_c1, _int_c2 = st.columns([3, 2])

        with _int_c1:
            # Win rate by category — grouped bar
            _cat_names = sorted(set(r.get("category", "General") for r in all_runs))
            _cat_won   = [sum(1 for r in all_runs if r.get("category") == c and r.get("project_outcome") == "won") for c in _cat_names]
            _cat_lost  = [sum(1 for r in all_runs if r.get("category") == c and r.get("project_outcome") == "lost") for c in _cat_names]
            _cat_open  = [sum(1 for r in all_runs if r.get("category") == c and r.get("project_outcome") not in ("won","lost","no_bid")) for c in _cat_names]
            _fig_cat   = go.Figure()
            _fig_cat.add_trace(go.Bar(name="Won",  x=_cat_names, y=_cat_won,  marker_color="#4ade80", text=_cat_won,  textposition="outside", textfont=dict(color="#94a3b8", size=10)))
            _fig_cat.add_trace(go.Bar(name="Lost", x=_cat_names, y=_cat_lost, marker_color="#f87171", text=_cat_lost, textposition="outside", textfont=dict(color="#94a3b8", size=10)))
            _fig_cat.add_trace(go.Bar(name="Open", x=_cat_names, y=_cat_open, marker_color="#475569", text=_cat_open, textposition="outside", textfont=dict(color="#94a3b8", size=10)))
            _fig_cat.update_layout(
                **_PL, barmode="group", height=230,
                title=dict(text="Win Rate by Category", font=dict(size=12, color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#94a3b8"),
                yaxis=dict(showgrid=True, gridcolor="#1a2540", zeroline=False, color="#64748b"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8", size=10), orientation="h", y=1.12),
            )
            st.plotly_chart(_fig_cat, width="stretch", config={"displayModeBar": False})

        with _int_c2:
            # Top clients by proposal count
            _client_ctr = collections.Counter(r.get("client_name", "Unnamed") or "Unnamed" for r in all_runs)
            _top_cli    = _client_ctr.most_common(8)
            _cli_max    = _top_cli[0][1] if _top_cli else 1
            _cli_rows   = []
            for _cn, _cc in _top_cli:
                _cbw = round(_cc / _cli_max * 100)
                _cli_rows.append(
                    f'<div class="client-row">'
                    f'<span class="client-name">{_cn[:28]}</span>'
                    f'<span class="client-cnt">{_cc}</span>'
                    f'<div style="position:absolute;bottom:0;left:0;right:0;height:2px;opacity:.4"><div class="client-bar" style="width:{_cbw}%"></div></div>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px">Top Clients</div>'
                + '<div style="position:relative;display:flex;flex-direction:column;gap:7px">'
                + "".join(_cli_rows) + "</div>",
                unsafe_allow_html=True,
            )

        # ── Live Pulse Feed ────────────────────────────────────────────────
        _pulse_c1, _pulse_c2 = st.columns([1, 1])

        with _pulse_c1:
            st.markdown('<div class="dash-sec">🔴 Live Activity Feed</div>', unsafe_allow_html=True)
            _live_acts = _acts[:8]
            if _live_acts:
                _pulse_cards = []
                for _i, _ev in enumerate(_live_acts):
                    _lbl, _col, _ico = _act_meta(_ev.get("action", ""))
                    _uname   = _ev.get("user_name") or _ev.get("user_email") or "System"
                    _udisp   = _uname.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _uname else _uname
                    _detail  = _ev.get("details", "") or "—"
                    _ts_str  = _ev.get("ts", "")
                    try:
                        _from_now = (datetime.now() - datetime.strptime(_ts_str, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        _ts_disp  = (f"{int(_from_now//60)}m ago" if _from_now < 3600
                                     else f"{int(_from_now//3600)}h ago" if _from_now < 86400
                                     else _ts_str[:10])
                    except Exception:
                        _ts_disp = _ts_str[11:16] if len(_ts_str) > 10 else _ts_str
                    _pulse_cards.append(
                        f'<div class="pulse-card" style="--pc:{_col};animation-delay:{_i*0.06:.2f}s">'
                        f'<span class="pulse-icon">{_ico}</span>'
                        f'<div class="pulse-body">'
                        f'<div class="pulse-who">{_udisp}</div>'
                        f'<div class="pulse-what">{_detail[:80]}</div>'
                        f'</div>'
                        f'<span class="pulse-ts">{_ts_disp}</span>'
                        f'</div>'
                    )
                st.markdown('<div class="pulse-feed">' + "".join(_pulse_cards) + '</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#334155;font-size:.8rem;padding:12px">No activity yet. Events will appear here in real-time.</div>', unsafe_allow_html=True)

        with _pulse_c2:
            st.markdown('<div class="dash-sec">👥 Team Leaderboard</div>', unsafe_allow_html=True)
            _team2: dict = {}
            for _r in all_runs:
                _nr = _r.get("created_by") or _r.get("created_by_email") or "Unknown"
                _nm = _nr.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _nr else _nr
                _team2.setdefault(_nm, {"count":0,"won":0,"decided":0})
                _team2[_nm]["count"] += 1
                if _r.get("project_outcome") == "won":   _team2[_nm]["won"] += 1
                if _r.get("project_outcome") in ("won","lost"): _team2[_nm]["decided"] += 1
            _lb2 = sorted(_team2.items(), key=lambda x:(-x[1]["count"],-x[1]["won"]))[:7]
            _mcnt2 = _lb2[0][1]["count"] if _lb2 else 1
            _AV_PAL2 = ["#00d4aa","#7b61ff","#f87171","#ffd166","#00b4d8","#4ade80","#fb923c"]
            for _rk, (_nm, _st2) in enumerate(_lb2, 1):
                _wrs2  = f'{round(_st2["won"]/_st2["decided"]*100)}% WR' if _st2["decided"] else "—"
                _barw2 = round(_st2["count"] / _mcnt2 * 100)
                _med2  = "🥇" if _rk==1 else "🥈" if _rk==2 else "🥉" if _rk==3 else f"#{_rk}"
                _av_color2 = _AV_PAL2[(_rk-1) % len(_AV_PAL2)]
                _av_init2  = "".join(p[0].upper() for p in _nm.split()[:2]) or "?"
                st.markdown(
                    f'<div class="lb-row">'
                    f'<div style="width:28px;height:28px;border-radius:50%;background:{_av_color2};'
                    f'display:flex;align-items:center;justify-content:center;font-size:.58rem;'
                    f'font-weight:800;color:#0a0e1a;flex-shrink:0">{_av_init2}</div>'
                    f'<div class="lb-info">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<span class="lb-name">{_nm}</span>'
                    f'<div style="display:flex;gap:8px"><span class="lb-wr">{_wrs2}</span>'
                    f'<span class="lb-cnt">{_st2["count"]}</span></div></div>'
                    f'<div class="lb-bar" style="width:{_barw2}%"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            if not _lb2:
                st.markdown('<div style="color:#64748b;font-size:.8rem;padding:12px">No team data yet.</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 2 — ACTIVITY LOG
    # ═══════════════════════════════════════════════════════════════════════
    with _dtab_log:

        # ── Derived analytics ─────────────────────────────────────────────
        _acts_all     = _acts
        _acts_today_  = [a for a in _acts_all if (a.get("ts") or "").startswith(_TODAY)]
        _acts_week_   = [a for a in _acts_all if (a.get("ts") or "")[:10] >= _WEEK_AGO]
        _users_unique = sorted(set(a.get("user_email","") for a in _acts_all if a.get("user_email")))
        _most_active  = collections.Counter(a.get("user_name") or a.get("user_email","?") for a in _acts_all)
        _top_user     = _most_active.most_common(1)[0][0] if _most_active else "—"
        _top_udisp    = _top_user.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _top_user else _top_user
        _login_ct     = sum(1 for a in _acts_all if a.get("action") == "login")
        _run_ct       = sum(1 for a in _acts_all if a.get("action") == "pipeline_run")
        _chat_ct      = sum(1 for a in _acts_all if a.get("action") == "bella_chat")
        _export_ct    = sum(1 for a in _acts_all if "export" in (a.get("action") or ""))
        _users_today_ct = len(set(a.get("user_email","") for a in _acts_today_))

        # ── Stats row ─────────────────────────────────────────────────────
        st.markdown(
            f'<div class="log-stats">'
            f'<div class="log-stat" style="--sc:#00d4aa">'
            f'<div class="log-stat-val">{len(_acts_today_)}</div>'
            f'<div class="log-stat-lbl">Events Today</div>'
            f'<div class="log-stat-sub">{_users_today_ct} user{"s" if _users_today_ct!=1 else ""} active · {len(_acts_week_)} this week</div></div>'
            f'<div class="log-stat" style="--sc:#7b61ff">'
            f'<div class="log-stat-val">{len(_users_unique)}</div>'
            f'<div class="log-stat-lbl">Total Users</div>'
            f'<div class="log-stat-sub">{_login_ct} logins recorded · {_run_ct} estimations</div></div>'
            f'<div class="log-stat" style="--sc:#ffd166">'
            f'<div class="log-stat-val">{_chat_ct}</div>'
            f'<div class="log-stat-lbl">BELLA Chats</div>'
            f'<div class="log-stat-sub">{_export_ct} exports generated</div></div>'
            f'<div class="log-stat" style="--sc:#4ade80">'
            f'<div class="log-stat-val" style="font-size:{"1.1" if len(_top_udisp)>8 else "1.7"}rem">{_top_udisp[:16]}</div>'
            f'<div class="log-stat-lbl">Most Active</div>'
            f'<div class="log-stat-sub">{_most_active.get(_top_user,0)} total events</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Mini analytics: Hour heatmap + Feature breakdown ──────────────
        _log_vis1, _log_vis2 = st.columns([3, 2])

        with _log_vis1:
            st.markdown(
                '<div style="font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;'
                'letter-spacing:.1em;margin-bottom:10px">Activity by Hour of Day</div>',
                unsafe_allow_html=True,
            )
            _hr_cnt = [0] * 24
            for _a in _acts_all:
                try:
                    _hr_cnt[int((_a.get("ts") or "00:00:00")[11:13])] += 1
                except Exception:
                    pass
            _hr_max = max(_hr_cnt) or 1
            _HM_COLS = ["#0f1929", "#0d2a3a", "#0a3a4a", "#006a54", "#00956e", "#00d4aa"]

            _cells_html = []
            for _h, _hv in enumerate(_hr_cnt):
                _idx = min(int(_hv / _hr_max * 5), 5)
                _hc  = _HM_COLS[_idx]
                _tip = f"{_h:02d}:00 — {_hv} event{'s' if _hv!=1 else ''}"
                _cells_html.append(
                    f'<div class="hour-cell" style="background:{_hc}" title="{_tip}">'
                    f'{_h:02d}</div>'
                )
            _peak_h = _hr_cnt.index(max(_hr_cnt)) if _hr_max > 0 else 0
            st.markdown(
                f'<div class="hour-hm-wrap">{"".join(_cells_html)}</div>'
                f'<div style="font-size:.63rem;color:#334155;margin-top:6px">'
                f'Peak hour: <span style="color:#00d4aa;font-weight:700">{_peak_h:02d}:00</span>'
                f' ({_hr_max} events) &nbsp;·&nbsp; Hover cells to see counts</div>',
                unsafe_allow_html=True,
            )

        with _log_vis2:
            st.markdown(
                '<div style="font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;'
                'letter-spacing:.1em;margin-bottom:10px">What Users Do Most</div>',
                unsafe_allow_html=True,
            )
            _feat_c2 = collections.Counter(a.get("action","other") for a in _acts_all)
            _feat_t2 = _feat_c2.most_common(7)
            _feat_mx = _feat_t2[0][1] if _feat_t2 else 1
            _f2_rows = []
            for _fa2, _fc2 in _feat_t2:
                _flbl2, _fcol2, _fic2 = _act_meta(_fa2)
                _fw2 = round(_fc2 / _feat_mx * 100)
                _f2_rows.append(
                    f'<div class="feat-row">'
                    f'<span class="feat-icon">{_fic2}</span>'
                    f'<span class="feat-lbl">{_flbl2}</span>'
                    f'<div class="feat-bar-wrap"><div class="feat-bar" style="width:{_fw2}%;--fc:{_fcol2}"></div></div>'
                    f'<span class="feat-cnt" style="--fc:{_fcol2}">{_fc2}</span>'
                    f'</div>'
                )
            st.markdown("".join(_f2_rows) or '<div style="color:#334155;font-size:.8rem">No data yet.</div>',
                        unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

        # ── Filter bar ────────────────────────────────────────────────────
        _fc1, _fc2, _fc3, _fc4, _fc5 = st.columns([2, 1.6, 2, 1, 1])
        with _fc1:
            _uopts = ["All users"] + [f'{u.split("@")[0].replace("."," ").replace("_"," ").title()} ({u})' if "@" in u else u for u in _users_unique]
            _sel_u = st.selectbox("User", _uopts, key="actlog_user_flt", label_visibility="collapsed")
            _sel_email = _sel_u.split("(")[-1].rstrip(")") if "(" in _sel_u else ("" if _sel_u == "All users" else _sel_u)
        with _fc2:
            _all_act_types = sorted(set(a.get("action","") for a in _acts_all if a.get("action")))
            _act_disp      = ["All actions"] + [f'{_act_meta(a)[2]} {_act_meta(a)[0]}' for a in _all_act_types]
            _sel_ai        = st.selectbox("Action", _act_disp, key="actlog_act_flt", label_visibility="collapsed")
            _sel_a         = "" if _sel_ai == "All actions" else _all_act_types[_act_disp.index(_sel_ai) - 1]
        with _fc3:
            _srch = st.text_input("Search", placeholder="🔍  Search user, feature, client...",
                                  key="actlog_srch", label_visibility="collapsed")
        with _fc4:
            _do_refresh = st.button("↻ Refresh", key="actlog_ref_btn", width="stretch")
        with _fc5:
            _do_export = st.button("⬇ CSV", key="actlog_export_btn", width="stretch")

        if _do_refresh:
            _cached_activity_log.clear()
            st.rerun()

        # ── Apply filters ─────────────────────────────────────────────────
        _filtered = _acts_all
        if _sel_email:
            _filtered = [a for a in _filtered if a.get("user_email") == _sel_email]
        if _sel_a:
            _filtered = [a for a in _filtered if a.get("action") == _sel_a]
        if _srch:
            _sl = _srch.lower()
            _filtered = [a for a in _filtered
                         if _sl in (a.get("details","") + a.get("user_name","") + a.get("user_email","") + a.get("module","")).lower()]

        # ── CSV export ────────────────────────────────────────────────────
        if _do_export and _filtered:
            _buf = _io.StringIO()
            _wr  = csv.DictWriter(_buf, fieldnames=["ts","user_name","user_email","action","details","module"])
            _wr.writeheader(); _wr.writerows(_filtered)
            st.download_button(
                "⬇ Download activity_log.csv",
                data=_buf.getvalue(), file_name="eci_activity_log.csv",
                mime="text/csv", key="actlog_dl",
            )

        st.markdown(
            f'<div style="font-size:.7rem;color:#334155;margin:8px 0 12px">'
            f'Showing <b style="color:#64748b">{len(_filtered)}</b> of {len(_acts_all)} events — newest first'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Timeline — grouped by date × user ─────────────────────────────
        if not _filtered:
            st.markdown(
                '<div style="text-align:center;padding:56px 24px;color:#334155;font-size:.85rem;'
                'border:1px solid #1a2540;border-radius:16px;background:#080d1a;margin-top:8px">'
                '🔍  No events match your filters.<br>'
                '<span style="font-size:.72rem;color:#1e293b">Events are recorded whenever users log in, run estimations, '
                'use BELLA, export documents, compare proposals, or perform any platform action.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            # Group by date
            _grouped: dict = {}
            for _ev in _filtered[:400]:
                _gd2 = (_ev.get("ts") or "")[:10]
                _grouped.setdefault(_gd2, []).append(_ev)

            _tl_html = ['<div class="log-scroll"><div class="log-timeline">']
            _av_pal  = ["#00d4aa","#7b61ff","#f87171","#ffd166","#00b4d8","#4ade80","#fb923c","#a78bfa"]
            _user_col: dict = {}  # stable color per user
            _col_idx = [0]
            def _get_ucol(email):
                if email not in _user_col:
                    _user_col[email] = _av_pal[_col_idx[0] % len(_av_pal)]
                    _col_idx[0] += 1
                return _user_col[email]

            for _gd in sorted(_grouped.keys(), reverse=True):
                try:
                    _gdate  = datetime.strptime(_gd, "%Y-%m-%d")
                    _gd_lbl = "Today" if _gd == _TODAY else (
                              "Yesterday" if _gd == (_NOW - timedelta(days=1)).strftime("%Y-%m-%d") else
                              _gdate.strftime("%A, %B %d %Y"))
                except Exception:
                    _gd_lbl = _gd
                _gd_evts = _grouped[_gd]
                _gd_cnt  = len(_gd_evts)
                _gd_users = len(set(a.get("user_email","") for a in _gd_evts))

                # Day separator with mini summary
                _gd_action_ctr = collections.Counter(a.get("action","") for a in _gd_evts)
                _gd_top_acts = [_act_meta(a)[2] for a, _ in _gd_action_ctr.most_common(4)]
                _gd_icons = " ".join(_gd_top_acts)
                _tl_html.append(
                    f'<div style="display:flex;align-items:center;gap:10px;margin:20px 0 12px 2px">'
                    f'<div style="background:#080d1a;border:1px solid #1a2540;border-radius:8px;'
                    f'padding:5px 12px;display:flex;align-items:center;gap:8px;flex-shrink:0">'
                    f'<span style="font-size:.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.1em">{_gd_lbl}</span>'
                    f'<span style="font-size:.7rem">{_gd_icons}</span>'
                    f'</div>'
                    f'<span style="flex:1;height:1px;background:#1a2540"></span>'
                    f'<span style="font-size:.62rem;color:#334155;font-weight:700;white-space:nowrap">'
                    f'{_gd_cnt} event{"s" if _gd_cnt!=1 else ""} · {_gd_users} user{"s" if _gd_users!=1 else ""}</span>'
                    f'</div>'
                )

                # Group events by user within the day (for user-session feel)
                _day_by_user: dict = {}
                for _ev2 in _gd_evts:
                    _eu = _ev2.get("user_email","") or "system"
                    _day_by_user.setdefault(_eu, []).append(_ev2)

                _user_order = list(_day_by_user.keys())
                _rendered = 0
                for _uemail in _user_order:
                    _u_evts = _day_by_user[_uemail]
                    _u_ev0  = _u_evts[0]
                    _uname  = _u_ev0.get("user_name") or _u_ev0.get("user_email") or "System"
                    _udisp  = _uname.split("@")[0].replace("."," ").replace("_"," ").title() if "@" in _uname else _uname
                    _uinit  = "".join(p[0].upper() for p in _udisp.split()[:2]) or "?"
                    _ucol   = _get_ucol(_uemail)

                    # Session header (user pill)
                    _first_ts = _u_evts[-1].get("ts","")
                    _last_ts  = _u_evts[0].get("ts","")
                    try:
                        _t0 = datetime.strptime(_first_ts, "%Y-%m-%d %H:%M:%S")
                        _t1 = datetime.strptime(_last_ts,  "%Y-%m-%d %H:%M:%S")
                        _dur_min = int((_t1 - _t0).total_seconds() / 60)
                        _dur_txt = f"{_dur_min}m session" if _dur_min > 0 else "< 1m"
                    except Exception:
                        _dur_txt = ""
                    _sess_acts_unique = list({_act_meta(e.get("action",""))[2] for e in _u_evts})
                    _sess_icons = " ".join(_sess_acts_unique[:5])

                    _tl_html.append(
                        f'<div class="session-sep" style="--sac:{_ucol}">'
                        f'<div class="session-av">{_uinit}</div>'
                        f'<div><div class="session-name">{_udisp}</div>'
                        f'<div class="session-dur">{len(_u_evts)} action{"s" if len(_u_evts)!=1 else ""}'
                        + (f' · {_dur_txt}' if _dur_txt else "")
                        + f' · {_sess_icons}</div></div>'
                        f'<span class="session-meta">{_first_ts[11:16] if len(_first_ts)>10 else ""}'
                        + (f' – {_last_ts[11:16]}' if _last_ts != _first_ts and len(_last_ts)>10 else "")
                        + f'</span></div>'
                    )

                    for _i, _ev in enumerate(_u_evts):
                        _lbl, _col, _ico = _act_meta(_ev.get("action",""))
                        _ts_str  = _ev.get("ts","")
                        try:
                            _ts_fmt = datetime.strptime(_ts_str, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
                        except Exception:
                            _ts_fmt = _ts_str[11:19] if len(_ts_str) > 10 else _ts_str
                        _detail  = _ev.get("details","") or ""
                        _module  = _ev.get("module","") or ""
                        _is_last = (_i == len(_u_evts) - 1)
                        _vline   = "" if _is_last else f'<div class="log-vline" style="--lc:{_col}"></div>'
                        _mod_html2 = f'<span class="log-module">{_module}</span>' if _module else ""

                        # Render detail as rich text — highlight key info
                        _detail_clean = _detail.replace("<","&lt;").replace(">","&gt;")
                        _rendered += 1
                        _tl_html.append(
                            f'<div class="log-entry" style="animation-delay:{min(_rendered*0.03,0.5):.2f}s">'
                            f'<div class="log-line-wrap">'
                            f'<div class="log-dot" style="--lc:{_col}"></div>'
                            f'{_vline}'
                            f'</div>'
                            f'<div class="log-body">'
                            f'<div class="log-head">'
                            f'<span class="log-act" style="--lc:{_col};border:1px solid rgba(0,0,0,.2);'
                            f'background:rgba(0,0,0,.2)">{_ico} {_lbl}</span>'
                            f'<span class="log-time">{_ts_fmt}</span>'
                            f'</div>'
                            + (f'<div class="log-detail">{_detail_clean}</div>' if _detail_clean else "")
                            + (f'<div style="margin-top:4px">{_mod_html2}</div>' if _mod_html2 else "")
                            + f'</div></div>'
                        )

            _tl_html.append('</div></div>')
            st.markdown("".join(_tl_html), unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="text-align:center;font-size:.65rem;color:#1e293b;padding:16px 0 4px">'
        f'ECI Presale Intelligence &nbsp;·&nbsp; Admin Dashboard &nbsp;·&nbsp; '
        f'{_N} proposals · {len(_acts)} activity events tracked &nbsp;·&nbsp; '
        f'Cache: proposals 15s · activity 10s</div>',
        unsafe_allow_html=True,
    )
