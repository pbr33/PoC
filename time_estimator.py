"""Time Estimator Agent — ECI three-point estimation with ML-trained patterns.

Generates phase-wise effort breakdown using ECI's standard project phases:
Discovery → Design → Development → Deployment → Support.
"""

import json


class TimeEstimatorAgent:
    """Estimates project hours using ECI methodology and historical data."""

    SYSTEM_PROMPT = (
        "You are an expert project estimator for ECI, an IT consulting company. "
        "Use the three-point estimation method (Optimistic, Most Likely, Pessimistic) "
        "with weighted averages. Structure estimates using ECI's standard phases: "
        "Discovery, Design, Development, Deployment, Support. "
        "Respond in JSON with keys: total_hours (number), duration_weeks (string), "
        "confidence (string like 'High 85%'), buffer (string like '15-20%'), "
        "phases (list of {name, hours, percentage, tasks: [{name, hours, role}]}), "
        "milestones (list of {name, week, description}), "
        "three_point: {optimistic, most_likely, pessimistic}."
    )

    def __init__(self, azure_client):
        self.client = azure_client

    def estimate(self, semantic: dict, rag_results: dict) -> dict:
        """Generate time estimate based on requirements and historical data."""
        context = {
            "requirements": semantic.get("requirements", []),
            "complexity_score": semantic.get("complexity_score", 5),
            "project_type": semantic.get("project_type", "Unknown"),
            "technology_stack": semantic.get("technology_stack", []),
            "historical_benchmark_hours": rag_results.get("benchmark_hours", 0),
            "similar_projects": rag_results.get("similar_projects", []),
        }

        result = self.client.agent_completion("TimeEstimator", self.SYSTEM_PROMPT, context)
        if result and isinstance(result, dict):
            return result

        return self._generate_estimate(semantic, rag_results)

    def _generate_estimate(self, semantic: dict, rag_results: dict) -> dict:
        """Intelligent mock estimation based on requirements analysis."""
        reqs = semantic.get("requirements", [])
        complexity = semantic.get("complexity_score", 7)
        benchmark = rag_results.get("benchmark_hours", 0)

        # Base calculation
        func_reqs = len([r for r in reqs if r.get("type") == "functional"])
        nonfunc_reqs = len([r for r in reqs if r.get("type") == "non-functional"])
        integ_reqs = len([r for r in reqs if r.get("type") == "integration"])

        base_hours = (func_reqs * 120) + (nonfunc_reqs * 80) + (integ_reqs * 100)
        complexity_multiplier = 0.7 + (complexity * 0.06)
        total_raw = int(base_hours * complexity_multiplier)

        # Adjust with benchmark if available
        if benchmark > 0:
            total_raw = int((total_raw * 0.6) + (benchmark * 0.4))

        buffer = int(total_raw * 0.18)
        total = total_raw + buffer
        weeks = max(8, total // 160)

        phases = [
            {
                "name": "Discovery & Requirements",
                "hours": int(total * 0.10),
                "percentage": "10%",
                "tasks": [
                    {"name": "Stakeholder workshops", "hours": int(total * 0.03), "role": "BA/Architect"},
                    {"name": "Requirements refinement", "hours": int(total * 0.03), "role": "Business Analyst"},
                    {"name": "Technical discovery", "hours": int(total * 0.02), "role": "Architect"},
                    {"name": "Project planning", "hours": int(total * 0.02), "role": "Project Manager"},
                ],
            },
            {
                "name": "Solution Design",
                "hours": int(total * 0.15),
                "percentage": "15%",
                "tasks": [
                    {"name": "Architecture design", "hours": int(total * 0.05), "role": "Architect"},
                    {"name": "UI/UX design", "hours": int(total * 0.04), "role": "UX Designer"},
                    {"name": "Data model design", "hours": int(total * 0.03), "role": "Data Architect"},
                    {"name": "Security design review", "hours": int(total * 0.02), "role": "Security Lead"},
                    {"name": "Design documentation", "hours": int(total * 0.01), "role": "Technical Writer"},
                ],
            },
            {
                "name": "Development",
                "hours": int(total * 0.40),
                "percentage": "40%",
                "tasks": [
                    {"name": "Backend development", "hours": int(total * 0.15), "role": "Senior Developer"},
                    {"name": "Frontend development", "hours": int(total * 0.10), "role": "Frontend Developer"},
                    {"name": "API development", "hours": int(total * 0.06), "role": "Developer"},
                    {"name": "Integration development", "hours": int(total * 0.05), "role": "Integration Developer"},
                    {"name": "Code reviews", "hours": int(total * 0.04), "role": "Lead Developer"},
                ],
            },
            {
                "name": "Testing & QA",
                "hours": int(total * 0.15),
                "percentage": "15%",
                "tasks": [
                    {"name": "Unit testing", "hours": int(total * 0.04), "role": "Developer"},
                    {"name": "Integration testing", "hours": int(total * 0.04), "role": "QA Engineer"},
                    {"name": "Performance testing", "hours": int(total * 0.03), "role": "QA Engineer"},
                    {"name": "UAT support", "hours": int(total * 0.02), "role": "BA"},
                    {"name": "Security scan", "hours": int(total * 0.02), "role": "Security Engineer"},
                ],
            },
            {
                "name": "Deployment & Go-Live",
                "hours": int(total * 0.10),
                "percentage": "10%",
                "tasks": [
                    {"name": "CI/CD pipeline setup", "hours": int(total * 0.03), "role": "DevOps"},
                    {"name": "Environment provisioning", "hours": int(total * 0.02), "role": "DevOps"},
                    {"name": "Data migration", "hours": int(total * 0.03), "role": "Data Engineer"},
                    {"name": "Go-live support", "hours": int(total * 0.02), "role": "Full Team"},
                ],
            },
            {
                "name": "Post-Launch Support",
                "hours": int(total * 0.10),
                "percentage": "10%",
                "tasks": [
                    {"name": "Hypercare support", "hours": int(total * 0.04), "role": "Support Team"},
                    {"name": "Knowledge transfer", "hours": int(total * 0.03), "role": "Lead Developer"},
                    {"name": "Documentation", "hours": int(total * 0.02), "role": "Technical Writer"},
                    {"name": "Warranty fixes", "hours": int(total * 0.01), "role": "Developer"},
                ],
            },
        ]

        milestones = [
            {"name": "Project Kickoff", "week": 1, "description": "Team onboarding and discovery start"},
            {"name": "Requirements Signed Off", "week": max(2, weeks // 8), "description": "All requirements baselined"},
            {"name": "Design Complete", "week": max(4, weeks // 4), "description": "Architecture and design approved"},
            {"name": "MVP Ready", "week": max(8, weeks // 2), "description": "Core features developed and testable"},
            {"name": "UAT Start", "week": max(10, int(weeks * 0.75)), "description": "User acceptance testing begins"},
            {"name": "Go-Live", "week": weeks, "description": "Production deployment and cutover"},
        ]

        return {
            "total_hours": total,
            "duration_weeks": f"{weeks} weeks",
            "confidence": "High (82%)" if complexity <= 6 else "Medium (68%)",
            "buffer": "18%",
            "phases": phases,
            "milestones": milestones,
            "three_point": {
                "optimistic": int(total * 0.80),
                "most_likely": total,
                "pessimistic": int(total * 1.35),
            },
        }
