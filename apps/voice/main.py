"""Vanshika AI Persona Backend — FastAPI entry point."""

from __future__ import annotations

import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.chat import router as chat_router
from routers.calendar import router as calendar_router

load_dotenv()

# ──────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

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


@app.post("/vapi/tool-call")
async def vapi_tool_call() -> dict[str, str]:
    """Vapi webhook placeholder — will be implemented in the voice agent branch."""
    return {"result": "ok"}


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
