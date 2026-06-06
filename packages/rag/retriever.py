"""
retriever.py – RAG pipeline semantic retriever.

Provides helpers for:
  • Embedding a query and performing cosine-similarity search via Supabase.
  • Filtering results by source (résumé / GitHub).
  • Formatting retrieved chunks into a clean context string for LLM prompts.
"""

from __future__ import annotations

from typing import Any

from google import genai
from supabase import Client

try:
    from .embedder import embed_query
except (ImportError, ValueError):
    from embedder import embed_query  # type: ignore


# ──────────────────────────────────────────────
#  1. Semantic search
# ──────────────────────────────────────────────


async def _embed_query(query: str, client: genai.Client) -> list[float]:
    """Embed a query string. Thin wrapper around :func:`embed_query` for caching."""
    return await embed_query(query, client)


async def retrieve(
    query: str,
    client: genai.Client,
    supabase: Client,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Embed *query* and return the most similar document chunks.

    Calls the ``match_documents`` Supabase RPC function, which performs
    cosine-similarity search against the ``documents`` table.

    Args:
        query: The user's natural-language query.
        client: A :class:`genai.Client` for embedding the query.
        supabase: A configured :class:`supabase.Client`.
        top_k: Maximum number of results to return.

    Returns:
        A list of matching chunk dicts, each containing:

        - ``id`` – chunk identifier.
        - ``text`` – chunk text.
        - ``source`` – ``"resume"`` or ``"github"``.
        - ``metadata`` – additional metadata dict.
        - ``similarity`` – cosine similarity score.

        Returns an empty list when no results exceed the threshold.
    """
    query_embedding = await _embed_query(query, client)

    response = (
        supabase.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.5,
                "match_count": top_k,
            },
        )
        .execute()
    )

    results: list[dict[str, Any]] = response.data or []

    return [
        {
            "id": row.get("id", ""),
            "text": row.get("text", ""),
            "source": row.get("source", ""),
            "metadata": row.get("metadata", {}),
            "similarity": row.get("similarity", 0.0),
        }
        for row in results
    ]


# ──────────────────────────────────────────────
#  2. Filtered search
# ──────────────────────────────────────────────


async def retrieve_from_source(
    query: str,
    source: str,
    client: genai.Client,
    supabase: Client,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Like :func:`retrieve`, but only returns chunks from *source*.

    Delegates to :func:`retrieve` with ``top_k * 2`` to over-fetch, then
    filters client-side by *source* and returns at most *top_k* results.

    Args:
        query: The user's natural-language query.
        source: Filter value – ``"resume"`` or ``"github"``.
        client: A :class:`genai.Client` for embedding the query.
        supabase: A configured :class:`supabase.Client`.
        top_k: Maximum number of results to return.

    Returns:
        A filtered list of matching chunk dicts (same schema as
        :func:`retrieve`).
    """
    results = await retrieve(query, client, supabase, top_k=top_k * 2)
    filtered = [chunk for chunk in results if chunk["source"] == source]
    return filtered[:top_k]


# ──────────────────────────────────────────────
#  3. Format context
# ──────────────────────────────────────────────


def format_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a clean context block for an LLM prompt.

    Each chunk is rendered as::

        [Source: resume | experience]
        <chunk text>
        ---

    Args:
        chunks: List of chunk dicts as returned by :func:`retrieve` or
            :func:`retrieve_from_source`.

    Returns:
        A single string with all formatted chunks joined together.
        Returns an empty string if *chunks* is empty.
    """
    if not chunks:
        return ""

    blocks: list[str] = []
    for chunk in chunks:
        source: str = chunk.get("source", "unknown")
        metadata: dict[str, Any] = chunk.get("metadata", {})

        # Pick the most descriptive label from metadata.
        label = metadata.get("section") or metadata.get("repo") or metadata.get("type", "")

        text: str = chunk.get("text", "")
        blocks.append(f"[Source: {source} | {label}]\n{text}\n---")

    return "\n".join(blocks)
