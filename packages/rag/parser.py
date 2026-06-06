"""
parser.py – RAG pipeline data parser.

Provides helpers for:
  • Extracting structured sections from raw résumé text.
  • Cleaning and normalising GitHub repo dicts for downstream chunking.
"""

from __future__ import annotations

import re
from typing import Any


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

# Section header patterns (case-insensitive).
# Each key maps to a list of alternative header labels that may appear in a résumé.
_SECTION_ALIASES: dict[str, list[str]] = {
    "education": ["education", "academic", "academics", "qualification", "qualifications"],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
    ],
    "projects": ["projects", "personal projects", "academic projects", "side projects"],
    "skills": [
        "skills",
        "technical skills",
        "technologies",
        "tools",
        "tools & technologies",
        "tools and technologies",
        "core competencies",
    ],
    "summary": [
        "summary",
        "objective",
        "career objective",
        "professional summary",
        "about",
        "about me",
        "profile",
    ],
}

# Build a single compiled pattern per section.
# It matches a line that starts with the header text (optionally followed by a
# colon or dash) so we can split the résumé into blocks.
_SECTION_PATTERNS: dict[str, re.Pattern[str]] = {}
for _section, _aliases in _SECTION_ALIASES.items():
    _alt = "|".join(re.escape(a) for a in _aliases)
    _SECTION_PATTERNS[_section] = re.compile(
        rf"^[\s]*(?:{_alt})[\s]*[:\-–—]?[\s]*$",
        re.IGNORECASE | re.MULTILINE,
    )

# Known technologies for tech-stack detection in GitHub repos.
_KNOWN_TECHNOLOGIES: list[str] = [
    "Python",
    "FastAPI",
    "React",
    "Next.js",
    "TypeScript",
    "PostgreSQL",
    "Redis",
    "Docker",
    "OpenAI",
    "LangChain",
    "Supabase",
    "MongoDB",
    "Node.js",
    "Express",
    "Tailwind",
]

# Pre-compiled case-insensitive patterns for each technology.
_TECH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (tech, re.compile(re.escape(tech), re.IGNORECASE)) for tech in _KNOWN_TECHNOLOGIES
]


# ──────────────────────────────────────────────
#  1. Résumé parsing
# ──────────────────────────────────────────────


def parse_resume(text: str) -> dict[str, Any]:
    """Parse raw résumé text into structured sections.

    Uses simple regex header detection to split the document into known
    sections (education, experience, projects, skills, summary).

    Args:
        text: Raw text extracted from a PDF résumé.

    Returns:
        A dict with two keys:

        - ``"raw"`` – the original full text.
        - ``"sections"`` – a dict mapping each section name to its extracted
          text (empty string if the section was not found).
    """
    sections: dict[str, str] = {key: "" for key in _SECTION_ALIASES}

    # Collect every (section_name, start_index, header_end_index) match.
    markers: list[tuple[str, int, int]] = []
    for section, pattern in _SECTION_PATTERNS.items():
        for match in pattern.finditer(text):
            markers.append((section, match.start(), match.end()))

    # Sort by position in the document.
    markers.sort(key=lambda m: m[1])

    # Slice the text between consecutive headers.
    for i, (section, _start, header_end) in enumerate(markers):
        # Content runs from end-of-header to start-of-next-header (or EOF).
        next_start = markers[i + 1][1] if i + 1 < len(markers) else len(text)
        content = text[header_end:next_start].strip()
        # If the same section appears more than once, concatenate.
        if sections[section]:
            sections[section] += "\n\n" + content
        else:
            sections[section] = content

    return {
        "raw": text,
        "sections": sections,
    }


# ──────────────────────────────────────────────
#  2. GitHub repo parsing
# ──────────────────────────────────────────────


def _detect_tech_stack(readme: str, languages: str) -> list[str]:
    """Scan *readme* and *languages* for known technologies.

    Args:
        readme: Full README text.
        languages: Comma-separated language names.

    Returns:
        De-duplicated list of matched technology names (original casing).
    """
    combined = f"{readme}\n{languages}"
    found: list[str] = []
    for tech, pattern in _TECH_PATTERNS:
        if pattern.search(combined):
            found.append(tech)
    return found


def parse_repo(repo: dict[str, Any]) -> dict[str, Any]:
    """Clean and normalise a raw repo dict from :func:`loader.fetch_github_repos`.

    Args:
        repo: A single repository dict as returned by the loader.

    Returns:
        A cleaned dict containing:

        - ``name``, ``description``, ``stars`` – basic metadata.
        - ``languages`` – comma-separated language names (bytes stripped).
        - ``readme_summary`` – first 500 characters of the README.
        - ``readme_full`` – full README text.
        - ``file_tree`` – flat list of file-path strings.
        - ``commits`` – list of commit-message strings.
        - ``tech_stack`` – detected technologies.
    """
    readme: str = repo.get("readme") or ""
    languages_dict: dict[str, int] = repo.get("languages") or {}
    languages_str = ", ".join(languages_dict.keys())

    file_tree_raw: list[dict[str, Any]] = repo.get("file_tree") or []
    file_paths = [item.get("path", "") for item in file_tree_raw if item.get("path")]

    commits_raw: list[dict[str, str]] = repo.get("commits") or []
    commit_messages = [c.get("message", "") for c in commits_raw if c.get("message")]

    if len(readme) < 1000:
        readme_summary = readme
    elif len(readme) <= 3000:
        readme_summary = readme[:1000]
    else:
        readme_summary = readme[:1500]

    tech_stack = _detect_tech_stack(readme, languages_str)

    return {
        "name": repo.get("name", ""),
        "description": repo.get("description", ""),
        "languages": languages_str,
        "stars": repo.get("stars", 0),
        "readme_summary": readme_summary,
        "readme_full": readme,
        "file_tree": file_paths,
        "commits": commit_messages,
        "tech_stack": tech_stack,
    }


def parse_all_repos(repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply :func:`parse_repo` to every repo in *repos*.

    Args:
        repos: List of raw repo dicts from the loader.

    Returns:
        List of cleaned repo dicts.
    """
    return [parse_repo(repo) for repo in repos]
