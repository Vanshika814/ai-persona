"""
chunker.py – RAG pipeline text chunker.

Provides helpers for:
  • Token-aware text chunking with sentence-boundary splitting.
  • Structured chunking of parsed résumés and GitHub repos.
  • Combining all chunks into a single flat list with unique IDs.
"""

from __future__ import annotations

import re
from typing import Any

import tiktoken

# ──────────────────────────────────────────────
#  Encoder (lazily cached)
# ──────────────────────────────────────────────

_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    """Return (and cache) the cl100k_base tiktoken encoder."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


# Sentence-boundary pattern: split *after* a terminator followed by whitespace.
_SENTENCE_SPLIT: re.Pattern[str] = re.compile(r"(?<=[.!?])[\s]+")


# ──────────────────────────────────────────────
#  1. Core chunking
# ──────────────────────────────────────────────


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[str]:
    """Split *text* into token-sized chunks with overlap.

    Uses the ``cl100k_base`` tiktoken encoding for accurate token counting.
    Splitting is performed on sentence boundaries where possible so that
    sentences are never cut mid-way if avoidable.

    Args:
        text: The input text to chunk.
        chunk_size: Target number of tokens per chunk.
        overlap: Number of tokens to overlap between consecutive chunks.

    Returns:
        A list of non-empty string chunks.
    """
    text = text.strip()
    if not text:
        return []

    enc = _get_encoder()

    # Split into sentences first.
    sentences = _SENTENCE_SPLIT.split(text)
    # Remove empty fragments that may result from the split.
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = len(enc.encode(sentence))

        # If a single sentence exceeds chunk_size, add it as its own chunk.
        if sentence_tokens > chunk_size:
            # Flush anything accumulated so far.
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0
            chunks.append(sentence)
            continue

        # Would adding this sentence exceed the limit?
        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            chunks.append(" ".join(current_sentences))

            # Build overlap: walk backwards keeping up to *overlap* tokens.
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                s_tok = len(enc.encode(s))
                if overlap_tokens + s_tok > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tok

            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    # Flush remaining.
    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c for c in chunks if c.strip()]


# ──────────────────────────────────────────────
#  2. Résumé chunking
# ──────────────────────────────────────────────


def chunk_resume(parsed_resume: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk each section of a parsed résumé separately.

    Also chunks the full raw text under section ``"raw"``.

    Args:
        parsed_resume: Dict returned by :func:`parser.parse_resume`.

    Returns:
        List of chunk dicts, each containing:

        - ``text`` – the chunk string.
        - ``source`` – ``"resume"``.
        - ``section`` – section name (e.g. ``"experience"``).
        - ``chunk_index`` – zero-based index within that section.
    """
    chunks: list[dict[str, Any]] = []

    # Chunk individual sections.
    sections: dict[str, str] = parsed_resume.get("sections", {})
    for section_name, section_text in sections.items():
        if not section_text or not section_text.strip():
            continue
        for idx, chunk in enumerate(chunk_text(section_text)):
            chunks.append(
                {
                    "text": chunk,
                    "source": "resume",
                    "section": section_name,
                    "chunk_index": idx,
                }
            )

    # Chunk the full raw text.
    raw: str = parsed_resume.get("raw", "")
    if raw and raw.strip():
        for idx, chunk in enumerate(chunk_text(raw)):
            chunks.append(
                {
                    "text": chunk,
                    "source": "resume",
                    "section": "raw",
                    "chunk_index": idx,
                }
            )

    return chunks


# ──────────────────────────────────────────────
#  3. Repo chunking
# ──────────────────────────────────────────────


def chunk_repo(parsed_repo: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk a parsed GitHub repo into typed segments.

    Creates:
      • Multiple README chunks (via :func:`chunk_text`).
      • One metadata chunk (name + description + languages + stars + tech_stack).
      • One file-tree chunk (paths joined by newlines).
      • One commits chunk (messages joined by newlines).

    Args:
        parsed_repo: Dict returned by :func:`parser.parse_repo`.

    Returns:
        List of chunk dicts, each containing:

        - ``text`` – the chunk string.
        - ``source`` – ``"github"``.
        - ``repo`` – repository name.
        - ``type`` – one of ``"readme"``, ``"metadata"``, ``"file_tree"``,
          ``"commits"``.
        - ``chunk_index`` – zero-based index within that type.
    """
    repo_name: str = parsed_repo.get("name", "")
    chunks: list[dict[str, Any]] = []

    # ── README chunks ──────────────────────────
    readme: str = parsed_repo.get("readme_full", "")
    if readme and readme.strip():
        for idx, chunk in enumerate(chunk_text(readme)):
            chunks.append(
                {
                    "text": chunk,
                    "source": "github",
                    "repo": repo_name,
                    "type": "readme",
                    "chunk_index": idx,
                }
            )

    # ── Metadata chunk ─────────────────────────
    tech_stack: list[str] = parsed_repo.get("tech_stack", [])
    meta_parts = [
        f"Repository: {repo_name}",
        f"Description: {parsed_repo.get('description', '')}",
        f"Languages: {parsed_repo.get('languages', '')}",
        f"Stars: {parsed_repo.get('stars', 0)}",
        f"Tech Stack: {', '.join(tech_stack) if tech_stack else 'N/A'}",
    ]
    meta_text = "\n".join(meta_parts).strip()
    if meta_text:
        chunks.append(
            {
                "text": meta_text,
                "source": "github",
                "repo": repo_name,
                "type": "metadata",
                "chunk_index": 0,
            }
        )

    # ── File-tree chunk ────────────────────────
    file_tree: list[str] = parsed_repo.get("file_tree", [])
    if file_tree:
        tree_text = "\n".join(file_tree)
        chunks.append(
            {
                "text": tree_text,
                "source": "github",
                "repo": repo_name,
                "type": "file_tree",
                "chunk_index": 0,
            }
        )

    # ── Commits chunk ──────────────────────────
    commit_messages: list[str] = parsed_repo.get("commits", [])
    if commit_messages:
        commits_text = "\n".join(commit_messages)
        for idx, chunk in enumerate(chunk_text(commits_text)):
            chunks.append(
                {
                    "text": chunk,
                    "source": "github",
                    "repo": repo_name,
                    "type": "commits",
                    "chunk_index": idx,
                }
            )

    return chunks


# ──────────────────────────────────────────────
#  4. Combined chunking
# ──────────────────────────────────────────────


def chunk_all(
    parsed_resume: dict[str, Any],
    parsed_repos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Chunk a résumé and all repos into a single flat list with unique IDs.

    Each chunk receives an ``"id"`` field of the form::

        resume_{section}_{chunk_index}
        github_{repo}_{type}_{chunk_index}

    Args:
        parsed_resume: Dict returned by :func:`parser.parse_resume`.
        parsed_repos: List of dicts returned by :func:`parser.parse_all_repos`.

    Returns:
        A single flat list of chunk dicts, each with an added ``"id"`` key.
    """
    all_chunks: list[dict[str, Any]] = []

    # Résumé chunks.
    for chunk in chunk_resume(parsed_resume):
        chunk["id"] = f"{chunk['source']}_{chunk['section']}_{chunk['chunk_index']}"
        all_chunks.append(chunk)

    # Repo chunks.
    for repo in parsed_repos:
        for chunk in chunk_repo(repo):
            chunk["id"] = f"{chunk['source']}_{chunk['repo']}_{chunk['type']}_{chunk['chunk_index']}"
            all_chunks.append(chunk)

    return all_chunks
