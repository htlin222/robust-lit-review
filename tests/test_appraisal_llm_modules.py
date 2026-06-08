"""Phases 3-6 tests: decomposition, GRADE arithmetic, verdict logic, cross-check."""

from __future__ import annotations

import json

from litreview.models import (
    GradeAssessment,
    OpenEvidenceCheck,
    PICOQuestion,
    PicoResult,
    Verdict,
)
from litreview.pipeline.claim_decomposer import collect_picos
from litreview.pipeline.crosscheck import collect_crosscheck
from litreview.pipeline.grade_judge import collect_grade, compute_final_certainty
from litreview.pipeline.verdict_builder import assemble_verdict, derive_overall, map_verdict


# --------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------

def test_collect_picos_assigns_ids_and_merges_domains(tmp_path):
    payload = [
        {"intervention": "diet", "outcome": "weight", "outcome_domain": "weight_loss", "priority": 2},
        {"intervention": "diet", "outcome": "HbA1c", "outcome_domain": "glycemic_control", "priority": 1},
        # duplicate domain, worse priority -> should be dropped in favor of priority 2 above
        {"intervention": "diet", "outcome": "BMI", "outcome_domain": "weight_loss", "priority": 5},
    ]
    (tmp_path / "pico_decomposition.json").write_text(json.dumps(payload), encoding="utf-8")

    picos = collect_picos("the diet works", tmp_path)

    assert len(picos) == 2  # weight_loss + glycemic_control (BMI duplicate merged out)
    # Sorted by priority: glycemic_control (1) first, then weight_loss (2)
    assert [p.pico_id for p in picos] == ["pico_01", "pico_02"]
    assert picos[0].outcome_domain == "glycemic_control"
    assert picos[1].outcome == "weight"  # the priority-2 weight entry, not the priority-5 BMI one


def test_collect_picos_missing_file_returns_empty(tmp_path):
    assert collect_picos("x", tmp_path) == []


# --------------------------------------------------------------------------
# GRADE arithmetic
# --------------------------------------------------------------------------

def test_compute_final_certainty_clamps():
    assert compute_final_certainty("high", 0) == "high"
    assert compute_final_certainty("high", -2) == "low"
    assert compute_final_certainty("high", -5) == "very_low"   # clamped
    assert compute_final_certainty("low", +1) == "moderate"
    assert compute_final_certainty("high", +3) == "high"        # clamped


def test_collect_grade_recomputes_certainty_ignoring_llm_label(tmp_path):
    payload = {
        "starting_level": "high",
        "domains": [
            {"name": "risk_of_bias", "rating": "serious", "downgrade": -1, "justification": "unblinded"},
            {"name": "imprecision", "rating": "serious", "downgrade": -1, "justification": "small n"},
        ],
        "effect_direction": "beneficial",
        "final_certainty": "high",   # LLM is WRONG; deterministic recompute must override
        "n_studies": 4, "n_rct": 2, "summary": "ok",
    }
    pico = PICOQuestion(pico_id="pico_01")
    (tmp_path / "grade_pico_01.json").write_text(json.dumps(payload), encoding="utf-8")

    grade = collect_grade(pico, tmp_path)
    assert grade.final_certainty == "low"   # high - 2 downgrades
    assert grade.effect_direction == "beneficial"
    assert len(grade.domains) == 2


def test_collect_grade_clamps_runaway_downgrade(tmp_path):
    payload = {
        "starting_level": "high",
        "domains": [{"name": "risk_of_bias", "rating": "very_serious", "downgrade": -9}],
        "effect_direction": "beneficial",
    }
    pico = PICOQuestion(pico_id="pico_02")
    (tmp_path / "grade_pico_02.json").write_text(json.dumps(payload), encoding="utf-8")
    grade = collect_grade(pico, tmp_path)
    # A single domain can drop at most 2 levels: high -> low
    assert grade.final_certainty == "low"


# --------------------------------------------------------------------------
# Verdict mapping + OE override
# --------------------------------------------------------------------------

def test_map_verdict():
    assert map_verdict("high", "beneficial") == "supported"
    assert map_verdict("moderate", "beneficial") == "supported"
    assert map_verdict("high", "no_effect") == "refuted"
    assert map_verdict("high", "harmful") == "refuted"
    assert map_verdict("low", "beneficial") == "uncertain"
    assert map_verdict("moderate", "mixed") == "uncertain"


def test_assemble_verdict_openevidence_disagree_softens():
    grade = GradeAssessment(pico_id="pico_01", final_certainty="moderate", effect_direction="beneficial")
    check = OpenEvidenceCheck(pico_id="pico_01", agreement="disagree", discrepancy_notes="OE says no benefit")

    v = assemble_verdict(grade, check)
    assert v.verdict == "uncertain"        # softened from supported
    assert v.confidence == "low"           # moderate downgraded one level
    assert "OpenEvidence" in v.dissent


def test_assemble_verdict_agree_keeps_supported():
    grade = GradeAssessment(pico_id="pico_01", final_certainty="high", effect_direction="beneficial")
    check = OpenEvidenceCheck(pico_id="pico_01", agreement="agree")
    v = assemble_verdict(grade, check)
    assert v.verdict == "supported"
    assert v.confidence == "high"
    assert v.dissent == ""


def test_derive_overall_conservative_rollup():
    def _result(verdict, confidence):
        return PicoResult(
            question=PICOQuestion(pico_id="p"),
            verdict=Verdict(verdict=verdict, confidence=confidence),
        )

    supported_all = [_result("supported", "high"), _result("supported", "moderate")]
    overall, certainty = derive_overall(supported_all)
    assert overall == "supported"
    assert certainty == "moderate"   # lowest certainty wins

    mixed = [_result("supported", "high"), _result("refuted", "low")]
    overall, certainty = derive_overall(mixed)
    assert overall == "uncertain"
    assert certainty == "low"

    refuted = [_result("refuted", "high"), _result("uncertain", "low")]
    overall, _ = derive_overall(refuted)
    assert overall == "refuted"


# --------------------------------------------------------------------------
# Cross-check
# --------------------------------------------------------------------------

def test_collect_crosscheck_missing_is_no_data(tmp_path):
    pico = PICOQuestion(pico_id="pico_01", outcome="weight")
    check = collect_crosscheck(pico, tmp_path)
    assert check.agreement == "no_data"
    assert check.pico_id == "pico_01"


def test_collect_crosscheck_parses_and_validates_agreement(tmp_path):
    payload = {
        "pico_id": "pico_01", "question_asked": "does it work?",
        "oe_article_id": "abc-123", "oe_verdict_text": "modest benefit",
        "oe_citations": ["10.1/x"], "agreement": "nonsense-value",
        "discrepancy_notes": "n",
    }
    (tmp_path / "crosscheck_pico_01.json").write_text(json.dumps(payload), encoding="utf-8")
    pico = PICOQuestion(pico_id="pico_01")
    check = collect_crosscheck(pico, tmp_path)
    assert check.agreement == "no_data"   # invalid value coerced
    assert check.oe_article_id == "abc-123"
    assert check.oe_citations == ["10.1/x"]
