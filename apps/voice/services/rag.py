"""RAG service for the voice FastAPI backend.

Self-contained module that handles query embedding via Gemini and
semantic retrieval via Supabase. Clients are initialised once at
module level so they can be reused across requests.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from supabase import Client, create_client

load_dotenv()

# ──────────────────────────────────────────────
#  Module-level client initialisation
# ──────────────────────────────────────────────

_gemini_client: genai.Client | None = None
_supabase_client: Client | None = None


def _get_gemini_client() -> genai.Client:
    """Return the module-level Gemini client, creating it on first call.

    Reads ``GEMINI_API_KEY`` from the environment. Forces the v1 API.

    Returns:
        A configured ``genai.Client`` instance.

    Raises:
        ValueError: If ``GEMINI_API_KEY`` is not set.
    """
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or export it as an environment variable."
            )
        _gemini_client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1"},
        )
    return _gemini_client


def _get_supabase_client() -> Client:
    """Return the module-level Supabase client, creating it on first call.

    Reads ``SUPABASE_URL`` and ``SUPABASE_SERVICE_KEY`` from the environment.

    Returns:
        A configured ``supabase.Client`` instance.

    Raises:
        ValueError: If either environment variable is missing.
    """
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            missing = []
            if not url:
                missing.append("SUPABASE_URL")
            if not key:
                missing.append("SUPABASE_SERVICE_KEY")
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}."
            )
        _supabase_client = create_client(url, key)
    return _supabase_client


# ──────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────


def _embed_query(query: str) -> list[float]:
    """Embed a query string using Gemini for retrieval.

    Uses ``models/gemini-embedding-001`` with ``RETRIEVAL_QUERY`` task type
    and 768-dimensional output to match the Supabase vector column.

    Args:
        query: The text to embed.

    Returns:
        The embedding vector as a list of floats.
    """
    client = _get_gemini_client()
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=query,
        config={
            "task_type": "RETRIEVAL_QUERY",
            "output_dimensionality": 768,
        },
    )
    return list(response.embeddings[0].values)


def _format_chunks(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunk rows into a clean context string.

    Each chunk is rendered as::

        [Source: resume | experience]
        <chunk text>

    Chunks are separated by ``---``.

    Args:
        chunks: Rows returned by the ``match_documents`` RPC.

    Returns:
        Formatted context string, or empty string if *chunks* is empty.
    """
    if not chunks:
        return ""

    blocks: list[str] = []
    for chunk in chunks:
        source: str = chunk.get("source", "unknown")
        metadata: dict[str, Any] = chunk.get("metadata", {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        label = (
            metadata.get("section")
            or metadata.get("repo")
            or metadata.get("type", "")
        )
        text: str = chunk.get("text", "")
        blocks.append(f"[Source: {source} | {label}]\n{text}")

    return "\n---\n".join(blocks)


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────


async def retrieve_context(query: str, top_k: int = 5) -> str:
    """Embed *query* and retrieve the most relevant context chunks.

    Calls the ``match_documents`` Supabase RPC with a similarity
    threshold of 0.4 and returns at most *top_k* results formatted
    as a context string.

    Args:
        query: The user's natural-language question.
        top_k: Maximum number of chunks to return.

    Returns:
        A formatted context string for LLM prompts.
        Returns an empty string on any error or no results.
    """
    try:
        query_embedding = _embed_query(query)
        supabase = _get_supabase_client()

        response = (
            supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.4,
                    "match_count": top_k,
                },
            )
            .execute()
        )

        results: list[dict[str, Any]] = response.data or []
        return _format_chunks(results)

    except Exception as exc:
        print(f"[rag] retrieve_context error: {exc}")
        return ""


async def retrieve_from_source(
    query: str,
    source: str,
    top_k: int = 5,
) -> str:
    """Like :func:`retrieve_context`, but filtered to a single source.

    Over-fetches (``top_k * 2``) from the database, then filters
    client-side by *source* to ensure enough results.

    Args:
        query: The user's natural-language question.
        source: Filter value — ``"resume"`` or ``"github"``.
        top_k: Maximum number of chunks to return after filtering.

    Returns:
        A formatted context string for LLM prompts.
        Returns an empty string on any error or no results.
    """
    try:
        query_embedding = _embed_query(query)
        supabase = _get_supabase_client()

        response = (
            supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.4,
                    "match_count": top_k * 2,
                },
            )
            .execute()
        )

        results: list[dict[str, Any]] = response.data or []
        filtered = [r for r in results if r.get("source") == source]
        return _format_chunks(filtered[:top_k])

    except Exception as exc:
        print(f"[rag] retrieve_from_source error: {exc}")
        return ""
