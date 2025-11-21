# orbit_agentic_dashboard_dag.py

from datetime import datetime, timedelta
import asyncio

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.mcp.mcp_client import MCPClient


# -------- Task 1: fetch list of AI50 company ids via MCP --------
def fetch_ai50_companies(**context):
    mcp = MCPClient()
    resp = asyncio.run(mcp.get_resource("ai50_companies"))

    # Expect: {"company_ids": ["abridge", "anthropic", ...]}
    company_ids = resp.get("company_ids", [])

    print(f"[fetch_ai50_companies] MCP response: {resp}")
    print(f"[fetch_ai50_companies] Fetched {len(company_ids)} company ids")

    # IMPORTANT: return list so Airflow stores it in XCom
    return company_ids


# -------- Task 2: loop over company_ids and call MCP tool --------
def generate_dashboards_for_all(**context):
    import asyncio

    ti = context["ti"]
    companies = ti.xcom_pull(task_ids="fetch_ai50_companies")

    print(f"[generate_mcp_dashboards] Companies to process: {companies}")

    if not companies:
        raise ValueError("XCom returned empty company list.")

    mcp = MCPClient()
    run_id = context["dag_run"].run_id

    for company_id in companies:
        print(f"\n========== Processing {company_id} ==========")

        # -----------------------------------------
        # 1. STRUCTURED DASHBOARD (mandatory)
        # -----------------------------------------
        structured_success = False

        try:
            payload_struct = {
                "company_id": company_id,
                "run_id": run_id,
                "risky": False
            }

            resp_structured = asyncio.run(
                mcp.call_tool("generate_structured_dashboard", payload_struct)
            )

            print(f"[OK] Structured dashboard generated for {company_id}")
            print(resp_structured)

            structured_success = True

        except Exception as e:
            print(f"[ERROR] Structured dashboard failed for {company_id}: {e}")
            print(f"[SKIP] Skipping RAG dashboard for {company_id}")
            continue   # <<<<<< SKIP RAG + move to next company

        # -----------------------------------------
        # 2. RAG DASHBOARD (only if structured OK)
        # -----------------------------------------
        if structured_success:
            try:
                payload_rag = {"company_id": company_id}

                resp_rag = asyncio.run(
                    mcp.call_tool("generate_rag_dashboard", payload_rag)
                )

                print(f"[OK] RAG dashboard generated for {company_id}")
                print(resp_rag)

            except Exception as e:
                print(f"[ERROR] RAG dashboard failed for {company_id}: {e}")

        print(f"========== Finished {company_id} ==========\n")

# ---------------- DAG definition ----------------

default_args = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="orbit_agentic_dashboard_dag",
    default_args=default_args,
    start_date=datetime(2025, 11, 19),
    schedule_interval="@daily",
    catchup=False,
) as dag:

    fetch_task = PythonOperator(
        task_id="fetch_ai50_companies",
        python_callable=fetch_ai50_companies,
    )

    generate_task = PythonOperator(
        task_id="generate_mcp_dashboards",
        python_callable=generate_dashboards_for_all,
    )

    # Task order: 1 -> 2
    fetch_task >> generate_task
