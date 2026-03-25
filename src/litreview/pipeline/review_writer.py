"""AI-powered academic review article writer.

Uses Claude to synthesize abstracts and metadata into a publication-ready
narrative literature review with proper academic prose, thematic analysis,
critical discussion, and scholarly synthesis.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx

from litreview.models import ArticleMetadata, ReviewOutput, ReviewStatistics
from litreview.utils.statistics import format_statistics_table, format_prisma_flow

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _get_api_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Required for AI-powered review writing. "
            "Set it in .env or export it in your shell."
        )
    return key


def _build_article_context(articles: list[ArticleMetadata]) -> str:
    """Build a structured context string from articles for the AI prompt."""
    entries = []
    for i, a in enumerate(articles, 1):
        entry = (
            f"[{i}] @{a.citation_key}\n"
            f"  Title: {a.title}\n"
            f"  Authors: {', '.join(a.authors[:3])}{'...' if len(a.authors) > 3 else ''}\n"
            f"  Journal: {a.journal} ({a.year})\n"
            f"  Citations: {a.citation_count}\n"
            f"  DOI: {a.doi}\n"
        )
        if a.abstract:
            # Truncate long abstracts
            abstract = a.abstract[:500] + "..." if len(a.abstract) > 500 else a.abstract
            entry += f"  Abstract: {abstract}\n"
        entries.append(entry)
    return "\n".join(entries)


async def _call_claude(prompt: str, system: str, max_tokens: int = 8000) -> str:
    """Call Claude API for text generation."""
    api_key = _get_api_key()
    async with httpx.AsyncClient(timeout=120) as client:
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
        data = resp.json()
        return data["content"][0]["text"]


SYSTEM_PROMPT = """You are a world-class academic medical writer producing a systematic literature review for publication in a high-impact peer-reviewed journal.

Your writing must:
- Use formal academic English with precise medical/scientific terminology
- Synthesize findings across studies, NOT just list them one by one
- Compare and contrast methodologies, findings, and conclusions
- Identify patterns, trends, gaps, and contradictions in the literature
- Use proper Pandoc/Quarto citation syntax: [@citationKey] for parenthetical, @citationKey for narrative
- Follow PRISMA guidelines for systematic review reporting
- Include critical analysis, not just description
- Group related studies thematically, not chronologically
- Write flowing paragraphs, not bullet points
- Target 5,000-8,000 words for the full review body
- Every claim must be supported by at least one citation"""


async def write_introduction(topic: str, articles: list[ArticleMetadata], stats: ReviewStatistics) -> str:
    """Generate a comprehensive introduction section."""
    context = _build_article_context(articles[:20])  # Use top cited for intro context

    prompt = f"""Write the Introduction section for a systematic literature review on: "{topic}"

Available articles for citation (use these citation keys with [@key] syntax):
{context}

Statistics:
- {stats.articles_included} articles included from {stats.journals_represented} journals
- Date range: {stats.date_range}
- Databases searched: Scopus, PubMed, Embase

The introduction must include:
1. Background and clinical significance of the topic (2-3 paragraphs)
2. Current state of knowledge and why a review is needed (1-2 paragraphs)
3. Definition of key terms and concepts (1 paragraph)
4. Specific objectives of this review (numbered list)

Use [@citationKey] for parenthetical citations and @citationKey for narrative citations.
Start with "# Introduction" as the heading. Write ~1,000-1,500 words."""

    return await _call_claude(prompt, SYSTEM_PROMPT)


async def write_methods(topic: str, stats: ReviewStatistics) -> str:
    """Generate the methods section."""
    prisma = format_prisma_flow(
        total_found=stats.total_articles_found,
        after_dedup=stats.articles_after_dedup,
        after_quality=stats.articles_after_quality_filter,
        after_validation=stats.articles_with_valid_doi,
        included=stats.articles_included,
    )

    prompt = f"""Write the Methods section for a systematic literature review on: "{topic}"

Search details:
- Databases: Scopus (Elsevier), PubMed (NCBI), Embase (Elsevier)
- Search queries: ("hemophagocytic lymphohistiocytosis" OR "hemophagocytic syndrome" OR "macrophage activation syndrome") AND (adult OR adults)
- Date range: 2016-2026 (10-year coverage)
- Total records identified: {stats.total_articles_found}
- After deduplication: {stats.articles_after_dedup}
- After quality screening: {stats.articles_after_quality_filter}
- After DOI validation: {stats.articles_with_valid_doi}
- Final included: {stats.articles_included}

Quality metrics used:
- CiteScore >= 3.0 (Scopus)
- SJR quartile Q1/Q2
- DOI validation via doi.org handle API
- Open access enrichment via Unpaywall

PRISMA flow:
{prisma}

The methods section must include:
1. Search strategy (databases, dates, terms)
2. Inclusion and exclusion criteria
3. Study selection process (PRISMA flow)
4. Data extraction procedure
5. Quality assessment approach

Start with "# Methods" as the heading. Write ~800-1,200 words.
Include the PRISMA flow diagram as a code block."""

    return await _call_claude(prompt, SYSTEM_PROMPT)


async def write_results(topic: str, articles: list[ArticleMetadata], stats: ReviewStatistics) -> str:
    """Generate the results section with thematic synthesis."""
    context = _build_article_context(articles)
    stats_table = format_statistics_table(stats)

    prompt = f"""Write the Results section for a systematic literature review on: "{topic}"

All {len(articles)} included articles (USE THESE CITATION KEYS with [@key] syntax):
{context}

Statistics:
{stats_table}

Articles by year: {json.dumps(stats.articles_by_year, indent=2) if stats.articles_by_year else 'See articles above'}

The Results section must:
1. Start with an overview paragraph (search yield, selection process summary)
2. Present summary statistics in a markdown table
3. Group articles into 3-5 THEMATIC CATEGORIES based on content analysis of titles and abstracts
4. For each theme:
   - Write 2-4 paragraphs synthesizing the findings
   - Compare methodologies across studies
   - Highlight key quantitative findings
   - Note areas of agreement and disagreement
   - Cite EVERY article using [@citationKey] syntax
5. Identify temporal trends in the literature

CRITICAL: You MUST cite every single article at least once. Use [@key] syntax.
CRITICAL: Synthesize across studies — do NOT write one paragraph per article.

Start with "# Results" as the heading. Write ~2,000-3,000 words."""

    return await _call_claude(prompt, SYSTEM_PROMPT, max_tokens=12000)


async def write_discussion(topic: str, articles: list[ArticleMetadata], stats: ReviewStatistics) -> str:
    """Generate the discussion section."""
    # Get top cited articles for emphasis
    top_cited = sorted(articles, key=lambda a: a.citation_count, reverse=True)[:15]
    context = _build_article_context(top_cited)

    prompt = f"""Write the Discussion section for a systematic literature review on: "{topic}"

Key articles for discussion (most cited, use [@key] syntax):
{context}

Review statistics:
- {stats.articles_included} articles from {stats.journals_represented} journals
- Date range: {stats.date_range}
- Average citations per article: {stats.avg_citation_count:.1f}
- Databases: Scopus, PubMed, Embase

The Discussion section must include:
1. Summary of principal findings (1-2 paragraphs)
2. Comparison with previous reviews and guidelines (1-2 paragraphs)
3. Clinical implications — what do these findings mean for practice? (2-3 paragraphs)
4. Research gaps and unanswered questions (1-2 paragraphs)
5. Strengths of this review (1 paragraph)
6. Limitations of this review (1 paragraph)
7. Future research directions (1-2 paragraphs)
8. A brief conclusion paragraph

Use [@citationKey] for citations. Write critically, not just descriptively.

Start with "# Discussion" as the heading. Write ~1,500-2,000 words."""

    return await _call_claude(prompt, SYSTEM_PROMPT, max_tokens=8000)


async def write_full_review(output: ReviewOutput) -> str:
    """Generate the complete publication-ready review article.

    Calls Claude for each section in sequence to maintain coherence
    and manage context windows effectively.
    """
    import asyncio
    from datetime import date

    topic = output.topic
    articles = output.articles
    stats = output.statistics

    logger.info("Writing AI-powered literature review...")

    # Generate sections — introduction and methods can be parallel,
    # but results should come first to inform discussion
    logger.info("  Writing Introduction and Methods...")
    intro_task = write_introduction(topic, articles, stats)
    methods_task = write_methods(topic, stats)
    intro, methods = await asyncio.gather(intro_task, methods_task)

    logger.info("  Writing Results...")
    results = await write_results(topic, articles, stats)

    logger.info("  Writing Discussion...")
    discussion = await write_discussion(topic, articles, stats)

    # Assemble the complete document
    frontmatter = f"""---
title: "Literature Review: {topic}"
subtitle: "A Systematic Literature Review"
date: "{date.today().isoformat()}"
author: "Automated Literature Review Pipeline"
format:
  pdf:
    toc: true
    toc-depth: 3
    number-sections: true
    colorlinks: true
    cite-method: citeproc
    documentclass: article
    geometry:
      - margin=1in
    fontsize: 11pt
    linestretch: 1.5
  docx:
    toc: true
    toc-depth: 3
    number-sections: true
  html:
    toc: true
    toc-depth: 3
    number-sections: true
    theme: cosmo
bibliography: references.bib
csl: https://raw.githubusercontent.com/citation-style-language/styles/master/american-medical-association.csl
abstract: |
  **Background:** {topic} represents a significant clinical challenge requiring comprehensive
  evidence synthesis. This systematic review aims to consolidate current knowledge from
  high-impact peer-reviewed literature.

  **Methods:** A systematic search of Scopus, PubMed, and Embase databases was conducted
  covering publications from {stats.date_range}. Articles were filtered by journal quality
  metrics (CiteScore >= 3.0), and all DOIs were validated. Of {stats.total_articles_found}
  initial records, {stats.articles_included} met inclusion criteria.

  **Results:** The included studies were published across {stats.journals_represented} journals,
  with an average of {stats.avg_citation_count:.0f} citations per article. Thematic analysis
  revealed key patterns in pathogenesis, diagnosis, management, and outcomes.

  **Conclusion:** This review provides a comprehensive synthesis of the evidence on {topic},
  identifying both established knowledge and critical gaps warranting further investigation.
---

"""

    # Combine all sections
    document = frontmatter + "\n\n".join([
        intro,
        methods,
        results,
        discussion,
        "# References\n\n::: {#refs}\n:::\n",
    ])

    logger.info("  Review article complete.")
    return document
