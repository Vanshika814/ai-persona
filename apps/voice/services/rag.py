from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from supabase import Client, create_client

load_dotenv()

_gemini_client: genai.Client | None = None
_supabase_client: Client | None = None


def _get_gemini_client() -> genai.Client:
    
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


def _embed_query(query: str) -> list[float]:
    
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

async def retrieve_context(query: str, top_k: int = 5) -> str:
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


def check_health() -> dict[str, str]:
    """Check Supabase and Gemini configuration and health."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    errors = []
    if not supabase_url:
        errors.append("SUPABASE_URL is not set")
    if not supabase_key:
        errors.append("SUPABASE_SERVICE_KEY is not set")
    if not gemini_key:
        errors.append("GEMINI_API_KEY is not set")

    if errors:
        return {"status": "unhealthy", "error": ", ".join(errors)}

    try:
        _get_gemini_client()
    except Exception as exc:
        return {"status": "unhealthy", "error": f"Gemini init failed: {exc}"}

    try:
        supabase = _get_supabase_client()
        supabase.table("documents").select("id").limit(1).execute()
    except Exception as exc:
        return {"status": "unhealthy", "error": f"Supabase check failed: {exc}"}

    return {"status": "healthy"}
