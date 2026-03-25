# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-25

### Added

- **Human-in-the-Loop mode** (`--hitl`): 9 checkpoints where pipeline pauses for human judgment — search strategy approval, borderline article review, final article set, thematic grouping, key claims verification, PRISMA audit, cover letter, final preview, publish decision. Multiple-choice format, defaults for auto-mode, logged to `checkpoint_log.json`
- **Full pipeline**: Topic to submission-ready manuscript in one command
- **Multi-database search**: Parallel search across Scopus, PubMed, and Embase APIs
- **API clients**: `ScopusClient`, `PubMedClient`, `EmbaseClient`, `UnpaywallClient`, `ZoteroClient`
- **DOI validation**: 100% validation via doi.org handle API
- **Abstract fetching**: Full abstracts via PubMed DOI lookup and Scopus Abstract Retrieval API
- **Structured data extraction**: Haiku subagent extraction of sample sizes, p-values, dosing, thresholds, diagnostic accuracy from abstracts (replaces regex)
- **Balanced subtopic selection**: `ensure_balanced_coverage()` guarantees minimum articles per subtopic across 16 categories (epidemiology, pathogenesis, diagnosis, genetics, treatment, prognosis, etc.)
- **Modular parallel writing**: 8 section files written by independent subagents via Quarto `{{< include >}}` architecture
- **Section dispatcher**: `section_dispatcher.py` splits enriched articles by subtopic and generates per-section context for writing agents
- **PRISMA 2020 flow diagram**: Professional TikZ-rendered figure using [ezefranca/prisma-flow-diagram](https://github.com/ezefranca/prisma-flow-diagram)
- **PRISMA 2020 checklist**: Auto-generated 27-item checklist as manuscript appendix
- **PRISMA 2020 audit loop**: `prisma_audit.py` checks all 27 items against manuscript content, generates targeted fix instructions, dispatches repair agents until all pass
- **LLM-as-judge audit**: `llm_prisma_judge.py` for haiku subagent-based PRISMA compliance evaluation (alternative to keyword matching)
- **PubMedBert semantic selection**: `semantic_selector.py` using `pritamdeka/S-PubMedBert-MS-MARCO` embeddings + haiku judge for article relevance scoring (optional, requires `pip install -e ".[semantic]"`)
- **Cover letter**: Auto-generated letter to the editor with key contributions, PRISMA compliance, and data availability
- **AMA citation format**: Superscript numbered references via CSL
- **GitHub Actions**: Automated render and release on push (PDF, DOCX, cover letter, BibTeX)
- **Claude Code skills**: `/lit-review` (full pipeline) and `/brainstorm-topic` (search term refinement)
- **CLI interface**: `lit-review review`, `lit-review validate`, `lit-review check-config`
- **Zotero export**: Automatic collection creation and article import
- **Open access enrichment**: Via Unpaywall API
- **CITATION.cff**: GitHub citation with ORCID (Hsieh-Ting Lin, 0009-0002-3974-4528)
- **README.zhtw.md**: Traditional Chinese documentation

### Architecture

```
Topic → Search (3 DBs parallel) → Dedup → Quality Filter → DOI Validate
  → Fetch Abstracts → Balanced Selection → Haiku Extraction (5 agents)
  → Section Writing (4 agents, 9 files) → PRISMA Audit → Repair Loop
  → Cover Letter → Quarto Render (PDF+DOCX) → GitHub Release
```

### Pipeline metrics (HLH in adults, 2016-2026)

| Metric | Value |
|--------|-------|
| Records identified | 897 |
| After deduplication | 783 |
| Articles included | 50 |
| Unique journals | 36 |
| Abstracts fetched | 47/50 |
| With quantitative data (haiku) | 35/50 |
| Total word count | 12,755 |
| PRISMA audit score | 35/36 PASS |
| DOIs validated | 50/50 (100%) |
| PDF size | 184 KB |

### Extraction comparison

| Method | Articles with quant data | Avg richness score |
|--------|------------------------|--------------------|
| Regex (v0) | 21/50 | 1.2/10 |
| Haiku subagent (v1) | 35/50 | 2.2/10 |

### Dependencies

- Python >= 3.11
- httpx, pydantic, typer, rich, tenacity, bibtexparser, python-dotenv, pyyaml
- Quarto >= 1.7 (for rendering)
- Optional: sentence-transformers, torch (for PubMedBert semantic selection)

[1.0.0]: https://github.com/htlin222/robust-lit-review/releases/tag/review-20260325-052506
