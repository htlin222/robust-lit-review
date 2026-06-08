"""Claim -> PICO decomposition via a Sonnet subagent.

Follows the generate-task -> dispatch -> collect contract (see utils/llm.py):

1. Python: task = generate_decomposition_task(claim, output_dir)
2. Claude Code: dispatch Agent(model="sonnet", prompt=task.prompt)
3. Python: picos = collect_picos(claim, output_dir)

Decomposition is the highest-leverage step — wrong PICOs waste the whole run —
so it uses Sonnet (reasoning) and feeds a human-approval checkpoint before any
search runs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from litreview.models import PICOQuestion
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

DECOMPOSITION_PROMPT_TEMPLATE = """You are a clinical evidence methodologist building a systematic review.

Decompose the following CLAIM into {max_picos} or fewer independent, testable PICO
sub-questions that together determine whether the claim holds. Each sub-question must
target ONE distinct outcome domain (e.g. a specific efficacy endpoint, a safety
endpoint, or a surrogate marker). Do NOT let two sub-questions share an outcome domain.
Cover efficacy AND safety where the claim implies both.

CLAIM:
{claim}

For EACH sub-question provide:
- population: the patient/participant group
- intervention: the exposure/treatment under test
- comparator: the control condition (use "none/observational" if not applicable)
- outcome: the specific measured outcome
- outcome_domain: a short snake_case tag (e.g. "weight_loss", "glycemic_control", "renal_safety")
- question_text: the full natural-language question (used for evidence cross-check)
- rationale: one sentence on why this sub-question matters to the claim
- primary_terms: 4-8 search terms for the intervention/population (strings)
- secondary_terms: optional outcome-side search terms (strings)
- mesh_terms: optional MeSH headings (strings)
- priority: integer 1 (most central to the claim) .. higher = less central

Return ONLY a JSON array (no markdown, no prose). Write it to:
{output_path}

[
  {{
    "population": "...", "intervention": "...", "comparator": "...",
    "outcome": "...", "outcome_domain": "...", "question_text": "...",
    "rationale": "...", "primary_terms": ["..."], "secondary_terms": ["..."],
    "mesh_terms": ["..."], "priority": 1
  }}
]
"""


def generate_decomposition_task(
    claim: str,
    output_dir: Path,
    max_picos: int = 6,
) -> SubagentTask:
    """Generate the single Sonnet task that decomposes *claim* into PICOs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pico_decomposition.json"
    prompt = DECOMPOSITION_PROMPT_TEMPLATE.format(
        claim=claim, max_picos=max_picos, output_path=output_path
    )
    return SubagentTask(
        task_id="pico_decomposition",
        description="Decompose claim into PICOs",
        prompt=prompt,
        output_path=output_path,
        model="sonnet",
    )


def collect_picos(claim: str, output_dir: Path) -> list[PICOQuestion]:
    """Parse the decomposition result into validated PICOQuestion objects.

    Assigns stable ``pico_id``s and merges any PICOs that collide on
    ``outcome_domain`` (keeping the higher-priority one) so the same evidence
    body is not double-counted across sub-questions.
    """
    output_path = output_dir / "pico_decomposition.json"
    raw = parse_json_result(output_path)
    if raw is None:
        logger.warning("No PICO decomposition found at %s", output_path)
        return []

    items = raw if isinstance(raw, list) else raw.get("pico", []) if isinstance(raw, dict) else []

    picos: list[PICOQuestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            picos.append(
                PICOQuestion(
                    population=str(item.get("population", "")),
                    intervention=str(item.get("intervention", "")),
                    comparator=str(item.get("comparator", "")),
                    outcome=str(item.get("outcome", "")),
                    outcome_domain=str(item.get("outcome_domain", "")),
                    question_text=str(item.get("question_text", "")),
                    rationale=str(item.get("rationale", "")),
                    primary_terms=[str(t) for t in item.get("primary_terms", []) if t],
                    secondary_terms=[str(t) for t in item.get("secondary_terms", []) if t],
                    mesh_terms=[str(t) for t in item.get("mesh_terms", []) if t],
                    priority=int(item.get("priority", 1) or 1),
                )
            )
        except (ValueError, TypeError) as e:
            logger.warning("Skipping malformed PICO item: %s", e)

    merged = _merge_by_domain(picos)
    # Sort by priority (ascending = most central first), then assign stable ids.
    merged.sort(key=lambda p: p.priority)
    for i, pico in enumerate(merged, start=1):
        pico.pico_id = f"pico_{i:02d}"

    logger.info("Decomposed claim into %d PICO question(s)", len(merged))
    return merged


def _merge_by_domain(picos: list[PICOQuestion]) -> list[PICOQuestion]:
    """Keep one PICO per outcome_domain (the lowest-priority-number wins)."""
    best: dict[str, PICOQuestion] = {}
    passthrough: list[PICOQuestion] = []
    for pico in picos:
        domain = pico.outcome_domain.strip().lower()
        if not domain:
            passthrough.append(pico)
            continue
        existing = best.get(domain)
        if existing is None or pico.priority < existing.priority:
            best[domain] = pico
    return list(best.values()) + passthrough
