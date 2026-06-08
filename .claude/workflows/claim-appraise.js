export const meta = {
  name: 'claim-appraise',
  description: 'Fan-out claim appraisal: per-PICO Q1/>=2016/CrossRef SR -> GRADE -> adversarial verify -> chapter, then build + deploy the verdict site',
  phases: [
    { title: 'Search', detail: 'per-PICO Scopus+PubMed+Embase, Q1/>=2016, DOI+CrossRef verified' },
    { title: 'Grade', detail: 'GRADE certainty + verdict chip per PICO' },
    { title: 'Verify', detail: 'adversarial cross-check of each verdict (3 lenses, majority)' },
    { title: 'Write', detail: 'one blueprint chapter per PICO, citing only verified studies' },
    { title: 'Ship', detail: 'assemble AMA refs, render blueprint site, deploy to Cloudflare' },
  ],
}

// ---------------------------------------------------------------------------
// Phase B of the hybrid: the parallel per-PICO fan-out. Phase A (research the
// claim's primary source -> decompose -> approve PICOs -> write picos.json) and
// the final argdown audit happen in the /claim-appraise SKILL, where mid-run
// AskUserQuestion gates are available (a workflow cannot prompt mid-run).
//
// args: { slug, claim, project, picos: [{ pico_id, outcome_domain, claim_zh,
//          chapter_id, ch_num, title, framing }] }
//   - picos approved in Phase A and written to output/<slug>/picos.json
//   - project: the Cloudflare Pages project name to deploy to
// ---------------------------------------------------------------------------

const slug = (args && args.slug) || 'appraisal'
const claim = (args && args.claim) || slug
const project = (args && args.project) || 'verdict-appraisal'
const picos = (args && args.picos) || []

if (!picos.length) {
  log('No PICOs in args. Pass {slug, claim, project, picos:[...]} approved in Phase A (and written to output/<slug>/picos.json).')
  return { error: 'no-picos' }
}

log(`Appraising "${claim}" over ${picos.length} PICO(s) -> project ${project}`)

const SEARCH = {
  type: 'object',
  properties: {
    pico_id: { type: 'string' },
    total_found: { type: 'integer' }, q1: { type: 'integer' },
    crossref: { type: 'integer' }, included: { type: 'integer' },
  },
  required: ['pico_id', 'included'],
}
const GRADE = {
  type: 'object',
  properties: {
    pico_id: { type: 'string' },
    grade: { type: 'string', enum: ['high', 'moderate', 'low', 'very_low'] },
    verdict: { type: 'string', enum: ['vc-strong', 'vc-moderate', 'vc-weak', 'vc-contra', 'vc-risk', 'vc-unproven'] },
    effect_direction: { type: 'string', enum: ['beneficial', 'no_effect', 'harmful', 'mixed'] },
    rationale: { type: 'string' },
  },
  required: ['pico_id', 'grade', 'verdict'],
}
const VOTE = {
  type: 'object',
  properties: { lens: { type: 'string' }, holds: { type: 'boolean' }, note: { type: 'string' } },
  required: ['lens', 'holds'],
}
const WRITE = {
  type: 'object',
  properties: { pico_id: { type: 'string' }, file: { type: 'string' }, n_cited: { type: 'integer' } },
  required: ['pico_id', 'file'],
}
const SHIP = {
  type: 'object',
  properties: { url: { type: 'string' }, references: { type: 'integer' }, leftover_data_doi: { type: 'integer' } },
  required: ['url'],
}

// Per-PICO pipeline — each PICO flows through all stages independently (no barrier).
const results = await pipeline(
  picos,

  // 1. SEARCH — agent runs the real Python pipeline for this PICO
  (p) => agent(
    `Run the Q1/>=2016/CrossRef-verified systematic search for PICO "${p.pico_id}" (${p.outcome_domain}).\n` +
    `Run exactly: .venv/bin/python scripts/run_one_pico.py ${slug} ${p.pico_id}\n` +
    `Then read output/${slug}/${p.pico_id}.json and report PRISMA counts (total_found, after_quality_filter as q1, after_crossref as crossref, included).`,
    { label: `search:${p.pico_id}`, phase: 'Search', schema: SEARCH }
  ),

  // 2. GRADE — certainty + verdict chip for the 4+2R claim this PICO tests
  (search, p) => agent(
    `Read output/${slug}/${p.pico_id}.json. Assess GRADE certainty and assign a verdict chip for the claim it tests: "${p.claim_zh || p.outcome_domain}".\n` +
    `${p.framing || ''}\n` +
    `Prioritise HUMAN clinical evidence; treat animal/in-vitro as mechanism only. Recompute certainty honestly. Return {pico_id, grade, verdict, effect_direction, rationale}.`,
    { label: `grade:${p.pico_id}`, phase: 'Grade', schema: GRADE }
  ),

  // 3. VERIFY — three independent skeptics; keep verdict only if a majority holds
  (grade, p) => parallel(
    ['correctness', 'indirectness', 'publication-bias'].map((lens) => () =>
      agent(
        `Adversarially scrutinise the verdict "${grade.verdict}" (GRADE ${grade.grade}) for PICO ${p.pico_id}, via the ${lens} lens, reading output/${slug}/${p.pico_id}.json. Default to holds=false if the evidence does not clearly support it. Return {lens, holds, note}.`,
        { label: `verify:${p.pico_id}:${lens}`, phase: 'Verify', schema: VOTE }
      )
    )
  ).then((votes) => {
    const ok = votes.filter(Boolean)
    const confirmed = ok.filter((v) => v.holds).length >= 2
    return { ...grade, votes: ok, confirmed }
  }),

  // 4. WRITE — one blueprint chapter, citing only verified studies by DOI
  (verified, p) => agent(
    `Write the chapter for PICO ${p.pico_id} following output/${slug}/CHAPTER_SPEC.md EXACTLY.\n` +
    `Cite ONLY studies in output/${slug}/${p.pico_id}.json via <cite class="ref" data-doi="DOI">. Never invent a citation.\n` +
    `Use chapter id "${p.chapter_id || p.pico_id}", ch-num "${p.ch_num || ''}", title "${p.title || ''}", verdict chip ${verified.verdict}, GRADE ${verified.grade}.\n` +
    `${verified.confirmed ? '' : 'NOTE: adversarial verify did NOT confirm this verdict — soften wording and state the uncertainty.'}\n` +
    `Write the HTML fragment (no fences) to output/${slug}/chapters_src/${p.chapter_id || p.pico_id}.html. Return {pico_id, file, n_cited}.`,
    { label: `write:${p.pico_id}`, phase: 'Write', schema: WRITE }
  )
)

// SHIP — assemble + render + deploy (one agent; the script itself cannot run shell)
phase('Ship')
const written = results.filter(Boolean)
log(`${written.length}/${picos.length} chapters written; assembling + deploying`)

const ship = await agent(
  `All per-PICO chapters are under output/${slug}/chapters_src/. Synthesis chapters (summary/methods/verdict) and the argdown audit are handled in the SKILL — assume they exist or skip if absent.\n` +
  `1. Build: .venv/bin/python scripts/build_4plus2r_site.py  (the 4+2R worked example; for another slug, adapt BASE/OUT/ORDER).\n` +
  `2. Verify: 0 leftover "data-doi" in output/site_${slug}/assets/chapters.js and all references resolved (no "unresolved DOI").\n` +
  `3. Deploy: wrangler pages deploy output/site_${slug} --project-name=${project} --branch=main --commit-dirty=true\n` +
  `Report {url, references, leftover_data_doi}.`,
  { label: 'ship', phase: 'Ship', schema: SHIP }
)

return { slug, claim, picos: written, verdicts: results.filter(Boolean), ship }
