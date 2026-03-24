"""Async Scopus API client using httpx with retry support."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata, DatabaseSource

logger = logging.getLogger(__name__)


class ScopusClient:
    """Async client for the Elsevier Scopus APIs.

    Supports searching articles, retrieving article details,
    and fetching journal-level metrics (CiteScore, SJR, SNIP).
    """

    BASE_URL = "https://api.elsevier.com"
    RESULTS_PER_PAGE = 25

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

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> ScopusClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Search API
    # ------------------------------------------------------------------

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3))
    async def _fetch_search_page(
        self, query: str, start: int
    ) -> dict:
        """Fetch a single page of Scopus search results."""
        response = await self._client.get(
            "/content/search/scopus",
            params={
                "query": query,
                "start": start,
                "count": self.RESULTS_PER_PAGE,
            },
        )
        response.raise_for_status()
        return response.json()

    async def search(self, query: str, max_results: int = 100) -> list[dict]:
        """Search Scopus and return raw entry dicts, handling pagination.

        Parameters
        ----------
        query:
            Scopus search query string.
        max_results:
            Maximum number of results to retrieve.

        Returns
        -------
        list[dict]
            List of raw Scopus entry dictionaries.
        """
        entries: list[dict] = []
        start = 0

        try:
            while start < max_results:
                data = await self._fetch_search_page(query, start)
                results = data.get("search-results", {})
                page_entries = results.get("entry", [])

                if not page_entries:
                    break

                # Scopus returns an error entry when no results are found
                if len(page_entries) == 1 and page_entries[0].get("error"):
                    logger.warning(
                        "Scopus search returned error: %s",
                        page_entries[0].get("error"),
                    )
                    break

                entries.extend(page_entries)

                total_results = int(results.get("opensearch:totalResults", 0))
                if start + self.RESULTS_PER_PAGE >= total_results:
                    break

                start += self.RESULTS_PER_PAGE

        except Exception:
            logger.warning("Scopus search failed for query: %s", query, exc_info=True)

        return entries[:max_results]

    # ------------------------------------------------------------------
    # Abstract Retrieval API
    # ------------------------------------------------------------------

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3))
    async def get_article(self, scopus_id: str) -> dict:
        """Retrieve full article metadata via the Abstract Retrieval API.

        Parameters
        ----------
        scopus_id:
            The Scopus document ID.

        Returns
        -------
        dict
            Article metadata dictionary, or empty dict on failure.
        """
        try:
            response = await self._client.get(
                f"/content/abstract/scopus_id/{scopus_id}",
            )
            response.raise_for_status()
            data = response.json()
            return data.get("abstracts-retrieval-response", {})
        except Exception:
            logger.warning(
                "Failed to retrieve article %s", scopus_id, exc_info=True
            )
            return {}

    # ------------------------------------------------------------------
    # Serial Title (Journal Metrics) API
    # ------------------------------------------------------------------

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3))
    async def get_journal_metrics(self, issn: str) -> dict:
        """Fetch journal-level metrics (CiteScore, SJR, SNIP).

        Parameters
        ----------
        issn:
            The ISSN of the journal.

        Returns
        -------
        dict
            Dictionary with keys ``citescore``, ``sjr``, ``snip``.
            Values are floats or ``None`` when unavailable.
        """
        try:
            response = await self._client.get(
                f"/content/serial/title/issn/{issn}",
            )
            response.raise_for_status()
            data = response.json()

            # Navigate into the serial-metadata-response
            entries = (
                data.get("serial-metadata-response", {})
                .get("entry", [])
            )
            if not entries:
                return {"citescore": None, "sjr": None, "snip": None}

            entry = entries[0] if isinstance(entries, list) else entries

            citescore_raw = entry.get("citeScoreCurrentMetric")
            sjr_raw = entry.get("SJR")
            snip_raw = entry.get("SNIP")

            return {
                "citescore": float(citescore_raw) if citescore_raw else None,
                "sjr": float(sjr_raw) if sjr_raw else None,
                "snip": float(snip_raw) if snip_raw else None,
            }

        except Exception:
            logger.warning(
                "Failed to retrieve journal metrics for ISSN %s",
                issn,
                exc_info=True,
            )
            return {"citescore": None, "sjr": None, "snip": None}

    # ------------------------------------------------------------------
    # Search + Enrich
    # ------------------------------------------------------------------

    async def search_and_enrich(
        self, query: str, max_results: int = 100
    ) -> list[ArticleMetadata]:
        """Search Scopus and enrich results with journal metrics.

        Parameters
        ----------
        query:
            Scopus search query string.
        max_results:
            Maximum number of results to retrieve.

        Returns
        -------
        list[ArticleMetadata]
            Enriched article metadata objects.
        """
        entries = await self.search(query, max_results=max_results)
        articles: list[ArticleMetadata] = []

        # Cache journal metrics by ISSN to avoid duplicate lookups
        metrics_cache: dict[str, dict] = {}

        for entry in entries:
            try:
                article = self._parse_entry(entry)

                # Enrich with journal metrics when ISSN is available
                issn = entry.get("prism:issn", "").replace("-", "")
                if issn:
                    if issn not in metrics_cache:
                        metrics_cache[issn] = await self.get_journal_metrics(issn)
                    metrics = metrics_cache[issn]
                    article.citescore = metrics.get("citescore")
                    article.sjr = metrics.get("sjr")
                    article.snip = metrics.get("snip")

                articles.append(article)

            except Exception:
                logger.warning(
                    "Failed to parse Scopus entry: %s",
                    entry.get("dc:title", "<unknown>"),
                    exc_info=True,
                )

        return articles

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entry(entry: dict) -> ArticleMetadata:
        """Convert a raw Scopus search entry into an ArticleMetadata object."""
        # Extract Scopus ID from dc:identifier (format "SCOPUS_ID:xxx")
        raw_id = entry.get("dc:identifier", "")
        scopus_id = raw_id.split(":")[-1] if ":" in raw_id else raw_id

        # Parse year from cover date
        cover_date = entry.get("prism:coverDate", "")
        year: int | None = None
        if cover_date:
            try:
                year = int(cover_date[:4])
            except (ValueError, IndexError):
                pass

        # Parse citation count
        try:
            citation_count = int(entry.get("citedby-count", 0))
        except (ValueError, TypeError):
            citation_count = 0

        # Authors — Scopus search only returns first author in dc:creator
        creator = entry.get("dc:creator", "")
        authors = [creator] if creator else []

        return ArticleMetadata(
            title=entry.get("dc:title", ""),
            authors=authors,
            abstract=entry.get("dc:description", "") or "",
            doi=entry.get("prism:doi"),
            scopus_id=scopus_id or None,
            year=year,
            journal=entry.get("prism:publicationName", ""),
            volume=entry.get("prism:volume"),
            issue=entry.get("prism:issueIdentifier"),
            pages=entry.get("prism:pageRange"),
            citation_count=citation_count,
            source_db=DatabaseSource.SCOPUS,
        )
