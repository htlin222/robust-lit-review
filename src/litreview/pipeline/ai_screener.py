"""AI-powered article screening with PICO criteria.

Two-pass screening replaces shallow journal-metric filtering with
semantic relevance assessment against the actual research question:

  Pass 1 (fast): PubMedBERT embedding similarity → auto-include/exclude extremes
  Pass 2 (precise): LLM judge with structured PICO criteria → final decisions

Integrates into the pipeline as Stage 4.5 between quality filter and DOI validation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from litreview.models import ArticleMetadata
from litreview.utils.llm import SubagentTask

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# Embedding similarity thresholds for Pass 1
AUTO_INCLUDE_THRESHOLD = 0.50  # High confidence: clearly relevant
AUTO_EXCLUDE_THRESHOLD = 0.15  # High confidence: clearly irrelevant


@dataclass
class PICOCriteria:
    """PICO framework for structured inclusion/exclusion criteria.

    Population, Intervention, Comparison, Outcome — the standard
    clinical research framework for systematic reviews.
    """

    population: str = ""  # e.g., "adult patients with HLH"
    intervention: str = ""  # e.g., "targeted therapies (emapalumab, ruxolitinib)"
    comparison: str = ""  # e.g., "standard HLH-94/2004 protocol"
    outcome: str = ""  # e.g., "survival, response rate, remission"
    study_types: list[str] = field(
        default_factory=lambda: [
            "original research",
            "clinical trial",
            "systematic review",
            "meta-analysis",
            "guideline",
            "cohort study",
            "case-control study",
        ]
    )
    additional_criteria: str = ""  # Free-text for topic-specific criteria

    def to_prompt(self) -> str:
        """Format PICO criteria for LLM prompt."""
        parts = ["**PICO Inclusion Criteria:**"]
        if self.population:
            parts.append(f"- **Population (P):** {self.population}")
        if self.intervention:
            parts.append(f"- **Intervention (I):** {self.intervention}")
        if self.comparison:
            parts.append(f"- **Comparison (C):** {self.comparison}")
        if self.outcome:
            parts.append(f"- **Outcome (O):** {self.outcome}")
        if self.study_types:
            parts.append(f"- **Study types:** {', '.join(self.study_types)}")
        if self.additional_criteria:
            parts.append(f"- **Additional:** {self.additional_criteria}")
        return "\n".join(parts)


@dataclass
class ScreeningResult:
    """Result of screening an individual article."""

    article: ArticleMetadata
    status: str  # "include" | "exclude" | "uncertain"
    reason: str
    pico_match: dict[str, bool] = field(default_factory=dict)  # {"P": True, "I": False, ...}
    confidence: float = 0.0  # 0-1
    pass_source: str = ""  # "pass1_auto_include" | "pass1_auto_exclude" | "pass2_llm"


async def generate_pico_criteria(
    topic: str,
    search_terms: list[str] | None = None,
) -> PICOCriteria:
    """Auto-generate PICO criteria from topic using Claude.

    Returns structured criteria that the LLM judge uses for screening.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY, using basic PICO criteria from topic")
        return PICOCriteria(
            population=f"patients or subjects related to {topic}",
            outcome=f"outcomes related to {topic}",
        )

    terms_str = ", ".join(search_terms) if search_terms else topic

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1000,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Generate PICO criteria for a systematic literature review on: {topic}\n"
                                f"Search terms: {terms_str}\n\n"
                                f"Return ONLY valid JSON with these fields:\n"
                                f'{{"population": "...", "intervention": "...", "comparison": "...", '
                                f'"outcome": "...", "study_types": [...], "additional_criteria": "..."}}'
                            ),
                        }
                    ],
                },
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"]
            # Extract JSON from response
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()
            data = json.loads(text)
            return PICOCriteria(**data)
        except Exception as e:
            logger.warning(f"PICO generation failed: {e}, using basic criteria")
            return PICOCriteria(
                population=f"patients or subjects related to {topic}",
                outcome=f"outcomes related to {topic}",
            )


def _pass1_embedding_screen(
    articles: list[ArticleMetadata],
    topic: str,
) -> tuple[list[ArticleMetadata], list[ArticleMetadata], list[ArticleMetadata]]:
    """Pass 1: Fast embedding-based screening.

    Returns (auto_included, uncertain, auto_excluded).
    """
    try:
        from litreview.pipeline.semantic_selector import compute_relevance_scores
    except ImportError:
        logger.warning("Semantic selector not available, skipping Pass 1")
        return [], articles, []

    scored = compute_relevance_scores(topic, articles)

    auto_included = []
    uncertain = []
    auto_excluded = []

    for article, score in scored:
        article.relevance_score = score
        if score >= AUTO_INCLUDE_THRESHOLD:
            article.screening_status = "include"
            article.screening_reason = f"High relevance (score={score:.3f})"
            auto_included.append(article)
        elif score <= AUTO_EXCLUDE_THRESHOLD:
            article.screening_status = "exclude"
            article.screening_reason = f"Low relevance (score={score:.3f})"
            auto_excluded.append(article)
        else:
            uncertain.append(article)

    logger.info(
        f"Pass 1 screening: {len(auto_included)} auto-include, "
        f"{len(uncertain)} uncertain, {len(auto_excluded)} auto-exclude"
    )
    return auto_included, uncertain, auto_excluded


def generate_screening_tasks(
    uncertain_articles: list[ArticleMetadata],
    topic: str,
    pico: PICOCriteria,
    output_dir: Path,
    batch_size: int = 10,
) -> list[SubagentTask]:
    """Generate LLM judge tasks for Pass 2 screening of uncertain articles.

    Each batch of articles is sent to a haiku judge for PICO-based
    inclusion/exclusion decisions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = []

    for batch_idx in range(0, len(uncertain_articles), batch_size):
        batch = uncertain_articles[batch_idx: batch_idx + batch_size]

        articles_text = []
        for i, article in enumerate(batch):
            idx = batch_idx + i
            abstract_preview = (
                (article.abstract[:400] + "...") if article.abstract else "(no abstract)"
            )
            articles_text.append(
                f"[{idx}] @{article.citation_key}\n"
                f"  Title: {article.title}\n"
                f"  Journal: {article.journal} ({article.year}), {article.citation_count} citations\n"
                f"  Relevance score: {article.relevance_score or 0:.3f}\n"
                f"  Abstract: {abstract_preview}"
            )

        output_path = output_dir / f"screen_batch_{batch_idx:03d}.json"

        prompt = (
            f"You are a systematic review screening judge.\n\n"
            f"**Review topic:** {topic}\n\n"
            f"{pico.to_prompt()}\n\n"
            f"**Exclusion criteria:**\n"
            f"- Only tangentially related (mentions the topic in passing)\n"
            f"- Wrong population (e.g., pediatric-only when review is about adults)\n"
            f"- Editorials/commentaries without primary data\n"
            f"- Case reports with fewer than 5 patients\n"
            f"- Non-English without English abstract\n\n"
            f"**Articles to screen:**\n\n"
            + "\n\n".join(articles_text)
            + "\n\n"
            f"For each article, respond with a JSON array:\n"
            f'[{{"index": {batch_idx}, "include": true/false, '
            f'"reason": "1-sentence justification", '
            f'"pico_match": {{"P": true/false, "I": true/false, "C": true/false, "O": true/false}}}}'
            f"]\n\n"
            f"Write the JSON result to: {output_path}"
        )

        tasks.append(
            SubagentTask(
                task_id=f"screen_batch_{batch_idx:03d}",
                description=f"Screen articles {batch_idx}-{batch_idx + len(batch)}",
                prompt=prompt,
                output_path=output_path,
                model="haiku",
            )
        )

    logger.info(f"Generated {len(tasks)} screening tasks for {len(uncertain_articles)} uncertain articles")
    return tasks


def collect_screening_results(
    uncertain_articles: list[ArticleMetadata],
    output_dir: Path,
) -> tuple[list[ArticleMetadata], list[ArticleMetadata], list[ArticleMetadata]]:
    """Collect Pass 2 LLM screening results.

    Returns (included, still_uncertain, excluded).
    """
    from litreview.utils.llm import parse_json_result

    included = []
    still_uncertain = []
    excluded = []

    # Build index map
    decisions: dict[int, dict] = {}
    for result_path in sorted(output_dir.glob("screen_batch_*.json")):
        raw = parse_json_result(result_path)
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            decisions[item.get("index", -1)] = item

    for idx, article in enumerate(uncertain_articles):
        decision = decisions.get(idx)
        if decision is None:
            # Not judged — keep as uncertain for CP2
            article.screening_status = "uncertain"
            article.screening_reason = "Not judged by LLM"
            still_uncertain.append(article)
        elif decision.get("include", False):
            article.screening_status = "include"
            article.screening_reason = decision.get("reason", "LLM approved")
            pico = decision.get("pico_match", {})
            article.screening_reason += f" PICO: P={pico.get('P', '?')}, I={pico.get('I', '?')}, C={pico.get('C', '?')}, O={pico.get('O', '?')}"
            included.append(article)
        else:
            article.screening_status = "exclude"
            article.screening_reason = decision.get("reason", "LLM excluded")
            excluded.append(article)

    logger.info(
        f"Pass 2 results: {len(included)} included, "
        f"{len(still_uncertain)} uncertain, {len(excluded)} excluded"
    )
    return included, still_uncertain, excluded


async def screen_articles(
    articles: list[ArticleMetadata],
    topic: str,
    pico: PICOCriteria | None = None,
    output_dir: Path | None = None,
) -> tuple[list[ArticleMetadata], list[ArticleMetadata]]:
    """Full two-pass screening pipeline.

    Pass 1: Embedding similarity — auto-include/exclude clear cases.
    Pass 2: LLM judge for uncertain articles (requires external dispatch).

    Returns (screened_articles, borderline_articles).
    Borderline articles should be presented at CP2 checkpoint for human review.

    Note: Pass 2 tasks must be dispatched externally (via Claude Code Agent tool).
    This function only runs Pass 1 synchronously. For Pass 2, use:
      1. generate_screening_tasks() to create judge tasks
      2. Dispatch tasks via Agent tool
      3. collect_screening_results() to get final decisions
    """
    if pico is None:
        pico = await generate_pico_criteria(topic)

    # Pass 1: Embedding screen
    auto_included, uncertain, auto_excluded = _pass1_embedding_screen(articles, topic)

    logger.info(
        f"AI Screening complete — Pass 1 only (synchronous):\n"
        f"  Auto-included: {len(auto_included)}\n"
        f"  Need Pass 2 (uncertain): {len(uncertain)}\n"
        f"  Auto-excluded: {len(auto_excluded)}"
    )

    # For now, return auto-included + uncertain as screened
    # Uncertain articles become borderline for CP2 human review
    screened = auto_included + uncertain
    borderline = uncertain

    return screened, borderline


def classify_with_llm(
    articles: list[ArticleMetadata],
    topic: str,
    output_dir: Path,
    batch_size: int = 10,
) -> list[SubagentTask]:
    """Generate LLM classification tasks to replace keyword-based subtopic classification.

    Each article gets categorized into subtopic categories by a haiku judge,
    replacing the keyword matching in enrichment.classify_article_subtopic().
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = []

    for batch_idx in range(0, len(articles), batch_size):
        batch = articles[batch_idx: batch_idx + batch_size]

        articles_text = []
        for i, article in enumerate(batch):
            idx = batch_idx + i
            abstract_preview = (
                (article.abstract[:400] + "...") if article.abstract else "(no abstract)"
            )
            articles_text.append(
                f"[{idx}] @{article.citation_key}\n"
                f"  Title: {article.title}\n"
                f"  Abstract: {abstract_preview}"
            )

        output_path = output_dir / f"classify_batch_{batch_idx:03d}.json"

        prompt = (
            f"You are a medical literature classifier.\n\n"
            f"**Review topic:** {topic}\n\n"
            f"**Available categories:**\n"
            f"epidemiology, pathogenesis, diagnosis, classification, genetics, "
            f"treatment_conventional, treatment_targeted, treatment_transplant, "
            f"infection_trigger, malignancy_trigger, autoimmune_trigger, iatrogenic, "
            f"prognosis, review_guideline, pediatric, general\n\n"
            f"**Articles to classify:**\n\n"
            + "\n\n".join(articles_text)
            + "\n\n"
            f"For each article, respond with a JSON array:\n"
            f'[{{"index": 0, "categories": ["category1", "category2"]}}]\n\n'
            f"Each article can have 1-3 categories. Choose the most specific ones.\n"
            f"Write the JSON result to: {output_path}"
        )

        tasks.append(
            SubagentTask(
                task_id=f"classify_batch_{batch_idx:03d}",
                description=f"Classify articles {batch_idx}-{batch_idx + len(batch)}",
                prompt=prompt,
                output_path=output_path,
                model="haiku",
            )
        )

    logger.info(f"Generated {len(tasks)} classification tasks for {len(articles)} articles")
    return tasks


def collect_classification_results(
    articles: list[ArticleMetadata],
    output_dir: Path,
) -> list[ArticleMetadata]:
    """Collect LLM classification results and update article subtopic_categories."""
    from litreview.utils.llm import parse_json_result

    decisions: dict[int, list[str]] = {}
    for result_path in sorted(output_dir.glob("classify_batch_*.json")):
        raw = parse_json_result(result_path)
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            idx = item.get("index", -1)
            categories = item.get("categories", ["general"])
            decisions[idx] = categories

    for idx, article in enumerate(articles):
        categories = decisions.get(idx)
        if categories:
            article.subtopic_categories = categories
        elif not article.subtopic_categories:
            # Fallback to keyword classification
            from litreview.pipeline.enrichment import classify_article_subtopic
            article.subtopic_categories = classify_article_subtopic(article)

    classified_count = sum(1 for a in articles if a.subtopic_categories)
    logger.info(f"Classification: {classified_count}/{len(articles)} articles classified")
    return articles
