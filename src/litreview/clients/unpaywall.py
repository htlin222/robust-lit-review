"""Unpaywall and DOI validation client."""

from __future__ import annotations

import asyncio
import logging
from typing import Self

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)


class UnpaywallClient:
    """Async client for Unpaywall OA lookups and DOI/URL validation."""

    UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
    DOI_API_BASE = "https://doi.org/api/handles"

    def __init__(self, email: str) -> None:
        self.email = email
        self._client = httpx.AsyncClient(timeout=20.0)
        self._semaphore = asyncio.Semaphore(10)

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
    async def check_doi(self, doi: str) -> dict | None:
        """Look up a DOI on Unpaywall and return OA info.

        Returns a dict with keys like is_oa, best_oa_location, etc.,
        or None if the DOI is not found.
        """
        url = f"{self.UNPAYWALL_BASE}/{doi}"
        try:
            response = await self._client.get(url, params={"email": self.email})
            if response.status_code == 404:
                logger.debug("DOI not found on Unpaywall: %s", doi)
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Unpaywall HTTP error for DOI %s: %s", doi, exc.response.status_code)
            raise
        except httpx.HTTPError as exc:
            logger.warning("Unpaywall request error for DOI %s: %s", doi, exc)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def validate_doi(self, doi: str) -> bool:
        """Check whether a DOI resolves via the DOI handle API.

        Returns True if the DOI is valid (responseCode == 1).
        """
        url = f"{self.DOI_API_BASE}/{doi}"
        try:
            response = await self._client.get(url)
            if response.status_code != 200:
                return False
            data = response.json()
            return data.get("responseCode") == 1
        except (httpx.HTTPError, ValueError):
            logger.debug("DOI validation failed for: %s", doi)
            return False

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def validate_url(self, url: str) -> bool:
        """Send a HEAD request to check whether a URL exists.

        Returns True for 2xx/3xx status codes.
        """
        try:
            response = await self._client.head(url, follow_redirects=True)
            return response.status_code < 400
        except httpx.HTTPError:
            logger.debug("URL validation failed for: %s", url)
            return False

    async def enrich_article(self, article: ArticleMetadata) -> ArticleMetadata:
        """Validate DOI and enrich an article with OA information.

        Sets doi_validated, is_open_access, oa_url, and pdf_url on the
        article when data is available.
        """
        if not article.doi:
            return article

        # Validate DOI
        article.doi_validated = await self.validate_doi(article.doi)

        # Check Unpaywall for OA data
        try:
            oa_data = await self.check_doi(article.doi)
            if oa_data:
                article.is_open_access = oa_data.get("is_oa", False)
                best_loc = oa_data.get("best_oa_location") or {}
                article.oa_url = best_loc.get("url")
                article.pdf_url = best_loc.get("url_for_pdf")
        except Exception:
            logger.warning("Unpaywall enrichment failed for DOI: %s", article.doi)

        return article

    async def batch_validate(
        self, articles: list[ArticleMetadata]
    ) -> list[ArticleMetadata]:
        """Validate and enrich all articles concurrently.

        Uses a semaphore to limit concurrency to 10 simultaneous requests.
        """

        async def _enrich_with_limit(article: ArticleMetadata) -> ArticleMetadata:
            async with self._semaphore:
                return await self.enrich_article(article)

        results = await asyncio.gather(
            *[_enrich_with_limit(a) for a in articles],
            return_exceptions=True,
        )

        enriched: list[ArticleMetadata] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Enrichment failed for article: %s", articles[i].title)
                enriched.append(articles[i])
            else:
                enriched.append(result)

        logger.info(
            "Batch validated %d articles (%d with valid DOIs)",
            len(enriched),
            sum(1 for a in enriched if a.doi_validated),
        )
        return enriched
