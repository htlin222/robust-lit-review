"""Data models for the literature review pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DatabaseSource(str, Enum):
    SCOPUS = "scopus"
    PUBMED = "pubmed"
    EMBASE = "embase"


class ArticleMetadata(BaseModel):
    """Unified article metadata across all databases."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    doi: str | None = None
    pmid: str | None = None
    scopus_id: str | None = None
    year: int | None = None
    journal: str = ""
    issn: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    citation_count: int = 0
    source_db: DatabaseSource = DatabaseSource.SCOPUS

    # Journal quality metrics
    citescore: float | None = None
    sjr: float | None = None
    snip: float | None = None
    impact_factor: float | None = None
    journal_quartile: str | None = None  # Q1, Q2, Q3, Q4

    # Access info
    is_open_access: bool = False
    oa_url: str | None = None
    pdf_url: str | None = None

    # Validation
    doi_validated: bool = False
    url_validated: bool = False

    # AI-enhanced fields (P0: RAG, P1: screening)
    relevance_score: float | None = None
    subtopic_categories: list[str] = Field(default_factory=list)
    screening_status: str | None = None  # "include" | "exclude" | "uncertain"
    screening_reason: str | None = None

    @property
    def citation_key(self) -> str:
        """Generate a BibTeX citation key."""
        import re
        if self.authors:
            # Handle both "Last, First" and "Last First" and "Last F.M." formats
            raw = self.authors[0].split(",")[0].strip()
            # Take the first word-like token (the surname), ignoring initials like "M.R."
            parts = [p for p in raw.split() if len(p) > 2 or not p.replace(".", "").isupper()]
            first_author = parts[0] if parts else raw.split()[0]
            # Remove non-alphanumeric
            first_author = re.sub(r"[^a-zA-Z]", "", first_author)
        else:
            first_author = "Unknown"
        year = self.year or "nd"
        title_word = re.sub(r"[^a-zA-Z]", "", self.title.split()[0]) if self.title else "untitled"
        return f"{first_author}{year}{title_word}"

    @property
    def is_high_quality(self) -> bool:
        """Check if from a high-impact journal."""
        if self.citescore and self.citescore >= 3.0:
            return True
        if self.journal_quartile in ("Q1", "Q2"):
            return True
        if self.sjr and self.sjr >= 0.5:
            return True
        return False


class SearchQuery(BaseModel):
    """A structured search query for literature databases."""

    topic: str
    primary_terms: list[str] = Field(default_factory=list)
    secondary_terms: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    boolean_query: str = ""
    date_from: int | None = None
    date_to: int | None = None
    article_types: list[str] = Field(default_factory=lambda: ["article", "review"])


class ReviewStatistics(BaseModel):
    """Statistics about the literature review."""

    total_articles_found: int = 0
    articles_after_dedup: int = 0
    articles_after_quality_filter: int = 0
    articles_after_screening: int = 0
    articles_with_valid_doi: int = 0
    articles_included: int = 0
    articles_by_source: dict[str, int] = Field(default_factory=dict)
    articles_by_year: dict[int, int] = Field(default_factory=dict)
    articles_by_quartile: dict[str, int] = Field(default_factory=dict)
    journals_represented: int = 0
    avg_citescore: float = 0.0
    avg_citation_count: float = 0.0
    date_range: str = ""
    word_count: int = 0
    reference_count: int = 0
    search_queries_used: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class ReviewOutput(BaseModel):
    """Complete output of the literature review pipeline."""

    topic: str
    articles: list[ArticleMetadata] = Field(default_factory=list)
    statistics: ReviewStatistics = Field(default_factory=ReviewStatistics)
    bibtex: str = ""
    quarto_content: str = ""
    search_queries: list[SearchQuery] = Field(default_factory=list)
    gap_report: dict | None = None
