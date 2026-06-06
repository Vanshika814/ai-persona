"""
loader.py – RAG pipeline data loader.

Provides helpers for:
  • Extracting text from a local PDF résumé (pypdf).
  • Fetching rich GitHub profile data (httpx, async).
  • Detecting repo changes via commit-SHA hashing.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

GITHUB_API = "https://api.github.com"

MAX_TREE_DEPTH = 2

SHA_STORE_DIR = Path(__file__).resolve().parents[3] / "data" / "github-dump"
SHA_STORE_PATH = SHA_STORE_DIR / ".repo_shas.json"


# ──────────────────────────────────────────────
#  1. Local résumé loading
# ──────────────────────────────────────────────


def load_resume_pdf(path: str) -> str:
    """Extract and return all text from a PDF file.

    Args:
        path: Filesystem path to the PDF résumé.

    Returns:
        The concatenated text of every page in the PDF.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file cannot be read as a valid PDF.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {path}")

    try:
        reader = PdfReader(str(file_path))
    except Exception as exc:
        raise ValueError(f"Unable to read PDF at {path}: {exc}") from exc

    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text.strip())

    return "\n\n".join(pages_text)


# ──────────────────────────────────────────────
#  2. GitHub loading (async)
# ──────────────────────────────────────────────


def _auth_headers(token: str) -> dict[str, str]:
    """Return common headers for authenticated GitHub API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _check_rate_limit(response: httpx.Response) -> None:
    """Raise a clear error when the GitHub rate limit is exhausted."""
    if response.status_code == 403:
        remaining = response.headers.get("x-ratelimit-remaining", "?")
        reset = response.headers.get("x-ratelimit-reset", "?")
        raise RuntimeError(
            f"GitHub API rate limit hit (remaining={remaining}). "
            f"Resets at Unix timestamp {reset}."
        )


async def _get(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    fallback: Any = None,
    empty_statuses: tuple[int, ...] = (404,),
) -> Any:
    """Shared GET helper: handles fallback statuses, rate-limit & error raising."""
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code in empty_statuses:
        return fallback
    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp.json()


async def _fetch_repo_readme(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict[str, str],
) -> str:
    """Fetch and decode a repo's README, returning empty string on failure."""
    data = await _get(client, f"{GITHUB_API}/repos/{owner}/{repo}/readme", headers, fallback=None)
    if data is None:
        return ""
    try:
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
    except Exception:
        return ""


async def _fetch_file_tree(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    default_branch: str,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    """Fetch the recursive file tree, filtered to *MAX_TREE_DEPTH* levels."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    data = await _get(client, url, headers, fallback=None, empty_statuses=(404, 409))
    if data is None:
        return []

    return [
        {"path": item.get("path", ""), "type": item.get("type"), "size": item.get("size")}
        for item in data.get("tree", [])
        if item.get("path", "").count("/") + 1 <= MAX_TREE_DEPTH
    ]


async def _fetch_commits(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict[str, str],
    max_commits: int = 100,
) -> list[dict[str, str]]:
    """Fetch all commits up to *max_commits* without any filtering."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    data = await _get(client, url, headers, params={"per_page": max_commits}, fallback=None, empty_statuses=(409,))
    if data is None:
        return []

    return [
        {
            "sha": c.get("sha", "")[:7],
            "message": c.get("commit", {}).get("message", "").split("\n", 1)[0],
            "date": c.get("commit", {}).get("author", {}).get("date", ""),
        }
        for c in data
    ]


async def _fetch_languages(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict[str, str],
) -> dict[str, int]:
    """Fetch the languages breakdown (bytes per language) for a repo."""
    return await _get(client, f"{GITHUB_API}/repos/{owner}/{repo}/languages", headers, fallback={})


async def fetch_github_repos(
    username: str,
    token: str,
    max_commits: int = 100,
) -> list[dict[str, Any]]:
    """Fetch all public repos for *username* with rich metadata.
    
    For every repo the following data is collected:
      - **metadata** - name, description, language, stargazers count
      - **readme** - decoded README content (or empty string)
      - **file_tree** - recursive listing limited to depth 2
      - **commits** - all commits up to *max_commits*
      - **languages** - bytes-per-language breakdown

    Args:
        username: GitHub username whose public repos to fetch.
        token: GitHub personal access token (for 5 000 req/hr limit).

    Returns:
        A list of dicts, one per repository.
    """
    headers = _auth_headers(token)
    repos_out: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Paginate through all public repos
        page = 1
        all_repos: list[dict[str, Any]] = []

        while True:
            url = f"{GITHUB_API}/users/{username}/repos"
            resp = await client.get(
                url,
                headers=headers,
                params={"per_page": 100, "page": page, "type": "public"},
            )
            _check_rate_limit(resp)
            resp.raise_for_status()

            batch: list[dict[str, Any]] = resp.json()
            if not batch:
                break
            all_repos.extend(batch)
            page += 1

        # Enrich each repo and track SHAs
        stored_shas = load_stored_shas()

        for repo in all_repos:
            repo_name: str = repo["name"]
            default_branch: str = repo.get("default_branch", "main")

            readme = await _fetch_repo_readme(client, username, repo_name, headers)
            file_tree = await _fetch_file_tree(
                client, username, repo_name, default_branch, headers
            )
            commits = await _fetch_commits(client, username, repo_name, headers, max_commits)
            languages = await _fetch_languages(client, username, repo_name, headers)

            repos_out.append(
                {
                    "name": repo_name,
                    "description": repo.get("description") or "",
                    "language": repo.get("language") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "default_branch": default_branch,
                    "readme": readme,
                    "file_tree": file_tree,
                    "commits": commits,
                    "languages": languages,
                }
            )

            # Update stored SHA for this repo
            sha = commits[0]["sha"] if commits else ""
            if sha:
                stored_shas[f"{username}/{repo_name}"] = sha

        save_shas(stored_shas)

    return repos_out


# ──────────────────────────────────────────────
#  3. Commit-SHA change detection
# ──────────────────────────────────────────────


async def get_commit_sha(username: str, repo: str, token: str) -> str:
    """Fetch the latest commit SHA for *repo* owned by *username*.

    Args:
        username: GitHub repository owner.
        repo: Repository name.
        token: GitHub personal access token.

    Returns:
        The full SHA string of the most recent commit, or an empty string
        if the repo has no commits.
    """
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{GITHUB_API}/repos/{username}/{repo}/commits"
        data = await _get(client, url, headers, params={"per_page": 1}, fallback=None, empty_statuses=(409,))
        if not data:
            return ""
        return data[0].get("sha", "")


def load_stored_shas() -> dict[str, str]:
    """Load previously stored commit SHAs from disk.

    Returns:
        A dict mapping ``"owner/repo"`` → SHA string.
        Returns an empty dict if the file does not exist.
    """
    if not SHA_STORE_PATH.exists():
        return {}

    try:
        return json.loads(SHA_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_shas(shas: dict[str, str]) -> None:
    """Persist commit SHAs to disk.

    Args:
        shas: Mapping of ``"owner/repo"`` → SHA string.
    """
    SHA_STORE_DIR.mkdir(parents=True, exist_ok=True)
    SHA_STORE_PATH.write_text(
        json.dumps(shas, indent=2) + "\n",
        encoding="utf-8",
    )


async def has_repo_changed(username: str, repo: str, token: str) -> bool:
    """Check whether a repo has new commits since the last recorded SHA.

    Compares the current HEAD SHA with the value stored in
    ``data/github-dump/.repo_shas.json``.

    Args:
        username: GitHub repository owner.
        repo: Repository name.
        token: GitHub personal access token.

    Returns:
        ``True`` if the repo is new or has changed; ``False`` otherwise.
    """
    current_sha = await get_commit_sha(username, repo, token)

    if not current_sha:
        # Empty repo – treat as unchanged (nothing to index).
        return False

    stored = load_stored_shas()
    key = f"{username}/{repo}"

    return stored.get(key) != current_sha
