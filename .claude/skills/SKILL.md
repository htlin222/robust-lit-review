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

### Stage 4.5: Balanced Selection & Data Enrichment (NEW)
Use `litreview.pipeline.enrichment` module:
- **Balanced subtopic coverage**: Don't just take top-N by citations (skews toward reviews/COVID).
  Use `ensure_balanced_coverage()` to guarantee minimum articles per subtopic:
  epidemiology, pathogenesis, diagnosis, classification, genetics,
  treatment (conventional/targeted/transplant), prognosis
- **Extract structured data from abstracts**: Use `enrich_articles()` to pull out:
  - Sample sizes, percentages, p-values, confidence intervals
  - Hazard/odds ratios, survival rates
  - Diagnostic thresholds (ferritin >10,000, sIL-2R cutoffs)
  - Drug dosing (etoposide 150 mg/m², anakinra 1-2 mg/kg)
  - Incidence rates (cases per million)
  - Sensitivity/specificity values
- **Classify articles by subtopic** for thematic grouping
- **Build rich context** with `build_rich_article_context()` for the AI writer

### Stage 5: Export to Zotero
- Create a new Zotero collection named "LitReview: {topic}"
- Add all validated articles

### Stage 6: Generate Outputs — PUBLICATION-QUALITY WRITING
Write a REAL publication-ready review article, NOT a skeleton.

**Writing the review (delegate to a writing subagent):**

The writing agent receives ALL article data including full abstracts and extracted
quantitative data. It must produce 5,000-8,000 words of proper academic prose.

**CRITICAL WRITING RULES for publication quality:**

1. **Use specific numbers from abstracts**: "ferritin >10,000 ng/mL (98% specificity)" not "elevated ferritin"
2. **Include dosing when available**: "etoposide 150 mg/m² twice weekly" not "etoposide-based therapy"
3. **Cite epidemiologic data**: incidence rates, mortality trends, cohort sizes
4. **Name specific organisms/drugs/genes**: Not "various viral triggers" but "EBV, CMV, HSV, HHV-6"
5. **Include diagnostic thresholds**: H-Score cutoff 169 (93% sensitivity, 86% specificity)
6. **Compare study findings quantitatively**: "Study A showed 61% 5-year OS vs Study B's 54%"
7. **Name specific criteria/classifications**: HLH-2004, HLH-2024, EULAR/ACR MAS criteria
8. **Include trial identifiers**: NCT numbers, study names (ZUMA-1, CARTITUDE-1)
9. **Describe novel/pipeline agents**: Not just established drugs
10. **Distinguish related but distinct entities**: CRS vs HLH, MAS vs HLH, COVID-19 vs classical HLH

**Document structure:**
- Structured abstract (~250 words: Background, Methods, Results, Conclusion)
- Introduction: clinical significance, historical context, evolving understanding, objectives
- Methods: PRISMA-compliant, search strategy, inclusion/exclusion, quality assessment
- Results: Organized thematically (NOT one paragraph per article)
  - Subtopic sections derived from article classification
  - Cross-study synthesis with specific data points
  - Temporal trends and evolution of the field
- Discussion: synthesis, clinical implications, controversies, strengths/limitations, future directions
- Conclusion
- References

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
