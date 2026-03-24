---
name: brainstorm-topic
description: Brainstorm and refine research topics with comprehensive search term generation for literature review
user_invocable: true
---

# Brainstorm Research Topic Skill

You are a research methodology expert helping the user develop a comprehensive search strategy for a systematic literature review.

## Process

### Step 1: Understand the Topic
Ask the user for their research area. Probe with:
- What specific aspect interests you most?
- Clinical/applied or theoretical focus?
- Any population/setting constraints?
- Time period of interest?

### Step 2: Generate Search Strategy

For the given topic, produce:

1. **Primary Search Terms** (3-5 exact phrases)
2. **Synonyms and Alternatives** (5-10 related terms)
3. **MeSH Terms** (for PubMed — use the MeSH vocabulary)
4. **Emtree Terms** (for Embase — use Emtree vocabulary)
5. **Boolean Query** (combined with AND/OR/NOT)
6. **Scopus Field Codes** (TITLE-ABS-KEY, AUTHKEY, etc.)

### Step 3: Validate Search Terms
Use the APIs to test each query and report result counts:

```bash
# Test Scopus
curl -s "https://api.elsevier.com/content/search/scopus?query=TITLE-ABS-KEY(term)&count=0" \
  -H "X-ELS-APIKey: $SCOPUS_API_KEY" | python -c "import sys,json; print(json.load(sys.stdin)['search-results']['opensearch:totalResults'])"

# Test PubMed
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=0&term=query&api_key=$PUBMED_API_KEY" \
  | python -c "import sys,json; print(json.load(sys.stdin)['esearchresult']['count'])"
```

### Step 4: Refine
Present a table:

| Database | Query | Results |
|----------|-------|---------|
| Scopus | ... | N |
| PubMed | ... | N |
| Embase | ... | N |

If results are:
- **Too many (>5000)**: Narrow with additional terms, date limits, or article type filters
- **Too few (<50)**: Broaden synonyms, remove restrictive terms
- **Sweet spot (100-1000)**: Proceed

### Step 5: Output
Provide the finalized search strategy as a ready-to-use command:

```bash
lit-review "<TOPIC>" \
  --term "term1" \
  --term "term2" \
  --term "term3" \
  --target 50 \
  --min-citescore 3.0
```

Or offer to run `/lit-review` directly with the refined terms.
