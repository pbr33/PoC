"""Risk Analyzer Agent — Multi-dimensional risk assessment.

Evaluates technical, schedule, resource, budget, and external risks using
ECI's risk taxonomy and severity framework.
"""


class RiskAnalyzerAgent:
    """Identifies and scores project risks with mitigation strategies."""

    SYSTEM_PROMPT = (
        "You are an expert risk analyst for ECI. Assess all project risks across "
        "these categories: Technical, Schedule, Resource, Budget, External. "
        "Assign severity levels per ECI's framework. "
        "Respond in JSON with: overall_score (1-10), overall_level (Low/Medium/High/Critical), "
        "risks (list of {category, title, description, severity, probability, impact, mitigation}), "
        "risk_matrix (list of {category, probability, impact})."
    )

    def __init__(self, azure_client):
        self.client = azure_client

    def analyze(self, semantic: dict, time_est: dict, cost_est: dict) -> dict:
        context = {
            "requirements_count": len(semantic.get("requirements", [])),
            "complexity_score": semantic.get("complexity_score", 5),
            "technology_stack": semantic.get("technology_stack", []),
            "total_hours": time_est.get("total_hours", 0),
            "total_cost": cost_est.get("total_cost", 0),
            "integration_count": len([r for r in semantic.get("requirements", []) if r.get("type") == "integration"]),
        }
        result = self.client.agent_completion("RiskAnalyzer", self.SYSTEM_PROMPT, context)
        if result and isinstance(result, dict):
            return result
        return self._generate_risks(semantic, time_est, cost_est)

    def _generate_risks(self, semantic: dict, time_est: dict, cost_est: dict) -> dict:
        complexity = semantic.get("complexity_score", 7)
        integ_count = len([r for r in semantic.get("requirements", []) if r.get("type") == "integration"])
        tech = semantic.get("technology_stack", [])
        hours = time_est.get("total_hours", 2000)

        risks = [
            {
                "category": "Technical",
                "title": "Integration Complexity",
                "description": f"Project requires {integ_count} third-party integrations which may have API limitations or compatibility issues.",
                "severity": "High" if integ_count >= 3 else "Medium",
                "probability": "Medium",
                "impact": "High",
                "mitigation": "Conduct early proof-of-concept for each integration. Allocate spike stories in Sprint 1-2. Maintain fallback approach documentation.",
            },
            {
                "category": "Technical",
                "title": "Technology Stack Maturity",
                "description": f"Stack includes {len(tech)} technologies. Newer or less-proven components may introduce unexpected issues.",
                "severity": "Medium",
                "probability": "Low",
                "impact": "Medium",
                "mitigation": "Use only Azure Well-Architected patterns. Conduct architecture review with ECI's Azure practice lead. Implement comprehensive monitoring from day one.",
            },
            {
                "category": "Schedule",
                "title": "Scope Creep During Development",
                "description": "Requirements may evolve as client sees working software, potentially extending timelines.",
                "severity": "High",
                "probability": "High",
                "impact": "High",
                "mitigation": "Implement strict change request process. Use Agile sprints with clearly defined acceptance criteria. Maintain product backlog with prioritization.",
            },
            {
                "category": "Schedule",
                "title": "Dependency on Client Decisions",
                "description": "Key design and architecture decisions require timely client approvals which may be delayed.",
                "severity": "Medium",
                "probability": "Medium",
                "impact": "Medium",
                "mitigation": "Establish RACI matrix upfront. Schedule weekly decision-making sessions. Define escalation path for delayed decisions.",
            },
            {
                "category": "Resource",
                "title": "Key Personnel Availability",
                "description": "Specialized roles (Architect, Security Lead) may have limited availability across ECI projects.",
                "severity": "Medium",
                "probability": "Medium",
                "impact": "High",
                "mitigation": "Secure resource commitments during proposal phase. Cross-train team members. Maintain a bench of pre-vetted contractors.",
            },
            {
                "category": "Resource",
                "title": "Client SME Availability",
                "description": "Domain experts on client side may be pulled into other priorities, delaying knowledge transfer.",
                "severity": "Medium",
                "probability": "High",
                "impact": "Medium",
                "mitigation": "Define minimum SME commitment hours per sprint. Record all knowledge transfer sessions. Create comprehensive domain documentation early.",
            },
            {
                "category": "Budget",
                "title": "Azure Cost Overrun",
                "description": "Cloud infrastructure costs may exceed estimates due to higher-than-expected usage or premium tier requirements.",
                "severity": "Medium" if cost_est.get("total_cost", 0) < 500000 else "High",
                "probability": "Medium",
                "impact": "Medium",
                "mitigation": "Implement Azure Cost Management alerts. Use reserved instances where possible. Conduct monthly cost reviews. Include 15% infrastructure contingency.",
            },
            {
                "category": "External",
                "title": "Regulatory Compliance Changes",
                "description": "Evolving data protection regulations may require additional security or compliance features.",
                "severity": "Low",
                "probability": "Low",
                "impact": "High",
                "mitigation": "Monitor regulatory changes quarterly. Design system with compliance extensibility. Engage ECI compliance team for periodic reviews.",
            },
            {
                "category": "External",
                "title": "Third-Party Service Disruption",
                "description": "External API providers or SaaS dependencies may experience outages or breaking changes.",
                "severity": "Medium",
                "probability": "Low",
                "impact": "High",
                "mitigation": "Implement circuit breaker patterns. Use API versioning. Design graceful degradation for all external dependencies.",
            },
        ]

        # Calculate overall score
        severity_scores = {"Low": 2, "Medium": 5, "High": 8, "Critical": 10}
        avg_score = sum(severity_scores.get(r["severity"], 5) for r in risks) / len(risks)
        overall = min(10, max(1, int(avg_score * complexity / 7)))

        return {
            "overall_score": overall,
            "overall_level": "Low" if overall <= 3 else "Medium" if overall <= 6 else "High" if overall <= 8 else "Critical",
            "risks": risks,
            "risk_matrix": [
                {"category": "Technical", "probability": 0.4, "impact": 0.7},
                {"category": "Schedule", "probability": 0.6, "impact": 0.6},
                {"category": "Resource", "probability": 0.5, "impact": 0.5},
                {"category": "Budget", "probability": 0.3, "impact": 0.4},
                {"category": "External", "probability": 0.2, "impact": 0.6},
            ],
        }
