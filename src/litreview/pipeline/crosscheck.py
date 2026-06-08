"""OpenEvidence + PubMed cross-check per PICO.

Unlike the other LLM modules, this task instructs the dispatched agent to CALL
MCP tools (OpenEvidence + PubMed) rather than reason in isolation, then compare
their conclusion against our included evidence and draft verdict.

OpenEvidence runs through a browser relay and can be slow / rate-limited /
unavailable. Cross-check is therefore NON-FATAL: on any failure the agent writes
``agreement: "no_data"`` and the pipeline proceeds without penalty.

Usage from SKILL.md:
1. Python: task = generate_crosscheck_task(pico, included, draft_verdict, output_dir)
2. Claude Code: dispatch an agent that can reach mcp__openevidence__* and
   mcp__claude_ai_PubMed__* (load via ToolSearch if deferred).
3. Python: check = collect_crosscheck(pico, output_dir)
"""

from __future__ import annotations

import logging
from pathlib import Path

from litreview.models import ArticleMetadata, OpenEvidenceCheck, PICOQuestion
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

_VALID_AGREEMENT = ("agree", "partial", "disagree", "no_data")


def generate_crosscheck_task(
    pico: PICOQuestion,
    included_studies: list[ArticleMetadata],
    draft_verdict: str,
    output_dir: Path,
) -> SubagentTask:
    """Generate the cross-check task for one PICO."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"crosscheck_{pico.pico_id}.json"

    our_dois = [a.doi for a in included_studies if a.doi]
    our_citations = ", ".join(f"@{a.citation_key}" for a in included_studies[:25]) or "(none)"
    question = pico.question_text or pico.outcome

    prompt = (
        "You are verifying a systematic-review verdict against an independent "
        "evidence source. Use the available MCP tools (load them with ToolSearch "
        "if they are not already active):\n"
        "  1. Call mcp__openevidence__oe_ask with this question:\n"
        f'     "{question}"\n'
        "     Capture the returned article_id, the synthesized answer, and the "
        "DOIs/PMIDs it cites.\n"
        "  2. (Optional corroboration) Call mcp__claude_ai_PubMed__search_articles "
        f"with the key terms ({', '.join(pico.primary_terms[:6]) or pico.intervention}).\n\n"
        f"OUR DRAFT VERDICT for this question: {draft_verdict}\n"
        f"OUR INCLUDED STUDIES: {our_citations}\n"
        f"OUR INCLUDED DOIs: {', '.join(our_dois[:25]) or '(none)'}\n\n"
        "Compare OpenEvidence's conclusion against ours on three axes: (a) effect "
        "direction, (b) citation overlap — do OE's key references appear in our "
        "included set? non-overlap may signal a search gap, (c) certainty language.\n\n"
        "Set agreement to:\n"
        "  agree    — same direction & compatible certainty\n"
        "  partial  — same direction but notable certainty/scope difference\n"
        "  disagree — opposite direction or contradictory conclusion\n"
        "  no_data  — OpenEvidence had no relevant evidence OR the call failed\n\n"
        "If any tool call fails or returns nothing usable, set agreement to "
        '"no_data" and continue — do NOT block.\n\n'
        "Return ONLY this JSON (no markdown). Write it to: "
        f"{output_path}\n"
        "{\n"
        f'  "pico_id": "{pico.pico_id}",\n'
        f'  "question_asked": "{question}",\n'
        '  "oe_article_id": "<uuid or empty>",\n'
        '  "oe_verdict_text": "<OE synthesized answer, trimmed>",\n'
        '  "oe_citations": ["<doi or pmid>"],\n'
        '  "agreement": "agree|partial|disagree|no_data",\n'
        '  "discrepancy_notes": "<what differs, citation overlap notes>",\n'
        '  "pubmed_corroboration": "<one line from the PubMed sanity check, or empty>"\n'
        "}"
    )

    return SubagentTask(
        task_id=f"crosscheck_{pico.pico_id}",
        description=f"OE cross-check: {pico.outcome_domain[:18]}",
        prompt=prompt,
        output_path=output_path,
        model="sonnet",
    )


def collect_crosscheck(pico: PICOQuestion, output_dir: Path) -> OpenEvidenceCheck:
    """Parse the cross-check result; default to no_data on any problem."""
    output_path = output_dir / f"crosscheck_{pico.pico_id}.json"
    raw = parse_json_result(output_path)

    if raw is None or not isinstance(raw, dict):
        logger.info("No cross-check result for %s (non-fatal)", pico.pico_id)
        return OpenEvidenceCheck(
            pico_id=pico.pico_id,
            question_asked=pico.question_text or pico.outcome,
            agreement="no_data",
        )

    agreement = str(raw.get("agreement", "no_data")).lower()
    if agreement not in _VALID_AGREEMENT:
        agreement = "no_data"

    return OpenEvidenceCheck(
        pico_id=pico.pico_id,
        question_asked=str(raw.get("question_asked", pico.question_text or pico.outcome)),
        oe_article_id=(str(raw["oe_article_id"]) if raw.get("oe_article_id") else None),
        oe_verdict_text=str(raw.get("oe_verdict_text", "")),
        oe_citations=[str(c) for c in raw.get("oe_citations", []) if c],
        agreement=agreement,
        discrepancy_notes=str(raw.get("discrepancy_notes", "")),
        pubmed_corroboration=str(raw.get("pubmed_corroboration", "")),
    )
