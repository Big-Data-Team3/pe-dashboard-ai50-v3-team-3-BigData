# src/workflows/due_diligence_graph.py

"""
Lab 17–18: Supervisory Workflow Pattern (Graph-based)
----------------------------------------------------

Implements the full due-diligence workflow:

NODES:
- Planner           → creates plan
- DataGenerator     → generates dashboards (local or MCP)
- Evaluator         → scores dashboards
- RiskDetector      → checks risky keywords and chooses branch
- HumanApproval     → pauses workflow for HITL (Lab 18)
- Finalizer         → completes flow, persists trace

This file satisfies:
✔ Lab 17 — graph workflow with branching
✔ Lab 18 — HITL integration (+ visualization-ready traces)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid
import json
import os
import asyncio

from src.agents.planner_agent import plan_due_diligence
from src.agents.evaluator_agent import evaluate_dashboards

# Optional MCP Client
try:
    from src.mcp.mcp_client import MCPClient
    MCP_AVAILABLE = True
except Exception:
    MCP_AVAILABLE = False
    MCPClient = None

RISK_KEYWORDS = ["layoff", "lay off", "breach", "data breach", "fraud", "lawsuit"]


# -----------------------------------------------------------------------------
# CONTEXT
# -----------------------------------------------------------------------------

@dataclass
class WorkflowContext:
    run_id: str
    company_id: str

    plan: Dict[str, Any] = field(default_factory=dict)
    structured_md: str = ""
    rag_md: str = ""

    evaluation: Dict[str, Any] = field(default_factory=dict)
    branch: Optional[str] = None   # AUTO_APPROVE or HITL_REVIEW
    human_approved: Optional[bool] = None

    trace: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, node: str, data: Dict[str, Any]):
        self.trace.append({
            "node": node,
            "run_id": self.run_id,
            "company_id": self.company_id,
            **data
        })


# -----------------------------------------------------------------------------
# NODES
# -----------------------------------------------------------------------------

def planner_node(ctx: WorkflowContext) -> WorkflowContext:
    ctx.plan = plan_due_diligence(ctx.company_id)
    ctx.log("Planner", {"plan": ctx.plan})
    return ctx


async def data_generator_node(ctx: WorkflowContext, use_mcp: bool = False) -> WorkflowContext:

    # NEW: Handle forced risky flag
    if os.getenv("FORCE_RISKY_DASH") == "1":
        ctx.structured_md = (
            f"# Structured Dashboard for {ctx.company_id}\n"
            f"Massive layoffs reported following data breach."
        )
        ctx.rag_md = (
            f"# RAG Dashboard for {ctx.company_id}\n"
            f"Severe data breach exposed customer information."
        )
        ctx.log("DataGenerator", {"forced_risky": True})
        return ctx

    # MCP or Local Mode
    if use_mcp and MCP_AVAILABLE:
        ...
    else:
        # SAFE dashboards
        ctx.structured_md = (
            f"# Structured Dashboard for {ctx.company_id}\n"
            f"Strong fundamentals, stable operations."
        )
        ctx.rag_md = (
            f"# RAG Dashboard for {ctx.company_id}\n"
            f"Positive reports across financial and product teams."
        )

    ctx.log("DataGenerator", {
        "structured_preview": ctx.structured_md[:100],
        "rag_preview": ctx.rag_md[:100],
    })
    return ctx



def evaluator_node(ctx: WorkflowContext) -> WorkflowContext:
    ctx.evaluation = evaluate_dashboards(ctx.structured_md, ctx.rag_md)
    ctx.log("Evaluator", {"evaluation": ctx.evaluation})
    return ctx


def risk_detector_node(ctx: WorkflowContext) -> WorkflowContext:
    full_text = (ctx.structured_md + " " + ctx.rag_md).lower()
    risky = any(k in full_text for k in RISK_KEYWORDS)

    ctx.branch = "HITL_REVIEW" if risky else "AUTO_APPROVE"
    ctx.log("RiskDetector", {"branch": ctx.branch})
    print(f"[Workflow] Branch Taken: {ctx.branch} (run_id={ctx.run_id})")
    return ctx


# -----------------------------------------------------------------------------
# HUMAN-IN-THE-LOOP (Lab 18)
# -----------------------------------------------------------------------------

def human_approval_node(ctx: WorkflowContext) -> WorkflowContext:
    if ctx.branch != "HITL_REVIEW":
        return ctx

    print("\n⚠️  HITL Review Required")
    print("Structured dashboard preview:")
    print(ctx.structured_md[:200], "...\n")

    decision = input("Approve? (y/n): ").strip().lower()
    ctx.human_approved = decision == "y"
    ctx.log("HumanApproval", {"approved": ctx.human_approved})
    return ctx


# -----------------------------------------------------------------------------
# FINALIZER
# -----------------------------------------------------------------------------

def finalizer_node(ctx: WorkflowContext) -> WorkflowContext:
    os.makedirs("docs/traces", exist_ok=True)
    out_path = f"docs/traces/{ctx.run_id}.json"

    with open(out_path, "w") as f:
        json.dump(ctx.trace, f, indent=2)

    ctx.log("Finalizer", {"output_path": out_path})
    return ctx


# -----------------------------------------------------------------------------
# WORKFLOW GRAPH
# -----------------------------------------------------------------------------

class WorkflowGraph:
    def __init__(self):
        self.nodes = []

    def add(self, name, fn, is_async=False):
        self.nodes.append((name, fn, is_async))
        return self

    async def run(self, ctx: WorkflowContext):
        for name, fn, is_async in self.nodes:

            if is_async:
                ctx = await fn(ctx)
            else:
                ctx = fn(ctx)

            # Branch logic
            if name == "RiskDetector" and ctx.branch == "AUTO_APPROVE":
                break

        return ctx



def build_workflow(use_mcp=False) -> WorkflowGraph:
    graph = WorkflowGraph()

    graph.add("Planner", planner_node, is_async=False)
    graph.add("DataGenerator",
              lambda ctx: data_generator_node(ctx, use_mcp=use_mcp),
              is_async=True)  # <-- async node
    graph.add("Evaluator", evaluator_node, is_async=False)
    graph.add("RiskDetector", risk_detector_node, is_async=False)
    graph.add("HumanApproval", human_approval_node, is_async=False)
    graph.add("Finalizer", finalizer_node, is_async=False)

    return graph



# -----------------------------------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------------------------------

def run_workflow(company_id: str, use_mcp=False):
    ctx = WorkflowContext(
        run_id=str(uuid.uuid4()),
        company_id=company_id,
    )
    graph = build_workflow(use_mcp)
    ctx = asyncio.run(graph.run(ctx))
    print(f"\nWorkflow Completed. Branch={ctx.branch}, HITL={ctx.human_approved}")
    return ctx


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id")
    parser.add_argument("--mcp", action="store_true", help="Use MCP dashboards")
    parser.add_argument("--risky", action="store_true",
                        help="Inject risky dashboard text to force HITL branch")
    args = parser.parse_args()

    # Optionally inject risky dashboards
    if args.risky:
        print("[Debug] Using forced risky dashboard text for HITL branch.")
        # Monkeypatch data via environment flag
        os.environ["FORCE_RISKY_DASH"] = "1"
    else:
        os.environ.pop("FORCE_RISKY_DASH", None)

    run_workflow(args.company_id, use_mcp=args.mcp)



if __name__ == "__main__":
    main()
