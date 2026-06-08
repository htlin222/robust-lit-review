"""Phase 2 tests: single-PICO thin slice (claim_orchestrator).

The DB search is stubbed so the test runs offline; it exercises the
dedup -> year -> Q1(strict) -> validate counting that populates PicoPrismaFlow.
"""

from __future__ import annotations

import litreview.pipeline.claim_orchestrator as co
from litreview.config import Config
from litreview.models import ArticleMetadata, PICOQuestion
from litreview.pipeline.claim_orchestrator import ClaimAppraisalPipeline
from litreview.pipeline.orchestrator import LitReviewPipeline


def _art(title, doi, year, citescore, abstract=""):
    # No ISSN -> OpenAlex lookup skipped; CiteScore drives the quartile fallback.
    return ArticleMetadata(title=title, doi=doi, year=year, citescore=citescore, abstract=abstract)


async def _stub_crossref_all_verified(articles, mailto="", concurrency=8):
    # Offline stub: mark every DOI-bearing article as confirmed in CrossRef.
    for a in articles:
        if a.doi:
            a.crossref_verified = True
            a.crossref_title_match = 1.0
    return articles


def _canned_corpus():
    return [
        _art("A q1 recent", "10.1/a", 2020, 15.0, abstract="long abstract here"),
        _art("A duplicate", "10.1/a", 2020, 15.0, abstract="short"),   # dup DOI of A
        _art("C too old", "10.1/c", 2010, 15.0),                        # dropped by year
        _art("D unranked", "10.1/d", 2020, None),                       # dropped by strict Q1
        _art("E q1 recent", "10.1/e", 2020, 15.0),                      # survives
    ]


async def test_run_pico_search_prisma_counts(monkeypatch):
    monkeypatch.setattr(co, "batch_verify_crossref", _stub_crossref_all_verified)
    config = Config(unpaywall_email="")  # no Unpaywall -> validation gate skipped, all kept
    pipe = ClaimAppraisalPipeline(config)
    # Compose a non-entered LitReviewPipeline (clients are None); stub the search.
    inner = LitReviewPipeline(config)
    pipe._pipeline = inner

    async def fake_search(queries):
        return _canned_corpus()

    inner.search_all_databases = fake_search  # type: ignore[assignment]

    pico = PICOQuestion(
        pico_id="pico_01",
        intervention="4+2R diet",
        outcome="weight loss",
        primary_terms=["4+2R diet", "metabolic diet"],
    )
    included, flow = await pipe.run_pico_search(pico)

    assert flow.total_found == 5
    assert flow.after_dedup == 4            # A, C, D, E
    assert flow.after_year_filter == 3      # A, D, E (C dropped: 2010)
    assert flow.excluded_by_year == 1
    assert flow.after_quality_filter == 2   # A, E (D dropped: Unknown quartile)
    assert flow.excluded_by_quality == 1
    assert flow.after_validation == 2       # no Unpaywall gate
    assert flow.after_crossref == 2         # both confirmed by stubbed CrossRef
    assert flow.excluded_by_crossref == 0
    assert flow.included == 2
    assert {a.title for a in included} == {"A q1 recent", "E q1 recent"}


async def test_run_pico_search_drops_crossref_unconfirmed(monkeypatch):
    # CrossRef confirms only "A q1 recent" -> the other Q1 study is dropped as
    # a possible hallucination.
    async def stub(articles, mailto="", concurrency=8):
        for a in articles:
            a.crossref_verified = a.title == "A q1 recent"
            a.crossref_title_match = 1.0 if a.crossref_verified else 0.0
        return articles

    monkeypatch.setattr(co, "batch_verify_crossref", stub)
    config = Config(unpaywall_email="")
    pipe = ClaimAppraisalPipeline(config)
    inner = LitReviewPipeline(config)
    pipe._pipeline = inner
    inner.search_all_databases = lambda queries: _async_return(_canned_corpus())  # type: ignore[assignment]

    pico = PICOQuestion(pico_id="pico_01", intervention="4+2R diet", outcome="weight loss",
                        primary_terms=["4+2R diet"])
    included, flow = await pipe.run_pico_search(pico)
    assert flow.after_crossref == 1
    assert flow.excluded_by_crossref == 1
    assert {a.title for a in included} == {"A q1 recent"}


async def _async_return(value):
    return value


async def test_run_pico_builds_result_and_audit_trail(monkeypatch):
    monkeypatch.setattr(co, "batch_verify_crossref", _stub_crossref_all_verified)
    config = Config(unpaywall_email="")
    pipe = ClaimAppraisalPipeline(config)
    inner = LitReviewPipeline(config)
    pipe._pipeline = inner

    async def fake_search(queries):
        return _canned_corpus()

    inner.search_all_databases = fake_search  # type: ignore[assignment]

    pico = PICOQuestion(pico_id="pico_01", intervention="4+2R diet", outcome="weight loss",
                        primary_terms=["4+2R diet"])
    result = await pipe.run_pico(pico)

    assert result.question.pico_id == "pico_01"
    assert result.prisma.included == 2
    assert len(result.search_queries) == 1
    assert result.search_queries[0].date_from == 2016
    assert [step["stage"] for step in result.audit_trail] == [
        "search", "dedup", "year_filter", "quality_filter", "validation", "crossref",
    ]


def test_build_pico_queries_combines_intervention_and_outcome():
    pipe = ClaimAppraisalPipeline(Config())
    pico = PICOQuestion(intervention="4+2R diet", outcome="HbA1c",
                        primary_terms=["4+2R diet", "meal replacement"])
    queries = pipe.build_pico_queries(pico)
    assert len(queries) == 1
    bq = queries[0].boolean_query
    assert '"4+2R diet"' in bq and '"meal replacement"' in bq
    assert '"HbA1c"' in bq
    assert " AND " in bq
    assert queries[0].date_from == 2016
