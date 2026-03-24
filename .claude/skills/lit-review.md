---
name: lit-review
description: Run a complete automated literature review pipeline - searches Scopus, PubMed, Embase, validates DOIs, filters by journal impact, generates Quarto/BibTeX/PDF/DOCX
user_invocable: true
---

# Literature Review Pipeline Skill

You are executing a world-class automated literature review. Follow this pipeline exactly.

## Pre-flight Checks

1. Read `.env` to confirm API keys are set (SCOPUS_API_KEY, PUBMED_API_KEY, EMBASE_API_KEY, UNPAYWALL_EMAIL, ZOTERO_API_KEY)
2. Ensure `uv` and virtual environment are available
3. Check if `quarto` is installed for rendering

## Pipeline Execution

### Step 1: Get the Topic
If the user hasn't provided a topic, ask them: "What research topic would you like to review?"

### Step 2: Brainstorm Search Terms
Before searching, brainstorm comprehensive search terms:
- Primary terms (exact topic phrases)
- Related terms and synonyms
- MeSH terms for PubMed
- Boolean combinations
- Present the search strategy to the user for approval

### Step 3: Run the Pipeline
Execute via CLI or direct Python:

```bash
cd /Users/htlin/robust-lit-review
source .venv/bin/activate 2>/dev/null || (uv venv && source .venv/bin/activate && uv pip install -e ".")
python -m litreview.cli review "<TOPIC>" --term "<TERM1>" --term "<TERM2>" --target 50 --min-citescore 3.0 -v
```

Or for more control, use subagents:

1. **Search Agent**: Search all databases in parallel
2. **Quality Agent**: Filter by CiteScore/SJR, deduplicate
3. **Validation Agent**: Validate every DOI via doi.org API, check URLs
4. **Enrichment Agent**: Get OA links from Unpaywall, export to Zotero
5. **Writing Agent**: Generate the Quarto document with proper academic structure
6. **Statistics Agent**: Compute and report all metrics

### Step 4: Validate Outputs
- Verify all DOIs resolve correctly
- Check BibTeX syntax
- Ensure word count meets academic standards (3000-8000 words)
- Verify all citations in text match BibTeX entries

### Step 5: Render
```bash
cd output && quarto render literature_review.qmd --to pdf && quarto render literature_review.qmd --to docx
```

### Step 6: Report Results
Present to user:
- PRISMA flow diagram
- Statistics table (articles by source, year, quartile)
- File locations (QMD, BIB, PDF, DOCX)
- Any warnings (invalid DOIs, missing metadata)

## Quality Standards
- Only Q1/Q2 journals (CiteScore ≥ 3.0)
- Every DOI validated via API
- Every URL checked for accessibility
- Proper APA citation format
- PRISMA-compliant methodology reporting
