"""
Groq AI agent — uses llama-3.3-70b-versatile with MCP tool calling.
Tool schemas are loaded lazily in the background with retries,
so a cold-starting MCP server doesn't block the backend from coming up.
"""

import json
import asyncio
from typing import AsyncGenerator
from groq import AsyncGroq
from config import settings
from services.mcp import call_tool, get_tool_schemas

groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

_mcp_tool_schemas: list[dict] = []
_schemas_loaded = False

SYSTEM_PROMPT = """You are MedBridge AI, a multilingual healthcare assistant for India.
Your role is to help patients find doctors, understand their symptoms, and book appointments.
You also assist doctors and nurses with patient information.

Rules:
1. Always detect and respond in the user's language (Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, or English).
2. Never make a definitive medical diagnosis. Always say "these symptoms may indicate..." and recommend professional consultation.
3. When a patient describes symptoms, call search_doctors to find relevant specialists nearby.
4. When booking appointments, confirm all details before calling book_appointment.
5. Be empathetic and clear. Use simple language.
6. If a patient says it's urgent, set is_urgent: true in book_appointment.
7. For doctors/nurses asking about patients, verify their role first.
8. Always protect patient privacy — never share data without consent.
"""


def _convert_to_groq_format(mcp_schemas) -> list[dict]:
    """
    Convert MCP tool schemas to OpenAI-compatible function format.
    Handles multiple response shapes:
      - list of dicts with 'name', 'description', 'input_schema'
      - list of strings (tool names only)
      - dict with a 'tools' key
    """
    tools = []

    if isinstance(mcp_schemas, dict):
        mcp_schemas = mcp_schemas.get("tools", [])

    if not isinstance(mcp_schemas, list):
        print(f"[Groq Agent] Unexpected schema format: {type(mcp_schemas)}")
        return []

    for schema in mcp_schemas:
        if isinstance(schema, str):
            tools.append({
                "type": "function",
                "function": {
                    "name": schema,
                    "description": f"Call the {schema} tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            })
        elif isinstance(schema, dict):
            name = schema.get("name") or schema.get("tool_name", "unknown")
            description = schema.get("description", "")
            parameters = (
                schema.get("input_schema")
                or schema.get("parameters")
                or {"type": "object", "properties": {}}
            )
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            })
    return tools


async def _load_with_retries(max_attempts: int = 10, delay: int = 10):
    """
    Try to load MCP tool schemas repeatedly until success.
    Waits `delay` seconds between attempts — gives the MCP server
    time to finish its own cold start.
    """
    global _mcp_tool_schemas, _schemas_loaded
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await get_tool_schemas()
            schemas = _convert_to_groq_format(raw)
            if schemas:
                _mcp_tool_schemas = schemas
                _schemas_loaded = True
                print(f"[Groq Agent] Loaded {len(schemas)} MCP tools (attempt {attempt})")
                return
            else:
                print(f"[Groq Agent] Got empty schema list on attempt {attempt}, retrying in {delay}s...")
        except Exception as e:
            print(f"[Groq Agent] Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay}s...")
        await asyncio.sleep(delay)

    print("[Groq Agent] Could not load MCP tool schemas after all attempts. "
          "Chat will work without tool calling until next restart.")


async def load_tool_schemas():
    """
    Called at app startup. Fires the retry loop as a background task
    so the backend comes up immediately regardless of MCP cold start.
    """
    asyncio.create_task(_load_with_retries(max_attempts=10, delay=10))
    print("[Groq Agent] Schema loading started in background (MCP may be cold-starting)...")


def _build_system_message(user_id: str | None, role: str | None,
                           lat: float | None, lng: float | None) -> str:
    context_parts = [SYSTEM_PROMPT]
    if user_id:
        context_parts.append(f"\nCurrent user ID: {user_id}")
    if role:
        context_parts.append(f"Current user role: {role}")
    if lat and lng:
        context_parts.append(f"User location: lat={lat}, lng={lng}")
    return "\n".join(context_parts)


async def run_agent(
    message: str,
    history: list[dict],
    user_id: str | None = None,
    role: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> str:
    system_msg = _build_system_message(user_id, role, lat, lng)
    messages = [{"role": "system", "content": system_msg}]
    messages.extend(history[-20:])
    messages.append({"role": "user", "content": message})

    for _ in range(10):
        kwargs: dict = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 2048,
        }
        if _mcp_tool_schemas:
            kwargs["tools"] = _mcp_tool_schemas
            kwargs["tool_choice"] = "auto"

        response = await groq_client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        if not msg.tool_calls:
            return msg.content or ""

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            try:
                tool_result = await call_tool(tool_name, args)
                result_content = json.dumps(tool_result)
            except Exception as e:
                result_content = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_content,
            })

    return "I'm sorry, I wasn't able to complete your request. Please try again."


async def run_agent_streaming(
    message: str,
    history: list[dict],
    user_id: str | None = None,
    role: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> AsyncGenerator[str, None]:
    system_msg = _build_system_message(user_id, role, lat, lng)
    messages = [{"role": "system", "content": system_msg}]
    messages.extend(history[-20:])
    messages.append({"role": "user", "content": message})

    for _ in range(10):
        kwargs: dict = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 2048,
        }
        if _mcp_tool_schemas:
            kwargs["tools"] = _mcp_tool_schemas
            kwargs["tool_choice"] = "auto"

        response = await groq_client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            yield msg.content or ""
            return

        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
        messages.append(assistant_msg)

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            try:
                tool_result = await call_tool(tool_name, args)
                result_content = json.dumps(tool_result)
            except Exception as e:
                result_content = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_content,
            })

    yield "I'm sorry, I wasn't able to complete your request. Please try again."
