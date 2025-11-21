import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

###############################################################################
# FIX 1 — MOCK GCS BEFORE IMPORTING ANY TOOL MODULES
###############################################################################

@pytest.fixture(scope="session", autouse=True)
def mock_gcs_client():
    """
    This fixture ensures that storage.Client() is mocked
    BEFORE importing run_tools / payload_tool.
    """
    with patch("google.cloud.storage.Client") as mock_client:
        yield mock_client


# ---------------------- IMPORT AFTER PATCHING ----------------------
from src.tools.run_tools import get_companies
from src.tools.payload_tool import get_latest_structured_payload
from src.tools.rag_tool import pinecone_search
from src.tools.risk_logger import detect_and_log_risks


###############################################################################
# 1. TEST get_companies()
###############################################################################

@patch("src.tools.run_tools.bucket")
def test_get_companies(mock_bucket):
    """Test extracting company_ids from mocked daily run file."""

    fake_blob = MagicMock()
    fake_blob.name = "data/raw/_runs/daily_20250101.json"
    fake_blob.download_as_text.return_value = json.dumps([
        {"company_id": "openai", "status": "ok"},
        {"company_id": "anthropic", "status": "ok"},
        {"company_id": "badcorp", "status": "failed"},
    ])

    # 👇 This is the key fix!
    # Make fake_blob pass isinstance(fake_blob, Blob)
    from google.cloud.storage.blob import Blob
    fake_blob.__class__ = Blob

    # Mock list_blobs to return only our fake blob
    mock_bucket.list_blobs.return_value = [fake_blob]

    result = get_companies()

    assert result == ["anthropic", "openai"]



###############################################################################
# 2. TEST get_latest_structured_payload()
###############################################################################

@patch("src.tools.payload_tool.httpx.AsyncClient")
@pytest.mark.asyncio
async def test_payload_tool_basic(mock_httpx, mock_gcs_client):
    """Test Cloud Run → payload GCS fetch workflow."""

    # -------- CREATE A REALISTIC ASYNC HTTP RESPONSE MOCK --------
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = AsyncMock()

    mock_resp.json = MagicMock(return_value={
        "structured_count": 1,
        "payload_count": 1,
        "results": [{
            "company_id": "databricks",
            "payload_uri": "gs://bucket/data/payloads/databricks.json"
        }]
    })

    # AsyncClient context manager mock
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_httpx.return_value.__aenter__.return_value = mock_client

    # -------- MOCK GCS PAYLOAD FETCH --------
    fake_blob = MagicMock()
    fake_blob.exists.return_value = True
    fake_blob.download_as_text.return_value = json.dumps({
        "company_record": {"company_id": "databricks"},
        "events": [],
        "snapshots": [],
    })

    fake_bucket = mock_gcs_client.return_value.bucket.return_value
    fake_bucket.blob.return_value = fake_blob

    payload = await get_latest_structured_payload("databricks")

    assert payload["company_record"]["company_id"] == "databricks"


###############################################################################
# 3. TEST rag_tool.pinecone_search()
###############################################################################

@patch("src.tools.rag_tool.index")
@patch("src.tools.rag_tool.openai_client")
def test_rag_search(mock_openai, mock_index):
    """Test Pinecone semantic search."""

    mock_openai.embeddings.create.return_value.data = [
        MagicMock(embedding=[0.1] * 3072)
    ]

    fake_match = MagicMock()
    fake_match.score = 0.99
    fake_match.metadata = {
        "page_key": "p1",
        "text_snippet": "There was a data breach.",
        "source_url": "http://example.com",
    }

    mock_index.query.return_value.matches = [fake_match]

    res = pinecone_search("openai", "breach", top_k=5)

    assert res.company_id == "openai"
    assert res.results[0].page_key == "p1"


###############################################################################
# 4. TEST risk_logger.detect_and_log_risks()
###############################################################################

@patch("src.tools.risk_logger.pinecone_search")
@patch("src.tools.risk_logger.get_latest_structured_payload")
@patch("src.tools.risk_logger.bucket")
@pytest.mark.asyncio
async def test_risk_detection(mock_bucket, mock_payload, mock_rag):
    """Test layoff + breach detection."""

    mock_payload.return_value = {
        "company_record": {"company_id": "anthropic"},
        "events": [
            {"title": "Company lays off 20% of staff", "description": "Major layoffs"},
        ]
    }

    fake_hit = MagicMock()
    fake_hit.page_key = "p1"
    fake_hit.text_snippet = "A major data breach occurred."
    fake_hit.score = 0.92
    fake_hit.source_url = "http://breach.example.com"

    mock_rag.return_value.results = [fake_hit]

    fake_blob = MagicMock()
    fake_blob.exists.return_value = False
    mock_bucket.blob.return_value = fake_blob

    result = await detect_and_log_risks("anthropic")

    assert result["detected"] is True
    assert len(result["events"]) >= 2
    assert result["company_id"] == "anthropic"
