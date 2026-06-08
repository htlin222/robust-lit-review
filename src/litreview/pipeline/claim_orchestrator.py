"""Claim-appraisal orchestrator: claim -> N PICO -> per-PICO SR.

This composes the existing :class:`LitReviewPipeline` as a per-PICO worker so
the deterministic API work (search -> dedup -> year -> Q1 -> validate) is reused
verbatim. The LLM/MCP steps (claim decomposition, semantic screening, GRADE,
OpenEvidence cross-check) are dispatched by the ``/lit-review`` SKILL agent via
the SubagentTask contract and collected back here — Python never calls an LLM or
MCP tool directly.

Phase 2 implements the non-LLM thin slice: ``run_pico_search`` takes one PICO
and produces its included-study set plus a populated ``PicoPrismaFlow``.
"""

from __future__ import annotations

import logging

from pathlib import Path

from litreview.config import Config, get_config
from litreview.models import (
    ArticleMetadata,
    ClaimAppraisal,
    PicoPrismaFlow,
    PICOQuestion,
    PicoResult,
    SearchQuery,
)
from litreview.pipeline import claim_decomposer, crosscheck, grade_judge
from litreview.pipeline.filters import filter_by_year
from litreview.pipeline.journal_quality import assess_journal_quality
from litreview.pipeline.orchestrator import LitReviewPipeline
from litreview.pipeline.verdict_builder import assemble_verdict, derive_overall
from litreview.utils.crossref import batch_verify_crossref, filter_crossref_verified

logger = logging.getLogger(__name__)


class ClaimAppraisalPipeline:
    """Run a claim appraisal by fanning out one SR pipeline per PICO question."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or get_config()
        self._pipeline: LitReviewPipeline | None = None

    async def __aenter__(self) -> ClaimAppraisalPipeline:
        # Reuse the existing pipeline's client lifecycle verbatim.
        self._pipeline = await LitReviewPipeline(self.config).__aenter__()
        return self

    async def __aexit__(self, *args) -> None:  # noqa: ANN002
        if self._pipeline is not None:
            await self._pipeline.__aexit__(*args)

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

    def build_pico_queries(self, pico: PICOQuestion) -> list[SearchQuery]:
        """Build a Boolean search query for one PICO sub-question.

        Combines the intervention/primary terms with the outcome terms as an
        AND of OR-groups, and carries ``date_from=min_year`` so the date bound
        is applied at query time (a post-filter enforces it authoritatively).
        """
        intervention_terms = pico.primary_terms or [pico.intervention]
        intervention_terms = [t for t in intervention_terms if t]
        outcome_terms = [t for t in ([pico.outcome] + pico.secondary_terms) if t]

        groups: list[str] = []
        if intervention_terms:
            groups.append("(" + " OR ".join(f'"{t}"' for t in intervention_terms) + ")")
        if outcome_terms:
            groups.append("(" + " OR ".join(f'"{t}"' for t in outcome_terms) + ")")
        boolean_query = " AND ".join(groups) if groups else f'"{pico.intervention}"'

        query = SearchQuery(
            topic=pico.question_text or pico.outcome_domain or pico.intervention,
            primary_terms=intervention_terms,
            secondary_terms=outcome_terms,
            mesh_terms=pico.mesh_terms,
            boolean_query=boolean_query,
            date_from=self.config.min_year,
            date_to=None,
        )
        return [query]

    # ------------------------------------------------------------------
    # Per-PICO deterministic pipeline (no LLM)
    # ------------------------------------------------------------------

    async def run_pico_search(
        self, pico: PICOQuestion
    ) -> tuple[list[ArticleMetadata], PicoPrismaFlow]:
        """Search -> dedup -> year(>=min_year) -> Q1-only(strict) -> validate.

        Returns the surviving studies and a fully-populated PRISMA flow. This is
        the authoritative count source for the PICO's PRISMA diagram. Semantic
        screening (Phase 4) narrows ``included`` further; until then the
        validated set is treated as provisionally included.
        """
        if self._pipeline is None:
            raise RuntimeError("ClaimAppraisalPipeline must be used as an async context manager")
        p = self._pipeline
        flow = PicoPrismaFlow()

        queries = self.build_pico_queries(pico)

        # Stage: search all databases (date bound applied at query time)
        articles = await p.search_all_databases(queries)
        flow.total_found = len(articles)

        # Stage: dedup by DOI
        deduped = p.deduplicate(articles)
        flow.after_dedup = len(deduped)

        # Stage: year >= min_year (authoritative post-filter)
        kept_year, dropped_year = filter_by_year(deduped, self.config.min_year)
        flow.after_year_filter = len(kept_year)
        flow.excluded_by_year = len(dropped_year)

        # Stage: Q1-only, strict (drop Unknown quartiles)
        q1 = await assess_journal_quality(
            kept_year,
            email=self.config.unpaywall_email,
            min_quartile=self.config.min_quartile,
            strict=True,
        )
        flow.after_quality_filter = len(q1)
        flow.excluded_by_quality = len(kept_year) - len(q1)

        # Stage: DOI validation + OA enrichment
        validated = await p.validate_and_enrich(q1)
        if p._unpaywall is not None:
            # With Unpaywall configured, require a resolved DOI (or no DOI at all).
            valid = [a for a in validated if a.doi_validated or not a.doi]
        else:
            # Cannot validate without Unpaywall — keep all and flag in logs.
            logger.warning("Unpaywall not configured; skipping DOI-validation gate for PICO %s", pico.pico_id)
            valid = validated
        flow.after_validation = len(valid)

        # Stage: CrossRef existence gate (anti-hallucination) — every retained
        # work MUST be confirmed to exist in CrossRef. Records without a DOI
        # cannot be confirmed and are dropped here.
        await batch_verify_crossref(valid, mailto=self.config.unpaywall_email)
        confirmed, unconfirmed = filter_crossref_verified(valid)
        flow.after_crossref = len(confirmed)
        flow.excluded_by_crossref = len(unconfirmed)
        if unconfirmed:
            logger.warning(
                "CrossRef dropped %d unconfirmed record(s) for PICO %s",
                len(unconfirmed), pico.pico_id,
            )

        # Provisional inclusion (refined by semantic screening in Phase 4)
        flow.included = len(confirmed)

        logger.info(
            "PICO %s flow: found=%d dedup=%d year>=%d=%d Q1=%d validated=%d crossref=%d",
            pico.pico_id, flow.total_found, flow.after_dedup, self.config.min_year,
            flow.after_year_filter, flow.after_quality_filter, flow.after_validation,
            flow.after_crossref,
        )
        return confirmed, flow

    async def run_pico(self, pico: PICOQuestion) -> PicoResult:
        """Run the deterministic per-PICO pipeline and assemble a PicoResult.

        GRADE/verdict are left ``None`` here; they are attached in later phases
        once the SKILL agent has dispatched the GRADE and cross-check subagents.
        """
        included, flow = await self.run_pico_search(pico)
        queries = self.build_pico_queries(pico)
        audit = [
            {"stage": "search", "count": flow.total_found},
            {"stage": "dedup", "count": flow.after_dedup},
            {"stage": "year_filter", "count": flow.after_year_filter, "excluded": flow.excluded_by_year},
            {"stage": "quality_filter", "count": flow.after_quality_filter, "excluded": flow.excluded_by_quality},
            {"stage": "validation", "count": flow.after_validation},
            {"stage": "crossref", "count": flow.after_crossref, "excluded": flow.excluded_by_crossref},
        ]
        return PicoResult(
            question=pico,
            search_queries=queries,
            prisma=flow,
            included_studies=included,
            audit_trail=audit,
        )

    # ------------------------------------------------------------------
    # LLM-phase task delegators (dispatched by the /lit-review SKILL agent)
    # ------------------------------------------------------------------

    def decomposition_task(self, claim: str, output_dir: Path, max_picos: int = 6):
        """SubagentTask that decomposes *claim* into PICO questions."""
        return claim_decomposer.generate_decomposition_task(claim, output_dir, max_picos)

    def collect_picos(self, claim: str, output_dir: Path) -> list[PICOQuestion]:
        return claim_decomposer.collect_picos(claim, output_dir)

    def grade_task(self, pico, included_studies, extracted, output_dir: Path):
        return grade_judge.generate_grade_task(pico, included_studies, extracted, output_dir)

    def collect_grade(self, pico, output_dir: Path):
        return grade_judge.collect_grade(pico, output_dir)

    def crosscheck_task(self, pico, included_studies, draft_verdict: str, output_dir: Path):
        return crosscheck.generate_crosscheck_task(pico, included_studies, draft_verdict, output_dir)

    def collect_crosscheck(self, pico, output_dir: Path):
        return crosscheck.collect_crosscheck(pico, output_dir)

    # ------------------------------------------------------------------
    # Verdict + claim-level assembly (pure)
    # ------------------------------------------------------------------

    def build_pico_verdict(self, pico_result: PicoResult, output_dir: Path) -> PicoResult:
        """Attach GRADE + cross-check + Verdict to a PicoResult by collecting
        the subagent outputs the SKILL has produced for this PICO."""
        grade = grade_judge.collect_grade(pico_result.question, output_dir)
        check = crosscheck.collect_crosscheck(pico_result.question, output_dir)
        verdict = assemble_verdict(grade, check)
        pico_result.grade = grade
        pico_result.verdict = verdict
        pico_result.audit_trail.append(
            {"stage": "grade", "certainty": grade.final_certainty, "effect": grade.effect_direction}
        )
        pico_result.audit_trail.append(
            {"stage": "verdict", "verdict": verdict.verdict, "oe_agreement": check.agreement}
        )
        return pico_result

    def assemble_appraisal(self, claim: str, pico_results: list[PicoResult]) -> ClaimAppraisal:
        """Roll per-PICO verdicts up into a ClaimAppraisal (the render contract)."""
        overall_verdict, overall_certainty = derive_overall(pico_results)
        return ClaimAppraisal(
            claim=claim,
            pico_results=pico_results,
            overall_verdict=overall_verdict,
            overall_certainty=overall_certainty,
            filters_applied={
                "min_year": self.config.min_year,
                "min_quartile": self.config.min_quartile,
            },
        )
