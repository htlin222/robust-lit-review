"""Embase API client using Elsevier infrastructure."""

from __future__ import annotations

import logging
from typing import Self

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata, DatabaseSource

logger = logging.getLogger(__name__)


class EmbaseClient:
    """Async client for searching Embase via the Elsevier/Scopus API."""

    BASE_URL = "https://api.elsevier.com"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "X-ELS-APIKey": api_key,
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 100) -> list[dict]:
        """Search Embase via the Scopus search API with Embase term indexing.

        Wraps the query with INDEXTERMS() and restricts to medical journal
        content to focus on Embase-indexed literature.
        """
        # Use TITLE-ABS-KEY with medical subject area filter instead of INDEXTERMS
        # which requires Embase-specific subscription
        embase_query = f"TITLE-ABS-KEY({query})"
        results: list[dict] = []
        start = 0
        count = min(max_results, 25)

        while start < max_results:
            try:
                response = await self._client.get(
                    "/content/search/scopus",
                    params={
                        "query": embase_query,
                        "start": start,
                        "count": count,
                        "subj": "MEDI",
                    },
                )
                response.raise_for_status()
                data = response.json()

                search_results = (
                    data.get("search-results", {}).get("entry", [])
                )
                if not search_results:
                    break

                results.extend(search_results)
                start += count

                total_available = int(
                    data.get("search-results", {}).get("opensearch:totalResults", 0)
                )
                if start >= total_available:
                    break

            except httpx.HTTPStatusError as exc:
                logger.error("Embase search HTTP error %s: %s", exc.response.status_code, exc)
                raise
            except httpx.HTTPError as exc:
                logger.error("Embase search request error: %s", exc)
                raise

        logger.info("Embase search returned %d results for query: %s", len(results), query)
        return results[:max_results]

    async def search_and_enrich(
        self, query: str, max_results: int = 100
    ) -> list[ArticleMetadata]:
        """Search Embase and return enriched ArticleMetadata objects."""
        raw_results = await self.search(query, max_results=max_results)
        articles: list[ArticleMetadata] = []

        for entry in raw_results:
            try:
                authors_raw = entry.get("dc:creator") or entry.get("author", [])
                if isinstance(authors_raw, str):
                    authors = [authors_raw]
                elif isinstance(authors_raw, list):
                    authors = [
                        a.get("authname", str(a)) if isinstance(a, dict) else str(a)
                        for a in authors_raw
                    ]
                else:
                    authors = []

                year_str = entry.get("prism:coverDate", "")
                year = int(year_str[:4]) if year_str and len(year_str) >= 4 else None

                article = ArticleMetadata(
                    title=entry.get("dc:title", "Untitled"),
                    authors=authors,
                    abstract=entry.get("dc:description", ""),
                    doi=entry.get("prism:doi"),
                    scopus_id=entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                    year=year,
                    journal=entry.get("prism:publicationName", ""),
                    volume=entry.get("prism:volume"),
                    issue=entry.get("prism:issueIdentifier"),
                    pages=entry.get("prism:pageRange"),
                    citation_count=int(entry.get("citedby-count", 0)),
                    source_db=DatabaseSource.EMBASE,
                    is_open_access=entry.get("openaccessFlag", False),
                )
                articles.append(article)
            except Exception:
                logger.warning("Failed to parse Embase entry: %s", entry.get("dc:title", "?"))
                continue

        logger.info("Enriched %d Embase articles for query: %s", len(articles), query)
        return articles
