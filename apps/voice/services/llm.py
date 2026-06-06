"""LLM service for the voice FastAPI backend.

Wraps Groq (Llama 3.1 70B) for chat completions (single-shot and
streaming) and provides a lightweight calendar-intent detector.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from groq import AsyncGroq

from services.persona import format_prompt_with_context, get_system_prompt

load_dotenv()

# ──────────────────────────────────────────────
#  Client Setup
# ──────────────────────────────────────────────

_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    """Return a configured Groq client, creating it on first call.

    Reads ``GROQ_API_KEY`` from the environment.

    Returns:
        An ``AsyncGroq`` client instance ready for use.

    Raises:
        ValueError: If ``GROQ_API_KEY`` is not set.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )
        _client = AsyncGroq(api_key=api_key)
    return _client


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

MODEL = "llama-3.3-70b-versatile"


def _build_messages(
    user_message: str,
    context: str,
    conversation_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build the messages list for the Groq chat API.

    Structure::

        [
            {"role": "system", "content": <system prompt>},
            ...conversation_history,
            {"role": "user", "content": <user message with context>},
        ]

    Args:
        user_message: The latest user message.
        context: RAG-retrieved context string.
        conversation_history: Prior turns as ``{"role": ..., "content": ...}``
            dicts.

    Returns:
        A list of message dicts ready for the Groq API.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": get_system_prompt()},
    ]

    for turn in conversation_history:
        messages.append({
            "role": turn.get("role", "user"),
            "content": turn.get("content", ""),
        })

    prompt = format_prompt_with_context(user_message, context)
    messages.append({"role": "user", "content": prompt})

    return messages


# ──────────────────────────────────────────────
#  Chat Completion
# ──────────────────────────────────────────────


async def chat_completion(
    user_message: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Generate a complete chat response using Groq (Llama 3.1 70B).

    Builds a multi-turn conversation from *conversation_history*,
    appends the current *user_message* (with RAG context), and
    returns the full model response.

    Args:
        user_message: The user's latest message.
        context: RAG-retrieved context to ground the response.
        conversation_history: Prior conversation turns. Each dict
            has ``"role"`` (``"user"`` or ``"assistant"``) and
            ``"content"`` keys. Defaults to an empty list.

    Returns:
        The model's response text.

    Raises:
        RuntimeError: If the Groq API call fails.
    """
    if conversation_history is None:
        conversation_history = []

    try:
        client = get_groq_client()
        messages = _build_messages(user_message, context, conversation_history)

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

        return response.choices[0].message.content or ""

    except Exception as exc:
        print(f"[llm] chat_completion error: {exc}")
        raise RuntimeError(f"Groq API error: {exc}") from exc


# ──────────────────────────────────────────────
#  Streaming Chat
# ──────────────────────────────────────────────


async def stream_chat(
    user_message: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat response token-by-token using Groq (Llama 3.1 70B).

    Same as :func:`chat_completion` but streams tokens, suitable for
    Server-Sent Events or WebSocket streaming.

    Args:
        user_message: The user's latest message.
        context: RAG-retrieved context to ground the response.
        conversation_history: Prior conversation turns. Defaults to
            an empty list.

    Yields:
        String chunks of the model's response as they arrive.

    Raises:
        RuntimeError: If the Groq API call fails.
    """
    if conversation_history is None:
        conversation_history = []

    try:
        client = get_groq_client()
        messages = _build_messages(user_message, context, conversation_history)

        stream = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta is not None:
                yield delta

    except Exception as exc:
        print(f"[llm] stream_chat error: {exc}")
        raise RuntimeError(f"Groq API error: {exc}") from exc


# ──────────────────────────────────────────────
#  Calendar Intent Detection
# ──────────────────────────────────────────────

_CALENDAR_KEYWORDS: set[str] = {
    "schedule",
    "book",
    "meeting",
    "call",
    "available",
    "availability",
    "slot",
    "interview",
    "when",
    "time",
}


def is_calendar_intent(message: str) -> bool:
    """Detect whether a message is asking about availability or booking.

    Performs a simple case-insensitive keyword check against a fixed
    set of calendar-related terms. No LLM call is made.

    Args:
        message: The user's message text.

    Returns:
        ``True`` if any calendar keyword is found in *message*.
    """
    words = set(message.lower().split())
    return bool(words & _CALENDAR_KEYWORDS)
