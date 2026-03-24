"""Statistics computation for literature review."""

from __future__ import annotations

import re
from collections import Counter

from litreview.models import ArticleMetadata, ReviewStatistics


def compute_statistics(
    articles: list[ArticleMetadata],
    quarto_content: str = "",
    bibtex_content: str = "",
    search_queries: list[str] | None = None,
) -> ReviewStatistics:
    """Compute comprehensive statistics for the literature review."""
    stats = ReviewStatistics()

    if not articles:
        return stats

    stats.articles_included = len(articles)

    # By source
    source_counts = Counter(a.source_db.value for a in articles)
    stats.articles_by_source = dict(source_counts)

    # By year
    year_counts = Counter(a.year for a in articles if a.year)
    stats.articles_by_year = dict(sorted(year_counts.items()))

    # By quartile
    q_counts = Counter(a.journal_quartile for a in articles if a.journal_quartile)
    stats.articles_by_quartile = dict(q_counts)

    # Journals
    journals = set(a.journal for a in articles if a.journal)
    stats.journals_represented = len(journals)

    # CiteScore
    citescores = [a.citescore for a in articles if a.citescore]
    stats.avg_citescore = sum(citescores) / len(citescores) if citescores else 0.0

    # Citations
    citations = [a.citation_count for a in articles]
    stats.avg_citation_count = sum(citations) / len(citations) if citations else 0.0

    # DOI validation
    stats.articles_with_valid_doi = sum(1 for a in articles if a.doi_validated)

    # Date range
    years = [a.year for a in articles if a.year]
    if years:
        stats.date_range = f"{min(years)}-{max(years)}"

    # Word count from Quarto content
    if quarto_content:
        # Strip YAML frontmatter
        content = re.sub(r"^---.*?---", "", quarto_content, flags=re.DOTALL)
        # Strip code blocks
        content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        # Strip citations
        content = re.sub(r"@\w+", "", content)
        words = content.split()
        stats.word_count = len(words)

    # Reference count
    if bibtex_content:
        stats.reference_count = len(re.findall(r"@\w+\{", bibtex_content))

    if search_queries:
        stats.search_queries_used = search_queries

    return stats


def format_statistics_table(stats: ReviewStatistics) -> str:
    """Format statistics as a markdown table for inclusion in the review."""
    lines = [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Articles included | {stats.articles_included} |",
        f"| Unique journals | {stats.journals_represented} |",
        f"| Date range | {stats.date_range} |",
        f"| Avg. CiteScore | {stats.avg_citescore:.2f} |",
        f"| Avg. citations | {stats.avg_citation_count:.1f} |",
        f"| DOIs validated | {stats.articles_with_valid_doi} |",
        f"| Word count | {stats.word_count:,} |",
        f"| References | {stats.reference_count} |",
    ]

    if stats.articles_by_quartile:
        for q, count in sorted(stats.articles_by_quartile.items()):
            lines.append(f"| {q} journals | {count} |")

    if stats.articles_by_source:
        for src, count in stats.articles_by_source.items():
            lines.append(f"| From {src} | {count} |")

    return "\n".join(lines)


def format_prisma_flow(
    total_found: int,
    after_dedup: int,
    after_quality: int,
    after_validation: int,
    included: int,
) -> str:
    """Generate a text-based PRISMA flow diagram."""
    return f"""```
PRISMA Flow Diagram
===================

Records identified through      Records identified through
database searching               other sources
(n = {total_found})                         (n = 0)
         |                                |
         +----------------+---------------+
                          |
              Records after duplicates
                    removed
                  (n = {after_dedup})
                          |
              Records screened by
              journal quality (IF/CiteScore)
                  (n = {after_quality})
                          |
              Records with validated DOI
                  (n = {after_validation})
                          |
              Studies included in
              literature review
                  (n = {included})
```"""
