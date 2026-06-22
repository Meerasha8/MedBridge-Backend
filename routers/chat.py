"""
Chat endpoints:
  POST /chat       — single-turn REST
  WS   /chat/ws   — streaming WebSocket
"""

import json
import uuid
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from jose import JWTError

from services.groq_agent import run_agent, run_agent_streaming
from services.session_store import get_history, append_message
from middleware.auth import decode_token

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    lat: float | None = None
    lng: float | None = None


@router.post("")
async def chat(body: ChatRequest, request: Request):
    user_id = request.state.user_id
    role = request.state.role

    session_id = body.session_id or str(uuid.uuid4())
    history = get_history(session_id)

    response_text = await run_agent(
        message=body.message,
        history=history,
        user_id=user_id,
        role=role,
        lat=body.lat,
        lng=body.lng,
    )

    # Persist to session history
    append_message(session_id, "user", body.message)
    append_message(session_id, "assistant", response_text)

    return {
        "session_id": session_id,
        "response": response_text,
    }


@router.websocket("/ws")
async def chat_ws(
    websocket: WebSocket,
    session_id: str = Query(...),
    token: str = Query(...),
):
    # Authenticate via query param token
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        role = payload.get("user_metadata", {}).get("role", "patient")
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            message = data.get("message", "").strip()
            if not message:
                continue

            lat = data.get("lat")
            lng = data.get("lng")
            history = get_history(session_id)

            # Stream the response token by token (or chunk by chunk)
            full_response = ""
            async for chunk in run_agent_streaming(
                message=message,
                history=history,
                user_id=user_id,
                role=role,
                lat=lat,
                lng=lng,
            ):
                full_response += chunk
                await websocket.send_json({"chunk": chunk, "done": False})

            # Signal completion
            await websocket.send_json({"chunk": "", "done": True, "full": full_response})

            # Save to session
            append_message(session_id, "user", message)
            append_message(session_id, "assistant", full_response)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
