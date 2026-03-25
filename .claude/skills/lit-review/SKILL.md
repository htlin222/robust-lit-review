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

### Stage 6: MODULAR PARALLEL WRITING (via section_dispatcher)

Write the review in PARALLEL using modular sections + Quarto `{{< include >}}`.

**Step 6a: Dispatch sections**
```python
from litreview.pipeline.section_dispatcher import dispatch_sections, generate_main_qmd
dispatched = dispatch_sections(articles, stats, Path("output"))
main_qmd = generate_main_qmd(topic, stats, Path("output"))
```

This creates `output/sections/*.context.json` with per-section article context.

**Step 6b: Launch parallel writing subagents (8 sections simultaneously)**

Launch ALL of these agents in a SINGLE message (parallel tool calls):

| Agent | Section File | Articles | Words |
|-------|-------------|----------|-------|
| 1 | `sections/00-abstract.qmd` | all | 300 |
| 2 | `sections/01-introduction.qmd` | review, classification, epidemiology | 1,200-1,500 |
| 3 | `sections/02-methods.qmd` | (none — methodological) | 800-1,000 |
| 4 | `sections/03-pathogenesis.qmd` | pathogenesis, genetics | 1,000-1,200 |
| 5 | `sections/04-diagnosis.qmd` | diagnosis, classification | 1,200-1,500 |
| 6 | `sections/05-etiology.qmd` | infection, malignancy, autoimmune, iatrogenic | 1,200-1,500 |
| 7 | `sections/06-treatment.qmd` | treatment_conventional/targeted/transplant | 1,500-1,800 |
| 8 | `sections/07-covid.qmd` | infection_trigger, pathogenesis | 800-1,000 |
| 9 | `sections/08-discussion.qmd` | review_guideline, prognosis | 1,500-1,800 |

Each agent:
1. Reads its context from `output/sections/{name}.context.json`
2. Reads `output/references.bib` for citation keys
3. Writes ONLY the body text (no YAML frontmatter) to `output/sections/{name}.qmd`
4. Uses [@key] citations matching the BibTeX

**Step 6c: Generate main.qmd**
Write the main file with `{{< include >}}` directives pointing to each section.

**CRITICAL WRITING RULES (include in EVERY agent prompt):**
1. Use specific numbers from abstracts (thresholds, dosing, sample sizes, p-values)
2. Include exact dosing when available
3. Name specific organisms/drugs/genes — never "various"
4. Include trial names + sample sizes (ZUMA-1 n=108)
5. Include diagnostic thresholds with sensitivity/specificity
6. Synthesize across studies — NOT one paragraph per article
7. Name all classification systems with full criteria
8. Distinguish related entities precisely (CRS vs IEC-HS vs HLH)
9. Use [@key] for parenthetical, @key for narrative citations
10. Write flowing academic paragraphs, not bullet points

### Stage 7: Assemble and Render
```bash
cd output
quarto render literature_review.qmd --to pdf
quarto render literature_review.qmd --to docx
```

### Stage 8: Final Report
Present to user:
- File locations: `.qmd`, `.bib`, `.pdf`, `.docx`
- Statistics table (PRISMA flow, articles by source/year/quartile)
- Word count per section and total
- Any warnings
- Remind: push to GitHub for release

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
