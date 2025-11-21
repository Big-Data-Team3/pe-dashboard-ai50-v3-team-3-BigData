"""
MCP SERVER (Labs 14–15)
------------------------
Exposes tools, resources, and prompts via HTTP for use by
a Supervisor Agent or MCP Inspector.

Endpoints provided:

TOOLS:
 - POST /tool/generate_structured_dashboard
 - POST /tool/generate_rag_dashboard

RESOURCES:
 - GET  /resource/ai50/companies

PROMPTS:
 - GET  /prompt/pe-dashboard

HEALTH:
 - GET  /health
"""

import os
import json
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()

# Tools
from src.tools.run_tools import get_companies
from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import pinecone_search
from src.utils.dashboard_generator import (
    generate_structured_dashboard,
    generate_rag_dashboard,
)

# -------------------------------------------------------
# FASTAPI SETUP
# -------------------------------------------------------
app = FastAPI(
    title="MCP Server – PE Dashboard Tools",
    description="Provides tools/resources/prompts for Supervisor Agent (Labs 14–15)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow localhost use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------
# Pydantic Models
# -------------------------------------------------------

class DashboardRequest(BaseModel):
    company_id: str = Field(..., example="anthropic")


class DashboardResponse(BaseModel):
    company_id: str
    markdown: str
    gcs_path: Optional[str]


class CompanyListResponse(BaseModel):
    company_ids: List[str]


class PromptResponse(BaseModel):
    system_prompt: str


# =======================================================
# HEALTH CHECK
# =======================================================

@app.get("/health", tags=["Health"], summary="Health Check")
async def health_check():
    return {"status": "ok"}


# =======================================================
# RESOURCES
# =======================================================

@app.get(
    "/resource/ai50/companies",
    tags=["Resources"],
    summary="List all Forbes AI50 companies",
    response_model=CompanyListResponse
)
async def resource_list_ai50_companies():
    try:
        return CompanyListResponse(company_ids=get_companies())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =======================================================
# PROMPTS
# =======================================================

@app.get(
    "/prompt/pe-dashboard",
    tags=["Prompts"],
    summary="Return the unified PE dashboard system prompt",
    response_model=PromptResponse
)
async def prompt_pe_dashboard():
    try:
        path = os.path.join("src", "prompts", "dashboard_system.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return PromptResponse(system_prompt=content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =======================================================
# TOOLS: STRUCTURED DASHBOARD
# =======================================================

@app.post(
    "/tool/generate_structured_dashboard",
    tags=["Tools"],
    summary="Generate Structured PE Dashboard",
    description="Builds an 8-section dashboard using structured payload + all RAG chunks.",
    response_model=DashboardResponse
)
async def generate_structured_dashboard_api(request: DashboardRequest):
    try:
        company_id = request.company_id

        # Pull structured payload
        payload = await get_latest_structured_payload(company_id)

        # Pull ALL RAG chunks
        rag_resp = pinecone_search(company_id=company_id, query=None, top_k=5000)
        rag_chunks = [hit.text_snippet for hit in rag_resp.results]

        # Generate dashboard
        markdown, gcs_path = await generate_structured_dashboard(
            company_id=company_id,
            payload=payload,
            rag_chunks=rag_chunks
        )

        return DashboardResponse(
            company_id=company_id,
            markdown=markdown,
            gcs_path=gcs_path
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Structured dashboard error: {str(e)}"
        )


# =======================================================
# TOOLS: RAG DASHBOARD
# =======================================================

@app.post(
    "/tool/generate_rag_dashboard",
    tags=["Tools"],
    summary="Generate RAG PE Dashboard",
    description="Builds a dashboard using ALL vector DB text chunks for the company.",
    response_model=DashboardResponse
)
async def generate_rag_dashboard_api(request: DashboardRequest):
    try:
        company_id = request.company_id

        # Pull ALL chunks (query=None)
        rag_resp = pinecone_search(company_id, query=None, top_k=5000)

        rag_chunks = []
        for hit in rag_resp.results:
            rag_chunks.append({
                "score": hit.score,
                "page_key": hit.page_key,
                "source_url": hit.source_url,
                "text": hit.text_snippet
            })

        # Generate dashboard
        markdown, gcs_path = await generate_rag_dashboard(
            company_id=company_id,
            rag_chunks=rag_chunks
        )

        return DashboardResponse(
            company_id=company_id,
            markdown=markdown,
            gcs_path=gcs_path
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG dashboard error: {str(e)}"
        )




# """
# MCP Server for Dashboard Generation (Lab 14)

# Exposes:
# - Tools:
#     * /tool/generate_structured_dashboard
#     * /tool/generate_rag_dashboard
# - Resources:
#     * /resource/ai50/companies
# - Prompts:
#     * /prompt/pe-dashboard

# This server is stateless and safe for container deployment.
# """

# import os
# import json
# from typing import Dict, Any
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from dotenv import load_dotenv
# load_dotenv()
# # ────────────────────────────────────────────
# # REQUIRED TOOL IMPORTS FOR DASHBOARD GENERATION
# # ────────────────────────────────────────────
# from src.tools.payload_tool import get_latest_structured_payload
# from src.tools.rag_tool import pinecone_search
# from src.tools.run_tools import get_companies

# # Import your real dashboard generator
# from src.utils.dashboard_generator import (
#     generate_structured_dashboard,
#     generate_rag_dashboard
# )

# # Import your tools
# from src.tools.run_tools import get_companies

# # ------------------------------------------------------------------------------
# # FastAPI App
# # ------------------------------------------------------------------------------

# app = FastAPI(title="MCP Server", version="1.0")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ------------------------------------------------------------------------------
# # MODELS
# # ------------------------------------------------------------------------------

# class DashboardRequest(BaseModel):
#     company_id: str

# # ------------------------------------------------------------------------------
# # HEALTH CHECK
# # ------------------------------------------------------------------------------

# @app.get("/health")
# def health():
#     return {"status": "ok"}

# # ------------------------------------------------------------------------------
# # RESOURCE — List all AI50 companies
# # ------------------------------------------------------------------------------

# @app.get("/resource/ai50/companies")
# def list_ai50_companies():
#     try:
#         return {"company_ids": get_companies()}
#     except Exception as e:
#         raise HTTPException(500, f"Error: {str(e)}")

# # ------------------------------------------------------------------------------
# # PROMPT — PE dashboard template (8-section)
# # ------------------------------------------------------------------------------

# @app.get("/prompt/pe-dashboard")
# def pe_dashboard_prompt():
#     with open("src/prompts/dashboard_system.md", "r", encoding="utf-8") as f:
#         text = f.read()
#     return {"prompt": text}

# # ------------------------------
# # STRUCTURED DASHBOARD TOOL
# # ------------------------------
# @app.post("/tool/generate_structured_dashboard")
# async def generate_structured_dashboard_api(request: Dict[str, str]):
#     try:
#         company_id = request.get("company_id")
#         if not company_id:
#             return {"detail": "company_id missing"}

#         # Pull payload
#         payload = await get_latest_structured_payload(company_id)

#         # Pull ALL RAG chunks
#         rag_response = pinecone_search(company_id=company_id, query=None, top_k=5000)
#         rag_chunks = [hit.text_snippet for hit in rag_response.results]

#         # Call generator
#         markdown, gcs_path = await generate_structured_dashboard(
#             company_id=company_id,
#             payload=payload,
#             rag_chunks=rag_chunks
#         )

#         return {"markdown": markdown, "gcs_path": gcs_path}

#     except Exception as e:
#         return {"detail": f"Structured dashboard error: {str(e)}"}


# # ------------------------------
# # RAG DASHBOARD TOOL
# # ------------------------------
# @app.post("/tool/generate_rag_dashboard")
# async def generate_rag_dashboard_api(request: Dict[str, str]):
#     try:
#         company_id = request["company_id"]

#         # 1. Load ALL RAG chunks (query=None returns full slice)
#         rag_resp = pinecone_search(company_id, query=None, top_k=5000)

#         rag_chunks = []
#         for hit in rag_resp.results:
#             rag_chunks.append({
#                 "score": hit.score,
#                 "page_key": hit.page_key,
#                 "source_url": hit.source_url,
#                 "text": hit.text_snippet,
#             })

#         # 2. Call generator correctly
#         markdown, gcs_path = await generate_rag_dashboard(
#             company_id=company_id,
#             rag_chunks=rag_chunks
#         )

#         return {"markdown": markdown, "gcs_path": gcs_path}

#     except Exception as e:
#         return {"detail": f"RAG dashboard error: {str(e)}"}


