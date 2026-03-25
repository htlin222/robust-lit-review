"""Section dispatcher for modular, parallel review writing.

Splits enriched articles by subtopic and generates per-section context files.
Each section can be written by a parallel subagent, then assembled via
Quarto's {{< include >}} syntax.

Usage from Claude Code skill:
1. Run dispatcher to create section contexts
2. Launch parallel writing subagents (one per section)
3. Assemble main.qmd with includes
4. Render
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from litreview.models import ArticleMetadata, ReviewStatistics
from litreview.pipeline.enrichment import (
    ExtractedData,
    build_rich_article_context,
    classify_article_subtopic,
    enrich_articles,
)

logger = logging.getLogger(__name__)


@dataclass
class SectionSpec:
    """Specification for one review section to be written by a subagent."""

    filename: str  # e.g., "01-introduction.qmd"
    heading: str  # e.g., "# Introduction"
    subtopics: list[str]  # Which subtopic categories to include
    word_target: str  # e.g., "1,200-1,500"
    writing_instructions: str  # Specific instructions for this section


# Define the review sections
SECTIONS: list[SectionSpec] = [
    SectionSpec(
        filename="01-introduction.qmd",
        heading="# Introduction",
        subtopics=["review_guideline", "classification", "epidemiology", "pathogenesis"],
        word_target="1,200-1,500",
        writing_instructions="""Write the Introduction section. Must include:
1. Opening paragraph on clinical significance of HLH in adults — mortality rates, incidence trends
2. Historical context — first described 1939 (histiocytic medullary reticulosis), 1952 familial form
3. Primary vs secondary HLH — genetic (PRF1, UNC13D, STX11) vs acquired (infections, malignancy, autoimmune)
4. Why a review is needed — field transformed 2016-2026 by COVID-19, CAR-T, checkpoint inhibitors
5. Objectives of this review (numbered list)

Use specific epidemiologic data when available. Frame the clinical urgency.""",
    ),
    SectionSpec(
        filename="02-methods.qmd",
        heading="# Methods",
        subtopics=[],  # No articles needed — this is methodological
        word_target="800-1,000",
        writing_instructions="""Write the Methods section. Include:
1. Search Strategy: Scopus, PubMed, Embase; date range 2016-2026; search terms
2. PRISMA Flow: 897 identified → 783 after deduplication → 50 included
3. Inclusion criteria: CiteScore >= 3.0, peer-reviewed, English, adult relevance
4. Exclusion criteria: case reports <5 patients, editorials, pediatric-only
5. Quality assessment approach
6. Data extraction and thematic synthesis methodology

Include the PRISMA flow as a code block diagram.""",
    ),
    SectionSpec(
        filename="03-pathogenesis.qmd",
        heading="# Pathogenesis and Immunology",
        subtopics=["pathogenesis", "genetics"],
        word_target="1,000-1,200",
        writing_instructions="""Write the Pathogenesis section. Must include:
1. IFNγ as master cytokine — NK/CD8+ T cell dysfunction → persistent antigen → IFNγ → macrophage activation
2. Cytokine cascade: IL-1, IL-6, IL-18, TNFα, IFNγ — roles and interactions
3. NLRP3 inflammasome as upstream amplifier (IL-1β and IL-18 processing)
4. Ferritin biology — not just biomarker but pathogenic mediator (active macrophage secretion)
5. Monocyte/macrophage axis — tissue infiltration, hemophagocytosis
6. Genetic underpinnings — PRF1, UNC13D, STX11, STXBP2; hypomorphic variants in adults

Use specific numbers: cytokine levels, ferritin thresholds, perforin secretion data.""",
    ),
    SectionSpec(
        filename="04-diagnosis.qmd",
        heading="# Classification and Diagnosis",
        subtopics=["diagnosis", "classification"],
        word_target="1,200-1,500",
        writing_instructions="""Write the Classification and Diagnosis section. MUST include ALL of these:
1. Revised Histiocyte Society classification (Emile 2016) — 5 groups
2. HLH-2004 criteria — list all 8 criteria with specific thresholds:
   - Fever >38.5°C, splenomegaly, bicytopenia
   - Ferritin ≥500 μg/L, triglycerides ≥265 mg/dL or fibrinogen ≤1.5 g/L
   - sCD25 (sIL-2R) ≥2,400 U/mL, low/absent NK cell activity
   - Hemophagocytosis on biopsy
3. HLH-2024 update — removed NK cell activity criterion (7 criteria, 5 needed)
4. HScore — 9 variables, cutoff 168-169 points, sensitivity 93-100%, specificity 86-94%
5. EULAR/ACR MAS criteria — ferritin >684 ng/mL + 2 of 4 criteria
6. sIL-2R/ferritin ratio — >8.6 suggests lymphoma
7. Adult vs pediatric diagnostic challenges
8. Role of genetic testing in adults — hypomorphic variants

Include EXACT numbers for sensitivity, specificity, cutoffs.""",
    ),
    SectionSpec(
        filename="05-etiology.qmd",
        heading="# Etiology and Triggers",
        subtopics=["infection_trigger", "malignancy_trigger", "autoimmune_trigger", "iatrogenic"],
        word_target="1,200-1,500",
        writing_instructions="""Write the Etiology section with subsections:

## Infection-Associated HLH
- Name SPECIFIC organisms: EBV (most common), CMV, HSV-1/2, HHV-6, HHV-8, HIV, SARS-CoV-2
- Bacterial: M. tuberculosis, Salmonella, S. aureus, tick-borne (Ehrlichia, Rickettsia)
- Fungal: Histoplasma, Candida, Cryptococcus, Aspergillus
- Parasitic: Plasmodium, Toxoplasma, Babesia, Leishmania

## Malignancy-Associated HLH
- T-cell and NK-cell lymphomas most common, also DLBCL, Hodgkin
- sIL-2R/ferritin ratio for lymphoma suspicion
- Multicentric Castleman disease overlap

## Autoimmune/MAS
- SLE, AOSD, sJIA, RA, vasculitis, inflammatory bowel disease
- MAS in ~6.2% of AOSD hospitalizations (9% mortality vs 1.5%)

## Iatrogenic HLH
- CAR-T: distinguish CRS from IEC-HS (delayed onset, recrudescent after CRS resolves)
  Name products: axicabtagene ciloleucel, lisocabtagene maraleucel, ciltacabtagene autoleucel
- ICIs: pembrolizumab, nivolumab, nivolumab/ipilimumab; onset ~102 days; mortality 13.7-15.3%
- Drugs: lamotrigine, carbamazepine, phenytoin, sulfamethoxazole""",
    ),
    SectionSpec(
        filename="06-treatment.qmd",
        heading="# Treatment and Management",
        subtopics=["treatment_conventional", "treatment_targeted", "treatment_transplant"],
        word_target="1,500-1,800",
        writing_instructions="""Write the Treatment section. MUST include specific dosing:

## Standard HLH-Directed Therapy
- HLH-94: etoposide 150 mg/m² (twice weekly weeks 1-2, weekly weeks 3-8) + dexamethasone 10 mg/m²/day (tapered over 8 weeks) + intrathecal methotrexate
- HLH-2004: added upfront cyclosporine A (week 1)
- 5-year survival 54% (HLH-94) vs no significant improvement (HLH-2004)
- Adult modifications: reduce to 100 mg/m² or 3 doses in weeks 1-2

## Adult-Specific Guidelines (Rose 2019)
- Escalating approach by severity: steroids → IVIG → etoposide → salvage
- Trigger-directed therapy paramount

## Targeted Therapies (with trial data)
- Emapalumab (anti-IFNγ): 63% response in refractory primary HLH (n=34, P=0.02), FDA approved
- Anakinra (IL-1R antagonist): reduced mortality in sepsis-MAS subgroup (n=763, P=0.0071), starting dose 1-2 mg/kg
- Ruxolitinib (JAK1/2): improved survival in mouse models, high ORR with dexamethasone
- Tocilizumab (anti-IL-6): standard for CRS, mixed evidence in classical HLH
- Novel: ELA026 (anti-SIRPα), itacitinib (selective JAK1)

## Trigger-Specific Treatment
- Lymphoma: DA-EPOCH-R + etoposide
- MAS: pulse methylprednisolone 1 g/day × 3-5 days + IVIG 1 g/kg × 2 days, then anakinra
- EBV: rituximab + HLH-94, salvage with ICI (nivolumab)

## HSCT
- Definitive for primary HLH, selected refractory secondary
- RIC > MAC for survival, bone marrow/PBSC > cord blood
- Alemtuzumab preconditioning: 75% 3-year OS""",
    ),
    SectionSpec(
        filename="07-covid.qmd",
        heading="# COVID-19 and the HLH Paradigm",
        subtopics=["infection_trigger", "pathogenesis"],
        word_target="800-1,000",
        writing_instructions="""Write the COVID-19 section. Include:
1. COVID-19 as model for secondary HLH — Mehta 2020 Lancet letter (7,564 citations)
2. Similarities: hyperferritinemia, IL-6 elevation, macrophage activation, multi-organ failure
3. Differences: COVID cytokine profiles LOWER IFNγ and IL-18 than classical HLH
4. COVID coagulopathy distinct: pulmonary intravascular coagulopathy, immunothrombosis
5. MIS-C: 30-fold increase in Kawasaki-like disease (Verdoni 2020, n=29)
6. Therapeutic crossover: dexamethasone validated in COVID, tocilizumab repurposed, anakinra for hyperinflammatory phenotype
7. Lasting legacy: HLH frameworks (HScore, ferritin monitoring) now mainstream in ICU""",
    ),
    SectionSpec(
        filename="08-discussion.qmd",
        heading="# Discussion",
        subtopics=["review_guideline", "prognosis"],
        word_target="1,500-1,800",
        writing_instructions="""Write the Discussion section:
1. Synthesis of key findings — 4 major advances 2016-2026
2. How the field evolved — from pediatric extrapolation to adult-specific guidelines
3. Clinical implications — when to suspect HLH, HScore screening, treatment urgency
4. Remaining controversies — diagnostic criteria validation, etoposide threshold, CRS vs HLH distinction
5. Strengths: systematic multi-DB search, quality filtering, cross-disciplinary synthesis
6. Limitations: CiteScore bias, no meta-analysis, COVID literature overrepresentation
7. Future directions: biomarker-driven therapy, adult diagnostic criteria, genetic profiling, combination targeted therapy, safer CAR-T engineering
8. Conclusion paragraph (~200 words)""",
    ),
]


def dispatch_sections(
    articles: list[ArticleMetadata],
    stats: ReviewStatistics,
    output_dir: Path,
) -> dict[str, dict]:
    """Prepare section-specific context files for parallel writing agents.

    Returns a dict mapping section filename to its context for the writing agent.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(exist_ok=True)

    # Enrich all articles
    enriched = enrich_articles(articles)

    # Classify articles
    article_categories: dict[str, list[tuple[ArticleMetadata, ExtractedData]]] = {}
    for article, data in enriched:
        categories = classify_article_subtopic(article)
        for cat in categories:
            article_categories.setdefault(cat, []).append((article, data))

    dispatched = {}

    for section in SECTIONS:
        # Gather relevant articles for this section
        relevant: list[tuple[ArticleMetadata, ExtractedData]] = []
        seen_dois = set()
        for subtopic in section.subtopics:
            for article, data in article_categories.get(subtopic, []):
                doi = article.doi or article.title
                if doi not in seen_dois:
                    relevant.append((article, data))
                    seen_dois.add(doi)

        # If no specific subtopics, include all (e.g., methods section)
        if not section.subtopics:
            relevant = []

        # Build context
        context_parts = []
        for article, data in relevant:
            context_parts.append(build_rich_article_context(article, data))
        article_context = "\n\n---\n\n".join(context_parts) if context_parts else "(No specific articles for this section)"

        # Build the section spec
        section_info = {
            "filename": section.filename,
            "heading": section.heading,
            "word_target": section.word_target,
            "writing_instructions": section.writing_instructions,
            "article_count": len(relevant),
            "article_context": article_context,
            "stats": {
                "total_found": stats.total_articles_found,
                "after_dedup": stats.articles_after_dedup,
                "after_quality": stats.articles_after_quality_filter,
                "included": stats.articles_included,
                "journals": stats.journals_represented,
                "date_range": stats.date_range,
                "avg_citations": stats.avg_citation_count,
            },
        }

        # Save context file for the agent
        context_path = sections_dir / f"{section.filename}.context.json"
        with open(context_path, "w") as f:
            json.dump(section_info, f, indent=2, default=str)

        dispatched[section.filename] = section_info
        logger.info(
            f"Dispatched {section.filename}: {len(relevant)} articles, "
            f"{len(article_context):,} chars context"
        )

    return dispatched


def generate_main_qmd(topic: str, stats: ReviewStatistics, output_dir: Path) -> str:
    """Generate the main .qmd file that includes all section files."""
    from datetime import date

    sections_dir = output_dir / "sections"

    content = f"""---
title: "{topic}: A Systematic Review (2016-2026)"
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
csl: https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl
abstract: |
  {{{{< include sections/00-abstract.qmd >}}}}
---

{{{{< include sections/01-introduction.qmd >}}}}

{{{{< include sections/02-methods.qmd >}}}}

{{{{< include sections/03-pathogenesis.qmd >}}}}

{{{{< include sections/04-diagnosis.qmd >}}}}

{{{{< include sections/05-etiology.qmd >}}}}

{{{{< include sections/06-treatment.qmd >}}}}

{{{{< include sections/07-covid.qmd >}}}}

{{{{< include sections/08-discussion.qmd >}}}}

# References

::: {{#refs}}
:::
"""
    return content


def get_section_specs() -> list[SectionSpec]:
    """Return the section specifications for external use."""
    return SECTIONS
