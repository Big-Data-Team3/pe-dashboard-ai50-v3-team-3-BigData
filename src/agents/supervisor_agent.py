# """
# Lab 13–15 — FINAL SUPERVISOR AGENT (LLM + RAG + Structured Dashboards)
# ---------------------------------------------------------------------

# This agent:
# - Uses manual ReAct loop (NO LangChain agents)
# - Calls your existing tools:
#     • get_companies()
#     • get_latest_structured_payload()
#     • pinecone_search()
#     • detect_and_log_risks()
# - Calls LLM-based dashboard generators:
#     • generate_structured_dashboard()
#     • generate_rag_dashboard()
# - Uploads dashboards to GCS

# This version is fully stable and compatible with your environment.
# """

# import json
# import uuid
# import asyncio
# from datetime import datetime
# from pathlib import Path
# from typing import Optional, Dict, Any

# from dotenv import load_dotenv
# load_dotenv()

# # ---------------------------
# # Your tools
# # ---------------------------
# from src.tools.run_tools import get_companies
# from src.tools.payload_tool import get_latest_structured_payload
# from src.tools.rag_tool import pinecone_search
# from src.tools.risk_logger import detect_and_log_risks

# # Dashboard generators
# from src.utils.dashboard_generator import (
#     generate_structured_dashboard,
#     generate_rag_dashboard,
#     _upload_markdown
# )

# # Logging
# from src.utils.react_logger import ReActLogger

# from src.mcp.mcp_client import MCPClient


# # ============================================================
# # Supervisor Agent
# # ============================================================

# class SupervisorAgent:
#     """Manual-ReAct Supervisor Agent with LLM dashboards."""

#     def __init__(self, run_id: Optional[str] = None):
#         self.run_id = run_id or str(uuid.uuid4())
#         self.logger = ReActLogger(run_id=self.run_id)

#         print("\n=============================================")
#         print("  SUPERVISOR AGENT INITIALIZED (Option A: LLM Dashboards)")
#         print("=============================================")
#         print(f"Run ID: {self.run_id}")
#         print("Tools loaded: get_companies, payload, RAG, risk_logger, dashboards\n")

#     # --------------------------------------------------------

#     async def run(self, company_id: str) -> str:
#         """Full due diligence workflow (manual ReAct)."""

#         print("\n=============================================")
#         print(f"RUNNING DUE DILIGENCE ON: {company_id}")
#         print("=============================================\n")

#         # -----------------------------------------
#         # STEP 1 — THOUGHT
#         # -----------------------------------------
#         thought = f"Begin due diligence for: {company_id}"
#         self.logger.log_thought(thought, company_id=company_id)

#         # -----------------------------------------
#         # STEP 2 — ACTION: Validate company exists
#         # -----------------------------------------
#         self.logger.log_action("get_companies", {}, company_id)
#         company_list = get_companies()
#         self.logger.log_observation(company_list, company_id)

#         if company_id not in company_list:
#             final = f"Company '{company_id}' not found in Forbes AI50 dataset."
#             self.logger.log_final_answer(final, company_id)
#             return final

#         # --------------------------------------------------
#         # STEP 3 — ACTION: Load structured payload
#         # --------------------------------------------------
#         self.logger.log_action("get_latest_structured_payload",
#                                {"company_id": company_id}, company_id)

#         payload = await get_latest_structured_payload(company_id)

#         payload_summary = {
#             "company": payload.get("company", {}),
#             "snapshot": payload.get("snapshot", {})
#         }

#         self.logger.log_observation(payload_summary, company_id)

#         # --------------------------------------------------
#         # STEP 4 — ACTION: Fetch ALL RAG Chunks (query=None)
#         # --------------------------------------------------
#         self.logger.log_action(
#             "pinecone_search",
#             {"company_id": company_id, "query": None},
#             company_id
#         )

#         rag_all = pinecone_search(company_id, query=None, top_k=5000)
#         rag_chunks = [hit.text_snippet for hit in rag_all.results]

#         rag_preview = rag_chunks[:3]  # show first 3 in logs
#         self.logger.log_observation(rag_preview, company_id)

#         # --------------------------------------------------
#         # STEP 5 — ACTION: Detect & log risks
#         # --------------------------------------------------
#         self.logger.log_action("detect_and_log_risks",
#                                {"company_id": company_id}, company_id)

#         risk_result = await detect_and_log_risks(company_id)
#         self.logger.log_observation(risk_result, company_id)

#         # --------------------------------------------------
#         # STEP 6 — ACTION: Generate STRUCTURED dashboard (LLM)
#         # --------------------------------------------------
#         self.logger.log_thought("Generating structured dashboard",
#                                 company_id)

#         structured_md = await generate_structured_dashboard(
#             company_id=company_id,
#             payload=payload,
#             rag_chunks=rag_chunks
#         )

#         structured_path = f"data/markdown/structured/{company_id}_structured.md"

#         self.logger.log_observation(
#             {"structured_dashboard_uploaded": structured_path},
#             company_id
#         )

#         # --------------------------------------------------
#         # STEP 7 — ACTION: Generate RAG dashboard (LLM)
#         # --------------------------------------------------
#         self.logger.log_thought("Generating RAG dashboard via LLM",
#                                 company_id)

#         rag_md = await generate_rag_dashboard(company_id=company_id,
#                                               rag_chunks=rag_chunks)

#         rag_path = f"data/markdown/rag/{company_id}_rag.md"

#         self.logger.log_observation(
#             {"rag_dashboard_uploaded": rag_path},
#             company_id
#         )

#         # --------------------------------------------------
#         # STEP 8 — FINAL ANSWER
#         # --------------------------------------------------

#         final_answer = f"""
# ==============================
# Due Diligence Summary: {company_id}
# ==============================

# 1. **Company Payload Summary**
# {json.dumps(payload_summary, indent=2)}

# 2. **Risk Detection**
# {json.dumps(risk_result, indent=2)}

# 3. **Dashboards Generated**
# - STRUCTURED Dashboard → `{structured_path}`
# - RAG Dashboard → `{rag_path}`

# 4. **RAG Chunk Count**
# Total Chunks: {len(rag_chunks)}

# ==============================
# Recommendation:
# ==============================
# {"⚠️ Risks detected — review required" if risk_result.get("detected") else "✅ No major risks detected"}
# """

#         self.logger.log_final_answer(final_answer, company_id)
#         return final_answer



# # ============================================================
# # CLI
# # ============================================================

# def main():
#     import argparse
#     parser = argparse.ArgumentParser()
#     parser.add_argument("company_id")
#     args = parser.parse_args()

#     agent = SupervisorAgent()
#     result = asyncio.run(agent.run(args.company_id))
#     print(result)


# if __name__ == "__main__":
#     main()



#########################################################################################
"""
Lab 13–15 — FINAL Supervisor Agent
----------------------------------
Supports:
✔ Local Mode (payload + rag + dashboards)
✔ MCP Mode (dashboards served from MCP server)
✔ Full ReAct Logging
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

# -------------------------------
# Import your real tools
# -------------------------------
from src.tools.run_tools import get_companies
from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import pinecone_search
from src.tools.risk_logger import detect_and_log_risks

# Dashboard generator (local mode)
from src.utils.dashboard_generator import (
    generate_structured_dashboard,
    generate_rag_dashboard,
)

# ReAct logger
from src.utils.react_logger import ReActLogger


# -------------------------------
# Optional MCP client (Lab 15)
# -------------------------------
try:
    from src.mcp.mcp_client import MCPClient
    MCP_AVAILABLE = True
except Exception:
    MCP_AVAILABLE = False
    MCPClient = None


# ============================================================
# SUPERVISOR AGENT
# ============================================================

class SupervisorAgent:
    def __init__(self, use_mcp: bool = False, run_id: Optional[str] = None):
        self.use_mcp = use_mcp
        self.run_id = run_id or str(uuid.uuid4())
        self.logger = ReActLogger(run_id=self.run_id)

        print("\n=============================================")
        print("  SUPERVISOR AGENT INITIALIZED")
        print("=============================================")
        print(f"Run ID: {self.run_id}")

        if self.use_mcp:
            if not MCP_AVAILABLE:
                raise RuntimeError("MCPClient is not available but MCP mode was enabled!")

            print("🌐 Mode: MCP (Dashboards generated via MCP Server)")
            self.mcp = MCPClient()
        else:
            print("🟦 Mode: Local (Dashboards generated via local LLM)")
            print("Tools loaded: get_companies, payload, RAG, risk_logger, dashboards")

        print("\n")

    # --------------------------------------------------------
    # MAIN RUN METHOD
    # --------------------------------------------------------
    async def run(self, company_id: str) -> str:

        print("=============================================")
        print(f"RUNNING DUE DILIGENCE ON: {company_id}")
        print("=============================================\n")

        # -----------------------------------------
        # STEP 1 — THOUGHT
        # -----------------------------------------
        self.logger.log_thought("Begin due diligence", company_id=company_id)

        # -----------------------------------------
        # STEP 2 — Validate company exists
        # -----------------------------------------
        self.logger.log_action("get_companies", {}, company_id)
        companies = get_companies()
        self.logger.log_observation(companies, company_id)

        if company_id not in companies:
            msg = f"Company '{company_id}' does not exist in dataset."
            self.logger.log_final_answer(msg, company_id)
            return msg

        # -----------------------------------------
        # STEP 3 — Load payload
        # -----------------------------------------
        self.logger.log_action("get_latest_structured_payload",
                               {"company_id": company_id}, company_id)

        payload = await get_latest_structured_payload(company_id)
        self.logger.log_observation({"company": payload.get("company", {})}, company_id)

        # -----------------------------------------
        # STEP 4 — Load all RAG chunks (query=None)
        # -----------------------------------------
        self.logger.log_action(
            "pinecone_search",
            {"company_id": company_id, "query": None},
            company_id
        )

        rag_response = pinecone_search(company_id=company_id, query=None, top_k=5000)
        rag_chunks = [hit.text_snippet for hit in rag_response.results]
        short_preview = rag_chunks[:3]
        self.logger.log_observation(short_preview, company_id)

        # -----------------------------------------
        # STEP 5 — Detect & log risks
        # -----------------------------------------
        self.logger.log_action("detect_and_log_risks",
                               {"company_id": company_id}, company_id)

        risks = await detect_and_log_risks(company_id)
        self.logger.log_observation(risks, company_id)

        # -----------------------------------------
        # STEP 6 — Dashboards
        # -----------------------------------------

        # ---------- MCP Mode ----------
        if self.use_mcp:
            self.logger.log_thought("Requesting MCP structured dashboard", company_id)

            structured_resp = await self.mcp.call_tool(
                "generate_structured_dashboard",
                {"company_id": company_id}
            )
            structured_md = structured_resp.get("markdown", "# Error: No markdown returned")

            self.logger.log_observation("Structured dashboard received", company_id)

            self.logger.log_thought("Requesting MCP RAG dashboard", company_id)
            rag_resp = await self.mcp.call_tool(
                "generate_rag_dashboard",
                {"company_id": company_id}
            )
            rag_md = rag_resp.get("markdown", "# Error: No markdown returned")

            final = self._format_final(company_id, payload, rag_chunks, risks,
                                       structured_md, rag_md)
            self.logger.log_final_answer(final, company_id)
            return final

        # ---------- LOCAL MODE ----------
        else:
            self.logger.log_thought("Generating structured dashboard (local)", company_id)

            structured_md, structured_path = await generate_structured_dashboard(
                company_id=company_id,
                payload=payload,
                rag_chunks=rag_chunks
            )

            self.logger.log_observation(f"Saved → {structured_path}", company_id)

            self.logger.log_thought("Generating RAG dashboard (local)", company_id)

            rag_md, rag_path = await generate_rag_dashboard(
                company_id=company_id,
                payload=payload,
                rag_chunks=rag_chunks
            )

            self.logger.log_observation(f"Saved → {rag_path}", company_id)

            final = self._format_final(company_id, payload, rag_chunks, risks,
                                       structured_md, rag_md)
            self.logger.log_final_answer(final, company_id)
            return final

    # --------------------------------------------------------
    def _format_final(self, company_id, payload, rag_chunks, risks,
                      structured_md, rag_md) -> str:

        return f"""
=========================
FINAL DUE DILIGENCE SUMMARY — {company_id}
=========================

### Structured Dashboard
(Full Markdown Saved)

---

### RAG Dashboard
(Full Markdown Saved)

---

### Risk Detection
{json.dumps(risks, indent=2)}

### Raw Context (Preview)
**Payload (company):**
{json.dumps(payload.get('company', {}), indent=2)}

**RAG Chunks (sample):**
{json.dumps(rag_chunks[:3], indent=2)}

=========================
Completed Successfully
=========================
"""


# ============================================================
# CLI WRAPPER
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("company_id")
    parser.add_argument("--mcp", action="store_true", help="Enable MCP mode (Lab 15)")
    args = parser.parse_args()

    agent = SupervisorAgent(use_mcp=args.mcp)
    output = asyncio.run(agent.run(args.company_id))

    print("\n=================== OUTPUT ===================")
    print(output)
    print("===============================================")


if __name__ == "__main__":
    main()
