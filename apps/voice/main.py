"""Vanshika AI Persona Backend — FastAPI entry point."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.chat import router as chat_router
from routers.calendar import router as calendar_router
from routers.vapi import router as vapi_router
from services.llm import check_health as check_llm_health
from services.rag import check_health as check_rag_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger("voice")

app = FastAPI(title="Vanshika AI Persona Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-persona-assignment.vercel.app",
    "https://ai-persona-assignment-scaler.vercel.app","http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(calendar_router)
app.include_router(vapi_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root health check."""
    return {"status": "online", "service": "Vanshika AI Persona Backend"}


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint that runs diagnostics on downstream services."""
    llm_status = check_llm_health()
    rag_status = check_rag_health()

    is_healthy = llm_status["status"] == "healthy" and rag_status["status"] == "healthy"

    content = {
        "status": "healthy" if is_healthy else "unhealthy",
        "services": {
            "llm": llm_status,
            "rag": rag_status,
        },
    }

    status_code = 200 if is_healthy else 503
    return JSONResponse(status_code=status_code, content=content)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting server on port %d", port)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
