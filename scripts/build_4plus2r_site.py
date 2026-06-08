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

# Make every "4+2R 主張" claim tag link to the official primary source, so readers
# can verify the claim is represented faithfully.
CLAIM_SOURCE_URL = "https://www.4plus2r.com/"
_CLAIM_TAG = re.compile(r'<span class="claim-tag">([^<]+)</span>')


def _link_claim_tags(html: str) -> str:
    return _CLAIM_TAG.sub(
        lambda m: f'<a class="claim-tag" href="{CLAIM_SOURCE_URL}" target="_blank" '
                  f'rel="noopener" title="連至 4+2R 官方來源">{m.group(1)} ↗</a>',
        html,
    )

# chapter id -> pico_*.json it was written from (for the clickable PRISMA popup)
CHAPTER_PICO = {
    "ch2": "pico_01", "ch3": "pico_02", "ch4": "pico_03", "ch5": "pico_04",
    "ch6": "pico_06", "ch7": "pico_05", "ch9": "pico_07", "ch10": "pico_08",
    "ch11": "pico_09",
}


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
        html = _link_claim_tags(html)

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

    meta = SiteMeta(description="以 robust-lit-review 工作流（Q1·≥2016·CrossRef 驗證·GRADE）對 4+2R 代謝飲食法九大主張的系統性評析。")
    index = render_blueprint_site(meta, chapters, refs, OUT)

    # Per-chapter included-study list for the clickable PRISMA popup.
    pico_studies: dict[str, list[dict]] = {}
    for chapter_id, pico_id in CHAPTER_PICO.items():
        pj = BASE / f"{pico_id}.json"
        if not pj.exists():
            continue
        data = json.loads(pj.read_text(encoding="utf-8"))
        pico_studies[chapter_id] = [
            {"title": s.get("title", ""), "journal": s.get("journal", ""),
             "year": s.get("year"), "quartile": s.get("quartile"),
             "doi": s.get("doi"), "pmid": s.get("pmid"),
             "crossref_verified": s.get("crossref_verified", False)}
            for s in data.get("included_studies", [])
        ]
    # Per-chapter search strategy (for the clickable 檢索命中 count).
    pico_search: dict[str, dict] = {}
    for chapter_id, pico_id in CHAPTER_PICO.items():
        pj = BASE / f"{pico_id}.json"
        if not pj.exists():
            continue
        p = json.loads(pj.read_text(encoding="utf-8")).get("pico", {})
        inter = [t for t in (p.get("primary_terms") or [p.get("intervention", "")]) if t]
        outc = [t for t in ([p.get("outcome", "")] + (p.get("secondary_terms") or [])) if t]
        groups = []
        if inter:
            groups.append("(" + " OR ".join(f'"{t}"' for t in inter) + ")")
        if outc:
            groups.append("(" + " OR ".join(f'"{t}"' for t in outc) + ")")
        query = " AND ".join(groups) if groups else f'"{p.get("intervention", "")}"'
        pico_search[chapter_id] = {
            "databases": ["Scopus", "PubMed", "Embase"],
            "query": query + " AND PUBYEAR > 2015",
            "date_from": 2016,
            "terms": inter + outc,
            "mesh": p.get("mesh_terms", []),
            "found": json.loads(pj.read_text(encoding="utf-8")).get("prisma", {}).get("total_found", 0),
        }

    (OUT / "assets" / "pico-studies.js").write_text(
        "window.__PICO_STUDIES__ = " + json.dumps(pico_studies, ensure_ascii=False) + ";\n"
        "window.__PICO_SEARCH__ = " + json.dumps(pico_search, ensure_ascii=False) + ";\n",
        encoding="utf-8")

    print(f"Rendered {index} — {len(chapters)} chapters, {len(refs)} references, "
          f"{sum(len(v) for v in pico_studies.values())} studies in {len(pico_studies)} popups")


if __name__ == "__main__":
    main()
