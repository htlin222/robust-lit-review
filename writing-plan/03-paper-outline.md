# Paper Outline

## Title
Harnessing Large Language Model Engineering for Automated Systematic Reviews:
A Multi-Agent Pipeline with PRISMA 2020 Self-Auditing

## Authors
Hsieh-Ting Lin (ORCID: 0009-0002-3974-4528)

---

## Structured Abstract (~300 words)

**Background:** Systematic reviews are the gold standard for evidence synthesis but require 6-18 months of manual effort. Current automation tools address screening (ASReview, Rayyan) or extraction (Elicit) but none produce submission-ready manuscripts with verified references and PRISMA compliance.

**Objective:** To develop and validate an end-to-end automated systematic review pipeline harnessing LLM engineering techniques — multi-agent orchestration, structured prompting, LLM-as-judge evaluation, and self-repair loops — to produce publication-ready manuscripts from a single topic input.

**Methods:** We designed a modular pipeline integrating: (1) parallel multi-database search (Scopus, PubMed, Embase); (2) journal quality filtering via Scimago/OpenAlex; (3) 100% DOI validation; (4) haiku-model structured extraction from abstracts; (5) balanced subtopic article selection; (6) parallel section writing via 8 independent LLM agents; (7) automated PRISMA 2020 27-item self-audit with repair loop; and (8) human-in-the-loop checkpoints. We validated the pipeline on hemophagocytic lymphohistiocytosis (HLH) in adults and compared output with an expert-written review (Hsu et al., Blood 2026).

**Results:** From 897 initial records, the pipeline selected 50 high-quality articles (46 Q1, 4 Q2), generated a 12,755-word manuscript with 48 validated references, achieved 35/36 PRISMA compliance score, and produced a submission-ready PDF with AMA citations and TikZ PRISMA flow diagram in approximately 25 minutes. Haiku extraction identified quantitative data in 70% of articles versus 42% with regex. The automated manuscript included specific diagnostic thresholds, treatment dosing, trial data, and organism names comparable to the expert-written review.

**Conclusions:** LLM engineering techniques can be systematically harnessed to automate the full systematic review workflow from search to submission-ready manuscript, with built-in quality assurance mechanisms that address concerns about AI-generated academic content.

---

## 1. Introduction (~800 words)

### 1.1 The Systematic Review Bottleneck
- Gold standard for evidence synthesis (Cochrane, GRADE)
- Manual process: 6-18 months, 2+ reviewers, 1000+ hours
- Growing volume of published literature (>3M articles/year on PubMed)
- Result: reviews outdated by publication date

### 1.2 Current State of Automation
- Screening tools: ASReview (active learning), Rayyan (AI-assisted), Covidence (workflow)
- Extraction tools: Elicit, LLM-SLR (vector embedding)
- Writing tools: LitLLM (RAG-based generation)
- **Gap:** No tool bridges from search to submission-ready manuscript
- Recent otto-SR (medRxiv 2025): screening + extraction only, no writing/compliance

### 1.3 LLM Engineering as a Discipline
- From ad-hoc prompting to systematic engineering (cite: Prompt Report, arXiv 2406.06608)
- Multi-agent orchestration for complex tasks (cite: Virtual Scientists, ACL 2025)
- LLM-as-judge for automated evaluation (cite: NeurIPS 2024)
- Self-repair / reflexion loops (cite: Reflexion, NeurIPS 2023)
- These techniques have not been systematically applied to evidence synthesis

### 1.4 Objectives
1. Design an end-to-end automated SR pipeline harnessing LLM engineering
2. Validate on a real medical topic (HLH in adults)
3. Compare automated output with expert-written review
4. Evaluate PRISMA 2020 compliance automatically
5. Assess the role of human-in-the-loop checkpoints

---

## 2. Methods (~1500 words)

### 2.1 Pipeline Architecture Overview
- Figure 1: System architecture diagram
- 9 stages from topic input to GitHub Release
- Modular design: each stage independently replaceable
- Two modes: fully automated (default) and human-in-the-loop (--hitl)

### 2.2 Multi-Database Search and Quality Filtering
- Parallel API search: Scopus, PubMed E-utilities, Embase
- Deduplication by DOI and title similarity
- Journal quality: 3-tier cascade (Scimago CSV → OpenAlex h-index → CiteScore)
- Default: Q1 journals only (configurable)
- 100% DOI validation via doi.org handle API
- Open access enrichment via Unpaywall

### 2.3 LLM-Engineered Structured Extraction
- **Problem:** Abstracts contain clinical data (dosing, thresholds, p-values) that regex poorly captures
- **Approach:** Dispatch haiku-model (Claude Haiku 4.5) subagents with structured JSON schema
- **Schema:** study_type, sample_size, key_statistics, diagnostic_thresholds, drug_dosing, incidence_prevalence, key_finding, clinical_relevance
- **Comparison:** Regex baseline vs haiku extraction (Table 2)
- Full abstract retrieval via PubMed DOI search for Scopus-sourced articles

### 2.4 Modular Parallel Writing with Agent Orchestration
- **Problem:** Single-agent writing causes context overflow (100K+ chars for 50 articles)
- **Solution:** Section dispatcher classifies articles into 16 subtopics, builds per-section context
- 8 independent writing agents (Claude Sonnet), each receiving only its domain's articles
- Quarto `{{< include >}}` assembly — each section is a separate .qmd file
- **Prompt engineering:** 10 critical writing rules enforced in every agent prompt
  (specific numbers, exact dosing, named organisms, trial identifiers, etc.)
- Model routing: Haiku for extraction/judging (cost-efficient), Sonnet for writing (quality)

### 2.5 PRISMA 2020 Self-Audit Loop
- **Problem:** LLM-written manuscripts may miss PRISMA requirements
- **Approach 1:** Keyword matching (fast, 36 items × ~5 keywords each)
- **Approach 2:** LLM-as-judge (haiku agents read actual section text, evaluate substantive compliance)
- Audit produces: PASS/PARTIAL/FAIL per item + specific fix instructions
- Repair loop: dispatch targeted repair agents for failed items (edit-only, no rewrites)
- Re-audit until convergence (max 2 iterations)
- Auto-generate PRISMA checklist appendix

### 2.6 Human-in-the-Loop Checkpoints
- 9 checkpoints at decision points where machine uncertainty or error cost is highest
- Multiple-choice format (not open-ended) to minimize human burden
- Each checkpoint has a default for fully automated mode
- Decisions logged to JSON for reproducibility
- Table 3: Checkpoint rationale matrix

### 2.7 Output Rendering and Release
- Quarto multi-format rendering (PDF with TikZ PRISMA diagram, DOCX, HTML)
- AMA citation format via CSL
- Auto-generated cover letter
- GitHub Actions CI/CD: push triggers render + release with all artifacts

---

## 3. Case Study: HLH in Adults (2016-2026) (~600 words)

### 3.1 Topic Selection Rationale
- Rapidly evolving field (COVID-19, CAR-T, checkpoint inhibitors)
- Expert-written review available for comparison (Hsu et al., Blood 2026)
- Spans multiple subspecialties (hematology, rheumatology, oncology, critical care)

### 3.2 Pipeline Execution
- Search: 897 records from 3 databases
- Dedup: 783 unique articles
- Quality filter: Q1+Q2 journals
- Selection: 50 articles across 16 subtopics
- Abstracts: 47/50 retrieved via PubMed DOI lookup
- Extraction: 5 haiku agents → 35/50 with quantitative data
- Writing: 4 agents → 9 sections, 12,755 words
- PRISMA audit: 35/36 PASS after 1 repair iteration
- Render: 184KB PDF, 56KB DOCX, zero warnings

### 3.3 Comparison with Expert Review
- Table 4: Feature-by-feature comparison with Hsu et al. (Blood 2026)

---

## 4. Results (~800 words)

### 4.1 Pipeline Performance (Table 1)
- End-to-end time, cost breakdown by agent type, API calls

### 4.2 Extraction Quality (Table 2)
- Regex vs Haiku: 42% → 70% with quantitative data
- Richness score: 1.2 → 2.2 (out of 10)
- Study type identification: 0% → 85%

### 4.3 PRISMA Compliance (Table 3)
- 35/36 items passed automatically
- 2 partials auto-repaired in 1 iteration
- 1 N/A (sensitivity analysis — correct for narrative synthesis)

### 4.4 Content Quality Comparison (Table 4)
- What automated review captures well: diagnostic criteria, dosing, trial data, organism lists
- What it misses: epidemiologic detail, clinical pearls (sIL-2R/ferritin ratio specifics), novel pipeline agents from very recent publications
- Word count: 12,755 (ours) vs ~8,000 (expert)
- References: 48 (ours, all validated) vs 92 (expert, includes case reports)

### 4.5 Journal Quality Distribution
- 46/50 articles from Q1 journals (h-index ≥ 100)
- 4/50 from Q2 journals
- 0 from Q3/Q4

---

## 5. Discussion (~1000 words)

### 5.1 LLM Engineering Enables End-to-End Automation
- Multi-agent orchestration solves context overflow
- Structured prompting captures clinical data that regex misses
- LLM-as-judge provides scalable quality evaluation
- Self-repair loop addresses the "write once, hope it's right" problem

### 5.2 Comparison with Existing Tools
- Table 5: Feature matrix (ASReview, Rayyan, otto-SR, LitLLM, Covidence vs ours)
- We are the only tool that does both rigorous methodology AND manuscript generation
- PRISMA self-audit is unique — no other tool checks its own compliance

### 5.3 The Hallucination Problem
- LLM can fabricate statistics, invert findings, cite wrong sources
- Our mitigations: structured extraction from real abstracts, PRISMA audit, CP5 key claims verification
- Future: automated grounding checks (cross-reference claims against source text)
- Human-in-the-loop as safety net, not bottleneck

### 5.4 Ethical Considerations
- Transparency: all code open source, prompts disclosed
- Authorship: pipeline assists, does not replace human judgment
- Reproducibility: checkpoint logs, deterministic pipeline state
- Bias: CiteScore/h-index filtering may exclude important work from low-resource settings

### 5.5 Limitations
- Topic-dependent quality (medical topics with rich abstracts work best)
- No full-text access (abstract-only extraction)
- English-language only
- Citation accuracy depends on BibTeX quality
- No meta-analysis capability

### 5.6 Future Directions
- Living review updates (search for new articles since last run)
- Citation graph intelligence (OpenAlex referenced_works)
- Hallucination detection (claim-source cross-referencing)
- Full-text PDF parsing for richer context
- PubMedBert embedding for semantic article selection

---

## 6. Conclusion (~200 words)

- First end-to-end pipeline from topic to submission-ready systematic review manuscript
- Demonstrates that LLM engineering techniques (agent orchestration, structured prompting, LLM-as-judge, self-repair) can be systematically applied to evidence synthesis
- Achieves 35/36 PRISMA compliance with automated auditing
- Human-in-the-loop checkpoints balance automation with clinical judgment
- Open source: https://github.com/htlin222/robust-lit-review

---

## Figures

1. **Figure 1:** Pipeline architecture diagram (search → select → extract → write → audit → render)
2. **Figure 2:** PRISMA 2020 TikZ flow diagram (from the HLH case study)
3. **Figure 3:** Multi-agent orchestration diagram (dispatcher → 8 writers → assembler)
4. **Figure 4:** PRISMA audit loop flowchart (audit → fail? → repair → re-audit)

## Tables

1. **Table 1:** Pipeline performance metrics (HLH case study)
2. **Table 2:** Extraction method comparison (regex vs haiku LLM)
3. **Table 3:** Human-in-the-loop checkpoint matrix (9 CPs with rationale)
4. **Table 4:** Automated vs expert review comparison (Hsu et al.)
5. **Table 5:** Feature comparison with existing tools

## Supplementary Materials

- S1: Full prompt templates for all agent types
- S2: PRISMA 2020 checklist (auto-generated)
- S3: Checkpoint decision log schema
- S4: Complete list of 50 included articles with extraction results
- GitHub repository: https://github.com/htlin222/robust-lit-review
