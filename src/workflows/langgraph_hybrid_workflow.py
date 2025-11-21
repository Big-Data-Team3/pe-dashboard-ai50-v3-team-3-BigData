"""
Hybrid LangGraph Workflow (Labs 17–18)
--------------------------------------

Uses SupervisorAgent (from Labs 12–15) as the data generation step
inside a LangGraph workflow.

Nodes:
1. Planner
2. SupervisorAgentRunner (calls supervisor_agent.run)
3. Evaluator
4. RiskDetector
5. HITL
6. FinalDecision
"""

import asyncio
import json
from typing import TypedDict, List

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.planner_agent import plan_due_diligence
from src.agents.evaluator_agent import evaluate_dashboards
from src.agents.supervisor_agent import SupervisorAgent


# ============================================================
# Workflow State
# ============================================================

class State(TypedDict):
    company_id: str
    run_id: str

    plan: dict | None
    structured_md: str | None
    rag_md: str | None

    evaluation: dict | None
    risk_detected: bool
    risk_keywords: List[str]

    hitl_required: bool
    hitl_approved: bool | None

    final_decision: str | None
    path: List[str]


# ============================================================
# Nodes
# ============================================================

def planner_node(state: State) -> State:
    state["plan"] = plan_due_diligence(state["company_id"])
    state["path"].append("planner")
    return state


async def supervisor_agent_node(state: State) -> State:
    """
    CALLS SupervisorAgent (Labs 12–15)
    Generates the local + MCP dashboards inside ReAct loop.
    """
    agent = SupervisorAgent(use_mcp=True)   # MCP mode enabled
    result = await agent.run(state["company_id"])

    # Extract structured + rag markdown from agent result:
    # Since SupervisorAgent returns a FINAL SUMMARY block,
    # we read the saved markdown files from agent internals.
    # To keep it simple, we just read local files generated.
    import glob

    structured_files = glob.glob(f"dashboards/structured/{state['company_id']}*.md")
    rag_files = glob.glob(f"dashboards/rag/{state['company_id']}*.md")

    if structured_files:
        state["structured_md"] = open(structured_files[-1]).read()
    if rag_files:
        state["rag_md"] = open(rag_files[-1]).read()

    # Even if no files found, fallback:
    state["structured_md"] = state["structured_md"] or "No structured content returned."
    state["rag_md"] = state["rag_md"] or "No rag content returned."

    state["path"].append("supervisor_agent")
    return state


def evaluator_node(state: State) -> State:
    state["evaluation"] = evaluate_dashboards(
        state["structured_md"] or "",
        state["rag_md"] or ""
    )
    state["path"].append("evaluator")
    return state


def risk_detector_node(state: State) -> State:
    text = (state["structured_md"] or "") + " " + (state["rag_md"] or "")
    text = text.lower()

    keywords = ["breach", "layoff", "fraud", "lawsuit"]
    found = [k for k in keywords if k in text]

    state["risk_detected"] = bool(found)
    state["risk_keywords"] = found
    state["hitl_required"] = bool(found)

    state["path"].append("risk_detector")
    return state


def hitl_node(state: State) -> State:
    print("\n⚠ HITL CHECKPOINT")
    print("Risks found:", state["risk_keywords"])
    resp = input("Approve? (y/n): ")
    state["hitl_approved"] = (resp.lower().strip() == "y")

    state["path"].append("hitl")
    return state


def auto_approve_node(state: State) -> State:
    state["hitl_approved"] = True
    state["path"].append("auto_approve")
    return state


def final_decision_node(state: State) -> State:
    decision = "APPROVE" if state["hitl_approved"] else "REJECT"
    state["final_decision"] = decision
    state["path"].append("final_decision")
    return state


# ============================================================
# Router
# ============================================================

def route_after_risk(state: State):
    return "hitl" if state["risk_detected"] else "auto"


# ============================================================
# Build Graph
# ============================================================

def build_graph():
    g = StateGraph(State)

    g.add_node("planner", planner_node)
    g.add_node("supervisor_agent", supervisor_agent_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("risk_detector", risk_detector_node)
    g.add_node("hitl", hitl_node)
    g.add_node("auto", auto_approve_node)
    g.add_node("final", final_decision_node)

    g.set_entry_point("planner")

    g.add_edge("planner", "supervisor_agent")
    g.add_edge("supervisor_agent", "evaluator")
    g.add_edge("evaluator", "risk_detector")

    g.add_conditional_edges(
        "risk_detector",
        route_after_risk,
        {"hitl": "hitl", "auto": "auto"}
    )

    g.add_edge("hitl", "final")
    g.add_edge("auto", "final")
    g.add_edge("final", END)

    return g.compile(checkpointer=MemorySaver())


# ============================================================
# Runner
# ============================================================

def run(company_id: str, run_id: str):
    initial: State = {
        "company_id": company_id,
        "run_id": run_id,
        "plan": None,
        "structured_md": None,
        "rag_md": None,
        "evaluation": None,
        "risk_detected": False,
        "risk_keywords": [],
        "hitl_required": False,
        "hitl_approved": None,
        "final_decision": None,
        "path": []
    }

    app = build_graph()

    # REQUIRED FOR MEMORY CHECKPOINTER
    config = {"configurable": {"thread_id": run_id}}

    final = None

    # Because supervisor_agent_node is async → we MUST use astream()
    async def run_async():
        nonlocal final
        async for event in app.astream(initial, config=config):
            node = list(event.keys())[0]
            print(f"Completed node: {node}")
            final = event[node]

    # Run the async loop
    asyncio.run(run_async())

    print("\n=== FINAL DECISION ===\n", final["final_decision"])
    print("Path:", " → ".join(final["path"]))
    return final


if __name__ == "__main__":
    import uuid, sys
    run(sys.argv[1], str(uuid.uuid4()))
