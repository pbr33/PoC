"""Architecture Designer Agent — Azure Well-Architected solution design.

Generates component-level architecture based on Azure best practices,
security controls, scalability patterns, and HA considerations.
"""


class ArchitectureDesignerAgent:
    """Designs Azure-based solution architectures from requirements."""

    SYSTEM_PROMPT = (
        "You are an Azure Solutions Architect designing for ECI. "
        "Create a comprehensive architecture using Azure Well-Architected Framework. "
        "Respond in JSON with: pattern (string), components (list of {name, type, services: [strings], azure_service}), "
        "data_flow (list of strings showing flow), security (list of security controls), "
        "scalability (string), availability (string), "
        "infrastructure_as_code (string describing IaC approach)."
    )

    def __init__(self, azure_client):
        self.client = azure_client

    def design(self, semantic: dict, rag_results: dict) -> dict:
        context = {
            "requirements": semantic.get("requirements", [])[:20],
            "technology_stack": semantic.get("technology_stack", []),
            "complexity_score": semantic.get("complexity_score", 5),
            "project_type": semantic.get("project_type", "Data/Cloud/AI"),
            "success_patterns": rag_results.get("success_patterns", []),
        }
        result = self.client.agent_completion("ArchitectureDesigner", self.SYSTEM_PROMPT, context)
        if result and isinstance(result, dict):
            return result
        return self._generate_architecture(semantic)

    def _generate_architecture(self, semantic: dict) -> dict:
        project_type = semantic.get("project_type", "Data/Cloud/AI")

        components = [
            {
                "name": "Frontend Layer",
                "type": "Web Application",
                "azure_service": "Azure App Service / Static Web Apps",
                "services": [
                    "React.js SPA with TypeScript",
                    "Azure CDN for static assets",
                    "Azure Front Door for global load balancing",
                    "Progressive Web App capabilities",
                ],
            },
            {
                "name": "API Gateway",
                "type": "Integration",
                "azure_service": "Azure API Management",
                "services": [
                    "RESTful API endpoints with OpenAPI spec",
                    "Rate limiting and throttling policies",
                    "OAuth 2.0 / JWT token validation",
                    "API versioning and deprecation management",
                    "Request/response transformation",
                ],
            },
            {
                "name": "Application Services",
                "type": "Microservices",
                "azure_service": "Azure App Service / Azure Functions",
                "services": [
                    ".NET Core Web API for business logic",
                    "Azure Functions for event-driven processing",
                    "Background job processing with Hangfire",
                    "SignalR for real-time notifications",
                ],
            },
            {
                "name": "Data Layer",
                "type": "Database",
                "azure_service": "Azure SQL + Cosmos DB",
                "services": [
                    "Azure SQL Database for relational data",
                    "Azure Cosmos DB for document/NoSQL data",
                    "Azure Redis Cache for session & cache",
                    "Azure Blob Storage for file storage",
                ],
            },
            {
                "name": "Integration Hub",
                "type": "Integration",
                "azure_service": "Azure Service Bus + Logic Apps",
                "services": [
                    "Azure Service Bus for async messaging",
                    "Azure Logic Apps for workflow automation",
                    "SharePoint Online connector",
                    "Microsoft Teams webhook integration",
                    "Power BI Embedded for analytics",
                ],
            },
            {
                "name": "Identity & Security",
                "type": "Security",
                "azure_service": "Azure AD B2C + Key Vault",
                "services": [
                    "Azure Active Directory B2C for authentication",
                    "Azure Key Vault for secrets management",
                    "Managed Identity for service-to-service auth",
                    "Azure Sentinel for threat detection",
                ],
            },
            {
                "name": "DevOps & Monitoring",
                "type": "Operations",
                "azure_service": "Azure DevOps + Monitor",
                "services": [
                    "Azure DevOps CI/CD pipelines",
                    "Infrastructure as Code (Bicep/Terraform)",
                    "Application Insights for APM",
                    "Azure Monitor for alerting and dashboards",
                    "Log Analytics workspace",
                ],
            },
            {
                "name": "AI & Analytics",
                "type": "Intelligence",
                "azure_service": "Azure Cognitive Services + ML",
                "services": [
                    "Azure OpenAI for intelligent features",
                    "Azure Cognitive Search for full-text search",
                    "Power BI Embedded for reporting",
                    "Azure Machine Learning for custom models",
                ],
            },
        ]

        data_flow = [
            "Client Browser",
            "Azure Front Door / CDN",
            "API Management Gateway",
            "App Service (Business Logic)",
            "Azure SQL / Cosmos DB",
            "Azure Service Bus",
            "Azure Functions (Processing)",
            "Blob Storage / SharePoint",
            "Power BI (Analytics)",
        ]

        security = [
            "Azure AD B2C with MFA for user authentication",
            "Azure Key Vault for all secrets and certificates",
            "TLS 1.3 encryption for data in transit",
            "Azure SQL TDE for data at rest encryption",
            "Azure Firewall and NSG for network segmentation",
            "Azure DDoS Protection Standard",
            "RBAC with least-privilege access model",
            "Azure Policy for compliance enforcement",
            "Azure Sentinel SIEM for threat monitoring",
            "Automated vulnerability scanning in CI/CD",
        ]

        return {
            "pattern": "Microservices Architecture with Event-Driven Integration",
            "components": components,
            "data_flow": data_flow,
            "security": security,
            "scalability": "Horizontal auto-scaling with Azure App Service plans. Cosmos DB auto-scale RUs. Azure Functions consumption plan for burst workloads.",
            "availability": "Multi-region active-passive with Azure Traffic Manager. 99.95% SLA target. Azure SQL geo-replication for DR.",
            "infrastructure_as_code": "Azure Bicep templates with modular resource groups. Azure DevOps YAML pipelines for multi-environment deployment (Dev → Staging → Production).",
        }
