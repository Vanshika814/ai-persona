from __future__ import annotations

from typing import Any

from google import genai
from supabase import Client

try:
    from .embedder import embed_query
except (ImportError, ValueError):
    from embedder import embed_query  # type: ignore

async def _embed_query(query: str, client: genai.Client) -> list[float]:
    """Embed a query string. Thin wrapper around :func:`embed_query` for caching."""
    return await embed_query(query, client)


async def retrieve(
    query: str,
    client: genai.Client,
    supabase: Client,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    
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

async def retrieve_from_source(
    query: str,
    source: str,
    client: genai.Client,
    supabase: Client,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    
    results = await retrieve(query, client, supabase, top_k=top_k * 2)
    filtered = [chunk for chunk in results if chunk["source"] == source]
    return filtered[:top_k]

def format_context(chunks: list[dict[str, Any]]) -> str:
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
