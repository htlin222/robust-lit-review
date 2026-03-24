"""Async PubMed API client using NCBI E-utilities."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Self

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata, DatabaseSource

logger = logging.getLogger(__name__)

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    """Async client for the PubMed E-utilities API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # ESearch
    # ------------------------------------------------------------------

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), reraise=True)
    async def search(self, query: str, max_results: int = 100) -> list[str]:
        """Search PubMed and return a list of PMIDs."""
        params = {
            "db": "pubmed",
            "retmode": "json",
            "retmax": max_results,
            "api_key": self.api_key,
            "term": query,
        }
        resp = await self._client.get("/esearch.fcgi", params=params)
        resp.raise_for_status()
        data = resp.json()
        pmids: list[str] = data.get("esearchresult", {}).get("idlist", [])
        logger.info("PubMed search returned %d PMIDs for query: %s", len(pmids), query)
        return pmids

    # ------------------------------------------------------------------
    # EFetch
    # ------------------------------------------------------------------

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), reraise=True)
    async def _fetch_batch(self, pmids: list[str]) -> str:
        """Fetch a single batch of articles as XML text."""
        params = {
            "db": "pubmed",
            "retmode": "xml",
            "rettype": "abstract",
            "id": ",".join(pmids),
            "api_key": self.api_key,
        }
        resp = await self._client.get("/efetch.fcgi", params=params)
        resp.raise_for_status()
        return resp.text

    async def fetch_articles(self, pmids: list[str]) -> list[dict]:
        """Fetch article details for *pmids* in batches of 200.

        Returns a list of dicts with keys: title, authors, abstract, doi,
        pmid, year, journal, volume, issue, pages.
        """
        articles: list[dict] = []
        batch_size = 200
        for start in range(0, len(pmids), batch_size):
            batch = pmids[start : start + batch_size]
            try:
                xml_text = await self._fetch_batch(batch)
                articles.extend(self._parse_articles_xml(xml_text))
            except Exception:
                logger.exception("Failed to fetch batch starting at index %d", start)
        return articles

    # ------------------------------------------------------------------
    # Combined search + fetch
    # ------------------------------------------------------------------

    async def search_and_fetch(
        self, query: str, max_results: int = 100
    ) -> list[ArticleMetadata]:
        """Search PubMed and return fully-populated ArticleMetadata objects."""
        pmids = await self.search(query, max_results=max_results)
        if not pmids:
            return []
        raw_articles = await self.fetch_articles(pmids)
        return [
            ArticleMetadata(
                source_db=DatabaseSource.PUBMED,
                **article,
            )
            for article in raw_articles
        ]

    # ------------------------------------------------------------------
    # XML parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_articles_xml(xml_text: str) -> list[dict]:
        """Parse EFetch XML into a list of article dicts."""
        articles: list[dict] = []
        try:
            root = ET.fromstring(xml_text)  # noqa: S314
        except ET.ParseError:
            logger.exception("Failed to parse PubMed XML response")
            return articles

        for article_el in root.findall(".//PubmedArticle"):
            try:
                articles.append(PubMedClient._parse_single_article(article_el))
            except Exception:
                logger.exception("Failed to parse a PubmedArticle element")
        return articles

    @staticmethod
    def _parse_single_article(article_el: ET.Element) -> dict:
        """Extract metadata from a single <PubmedArticle> element."""
        citation = article_el.find("MedlineCitation")
        article = citation.find("Article") if citation is not None else None

        def _text(el: ET.Element | None, path: str) -> str:
            node = el.find(path) if el is not None else None
            return (node.text or "").strip() if node is not None else ""

        # Title
        title = _text(article, "ArticleTitle")

        # Authors
        authors: list[str] = []
        author_list = article.find("AuthorList") if article is not None else None
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = _text(author, "LastName")
                fore = _text(author, "ForeName")
                if last:
                    authors.append(f"{last}, {fore}" if fore else last)

        # Abstract – may have multiple AbstractText elements
        abstract_parts: list[str] = []
        abstract_el = article.find("Abstract") if article is not None else None
        if abstract_el is not None:
            for abs_text in abstract_el.findall("AbstractText"):
                text = abs_text.text or ""
                label = abs_text.get("Label")
                if label:
                    abstract_parts.append(f"{label}: {text.strip()}")
                else:
                    abstract_parts.append(text.strip())
        abstract = " ".join(abstract_parts)

        # Journal metadata
        journal_el = article.find("Journal") if article is not None else None
        journal = _text(journal_el, "Title")
        journal_issue = journal_el.find("JournalIssue") if journal_el is not None else None
        volume = _text(journal_issue, "Volume")
        issue = _text(journal_issue, "Issue")

        # Year – try PubDate/Year first, then MedlineDate
        year_str = _text(journal_issue, "PubDate/Year")
        year: int | None = None
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass

        # Pages
        pages = _text(article, "Pagination/MedlinePgn")

        # DOI
        doi = ""
        if article is not None:
            for eloc in article.findall("ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = (eloc.text or "").strip()
                    break

        # PMID
        pmid = _text(citation, "PMID")

        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "doi": doi or None,
            "pmid": pmid or None,
            "year": year,
            "journal": journal,
            "volume": volume or None,
            "issue": issue or None,
            "pages": pages or None,
        }
