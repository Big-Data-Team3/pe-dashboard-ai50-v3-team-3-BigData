import pytest
from fastapi.testclient import TestClient
from src.server.mcp_server import app
from src.mcp.mcp_client import MCPClient
import asyncio

# -----------------------------
# FIXTURES
# -----------------------------

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mcp_client(tmp_path):
    """MCP client pointing to test config"""
    config = tmp_path / "mcp_config.json"

    # Matching the FIXED CONFIG FORMAT
    config.write_text("""
    {
      "base_url": "http://testserver",

      "tools": {
        "generate_structured_dashboard": {
          "endpoint": "tool/generate_structured_dashboard",
          "method": "POST"
        },
        "generate_rag_dashboard": {
          "endpoint": "tool/generate_rag_dashboard",
          "method": "POST"
        }
      },

      "resources": {
        "ai50_companies": {
          "endpoint": "resource/ai50/companies"
        }
      },

      "prompts": {
        "pe_dashboard": {
          "endpoint": "prompt/pe-dashboard"
        }
      }
    }
    """)
    return MCPClient(config_path=str(config))


# -----------------------------
# TEST 1 — HEALTH CHECK
# -----------------------------

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# -----------------------------
# TEST 2 — RESOURCES ENDPOINT
# -----------------------------

def test_list_ai50_companies(client):
    res = client.get("/resource/ai50/companies")
    assert res.status_code == 200
    data = res.json()
    assert "company_ids" in data
    assert isinstance(data["company_ids"], list)
    assert "anthropic" in data["company_ids"]  # from seeds


# -----------------------------
# TEST 3 — PROMPT ENDPOINT
# -----------------------------

def test_pe_dashboard_prompt(client):
    res = client.get("/prompt/pe-dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "system_prompt" in data
    assert "Company Overview" in data["system_prompt"]  # critical section header


# -----------------------------
# TEST 4 — STRUCTURED TOOL
# -----------------------------

def test_structured_dashboard_tool(client):
    res = client.post(
        "/tool/generate_structured_dashboard",
        json={"company_id": "anthropic"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "company_id" in data
    assert "markdown" in data
    assert "Disclaimer" not in data["markdown"]  # ensures correct template
    assert data["company_id"] == "anthropic"


# -----------------------------
# TEST 5 — RAG TOOL
# -----------------------------

def test_rag_dashboard_tool(client):
    res = client.post(
        "/tool/generate_rag_dashboard",
        json={"company_id": "anthropic"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "markdown" in data
    assert "Company Overview" in data["markdown"]  # ensures LLM output format


# -----------------------------
# TEST 6 — MCP CLIENT RESOLVES TOOL
# -----------------------------

@pytest.mark.asyncio
async def test_mcp_client_finds_tool(mcp_client, monkeypatch):
    """
    Validate that the updated config format matches MCPClient expectations.
    """
    async def fake_post(url, json):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"ok": True}
        return R()

    monkeypatch.setattr(mcp_client, "base_url", "http://testserver")

    # Mock the HTTPX client inside MCPClient
    with monkeypatch.context() as mp:
        async def mock_post(*args, **kwargs):
            class Response:
                def raise_for_status(self): ...
                def json(self): return {"mocked": True}
            return Response()

        mp.setattr("httpx.AsyncClient.post", mock_post)

        resp = await mcp_client.call_tool(
            "generate_structured_dashboard",
            {"company_id": "anthropic"}
        )

        assert resp == {"mocked": True}


# -----------------------------
# TEST 7 — CONFIG HAS ALL REQUIRED TOOLS
# -----------------------------

def test_mcp_config_structure(mcp_client):
    assert "tools" in mcp_client.config
    assert "generate_structured_dashboard" in mcp_client.config["tools"]
    assert "endpoint" in mcp_client.config["tools"]["generate_structured_dashboard"]
