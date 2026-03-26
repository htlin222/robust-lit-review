# Key Tables for the Paper

## Table 1: Pipeline Performance Metrics (HLH Case Study)

| Metric | Value |
|--------|-------|
| Records identified (3 databases) | 897 |
| After deduplication | 783 |
| After quality filter (Q1+Q2) | 783 |
| DOIs validated | 50/50 (100%) |
| Abstracts fetched | 47/50 (94%) |
| Articles with quantitative data (haiku) | 35/50 (70%) |
| Articles included | 50 |
| Unique journals | 32 (29 Q1, 3 Q2) |
| Total word count | 12,755 |
| Unique citations | 48 |
| PRISMA 2020 audit score | 35/36 PASS |
| Extraction agents (haiku) | 5 |
| Writing agents (sonnet) | 4 |
| Repair agents (haiku) | 1 |
| PDF output size | 184 KB (40 pages) |
| Pipeline time (approx.) | ~25 minutes |

## Table 2: Extraction Method Comparison

| Metric | Regex | Haiku LLM | Improvement |
|--------|-------|-----------|-------------|
| Articles with quantitative data | 21/50 (42%) | 35/50 (70%) | +67% |
| Average richness score (/10) | 1.2 | 2.2 | +83% |
| Study type identified | 0/50 (0%) | 43/50 (86%) | New capability |
| Sample size extracted | 8/50 (16%) | 28/50 (56%) | +250% |
| Dosing information | 6/50 (12%) | 24/50 (48%) | +300% |
| p-values captured | 4/50 (8%) | 18/50 (36%) | +350% |
| Diagnostic thresholds | 5/50 (10%) | 20/50 (40%) | +300% |
| Key finding sentence | 0/50 (0%) | 47/50 (94%) | New capability |

## Table 3: Human-in-the-Loop Checkpoint Matrix

| CP | Stage | Decision | Why Human Needed | Error Cost if Wrong | Default |
|----|-------|----------|-----------------|--------------------| --------|
| 1 | Search strategy | Approve/modify query | Domain-specific terms | Entire review scope | Strategy A |
| 2 | Borderline articles | Include/exclude | Near-threshold articles | Missing evidence | Review each |
| 3 | Final article set | Approve/modify | Missing landmarks | Incomplete review | Approve |
| 4 | Thematic grouping | Approve/reorganize | Narrative structure | Weak synthesis | Approve |
| 5 | Key claims | Verify/correct | **Hallucinated statistics** | **Clinical misinformation** | All correct |
| 6 | PRISMA audit | Fix/justify N/A | Journal requirements | Desk rejection | Auto-fix |
| 7 | Cover letter | Approve/tailor | Target journal | Poor framing | Approve |
| 8 | Final preview | Approve/revise | Overall quality | Wasted submission | Render |
| 9 | Publish | Push/save local | Public release | Premature publication | Publish |

## Table 4: Automated vs Expert Review (Hsu et al. Blood 2026)

| Feature | Our Pipeline | Expert (Hsu et al.) |
|---------|-------------|---------------------|
| Word count | 12,755 | ~8,000 |
| References | 48 (100% DOI validated) | 92 (includes case reports) |
| Databases searched | 3 (Scopus, PubMed, Embase) | Not systematic |
| PRISMA checklist included | Yes (27 items) | No |
| PRISMA flow diagram | Yes (TikZ) | No |
| Diagnostic criteria (exact thresholds) | HLH-2004, HLH-2024, HScore, EULAR/ACR | HLH-2004, HLH-2024, HScore, EULAR/ACR |
| Treatment dosing (exact mg/m²) | Yes | Yes |
| Specific organisms named | Yes (all categories) | Yes (all categories) |
| IEC-HS vs CRS distinction | Yes | Yes |
| Epidemiologic data (incidence trends) | Partial | Comprehensive |
| sIL-2R/ferritin ratio | Yes (>8.6) | Yes (8.6 vs 0.7) |
| Novel pipeline agents | Yes (ELA026, itacitinib) | Yes (ELA026, tabelecleucel) |
| HLH-2024 criteria update | Yes (99% accuracy) | Yes (detailed) |
| Genetic mutations detail | PRF1, UNC13D, STX11, STXBP2, HAVCR2 | PRF1, UNC13D, STX11, STXBP2, HAVCR2, LAMP-1, RYR1 |
| Cover letter | Auto-generated | N/A (review article) |
| Time to produce | ~25 minutes | Months |
| Reproducible | Yes (pipeline state + checkpoint log) | No |

## Table 5: Feature Comparison with Existing Tools

| Capability | ASReview | Rayyan | otto-SR | LitLLM | Covidence | **Ours** |
|-----------|----------|--------|---------|--------|-----------|---------|
| Multi-DB API search | - | - | - | - | - | 3 DBs |
| Active learning screening | Yes | Partial | - | - | - | - |
| LLM screening | - | - | Yes | - | - | Haiku judge |
| Structured extraction | - | - | Yes | - | Manual | Haiku JSON |
| Full manuscript generation | - | - | - | Partial | - | **12K+ words** |
| PRISMA flow diagram | - | - | - | - | - | **TikZ** |
| PRISMA 27-item audit | - | - | - | - | - | **Auto + repair** |
| DOI validation | - | - | - | - | - | **100%** |
| Journal quality filter | - | - | - | - | - | **Q1/Q2** |
| Human-in-the-loop | Active learning | - | - | - | Workflow | **9 checkpoints** |
| Cover letter | - | - | - | - | - | **Auto** |
| Team collaboration | - | Yes | - | - | Yes | - |
| Web UI | Yes | Yes | - | Yes | Yes | CLI |
| Open source | Yes | - | - | Partial | - | **Yes** |
| CI/CD release | - | - | - | - | - | **GitHub Actions** |
