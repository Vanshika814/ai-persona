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
from services.persona import get_chat_system_prompt

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
    system_prompt: str | None = None,
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
            system_prompt=system_prompt,
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
            from services import calendar as cal_service
            from datetime import date
            try:
                slots = await cal_service.get_available_slots(date=date.today().isoformat())
                if slots:
                    slots_str = "\n".join([f"- {s['display']} (ISO start: {s['datetime']})" for s in slots[:5]])
                    context = (
                        f"{context}\n\n"
                        f"Available interview slots:\n{slots_str}\n\n"
                        "User is asking about scheduling. Propose these exact available slots. "
                        "Tell them they can choose one of these slots or type a slot directly to book it. "
                        "When they select a slot, explain that they can confirm by giving their Name, Email, and the chosen Slot. "
                        "Always end your message with the exact token [SCHEDULER_WIDGET] so the interactive calendar widget is rendered."
                    )
                else:
                    context = (
                        f"{context}\n\n"
                        "User is asking about scheduling, but no available slots were found on the calendar. "
                        "Please ask them to check back later or suggest another time. "
                        "Always end your message with the exact token [SCHEDULER_WIDGET] so they can see the calendar widget and retry."
                    )
            except Exception as e:
                logger.error("Failed to get available slots: %s", e)
                context = (
                    f"{context}\n\n"
                    "User is asking about scheduling, but there was an error retrieving available slots. "
                    "Ask them to retry. "
                    "Always end your message with the exact token [SCHEDULER_WIDGET] so they can retry using the widget."
                )

        # 4. Stream response
        return StreamingResponse(
            _sse_stream(
                body.message,
                context,
                body.conversation_history,
                system_prompt=get_chat_system_prompt(),
            ),
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
