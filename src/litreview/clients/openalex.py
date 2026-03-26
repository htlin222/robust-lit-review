"""OpenAlex API client for journal metrics and article enrichment.

OpenAlex is free, no API key required (just polite pool with email).
Provides: journal-level metrics, citation data, topics, article metadata.

Used together with Scimago CSV for Q1-Q4 quartile lookup.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"


class OpenAlexClient:
    """Async OpenAlex API client."""

    def __init__(self, email: str = ""):
        self._email = email
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        params = {}
        if self._email:
            params["mailto"] = self._email
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            params=params,
            timeout=20,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def close(self):
        if self._client:
            await self._client.aclose()

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    async def get_journal_by_issn(self, issn: str) -> dict | None:
        """Get journal metadata by ISSN."""
        try:
            resp = await self._client.get(f"/sources/issn:{issn}")
            if resp.status_code == 200:
                return resp.json()
            # Try with filter
            resp = await self._client.get("/sources", params={"filter": f"issn:{issn}"})
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                return results[0] if results else None
        except Exception as e:
            logger.warning(f"OpenAlex lookup failed for ISSN {issn}: {e}")
        return None

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    async def get_article_by_doi(self, doi: str) -> dict | None:
        """Get article metadata by DOI."""
        try:
            resp = await self._client.get(f"/works/doi:{doi}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"OpenAlex DOI lookup failed for {doi}: {e}")
        return None

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    async def get_citation_references(self, doi: str) -> list[str]:
        """Get DOIs of articles referenced by this article."""
        try:
            resp = await self._client.get(f"/works/doi:{doi}")
            if resp.status_code == 200:
                work = resp.json()
                refs = work.get("referenced_works", [])
                # Extract DOIs from OpenAlex IDs
                dois = []
                for ref in refs:
                    # ref is like "https://openalex.org/W12345"
                    # Need to resolve to DOI
                    dois.append(ref)
                return dois
        except Exception as e:
            logger.warning(f"OpenAlex references failed for {doi}: {e}")
        return []

    async def get_journal_metrics(self, issn: str) -> dict:
        """Get comprehensive journal metrics.

        Returns dict with:
        - display_name: journal name
        - issn: list of ISSNs
        - works_count: total articles
        - cited_by_count: total citations
        - h_index: h-index
        - impact_factor_approx: 2yr mean citedness (≈ impact factor)
        - is_oa: open access journal
        - topics: top subject areas
        """
        data = await self.get_journal_by_issn(issn)
        if not data:
            return {}

        stats = data.get("summary_stats", {})
        return {
            "display_name": data.get("display_name", ""),
            "issn": data.get("issn", []),
            "works_count": data.get("works_count", 0),
            "cited_by_count": data.get("cited_by_count", 0),
            "h_index": stats.get("h_index", 0),
            "impact_factor_approx": stats.get("2yr_mean_citedness", 0.0),
            "is_oa": data.get("is_oa", False),
            "topics": [t["display_name"] for t in data.get("topics", [])[:5]],
        }

    async def batch_journal_metrics(
        self,
        issns: list[str],
        concurrency: int = 10,
    ) -> dict[str, dict]:
        """Get metrics for multiple journals concurrently."""
        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, dict] = {}

        async def _fetch(issn: str):
            async with semaphore:
                metrics = await self.get_journal_metrics(issn)
                if metrics:
                    results[issn] = metrics
                await asyncio.sleep(0.1)  # Polite rate limiting

        tasks = [_fetch(issn) for issn in set(issns) if issn]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"OpenAlex: fetched metrics for {len(results)}/{len(issns)} journals")
        return results
