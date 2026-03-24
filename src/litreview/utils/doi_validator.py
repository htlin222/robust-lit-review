from __future__ import annotations
import asyncio
import logging
import re
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

DOI_REGEX = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)

async def is_valid_doi_format(doi: str) -> bool:
    """Check DOI format against regex."""
    return bool(DOI_REGEX.match(doi.strip()))

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
async def resolve_doi(doi: str) -> dict | None:
    """Resolve a DOI via doi.org API and return metadata."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # First check via handle API
        resp = await client.get(f"https://doi.org/api/handles/{doi}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("responseCode") != 1:
            return None

        # Get metadata via content negotiation
        resp2 = await client.get(
            f"https://doi.org/{doi}",
            headers={"Accept": "application/citeproc+json"},
        )
        if resp2.status_code == 200:
            return resp2.json()
        return {"resolved": True, "doi": doi}

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
async def validate_url_exists(url: str) -> bool:
    """Check if a URL resolves (2xx or 3xx)."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.head(url)
            return resp.status_code < 400
    except Exception:
        return False

async def batch_validate_dois(dois: list[str], concurrency: int = 10) -> dict[str, bool]:
    """Validate multiple DOIs concurrently."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _validate(doi: str) -> tuple[str, bool]:
        async with semaphore:
            if not await is_valid_doi_format(doi):
                return doi, False
            result = await resolve_doi(doi)
            return doi, result is not None

    tasks = [_validate(doi) for doi in dois]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        doi: valid
        for doi, valid in results
        if not isinstance((doi, valid), BaseException)
    }
