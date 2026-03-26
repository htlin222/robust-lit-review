"""Journal quality assessment using Scimago + OpenAlex.

Two data sources:
1. Scimago CSV (optional): Pre-downloaded Q1-Q4 quartile data by ISSN
   Download from: https://www.scimagojr.com/journalrank.php?out=xls
   Place at: data/scimago.csv
2. OpenAlex API (always available): Free metrics, compute quartiles from h-index/citedness

Default filter: Q1 journals only (can be relaxed to Q1+Q2 via config).
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)


@dataclass
class JournalQuality:
    """Quality assessment for a journal."""

    issn: str
    name: str
    quartile: str  # "Q1", "Q2", "Q3", "Q4", "Unknown"
    sjr: float = 0.0
    h_index: int = 0
    impact_factor_approx: float = 0.0  # 2yr mean citedness from OpenAlex
    source: str = ""  # "scimago", "openalex", "scopus"


class ScimagoLookup:
    """ISSN → quartile lookup from Scimago CSV.

    The CSV should be downloaded from scimagojr.com and placed at data/scimago.csv.
    Columns used: Issn, Title, SJR Best Quartile, SJR, H index, Categories.
    """

    def __init__(self):
        self._data: dict[str, JournalQuality] = {}
        self._loaded = False

    def load(self, csv_path: Path | None = None) -> bool:
        """Load Scimago CSV data.

        Returns True if loaded successfully, False if file not found.
        """
        if csv_path is None:
            # Look in common locations
            candidates = [
                Path("data/scimago.csv"),
                Path("data/scimagojr.csv"),
                Path.home() / ".litreview" / "scimago.csv",
            ]
            for p in candidates:
                if p.exists():
                    csv_path = p
                    break

        if csv_path is None or not csv_path.exists():
            logger.info("Scimago CSV not found — will use OpenAlex for journal metrics")
            return False

        count = 0
        try:
            with open(csv_path, encoding="utf-8") as f:
                # Scimago CSV uses semicolon separator
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    issns = row.get("Issn", "").replace(" ", "")
                    if not issns:
                        continue
                    # Scimago stores multiple ISSNs comma-separated
                    for issn in issns.split(","):
                        issn = issn.strip()
                        if len(issn) == 8:
                            issn = f"{issn[:4]}-{issn[4:]}"
                        if issn:
                            self._data[issn] = JournalQuality(
                                issn=issn,
                                name=row.get("Title", ""),
                                quartile=row.get("SJR Best Quartile", "Unknown"),
                                sjr=_safe_float(row.get("SJR", "0")),
                                h_index=_safe_int(row.get("H index", "0")),
                                source="scimago",
                            )
                            count += 1
        except Exception as e:
            logger.warning(f"Failed to load Scimago CSV: {e}")
            return False

        self._loaded = True
        logger.info(f"Loaded {count} journals from Scimago CSV")
        return True

    def lookup(self, issn: str) -> JournalQuality | None:
        """Look up journal quality by ISSN."""
        if not self._loaded:
            return None
        # Normalize ISSN
        issn = issn.strip().upper()
        if len(issn) == 8 and "-" not in issn:
            issn = f"{issn[:4]}-{issn[4:]}"
        return self._data.get(issn)

    @property
    def is_loaded(self) -> bool:
        return self._loaded


async def compute_quartile_from_openalex(
    metrics: dict,
    all_metrics: list[dict] | None = None,
) -> str:
    """Compute approximate quartile from OpenAlex metrics.

    Uses h-index and impact_factor_approx (2yr mean citedness) to estimate quartile.
    If all_metrics is provided, computes percentile-based quartile.
    Otherwise uses absolute thresholds based on known distributions.
    """
    h = metrics.get("h_index", 0)
    if_approx = metrics.get("impact_factor_approx", 0.0)

    if all_metrics:
        # Percentile-based: rank this journal among all fetched journals
        all_if = sorted(m.get("impact_factor_approx", 0) for m in all_metrics)
        n = len(all_if)
        if n == 0:
            return "Unknown"
        rank = sum(1 for x in all_if if x <= if_approx) / n
        if rank >= 0.75:
            return "Q1"
        elif rank >= 0.50:
            return "Q2"
        elif rank >= 0.25:
            return "Q3"
        else:
            return "Q4"

    # Absolute thresholds based on h-index (stable, well-distributed)
    # Medical journal h-index distribution: Q1 >100, Q2 50-100, Q3 20-50, Q4 <20
    # 2yr_mean_citedness is a proportion (not IF), so use h-index as primary signal
    if h >= 100:
        return "Q1"
    elif h >= 50:
        return "Q2"
    elif h >= 20:
        return "Q3"
    elif h > 0:
        return "Q4"
    return "Unknown"


async def assess_journal_quality(
    articles: list[ArticleMetadata],
    email: str = "",
    scimago_csv: Path | None = None,
    min_quartile: str = "Q1",
) -> list[ArticleMetadata]:
    """Assess journal quality for all articles and filter by quartile.

    Strategy:
    1. Try Scimago CSV lookup (fastest, most accurate)
    2. Fall back to OpenAlex API for unknowns
    3. Fall back to existing CiteScore from Scopus for remaining

    Args:
        min_quartile: Minimum quartile to include. "Q1" = Q1 only,
                      "Q2" = Q1+Q2, "Q3" = Q1+Q2+Q3, "Q4" = all.
    """
    from litreview.clients.openalex import OpenAlexClient

    # Build quartile acceptance set
    quartile_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    max_q = quartile_order.get(min_quartile, 2)
    accepted = {q for q, v in quartile_order.items() if v <= max_q}

    # Step 1: Scimago lookup
    scimago = ScimagoLookup()
    scimago.load(scimago_csv)

    results: dict[str, str] = {}  # doi/title -> quartile
    unknown_issns: set[str] = set()

    for article in articles:
        issn = _extract_issn(article)
        if issn and scimago.is_loaded:
            quality = scimago.lookup(issn)
            if quality:
                article.journal_quartile = quality.quartile
                article.sjr = quality.sjr
                key = article.doi or article.title
                results[key] = quality.quartile
                continue

        if issn:
            unknown_issns.add(issn)

    # Step 2: OpenAlex for unknowns
    if unknown_issns:
        logger.info(f"Fetching metrics from OpenAlex for {len(unknown_issns)} journals")
        async with OpenAlexClient(email) as client:
            oa_metrics = await client.batch_journal_metrics(list(unknown_issns))

        all_metrics_list = list(oa_metrics.values())
        for article in articles:
            key = article.doi or article.title
            if key in results:
                continue
            issn = _extract_issn(article)
            if issn and issn in oa_metrics:
                metrics = oa_metrics[issn]
                quartile = await compute_quartile_from_openalex(metrics, all_metrics_list)
                article.journal_quartile = quartile
                article.impact_factor = metrics.get("impact_factor_approx", 0.0)
                results[key] = quartile

    # Step 3: Existing CiteScore fallback
    for article in articles:
        key = article.doi or article.title
        if key not in results:
            if article.citescore and article.citescore >= 10:
                article.journal_quartile = "Q1"
            elif article.citescore and article.citescore >= 4:
                article.journal_quartile = "Q2"
            elif article.citescore and article.citescore >= 1.5:
                article.journal_quartile = "Q3"
            elif article.citescore:
                article.journal_quartile = "Q4"
            else:
                article.journal_quartile = "Unknown"
            results[key] = article.journal_quartile or "Unknown"

    # Filter by quartile
    filtered = []
    for article in articles:
        q = article.journal_quartile or "Unknown"
        if q in accepted or q == "Unknown":
            # Include unknowns (can't confirm they're low quality)
            filtered.append(article)

    # Stats
    from collections import Counter
    q_dist = Counter(a.journal_quartile for a in articles)
    q_filtered = Counter(a.journal_quartile for a in filtered)
    logger.info(f"Journal quality: {dict(q_dist)}")
    logger.info(f"After {min_quartile} filter: {len(filtered)}/{len(articles)} ({dict(q_filtered)})")

    return filtered


def _extract_issn(article: ArticleMetadata) -> str:
    """Extract ISSN from article metadata."""
    return article.issn or ""


def _safe_float(s: str) -> float:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _safe_int(s: str) -> int:
    try:
        return int(s)
    except (ValueError, AttributeError):
        return 0
