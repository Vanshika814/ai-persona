"""Chat router for the voice FastAPI backend.

Provides:
- POST /chat — SSE-streamed chat with RAG context or scheduling.
- GET /chat/health — Simple health check.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.llm import agentic_chat, current_session_id
from services.rag import retrieve_context
from services.persona import get_chat_system_prompt

logger = logging.getLogger("voice.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    message: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    session_id: str | None = None


async def _sse_stream(stream):
    """Yield SSE-formatted chunks from the LLM stream."""
    try:
        async for chunk in stream:
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        logger.error("SSE stream error: %s", exc)
        yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"


@router.post("")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """Handle a chat message with RAG-augmented or scheduling streaming response."""
    print("🔥 CHAT ROUTE HIT", flush=True)
    logger.info(
        "POST /chat — message=%r history_len=%d",
        body.message[:80],
        len(body.conversation_history),
    )

    session_id = body.session_id or (request.client.host if request.client else "default_user")

    try:
        context = await retrieve_context(body.message)
        stream = agentic_chat(
            body.message,
            context,
            body.conversation_history,
            get_chat_system_prompt(),
            session_id=session_id,
        )

        return StreamingResponse(
            _sse_stream(stream),
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
        {"status": "ok"}
    """
    return {"status": "ok"}
