from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.rag import retrieve_context

logger = logging.getLogger("voice.vapi")

router = APIRouter(prefix="/vapi", tags=["vapi"])

class GetContextRequest(BaseModel):
    """Request body for retrieving RAG context."""

    query: str = Field(..., description="The query to search the knowledge base for.")

@router.post("/get-context")
async def get_context(body: GetContextRequest) -> dict[str, str]:
    
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
    logger.info("Vapi tool call webhook invoked with body: %r", body)
    return {"result": "ok"}
