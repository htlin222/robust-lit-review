"""Human-in-the-Loop checkpoint system.

When enabled, the pipeline pauses at critical decision points and presents
the human with structured choices. The human's decision is recorded and
the pipeline resumes accordingly.

Design principles:
- Only pause where machine uncertainty is high OR error cost is high
- Always present as multiple-choice (not open-ended)
- Each checkpoint has a default that auto-proceeds if HITL is disabled
- Decisions are logged for reproducibility

Usage in SKILL.md:
  At each checkpoint, present the options to the user using AskUserQuestion.
  Record the response and continue the pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class CheckpointID(str, Enum):
    SEARCH_STRATEGY = "cp1_search_strategy"
    BORDERLINE_ARTICLES = "cp2_borderline_articles"
    FINAL_ARTICLE_SET = "cp3_final_article_set"
    THEMATIC_GROUPING = "cp4_thematic_grouping"
    KEY_CLAIMS = "cp5_key_claims"
    PRISMA_AUDIT = "cp6_prisma_audit"
    COVER_LETTER = "cp7_cover_letter"
    FINAL_PREVIEW = "cp8_final_preview"
    PUBLISH_DECISION = "cp9_publish_decision"


@dataclass
class Choice:
    """A single option the human can select."""

    key: str  # e.g., "A", "B", "C"
    label: str  # Short label
    description: str  # Detailed description
    is_default: bool = False  # Auto-selected if HITL disabled


@dataclass
class Checkpoint:
    """A decision point where the pipeline pauses for human input."""

    id: CheckpointID
    title: str
    why_human_needed: str  # Why machine can't decide this alone
    context: str  # What to show the human
    choices: list[Choice]
    selected: str | None = None  # The human's choice key
    timestamp: str | None = None
    notes: str = ""  # Optional human notes


@dataclass
class CheckpointLog:
    """Record of all checkpoint decisions for reproducibility."""

    topic: str
    decisions: list[dict] = field(default_factory=list)

    def record(self, checkpoint: Checkpoint) -> None:
        self.decisions.append({
            "id": checkpoint.id.value,
            "title": checkpoint.title,
            "selected": checkpoint.selected,
            "timestamp": checkpoint.timestamp or datetime.now().isoformat(),
            "notes": checkpoint.notes,
        })

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({
            "topic": self.topic,
            "decisions": self.decisions,
        }, indent=2, ensure_ascii=False))


# ── Checkpoint Generators ──────────────────────────────────────────


def cp1_search_strategy(
    topic: str,
    suggested_queries: list[dict],
) -> Checkpoint:
    """CP1: Search strategy approval.

    Machine suggests 3 query strategies, human picks one or modifies.
    WHY: Wrong query = wrong articles = wrong review. High-impact decision.
    """
    choices = []
    for i, q in enumerate(suggested_queries):
        choices.append(Choice(
            key=chr(65 + i),  # A, B, C
            label=q.get("label", f"Strategy {i+1}"),
            description=f"Query: {q['query']}\nExpected results: {q.get('estimated', 'unknown')}",
            is_default=(i == 0),
        ))
    choices.append(Choice(
        key="M",
        label="Modify",
        description="I want to modify the search terms before proceeding",
    ))

    return Checkpoint(
        id=CheckpointID.SEARCH_STRATEGY,
        title="Search Strategy Approval",
        why_human_needed=(
            "The search query determines which articles enter the review. "
            "Too broad = noise, too narrow = missed evidence. "
            "A domain expert can judge whether the terms capture the right scope."
        ),
        context=f"Topic: {topic}\n\n{len(suggested_queries)} strategies generated:",
        choices=choices,
    )


def cp2_borderline_articles(
    borderline: list[dict],
) -> Checkpoint:
    """CP2: Borderline article inclusion/exclusion.

    Articles near the inclusion threshold where the machine is uncertain.
    WHY: These edge cases often determine whether important findings are included.
    """
    articles_text = []
    for i, a in enumerate(borderline):
        articles_text.append(
            f"{i+1}. [{a.get('relevance_score', '?'):.2f}] {a['title'][:80]}\n"
            f"   Journal: {a['journal']} ({a['year']}), {a['citations']} cites\n"
            f"   Why uncertain: {a.get('uncertainty_reason', 'borderline relevance score')}"
        )

    return Checkpoint(
        id=CheckpointID.BORDERLINE_ARTICLES,
        title="Borderline Articles Review",
        why_human_needed=(
            "These articles scored near the inclusion/exclusion threshold. "
            "A domain expert can judge whether they add meaningful evidence "
            "or are only tangentially related."
        ),
        context="\n\n".join(articles_text),
        choices=[
            Choice("A", "Include all", "Include all borderline articles"),
            Choice("B", "Exclude all", "Exclude all borderline articles"),
            Choice("C", "Review individually", "I'll decide each one individually", is_default=True),
        ],
    )


def cp3_final_article_set(
    articles: list[dict],
    subtopic_dist: dict[str, int],
) -> Checkpoint:
    """CP3: Final article set confirmation.

    Show the selected 50 articles with subtopic distribution.
    WHY: The human may notice missing key papers or topic imbalance.
    """
    dist_text = "\n".join(f"  {cat}: {count}" for cat, count in sorted(subtopic_dist.items(), key=lambda x: -x[1]))
    top_articles = "\n".join(
        f"  {i+1}. [{a['citations']} cites] {a['title'][:70]}"
        for i, a in enumerate(articles[:10])
    )

    return Checkpoint(
        id=CheckpointID.FINAL_ARTICLE_SET,
        title="Final Article Set Confirmation",
        why_human_needed=(
            "The final article set determines the entire review's scope. "
            "A domain expert may know of landmark papers that were missed, "
            "or notice that a critical subtopic is underrepresented."
        ),
        context=f"Selected {len(articles)} articles:\n\nSubtopic distribution:\n{dist_text}\n\nTop 10 by citations:\n{top_articles}",
        choices=[
            Choice("A", "Approve", "Proceed with this article set", is_default=True),
            Choice("B", "Add articles", "I want to add specific articles (provide DOIs)"),
            Choice("C", "Remove articles", "I want to remove specific articles"),
            Choice("D", "Rebalance", "Adjust subtopic balance (specify which topics need more/fewer)"),
        ],
    )


def cp4_thematic_grouping(
    proposed_themes: list[dict],
) -> Checkpoint:
    """CP4: Thematic grouping of results.

    Machine proposes how to organize the Results section.
    WHY: Thematic structure shapes the narrative. Expert may prefer different framing.
    """
    themes_text = "\n".join(
        f"  {i+1}. {t['name']} ({t['article_count']} articles)\n"
        f"     Key articles: {', '.join(t.get('key_articles', [])[:3])}"
        for i, t in enumerate(proposed_themes)
    )

    return Checkpoint(
        id=CheckpointID.THEMATIC_GROUPING,
        title="Results Thematic Organization",
        why_human_needed=(
            "How findings are grouped determines the review's narrative arc. "
            "The machine groups by keywords, but a domain expert knows which "
            "conceptual connections matter most for the field."
        ),
        context=f"Proposed thematic structure:\n\n{themes_text}",
        choices=[
            Choice("A", "Approve structure", "Use this thematic organization", is_default=True),
            Choice("B", "Merge themes", "Some themes should be combined"),
            Choice("C", "Split themes", "Some themes should be split into subtopics"),
            Choice("D", "Reorder", "Change the order of themes"),
            Choice("E", "Propose new", "I want a completely different organization"),
        ],
    )


def cp5_key_claims(
    section_claims: list[dict],
) -> Checkpoint:
    """CP5: Key claims verification.

    Top 3 factual claims per section for human to verify.
    WHY: LLM can hallucinate or misinterpret statistical findings.
    Error cost is highest here — wrong clinical numbers could mislead.
    """
    claims_text = []
    for sec in section_claims:
        claims_text.append(f"**{sec['section']}:**")
        for j, claim in enumerate(sec['claims'][:3]):
            claims_text.append(
                f"  {j+1}. \"{claim['text'][:100]}\"\n"
                f"     Source: @{claim['citation_key']} — {claim.get('verification', 'unverified')}"
            )
    claims_text = "\n".join(claims_text)

    return Checkpoint(
        id=CheckpointID.KEY_CLAIMS,
        title="Key Claims Verification",
        why_human_needed=(
            "These are the most important factual claims in the manuscript. "
            "LLMs can misstate statistics, invert findings, or cite the wrong source. "
            "A domain expert should verify that critical numbers "
            "(dosing, thresholds, survival rates, p-values) are accurate."
        ),
        context=claims_text,
        choices=[
            Choice("A", "All correct", "I've verified these claims and they are accurate", is_default=True),
            Choice("B", "Some errors", "I found errors that need correction (I'll specify)"),
            Choice("C", "Need to check", "I need to check these against the original papers first"),
        ],
    )


def cp6_prisma_audit(
    audit_summary: str,
    failed_items: list[dict],
) -> Checkpoint:
    """CP6: PRISMA audit results.

    Show failed/partial items and let human decide how to handle.
    WHY: Some items may be legitimately N/A for the review type,
    but only a human can judge whether that's acceptable for the target journal.
    """
    return Checkpoint(
        id=CheckpointID.PRISMA_AUDIT,
        title="PRISMA 2020 Audit Results",
        why_human_needed=(
            "Some PRISMA items may not apply to this specific review type. "
            "The human should decide whether to fix gaps or justify them as N/A. "
            "Target journal requirements vary."
        ),
        context=audit_summary,
        choices=[
            Choice("A", "Auto-fix all", "Dispatch repair agents to fix all gaps", is_default=True),
            Choice("B", "Fix some, skip others", "I'll specify which to fix and which to mark N/A"),
            Choice("C", "Accept as-is", "The current audit score is acceptable for my target journal"),
        ],
    )


def cp7_cover_letter(
    letter_preview: str,
    topic: str,
) -> Checkpoint:
    """CP7: Cover letter review.

    WHY: Target journal selection affects the letter's framing.
    The human may want to emphasize different aspects.
    """
    return Checkpoint(
        id=CheckpointID.COVER_LETTER,
        title="Cover Letter Review",
        why_human_needed=(
            "The cover letter frames why the journal should publish this review. "
            "Only the author knows which journal they're targeting and what angle "
            "would appeal to that journal's editors."
        ),
        context=f"Topic: {topic}\n\nDraft cover letter (first 500 chars):\n{letter_preview[:500]}...",
        choices=[
            Choice("A", "Approve", "Cover letter is ready", is_default=True),
            Choice("B", "Change target journal", "I want to tailor it for a specific journal"),
            Choice("C", "Edit emphasis", "I want to emphasize different contributions"),
            Choice("D", "Add co-authors", "I need to add co-author information"),
        ],
    )


def cp8_final_preview(
    word_count: int,
    citation_count: int,
    prisma_score: str,
) -> Checkpoint:
    """CP8: Final manuscript preview before rendering.

    WHY: Last chance to catch major issues before the PDF is generated.
    """
    return Checkpoint(
        id=CheckpointID.FINAL_PREVIEW,
        title="Final Manuscript Preview",
        why_human_needed=(
            "This is the final quality gate before the manuscript is rendered. "
            "The human should spot-check the overall structure, word count, "
            "and citation coverage."
        ),
        context=(
            f"Word count: {word_count:,}\n"
            f"Citations: {citation_count}\n"
            f"PRISMA score: {prisma_score}\n"
        ),
        choices=[
            Choice("A", "Render", "Looks good — render PDF and DOCX", is_default=True),
            Choice("B", "Review sections", "I want to read specific sections before rendering"),
            Choice("C", "Revise", "I want to request changes to specific sections"),
        ],
    )


def cp9_publish_decision(
    release_url: str = "",
) -> Checkpoint:
    """CP9: Publish decision.

    WHY: Pushing to GitHub makes it public. Human must consciously decide.
    """
    return Checkpoint(
        id=CheckpointID.PUBLISH_DECISION,
        title="Publish Decision",
        why_human_needed=(
            "Publishing creates a GitHub Release with the manuscript PDF. "
            "This is a public, permanent action. The human must confirm."
        ),
        context="Manuscript rendered successfully. Ready to publish.",
        choices=[
            Choice("A", "Publish", "Push to GitHub and create a release", is_default=True),
            Choice("B", "Save locally", "Keep files local, don't push"),
            Choice("C", "Push without release", "Push code but don't create a release tag"),
        ],
    )


# ── Format for Claude Code presentation ────────────────────────────


def format_checkpoint_for_user(cp: Checkpoint) -> str:
    """Format a checkpoint as a user-facing prompt.

    Returns markdown text that Claude Code should present via AskUserQuestion.
    """
    lines = [
        f"## Checkpoint: {cp.title}",
        "",
        f"**Why your input is needed:** {cp.why_human_needed}",
        "",
        "---",
        "",
        cp.context,
        "",
        "---",
        "",
        "**Options:**",
        "",
    ]

    for choice in cp.choices:
        default_marker = " (recommended)" if choice.is_default else ""
        lines.append(f"**{choice.key})** {choice.label}{default_marker}")
        lines.append(f"   {choice.description}")
        lines.append("")

    return "\n".join(lines)
