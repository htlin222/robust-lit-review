---
name: claim-appraise
description: Appraise a CLAIM (e.g. a popular diet or health product) — decompose into PICO sub-questions, run a Q1/post-2016/CrossRef-verified systematic review per question, GRADE each, cross-check with OpenEvidence, and ship a verdict-style bilingual site to Cloudflare Pages.
user_invocable: true
---

# Claim Appraisal Workflow (`/claim-appraise`)

You are turning ONE real-world **claim** into a defensible, peer-checkable evidence
appraisal. Unlike `/lit-review` (which reviews a *topic* into a manuscript), this
**adjudicates a claim** and renders a *verdict* per sub-question.

Worked example shipped with this repo: the **4+2R 代謝飲食法** appraisal →
<https://verdict-4plus2r-sr.pages.dev/>.

## When to use
"Is <X> legit?", "appraise the <X> diet/supplement/protocol", "fact-check this health claim".

## Hard quality gates (non-negotiable)
- Literature **≥ 2016** and **Q1 journals only** (`assess_journal_quality(strict=True)` + `filter_by_year`).
- Every DOI resolved via doi.org **and CrossRef-verified to exist** (`utils/crossref.py`) — the anti-hallucination gate. Never cite a work CrossRef can't confirm.
- Per sub-question **GRADE** certainty (recomputed deterministically, LLM rating is advisory).
- **OpenEvidence** cross-check where the relay is available (non-fatal if not).
- Overall verdict logic **audited with `/argdown`** before wording ships.
- Attach the **claim's primary source URL** so peers can confirm no 斷章取義 (cherry-picking).

## Steps

1. **Identify the real claims.** Read the claim's PRIMARY source (official site / book), not secondary blogs. Enumerate every distinct sub-claim. Save the source URL(s).

2. **Decompose into PICO sub-questions** — one per distinct outcome domain (efficacy AND safety AND any over-extended claims). See `scripts/run_4plus2r.py` for the `PICOQuestion` shape. Get the list approved before searching (wrong PICOs waste the run).

3. **Run the per-PICO SR** (real API search; needs `.env` keys). For each PICO:
   `ClaimAppraisalPipeline.run_pico_search` → Scopus+PubMed+Embase → dedup → year≥2016 → Q1-strict → DOI-validate → CrossRef-verify → `PicoPrismaFlow` + included studies. Drive it like `scripts/run_4plus2r.py` (saves `output/<claim>/pico_NN.json`).

4. **Write one chapter per PICO** following `output/4plus2r/CHAPTER_SPEC.md`: dispatch a subagent per chapter that reads only its `pico_NN.json`, selects the most relevant HUMAN studies (flag animal/in-vitro as 機轉假說), assigns a **verdict chip** (`vc-strong/moderate/weak/contra/risk/unproven`) and **GRADE pips**, and cites via `<cite class="ref" data-doi="DOI">`. NEVER invent a citation.

5. **GRADE + OpenEvidence cross-check** per PICO (`grade_judge.py`, `crosscheck.py`). On OE `disagree`, cap confidence and surface dissent. If the OE browser-relay is down, mark cross-check pending — do not fabricate.

6. **Synthesize** the executive summary (verdict table), methods (PRISMA totals), and overall verdict. **Audit the overall verdict argument with `/argdown`** — confirm the conclusion follows and excludes the obvious overreaches.

7. **Render + deploy.** Assemble references (DOI→number, AMA, CrossRef/PubMed/OE badges) and render with `blueprint_renderer.py` (reuses the verdict-site `style.css`/`app.js`). Build like `scripts/build_4plus2r_site.py`, then:
   `wrangler pages deploy output/<site> --project-name=<name> --branch=main`.

## Key files (reuse, don't rewrite)
- `src/litreview/pipeline/claim_orchestrator.py` — per-PICO pipeline + assembly
- `src/litreview/pipeline/{claim_decomposer,grade_judge,crosscheck,verdict_builder}.py`
- `src/litreview/utils/crossref.py` — existence gate
- `src/litreview/pipeline/blueprint_renderer.py` + `templates/blueprint/` — verdict-style site
- `scripts/run_4plus2r.py`, `scripts/build_4plus2r_site.py` — runnable templates
- `output/4plus2r/CHAPTER_SPEC.md` — chapter authoring contract

## Scale it — dynamic workflow (optional)
For many claims or many PICOs, the parallel fan-out (Steps 3–5) can run as the
bundled **dynamic workflow** `.claude/workflows/claim-appraise.js` (background,
resumable, with adversarial verify per verdict). Two-phase hybrid, because a
workflow can't prompt mid-run:
- **Phase A (this skill):** research the primary source → decompose → approve PICOs → write `output/<slug>/picos.json`.
- **Phase B (workflow):** `ultracode: run the claim-appraise workflow for <slug>` (needs Claude Code ≥ v2.1.154 + the `ultracode` opt-in). Agents call `scripts/run_one_pico.py`, GRADE, verify, and write chapters.
- **Phase C (this skill):** synthesis chapters → `/argdown` audit → render → deploy.
Allowlist `wrangler`/`uv`/`scripts/*` (see `.claude/settings.local.json`) so the workflow agents don't stall on prompts.

## Output
A bilingual, dual-audience (專業/民眾) verdict site on Cloudflare Pages, plus the
per-PICO `pico_NN.json` evidence (every study Q1 · ≥2016 · CrossRef-verified).
The renderer emits an OG share-card (`assets/og-image.png`, 1200×630) for link previews.
