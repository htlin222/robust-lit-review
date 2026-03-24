# Robust Literature Review Pipeline

Automated systematic literature review pipeline that searches **Scopus**, **PubMed**, and **Embase**, filters by journal impact (CiteScore/SJR), validates every DOI, and generates publication-ready documents.

## What It Does

Given a research topic, this pipeline:

1. **Searches** 3 major databases in parallel (Scopus, PubMed, Embase)
2. **Deduplicates** results across databases by DOI and title
3. **Filters** by journal quality (CiteScore >= 3.0, Q1/Q2 journals)
4. **Validates** every DOI via doi.org API — no broken references
5. **Enriches** with open access links via Unpaywall
6. **Exports** to Zotero collection automatically
7. **Generates** Quarto document with PRISMA flow, statistics, thematic synthesis
8. **Renders** to PDF, DOCX, and HTML with APA citations
9. **Releases** artifacts via GitHub Actions on push

## Quick Start

```bash
# Install
uv venv && source .venv/bin/activate && uv pip install -e "."

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run a literature review
lit-review review "your research topic" --target 50 --min-citescore 3.0

# Validate DOIs in existing BibTeX
lit-review validate output/references.bib

# Check API configuration
lit-review check-config
```

## API Keys Required

| Service | Purpose | Get Key |
|---------|---------|---------|
| Scopus | Article search + CiteScore/SJR metrics | [Elsevier Developer Portal](https://dev.elsevier.com/) |
| PubMed | Biomedical literature search | [NCBI API Key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) |
| Embase | Medical literature (via Elsevier) | Same as Scopus |
| Unpaywall | DOI validation + open access links | [Unpaywall](https://unpaywall.org/) (just email) |
| Zotero | Reference management export | [Zotero Settings](https://www.zotero.org/settings/keys) |

## Pipeline Architecture

```
Topic Input
    |
    v
[Scopus API] --+-- [PubMed API] --+-- [Embase API]    (parallel search)
    |                |                  |
    +--------+-------+------------------+
             |
         Deduplicate (by DOI/title)
             |
         Quality Filter (CiteScore >= 3.0)
             |
         DOI Validation (doi.org API)
             |
         OA Enrichment (Unpaywall)
             |
         Zotero Export
             |
    +--------+--------+
    |        |        |
  .bib     .qmd    Stats
    |        |
    v        v
  PDF      DOCX
```

## Output Files

| File | Description |
|------|-------------|
| `output/literature_review.pdf` | Formatted PDF with citations |
| `output/literature_review.docx` | Word document |
| `output/literature_review.qmd` | Quarto source (editable) |
| `output/references.bib` | BibTeX references |

## GitHub Actions

On push to `main`, the workflow automatically:
- Renders Quarto to PDF + DOCX
- Creates a GitHub Release with all artifacts
- Uploads artifacts for 90-day retention

## Quality Standards

- Only Q1/Q2 journals (CiteScore >= 3.0)
- 100% DOI validation via doi.org handle API
- PRISMA-compliant methodology reporting
- APA citation format (CSL)
- Cross-database deduplication

## Claude Code Integration

This project includes Claude Code skills:

- `/robust-lit-review` — Run the full pipeline
- `/brainstorm-topic` — Brainstorm and refine search terms

## License

MIT
