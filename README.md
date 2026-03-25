# Robust Literature Review Pipeline

[![Render & Release](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml/badge.svg)](https://github.com/htlin222/robust-lit-review/actions/workflows/render-release.yml)

**From topic to submission-ready manuscript in one command.** This pipeline produces a complete, publication-grade systematic literature review article — not a skeleton or reference list, but a real academic manuscript with narrative synthesis, specific clinical data, and full PRISMA 2020 compliance.

## Why "Robust"?

Most automated review tools stop at collecting references. This pipeline goes all the way to a **submission-ready manuscript** with built-in quality assurance:

| What we deliver | How we ensure quality |
|----------------|----------------------|
| 10,000+ word narrative review | 8 parallel writing agents, each with domain-specific context |
| Specific clinical data (dosing, thresholds, p-values) | Haiku subagent structured extraction from full abstracts |
| Balanced topic coverage | Subtopic-aware article selection across 16 categories |
| Every DOI verified | doi.org handle API validation (100% pass rate) |
| PRISMA 2020 flow diagram | TikZ-rendered professional figure |
| PRISMA 2020 checklist | 27-item self-audit with automated gap detection |
| Auto-repair of gaps | Audit loop dispatches repair agents until all items pass |
| Cover letter to editor | Ready-to-submit letter highlighting significance |
| AMA-formatted citations | CSL-driven superscript numbering |
| PDF + DOCX + BibTeX | Quarto multi-format rendering |
| GitHub Release artifacts | Automated CI/CD on every push |

## Final Deliverables

Every run produces a complete submission package:

| File | Purpose |
|------|---------|
| `literature_review.pdf` | The manuscript — ready for journal submission |
| `literature_review.docx` | Editable Word version for co-author revisions |
| `cover_letter.qmd` | Cover letter to the editor (auto-generated) |
| `references.bib` | Validated BibTeX with all DOIs resolved |
| `sections/09-prisma-checklist.qmd` | Completed PRISMA 2020 checklist (27 items) |

## Pipeline: Topic to Manuscript

```
"Hemophagocytic lymphohistiocytosis in adults"
                    |
                    v
    +-----------+----------+-----------+
    |           |          |           |
 Scopus      PubMed     Embase     (parallel)
    |           |          |
    +-----------+----------+
                |
          897 records
                |
          Deduplicate ──> 783 unique
                |
          Quality filter (CiteScore >= 3.0)
                |
          DOI validation (100% via doi.org)
                |
          Fetch full abstracts (PubMed API)
                |
          Balanced subtopic selection ──> 50 articles
                |
          Haiku structured extraction (5 agents)
                |
          Zotero export
                |
    +-----------+--+--+--+--+--+--+--+-----------+
    |  abstract  intro  methods  pathogenesis  ...  |
    |          8 parallel writing agents             |
    +------------------------------------------------+
                |
          PRISMA 2020 audit (27 items)
                |
           pass? ──no──> repair agents ──> re-audit
                |
               yes
                |
          Generate cover letter
                |
          Quarto render (PDF + DOCX)
                |
          GitHub Release
```

## The PRISMA 2020 Audit Loop

What makes this pipeline truly robust is the **self-audit mechanism**. After all sections are written, the pipeline automatically:

1. **Audits** the manuscript against all 27 PRISMA 2020 checklist items (keyword matching or LLM-as-judge via haiku subagents)
2. **Identifies gaps** — items that are missing or partially addressed
3. **Generates targeted fix instructions** for each section file that needs improvement
4. **Dispatches repair agents** that add only the missing content (no rewrites)
5. **Re-audits** until all items pass (max 2 iterations)

```python
from litreview.pipeline.prisma_audit import audit_manuscript, format_audit_report

results = audit_manuscript(Path("output/sections"))
print(format_audit_report(results))
# Score: 35/36 passed (0 failed, 0 partial, 1 N/A)
# All PRISMA 2020 items are addressed. The manuscript is ready for submission.
```

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

## Modular Section Architecture

The review is written in parallel using Quarto `{{< include >}}` syntax:

```
output/
  literature_review.qmd              # Main file with includes
  cover_letter.qmd                   # Letter to the editor
  references.bib                     # BibTeX references
  prisma-flow-diagram/               # PRISMA TikZ package
  sections/
    00-abstract.qmd                  # Structured abstract (~300 words)
    01-introduction.qmd              # Clinical significance, history, objectives
    02-methods.qmd                   # PRISMA flow, search strategy, quality assessment
    03-pathogenesis.qmd              # IFN-gamma axis, cytokines, ferritin, genetics
    04-diagnosis.qmd                 # HLH-2004, HLH-2024, HScore, MAS criteria
    05-etiology.qmd                  # Infections, malignancy, MAS, iatrogenic
    06-treatment.qmd                 # HLH-94 dosing, targeted therapies, HSCT
    07-covid.qmd                     # COVID-19 and HLH paradigm
    08-discussion.qmd                # Synthesis, controversies, future directions
    09-prisma-checklist.qmd          # PRISMA 2020 checklist (27 items, auto-audited)
```

## What's in the Manuscript

This is not a template — it's a real article with clinical granularity:

- **Diagnostic criteria with exact thresholds**: HLH-2004 (8 criteria, 5/8 needed), HScore (cutoff 168, 93% sensitivity, 86% specificity), EULAR/ACR MAS (ferritin >684 + 2/4 criteria)
- **Treatment protocols with dosing**: etoposide 150 mg/m² twice weekly, dexamethasone 10 mg/m²/day, anakinra 1-2 mg/kg
- **Trial data with sample sizes**: ZUMA-1 (n=108), CARTITUDE-1 (n=97), emapalumab (n=34, 63% response, P=0.02)
- **Every organism named**: EBV, CMV, HSV-1/2, HHV-6, HHV-8, HIV, SARS-CoV-2, M. tuberculosis, Ehrlichia, Histoplasma, Plasmodium...
- **Distinct entities distinguished**: CRS vs IEC-HS vs classical HLH, HLH-2004 vs HLH-2024, MAS vs secondary HLH

## GitHub Actions

On push to `main`, the workflow automatically:
- Renders Quarto to PDF + DOCX
- Creates a GitHub Release with all artifacts (PDF, DOCX, BibTeX, QMD)
- Uploads artifacts for 90-day retention

## Claude Code Integration

This project includes Claude Code skills:

- `/lit-review` -- Run the full pipeline with modular parallel writing + PRISMA audit
- `/brainstorm-topic` -- Brainstorm and refine search terms before running

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

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT
