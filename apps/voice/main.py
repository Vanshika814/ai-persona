"""Vanshika AI Persona Backend — FastAPI entry point."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.chat import router as chat_router
from routers.calendar import router as calendar_router

# ──────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger("voice")

# ──────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────

app = FastAPI(title="Vanshika AI Persona Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(calendar_router)


# ──────────────────────────────────────────────
#  Root & placeholders
# ──────────────────────────────────────────────


@app.get("/")
async def root() -> dict[str, str]:
    """Root health check."""
    return {"status": "online", "service": "Vanshika AI Persona Backend"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for Railway."""
    return {"status": "ok"}


@app.post("/vapi/tool-call")
async def vapi_tool_call() -> dict[str, str]:
    """Vapi webhook placeholder — will be implemented in the voice agent branch."""
    return {"result": "ok"}


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting server on port %d", port)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
