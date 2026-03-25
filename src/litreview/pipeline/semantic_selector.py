"""Semantic article selection using PubMedBert embeddings + LLM judge.

Replaces naive citation-count sorting with:
1. S-PubMedBert-MS-MARCO embeddings for topic relevance scoring
2. Haiku subagent as final inclusion judge

Architecture:
  Articles → PubMedBert embedding → cosine similarity to topic → top-K candidates
  → Haiku judge batches → final inclusion/exclusion decisions

Requires: pip install sentence-transformers torch
Model: pritamdeka/S-PubMedBert-MS-MARCO (420MB, downloaded on first use)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from litreview.models import ArticleMetadata
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"


def compute_relevance_scores(
    topic: str,
    articles: list[ArticleMetadata],
    batch_size: int = 64,
) -> list[tuple[ArticleMetadata, float]]:
    """Compute semantic relevance scores using PubMedBert embeddings.

    Returns articles sorted by relevance score (descending).
    """
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. "
            "Install with: uv pip install sentence-transformers torch\n"
            "Falling back to citation-count sorting."
        )
        return [(a, float(a.citation_count or 0)) for a in articles]

    logger.info(f"Loading PubMedBert model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Build document texts: title + abstract
    doc_texts = []
    for article in articles:
        text = article.title
        if article.abstract:
            text += " " + article.abstract[:500]
        doc_texts.append(text)

    logger.info(f"Encoding {len(doc_texts)} documents...")
    topic_embedding = model.encode(topic, convert_to_tensor=True)
    doc_embeddings = model.encode(doc_texts, batch_size=batch_size, convert_to_tensor=True)

    # Compute cosine similarity
    scores = util.cos_sim(topic_embedding, doc_embeddings)[0].cpu().tolist()

    scored = list(zip(articles, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Log distribution
    top_10_avg = sum(s for _, s in scored[:10]) / 10
    bottom_10_avg = sum(s for _, s in scored[-10:]) / 10
    logger.info(
        f"Relevance scores: top-10 avg={top_10_avg:.3f}, "
        f"bottom-10 avg={bottom_10_avg:.3f}"
    )

    return scored


def generate_judge_tasks(
    topic: str,
    scored_articles: list[tuple[ArticleMetadata, float]],
    output_dir: Path,
    candidates: int = 80,
    batch_size: int = 10,
) -> list[SubagentTask]:
    """Generate haiku judge tasks for final article inclusion decisions.

    Takes the top-K candidates by embedding score and asks haiku
    to judge each batch for inclusion/exclusion with reasoning.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    top_candidates = scored_articles[:candidates]

    tasks = []
    for batch_idx in range(0, len(top_candidates), batch_size):
        batch = top_candidates[batch_idx:batch_idx + batch_size]

        articles_text = []
        for i, (article, score) in enumerate(batch):
            idx = batch_idx + i
            abstract_preview = (article.abstract[:300] + "...") if article.abstract else "(no abstract)"
            articles_text.append(
                f"[{idx}] @{article.citation_key}\n"
                f"  Title: {article.title}\n"
                f"  Journal: {article.journal} ({article.year}), {article.citation_count} citations\n"
                f"  Relevance score: {score:.3f}\n"
                f"  Abstract: {abstract_preview}"
            )

        output_path = output_dir / f"judge_batch_{batch_idx:03d}.json"

        prompt = (
            f"You are a systematic review inclusion/exclusion judge.\n\n"
            f"**Review topic:** {topic}\n\n"
            f"**Inclusion criteria:**\n"
            f"- Directly relevant to the review topic in adult populations\n"
            f"- Published in a high-impact peer-reviewed journal\n"
            f"- Provides substantive evidence (not just tangentially mentions the topic)\n"
            f"- Original research, clinical trials, systematic reviews, or authoritative guidelines\n\n"
            f"**Exclusion criteria:**\n"
            f"- Only tangentially related (mentions the topic in passing)\n"
            f"- Pediatric-only without adult applicability\n"
            f"- Editorials or commentaries without primary data\n"
            f"- Duplicate or superseded studies\n\n"
            f"**Articles to judge:**\n\n"
            + "\n\n".join(articles_text)
            + "\n\n"
            f"For each article, respond with a JSON array:\n"
            f'[{{"index": 0, "include": true/false, "reason": "1-sentence justification"}}]\n\n'
            f"Write the JSON result to: {output_path}"
        )

        tasks.append(SubagentTask(
            task_id=f"judge_batch_{batch_idx:03d}",
            description=f"Judge articles {batch_idx}-{batch_idx+len(batch)}",
            prompt=prompt,
            output_path=output_path,
            model="haiku",
        ))

    logger.info(f"Generated {len(tasks)} judge tasks for {len(top_candidates)} candidates")
    return tasks


def collect_judge_results(
    scored_articles: list[tuple[ArticleMetadata, float]],
    output_dir: Path,
    target: int = 50,
) -> list[ArticleMetadata]:
    """Collect inclusion decisions from haiku judges.

    Returns the final selected articles, up to target count.
    """
    included_indices: set[int] = set()
    exclusion_reasons: dict[int, str] = {}

    for result_path in sorted(output_dir.glob("judge_batch_*.json")):
        raw = parse_json_result(result_path)
        if raw is None:
            continue

        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            idx = item.get("index", -1)
            if item.get("include", False):
                included_indices.add(idx)
            else:
                exclusion_reasons[idx] = item.get("reason", "")

    # Select included articles, respecting target count
    selected = []
    for idx in sorted(included_indices):
        if idx < len(scored_articles):
            article, score = scored_articles[idx]
            selected.append(article)

    # If we have more than target, take highest relevance scores
    if len(selected) > target:
        # Re-sort by score among included
        included_scored = [
            (a, s) for i, (a, s) in enumerate(scored_articles)
            if i in included_indices
        ]
        included_scored.sort(key=lambda x: x[1], reverse=True)
        selected = [a for a, _ in included_scored[:target]]

    # If we have fewer than target, add from unjudged by score
    if len(selected) < target:
        for idx, (article, score) in enumerate(scored_articles):
            if len(selected) >= target:
                break
            if idx not in included_indices and idx not in exclusion_reasons:
                selected.append(article)

    logger.info(
        f"Semantic selection: {len(included_indices)} included by judge, "
        f"{len(exclusion_reasons)} excluded, {len(selected)} final"
    )
    return selected


def select_articles(
    topic: str,
    articles: list[ArticleMetadata],
    output_dir: Path,
    target: int = 50,
) -> tuple[list[tuple[ArticleMetadata, float]], list[SubagentTask]]:
    """Full semantic selection pipeline: embed → score → generate judge tasks.

    Returns (scored_articles, judge_tasks).
    After dispatching judge_tasks, call collect_judge_results() to get final selection.
    """
    scored = compute_relevance_scores(topic, articles)
    tasks = generate_judge_tasks(topic, scored, output_dir, candidates=target * 2)
    return scored, tasks
