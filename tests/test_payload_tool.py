import pytest
from src.tools.payload_tool import get_latest_structured_payload

@pytest.mark.asyncio
async def test_payload_tool_basic():
    result = await get_latest_structured_payload("synthesia")

    assert "company_record" in result
    assert "events" in result
