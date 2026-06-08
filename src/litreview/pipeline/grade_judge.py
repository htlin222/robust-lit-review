"""GRADE certainty assessment per PICO via a Sonnet subagent.

Clones the llm_prisma_judge contract. The subagent rates the five GRADE
downgrade domains; Python recomputes ``final_certainty`` deterministically from
the starting level and the sum of downgrades/upgrades (the LLM's own certainty
label is treated as advisory only).

Usage from SKILL.md:
1. Python: task = generate_grade_task(pico, included_studies, extracted, output_dir)
2. Claude Code: dispatch Agent(model="sonnet", prompt=task.prompt)
3. Python: grade = collect_grade(pico, output_dir)
"""

from __future__ import annotations

import logging
from pathlib import Path

from litreview.models import ArticleMetadata, GradeAssessment, GradeDomain, PICOQuestion
from litreview.pipeline.enrichment import ExtractedData
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

GRADE_DOMAINS = (
    "risk_of_bias",
    "inconsistency",
    "indirectness",
    "imprecision",
    "publication_bias",
)

_LEVELS = ("very_low", "low", "moderate", "high")
_LEVEL_INDEX = {name: i for i, name in enumerate(_LEVELS)}


def compute_final_certainty(starting_level: str, total_change: int) -> str:
    """Map (starting level + net change) to a GRADE certainty label.

    ``total_change`` is the signed sum of domain downgrades (negative) and any
    upgrades (positive). The result is clamped to [very_low, high].
    """
    start = _LEVEL_INDEX.get(starting_level, _LEVEL_INDEX["high"])
    idx = max(0, min(len(_LEVELS) - 1, start + total_change))
    return _LEVELS[idx]


def _study_line(article: ArticleMetadata, data: ExtractedData | None) -> str:
    bits = [f"@{article.citation_key}"]
    if data and data.study_type:
        bits.append(data.study_type)
    if data and data.sample_sizes:
        bits.append(data.sample_sizes[0])
    if data and data.key_findings:
        bits.append(data.key_findings[0])
    stats = []
    if data:
        stats = (data.hazard_ratios + data.odds_ratios + data.p_values
                 + data.confidence_intervals + data.percentages)[:3]
    if stats:
        bits.append("; ".join(stats))
    return " | ".join(bits)


def generate_grade_task(
    pico: PICOQuestion,
    included_studies: list[ArticleMetadata],
    extracted: dict[str, ExtractedData] | None,
    output_dir: Path,
) -> SubagentTask:
    """Generate the Sonnet GRADE task for one PICO.

    Args:
        extracted: optional map of citation_key -> ExtractedData (from
            llm_extraction.collect_extraction_results) used to enrich study lines.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"grade_{pico.pico_id}.json"

    extracted = extracted or {}
    study_lines = "\n".join(
        f"- {_study_line(a, extracted.get(a.citation_key))}" for a in included_studies
    ) or "- (no included studies)"

    prompt = (
        "You are a GRADE methodologist assessing certainty of evidence for a "
        "systematic-review question.\n\n"
        f"PICO QUESTION: {pico.question_text or pico.outcome}\n"
        f"Population: {pico.population}\nIntervention: {pico.intervention}\n"
        f"Comparator: {pico.comparator}\nOutcome: {pico.outcome}\n\n"
        "INCLUDED STUDIES (one per line):\n"
        f"{study_lines}\n\n"
        "Start at HIGH certainty if the body of evidence is RCT-dominant, or LOW if "
        "observational-dominant (state which). For each of the 5 domains, rate "
        "not_serious / serious / very_serious with a downgrade of 0 / -1 / -2 and a "
        "one-sentence justification grounded in the studies above:\n"
        "  risk_of_bias, inconsistency, indirectness, imprecision, publication_bias\n\n"
        "Also state the overall effect_direction for the intervention on this outcome: "
        "beneficial | no_effect | harmful | mixed.\n\n"
        "Return ONLY this JSON (no markdown). Write it to: "
        f"{output_path}\n"
        "{\n"
        '  "starting_level": "high|low",\n'
        '  "domains": [\n'
        '    {"name": "risk_of_bias", "rating": "not_serious|serious|very_serious", '
        '"downgrade": 0, "justification": "...", "evidence_refs": ["@key"]}\n'
        "  ],\n"
        '  "effect_direction": "beneficial|no_effect|harmful|mixed",\n'
        '  "final_certainty": "high|moderate|low|very_low",\n'
        '  "n_studies": 0, "n_rct": 0, "summary": "one-to-two sentence GRADE narrative"\n'
        "}"
    )

    return SubagentTask(
        task_id=f"grade_{pico.pico_id}",
        description=f"GRADE: {pico.outcome_domain[:20]}",
        prompt=prompt,
        output_path=output_path,
        model="sonnet",
    )


def collect_grade(pico: PICOQuestion, output_dir: Path) -> GradeAssessment:
    """Parse the GRADE result; recompute final_certainty deterministically."""
    output_path = output_dir / f"grade_{pico.pico_id}.json"
    raw = parse_json_result(output_path)

    if raw is None:
        logger.warning("No GRADE result for %s; defaulting to very_low", pico.pico_id)
        return GradeAssessment(pico_id=pico.pico_id, final_certainty="very_low")

    starting_level = str(raw.get("starting_level", "high")).lower()
    if starting_level not in _LEVEL_INDEX:
        starting_level = "high"

    domains: list[GradeDomain] = []
    for d in raw.get("domains", []):
        if not isinstance(d, dict):
            continue
        domains.append(
            GradeDomain(
                name=str(d.get("name", "")),
                rating=str(d.get("rating", "not_serious")),
                downgrade=int(d.get("downgrade", 0) or 0),
                justification=str(d.get("justification", "")),
                evidence_refs=[str(r) for r in d.get("evidence_refs", []) if r],
            )
        )

    upgrades: list[GradeDomain] = []
    for u in raw.get("upgrades", []):
        if not isinstance(u, dict):
            continue
        upgrades.append(
            GradeDomain(
                name=str(u.get("name", "")),
                rating=str(u.get("rating", "")),
                downgrade=int(u.get("downgrade", 0) or 0),
                justification=str(u.get("justification", "")),
                evidence_refs=[str(r) for r in u.get("evidence_refs", []) if r],
            )
        )

    # Deterministic recompute: clamp downgrades to [-2, 0], then apply.
    total_change = sum(max(-2, min(0, d.downgrade)) for d in domains)
    total_change += sum(max(0, u.downgrade) for u in upgrades)
    final_certainty = compute_final_certainty(starting_level, total_change)

    effect = str(raw.get("effect_direction", "no_effect")).lower()
    if effect not in ("beneficial", "no_effect", "harmful", "mixed"):
        effect = "no_effect"

    assessment = GradeAssessment(
        pico_id=pico.pico_id,
        starting_level=starting_level,
        domains=domains,
        upgrades=upgrades,
        final_certainty=final_certainty,
        effect_direction=effect,
        n_studies=int(raw.get("n_studies", 0) or 0),
        n_rct=int(raw.get("n_rct", 0) or 0),
        summary=str(raw.get("summary", "")),
    )
    logger.info(
        "GRADE %s: start=%s change=%d -> %s (effect=%s)",
        pico.pico_id, starting_level, total_change, final_certainty, effect,
    )
    return assessment
