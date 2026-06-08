"""Pure filtering helpers for the claim-appraisal pipeline.

These are deterministic, side-effect-free functions so they can be unit-tested
without API access. They are the authoritative source for PRISMA flow counts.
"""

from __future__ import annotations

from litreview.models import ArticleMetadata


def filter_by_year(
    articles: list[ArticleMetadata],
    min_year: int = 2016,
    max_year: int | None = None,
) -> tuple[list[ArticleMetadata], list[ArticleMetadata]]:
    """Split *articles* into ``(kept, dropped)`` by publication year.

    Articles with no resolvable year are dropped under the strict regime: we
    cannot confirm they are >= ``min_year``, and a robust appraisal must not
    silently admit undated records. Callers should log the dropped-no-year
    count so coverage loss is visible.

    Args:
        articles: candidate articles.
        min_year: earliest publication year to keep (inclusive).
        max_year: latest publication year to keep (inclusive); ``None`` = no cap.

    Returns:
        A ``(kept, dropped)`` tuple.
    """
    kept: list[ArticleMetadata] = []
    dropped: list[ArticleMetadata] = []
    for a in articles:
        if a.year is None:
            dropped.append(a)
        elif a.year < min_year:
            dropped.append(a)
        elif max_year is not None and a.year > max_year:
            dropped.append(a)
        else:
            kept.append(a)
    return kept, dropped
