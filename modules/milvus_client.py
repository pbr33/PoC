# ═══════════════════════════════════════════════════════════════════════
#  MILVUS RAG CLIENT
#  Searches collection_demo_v1 for similar past scope documents,
#  enriching pipeline estimation with real historical context.
#
#  Embedding uses a dedicated Azure OpenAI endpoint (can differ from
#  the main chat endpoint). Falls back to keyword scoring if unavailable.
# ═══════════════════════════════════════════════════════════════════════
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")

import re
import time
import uuid
import logging

log = logging.getLogger(__name__)

_COLLECTION = "collection_demo_v1"

# ── Cost parser: extract service costs from estimation document text ──────────
_SVC_ALIASES = {
    "app service": "Azure App Service",
    "web app": "Azure App Service",
    "azure function": "Azure Functions",
    "function app": "Azure Functions",
    "serverless": "Azure Functions",
    "sql database": "Azure SQL Database",
    "azure sql": "Azure SQL Database",
    "cosmos": "Cosmos DB",
    "cosmosdb": "Cosmos DB",
    "blob storage": "Azure Blob Storage",
    "blob": "Azure Blob Storage",
    "key vault": "Azure Key Vault",
    "ai search": "Azure AI Search",
    "cognitive search": "Azure AI Search",
    "openai": "Azure OpenAI",
    "gpt": "Azure OpenAI",
    "foundry": "Azure AI Foundry",
    "claude": "Azure AI Foundry",
    "monitor": "Azure Monitor",
    "app insights": "Azure Monitor",
    "redis": "Azure Redis Cache",
    "cache": "Azure Redis Cache",
    "api management": "API Management",
    "apim": "API Management",
    "front door": "Azure Front Door",
    "service bus": "Azure Service Bus",
    "logic app": "Azure Logic Apps",
    "event grid": "Azure Event Grid",
    "signalr": "SignalR",
    "devops": "Azure DevOps",
    "container app": "Azure Container Apps",
    "kubernetes": "Azure Container Apps",
    "aks": "Azure Container Apps",
    "entra": "Azure AD / Entra ID",
    "active directory": "Azure AD / Entra ID",
    "sharepoint": "SharePoint",
    "teams": "Microsoft Teams",
    "copilot studio": "Copilot Studio",
    "power bi": "Power BI",
}

def _parse_costs_from_text(text: str) -> dict:
    """
    Parse cost data from an estimation document text retrieved from Milvus.
    Returns {services: [{service, monthly_cost}], total_monthly: int}.
    """
    if not text:
        return {"services": [], "total_monthly": 0}

    text_l = text.lower()
    services = []
    seen_svcs = set()

    # Pattern: find "$NNN" or "NNN/mo" or "NNN per month" near a service keyword
    dollar_pattern = re.compile(
        r'(?:USD\s*)?\$\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:/\s*(?:mo|month|monthly))?',
        re.IGNORECASE
    )
    # Find all dollar amounts with their position
    amounts = [(m.start(), int(m.group(1).replace(",", ""))) for m in dollar_pattern.finditer(text)]

    # For each known service alias, look for the NEXT dollar amount after the keyword
    # (price always follows the service name in an estimation doc)
    for alias, canonical in _SVC_ALIASES.items():
        if canonical in seen_svcs:
            continue
        idx = text_l.find(alias)
        if idx == -1:
            continue
        # Find the first dollar amount that comes AFTER the keyword, within 150 chars
        # Fall back to the nearest backward amount within 80 chars if nothing forward
        forward = None
        backward = None
        for pos, amt in amounts:
            if 0 < amt <= 2000:
                if pos >= idx and (pos - idx) <= 150:
                    if forward is None or (pos - idx) < (forward[0] - idx):
                        forward = (pos, amt)
                elif pos < idx and (idx - pos) <= 80:
                    if backward is None or (idx - pos) < (idx - backward[0]):
                        backward = (pos, amt)
        chosen = forward[1] if forward else (backward[1] if backward else None)
        if chosen is not None:
            services.append({"service": canonical, "monthly_cost": chosen})
            seen_svcs.add(canonical)

    # Also look for "Total: $NNN" or "Total monthly: $NNN"
    total_match = re.search(
        r'(?:total|grand\s+total|total\s+monthly|monthly\s+total)\s*:?\s*\$?\s*(\d{1,6}(?:,\d{3})*)',
        text_l
    )
    total_monthly = int(total_match.group(1).replace(",","")) if total_match else sum(s["monthly_cost"] for s in services)

    return {"services": services, "total_monthly": total_monthly}


def _empty_rag() -> dict:
    return {
        "similar_projects": [],
        "benchmark_hours": 0,
        "benchmark_cost": 0,
        "benchmark_cost_services": [],   # parsed cost services from RAG docs
        "success_patterns": [],
        "risk_patterns": [],
        "milvus_context": "",
        "milvus_hits": 0,
    }


class MilvusRAG:
    """
    Wraps pymilvus for the presales pipeline.

      search(text)  → rag-format dict  (injected at pipeline RAG step)
      store(text, …) → bool            (called after pipeline completes)

    Embedding uses a dedicated Azure OpenAI endpoint configured under
    integrations.milvus in config.yaml (separate from the main chat endpoint).
    Falls back to local keyword scoring when the embedding endpoint is
    unavailable so the pipeline never hard-fails.
    """

    def __init__(self, host: str, port,
                 user: str, password: str, db_name: str,
                 emb_endpoint: str, emb_key: str,
                 emb_deployment: str, emb_api_version: str):
        self._host = host
        self._port = str(port)
        self._user = user
        self._password = password
        self._db_name = db_name
        self._emb_endpoint = emb_endpoint.rstrip("/") if emb_endpoint else ""
        self._emb_key = emb_key
        self._emb_deployment = emb_deployment
        self._emb_api_ver = emb_api_version or "2025-01-01-preview"
        self._col = None
        self._schema_fields: list = []   # field names from actual collection schema
        self._auto_id: bool = False       # whether primary key is auto-generated

    @classmethod
    def from_session(cls) -> "MilvusRAG":
        """Build instance from Streamlit session state (populated by config_loader)."""
        import streamlit as st
        ss = st.session_state
        return cls(
            host=ss.get("milvus_host", ""),
            port=ss.get("milvus_port", "19530"),
            user=ss.get("milvus_user", ""),
            password=ss.get("milvus_password", ""),
            db_name=ss.get("milvus_db", ""),
            emb_endpoint=ss.get("milvus_embedding_endpoint", ""),
            emb_key=ss.get("milvus_embedding_key", ""),
            emb_deployment=ss.get("milvus_embedding_deployment", "text-embedding-3-small"),
            emb_api_version=ss.get("milvus_embedding_api_version", "2025-01-01-preview"),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._user and self._password)

    def _ensure_connected(self) -> bool:
        if not self.is_configured:
            return False
        try:
            from pymilvus import connections, Collection
            alias = "milvus_rag"
            if not connections.has_connection(alias):
                connections.connect(
                    alias=alias,
                    host=self._host,
                    port=self._port,
                    user=self._user,
                    password=self._password,
                    db_name=self._db_name,
                )
            if self._col is None:
                self._col = Collection(_COLLECTION, using=alias)
                self._col.load()
                # Read schema so store() only inserts fields that actually exist
                try:
                    schema = self._col.schema
                    self._auto_id = getattr(schema, "auto_id", False)
                    self._schema_fields = [
                        f.name for f in schema.fields
                    ]
                    log.debug("[MilvusRAG] Schema fields: %s (auto_id=%s)",
                              self._schema_fields, self._auto_id)
                except Exception as se:
                    log.debug("[MilvusRAG] Could not read schema: %s", se)
                    self._schema_fields = []
            return True
        except Exception as e:
            log.warning("[MilvusRAG] Connection failed: %s", e)
            return False

    def _embed(self, text: str) -> list:
        """Generate embedding via the dedicated Azure OpenAI embeddings endpoint."""
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=self._emb_endpoint,
            api_key=self._emb_key,
            api_version=self._emb_api_ver,
        )
        resp = client.embeddings.create(
            model=self._emb_deployment,
            input=text[:8000],
        )
        return resp.data[0].embedding

    def _safe_output_fields(self, wanted: list) -> list:
        """Return only fields from *wanted* that exist in the schema."""
        if not self._schema_fields:
            return wanted   # schema unknown — try them all, catch error above
        return [f for f in wanted if f in self._schema_fields]

    # ── Public search ──────────────────────────────────────────────────
    def search(self, text: str, top_k: int = 5) -> dict:
        """
        Search Milvus for similar past scope documents.

        1. Try vector (cosine) search via Azure OpenAI embeddings — most accurate.
        2. If embedding endpoint is unavailable, fall back to keyword scoring
           across all docs fetched from Milvus (zero extra deployments needed).
        3. On any error → return _empty_rag() so the pipeline continues without RAG.
        """
        try:
            if not self._ensure_connected():
                return _empty_rag()

            # Strategy 1: Vector search
            if self._emb_endpoint and self._emb_key and self._emb_deployment:
                try:
                    vec = self._embed(text)
                    return self._vector_search(vec, top_k)
                except Exception as e:
                    log.info("[MilvusRAG] Embedding failed (%s) — falling back to keyword search.", e)

            # Strategy 2: Keyword fallback
            return self._keyword_search(text, top_k)
        except Exception as e:
            log.warning("[MilvusRAG] search() unhandled error: %s — continuing without RAG.", e)
            return _empty_rag()

    def _vector_search(self, vec: list, top_k: int) -> dict:
        wanted = ["id", "source", "document_type", "text", "estimation_reference_url"]
        out_fields = self._safe_output_fields(wanted)
        results = self._col.search(
            data=[vec],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=out_fields,
        )
        hits = results[0] if results else []
        similar_projects, context_parts = [], []
        all_benchmark_services = {}
        best_total = 0
        _seen_sources: set = set()
        for hit in hits:
            score = round(float(hit.score), 3)
            ent = hit.entity
            source = ent.get("source") or "Unknown project"
            # Skip duplicate source documents (same scope stored multiple times)
            _src_key = source.strip().lower()
            if _src_key in _seen_sources:
                continue
            _seen_sources.add(_src_key)
            full_text = ent.get("text") or ""
            snippet = full_text[:800]
            ref_url = ent.get("estimation_reference_url") or ""
            # Parse cost data from the retrieved estimation document text
            parsed = _parse_costs_from_text(full_text)
            proj_cost = parsed["total_monthly"]
            for svc in parsed["services"]:
                k = svc["service"]
                if k not in all_benchmark_services:
                    all_benchmark_services[k] = svc["monthly_cost"]
            if proj_cost > best_total:
                best_total = proj_cost
            similar_projects.append({
                "name": source, "similarity": score,
                "hours": 0, "cost": proj_cost,
                "outcome": snippet[:200], "reference_url": ref_url,
            })
            if score > 0.45:
                cost_hint = f" | Parsed infra cost: ${proj_cost}/mo" if proj_cost else ""
                context_parts.append(
                    f"--- Past Project: {source} (similarity {score}){cost_hint} ---\n{snippet}"
                )
        bm_services = [{"service": k, "monthly_cost": v} for k, v in all_benchmark_services.items()]
        return {
            "similar_projects": similar_projects,
            "benchmark_hours": 0,
            "benchmark_cost": best_total,
            "benchmark_cost_services": bm_services,
            "success_patterns": [], "risk_patterns": [],
            "milvus_context": "\n\n".join(context_parts),
            "milvus_hits": len(similar_projects),
            "milvus_search_mode": "vector",
        }

    def _keyword_search(self, query: str, top_k: int) -> dict:
        """Retrieve all docs, score by keyword overlap — no embedding needed."""
        try:
            wanted = ["id", "source", "document_type", "text", "estimation_reference_url"]
            out_fields = self._safe_output_fields(wanted)
            rows = self._col.query(
                expr='id != ""',
                output_fields=out_fields,
                limit=200,
            )
        except Exception as e:
            log.warning("[MilvusRAG] Keyword fetch failed: %s", e)
            return _empty_rag()

        if not rows:
            return _empty_rag()

        query_words = set(w for w in query.lower().split() if len(w) > 3)
        scored = []
        for row in rows:
            doc_text = (row.get("text") or "").lower()
            overlap = sum(1 for w in query_words if w in doc_text)
            score = round(min(overlap / max(len(query_words), 1), 1.0), 3)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        similar_projects, context_parts = [], []
        all_benchmark_services = {}
        best_total = 0
        _seen_sources: set = set()
        for score, row in scored:
            if len(similar_projects) >= top_k:
                break
            source = row.get("source") or "Unknown project"
            # Skip duplicate source documents (same scope stored multiple times)
            _src_key = source.strip().lower()
            if _src_key in _seen_sources:
                continue
            _seen_sources.add(_src_key)
            full_text = row.get("text") or ""
            snippet = full_text[:800]
            ref_url = row.get("estimation_reference_url") or ""
            parsed = _parse_costs_from_text(full_text)
            proj_cost = parsed["total_monthly"]
            for svc in parsed["services"]:
                k = svc["service"]
                if k not in all_benchmark_services:
                    all_benchmark_services[k] = svc["monthly_cost"]
            if proj_cost > best_total:
                best_total = proj_cost
            similar_projects.append({
                "name": source, "similarity": score,
                "hours": 0, "cost": proj_cost,
                "outcome": snippet[:200], "reference_url": ref_url,
            })
            cost_hint = f" | Parsed infra: ${proj_cost}/mo" if proj_cost else ""
            context_parts.append(
                f"--- Past Project: {source} (keyword {score}){cost_hint} ---\n{snippet}"
            )
        bm_services = [{"service": k, "monthly_cost": v} for k, v in all_benchmark_services.items()]
        return {
            "similar_projects": similar_projects,
            "benchmark_hours": 0,
            "benchmark_cost": best_total,
            "benchmark_cost_services": bm_services,
            "success_patterns": [], "risk_patterns": [],
            "milvus_context": "\n\n".join(context_parts),
            "milvus_hits": len(similar_projects),
            "milvus_search_mode": "keyword",
        }

    # ── Store new document ─────────────────────────────────────────────
    def store(self, text: str, source: str,
              doc_type: str = "", ref_url: str = "") -> bool:
        """
        Store a freshly-processed scope document in Milvus so it becomes
        available as a RAG reference for future proposals.
        Requires the embedding endpoint — skipped silently if unavailable.

        Uses schema introspection to insert only the fields the collection
        actually has, preventing fieldData count mismatches.
        """
        if not self._ensure_connected():
            return False
        if not (self._emb_endpoint and self._emb_key and self._emb_deployment):
            return False
        try:
            vec = self._embed(text)

            # Full candidate row — all fields we *might* want to insert
            candidate = {
                "id":                       str(uuid.uuid4())[:100],
                "document_id":              int(time.time()),
                "vector":                   vec,
                "source":                   source[:250],
                "document_type":            doc_type[:100],
                "text":                     text[:65000],
                "estimation_reference_url": ref_url[:3000],
            }

            # Filter to only fields present in the real schema.
            # If we couldn't read the schema, try without the id field first
            # (handles auto_id=True collections).
            if self._schema_fields:
                row = {k: v for k, v in candidate.items()
                       if k in self._schema_fields}
                # If primary key is auto-generated, drop it from the insert
                if self._auto_id:
                    pk_names = [f.name for f in self._col.schema.fields
                                if f.is_primary]
                    for pk in pk_names:
                        row.pop(pk, None)
            else:
                # Schema unknown — try without 'id' (common auto_id scenario)
                row = {k: v for k, v in candidate.items() if k != "id"}

            self._col.insert([row])
            self._col.flush()
            log.info("[MilvusRAG] Stored '%s' (%d fields) in Milvus.",
                     source, len(row))
            return True
        except Exception as e:
            log.warning("[MilvusRAG] Store failed: %s", e)
            return False
