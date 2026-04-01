"""Agentic research gap explorer (AI-Scientist concept).

Performs automated landscape analysis before the main search to identify:
- Under-researched subtopics
- Conflicting findings across studies
- Emerging trends
- Methodological gaps

Runs as optional Stage 0 in the pipeline (--explore-gaps flag).
Feeds refined search queries into build_search_queries() for better coverage.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from litreview.models import ArticleMetadata, SearchQuery

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class ResearchGap:
    """A single identified research gap."""

    gap_type: str  # "under_researched" | "conflicting" | "emerging" | "methodological"
    description: str
    evidence: str  # What evidence supports this gap
    suggested_queries: list[str] = field(default_factory=list)
    priority: str = "medium"  # "high" | "medium" | "low"


@dataclass
class GapExplorerReport:
    """Complete report from gap exploration."""

    topic: str
    landscape_summary: str  # Overview of current research landscape
    total_preliminary_articles: int = 0
    gaps: list[ResearchGap] = field(default_factory=list)
    refined_queries: list[SearchQuery] = field(default_factory=list)
    research_questions: list[str] = field(default_factory=list)
    temporal_trends: dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_appendix(self) -> str:
        """Format as Quarto appendix section for inclusion in the review."""
        lines = [
            "# Appendix: Research Gap Analysis",
            "",
            "## Landscape Summary",
            "",
            self.landscape_summary,
            "",
            "## Identified Gaps",
            "",
        ]

        for i, gap in enumerate(self.gaps, 1):
            priority_icon = {"high": "!!!", "medium": "!!", "low": "!"}.get(gap.priority, "!")
            lines.extend([
                f"### Gap {i}: {gap.description} [{priority_icon}]",
                f"",
                f"**Type:** {gap.gap_type}",
                f"",
                f"**Evidence:** {gap.evidence}",
                f"",
            ])
            if gap.suggested_queries:
                lines.append("**Suggested search queries:**")
                for q in gap.suggested_queries:
                    lines.append(f"- `{q}`")
                lines.append("")

        if self.research_questions:
            lines.extend([
                "## Suggested Research Questions",
                "",
            ])
            for i, q in enumerate(self.research_questions, 1):
                lines.append(f"{i}. {q}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "topic": self.topic,
            "landscape_summary": self.landscape_summary,
            "total_preliminary_articles": self.total_preliminary_articles,
            "gaps": [
                {
                    "gap_type": g.gap_type,
                    "description": g.description,
                    "evidence": g.evidence,
                    "suggested_queries": g.suggested_queries,
                    "priority": g.priority,
                }
                for g in self.gaps
            ],
            "research_questions": self.research_questions,
            "temporal_trends": self.temporal_trends,
            "generated_at": self.generated_at,
        }


async def _call_claude(prompt: str, system: str, max_tokens: int = 4000) -> str:
    """Call Claude API for gap analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for gap exploration")

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


async def _analyze_landscape(
    topic: str,
    articles: list[ArticleMetadata],
) -> dict:
    """Phase 2: Analyze research landscape from preliminary articles."""
    # Build context from top articles
    article_summaries = []
    for a in articles[:50]:  # Top 50 by citation count
        summary = (
            f"- {a.title} ({a.journal}, {a.year}, {a.citation_count} cites)\n"
            f"  Abstract: {a.abstract[:300]}..." if a.abstract else f"- {a.title} ({a.journal}, {a.year})"
        )
        article_summaries.append(summary)

    # Year distribution
    year_dist = {}
    for a in articles:
        if a.year:
            year_dist[a.year] = year_dist.get(a.year, 0) + 1

    system = (
        "You are a research methodology expert specializing in systematic reviews. "
        "Analyze the research landscape and identify gaps, trends, and opportunities."
    )

    prompt = f"""Analyze the research landscape for a systematic review on: "{topic}"

Preliminary search found {len(articles)} articles. Here are the top 50 by citations:

{chr(10).join(article_summaries)}

Year distribution: {json.dumps(dict(sorted(year_dist.items())), indent=2)}

Analyze this landscape and return ONLY valid JSON with this structure:
{{
    "landscape_summary": "2-3 paragraph overview of the current research state",
    "gaps": [
        {{
            "gap_type": "under_researched|conflicting|emerging|methodological",
            "description": "concise gap description",
            "evidence": "what evidence supports this is a gap",
            "suggested_queries": ["boolean query 1", "boolean query 2"],
            "priority": "high|medium|low"
        }}
    ],
    "research_questions": [
        "Suggested review question 1",
        "Suggested review question 2"
    ],
    "temporal_trends": {{
        "trend_name": "description of temporal pattern"
    }},
    "subtopic_coverage": {{
        "well_covered": ["subtopic1", "subtopic2"],
        "under_covered": ["subtopic3", "subtopic4"]
    }}
}}

Identify 3-7 gaps. Focus on clinically important gaps, not trivial ones."""

    text = await _call_claude(prompt, system, max_tokens=4000)

    # Parse JSON from response
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    if text.startswith("json"):
        text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse landscape analysis JSON: {e}")
        return {
            "landscape_summary": f"Analysis of {len(articles)} articles on {topic}.",
            "gaps": [],
            "research_questions": [],
            "temporal_trends": {},
        }


def _build_refined_queries(
    topic: str,
    original_terms: list[str] | None,
    analysis: dict,
) -> list[SearchQuery]:
    """Phase 3: Generate refined search queries from gap analysis."""
    queries = []

    for gap in analysis.get("gaps", []):
        for suggested_query in gap.get("suggested_queries", []):
            queries.append(
                SearchQuery(
                    topic=topic,
                    primary_terms=original_terms or [topic],
                    secondary_terms=[gap["description"][:50]],
                    boolean_query=suggested_query,
                )
            )

    # Also create queries for under-covered subtopics
    under_covered = analysis.get("subtopic_coverage", {}).get("under_covered", [])
    for subtopic in under_covered:
        base_terms = original_terms or [topic]
        query = " AND ".join(f'"{t}"' for t in base_terms) + f' AND "{subtopic}"'
        queries.append(
            SearchQuery(
                topic=topic,
                primary_terms=base_terms,
                secondary_terms=[subtopic],
                boolean_query=query,
            )
        )

    logger.info(f"Generated {len(queries)} refined queries from gap analysis")
    return queries


async def explore_gaps(
    topic: str,
    search_terms: list[str] | None,
    pipeline,
) -> GapExplorerReport:
    """Full gap exploration pipeline.

    Phase 1: Broad preliminary search (reuses pipeline's search_all_databases)
    Phase 2: LLM landscape analysis
    Phase 3: Generate refined queries
    Phase 4: Suggest research questions

    Args:
        topic: Research topic.
        search_terms: User-provided search terms.
        pipeline: LitReviewPipeline instance (for database access).

    Returns:
        GapExplorerReport with gaps, refined queries, and research questions.
    """
    logger.info(f"Starting gap exploration for: {topic}")

    # Phase 1: Preliminary broad search
    logger.info("Phase 1: Preliminary broad search...")
    preliminary_queries = pipeline.build_search_queries(topic, search_terms)
    try:
        preliminary_articles = await pipeline.search_all_databases(preliminary_queries)
    except Exception as e:
        logger.warning(f"Preliminary search failed: {e}")
        preliminary_articles = []

    # Sort by citations for analysis
    preliminary_articles.sort(key=lambda a: a.citation_count or 0, reverse=True)

    if not preliminary_articles:
        logger.warning("No preliminary articles found, returning empty gap report")
        return GapExplorerReport(
            topic=topic,
            landscape_summary="No articles found in preliminary search.",
        )

    # Phase 2: Analyze landscape
    logger.info(f"Phase 2: Analyzing landscape ({len(preliminary_articles)} articles)...")
    analysis = await _analyze_landscape(topic, preliminary_articles)

    # Phase 3: Generate refined queries
    logger.info("Phase 3: Generating refined queries...")
    refined_queries = _build_refined_queries(topic, search_terms, analysis)

    # Phase 4: Build report
    gaps = [
        ResearchGap(
            gap_type=g.get("gap_type", "under_researched"),
            description=g.get("description", ""),
            evidence=g.get("evidence", ""),
            suggested_queries=g.get("suggested_queries", []),
            priority=g.get("priority", "medium"),
        )
        for g in analysis.get("gaps", [])
    ]

    report = GapExplorerReport(
        topic=topic,
        landscape_summary=analysis.get("landscape_summary", ""),
        total_preliminary_articles=len(preliminary_articles),
        gaps=gaps,
        refined_queries=refined_queries,
        research_questions=analysis.get("research_questions", []),
        temporal_trends=analysis.get("temporal_trends", {}),
    )

    logger.info(
        f"Gap exploration complete: {len(gaps)} gaps identified, "
        f"{len(refined_queries)} refined queries, "
        f"{len(report.research_questions)} research questions"
    )

    return report


def merge_search_terms(
    original_terms: list[str] | None,
    gap_report: GapExplorerReport,
    max_additional: int = 5,
) -> list[str]:
    """Merge original search terms with gap-derived terms.

    Adds high-priority gap terms to the search term list,
    limited to max_additional to avoid query explosion.
    """
    terms = list(original_terms or [])
    added = 0

    # Add terms from high-priority gaps first
    for gap in sorted(gap_report.gaps, key=lambda g: {"high": 0, "medium": 1, "low": 2}.get(g.priority, 2)):
        if added >= max_additional:
            break
        for query in gap.suggested_queries:
            if added >= max_additional:
                break
            # Extract key terms from boolean query
            # Remove operators and quotes
            clean = query.replace('"', "").replace("(", "").replace(")", "")
            for op in ["AND", "OR", "NOT"]:
                clean = clean.replace(op, " ")
            key_terms = [t.strip() for t in clean.split() if len(t.strip()) > 3]
            for term in key_terms[:2]:  # At most 2 terms per gap
                if term.lower() not in [t.lower() for t in terms]:
                    terms.append(term)
                    added += 1

    logger.info(f"Merged terms: {len(original_terms or [])} original + {added} from gaps = {len(terms)} total")
    return terms
