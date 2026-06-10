"""
indexer.py – RAG pipeline Supabase indexer.

Provides helpers for:
  • Configuring the Supabase client from environment variables.
  • Upserting embedded chunks into Supabase.
  • Deleting documents by source for re-indexing.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def get_supabase_client() -> Client:
    
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

    return create_client(url, key)

UPSERT_BATCH_SIZE = 50

def upsert_chunks(chunks: list[dict[str, Any]], client: Client) -> int:
    
    total = len(chunks)
    upserted = 0

    # Keys that map directly to table columns (not metadata).
    _COLUMN_KEYS = {"id", "text", "embedding", "source"}

    for i in range(0, total, UPSERT_BATCH_SIZE):
        batch = chunks[i : i + UPSERT_BATCH_SIZE]
        batch_num = i // UPSERT_BATCH_SIZE + 1
        total_batches = (total + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
        print(f"Upserting batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        rows: list[dict[str, Any]] = []
        for chunk in batch:
            metadata = {k: v for k, v in chunk.items() if k not in _COLUMN_KEYS}
            rows.append(
                {
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "embedding": chunk["embedding"],
                    "source": chunk["source"],
                    "metadata": metadata,
                }
            )

        try:
            client.table("documents").upsert(rows).execute()
            upserted += len(rows)
        except Exception as exc:
            print(f"Error upserting batch {batch_num}: {exc}")

    print(f"Upserted {upserted}/{total} chunks.")
    return upserted


def delete_by_source(source: str, client: Client) -> None:
    
    try:
        client.table("documents").delete().eq("source", source).execute()
        print(f"Deleted all documents with source='{source}'.")
    except Exception as exc:
        print(f"Error deleting documents with source='{source}': {exc}")
