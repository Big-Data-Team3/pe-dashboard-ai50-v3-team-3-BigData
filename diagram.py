from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.workflow import Airflow
from diagrams.programming.language import Python
from diagrams.onprem.client import Users
from diagrams.aws.storage import S3


with Diagram(
    "Project ORBIT — Agentic Architecture Overview (Assignment 5, Full)",
    show=False,
    direction="TB",
):

    # ---------------------------------------------------
    # Airflow Orchestration Layer
    # ---------------------------------------------------
    with Cluster("Airflow DAGs"):
        initial_load_dag = Airflow(
            "Initial Load DAG\norbit_initial_load_dag.py"
        )
        daily_update_dag = Airflow(
            "Daily Update DAG\norbit_daily_update_dag.py"
        )
        agentic_dag = Airflow(
            "Agentic Dashboard DAG\norbit_agentic_dashboard_dag.py"
        )

    # ---------------------------------------------------
    # Agentic Services: MCP + Agents + Tools + Workflows
    # ---------------------------------------------------
    with Cluster("Agentic Services (Docker / MCP + Agents)"):

        # MCP layer
        with Cluster("MCP Layer"):
            mcp_client = Python("MCP Client\nsrc/mcp/mcp_client.py")
            mcp_server = Python("MCP Server\nsrc/server/mcp_server.py")
            mcp_config = Python("Config\nsrc/config/mcp_config.json")

        # Agents
        with Cluster("Agents"):
            planner_agent = Python("Planner Agent\nsrc/agents/planner_agent.py")
            evaluator_agent = Python("Evaluator Agent\nsrc/agents/evaluator_agent.py")
            supervisor_agent = Python("Supervisor Agent\nsrc/agents/supervisor_agent.py")

        # Tools exposed via MCP
        with Cluster("Tools (MCP Resources)"):
            core_tools = Python("Core Tools\nsrc/tools/core_tools.py")
            rag_tool = Python("RAG Tool\nsrc/tools/rag_tool.py")
            payload_tool = Python("Payload Tool\nsrc/tools/payload_tool.py")
            run_tools = Python("Run Tools\nsrc/tools/run_tools.py")
            risk_logger_tool = Python("Risk Logger Tool\nsrc/tools/risk_logger.py")

        # Workflows, prompts, and utilities
        with Cluster("Workflows, Prompts & Utils"):
            due_diligence = Python(
                "Due Diligence Graph\nsrc/workflows/due_diligence_graph.py"
            )
            hybrid_workflow = Python(
                "LangGraph Hybrid Workflow\nsrc/workflows/langgraph_hybrid_workflow.py"
            )
            dash_generator = Python(
                "Dashboard Generator\nsrc/utils/dashboard_generator.py"
            )
            react_logger = Python(
                "ReAct Logger\nsrc/utils/react_logger.py"
            )
            dash_prompt = Python(
                "Dashboard Prompt\nsrc/prompts/dashboard_system.md"
            )

        # Logging / observability
        with Cluster("Logging / Observability"):
            json_logs = Python("Structured JSON Logs\nlogs/*.jsonl")

    # ---------------------------------------------------
    # HITL + Storage
    # ---------------------------------------------------
    hitl_reviewer = Users("Human Approval\n(HITL Reviewer)")
    dashboards_store = S3("Dashboards DB or S3\n(ai50 dashboards)")

    # ---------------------------------------------------
    # Flows
    # ---------------------------------------------------

    # Airflow → MCP
    agentic_dag >> Edge(label="HTTP / CLI") >> mcp_client >> mcp_server

    # Initial / daily DAGs keep raw + dashboards up to date
    initial_load_dag >> dashboards_store
    daily_update_dag >> dashboards_store

    # MCP uses config + tools
    mcp_config >> mcp_server
    mcp_server >> Edge(label="invokes tools") >> [
        core_tools,
        rag_tool,
        payload_tool,
        run_tools,
    ]

    # Agents ReAct loop
    mcp_server >> Edge(label="task requests") >> supervisor_agent
    supervisor_agent >> Edge(label="planning") >> planner_agent
    planner_agent >> Edge(label="execution plan") >> supervisor_agent
    supervisor_agent >> Edge(label="delegate") >> evaluator_agent
    evaluator_agent >> Edge(label="critique / score") >> supervisor_agent

    # Agents drive workflows
    supervisor_agent >> Edge(label="run workflow") >> [
        due_diligence,
        hybrid_workflow,
    ]

    # Workflows generate dashboards
    due_diligence >> dash_generator
    hybrid_workflow >> dash_generator
    dash_prompt >> [mcp_server, dash_generator]
    dash_generator >> dashboards_store

    # Risk logging + ReAct trace
    supervisor_agent >> Edge(label="log_risk()") >> risk_logger_tool
    supervisor_agent >> Edge(label="ReAct trace") >> react_logger
    risk_logger_tool >> json_logs
    react_logger >> json_logs
    mcp_server >> json_logs

    # HITL path
    supervisor_agent >> Edge(label="Risk Detected") >> hitl_reviewer
    hitl_reviewer >> Edge(label="Approve / Override") >> dashboards_store
