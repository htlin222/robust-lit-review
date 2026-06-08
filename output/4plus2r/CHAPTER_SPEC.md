# Chapter authoring spec — 4+2R SR appraisal (blueprint style)

You are writing ONE chapter of a Traditional-Chinese, systematic-review-grade
critical appraisal of the "4+2R 代謝飲食法". The audience toggles between
**專業人員版 (pro)** and **民眾版 (public)**. Output is an HTML fragment.

## Evidence you may cite
Read your assigned `output/4plus2r/pico_XX.json`. It contains:
- `pico`: the sub-question (population/intervention/comparator/outcome).
- `prisma`: real PRISMA counts (total_found, after_dedup, after_year_filter,
  after_quality_filter [Q1], after_validation, after_crossref, included).
- `included_studies[]`: REAL Q1, ≥2016, CrossRef-verified studies — each has
  `doi, title, authors, journal, year, quartile, citation_count, abstract`.

Rules:
- Cite ONLY studies present in that file. NEVER invent a citation or DOI.
- Select the ~6–12 most relevant studies. PRIORITISE human clinical evidence
  (RCT, cohort, meta-analysis). If a study is animal/in-vitro/preclinical, you
  may cite it ONLY to illustrate *mechanism*, and must say so explicitly
  (機轉假說，非人體證據) — this distinction is the core of a rigorous appraisal.
- Read each abstract before citing; the claim you attach must match the abstract.

## Citation syntax
Inline: `<cite class="ref" data-doi="10.xxxx/yyyy"></cite>` (empty; the build step
numbers it). Put cites right after the clause they support. Multiple allowed.

## Required chapter structure (HTML fragment, no <html>/<body>)
```
<section class="chapter" id="chX" data-title="中文章節標題">
  <h2 class="ch-title"><span class="ch-num">N</span> 中文章節標題</h2>

  <!-- the 4+2R claim this chapter tests -->
  <div class="claim-card">
    <div class="claim-head"><span class="claim-tag">4+2R 主張</span>
      <span class="verdict-chip vc-XXX">判定詞</span></div>
    <p class="claim-text">（用一句話寫出 4+2R 對此主張的宣稱）</p>
  </div>

  <!-- our SR rigor line: PRISMA + GRADE -->
  <div class="prisma-strip">
    <div class="prisma-step"><span class="ps-n">N</span><span class="ps-l">檢索命中</span></div>
    <div class="prisma-step"><span class="ps-n">N</span><span class="ps-l">Q1 期刊</span></div>
    <div class="prisma-step"><span class="ps-n">N</span><span class="ps-l">CrossRef 驗證</span></div>
    <div class="prisma-step is-final"><span class="ps-n">N</span><span class="ps-l">納入評析</span></div>
  </div>
  <p class="sr-meta">GRADE 證據確定性：
    <span class="grade-pips gc-YYY">⊕⊕⊝⊝</span>
    <span class="grade-note">（理由：降級於 ... ）</span></p>

  <h3>證據怎麼說</h3>
  <p>... 專業敘述，帶 <cite class="ref" data-doi="..."></cite> ...</p>
  <div class="callout co-evidence"><p>關鍵證據一句話。</p></div>

  <!-- pro-only deeper methods/numbers -->
  <div class="pro-only"><span class="audience-tag">專業</span>
    <p>效應量、CI、異質性、偏誤風險等細節 <cite class="ref" data-doi="..."></cite></p>
  </div>

  <!-- public-only plain language -->
  <div class="public-only"><span class="audience-tag">民眾</span>
    <p>白話說明：這代表什麼、能不能照做。</p>
  </div>

  <div class="callout co-bottom"><p><strong>本章判定：</strong>...（為何是這個判定詞）</p></div>
</section>
```

## Verdict chips (pick the honest one)
- `vc-strong` 證據強 — consistent high/moderate-certainty human evidence supports it
- `vc-moderate` 部分成立 — real but modest/short-term, or attenuates over time
- `vc-weak` 證據薄弱 — only association / animal / surrogate; human causal weak
- `vc-contra` 與證據牴觸 — good evidence points the other way
- `vc-risk` 安全疑慮 — a safety signal needing caution
- `vc-unproven` 尚無實證 — no direct human evidence either way

## GRADE pips
`gc-high` ⊕⊕⊕⊕ · `gc-moderate` ⊕⊕⊕⊝ · `gc-low` ⊕⊕⊝⊝ · `gc-verylow` ⊕⊝⊝⊝.
Start RCT-bodies at high, observational at low; downgrade for risk of bias,
inconsistency, indirectness, imprecision, publication bias. State the reason.

## Tone
Pro: precise, quantitative, hedged. Public: plain, calm, actionable. Be
even-handed — 4+2R repackages several real mechanisms; say what holds and what
is over-claimed. Write in Traditional Chinese (zh-Hant-TW).

## Output
Write ONLY the HTML fragment to your given output path. No markdown fences.
