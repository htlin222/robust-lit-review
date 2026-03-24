# Robust Literature Review Pipeline

## Overview
Automated systematic literature review pipeline that searches Scopus, PubMed, and Embase,
filters by journal quality (CiteScore/SJR), validates DOIs, and generates publication-ready
Quarto documents with BibTeX references.

## Skills
- `/lit-review` — Run the complete pipeline for a topic
- `/brainstorm-topic` — Brainstorm and refine search terms before running

## Project Structure
```
src/litreview/
  clients/        — API clients (Scopus, PubMed, Embase, Unpaywall, Zotero)
  pipeline/       — Orchestrator + Quarto renderer
  utils/          — BibTeX generator, DOI validator, statistics
  cli.py          — Typer CLI interface
  config.py       — Environment-based configuration
  models.py       — Pydantic data models
output/           — Generated review files (.qmd, .bib, .pdf, .docx)
templates/        — Quarto templates
.github/workflows/ — GitHub Actions for render + release
```

## Commands
```bash
# Install
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Run review
lit-review review "topic" --term "term1" --target 50 --min-citescore 3.0

# Validate DOIs in existing BibTeX
lit-review validate output/references.bib

# Check API config
lit-review check-config
```

## Environment Variables (in .env)
- SCOPUS_API_KEY — Elsevier/Scopus API key
- PUBMED_API_KEY — NCBI E-utilities API key
- EMBASE_API_KEY — Elsevier/Embase API key
- UNPAYWALL_EMAIL — Email for Unpaywall API
- ZOTERO_API_KEY — Zotero API key
- ZOTERO_LIBRARY_TYPE — "user" or "group"
- ZOTERO_LIBRARY_ID — Zotero library ID
- ZOTERO_COLLECTION_KEY — Target collection key

## Quality Standards
- Only include articles from Q1/Q2 journals (CiteScore >= 3.0)
- Every DOI must be validated via doi.org handle API
- All URLs checked for accessibility
- PRISMA-compliant methodology reporting
- APA citation format via CSL
