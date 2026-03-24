"""Quarto document generation and rendering."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from datetime import date

from litreview.models import ArticleMetadata, ReviewOutput, ReviewStatistics
from litreview.utils.statistics import format_statistics_table, format_prisma_flow

logger = logging.getLogger(__name__)


def generate_quarto_frontmatter(topic: str, output_dir: Path) -> str:
    """Generate YAML frontmatter for Quarto document."""
    bib_path = output_dir / "references.bib"
    return f"""---
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
    keep-tex: false
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
csl: https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl
abstract: |
  This literature review provides a comprehensive synthesis of current research on {topic}.
  Articles were systematically retrieved from Scopus, PubMed, and Embase databases,
  filtered by journal impact metrics (CiteScore, SJR), and validated through DOI resolution.
  All references have been verified for accessibility and correctness.
---

"""


def generate_introduction(topic: str, stats: ReviewStatistics) -> str:
    """Generate the introduction section."""
    return f"""# Introduction

This systematic literature review examines the current state of research on **{topic}**.
The review synthesizes findings from {stats.articles_included} peer-reviewed articles
published in {stats.journals_represented} journals spanning {stats.date_range}.

Articles were identified through comprehensive searches of Scopus, PubMed, and Embase
databases and filtered to include only publications from high-impact journals
(average CiteScore: {stats.avg_citescore:.2f}).

## Objectives

1. To provide a comprehensive overview of the current literature on {topic}
2. To identify key themes, methodologies, and findings in the field
3. To highlight research gaps and future directions
4. To synthesize evidence from high-quality, peer-reviewed sources

"""


def generate_methods(stats: ReviewStatistics) -> str:
    """Generate the methods section."""
    queries_text = ""
    if stats.search_queries_used:
        queries_text = "\n".join(f"- `{q}`" for q in stats.search_queries_used)

    return f"""# Methods

## Search Strategy

A systematic search was conducted across the following databases:

- **Scopus** (Elsevier) — using the Scopus Search API
- **PubMed** (NCBI) — using E-utilities API
- **Embase** (Elsevier) — using the Embase Search API

### Search Queries

{queries_text}

## Inclusion Criteria

- Published in peer-reviewed journals
- Journal CiteScore >= 3.0 or SJR quartile Q1/Q2
- Valid, resolvable DOI
- English language

## Article Selection Process

{format_prisma_flow(
    total_found=stats.total_articles_found,
    after_dedup=stats.articles_after_dedup,
    after_quality=stats.articles_after_quality_filter,
    after_validation=stats.articles_with_valid_doi,
    included=stats.articles_included,
)}

"""


def group_articles_by_theme(articles: list[ArticleMetadata]) -> dict[str, list[ArticleMetadata]]:
    """Group articles by broad thematic categories based on journal and title keywords."""
    themes: dict[str, list[ArticleMetadata]] = {}

    for article in articles:
        # Simple keyword-based theming
        title_lower = article.title.lower()
        assigned = False

        theme_keywords = {
            "Methodology and Design": ["method", "framework", "model", "algorithm", "approach", "design", "protocol"],
            "Clinical and Applied Research": ["clinical", "patient", "treatment", "therapy", "trial", "intervention", "outcome"],
            "Review and Synthesis": ["review", "meta-analysis", "synthesis", "overview", "survey", "systematic"],
            "Technology and Innovation": ["technology", "digital", "machine learning", "artificial intelligence", "ai", "deep learning", "novel"],
            "Epidemiology and Public Health": ["epidemiol", "prevalence", "incidence", "population", "public health", "risk factor"],
        }

        for theme, keywords in theme_keywords.items():
            if any(kw in title_lower for kw in keywords):
                themes.setdefault(theme, []).append(article)
                assigned = True
                break

        if not assigned:
            themes.setdefault("General Findings", []).append(article)

    return themes


def generate_results(articles: list[ArticleMetadata], stats: ReviewStatistics) -> str:
    """Generate the results section with thematic grouping."""
    sections = ["# Results\n"]
    sections.append(f"A total of {stats.articles_included} articles met the inclusion criteria.\n")
    sections.append("## Summary Statistics\n")
    sections.append(format_statistics_table(stats))
    sections.append("\n")

    # Year distribution
    if stats.articles_by_year:
        sections.append("## Publication Timeline\n")
        sections.append("| Year | Count |")
        sections.append("|------|-------|")
        for year, count in sorted(stats.articles_by_year.items()):
            sections.append(f"| {year} | {count} |")
        sections.append("\n")

    # Thematic synthesis
    themes = group_articles_by_theme(articles)
    sections.append("## Thematic Synthesis\n")

    for theme_name, theme_articles in themes.items():
        sections.append(f"### {theme_name}\n")
        sections.append(f"This theme encompasses {len(theme_articles)} articles.\n")

        for article in theme_articles[:10]:  # Limit per theme
            cite_key = article.citation_key
            sections.append(
                f"[@{cite_key}] investigated {article.title.lower().rstrip('.')}. "
                f"Published in *{article.journal}*"
                f"{f' (CiteScore: {article.citescore:.1f})' if article.citescore else ''}"
                f", this study has been cited {article.citation_count} times.\n"
            )
        sections.append("")

    return "\n".join(sections)


def generate_discussion(topic: str, stats: ReviewStatistics) -> str:
    """Generate the discussion section."""
    return f"""# Discussion

## Key Findings

This review synthesized {stats.articles_included} high-quality articles on {topic},
drawn from {stats.journals_represented} peer-reviewed journals with an average
CiteScore of {stats.avg_citescore:.2f}. The literature spans from {stats.date_range},
indicating {'active' if stats.articles_included > 20 else 'growing'} research interest in this area.

## Research Trends

The temporal distribution of publications reveals the evolution of research focus in this
domain. The average citation count of {stats.avg_citation_count:.1f} per article suggests
{'high' if stats.avg_citation_count > 20 else 'moderate'} scholarly impact.

## Strengths and Limitations

### Strengths
- Systematic multi-database search (Scopus, PubMed, Embase)
- Quality filtering using CiteScore and SJR metrics
- DOI validation ensuring reference integrity
- Reproducible automated pipeline

### Limitations
- Automated thematic grouping may miss nuanced connections
- Language restricted to English publications
- Journal quality metrics may not capture all impactful work

## Future Directions

Based on the identified gaps, future research should focus on:

1. Expanding the evidence base with emerging methodologies
2. Cross-disciplinary integration of findings
3. Longitudinal studies to track evolving trends

"""


def generate_quarto_document(output: ReviewOutput) -> str:
    """Generate the complete Quarto document."""
    output_dir = Path("output")
    parts = [
        generate_quarto_frontmatter(output.topic, output_dir),
        generate_introduction(output.topic, output.statistics),
        generate_methods(output.statistics),
        generate_results(output.articles, output.statistics),
        generate_discussion(output.topic, output.statistics),
        "# References\n\n::: {#refs}\n:::\n",
    ]
    return "\n".join(parts)


def write_outputs(output: ReviewOutput, output_dir: Path | None = None) -> dict[str, Path]:
    """Write all output files (Quarto, BibTeX) and return file paths."""
    out = output_dir or Path("output")
    out.mkdir(parents=True, exist_ok=True)

    # Generate Quarto content
    quarto_content = generate_quarto_document(output)
    output.quarto_content = quarto_content

    # Recompute stats with word count
    from litreview.utils.statistics import compute_statistics
    output.statistics = compute_statistics(
        articles=output.articles,
        quarto_content=quarto_content,
        bibtex_content=output.bibtex,
        search_queries=output.statistics.search_queries_used,
    )
    # Preserve pipeline stats
    output.statistics.total_articles_found = output.statistics.total_articles_found or len(output.articles)

    paths = {}

    # Write Quarto file
    qmd_path = out / "literature_review.qmd"
    qmd_path.write_text(quarto_content, encoding="utf-8")
    paths["qmd"] = qmd_path
    logger.info(f"Wrote Quarto document: {qmd_path}")

    # Write BibTeX
    bib_path = out / "references.bib"
    bib_path.write_text(output.bibtex, encoding="utf-8")
    paths["bib"] = bib_path
    logger.info(f"Wrote BibTeX: {bib_path}")

    return paths


def render_quarto(output_dir: Path | None = None, formats: list[str] | None = None) -> dict[str, Path]:
    """Render the Quarto document to PDF and DOCX."""
    out = output_dir or Path("output")
    qmd_path = out / "literature_review.qmd"
    formats = formats or ["pdf", "docx"]
    rendered = {}

    qmd_abs = qmd_path.resolve()
    out_abs = out.resolve()

    for fmt in formats:
        try:
            result = subprocess.run(
                ["quarto", "render", str(qmd_abs), "--to", fmt],
                capture_output=True,
                text=True,
                cwd=str(out_abs),
                timeout=120,
            )
            if result.returncode == 0:
                output_path = out / f"literature_review.{fmt}"
                if output_path.exists():
                    rendered[fmt] = output_path
                    logger.info(f"Rendered {fmt}: {output_path}")
                else:
                    logger.warning(f"Render claimed success but file not found: {output_path}")
            else:
                logger.warning(f"Quarto render to {fmt} failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning("Quarto not found. Install with: https://quarto.org/docs/get-started/")
        except subprocess.TimeoutExpired:
            logger.warning(f"Quarto render to {fmt} timed out")

    return rendered
