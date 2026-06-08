"""Phase 1 tests: year >= 2016 and strict Q1-only filters."""

from __future__ import annotations

from litreview.models import ArticleMetadata
from litreview.pipeline.filters import filter_by_year
from litreview.pipeline.journal_quality import assess_journal_quality
from litreview.utils.crossref import filter_crossref_verified, title_similarity


def _article(title: str, year: int | None = None, citescore: float | None = None) -> ArticleMetadata:
    # No ISSN -> the OpenAlex lookup is skipped, so these tests run offline.
    return ArticleMetadata(title=title, year=year, citescore=citescore)


def test_filter_by_year_keeps_2016_and_later():
    articles = [
        _article("old", year=2015),
        _article("boundary", year=2016),
        _article("recent", year=2020),
        _article("undated", year=None),
    ]
    kept, dropped = filter_by_year(articles, min_year=2016)

    kept_titles = {a.title for a in kept}
    dropped_titles = {a.title for a in dropped}
    assert kept_titles == {"boundary", "recent"}
    # 2015 is too old; undated cannot be confirmed and is dropped under the strict regime.
    assert dropped_titles == {"old", "undated"}


def test_filter_by_year_respects_max_year():
    articles = [_article("a", year=2016), _article("b", year=2030)]
    kept, dropped = filter_by_year(articles, min_year=2016, max_year=2026)
    assert {a.title for a in kept} == {"a"}
    assert {a.title for a in dropped} == {"b"}


async def test_assess_quality_strict_drops_unknown():
    # citescore>=10 resolves to Q1 via the CiteScore fallback; None -> Unknown.
    q1 = _article("q1-journal", year=2020, citescore=15.0)
    unknown = _article("unranked-journal", year=2020, citescore=None)

    strict = await assess_journal_quality([q1, unknown], min_quartile="Q1", strict=True)
    assert {a.title for a in strict} == {"q1-journal"}


async def test_assess_quality_lenient_keeps_unknown():
    q1 = _article("q1-journal", year=2020, citescore=15.0)
    unknown = _article("unranked-journal", year=2020, citescore=None)

    lenient = await assess_journal_quality([q1, unknown], min_quartile="Q1", strict=False)
    assert {a.title for a in lenient} == {"q1-journal", "unranked-journal"}


def test_title_similarity():
    assert title_similarity("Effect of diet on weight", "Effect of diet on weight") == 1.0
    assert title_similarity("", "anything") == 0.0
    assert 0.0 < title_similarity("diet and weight loss", "weight loss and diet") <= 1.0


def test_filter_crossref_verified_existence_gate():
    confirmed = ArticleMetadata(title="real", doi="10.1/a", crossref_verified=True, crossref_title_match=1.0)
    fabricated = ArticleMetadata(title="fake", doi="10.1/x", crossref_verified=False)
    no_doi = ArticleMetadata(title="nodoi", crossref_verified=False)

    kept, dropped = filter_crossref_verified([confirmed, fabricated, no_doi])
    assert [a.title for a in kept] == ["real"]
    assert {a.title for a in dropped} == {"fake", "nodoi"}


def test_filter_crossref_verified_title_match_threshold():
    wrong_paper = ArticleMetadata(title="x", doi="10.1/a", crossref_verified=True, crossref_title_match=0.1)
    kept, dropped = filter_crossref_verified([wrong_paper], min_title_match=0.5)
    assert kept == []
    assert len(dropped) == 1
