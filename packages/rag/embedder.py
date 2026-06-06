"""
embedder.py – RAG pipeline embedding helper using Google Gemini.

Provides helpers for:
  • Configuring the Gemini client from environment variables.
  • Embedding single texts and queries via Gemini `models/text-embedding-004`.
  • Sequential batch-embedding of chunk dicts with progress printing and retry logic.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError

load_dotenv()

# ──────────────────────────────────────────────
#  Client Setup
# ──────────────────────────────────────────────

def get_gemini_client() -> genai.Client:
    """Create and return a configured Gemini client.

    Reads `GEMINI_API_KEY` from the environment (loaded via python-dotenv).

    Returns:
        A `genai.Client` instance ready for use.

    Raises:
        ValueError: If `GEMINI_API_KEY` is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
    return genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1"}
    )


# ──────────────────────────────────────────────
#  Embedding Helpers
# ──────────────────────────────────────────────

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


async def _embed_with_retry(text: str, client: genai.Client, task_type: str) -> list[float]:
    """Embed text using Gemini with exponential backoff retry logic.

    Args:
        text: The text to embed.
        client: A `genai.Client` instance.
        task_type: The task type (e.g. RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY).

    Returns:
        The embedding vector as a list of floats.
    """
    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
                config={
                    "task_type": task_type,
                    "output_dimensionality": 768
                }
            )
            return list(response.embeddings[0].values)
        except Exception as exc:
            is_rate_limit = isinstance(exc, ClientError) and "429" in str(exc)
            if is_rate_limit:
                import re
                match = re.search(r'retry in (\d+)', str(exc))
                wait_time = int(match.group(1)) + 2 if match else 30
                print(f"Rate limit hit, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue  # retry without counting as failed attempt
            if attempt == MAX_RETRIES:
                raise ValueError(f"Gemini embedding failed after {MAX_RETRIES} retries: {exc}") from exc
            await asyncio.sleep(backoff)
            backoff *= 2
    return []


async def embed_text(text: str, client: genai.Client) -> list[float]:
    """Embed a single string using Gemini `models/gemini-embedding-001` (RETRIEVAL_DOCUMENT).

    Args:
        text: The text to embed.
        client: A `genai.Client` instance.

    Returns:
        The embedding vector as a list of floats.
    """
    return await _embed_with_retry(text, client, task_type="RETRIEVAL_DOCUMENT")


async def embed_query(text: str, client: genai.Client) -> list[float]:
    """Embed a query string using Gemini `models/text-embedding-004` (RETRIEVAL_QUERY).

    Args:
        text: The query text to embed.
        client: A `genai.Client` instance.

    Returns:
        The embedding vector as a list of floats.
    """
    return await _embed_with_retry(text, client, task_type="RETRIEVAL_QUERY")


async def embed_chunks(
    chunks: list[dict[str, Any]],
    client: genai.Client,
) -> list[dict[str, Any]]:
    """Embed all chunk dicts sequentially, adding an `"embedding"` key to each.

    Processes chunks sequentially using asyncio.

    Args:
        chunks: List of chunk dicts. Each must contain a `"text"` key.
        client: A `genai.Client` instance.

    Returns:
        The same list of chunk dicts with an `"embedding"` key added.
    """
    BATCH_SIZE = 20
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        embedding = await embed_text(chunk["text"], client)
        chunk["embedding"] = embedding
        await asyncio.sleep(0.7)

        current_count = idx + 1
        if current_count % BATCH_SIZE == 0 or current_count == total_chunks:
            print(f"Embedded {current_count}/{total_chunks} chunks...")

    return chunks
