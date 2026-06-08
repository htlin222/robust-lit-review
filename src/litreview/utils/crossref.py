"""CrossRef existence verification — anti-hallucination gate.

Every cited work MUST be confirmed to actually exist in CrossRef before it can
appear in an appraisal. This guards against fabricated or mistyped DOIs and
against an LLM inventing a plausible-looking reference: a DOI that does not
resolve in CrossRef is dropped, and a CrossRef record whose title does not match
ours is flagged (low title-match) for review.

CrossRef needs no API key; supplying a mailto puts us in the polite pool.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)

_CROSSREF_BASE = "https://api.crossref.org/works"
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def title_similarity(a: str, b: str) -> float:
    """Jaccard token overlap of two titles in [0, 1]."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
async def _fetch_crossref(client: httpx.AsyncClient, doi: str) -> dict | None:
    resp = await client.get(f"{_CROSSREF_BASE}/{doi}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("message")


async def verify_doi_crossref(
    doi: str, expected_title: str | None = None, mailto: str = ""
) -> dict:
    """Verify a single DOI exists in CrossRef.

    Returns ``{"exists": bool, "title": str, "title_match": float}``.
    """
    headers = {"User-Agent": f"robust-lit-review/1.0 (mailto:{mailto or 'anonymous'})"}
    try:
        async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
            message = await _fetch_crossref(client, doi)
    except Exception as e:  # noqa: BLE001 — network errors mean "unverified", not crash
        logger.warning("CrossRef lookup failed for %s: %s", doi, e)
        return {"exists": False, "title": "", "title_match": 0.0}

    if not message:
        return {"exists": False, "title": "", "title_match": 0.0}

    titles = message.get("title") or []
    cr_title = titles[0] if titles else ""
    match = title_similarity(expected_title, cr_title) if expected_title else 1.0
    return {"exists": True, "title": cr_title, "title_match": match}


async def batch_verify_crossref(
    articles: list[ArticleMetadata], mailto: str = "", concurrency: int = 8
) -> list[ArticleMetadata]:
    """Set ``crossref_verified`` / ``crossref_title_match`` on each article.

    Articles without a DOI cannot be CrossRef-verified and are left
    ``crossref_verified=False`` (the caller decides whether to drop them).
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(article: ArticleMetadata) -> None:
        if not article.doi:
            return
        async with semaphore:
            result = await verify_doi_crossref(article.doi, article.title, mailto)
        article.crossref_verified = bool(result["exists"])
        article.crossref_title_match = float(result["title_match"])

    await asyncio.gather(*(_one(a) for a in articles), return_exceptions=True)
    verified = sum(1 for a in articles if a.crossref_verified)
    logger.info("CrossRef: %d/%d articles confirmed to exist", verified, len(articles))
    return articles


def filter_crossref_verified(
    articles: list[ArticleMetadata], min_title_match: float = 0.0
) -> tuple[list[ArticleMetadata], list[ArticleMetadata]]:
    """Split into (kept, dropped): keep only CrossRef-confirmed works.

    ``min_title_match`` (0..1) optionally also drops confirmed works whose title
    diverges too far from ours (possible wrong-DOI), but defaults to 0 so the
    gate is purely existence-based unless tightened.
    """
    kept: list[ArticleMetadata] = []
    dropped: list[ArticleMetadata] = []
    for a in articles:
        if a.crossref_verified and a.crossref_title_match >= min_title_match:
            kept.append(a)
        else:
            dropped.append(a)
    return kept, dropped
