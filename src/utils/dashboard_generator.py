# """
# Dashboard Generation Utilities (FINAL)

# Generates 8-section PE dashboards using a single system prompt and:
# 1. Structured extraction (payload JSON)
# 2. RAG-based synthesis (all RAG chunks for a company)

# Both dashboards are:
# - Generated via OpenAI chat completions
# - Saved as .md files in GCS:

#   Structured:
#     gs://<BUCKET_NAME>/data/markdown/structured/{company_id}_structured_dashboard.md

#   RAG:
#     gs://<BUCKET_NAME>/data/markdown/rag/{company_id}_rag_dashboard.md
# """

# import os
# import json
# from datetime import datetime
# from typing import Dict, Any, Tuple

# from dotenv import load_dotenv

# from google.cloud import storage
# from openai import OpenAI

# from src.tools.payload_tool import get_latest_structured_payload
# from src.tools.rag_tool import pinecone_search
# from src.tools.run_tools import BUCKET_NAME  # reuse same bucket
# # if BUCKET_NAME isn’t exported from run_tools, just hardcode it instead.

# load_dotenv()

# # ----------------- OpenAI client -----------------
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# if not OPENAI_API_KEY:
#     raise RuntimeError("OPENAI_API_KEY not set in environment")

# client = OpenAI(api_key=OPENAI_API_KEY)

# # ----------------- GCS client --------------------
# storage_client = storage.Client()
# bucket = storage_client.bucket(BUCKET_NAME)

# # ----------------- Prompt loader -----------------
# PROMPT_PATH = os.path.join(
#     os.path.dirname(__file__),
#     "..",
#     "prompts",
#     "dashboard_system.md",
# )

# def load_dashboard_system_prompt() -> str:
#     with open(PROMPT_PATH, "r", encoding="utf-8") as f:
#         return f.read()


# SYSTEM_PROMPT = load_dashboard_system_prompt()


# # ----------------- LLM helper --------------------
# def _call_dashboard_llm(mode: str, company_id: str, context_json: Dict[str, Any]) -> str:
#     """
#     Call OpenAI with a unified system prompt and a mode:
#     - mode = "structured" with payload JSON
#     - mode = "rag" with rag_snippets JSON
#     """
#     # Keep context compact but faithful
#     user_msg = (
#         f"Mode: {mode}\n"
#         f"Company ID: {company_id}\n\n"
#         "Context JSON:\n"
#         f"{json.dumps(context_json, ensure_ascii=False, indent=2)}\n\n"
#         "Using this context only, generate the full 8-section PE due diligence dashboard "
#         "(same section headings as in the system prompt). "
#         "If a datapoint is missing, explicitly say 'Not disclosed'."
#     )

#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         temperature=0.2,
#         messages=[
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": user_msg},
#         ],
#     )

#     return resp.choices[0].message.content


# # ----------------- GCS helper --------------------
# def _upload_markdown(company_id: str, mode: str, markdown: str) -> str:
#     """
#     Upload markdown to GCS and return the gs:// path.

#     mode ∈ {"structured", "rag"}
#     """
#     if mode == "structured":
#         blob_path = f"data/markdown/structured/{company_id}_structured_dashboard.md"
#     else:
#         blob_path = f"data/markdown/rag/{company_id}_rag_dashboard.md"

#     blob = bucket.blob(blob_path)
#     blob.upload_from_string(markdown, content_type="text/markdown")

#     return f"gs://{BUCKET_NAME}/{blob_path}"


# # ----------------- PUBLIC API --------------------
# async def generate_structured_dashboard(company_id: str) -> Tuple[str, str]:
#     """
#     Generate a structured dashboard using the payload JSON only
#     + the unified system prompt.

#     Returns:
#         (markdown, gcs_path)
#     """
#     try:
#         payload = await get_latest_structured_payload(company_id)
#         if not isinstance(payload, dict):
#             # In case your tool returns a pydantic model, convert to dict
#             payload = json.loads(json.dumps(payload, default=lambda o: getattr(o, "__dict__", str(o))))

#         context = {
#             "company_id": company_id,
#             "payload": payload,
#             "generated_at": datetime.utcnow().isoformat() + "Z",
#         }

#         markdown = _call_dashboard_llm(
#             mode="structured",
#             company_id=company_id,
#             context_json=context,
#         )

#         gcs_path = _upload_markdown(company_id, mode="structured", markdown=markdown)
#         return markdown, gcs_path

#     except Exception as e:
#         error_md = (
#             f"# Error Generating Structured Dashboard\n\n"
#             f"**Company**: {company_id}\n"
#             f"**Error**: {str(e)}"
#         )
#         gcs_path = _upload_markdown(company_id, mode="structured", markdown=error_md)
#         return error_md, gcs_path


# async def generate_rag_dashboard(company_id: str) -> Tuple[str, str]:
#     """
#     Generate a RAG-based dashboard by:
#     - Pulling ALL chunks for the company (query=None)
#     - Feeding them as JSON context into the same system prompt.

#     Returns:
#         (markdown, gcs_path)
#     """
#     try:
#         # Get ALL vectors for the company (no query, full slice)
#         rag_response = pinecone_search(company_id=company_id, query=None, top_k=5000)

#         snippets = []
#         for hit in rag_response.results:
#             snippets.append(
#                 {
#                     "score": hit.score,
#                     "page_key": hit.page_key,
#                     "source_url": hit.source_url,
#                     "text": hit.text_snippet,
#                 }
#             )

#         context = {
#             "company_id": company_id,
#             "rag_snippets": snippets,
#             "generated_at": datetime.utcnow().isoformat() + "Z",
#         }

#         markdown = _call_dashboard_llm(
#             mode="rag",
#             company_id=company_id,
#             context_json=context,
#         )

#         gcs_path = _upload_markdown(company_id, mode="rag", markdown=markdown)
#         return markdown, gcs_path

#     except Exception as e:
#         error_md = (
#             f"# Error Generating RAG Dashboard\n\n"
#             f"**Company**: {company_id}\n"
#             f"**Error**: {str(e)}"
#         )
#         gcs_path = _upload_markdown(company_id, mode="rag", markdown=error_md)
#         return error_md, gcs_path

"""
Dashboard Generator (Structured + RAG)
--------------------------------------

Generates two types of dashboards:

1. Structured Dashboard
   - Uses structured payload JSON (from payload_tool)
   - May also use rag_chunks as additional optional context
   - Follows SYSTEM_PROMPT_STRUCTURED in dashboard_systems.md

2. RAG Dashboard
   - Uses ALL Pinecone chunks (rag_chunks)
   - Follows SYSTEM_PROMPT_RAG in dashboard_systems.md

Both dashboards are uploaded to GCS:
- data/markdown/structured/{company_id}_structured_dashboard.md
- data/markdown/rag/{company_id}_rag_dashboard.md
"""

import os
import json
import asyncio
from typing import Tuple, Dict, Any, List
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from google.cloud import storage
from src.tools.rag_tool import pinecone_search

# Load models
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------
# Load system prompt (single file)
# -------------------------------

PROMPT_PATH = Path("src/prompts/dashboard_system.md")
if not PROMPT_PATH.exists():
    raise FileNotFoundError(f"Missing dashboard prompt file: {PROMPT_PATH}")

SYSTEM_PROMPT = PROMPT_PATH.read_text().strip()


# ============================================================
# Helper: Upload markdown to GCS
# ============================================================

def _upload_markdown(company_id: str, mode: str, markdown: str) -> str:
    """
    Upload dashboard markdown to GCS with correct folder structure.

    mode ∈ {"structured", "rag"}
    """
    bucket_name = os.getenv("GCS_BUCKET_NAME", "us-central1-pe-dashboard-or-395f6975-bucket")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    folder = f"data/markdown/{mode}"
    file_name = f"{company_id}_{mode}_dashboard.md"
    gcs_path = f"{folder}/{file_name}"

    blob = bucket.blob(gcs_path)
    blob.upload_from_string(markdown, content_type="text/markdown")

    return f"gs://{bucket_name}/{gcs_path}"


# ============================================================
# Helper: Call OpenAI LLM for dashboard generation
# ============================================================

def _call_dashboard_llm(
    mode: str,
    company_id: str,
    context_json: Dict[str, Any],
) -> str:
    """
    Internal wrapper to generate dashboards using the unified system prompt.
    """

    mode_title = "STRUCTURED DASHBOARD" if mode == "structured" else "RAG DASHBOARD"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Generate a **{mode_title}** for company: {company_id}\n\n"
                f"Context JSON:\n{json.dumps(context_json, indent=2)}"
            )
        }
    ]

    response = client.chat.completions.create(
        model=os.getenv("DASHBOARD_MODEL", "gpt-4o-mini"),
        messages=messages,
        temperature=0.1,
        max_tokens=3000,
    )

    return response.choices[0].message.content


# ============================================================
# Generate Structured Dashboard (payload + optional rag_chunks)
# ============================================================

async def generate_structured_dashboard(
    company_id: str,
    payload: Dict[str, Any],
    rag_chunks: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Generate a structured dashboard using:
    - structured payload JSON
    - rag_chunks as optional auxiliary context

    Supervisor agent MUST provide:
        payload: dict
        rag_chunks: list of rag_hit dicts

    Returns:
        (markdown, gcs_path)
    """

    try:
        # Ensure payload is JSON-friendly
        if not isinstance(payload, dict):
            payload = json.loads(json.dumps(payload, default=lambda o: getattr(o, "__dict__", str(o))))

        context = {
            "company_id": company_id,
            "payload": payload,
            "rag_chunks": rag_chunks,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        markdown = _call_dashboard_llm(
            mode="structured",
            company_id=company_id,
            context_json=context,
        )

        gcs_path = _upload_markdown(company_id, "structured", markdown)
        return markdown, gcs_path

    except Exception as e:
        error_md = (
            f"# Error Generating Structured Dashboard\n\n"
            f"**Company**: {company_id}\n"
            f"**Error**: {str(e)}"
        )
        gcs_path = _upload_markdown(company_id, "structured", error_md)
        return error_md, gcs_path


# ============================================================
# Generate RAG Dashboard (rag_chunks only)
# ============================================================

async def generate_rag_dashboard(
    company_id: str,
    rag_chunks: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Generate a RAG-based dashboard using all pinecone chunks.

    Supervisor agent MUST provide:
        rag_chunks: list of dicts from pinecone_search

    Returns:
        (markdown, gcs_path)
    """

    try:
        context = {
            "company_id": company_id,
            "rag_snippets": rag_chunks,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        markdown = _call_dashboard_llm(
            mode="rag",
            company_id=company_id,
            context_json=context,
        )

        gcs_path = _upload_markdown(company_id, "rag", markdown)
        return markdown, gcs_path

    except Exception as e:
        error_md = (
            f"# Error Generating RAG Dashboard\n\n"
            f"**Company**: {company_id}\n"
            f"**Error**: {str(e)}"
        )
        gcs_path = _upload_markdown(company_id, "rag", error_md)
        return error_md, gcs_path


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    async def _selftest():
        cid = "anthropic"

        # Fake data for testing
        payload = {"company": {"name": "Anthropic"}, "snapshot": {}}

        rag_response = pinecone_search(cid, query=None, top_k=1000)
        rag_chunks = [
            {"score": h.score, "page_key": h.page_key, "source_url": h.source_url, "text": h.text_snippet}
            for h in rag_response.results
        ]

        print("\nTesting structured dashboard...\n")
        md_s, path_s = await generate_structured_dashboard(cid, payload, rag_chunks)
        print("Wrote to:", path_s)

        print("\nTesting RAG dashboard...\n")
        md_r, path_r = await generate_rag_dashboard(cid, rag_chunks)
        print("Wrote to:", path_r)

    asyncio.run(_selftest())
