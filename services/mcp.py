"""
Client for calling MedBridge MCP tool server.
All tool calls go through call_tool().
"""

import httpx
from config import settings


def _headers() -> dict:
    return {
        "X-MCP-Key": settings.MCP_SECRET_KEY,
        "Content-Type": "application/json",
    }


async def call_tool(tool_name: str, payload: dict) -> dict | list:
    url = f"{settings.MCP_SERVER_URL}/tools/{tool_name}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_tool_schemas() -> list[dict]:
    """Fetch all tool schemas from MCP server for Groq registration."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{settings.MCP_SERVER_URL}/tools",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
