# Systematic Reviews (Springer/BMC) — Submission Guide

## Journal Profile

- **Publisher:** BioMed Central / Springer Nature
- **ISSN:** 2046-4053
- **IF:** 4.6 (2024) | **Quartile:** Q1
- **Open Access:** Yes (always, Gold OA)
- **APC:** ~$2,190 USD
- **URL:** https://link.springer.com/journal/13643
- **Indexed in:** PubMed, Scopus, Web of Science, DOAJ

## Article Types

| Type | Description |
|------|-------------|
| **Research** | Full systematic reviews, scoping reviews, rapid reviews |
| **Protocol** | Prospective registration of planned reviews |
| **Methodology** | **← OUR TARGET.** New methods, tools, procedures for SR conduct |
| **Commentary** | Opinion pieces on SR methodology |
| **Update** | Updates of previously published reviews |

## Methodology Article Requirements

**What it is:** "Present a new experimental or computational method, test or procedure. The method described may either be completely new, or may offer a better version of an existing method. The article must describe a **demonstrable advance** on what is currently available."

This is exactly us — an end-to-end automated pipeline that advances the state of the art.

## Formatting Requirements

### Abstract
- **Structured:** Background, Methods, Results, Conclusions
- **Word limit:** ≤350 words
- **No citations** in abstract
- **Registration:** Include PROSPERO/OSF registration number as last line (or state "Not registered")
- **Keywords:** 3-10 keywords after abstract

### Main Text
- **No strict word limit** for Methodology articles (Research articles: ~3,500 words)
- **Sections:** Background, Methods, Results and Discussion, Conclusions
- **PRISMA:** Completed PRISMA checklist required as additional file for any SR
- **Figures/Tables:** No strict limit, but supplementary files encouraged for large datasets

### References
- **Style:** Vancouver (numbered)
- **Format:** Author(s). Title. Journal. Year;Volume(Issue):Pages. DOI.
- **Note:** AMA is compatible with Vancouver — our current format works

### Required Declarations
- Ethics approval and consent (N/A for methodology)
- Consent for publication
- Competing interests
- Funding
- Authors' contributions
- Data availability statement
- Acknowledgements

## Registration

- **PROSPERO** registration encouraged but NOT required for methodology articles
- If not registered, state: "This study was not registered as it describes a methodological tool rather than a specific systematic review."

## Recent Precedent Papers (directly relevant to ours)

### Published in Systematic Reviews 2024:

1. **"Leveraging artificial intelligence to enhance systematic reviews in health research: advanced tools and challenges"**
   - Systematic Reviews 13, 269 (2024)
   - DOI: 10.1186/s13643-024-02682-2
   - Scope: AI tools for screening, extraction, quality assessment

2. **"Automation of systematic reviews of biomedical literature: a scoping review of studies indexed in PubMed"**
   - Systematic Reviews 13 (2024)
   - DOI: 10.1186/s13643-024-02592-3
   - Scope: Overview of SR automation technologies

**Neither of these describes an end-to-end pipeline that produces a manuscript.** Both are reviews of existing tools. We are the tool itself, validated on 3 topics.

## Our Paper Structure (adapted for this journal)

```
Title: Harnessing Large Language Model Engineering for Automated
       Systematic Reviews: A Multi-Agent Pipeline with PRISMA 2020
       Self-Auditing

Article type: Methodology

Abstract: (structured, ≤350 words)
  Background:
  Methods:
  Results:
  Conclusions:
  Registration: Not registered (methodological tool)

Keywords: systematic review automation, large language model,
  multi-agent orchestration, PRISMA 2020, evidence synthesis,
  human-in-the-loop, structured extraction, publication automation

Background: (~800 words)
  - SR bottleneck, current tools landscape, gap, LLM engineering

Methods: (~1,500 words)
  - Pipeline architecture (Figure 1)
  - Multi-DB search + quality filtering
  - LLM extraction (haiku subagents)
  - Modular parallel writing
  - PRISMA self-audit loop
  - Human-in-the-loop checkpoints

Results: (~1,200 words)
  - Three case studies: HLH, DLBCL, MM
  - Table 1: Pipeline metrics across 3 topics
  - Table 2: Extraction comparison (regex vs haiku)
  - Table 3: PRISMA compliance across 3 topics
  - Table 4: Comparison with expert reviews
  - Table 5: Feature comparison with existing tools

Discussion: (~1,000 words)
  - Advances, limitations, ethical considerations, future

Conclusions: (~200 words)

Declarations:
  - Competing interests: None
  - Funding: None
  - Data availability: GitHub repository
  - Code availability: Open source, MIT license

Additional files:
  - Additional file 1: PRISMA 2020 checklist
  - Additional file 2: Prompt templates for all agent types
  - Additional file 3: Complete pipeline metrics for all 3 case studies
```

## What Gives Us an Edge for This Journal

1. **Methodology article type** = lower competition than Research (fewer submissions)
2. **Three validated case studies** = demonstrated advance (their key requirement)
3. **Open source + reproducible** = aligns with their data availability requirements
4. **PRISMA self-audit** = speaks directly to their core audience
5. **Two recent 2024 papers on SR automation** = editors are actively interested in this space
6. **We go further than those papers** = they reviewed tools; we ARE the tool, validated

## Submission Checklist

- [ ] Manuscript in Word/LaTeX format
- [ ] Structured abstract ≤350 words
- [ ] PRISMA 2020 checklist (Additional file 1)
- [ ] All figures as separate high-resolution files
- [ ] Cover letter
- [ ] Competing interests declaration
- [ ] Data availability statement (link to GitHub)
- [ ] Authors' contributions statement
- [ ] Registration statement ("Not registered — methodological tool")
- [ ] Keywords (3-10)

## Timeline

- Week 1-2: Draft manuscript
- Week 3: Internal review, polish figures
- Week 4: Submit
- Week 6-10: Peer review (~4-6 weeks typical)
- Week 10-12: Revisions
- Week 14-16: Acceptance → publication (OA = immediate)

## Sources

- [Systematic Reviews — Home](https://link.springer.com/journal/13643)
- [Submission Guidelines](https://systematicreviewsjournal.biomedcentral.com/submission-guidelines)
- [Methodology Article Type](https://systematicreviewsjournal.biomedcentral.com/submission-guidelines/preparing-your-manuscript/methodology)
- [AI in SR (2024)](https://systematicreviewsjournal.biomedcentral.com/articles/10.1186/s13643-024-02682-2)
- [SR Automation Scoping Review (2024)](https://systematicreviewsjournal.biomedcentral.com/articles/10.1186/s13643-024-02592-3)
