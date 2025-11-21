import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone
from pydantic import BaseModel

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "ai50-rag-index")

EMBED_MODEL = "text-embedding-3-large"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# detect dimension properly
try:
    INDEX_DIM = index.describe_index_stats()["dimension"]
except Exception:
    INDEX_DIM = index.describe()["dimension"]
print(f"[RAG] Pinecone index dim = {INDEX_DIM}")

# ---------------- MODELS ----------------
class RagHit(BaseModel):
    score: float
    page_key: str
    text_snippet: str
    source_url: str

class RagSearchResponse(BaseModel):
    company_id: str
    query: Optional[str]
    results: List[RagHit]

# ---------------- HELPERS ----------------
def embed_query(text: str) -> List[float]:
    """Convert text query into embedding."""
    resp = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=[text]
    )
    return resp.data[0].embedding

# ---------------- CORE FUNCTION ----------------
def pinecone_search(company_id: str, query: Optional[str], top_k: int = 10) -> RagSearchResponse:
    """
    Dual-mode RAG search:
    - If query is None → return ALL vectors for the company
    - If query is provided → semantic RAG search
    """

    # -------- MODE 1: Get all vectors -------- #
    if not query:
        dummy_vector = [0.0] * INDEX_DIM      # FIXED

        raw = index.query(
            vector=dummy_vector,
            top_k=5000,
            include_metadata=True,
            filter={"company_id": {"$eq": company_id}},
        )

        hits = []
        for m in getattr(raw, "matches", []):
            meta = m.metadata or {}
            hits.append(RagHit(
                score=float(m.score),
                page_key=meta.get("page_key", ""),
                text_snippet=(meta.get("text_snippet") or "")[:700],
                source_url=meta.get("source_url", "")
            ))

        return RagSearchResponse(company_id=company_id, query=None, results=hits)

    # -------- MODE 2: Query-based semantic search -------- #
    qvec = embed_query(query)

    raw = index.query(
        vector=qvec,
        top_k=top_k,
        include_metadata=True,
        filter={"company_id": {"$eq": company_id}},
    )

    hits = []
    for m in getattr(raw, "matches", []):
        meta = m.metadata or {}
        hits.append(RagHit(
            score=float(m.score),
            page_key=meta.get("page_key", ""),
            text_snippet=(meta.get("text_snippet") or "")[:700],
            source_url=meta.get("source_url", "")
        ))

    return RagSearchResponse(company_id=company_id, query=query, results=hits)

# ---------------- MCP WRAPPER ----------------
def mcp_rag_search(company_id: str, query: Optional[str] = None) -> Dict[str, Any]:
    resp = pinecone_search(company_id, query)
    return json.loads(resp.model_dump_json())

# ---------------- Local Test ----------------
if __name__ == "__main__":
    cid = input("company_id: ").strip()
    q = input("query (empty = return all vectors): ").strip()
    q = q if q else None

    out = mcp_rag_search(cid, q)
    print(json.dumps(out, indent=2))
