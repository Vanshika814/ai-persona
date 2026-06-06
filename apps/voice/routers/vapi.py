"""Vapi router for the voice FastAPI backend.

Provides endpoints for integration with Vapi:
- ``POST /vapi/get-context`` — Retrieve context from RAG.
- ``POST /vapi/tool-call`` — Webhook placeholder for Vapi tool execution.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.rag import retrieve_context

logger = logging.getLogger("voice.vapi")

router = APIRouter(prefix="/vapi", tags=["vapi"])


# ──────────────────────────────────────────────
#  Request models
# ──────────────────────────────────────────────


class GetContextRequest(BaseModel):
    """Request body for retrieving RAG context."""

    query: str = Field(..., description="The query to search the knowledge base for.")


# ──────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────


@router.post("/get-context")
async def get_context(body: GetContextRequest) -> dict[str, str]:
    """Retrieve relevant context chunks for the given query using RAG.

    Args:
        body: The GetContextRequest payload.

    Returns:
        A dictionary containing the compiled context string.
    """
    logger.info("Retrieving context for query: %r", body.query)
    try:
        context = await retrieve_context(body.query)
        return {"context": context}
    except Exception as exc:
        logger.error("Failed to retrieve context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve context: {exc}",
        )


@router.post("/tool-call")
async def tool_call(body: dict[str, Any] = None) -> dict[str, str]:
    """Generic tool-call webhook placeholder for Vapi.

    Returns:
        A dictionary response indicating success.
    """
    logger.info("Vapi tool call webhook invoked with body: %r", body)
    return {"result": "ok"}
