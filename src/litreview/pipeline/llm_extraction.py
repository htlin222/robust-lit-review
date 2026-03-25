"""LLM-based structured data extraction from abstracts.

Replaces regex-based extract_data_from_abstract() with haiku subagent dispatch.
Each article's abstract is sent to a haiku agent that returns structured JSON.

Usage from SKILL.md:
1. Python: tasks = generate_extraction_tasks(articles, output_dir)
2. Claude Code: dispatch each task as Agent(model="haiku", prompt=task.prompt)
3. Python: results = collect_extraction_results(articles, output_dir)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from litreview.models import ArticleMetadata
from litreview.pipeline.enrichment import ExtractedData
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM = """You are a biomedical data extraction specialist.
Given an article's title and abstract, extract structured data into JSON format.
Be precise — only extract what is explicitly stated in the text.
If a field has no data, use an empty list or empty string."""

EXTRACTION_PROMPT_TEMPLATE = """Extract structured data from this article:

Title: {title}
Authors: {authors}
Journal: {journal} ({year})
Abstract: {abstract}

Return ONLY this JSON structure (no markdown, no explanation):
{{
  "study_type": "<RCT|cohort|case-control|cross-sectional|meta-analysis|systematic review|narrative review|case series|phase 1 trial|phase 2 trial|phase 3 trial|guideline|consensus|basic science|other>",
  "sample_size": "<e.g., 'n=342' or '1,204 patients' or ''>",
  "key_statistics": [
    "<e.g., '5-year OS 61%', 'HR 0.28 (95% CI 0.11-0.71)', 'p=0.0071', 'sensitivity 93%'>"
  ],
  "diagnostic_thresholds": [
    "<e.g., 'ferritin >10,000 ng/mL', 'sIL-2R ≥2,400 U/mL', 'HScore cutoff 168'>"
  ],
  "drug_dosing": [
    "<e.g., 'etoposide 150 mg/m² twice weekly', 'anakinra 1-2 mg/kg SC daily'>"
  ],
  "incidence_prevalence": [
    "<e.g., '1.06 per million population', '6.2% of AOSD hospitalizations'>"
  ],
  "key_finding": "<One sentence: the single most important finding of this study>",
  "clinical_relevance": "<One sentence: why this matters for clinical practice>"
}}"""


def generate_extraction_tasks(
    articles: list[ArticleMetadata],
    output_dir: Path,
) -> list[SubagentTask]:
    """Generate haiku subagent tasks for structured extraction.

    Returns list of SubagentTask objects. Each should be dispatched as:
        Agent(model="haiku", prompt=task.prompt, description=task.description)
    The agent must write its JSON result to task.output_path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = []

    for i, article in enumerate(articles):
        if not article.abstract or len(article.abstract) < 50:
            continue

        output_path = output_dir / f"extract_{i:03d}_{article.citation_key}.json"

        prompt = (
            f"{EXTRACTION_SYSTEM}\n\n"
            f"{EXTRACTION_PROMPT_TEMPLATE.format(
                title=article.title,
                authors=', '.join(article.authors[:3]),
                journal=article.journal,
                year=article.year or 'n.d.',
                abstract=article.abstract[:1500],
            )}\n\n"
            f"Write the JSON result to: {output_path}"
        )

        tasks.append(SubagentTask(
            task_id=f"extract_{i:03d}",
            description=f"Extract data: {article.citation_key[:20]}",
            prompt=prompt,
            output_path=output_path,
            model="haiku",
        ))

    logger.info(f"Generated {len(tasks)} extraction tasks for haiku agents")
    return tasks


def collect_extraction_results(
    articles: list[ArticleMetadata],
    output_dir: Path,
) -> list[tuple[ArticleMetadata, ExtractedData]]:
    """Collect and parse results from haiku extraction agents.

    Call this after all extraction agents have completed.
    Returns enriched (article, extracted_data) pairs.
    """
    enriched = []

    for i, article in enumerate(articles):
        result_path = output_dir / f"extract_{i:03d}_{article.citation_key}.json"
        raw = parse_json_result(result_path)

        data = ExtractedData()
        if raw:
            data.study_type = raw.get("study_type", "")
            data.is_clinical_trial = "trial" in data.study_type.lower()

            sample = raw.get("sample_size", "")
            if sample:
                data.sample_sizes = [sample]

            data.key_findings = []
            kf = raw.get("key_finding", "")
            if kf:
                data.key_findings.append(kf)
            cr = raw.get("clinical_relevance", "")
            if cr:
                data.key_findings.append(cr)

            for stat in raw.get("key_statistics", []):
                if "%" in stat:
                    data.percentages.append(stat)
                elif "p" in stat.lower() and ("=" in stat or "<" in stat):
                    data.p_values.append(stat)
                elif "HR" in stat or "hazard" in stat.lower():
                    data.hazard_ratios.append(stat)
                elif "OR" in stat or "odds" in stat.lower():
                    data.odds_ratios.append(stat)
                elif "CI" in stat:
                    data.confidence_intervals.append(stat)
                elif "survival" in stat.lower():
                    data.survival_rates.append(stat)
                elif "sensitivity" in stat.lower() or "specificity" in stat.lower():
                    data.sensitivity_specificity.append(stat)

            data.thresholds = raw.get("diagnostic_thresholds", [])
            data.dosing = raw.get("drug_dosing", [])
            data.incidence = raw.get("incidence_prevalence", [])
            data.conclusion = kf
        else:
            # Fallback to regex extraction
            from litreview.pipeline.enrichment import extract_data_from_abstract
            data = extract_data_from_abstract(article)

        enriched.append((article, data))

    with_data = sum(1 for _, d in enriched if d.has_quantitative_data)
    logger.info(
        f"LLM extraction: {len(enriched)} articles, "
        f"{with_data} with quantitative data"
    )
    return enriched
