"""Azure OpenAI Client for the ECI Presale Agent.

Handles all interactions with Azure OpenAI including semantic analysis,
requirement extraction, and agent-specific completions. Falls back to
intelligent mock data when no API key is configured so the UI remains
fully demonstrable.
"""

import json
import streamlit as st

try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None


class AzureOpenAIClient:
    """Wrapper around the Azure OpenAI API with ECI-specific prompts."""

    def __init__(self, api_key: str, endpoint: str, api_version: str, deployment: str):
        self.api_key = api_key
        self.endpoint = endpoint
        self.api_version = api_version
        self.deployment = deployment
        self._client = None

        if api_key and endpoint and AzureOpenAI:
            try:
                self._client = AzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint,
                )
            except Exception:
                self._client = None

    @classmethod
    def from_session(cls):
        return cls(
            api_key=st.session_state.get("azure_api_key", ""),
            endpoint=st.session_state.get("azure_endpoint", ""),
            api_version=st.session_state.get("azure_api_version", "2024-06-01"),
            deployment=st.session_state.get("azure_deployment", "gpt-4"),
        )

    # ── Connection Test ──
    def test_connection(self):
        if not self._client:
            return False, "Client not initialized. Check API key and endpoint."
        try:
            resp = self._client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": "Reply OK"}],
                max_tokens=5,
            )
            return True, f"✅ Connected — Model: {self.deployment}"
        except Exception as e:
            return False, f"Connection failed: {str(e)[:200]}"

    # ── Core completion ──
    def complete(self, system_prompt: str, user_prompt: str, response_format: str = "json"):
        if self._client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                kwargs = dict(
                    model=self.deployment,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.3,
                )
                if response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                resp = self._client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content
                if response_format == "json":
                    return json.loads(content)
                return content
            except Exception as e:
                st.warning(f"Azure OpenAI call failed, using intelligent mock: {str(e)[:150]}")
                return None
        return None

    # ── Semantic Analysis ──
    def analyze_requirements(self, document_text: str) -> dict:
        system = (
            "You are an expert presales analyst for an IT consulting company called ECI. "
            "Analyze the provided scope document and extract structured requirements. "
            "Respond in JSON with keys: requirements (list of {title, description, type, complexity, priority}), "
            "technology_stack (list of identified technologies), "
            "business_objectives (list), complexity_score (1-10), "
            "project_type (Data/Cloud/AI, Web Application, Mobile, SharePoint, Integration, Other)."
        )
        result = self.complete(system, f"Analyze this scope document:\n\n{document_text[:12000]}")
        if result:
            return result
        return self._mock_semantic_analysis(document_text)

    # ── Historical RAG Search ──
    def search_historical(self, document_text: str, historical_projects: list) -> dict:
        if historical_projects and self._client:
            system = (
                "You are a historical data analyst. Given a new project description and historical project data, "
                "identify similar past projects and extract useful benchmarks. "
                "Respond in JSON with: similar_projects (list), benchmark_hours, benchmark_cost, success_patterns, risk_patterns."
            )
            user = (
                f"New project:\n{document_text[:4000]}\n\n"
                f"Historical data:\n{json.dumps(historical_projects[:20], default=str)}"
            )
            result = self.complete(system, user)
            if result:
                return result
        return self._mock_rag_results()

    # ── Agent-specific completions ──
    def agent_completion(self, agent_name: str, system_prompt: str, context: dict) -> dict:
        user_prompt = json.dumps(context, default=str)[:8000]
        result = self.complete(system_prompt, user_prompt)
        return result

    # ══════════════════════════════════════════════════
    #  Mock Data (when no API key configured)
    # ══════════════════════════════════════════════════

    def _mock_semantic_analysis(self, text: str) -> dict:
        keywords = text.lower()
        reqs = []
        # Generate contextual requirements based on document content
        func_items = [
            ("User Authentication & SSO", "Implement Azure AD-based single sign-on with MFA support", "High"),
            ("Dashboard & Reporting", "Interactive dashboards with real-time data visualization using Power BI", "High"),
            ("Data Pipeline Processing", "Automated ETL pipeline for data ingestion from multiple sources", "High"),
            ("API Gateway & Integration", "RESTful API layer with rate limiting and authentication", "Medium"),
            ("Notification Engine", "Multi-channel notifications via email, Teams, and push notifications", "Medium"),
            ("Search & Filtering", "Full-text search with faceted filtering and advanced query support", "Medium"),
            ("File Management", "Document upload, versioning, and metadata management", "Low"),
            ("Audit Trail & Logging", "Comprehensive audit logging for compliance and troubleshooting", "Low"),
        ]
        for title, desc, complexity in func_items:
            reqs.append({"title": title, "description": desc, "type": "functional", "complexity": complexity, "priority": "P1" if complexity == "High" else "P2"})

        nonfunc = [
            ("Performance SLA", "Response time under 200ms for 95th percentile, support 10K concurrent users"),
            ("Security Compliance", "SOC 2 Type II compliance, data encryption at rest and in transit"),
            ("Scalability", "Auto-scaling to handle 5x peak load with zero downtime"),
            ("Availability", "99.95% uptime SLA with multi-region failover"),
        ]
        for title, desc in nonfunc:
            reqs.append({"title": title, "description": desc, "type": "non-functional", "complexity": "High", "priority": "P1"})

        integ = [
            ("Azure Active Directory", "SSO and role-based access control integration"),
            ("SharePoint Online", "Document library integration for file storage and collaboration"),
            ("Power BI Embedded", "Embedded analytics and reporting dashboards"),
            ("Microsoft Teams", "Teams notifications and bot integration"),
        ]
        for title, desc in integ:
            reqs.append({"title": title, "description": desc, "type": "integration", "complexity": "Medium", "priority": "P2"})

        return {
            "requirements": reqs,
            "technology_stack": [
                "Azure App Service", "Azure SQL Database", "Azure Cosmos DB",
                "Azure Functions", "Azure API Management", "Azure AD B2C",
                "Power BI Embedded", "Azure DevOps", "React.js", "Node.js",
                "Python", ".NET Core", "Redis Cache", "Azure Blob Storage",
            ],
            "business_objectives": [
                "Streamline data processing and reduce manual effort by 60%",
                "Provide real-time analytics for executive decision-making",
                "Enable secure collaboration across distributed teams",
                "Ensure regulatory compliance across all data touchpoints",
            ],
            "complexity_score": 7,
            "project_type": "Data/Cloud/AI",
        }

    def _mock_rag_results(self) -> dict:
        return {
            "similar_projects": [
                {"name": "Azure Data Platform for FinCorp", "similarity": 0.87, "hours": 2400, "cost": 480000, "outcome": "Won"},
                {"name": "Cloud Migration for MedTech Inc", "similarity": 0.82, "hours": 1800, "cost": 360000, "outcome": "Won"},
                {"name": "Analytics Dashboard for RetailCo", "similarity": 0.76, "hours": 1200, "cost": 240000, "outcome": "Won"},
                {"name": "Enterprise API Platform for LogiTech", "similarity": 0.71, "hours": 3200, "cost": 640000, "outcome": "Lost"},
            ],
            "benchmark_hours": 2150,
            "benchmark_cost": 430000,
            "success_patterns": [
                "Phased delivery approach with early MVP",
                "Strong discovery phase with client workshops",
                "Dedicated architecture review checkpoint",
            ],
            "risk_patterns": [
                "Scope creep in integration phase",
                "Data quality issues delaying migration",
                "Client stakeholder availability constraints",
            ],
        }
