import pytest
from src.workflows.due_diligence_graph import run_workflow, WorkflowContext

def test_auto_approve_branch(monkeypatch):
    # Monkeypatch data generator to return safe dashboards
    monkeypatch.setattr(
        "src.workflows.due_diligence_graph.data_generator_node",
        lambda ctx, use_mcp=False: ctx.__dict__.update({
            "structured_md": "Strong fundamentals.",
            "rag_md": "Positive growth."
        }) or ctx
    )

    ctx: WorkflowContext = run_workflow("anthropic")
    assert ctx.branch == "AUTO_APPROVE"
    assert ctx.human_approved is None


def test_hitl_branch(monkeypatch):
    # Monkeypatch dashboards with risky language
    monkeypatch.setattr(
        "src.workflows.due_diligence_graph.data_generator_node",
        lambda ctx, use_mcp=False: ctx.__dict__.update({
            "structured_md": "Massive layoffs reported.",
            "rag_md": "Data breach exposed customer info."
        }) or ctx
    )

    # Auto-approve HITL inside test
    monkeypatch.setattr("builtins.input", lambda _: "y")

    ctx: WorkflowContext = run_workflow("anthropic")
    assert ctx.branch == "HITL_REVIEW"
    assert ctx.human_approved is True
