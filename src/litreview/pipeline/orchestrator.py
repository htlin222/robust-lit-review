"""Main pipeline orchestrator for the literature review."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from litreview.clients.scopus import ScopusClient
from litreview.clients.pubmed import PubMedClient
from litreview.clients.embase import EmbaseClient
from litreview.clients.unpaywall import UnpaywallClient
from litreview.clients.zotero import ZoteroClient
from litreview.config import Config, get_config
from litreview.models import ArticleMetadata, ReviewOutput, SearchQuery
from litreview.utils.bibtex import generate_bibtex
from litreview.utils.doi_validator import batch_validate_dois
from litreview.utils.statistics import compute_statistics, format_statistics_table, format_prisma_flow

logger = logging.getLogger(__name__)


class LitReviewPipeline:
    """Orchestrates the entire literature review pipeline.

    Pipeline stages:
    1. Generate search queries from topic
    2. Search across databases (Scopus, PubMed, Embase) in parallel
    3. Deduplicate results by DOI
    4. Filter by journal quality (CiteScore, SJR, quartile)
    5. Validate DOIs via doi.org and Unpaywall
    6. Enrich with OA links
    7. Export to Zotero
    8. Generate BibTeX
    9. Compute statistics
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._scopus: ScopusClient | None = None
        self._pubmed: PubMedClient | None = None
        self._embase: EmbaseClient | None = None
        self._unpaywall: UnpaywallClient | None = None
        self._zotero: ZoteroClient | None = None

    async def __aenter__(self):
        keys = self.config.validate_keys()
        if keys["scopus"]:
            self._scopus = ScopusClient(self.config.scopus_api_key)
        if keys["pubmed"]:
            self._pubmed = PubMedClient(self.config.pubmed_api_key)
        if keys["embase"]:
            self._embase = EmbaseClient(self.config.embase_api_key)
        if keys["unpaywall"]:
            self._unpaywall = UnpaywallClient(self.config.unpaywall_email)
        if keys["zotero"]:
            self._zotero = ZoteroClient(
                api_key=self.config.zotero_api_key,
                library_type=self.config.zotero_library_type,
                library_id=self.config.zotero_library_id,
                collection_key=self.config.zotero_collection_key,
            )
        return self

    async def __aexit__(self, *args):
        clients = [self._scopus, self._pubmed, self._embase, self._unpaywall, self._zotero]
        for client in clients:
            if client:
                await client.close()

    def build_search_queries(self, topic: str, terms: list[str] | None = None) -> list[SearchQuery]:
        """Build structured search queries for a topic."""
        primary = terms or [topic]

        # Main comprehensive query
        main_query = SearchQuery(
            topic=topic,
            primary_terms=primary,
            boolean_query=" OR ".join(f'"{t}"' for t in primary),
        )

        # Narrowed query with common academic modifiers
        review_query = SearchQuery(
            topic=topic,
            primary_terms=primary,
            secondary_terms=["systematic review", "meta-analysis", "literature review"],
            boolean_query=f'({main_query.boolean_query}) AND ("systematic review" OR "meta-analysis" OR "review")',
        )

        return [main_query, review_query]

    async def search_all_databases(self, queries: list[SearchQuery]) -> list[ArticleMetadata]:
        """Search all configured databases in parallel."""
        all_articles: list[ArticleMetadata] = []
        tasks = []

        primary_query = queries[0].boolean_query if queries else ""

        if self._scopus and primary_query:
            logger.info("Searching Scopus...")
            tasks.append(self._scopus.search_and_enrich(primary_query, self.config.max_results_per_db))

        if self._pubmed and primary_query:
            logger.info("Searching PubMed...")
            tasks.append(self._pubmed.search_and_fetch(primary_query, self.config.max_results_per_db))

        if self._embase and primary_query:
            logger.info("Searching Embase...")
            tasks.append(self._embase.search_and_enrich(primary_query, self.config.max_results_per_db))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_articles.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Database search failed: {result}")

        logger.info(f"Total articles found across all databases: {len(all_articles)}")
        return all_articles

    def deduplicate(self, articles: list[ArticleMetadata]) -> list[ArticleMetadata]:
        """Deduplicate articles by DOI, keeping the one with most metadata."""
        seen_dois: dict[str, ArticleMetadata] = {}
        no_doi: list[ArticleMetadata] = []

        for article in articles:
            if article.doi:
                doi_lower = article.doi.lower().strip()
                if doi_lower in seen_dois:
                    existing = seen_dois[doi_lower]
                    # Keep the one with more metadata
                    if len(article.abstract) > len(existing.abstract):
                        seen_dois[doi_lower] = article
                else:
                    seen_dois[doi_lower] = article
            else:
                # Deduplicate by title similarity for articles without DOI
                title_lower = article.title.lower().strip()
                is_dup = any(
                    a.title.lower().strip() == title_lower for a in list(seen_dois.values()) + no_doi
                )
                if not is_dup:
                    no_doi.append(article)

        deduped = list(seen_dois.values()) + no_doi
        logger.info(f"After deduplication: {len(deduped)} articles (removed {len(articles) - len(deduped)} duplicates)")
        return deduped

    def filter_by_quality(self, articles: list[ArticleMetadata]) -> list[ArticleMetadata]:
        """Filter articles to only include high-impact journal publications."""
        filtered = []
        for article in articles:
            # Articles with known high quality metrics
            if article.citescore and article.citescore >= self.config.min_citescore:
                filtered.append(article)
            elif article.journal_quartile in ("Q1", "Q2"):
                filtered.append(article)
            elif article.sjr and article.sjr >= self.config.min_sjr:
                filtered.append(article)
            elif not article.citescore and not article.journal_quartile and not article.sjr:
                # Include articles without metrics (from PubMed etc.) - they'll be validated later
                filtered.append(article)

        logger.info(f"After quality filter: {len(filtered)} articles (removed {len(articles) - len(filtered)})")
        return filtered

    async def validate_and_enrich(self, articles: list[ArticleMetadata]) -> list[ArticleMetadata]:
        """Validate DOIs and enrich with OA information."""
        if not self._unpaywall:
            logger.warning("Unpaywall not configured, skipping DOI validation")
            return articles

        validated = await self._unpaywall.batch_validate(articles)
        valid_count = sum(1 for a in validated if a.doi_validated)
        logger.info(f"DOI validation: {valid_count}/{len(validated)} valid")
        return validated

    async def export_to_zotero(self, articles: list[ArticleMetadata], topic: str) -> str | None:
        """Export articles to a Zotero collection."""
        if not self._zotero:
            logger.warning("Zotero not configured, skipping export")
            return None

        collection_name = f"LitReview: {topic[:50]}"
        try:
            key = await self._zotero.export_to_collection(articles, collection_name)
            logger.info(f"Exported {len(articles)} articles to Zotero collection: {key}")
            return key
        except Exception as e:
            logger.warning(f"Zotero export failed: {e}")
            return None

    async def run(
        self,
        topic: str,
        search_terms: list[str] | None = None,
    ) -> ReviewOutput:
        """Execute the complete literature review pipeline."""
        logger.info(f"Starting literature review pipeline for: {topic}")
        output = ReviewOutput(topic=topic)

        # Stage 1: Build search queries
        queries = self.build_search_queries(topic, search_terms)
        output.search_queries = queries
        logger.info(f"Generated {len(queries)} search queries")

        # Stage 2: Search all databases in parallel
        all_articles = await self.search_all_databases(queries)
        total_found = len(all_articles)

        # Stage 3: Deduplicate
        deduped = self.deduplicate(all_articles)
        after_dedup = len(deduped)

        # Stage 4: Filter by journal quality
        filtered = self.filter_by_quality(deduped)
        after_quality = len(filtered)

        # Stage 5: Validate DOIs and enrich
        validated = await self.validate_and_enrich(filtered)
        after_validation = len([a for a in validated if a.doi_validated or not a.doi])

        # Stage 6: Select top articles (by citation count, then CiteScore)
        validated.sort(key=lambda a: (a.citation_count or 0, a.citescore or 0), reverse=True)
        selected = validated[: self.config.target_articles]
        output.articles = selected

        # Stage 7: Export to Zotero
        await self.export_to_zotero(selected, topic)

        # Stage 8: Generate BibTeX
        output.bibtex = generate_bibtex(selected)

        # Stage 9: Compute statistics
        output.statistics = compute_statistics(
            articles=selected,
            bibtex_content=output.bibtex,
            search_queries=[q.boolean_query for q in queries],
        )
        output.statistics.total_articles_found = total_found
        output.statistics.articles_after_dedup = after_dedup
        output.statistics.articles_after_quality_filter = after_quality
        output.statistics.articles_with_valid_doi = after_validation

        # Generate PRISMA flow
        prisma = format_prisma_flow(
            total_found=total_found,
            after_dedup=after_dedup,
            after_quality=after_quality,
            after_validation=after_validation,
            included=len(selected),
        )

        logger.info(f"Pipeline complete: {len(selected)} articles selected")
        logger.info(f"Statistics:\n{format_statistics_table(output.statistics)}")

        return output


async def run_pipeline(
    topic: str,
    search_terms: list[str] | None = None,
    config: Config | None = None,
) -> ReviewOutput:
    """Convenience function to run the full pipeline."""
    async with LitReviewPipeline(config) as pipeline:
        return await pipeline.run(topic, search_terms)
