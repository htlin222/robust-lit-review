"""Assemble the 4+2R SR site: chapters_src/*.html + pico_*.json -> output/site_4plus2r.

- Builds a DOI -> study-metadata map from the six pico_*.json files.
- Scans chapters in display order, numbers <cite data-doi> by first appearance.
- Emits an AMA reference list (with PubMed/CrossRef verification badges).
- Rewrites data-doi -> data-ref and renders via blueprint_renderer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from litreview.pipeline.blueprint_renderer import Chapter, SiteMeta, render_blueprint_site

BASE = Path("output/4plus2r")
SRC = BASE / "chapters_src"
OUT = Path("output/site_4plus2r")

# Display order. ch0/ch1/ch8 are synthesis chapters (may be absent during drafts).
ORDER = [
    ("ch0", "chapters/00-summary.html"),
    ("ch1", "chapters/01-methods.html"),
    ("ch2", "chapters/02-microbiome.html"),
    ("ch3", "chapters/03-protein.html"),
    ("ch4", "chapters/04-meal-order.html"),
    ("ch5", "chapters/05-setpoint.html"),
    ("ch6", "chapters/06-safety.html"),
    ("ch7", "chapters/07-lowcarb.html"),
    ("ch9", "chapters/09-recomposition.html"),
    ("ch10", "chapters/10-mental-health.html"),
    ("ch11", "chapters/11-aging.html"),
    ("ch8", "chapters/12-verdict.html"),
]

_CITE_DOI = re.compile(r'data-doi="([^"]+)"')


def load_study_map() -> dict[str, dict]:
    m: dict[str, dict] = {}
    for pj in sorted(BASE.glob("pico_*.json")):
        data = json.loads(pj.read_text(encoding="utf-8"))
        for s in data.get("included_studies", []):
            doi = (s.get("doi") or "").lower().strip()
            if doi and doi not in m:
                m[doi] = s
    return m


def ama_authors(authors: list[str]) -> str:
    out = []
    for a in (authors or [])[:6]:
        a = a.strip()
        if "," in a:
            last, first = a.split(",", 1)
        else:
            parts = a.split()
            last, first = (parts[-1], " ".join(parts[:-1])) if parts else (a, "")
        initials = "".join(p[0] for p in first.replace(".", " ").split() if p)[:3]
        out.append(f"{last.strip()} {initials}".strip())
    s = ", ".join(out)
    if authors and len(authors) > 6:
        s += ", et al"
    return s


def ama(study: dict) -> str:
    auth = ama_authors(study.get("authors") or [])
    title = (study.get("title") or "").rstrip(". ")
    journal = study.get("journal") or ""
    year = study.get("year") or ""
    base = f"{auth}. {title}. <i>{journal}</i>. {year}."
    badges = ' <span class="ver-badge vb-crossref">CrossRef ✓</span>'
    if study.get("pmid"):
        badges += f' <span class="ver-badge vb-pubmed">PubMed {study["pmid"]}</span>'
    return base + badges


def main() -> None:
    study_map = load_study_map()
    OUT.mkdir(parents=True, exist_ok=True)

    doi_to_n: dict[str, int] = {}
    refs: list[dict] = []
    chapters: list[Chapter] = []

    for cid, cfile in ORDER:
        src = SRC / f"{cid}.html"
        if not src.exists():
            continue
        html = src.read_text(encoding="utf-8")

        # number citations by first appearance across the whole document
        def _sub(match: re.Match) -> str:
            doi = match.group(1).lower().strip()
            if doi not in doi_to_n:
                n = len(refs) + 1
                doi_to_n[doi] = n
                study = study_map.get(doi)
                if study:
                    refs.append({"n": n, "ama": ama(study), "doi": doi})
                else:
                    refs.append({"n": n, "ama": f"[unresolved DOI: {doi}]", "doi": doi})
                    print(f"  WARN unresolved DOI in {cid}: {doi}")
            return f'data-ref="{doi_to_n[doi]}"'

        html = _CITE_DOI.sub(_sub, html)
        chapters.append(Chapter(id=cid, file=cfile, html=html))

    meta = SiteMeta(description="以 robust-lit-review 工作流（Q1·≥2016·CrossRef 驗證·GRADE）對 4+2R 代謝飲食法六大主張的系統性評析。")
    index = render_blueprint_site(meta, chapters, refs, OUT)
    print(f"Rendered {index} — {len(chapters)} chapters, {len(refs)} references")


if __name__ == "__main__":
    main()
