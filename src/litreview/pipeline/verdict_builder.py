"""Verdict assembly: GRADE + OpenEvidence cross-check -> Verdict, and rollup.

Pure, deterministic functions (no I/O) so the adjudication logic is unit-tested
and reproducible from the audit trail. The claim under test is always of the
form "the intervention improves/benefits the outcome", so:
  - good-certainty BENEFICIAL effect   -> supported
  - good-certainty NO_EFFECT / HARMFUL -> refuted
  - low/very-low certainty or MIXED    -> uncertain
An OpenEvidence DISAGREE caps confidence one level lower and softens a
supported/refuted verdict to uncertain, surfacing the dissent rather than
hiding it.
"""

from __future__ import annotations

from litreview.models import GradeAssessment, OpenEvidenceCheck, PicoResult, Verdict

_LEVELS = ("very_low", "low", "moderate", "high")
_LEVEL_INDEX = {name: i for i, name in enumerate(_LEVELS)}
_GOOD_CERTAINTY = ("high", "moderate")


def _downgrade_one(certainty: str) -> str:
    idx = _LEVEL_INDEX.get(certainty, 0)
    return _LEVELS[max(0, idx - 1)]


def map_verdict(certainty: str, effect_direction: str) -> str:
    """Map (certainty, effect_direction) to supported/uncertain/refuted."""
    if certainty not in _GOOD_CERTAINTY or effect_direction == "mixed":
        return "uncertain"
    if effect_direction == "beneficial":
        return "supported"
    if effect_direction in ("no_effect", "harmful"):
        return "refuted"
    return "uncertain"


def assemble_verdict(
    grade: GradeAssessment,
    crosscheck: OpenEvidenceCheck | None,
    plain_language_en: str = "",
    plain_language_lay_en: str = "",
) -> Verdict:
    """Build the final Verdict for a PICO from its GRADE + cross-check."""
    confidence = grade.final_certainty
    verdict = map_verdict(confidence, grade.effect_direction)
    dissent = ""

    if crosscheck is not None and crosscheck.agreement == "disagree":
        # External source contradicts us: lower confidence and soften the verdict.
        confidence = _downgrade_one(confidence)
        if verdict in ("supported", "refuted"):
            verdict = "uncertain"
        dissent = (
            "OpenEvidence reached a contrary conclusion. "
            f"{crosscheck.discrepancy_notes}".strip()
        )
    elif crosscheck is not None and crosscheck.agreement == "partial":
        dissent = crosscheck.discrepancy_notes

    return Verdict(
        pico_id=grade.pico_id,
        verdict=verdict,
        confidence=confidence,
        effect_direction=grade.effect_direction,
        plain_language_en=plain_language_en or grade.summary,
        plain_language_lay_en=plain_language_lay_en,
        crosscheck=crosscheck,
        grade=grade,
        dissent=dissent,
    )


def derive_overall(pico_results: list[PicoResult]) -> tuple[str, str]:
    """Synthesize a claim-level (verdict, certainty) from the per-PICO verdicts.

    Conservative rules:
      - certainty = the LOWEST certainty among adjudicated PICOs
      - verdict   = "refuted" if any PICO is refuted and none supported;
                    "supported" if all adjudicated PICOs are supported;
                    otherwise "uncertain"
    """
    verdicts = [r.verdict for r in pico_results if r.verdict is not None]
    if not verdicts:
        return "uncertain", "very_low"

    certainties = [v.confidence for v in verdicts]
    overall_certainty = min(certainties, key=lambda c: _LEVEL_INDEX.get(c, 0))

    labels = [v.verdict for v in verdicts]
    n_supported = labels.count("supported")
    n_refuted = labels.count("refuted")

    if n_supported == len(labels):
        overall = "supported"
    elif n_refuted > 0 and n_supported == 0:
        overall = "refuted"
    else:
        overall = "uncertain"

    return overall, overall_certainty
