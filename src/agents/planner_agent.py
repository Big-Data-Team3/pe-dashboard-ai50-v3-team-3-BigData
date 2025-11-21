# src/agents/planner_agent.py

def plan_due_diligence(company_id: str):
    """Produce a simple static due-diligence plan.
    Replace with LLM-based planner in advanced versions."""
    return {
        "company_id": company_id,
        "steps": [
            "generate_structured_dashboard",
            "generate_rag_dashboard",
            "evaluate_dashboards",
            "check_for_risks",
        ],
    }
