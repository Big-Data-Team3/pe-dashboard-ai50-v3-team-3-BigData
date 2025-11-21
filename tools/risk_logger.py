"""
risk_logger.py
-----------------------------------------
Risk event detection + logging tool for
AI-50 project (Assignment 12+).

Sources used:
  • Payload events (Lab 5–6)
  • Pinecone RAG chunks
  • No external APIs

Writes:
  gs://<BUCKET>/data/risk_logs/<company_id>.jsonl
-----------------------------------------
"""


# -----------------------------------------
# Fix PYTHONPATH so src/ becomes importable
# -----------------------------------------
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

# -----------------------------------------
# Standard imports
# -----------------------------------------
import json
import datetime
from typing import Dict, Any, List

from google.cloud import storage

# -----------------------------------------
# Now imports work correctly
# -----------------------------------------
from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import pinecone_search


# ------------------------
# CONFIG
# ------------------------
BUCKET_NAME = "us-central1-pe-dashboard-or-395f6975-bucket"
RISK_PREFIX = "data/risk_logs/"

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


# ------------------------
# Keyword dictionaries
# ------------------------
LAYOFF_KEYWORDS = [
    "layoff", "laid off", "job cuts", "headcount reduction", "downsizing",
    "cut roles", "employees let go", "fired", "redundancies"
]

BREACH_KEYWORDS = [
    "data breach", "security incident", "cyberattack",
    "ransomware", "hacked", "security breach"
]

BANKRUPTCY_KEYWORDS = [
    "bankruptcy", "chapter 11", "insolvent", "shut down",
    "ceasing operations", "wind down", "closing"
]

LEADERSHIP_KEYWORDS = [
    "stepped down", "resigned", "fired as ceo", "leadership change",
    "departure", "terminated as ceo"
]

LEGAL_KEYWORDS = [
    "lawsuit", "sued", "regulatory action", "investigation",
    "fined", "class action", "complaint filed"
]


ALL_SIGNALS = {
    "layoff": LAYOFF_KEYWORDS,
    "breach": BREACH_KEYWORDS,
    "bankruptcy": BANKRUPTCY_KEYWORDS,
    "leadership_exit": LEADERSHIP_KEYWORDS,
    "legal_issue": LEGAL_KEYWORDS,
}


def keyword_match(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


# -----------------------------------------------------
# LOG RISK EVENT INTO GCS
# -----------------------------------------------------

def log_risk_signal(company_id: str, signal_type: str, details: Dict[str, Any]) -> str:
    """
    Appends a new risk record to:
      gs://bucket/data/risk_logs/<company_id>.jsonl
    """

    log_path = f"{RISK_PREFIX}{company_id}.jsonl"
    blob = bucket.blob(log_path)

    record = {
        "company_id": company_id,
        "signal_type": signal_type,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "details": details,
    }

    line = json.dumps(record, ensure_ascii=False) + "\n"

    # append if exists else create
    if blob.exists():
        blob.upload_from_string(
            blob.download_as_text() + line,
            content_type="application/jsonl"
        )
    else:
        blob.upload_from_string(line, content_type="application/jsonl")

    return f"gs://{BUCKET_NAME}/{log_path}"


# -----------------------------------------------------
# RISK DETECTION ENGINE
# -----------------------------------------------------

async def detect_and_log_risks(company_id: str) -> Dict[str, Any]:
    """
    Fully automatic:

    1. Load payload for company
    2. Scan events for risk signals
    3. Scan RAG vectors for signals
    4. Log all detected risks
    5. Return summary (MCP friendly)
    """

    detected: List[Dict[str, Any]] = []

    # ----------------------------
    # STEP 1 — PAYLOAD EVENTS
    # ----------------------------
    try:
        payload = await get_latest_structured_payload(company_id)
        events = payload.get("events", [])

        for e in events:
            text = (e.get("description") or "") + " " + (e.get("title") or "")

            for signal_type, keywords in ALL_SIGNALS.items():
                if keyword_match(text, keywords):
                    uri = log_risk_signal(company_id, signal_type, e)
                    detected.append({
                        "source": "payload",
                        "signal_type": signal_type,
                        "details": e,
                        "logged_to": uri
                    })
    except Exception as ex:
        pass  # payload missing is allowed


    # ----------------------------
    # STEP 2 — RAG SEARCH
    # ----------------------------
    for signal_type, keywords in ALL_SIGNALS.items():

        # Run semantic search for the *signal type*
        rag_resp = pinecone_search(company_id, query=signal_type, top_k=30)

        for hit in rag_resp.results:
            if keyword_match(hit.text_snippet, keywords):
                uri = log_risk_signal(company_id, signal_type, {
                    "page_key": hit.page_key,
                    "text_snippet": hit.text_snippet,
                    "score": hit.score,
                    "source_url": hit.source_url,
                })
                detected.append({
                    "source": "rag",
                    "signal_type": signal_type,
                    "details": {
                        "page_key": hit.page_key,
                        "snippet": hit.text_snippet,
                        "score": hit.score,
                        "url": hit.source_url
                    },
                    "logged_to": uri
                })


    # ----------------------------
    # FINISH
    # ----------------------------
    if not detected:
        return {
            "company_id": company_id,
            "detected": False,
            "summary": "No risk events detected."
        }

    return {
        "company_id": company_id,
        "detected": True,
        "events": detected,
    }


# -----------------------------------------------------
# LOCAL TESTING (python src/tools/risk_logger.py)
# -----------------------------------------------------

if __name__ == "__main__":
    import asyncio
    cid = input("Enter company_id: ").strip()
    out = asyncio.run(detect_and_log_risks(cid))
    print(json.dumps(out, indent=2))
