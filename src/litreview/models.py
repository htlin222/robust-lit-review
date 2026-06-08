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
    crossref_verified: bool = False  # confirmed to exist in CrossRef (anti-hallucination gate)
    crossref_title_match: float = 0.0  # 0..1 similarity of CrossRef title to our title

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


# ---------------------------------------------------------------------------
# Claim appraisal models (claim -> PICO -> SR -> GRADE/verdict)
#
# These are additive. The topic-centric `review` path keeps using
# ArticleMetadata / ReviewOutput; the claim-centric `appraise` path uses the
# models below. A `ClaimAppraisal` is the single upstream artifact that drives
# both the Quarto (print) and the Jinja2 (web) renderers.
# ---------------------------------------------------------------------------


class PICOQuestion(BaseModel):
    """One PICO sub-question decomposed from a claim."""

    pico_id: str = ""
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    outcome: str = ""
    outcome_domain: str = ""  # snake_case, e.g. "glycemic_control"
    question_text: str = ""  # rendered NL question for display + OE cross-check
    rationale: str = ""
    primary_terms: list[str] = Field(default_factory=list)
    secondary_terms: list[str] = Field(default_factory=list)
    mesh_terms: list[str] = Field(default_factory=list)
    priority: int = 1


class PicoPrismaFlow(BaseModel):
    """PRISMA flow counts for a single PICO's search/screen pipeline."""

    total_found: int = 0
    after_dedup: int = 0
    after_year_filter: int = 0  # >= min_year (default 2016)
    after_quality_filter: int = 0  # Q1-only
    after_validation: int = 0  # DOI resolves via doi.org
    after_crossref: int = 0  # confirmed to exist in CrossRef
    screened: int = 0
    included: int = 0
    excluded_by_year: int = 0
    excluded_by_quality: int = 0
    excluded_by_crossref: int = 0  # dropped: not found in CrossRef (possible hallucination)
    excluded_by_screen: int = 0
    excluded_reasons: dict[str, int] = Field(default_factory=dict)


class GradeDomain(BaseModel):
    """One GRADE certainty domain (downgrade) or upgrade assessment."""

    name: str  # risk_of_bias | inconsistency | indirectness | imprecision | publication_bias
    rating: str = "not_serious"  # not_serious | serious | very_serious
    downgrade: int = 0  # 0, -1, -2 (or positive for upgrades)
    justification: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class GradeAssessment(BaseModel):
    """GRADE certainty-of-evidence assessment for a PICO."""

    pico_id: str = ""
    starting_level: str = "high"  # "high" (RCT-dominant) | "low" (observational)
    domains: list[GradeDomain] = Field(default_factory=list)  # 5 downgrade domains
    upgrades: list[GradeDomain] = Field(default_factory=list)  # observational upgrades
    final_certainty: str = "very_low"  # high | moderate | low | very_low
    effect_direction: str = "no_effect"  # beneficial | no_effect | harmful | mixed
    n_studies: int = 0
    n_rct: int = 0
    summary: str = ""


class OpenEvidenceCheck(BaseModel):
    """Cross-check of our verdict against OpenEvidence + PubMed."""

    pico_id: str = ""
    question_asked: str = ""
    oe_article_id: str | None = None
    oe_verdict_text: str = ""
    oe_citations: list[str] = Field(default_factory=list)
    agreement: str = "no_data"  # agree | partial | disagree | no_data
    discrepancy_notes: str = ""
    pubmed_corroboration: str = ""


class Verdict(BaseModel):
    """Final verdict for a PICO question."""

    pico_id: str = ""
    verdict: str = "uncertain"  # supported | uncertain | refuted
    confidence: str = "very_low"  # mirrors GRADE final_certainty
    effect_direction: str = "no_effect"  # beneficial | no_effect | harmful | mixed
    plain_language_en: str = ""  # clinician-facing summary
    plain_language_lay_en: str = ""  # lay-audience summary
    crosscheck: OpenEvidenceCheck | None = None
    grade: GradeAssessment | None = None
    dissent: str = ""  # surfaced when OpenEvidence disagrees with our verdict


class PicoResult(BaseModel):
    """Complete result bundle for a single PICO sub-question."""

    question: PICOQuestion
    search_queries: list[SearchQuery] = Field(default_factory=list)
    prisma: PicoPrismaFlow = Field(default_factory=PicoPrismaFlow)
    included_studies: list[ArticleMetadata] = Field(default_factory=list)
    grade: GradeAssessment | None = None
    verdict: Verdict | None = None
    audit_trail: list[dict] = Field(default_factory=list)


class ClaimAppraisal(BaseModel):
    """Top-level claim appraisal output — the web/print render contract."""

    claim: str
    claim_id: str = ""
    decomposed_at: datetime = Field(default_factory=datetime.now)
    pico_results: list[PicoResult] = Field(default_factory=list)
    # claim-level rollup synthesized across PICOs
    overall_verdict: str = "uncertain"  # supported | uncertain | refuted
    overall_certainty: str = "very_low"
    overall_summary_en: str = ""
    overall_summary_lay_en: str = ""
    # bilingual fields populated by a downstream translation pass (left empty by backend)
    overall_summary_zh: str = ""
    overall_summary_lay_zh: str = ""
    filters_applied: dict = Field(
        default_factory=lambda: {"min_year": 2016, "min_quartile": "Q1"}
    )
    generated_at: datetime = Field(default_factory=datetime.now)
