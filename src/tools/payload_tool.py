# import httpx
# import json
# from pydantic import BaseModel
# from typing import List, Dict, Any
# from google.cloud import storage
# import datetime

# # Cloud Run API for structured + payload generation
# PIPELINE_URL = (
#     "https://structured-pipeline-dot-glowing-jetty-477417-h9.ue.r.appspot.com/pipeline/run"
# )

# # -------- Response models -------- #

# class PipelineResult(BaseModel):
#     company_id: str
#     payload_uri: str


# class PipelineResponse(BaseModel):
#     structured_count: int
#     payload_count: int
#     results: List[Dict[str, str]]


# # -------- Helper to fetch the JSON from GCS -------- #

# async def fetch_gcs_json(payload_uri: str) -> Dict[str, Any]:
#     """
#     Fetch JSON from a *private* GCS bucket using the authenticated GCS SDK.
#     """

#     # gs://bucket/path/file.json → bucket + path
#     bucket_name = payload_uri.replace("gs://", "").split("/")[0]
#     path = "/".join(payload_uri.replace("gs://", "").split("/")[1:])

#     client = storage.Client()
#     bucket = client.bucket(bucket_name)
#     blob = bucket.blob(path)

#     if not blob.exists(client):
#         raise FileNotFoundError(f"GCS object not found: {payload_uri}")

#     text = blob.download_as_text(encoding="utf-8")
#     return json.loads(text)



# # -------- MAIN TOOL (lab 12) -------- #

# async def get_latest_structured_payload(company_id: str) -> Dict[str, Any]:
#     """
#     Lab 12 Tool 1:
#     ------------------------------------
#     Calls Cloud Run pipeline API:
#         - Builds structured extraction (Lab 5)
#         - Builds payload (Lab 6)
#         - Returns the GCS URI

#     Then:
#         - Fetches the payload JSON directly from GCS over HTTPS
#     """

#     print(f"[TOOL] Requesting structured payload for: {company_id}")

#     async with httpx.AsyncClient(timeout=120) as client:
#         resp = await client.post(
#             PIPELINE_URL,
#             json={"company_name": company_id},
#         )
#         resp.raise_for_status()

#     data = resp.json()
#     parsed = PipelineResponse(**data)

#     if not parsed.results:
#         raise RuntimeError(f"No payload results returned for {company_id}")

#     payload_uri = parsed.results[0]["payload_uri"]
#     print(f"[TOOL] Payload located at: {payload_uri}")

#     # Now fetch the actual JSON
#     payload_json = await fetch_gcs_json(payload_uri)

#     print(f"[TOOL] Retrieved payload JSON for {company_id}")
#     return payload_json



# ------------------------------------------------------------
# MCP TOOL: payload.get_latest
# ------------------------------------------------------------
# Tool returns the full payload JSON for a given company_id.
# ------------------------------------------------------------

import httpx
import json
from pydantic import BaseModel
from typing import List, Dict, Any
from google.cloud import storage

PIPELINE_URL = (
    "https://structured-pipeline-dot-glowing-jetty-477417-h9.ue.r.appspot.com/pipeline/run"
)

# ---------------- Response Models ----------------

class PipelineResult(BaseModel):
    company_id: str
    payload_uri: str

class PipelineResponse(BaseModel):
    structured_count: int
    payload_count: int
    results: List[Dict[str, str]]

# ---------------- GCS Fetch Helper ----------------

async def fetch_gcs_json(payload_uri: str) -> Dict[str, Any]:
    """
    Fetch JSON from a *private* GCS bucket using the authenticated GCS SDK.
    """
    bucket_name = payload_uri.replace("gs://", "").split("/")[0]
    path = "/".join(payload_uri.replace("gs://", "").split("/")[1:])

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)

    if not blob.exists(client):
        raise FileNotFoundError(f"GCS object not found: {payload_uri}")

    text = blob.download_as_text(encoding="utf-8")
    return json.loads(text)

# ---------------- Main Tool Logic ----------------

async def get_latest_structured_payload(company_id: str) -> Dict[str, Any]:
    """
    Lab 12 Tool 1:
    Calls Cloud Run → builds structured → builds payload → returns payload JSON
    """
    print(f"[TOOL] Requesting structured payload for: {company_id}")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            PIPELINE_URL,
            json={"company_name": company_id},
        )
        resp.raise_for_status()

    parsed = PipelineResponse(**resp.json())

    if not parsed.results:
        raise RuntimeError(f"No payload results returned for {company_id}")

    payload_uri = parsed.results[0]["payload_uri"]
    print(f"[TOOL] Payload located at: {payload_uri}")

    payload_json = await fetch_gcs_json(payload_uri)

    print(f"[TOOL] Retrieved payload JSON for {company_id}")
    return payload_json

# ---------------- MCP Export ----------------

def mcp_get_latest(company_id: str) -> Dict[str, Any]:
    """
    MCP synchronous wrapper.
    MCP tools cannot be async → we run async code inside sync wrapper.
    """
    import asyncio
    return asyncio.run(get_latest_structured_payload(company_id))

# ---------------- Manual Test ----------------

if __name__ == "__main__":
    import asyncio
    cid = input("Enter company_id: ").strip()
    obj = asyncio.run(get_latest_structured_payload(cid))
    print(json.dumps(obj, indent=2))
