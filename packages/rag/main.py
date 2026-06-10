
from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from dotenv import load_dotenv

try:
    from . import chunker, embedder, indexer, loader, parser, retriever
except (ImportError, ValueError):
    import chunker  # type: ignore
    import embedder  # type: ignore
    import indexer  # type: ignore
    import loader  # type: ignore
    import parser  # type: ignore
    import retriever  # type: ignore

load_dotenv()

async def run_indexing(username: str, token: str, resume_path: str) -> None:
    # ── Load ───────────────────────────────────
    print("Loading resume PDF...")
    resume_text = loader.load_resume_pdf(resume_path)
    print(f"Resume loaded ({len(resume_text)} chars).")

    print(f"Fetching GitHub repos for {username}...")
    repos_raw = await loader.fetch_github_repos(username, token)
    print(f"Fetched {len(repos_raw)} repos.")

    # ── Parse ──────────────────────────────────
    print("Parsing resume...")
    parsed_resume = parser.parse_resume(resume_text)

    print("Parsing repos...")
    parsed_repos = parser.parse_all_repos(repos_raw)

    # ── Chunk ──────────────────────────────────
    print("Chunking all data...")
    all_chunks: list[dict[str, Any]] = chunker.chunk_all(parsed_resume, parsed_repos)
    print(f"Total chunks: {len(all_chunks)}")

    # ── Embed ──────────────────────────────────
    print("Getting Gemini client...")
    gemini_client = embedder.get_gemini_client()

    print("Embedding chunks...")
    embedded_chunks = await embedder.embed_chunks(all_chunks, gemini_client)
    print(f"Embedded {len(embedded_chunks)} chunks.")

    # ── Upsert ─────────────────────────────────
    print("Getting Supabase client...")
    supabase_client = indexer.get_supabase_client()

    print("Clearing stale resume data...")
    indexer.delete_by_source("resume", supabase_client)

    print("Clearing stale github data...")
    indexer.delete_by_source("github", supabase_client)

    print("Upserting chunks...")
    count = indexer.upsert_chunks(embedded_chunks, supabase_client)
    print(f"Upserted {count} chunks.")

    print("Indexing complete!")

async def run_query(query: str) -> str:
    
    gemini_client = embedder.get_gemini_client()
    supabase_client = indexer.get_supabase_client()

    print(f"Querying: {query}")
    chunks = await retriever.retrieve(query, gemini_client, supabase_client, top_k=5)
    print(f"Retrieved {len(chunks)} chunks.")

    context = retriever.format_context(chunks)
    return context

def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate pipeline."""
    arg_parser = argparse.ArgumentParser(
        description="RAG pipeline – index data or run test queries.",
    )
    subparsers = arg_parser.add_subparsers(dest="command", required=True)

    # ── index subcommand ───────────────────────
    index_parser = subparsers.add_parser("index", help="Run the full indexing pipeline.")
    index_parser.add_argument(
        "--username",
        required=True,
        help="GitHub username whose repos to index.",
    )
    index_parser.add_argument(
        "--resume",
        required=True,
        help="Path to the resume PDF file.",
    )

    # ── query subcommand ───────────────────────
    query_parser = subparsers.add_parser("query", help="Run a test retrieval query.")
    query_parser.add_argument(
        "--query",
        required=True,
        help="Natural-language query string.",
    )

    args = arg_parser.parse_args()

    if args.command == "index":
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            print("Warning: GITHUB_TOKEN not set. API rate limits will be very low.")
        asyncio.run(run_indexing(args.username, token, args.resume))

    elif args.command == "query":
        context = asyncio.run(run_query(args.query))
        print("\n── Retrieved Context ─────────────────────")
        print(context or "(no matching chunks found)")


if __name__ == "__main__":
    main()
