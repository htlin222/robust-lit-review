---
name: robust-lit-review
description: World-class automated literature review pipeline - the single entry point for all lit review operations (brainstorm, search, review, render)
user_invocable: true
---

# Robust Literature Review Pipeline

You are orchestrating a world-class automated systematic literature review. This is the single entry point for all operations.

## Available Commands

The user can request any of these modes:

| Command | What it does |
|---------|-------------|
| `/robust-lit-review` | Full pipeline: topic -> search -> filter -> validate -> write -> render |
| `/robust-lit-review brainstorm` | Brainstorm and refine search terms before running |
| `/robust-lit-review validate` | Validate DOIs in an existing .bib file |
| `/robust-lit-review render` | Re-render existing .qmd to PDF/DOCX |

## Environment

API keys are in `.env`:
- `SCOPUS_API_KEY` — Elsevier/Scopus (search + CiteScore/SJR journal metrics)
- `PUBMED_API_KEY` — NCBI E-utilities (PubMed search)
- `EMBASE_API_KEY` — Elsevier/Embase (medical literature)
- `UNPAYWALL_EMAIL` — DOI validation + open access links
- `ZOTERO_API_KEY` + `ZOTERO_LIBRARY_*` — Export to Zotero collection

## BRAINSTORM Mode

When the user wants to explore/refine their topic before running:

1. **Understand** — Ask probing questions about the topic scope
2. **Generate search terms** — Primary terms, synonyms, MeSH/Emtree terms, Boolean queries
3. **Test queries** — Use the APIs to check result counts per database:
   ```bash
   cd /Users/htlin/robust-lit-review && source .venv/bin/activate
   python -c "
   import asyncio
   from litreview.config import get_config
   from litreview.clients.scopus import ScopusClient
   async def count():
       config = get_config()
       async with ScopusClient(config.scopus_api_key) as c:
           r = await c.search('TITLE-ABS-KEY(\"YOUR QUERY\")', max_results=1)
           # Check opensearch:totalResults from raw response
   asyncio.run(count())
   "
   ```
4. **Refine** — Too many (>5000)? Narrow. Too few (<50)? Broaden. Sweet spot: 100-1000.
5. **Approve** — Present final strategy, then offer to run full pipeline

## FULL PIPELINE Mode

Execute these stages sequentially. Use subagents for parallelizable steps.

### Stage 1: Setup
```bash
cd /Users/htlin/robust-lit-review
source .venv/bin/activate 2>/dev/null || (uv venv && source .venv/bin/activate && uv pip install -e ".")
```

### Stage 2: Search (parallelize across databases)
Launch 3 subagents in parallel:
- **Scopus Agent**: Search Scopus API, get CiteScore/SJR metrics per journal
- **PubMed Agent**: Search PubMed via E-utilities
- **Embase Agent**: Search Embase with medical subject filters

### Stage 3: Deduplicate & Quality Filter
- Remove duplicates by DOI
- Filter to Q1/Q2 journals only (CiteScore >= 3.0, SJR quartile)
- Articles without metrics from PubMed are kept for validation

### Stage 4: Validate (parallelize)
Launch validation subagent:
- Validate every DOI via `https://doi.org/api/handles/{doi}`
- Check OA status via Unpaywall API
- Verify URL accessibility
- **REJECT articles with invalid DOIs**

### Stage 5: Export to Zotero
- Create a new Zotero collection named "LitReview: {topic}"
- Add all validated articles

### Stage 6: Generate Outputs
- BibTeX file (`output/references.bib`)
- Quarto document (`output/literature_review.qmd`) with:
  - YAML frontmatter (PDF + DOCX + HTML formats, APA citation style)
  - Introduction (objectives, scope)
  - Methods (PRISMA flow, search strategy, inclusion criteria)
  - Results (statistics table, year distribution, thematic synthesis)
  - Discussion (findings, trends, limitations, future directions)
  - References section

### Stage 7: Compute Statistics
Report to user:
- PRISMA flow diagram
- Articles by source database
- Articles by year
- Articles by journal quartile
- Average CiteScore and citation count
- Word count
- Reference count

### Stage 8: Render
```bash
cd output
quarto render literature_review.qmd --to pdf
quarto render literature_review.qmd --to docx
```

### Stage 9: Final Report
Present the user with:
- File locations: `.qmd`, `.bib`, `.pdf`, `.docx`
- Statistics summary table
- Any warnings (invalid DOIs, missing metadata, Embase errors)
- Remind: push to GitHub to trigger the release workflow

## CLI Alternative

The full pipeline is also available via CLI:
```bash
lit-review review "TOPIC" --term "term1" --term "term2" --target 50 --min-citescore 3.0 -v
```

## Quality Gates (NON-NEGOTIABLE)

1. **Only high-IF articles**: CiteScore >= 3.0 OR Q1/Q2 journals
2. **Every DOI validated**: Via doi.org handle API — no unresolved DOIs
3. **Every URL checked**: HEAD request to verify accessibility
4. **PRISMA compliance**: Full flow diagram with numbers at each stage
5. **APA format**: Via CSL stylesheet
6. **Word count target**: 3,000-8,000 words for the review body
7. **Deduplication**: Cross-database duplicate removal by DOI and title

## GitHub Actions

On push to `main` with changes in `output/`, the workflow:
1. Renders Quarto to PDF + DOCX
2. Creates a GitHub Release with all artifacts
3. Uploads artifacts for 90-day retention

## Error Handling

- If Scopus fails: Continue with PubMed + Embase
- If PubMed fails: Continue with Scopus + Embase
- If Embase fails: Continue with Scopus + PubMed (most common — Embase requires specific subscription)
- If Unpaywall fails: Mark DOIs as unvalidated, warn user
- If Zotero fails: Skip export, warn user
- If Quarto rendering fails: Provide .qmd + .bib, instruct manual render
- **Never fail silently** — always report what succeeded and what didn't
