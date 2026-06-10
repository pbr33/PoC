"""Scope & Assumptions Agent — Crystal-clear boundaries and prerequisites.

Defines in-scope items, out-of-scope exclusions, assumptions, and
prerequisites for clear project boundaries.
"""


class ScopeAssumptionsAgent:
    """Defines project scope, assumptions, and prerequisites."""

    SYSTEM_PROMPT = (
        "You are a presales scope definition expert for ECI. Define crystal-clear "
        "project boundaries including in-scope deliverables, out-of-scope items, "
        "assumptions, and prerequisites. "
        "Respond in JSON with: in_scope (list of strings), out_of_scope (list of strings), "
        "assumptions (list of strings), prerequisites (list of strings), "
        "change_management (string describing change request process)."
    )

    def __init__(self, azure_client):
        self.client = azure_client

    def define(self, semantic: dict, time_est: dict, cost_est: dict) -> dict:
        context = {
            "requirements": semantic.get("requirements", [])[:15],
            "project_type": semantic.get("project_type", ""),
            "technology_stack": semantic.get("technology_stack", []),
            "total_hours": time_est.get("total_hours", 0),
            "total_cost": cost_est.get("total_cost", 0),
        }
        result = self.client.agent_completion("ScopeAssumptions", self.SYSTEM_PROMPT, context)
        if result and isinstance(result, dict):
            return result
        return self._generate_scope(semantic, time_est, cost_est)

    def _generate_scope(self, semantic: dict, time_est: dict, cost_est: dict) -> dict:
        reqs = semantic.get("requirements", [])
        func_count = len([r for r in reqs if r.get("type") == "functional"])

        in_scope = [
            f"All {func_count} functional requirements as itemized in the Requirements section",
            "Feature list with acceptance criteria for each deliverable",
            "Azure-based solution architecture design and documentation",
            "Full-stack application development (frontend + backend + API layer)",
            "Integration with specified third-party systems (Azure AD, SharePoint, Power BI, Teams)",
            "Comprehensive testing: unit, integration, performance, security scan, and UAT support",
            "CI/CD pipeline setup and Infrastructure as Code (Bicep/Terraform)",
            "Data migration from identified source systems",
            "User documentation and admin guide",
            "Knowledge transfer sessions (3 sessions × 2 hours)",
            "30-day post-launch hypercare support",
            "Project management throughout all phases",
        ]

        out_of_scope = [
            "Legacy system decommissioning or retirement",
            "End-user training beyond admin and power-user levels",
            "Custom hardware procurement or on-premises infrastructure",
            "Third-party license procurement (client responsibility)",
            "Data cleansing or quality remediation of source data",
            "Mobile native application development (web-responsive only)",
            "Multi-language / i18n support beyond English",
            "Penetration testing (recommended as separate engagement)",
            "Business process re-engineering or change management consulting",
            "Ongoing support and maintenance beyond 30-day hypercare",
        ]

        assumptions = [
            "Client will provide Azure subscription with sufficient permissions for provisioning resources",
            "Dedicated client project sponsor and product owner available for weekly sync meetings",
            "Client SMEs available for minimum 10 hours/week during Discovery and UAT phases",
            "All source system APIs are documented and accessible with valid credentials",
            "Source data is of sufficient quality for migration without major cleansing effort",
            "Client IT team will support VPN/network access setup within first week of project",
            "All regulatory and compliance requirements are known and documented upfront",
            "No major organizational restructuring during project duration that would affect scope",
            "Azure service availability in the target region for all proposed services",
            "Standard business hours (9 AM – 6 PM local time) for team availability",
        ]

        prerequisites = [
            "Azure subscription with Owner/Contributor access provisioned",
            "Azure AD tenant configured with test user accounts",
            "SharePoint Online site collection created for project documents",
            "VPN or network access to client environments (if applicable)",
            "Source system API credentials and documentation provided",
            "Signed Statement of Work and project charter",
            "Client project team identified and onboarded",
            "Design mockups or wireframes approved (if existing)",
        ]

        return {
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "assumptions": assumptions,
            "prerequisites": prerequisites,
            "change_management": (
                "Any changes to the agreed scope will follow ECI's formal Change Request (CR) process: "
                "1) CR submitted with business justification, 2) Impact assessment on timeline and cost within 2 business days, "
                "3) Client approval required before implementation, 4) CR tracked in project backlog with separate budget allocation."
            ),
        }
