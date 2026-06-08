"""Phase 7 tests: appraisal.json -> verdict-style static site."""

from __future__ import annotations

from pathlib import Path

import pytest

from litreview.pipeline.prisma_svg import build_prisma_svg
from litreview.pipeline.site_renderer import render_site

FIXTURE = Path(__file__).parent / "fixtures" / "appraisal.sample.json"


def test_build_prisma_svg_has_counts_and_bilingual_labels():
    svg = build_prisma_svg({"identification": 312, "screening": 240, "eligibility": 31,
                            "included": 6, "excluded": {"screening": 209}})
    assert svg.startswith("<svg")
    assert "n = 312" in svg and "n = 6" in svg
    assert 'data-lang="zh"' in svg and 'data-lang="en"' in svg
    assert "n = 209" in svg  # exclusion side-box


def test_render_site_produces_index_and_assets(tmp_path):
    out = tmp_path / "site"
    index = render_site(FIXTURE, out)

    assert index.exists()
    html = index.read_text(encoding="utf-8")
    # claim + verdict
    assert "metabolic health" in html
    assert "verdict-uncertain" in html
    # all four writeup variants present in the DOM (dual toggle)
    assert html.count('class="writeup"') == 4
    # badges / verification surfaced
    assert "PubMed ✓" in html and "CrossRef ✓" in html
    # PRISMA svg inlined (not escaped)
    assert "<svg" in html and "prisma-flow" in html
    # assets copied + CF headers written
    assert (out / "assets" / "verdict.css").exists()
    assert (out / "assets" / "toggles.js").exists()
    assert (out / "_headers").exists()


def test_render_site_rejects_incomplete_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"claim": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        render_site(bad, tmp_path / "site")
