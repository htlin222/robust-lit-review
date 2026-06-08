"""Run the real per-PICO SR pipeline for the 4+2R claim appraisal.

Searches Scopus + PubMed + Embase, >= 2016, Q1-only (strict), DOI-validated and
CrossRef-verified, for the six core claims of the 4+2R metabolic diet. Saves each
PICO's included studies + PRISMA flow to output/4plus2r/.

Run: .venv/bin/python scripts/run_4plus2r.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from litreview.config import get_config
from litreview.models import PICOQuestion
from litreview.pipeline.claim_orchestrator import ClaimAppraisalPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_4plus2r")

OUT = Path("output/4plus2r")

# Six PICO sub-questions mapping the 4+2R branded claims to their mechanistic
# components (the branded program has no Q1 RCT, so we appraise the mechanisms).
PICOS = [
    PICOQuestion(
        pico_id="pico_01", outcome_domain="microbiome",
        population="adults with overweight or obesity",
        intervention="gut microbiota modulation (diet, probiotics)",
        comparator="control diet", outcome="body weight / adiposity",
        question_text="In adults with obesity, does modulating the gut microbiota cause weight loss beyond calorie restriction?",
        primary_terms=["gut microbiota", "gut microbiome", "probiotics"],
        secondary_terms=["obesity", "weight loss", "body weight"], priority=1),
    PICOQuestion(
        pico_id="pico_02", outcome_domain="high_protein",
        population="adults with overweight or obesity",
        intervention="energy-restricted high-protein diet",
        comparator="standard-protein diet", outcome="fat mass / lean mass / weight",
        question_text="In adults with obesity, does a high-protein diet improve weight and body composition vs standard protein?",
        primary_terms=["high-protein diet", "dietary protein", "protein intake"],
        secondary_terms=["weight loss", "fat mass", "body composition", "lean mass"], priority=2),
    PICOQuestion(
        pico_id="pico_03", outcome_domain="meal_order",
        population="adults with or at risk of type 2 diabetes",
        intervention="nutrient/food order (vegetables and protein before carbohydrate)",
        comparator="usual eating order", outcome="postprandial glucose / HbA1c",
        question_text="Does eating vegetables and protein before carbohydrate improve glycaemic outcomes?",
        primary_terms=["food order", "meal sequence", "nutrient order", "food sequence"],
        secondary_terms=["postprandial glucose", "glycemic", "type 2 diabetes"], priority=3),
    PICOQuestion(
        pico_id="pico_04", outcome_domain="setpoint_regain",
        population="adults who lost weight by caloric restriction",
        intervention="dietary weight loss",
        comparator="—", outcome="weight regain / metabolic adaptation",
        question_text="After diet-induced weight loss, can a 'metabolic reset' prevent weight regain and adaptive thermogenesis?",
        primary_terms=["weight regain", "metabolic adaptation", "adaptive thermogenesis", "weight loss maintenance"],
        secondary_terms=["obesity", "energy expenditure"], priority=4),
    PICOQuestion(
        pico_id="pico_05", outcome_domain="low_carb",
        population="adults with overweight or obesity",
        intervention="low-carbohydrate diet",
        comparator="balanced or low-fat diet", outcome="weight / cardiometabolic risk",
        question_text="Does a low-carbohydrate diet produce superior long-term weight and cardiometabolic outcomes?",
        primary_terms=["low-carbohydrate diet", "carbohydrate restriction", "ketogenic diet"],
        secondary_terms=["weight loss", "cardiometabolic", "body weight"], priority=5),
    PICOQuestion(
        pico_id="pico_06", outcome_domain="safety",
        population="adults on rapid or very-low-calorie weight-loss diets",
        intervention="very-low-calorie / rapid weight loss diet",
        comparator="gradual weight loss", outcome="gallstones / adverse events",
        question_text="Do rapid very-low-calorie weight-loss diets increase gallstones and other adverse events?",
        primary_terms=["very low calorie diet", "rapid weight loss", "very-low-energy diet"],
        secondary_terms=["gallstones", "cholelithiasis", "adverse effects", "cholecystectomy"], priority=6),
    PICOQuestion(
        pico_id="pico_07", outcome_domain="recomposition",
        population="adults in an energy deficit doing resistance training",
        intervention="high-protein diet plus resistance training",
        comparator="lower-protein or no resistance training",
        outcome="simultaneous fat loss and muscle/lean-mass gain (body recomposition)",
        question_text="Can adults simultaneously gain muscle and lose fat (body recomposition) during energy restriction with high protein and resistance training?",
        primary_terms=["body recomposition", "resistance training", "muscle hypertrophy", "lean body mass"],
        secondary_terms=["energy restriction", "fat loss", "dietary protein"], priority=7),
    PICOQuestion(
        pico_id="pico_08", outcome_domain="mental_health",
        population="adults with overweight/obesity or depressive symptoms",
        intervention="dietary intervention / diet quality / weight loss",
        comparator="usual diet", outcome="depression / mood / mental health",
        question_text="Do dietary interventions or diet-induced weight loss improve depression and mood?",
        primary_terms=["dietary intervention", "diet quality", "dietary pattern"],
        secondary_terms=["depression", "depressive symptoms", "mental health", "mood"], priority=8),
    PICOQuestion(
        pico_id="pico_09", outcome_domain="aging_longevity",
        population="adults",
        intervention="caloric restriction / time-restricted eating / dietary intervention",
        comparator="ad libitum diet", outcome="biological aging / healthspan / longevity markers",
        question_text="Does caloric restriction or dietary intervention slow biological aging or improve healthspan/longevity markers in humans?",
        primary_terms=["caloric restriction", "time-restricted eating", "dietary restriction"],
        secondary_terms=["aging", "longevity", "healthspan", "biological age"], priority=9),
]


def _study_dump(a):
    return {
        "citation_key": a.citation_key, "title": a.title, "authors": a.authors,
        "journal": a.journal, "year": a.year, "doi": a.doi, "pmid": a.pmid,
        "quartile": a.journal_quartile, "citescore": a.citescore,
        "citation_count": a.citation_count, "abstract": a.abstract,
        "crossref_verified": a.crossref_verified, "doi_validated": a.doi_validated,
        "is_open_access": a.is_open_access,
    }


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    config = get_config()
    config.max_results_per_db = 40
    config.min_year = 2016
    config.min_quartile = "Q1"

    async with ClaimAppraisalPipeline(config) as pipe:
        for pico in PICOS:
            out_path = OUT / f"{pico.pico_id}.json"
            if out_path.exists():
                log.info("skip %s (already done)", pico.pico_id)
                continue
            log.info("=== %s (%s) ===", pico.pico_id, pico.outcome_domain)
            try:
                included, flow = await pipe.run_pico_search(pico)
            except Exception:
                log.exception("PICO %s failed", pico.pico_id)
                continue
            payload = {
                "pico": pico.model_dump(),
                "prisma": flow.model_dump(),
                "included_studies": [_study_dump(a) for a in included],
            }
            (OUT / f"{pico.pico_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("%s -> %d included (found=%d Q1=%d crossref=%d)",
                     pico.pico_id, flow.included, flow.total_found,
                     flow.after_quality_filter, flow.after_crossref)

    log.info("DONE — results in %s", OUT)


if __name__ == "__main__":
    asyncio.run(main())
