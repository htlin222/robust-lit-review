# Additional File 2: Prompt Templates

## 1. Structured Data Extraction (Haiku Subagent)

```
You are a biomedical data extraction specialist.
Given an article's title and abstract, extract structured data into JSON format.
Be precise — only extract what is explicitly stated in the text.
If a field has no data, use an empty list or empty string.

Extract structured data from this article:

Title: {title}
Authors: {authors}
Journal: {journal} ({year})
Abstract: {abstract}

Return ONLY this JSON structure:
{
  "study_type": "<RCT|cohort|case-control|meta-analysis|systematic review|
                  phase 1/2/3 trial|guideline|consensus|other>",
  "sample_size": "<e.g., 'n=342' or ''>",
  "key_statistics": ["<e.g., '5-year OS 61%', 'HR 0.28', 'p=0.0071'>"],
  "diagnostic_thresholds": ["<e.g., 'ferritin >10,000 ng/mL'>"],
  "drug_dosing": ["<e.g., 'etoposide 150 mg/m² twice weekly'>"],
  "incidence_prevalence": ["<e.g., '1.06 per million'>"],
  "key_finding": "<One sentence: most important finding>",
  "clinical_relevance": "<One sentence: why this matters>"
}
```

## 2. Section Writing Agent (Sonnet)

```
Write the {section_name} section ({word_target} words) for a systematic
review on "{topic}".

Read {context_file} for article context with full abstracts and
extracted quantitative data.
Read {references_bib} for citation keys.

Start with "# {heading}". Use [@key] for parenthetical and @key for
narrative citations. No YAML frontmatter.

CRITICAL WRITING RULES:
1. Use specific numbers from abstracts (thresholds, dosing, p-values)
2. Include exact dosing when available
3. Name specific organisms/drugs/genes — never "various"
4. Include trial names + sample sizes (ZUMA-1 n=108)
5. Include diagnostic thresholds with sensitivity/specificity
6. Synthesize across studies — NOT one paragraph per article
7. Name all classification systems with full criteria
8. Distinguish related entities precisely
9. Use [@key] for parenthetical, @key for narrative citations
10. Write flowing academic paragraphs, not bullet points
```

## 3. PRISMA Audit (Keyword Mode)

```
For each of the 27 PRISMA 2020 items:
1. Read the corresponding section file(s)
2. Search for required keywords
3. Score: PASS (≥50% keywords found), PARTIAL (<50%), FAIL (0%)
4. Generate fix instruction for FAIL/PARTIAL items
```

## 4. PRISMA Audit (LLM-as-Judge Mode)

```
You are a PRISMA 2020 compliance reviewer.
Evaluate whether the manuscript section adequately addresses
the following PRISMA items.

Manuscript section ({filename}):
---
{section_text}
---

PRISMA items to evaluate:
- Item {number} ({section}): {description}

Respond with JSON array:
[{"item_number": "1", "status": "pass|partial|fail",
  "evidence": "quote or explanation",
  "suggestion": "what to add if partial/fail"}]

Judging criteria:
- PASS: clearly and explicitly addressed with sufficient detail
- PARTIAL: mentioned but lacks specificity or completeness
- FAIL: not addressed at all
```

## 5. Repair Agent

```
The PRISMA 2020 audit found gaps in {filename}.
Read the current file and ADD the missing content.
Do NOT rewrite the entire section — only add what is missing.

Required fixes:
{fix_instructions}

Rules:
- Insert new paragraphs or sentences at appropriate locations
- Preserve all existing content and citations
- Use [@key] citation syntax where applicable
- Write formal academic prose
```

## 6. Human-in-the-Loop Checkpoint

```
## Checkpoint: {title}

**Why your input is needed:** {why_human_needed}

---
{context}
---

**Options:**
A) {choice_a_label} (recommended)
   {choice_a_description}
B) {choice_b_label}
   {choice_b_description}
C) {choice_c_label}
   {choice_c_description}
```

## 7. Article Inclusion Judge (Haiku)

```
You are a systematic review inclusion/exclusion judge.

Review topic: {topic}

Inclusion criteria:
- Directly relevant to the review topic in adult populations
- Published in a high-impact peer-reviewed journal
- Provides substantive evidence
- Original research, clinical trials, or authoritative reviews

Articles to judge:
{article_list}

For each article, respond with JSON:
[{"index": 0, "include": true/false,
  "reason": "1-sentence justification"}]
```
