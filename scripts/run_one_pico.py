"""Run the Q1/>=2016/CrossRef SR pipeline for ONE PICO (used by the workflow agents).

The dynamic workflow (.claude/workflows/claim-appraise.js) cannot run shell itself,
so each per-PICO search agent calls this:

    .venv/bin/python scripts/run_one_pico.py <slug> <pico_id>

Reads output/<slug>/picos.json (a list of PICOQuestion dicts approved in Phase A),
runs the per-PICO pipeline, and writes output/<slug>/<pico_id>.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from litreview.config import get_config
from litreview.models import PICOQuestion
from litreview.pipeline.claim_orchestrator import ClaimAppraisalPipeline


def _study_dump(a) -> dict:
    return {
        "citation_key": a.citation_key, "title": a.title, "authors": a.authors,
        "journal": a.journal, "year": a.year, "doi": a.doi, "pmid": a.pmid,
        "quartile": a.journal_quartile, "citescore": a.citescore,
        "citation_count": a.citation_count, "abstract": a.abstract,
        "crossref_verified": a.crossref_verified, "doi_validated": a.doi_validated,
        "is_open_access": a.is_open_access,
    }


async def _run(slug: str, pico_id: str) -> None:
    base = Path("output") / slug
    picos = json.loads((base / "picos.json").read_text(encoding="utf-8"))
    spec = next((p for p in picos if p.get("pico_id") == pico_id), None)
    if spec is None:
        raise SystemExit(f"PICO {pico_id} not found in {base/'picos.json'}")

    pico = PICOQuestion(**spec)
    cfg = get_config()
    cfg.max_results_per_db = 40
    cfg.min_year = 2016
    cfg.min_quartile = "Q1"

    async with ClaimAppraisalPipeline(cfg) as pipe:
        included, flow = await pipe.run_pico_search(pico)

    payload = {
        "pico": pico.model_dump(),
        "prisma": flow.model_dump(),
        "included_studies": [_study_dump(a) for a in included],
    }
    (base / f"{pico_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{pico_id}: found={flow.total_found} Q1={flow.after_quality_filter} "
          f"crossref={flow.after_crossref} included={flow.included}")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: run_one_pico.py <slug> <pico_id>")
    asyncio.run(_run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
