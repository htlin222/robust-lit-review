# Robust Literature Review Pipeline

[![Render & Release](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml/badge.svg)](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml)

Automated systematic literature review pipeline that searches **Scopus**, **PubMed**, and **Embase**, filters by journal impact (CiteScore/SJR), validates every DOI, and generates publication-ready documents with AMA-formatted citations and PRISMA TikZ flow diagrams.

## What It Does

Given a research topic, this pipeline:

1. **Searches** 3 major databases in parallel (Scopus, PubMed, Embase)
2. **Deduplicates** results across databases by DOI and title
3. **Filters** by journal quality (CiteScore >= 3.0, Q1/Q2 journals)
4. **Validates** every DOI via doi.org API
5. **Fetches full abstracts** via PubMed/Scopus Abstract Retrieval API
6. **Extracts structured data** from abstracts (sample sizes, p-values, dosing, thresholds)
7. **Balances subtopic coverage** (epidemiology, pathogenesis, diagnosis, treatment, prognosis)
8. **Enriches** with open access links via Unpaywall
9. **Exports** to Zotero collection automatically
10. **Writes modular sections in parallel** via `{{< include >}}` architecture
11. **Renders** to PDF (with PRISMA TikZ diagram) and DOCX with AMA citations
12. **Releases** artifacts via GitHub Actions on push

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
         Fetch Full Abstracts (PubMed/Scopus)
             |
         Balanced Subtopic Selection
             |
         Extract Structured Data (regex)
             |
         OA Enrichment (Unpaywall)
             |
         Zotero Export
             |
    +--------+--------+--------+
    |        |        |        |
  .bib    sections/  Stats  PRISMA
             |                (TikZ)
    8 parallel writing agents
             |
         main.qmd ({{< include >}})
             |
    +--------+--------+
    |                 |
   PDF              DOCX
```

## Modular Section Architecture

The review is written in parallel using Quarto `{{< include >}}` syntax:

```
output/
  literature_review.qmd          # Main file with includes
  references.bib                 # BibTeX references
  prisma-flow-diagram/           # PRISMA TikZ package
  sections/
    00-abstract.qmd              # Structured abstract
    01-introduction.qmd          # Clinical significance, history, objectives
    02-methods.qmd               # PRISMA flow, search strategy, quality assessment
    03-pathogenesis.qmd          # IFN-gamma axis, cytokines, ferritin, genetics
    04-diagnosis.qmd             # HLH-2004, HLH-2024, HScore, MAS criteria
    05-etiology.qmd              # Infections, malignancy, MAS, iatrogenic (CAR-T, ICI)
    06-treatment.qmd             # HLH-94 dosing, targeted therapies, HSCT
    07-covid.qmd                 # COVID-19 and HLH paradigm
    08-discussion.qmd            # Synthesis, controversies, future directions
```

## Output Files

| File | Description |
|------|-------------|
| `output/literature_review.pdf` | Formatted PDF with AMA citations + PRISMA TikZ diagram |
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
- PRISMA 2020 compliant (TikZ flow diagram)
- AMA citation format
- Balanced subtopic coverage (not just top-cited)
- Structured data extraction from abstracts
- Cross-database deduplication

## Claude Code Integration

This project includes Claude Code skills:

- `/lit-review` -- Run the full pipeline with modular parallel writing
- `/brainstorm-topic` -- Brainstorm and refine search terms

## Citing This Project

If you use this pipeline in your research, please cite:

### BibTeX

```bibtex
@software{lin2026robustlitreview,
  author       = {Lin, Hsieh-Ting},
  title        = {Robust Literature Review Pipeline: Automated Systematic Review with Multi-Database Search, DOI Validation, and Publication-Ready Output},
  year         = {2026},
  publisher    = {GitHub},
  url          = {https://github.com/htlin222/robust-lit-review},
  version      = {1.0.0}
}
```

### APA

Lin, H.-T. (2026). *Robust Literature Review Pipeline: Automated systematic review with multi-database search, DOI validation, and publication-ready output* (Version 1.0.0) [Computer software]. GitHub. https://github.com/htlin222/robust-lit-review

### AMA

Lin HT. Robust Literature Review Pipeline: Automated Systematic Review with Multi-Database Search, DOI Validation, and Publication-Ready Output. Version 1.0.0. GitHub; 2026. Accessed March 25, 2026. https://github.com/htlin222/robust-lit-review

## License

MIT
