"""Chat router for the voice FastAPI backend.

Provides:
- ``POST /chat`` — SSE-streamed chat with RAG context and calendar intent detection.
- ``GET /chat/health`` — Simple health check.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services import llm, rag

logger = logging.getLogger("voice.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


# ──────────────────────────────────────────────
#  Request / Response models
# ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    message: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)


# ──────────────────────────────────────────────
#  SSE streaming helper
# ──────────────────────────────────────────────


async def _sse_stream(
    message: str,
    context: str,
    conversation_history: list[dict[str, str]],
):
    """Yield SSE-formatted chunks from the LLM stream.

    Each chunk is sent as ``data: <text>\\n\\n``.  A final
    ``data: [DONE]\\n\\n`` sentinel is emitted when the stream ends.

    Args:
        message: The user's message.
        context: RAG-retrieved context string.
        conversation_history: Prior conversation turns.

    Yields:
        SSE-formatted string chunks.
    """
    try:
        async for chunk in llm.stream_chat(
            user_message=message,
            context=context,
            conversation_history=conversation_history,
        ):
            yield f"data: {chunk}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.error("SSE stream error: %s", exc)
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"


# ──────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────


@router.post("")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """Handle a chat message with RAG-augmented streaming response.

    Flow:
        1. Detect calendar intent via keyword check.
        2. Retrieve RAG context from Supabase.
        3. If calendar intent, append scheduling instruction to context.
        4. Stream the Gemini response back as Server-Sent Events.

    Args:
        request: The incoming FastAPI request (for logging).
        body: Parsed ``ChatRequest`` with message and optional history.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` content type.
    """
    logger.info(
        "POST /chat — message=%r history_len=%d",
        body.message[:80],
        len(body.conversation_history),
    )

    try:
        # 1. Calendar intent detection
        calendar_intent = llm.is_calendar_intent(body.message)
        if calendar_intent:
            logger.info("Calendar intent detected")

        # 2. Retrieve RAG context
        context = await rag.retrieve_context(body.message)

        # 3. Enrich context for calendar requests
        if calendar_intent:
            context = (
                f"{context}\n\n"
                "User is asking about scheduling. "
                "Check availability and propose slots."
            )

        # 4. Stream response
        return StreamingResponse(
            _sse_stream(body.message, context, body.conversation_history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as exc:
        logger.error("POST /chat failed: %s\n%s", exc, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


@router.get("/health")
async def health() -> dict[str, str]:
    """Simple health check.

    Returns:
        ``{"status": "ok"}``
    """
    return {"status": "ok"}
