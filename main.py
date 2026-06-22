"""
MedBridge Backend — FastAPI application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from middleware.auth import auth_middleware
from services.groq_agent import load_tool_schemas

from routers import (
    auth,
    doctors,
    appointments,
    sub_accounts,
    documents,
    prescriptions,
    reviews,
    notifications,
    admin,
    chat,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load MCP tool schemas into Groq agent."""
    await load_tool_schemas()
    yield


app = FastAPI(
    title="MedBridge Backend",
    description="Multilingual AI healthcare platform for India",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (runs on every request except public routes)
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# Routers
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(sub_accounts.router)
app.include_router(documents.router)
app.include_router(prescriptions.router)
app.include_router(reviews.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(chat.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "medbridge-backend"}
