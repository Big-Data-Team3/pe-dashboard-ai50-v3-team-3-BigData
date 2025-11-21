import os
import json
import httpx
import asyncio
from pathlib import Path
from typing import Dict, Any

class MCPClient:
    """Client for calling MCP HTTP server tools."""

    def __init__(self, config_path="src/config/mcp_config.json", timeout=120):
        self.timeout = timeout
        self.config = self._load_config(config_path)

        # base URL from env or config
        self.base_url = (
            os.getenv("MCP_BASE_URL") or
            self.config.get("base_url") or
            "http://localhost:9000"
        ).rstrip("/")

    def _load_config(self, path: str) -> Dict[str, Any]:
        path = Path(path)
        if path.exists():
            return json.loads(path.read_text())
        return {}

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool endpoint."""

        tool_info = self.config.get("tools", {}).get(tool_name)
        if not tool_info:
            raise ValueError(f"Tool {tool_name} not found in mcp_config.json")

        url = f"{self.base_url}/{tool_info['endpoint'].lstrip('/')}"

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            res = await client.post(url, json=params)
            res.raise_for_status()
            return res.json()

    async def get_resource(self, resource_name: str) -> Dict[str, Any]:
        """Fetch an MCP resource via GET."""

        res_info = self.config.get("resources", {}).get(resource_name)
        if not res_info:
            raise ValueError(f"Resource {resource_name} missing in config")

        url = f"{self.base_url}/{res_info['endpoint'].lstrip('/')}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            res = await client.get(url)
            res.raise_for_status()
            return res.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False
