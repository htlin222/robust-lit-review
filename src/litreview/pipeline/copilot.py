"""Enhanced co-pilot mode for interactive literature review refinement.

Wraps the checkpoint system with:
- Real-time impact analysis of decisions
- Cross-checkpoint learning (past decisions inform suggestions)
- Iterative refinement loops
- Quality forecasting

Activates with --copilot CLI flag. Enhances every checkpoint with
contextual intelligence about the consequences of each choice.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from litreview.models import ArticleMetadata, ReviewStatistics
from litreview.pipeline.checkpoints import Checkpoint, CheckpointID, CheckpointLog
from litreview.pipeline.enrichment import classify_article_subtopic

logger = logging.getLogger(__name__)


@dataclass
class ImpactSnapshot:
    """Snapshot of pipeline state for impact comparison."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    article_count: int = 0
    subtopic_distribution: dict[str, int] = field(default_factory=dict)
    avg_citescore: float = 0.0
    avg_citations: float = 0.0
    year_range: str = ""
    coverage_gaps: list[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0-100 estimated review quality


@dataclass
class CopilotDecision:
    """Record of a co-pilot assisted decision."""

    checkpoint_id: str
    choice_key: str
    impact_before: ImpactSnapshot
    impact_after: ImpactSnapshot
    reasoning: str = ""
    refinement_count: int = 0


class CopilotContext:
    """Accumulated pipeline state across checkpoints.

    Provides impact analysis, cross-checkpoint hints, and quality forecasting.
    """

    def __init__(self, topic: str):
        self.topic = topic
        self._decisions: list[CopilotDecision] = []
        self._article_pool: list[ArticleMetadata] = []
        self._snapshots: list[ImpactSnapshot] = []
        self._checkpoint_log = CheckpointLog(topic=topic)

    @property
    def decisions(self) -> list[CopilotDecision]:
        return self._decisions

    def update_article_pool(self, articles: list[ArticleMetadata]) -> None:
        """Update the current article pool after a pipeline stage."""
        self._article_pool = articles
        self._snapshots.append(self._take_snapshot(articles))

    def _take_snapshot(self, articles: list[ArticleMetadata]) -> ImpactSnapshot:
        """Take a snapshot of the current pipeline state."""
        if not articles:
            return ImpactSnapshot()

        # Subtopic distribution
        subtopic_dist: dict[str, int] = {}
        for article in articles:
            categories = article.subtopic_categories or classify_article_subtopic(article)
            for cat in categories:
                subtopic_dist[cat] = subtopic_dist.get(cat, 0) + 1

        # Important categories that should be represented
        important_categories = [
            "epidemiology", "pathogenesis", "diagnosis", "treatment_conventional",
            "treatment_targeted", "prognosis", "genetics",
        ]
        coverage_gaps = [c for c in important_categories if subtopic_dist.get(c, 0) == 0]

        # Year range
        years = [a.year for a in articles if a.year]
        year_range = f"{min(years)}-{max(years)}" if years else ""

        # Quality metrics
        citescores = [a.citescore for a in articles if a.citescore]
        citations = [a.citation_count for a in articles if a.citation_count]

        return ImpactSnapshot(
            article_count=len(articles),
            subtopic_distribution=subtopic_dist,
            avg_citescore=sum(citescores) / len(citescores) if citescores else 0.0,
            avg_citations=sum(citations) / len(citations) if citations else 0.0,
            year_range=year_range,
            coverage_gaps=coverage_gaps,
            quality_score=_estimate_quality_score(articles, subtopic_dist, coverage_gaps),
        )

    def impact_analysis(
        self,
        checkpoint: Checkpoint,
        choice_key: str,
        simulated_articles: list[ArticleMetadata] | None = None,
    ) -> str:
        """Compute the impact of selecting a specific choice.

        Returns formatted markdown showing how this choice changes the pipeline state.
        """
        current = self._take_snapshot(self._article_pool)
        simulated = self._take_snapshot(simulated_articles or self._article_pool)

        lines = [
            f"### Impact of selecting **{choice_key}**:",
            "",
            "| Metric | Current | After |",
            "|--------|---------|-------|",
            f"| Articles | {current.article_count} | {simulated.article_count} |",
            f"| Avg CiteScore | {current.avg_citescore:.1f} | {simulated.avg_citescore:.1f} |",
            f"| Avg Citations | {current.avg_citations:.0f} | {simulated.avg_citations:.0f} |",
            f"| Year Range | {current.year_range} | {simulated.year_range} |",
            f"| Coverage Gaps | {len(current.coverage_gaps)} | {len(simulated.coverage_gaps)} |",
            f"| Quality Score | {current.quality_score:.0f}/100 | {simulated.quality_score:.0f}/100 |",
        ]

        # Subtopic changes
        all_cats = set(current.subtopic_distribution) | set(simulated.subtopic_distribution)
        changed_cats = [
            c for c in all_cats
            if current.subtopic_distribution.get(c, 0) != simulated.subtopic_distribution.get(c, 0)
        ]
        if changed_cats:
            lines.extend(["", "**Subtopic changes:**"])
            for cat in sorted(changed_cats):
                before = current.subtopic_distribution.get(cat, 0)
                after = simulated.subtopic_distribution.get(cat, 0)
                delta = after - before
                symbol = "+" if delta > 0 else ""
                lines.append(f"- {cat}: {before} -> {after} ({symbol}{delta})")

        # Coverage gap warnings
        new_gaps = set(simulated.coverage_gaps) - set(current.coverage_gaps)
        if new_gaps:
            lines.extend(["", f"**Warning:** New coverage gaps: {', '.join(new_gaps)}"])

        resolved_gaps = set(current.coverage_gaps) - set(simulated.coverage_gaps)
        if resolved_gaps:
            lines.extend(["", f"**Improvement:** Resolved gaps: {', '.join(resolved_gaps)}"])

        return "\n".join(lines)

    def cross_checkpoint_hint(self, current_cp: CheckpointID) -> str | None:
        """Generate a hint based on past checkpoint decisions.

        Uses accumulated decisions to suggest contextually-appropriate choices.
        """
        if not self._decisions:
            return None

        hints = []

        # CP2 hint based on CP1 (search strategy)
        if current_cp == CheckpointID.BORDERLINE_ARTICLES:
            cp1_decisions = [d for d in self._decisions if d.checkpoint_id == CheckpointID.SEARCH_STRATEGY.value]
            if cp1_decisions:
                last_snapshot = self._snapshots[-1] if self._snapshots else None
                if last_snapshot and last_snapshot.article_count < 40:
                    hints.append(
                        "Your search yielded fewer articles than target. "
                        "Consider **including borderline articles** (Option A) to ensure sufficient coverage."
                    )
                elif last_snapshot and last_snapshot.article_count > 80:
                    hints.append(
                        "Your search yielded many articles. "
                        "Consider **reviewing individually** (Option C) to maintain quality."
                    )

        # CP3 hint based on coverage
        if current_cp == CheckpointID.FINAL_ARTICLE_SET:
            last_snapshot = self._snapshots[-1] if self._snapshots else None
            if last_snapshot and last_snapshot.coverage_gaps:
                gaps_str = ", ".join(last_snapshot.coverage_gaps)
                hints.append(
                    f"Coverage gaps detected: **{gaps_str}**. "
                    f"Consider **Rebalance** (Option D) to improve subtopic diversity."
                )

        # CP4 hint based on article distribution
        if current_cp == CheckpointID.THEMATIC_GROUPING:
            last_snapshot = self._snapshots[-1] if self._snapshots else None
            if last_snapshot:
                dominant = max(last_snapshot.subtopic_distribution.items(), key=lambda x: x[1], default=None)
                if dominant and dominant[1] > last_snapshot.article_count * 0.4:
                    hints.append(
                        f"**{dominant[0]}** dominates ({dominant[1]} articles, "
                        f"{dominant[1]/last_snapshot.article_count*100:.0f}%). "
                        f"Consider splitting this theme into sub-themes."
                    )

        # CP5 hint
        if current_cp == CheckpointID.KEY_CLAIMS:
            hints.append(
                "Focus on verifying **dosing**, **thresholds**, and **survival rates** — "
                "these are the highest-risk claims for clinical reviews."
            )

        if hints:
            return "**Co-pilot suggestion:** " + " ".join(hints)
        return None

    def quality_forecast(self) -> str:
        """Predict review quality based on current article pool.

        Returns formatted markdown with quality predictions and warnings.
        """
        if not self._article_pool:
            return "No articles in pool — cannot forecast quality."

        snapshot = self._take_snapshot(self._article_pool)

        lines = [
            "## Quality Forecast",
            "",
            f"**Overall Score: {snapshot.quality_score:.0f}/100**",
            "",
        ]

        # Detailed breakdown
        checks = []

        # Article count check
        if snapshot.article_count >= 40:
            checks.append(("Article count", "Good", f"{snapshot.article_count} articles"))
        elif snapshot.article_count >= 25:
            checks.append(("Article count", "Acceptable", f"{snapshot.article_count} articles (target: 40-60)"))
        else:
            checks.append(("Article count", "Low", f"Only {snapshot.article_count} articles — may be insufficient"))

        # CiteScore check
        if snapshot.avg_citescore >= 5.0:
            checks.append(("Journal quality", "Excellent", f"Avg CiteScore: {snapshot.avg_citescore:.1f}"))
        elif snapshot.avg_citescore >= 3.0:
            checks.append(("Journal quality", "Good", f"Avg CiteScore: {snapshot.avg_citescore:.1f}"))
        else:
            checks.append(("Journal quality", "Below target", f"Avg CiteScore: {snapshot.avg_citescore:.1f} (target: >=3.0)"))

        # Coverage check
        if not snapshot.coverage_gaps:
            checks.append(("Subtopic coverage", "Complete", "All important subtopics represented"))
        elif len(snapshot.coverage_gaps) <= 2:
            checks.append(("Subtopic coverage", "Minor gaps", f"Missing: {', '.join(snapshot.coverage_gaps)}"))
        else:
            checks.append(("Subtopic coverage", "Significant gaps", f"Missing: {', '.join(snapshot.coverage_gaps)}"))

        # PRISMA feasibility
        checks.append(("PRISMA compliance", "Feasible", "Sufficient data for PRISMA flow"))

        # Word count estimate (rough: ~100 words per article in review)
        estimated_words = snapshot.article_count * 120
        if estimated_words >= 5000:
            checks.append(("Word count", "On target", f"Estimated ~{estimated_words:,} words"))
        else:
            checks.append(("Word count", "May be short", f"Estimated ~{estimated_words:,} words (target: 5,000-8,000)"))

        lines.append("| Check | Status | Detail |")
        lines.append("|-------|--------|--------|")
        for check, status, detail in checks:
            status_icon = {"Good": "OK", "Excellent": "OK", "Complete": "OK",
                           "On target": "OK", "Feasible": "OK", "Acceptable": "~"}.get(status, "!")
            lines.append(f"| {check} | {status_icon} {status} | {detail} |")

        return "\n".join(lines)

    def suggest_refinement(
        self,
        checkpoint: Checkpoint,
        feedback: str,
    ) -> list[str]:
        """Generate alternative options based on human feedback.

        Called when human selects "Modify" at a checkpoint.
        Returns a list of suggested refinements.
        """
        suggestions = []
        snapshot = self._take_snapshot(self._article_pool)

        if checkpoint.id == CheckpointID.SEARCH_STRATEGY:
            suggestions.extend([
                f"Broaden search: add MeSH terms for under-covered areas ({', '.join(snapshot.coverage_gaps[:3])})",
                f"Narrow search: focus on {feedback} specifically",
                "Add date restriction to focus on recent literature (2020-2026)",
            ])

        elif checkpoint.id == CheckpointID.BORDERLINE_ARTICLES:
            suggestions.extend([
                "Include only borderline articles from under-represented subtopics",
                "Include borderline articles with CiteScore > 5.0 (high-quality journals)",
                "Include borderline articles from the last 3 years (recent evidence)",
            ])

        elif checkpoint.id == CheckpointID.FINAL_ARTICLE_SET:
            if snapshot.coverage_gaps:
                suggestions.append(
                    f"Add articles specifically targeting: {', '.join(snapshot.coverage_gaps)}"
                )
            suggestions.extend([
                "Remove oldest articles (pre-2018) and replace with newer ones",
                "Replace low-citation articles with higher-impact alternatives",
                "Increase target from 50 to 60 to improve coverage",
            ])

        elif checkpoint.id == CheckpointID.THEMATIC_GROUPING:
            suggestions.extend([
                "Reorganize by clinical workflow (diagnosis → staging → treatment → monitoring)",
                "Group by evidence level (meta-analyses → RCTs → cohorts → case series)",
                f"Create dedicated section for {feedback}" if feedback else "Add a dedicated emerging trends section",
            ])

        if not suggestions:
            suggestions.append(f"Please describe what you'd like to change about: {checkpoint.title}")

        return suggestions

    def record_decision(
        self,
        checkpoint: Checkpoint,
        choice_key: str,
        articles_before: list[ArticleMetadata],
        articles_after: list[ArticleMetadata],
        reasoning: str = "",
    ) -> None:
        """Record a co-pilot assisted decision with impact data."""
        decision = CopilotDecision(
            checkpoint_id=checkpoint.id.value,
            choice_key=choice_key,
            impact_before=self._take_snapshot(articles_before),
            impact_after=self._take_snapshot(articles_after),
            reasoning=reasoning,
        )
        self._decisions.append(decision)
        self._checkpoint_log.record(checkpoint)
        self._article_pool = articles_after

        logger.info(
            f"Co-pilot decision recorded: {checkpoint.id.value} -> {choice_key} "
            f"({len(articles_before)} -> {len(articles_after)} articles)"
        )

    def save_session(self, output_dir: Path) -> None:
        """Save co-pilot session data for analysis."""
        output_dir.mkdir(parents=True, exist_ok=True)

        session_data = {
            "topic": self.topic,
            "decisions": [
                {
                    "checkpoint": d.checkpoint_id,
                    "choice": d.choice_key,
                    "reasoning": d.reasoning,
                    "articles_before": d.impact_before.article_count,
                    "articles_after": d.impact_after.article_count,
                    "quality_before": d.impact_before.quality_score,
                    "quality_after": d.impact_after.quality_score,
                }
                for d in self._decisions
            ],
            "final_quality": self._snapshots[-1].quality_score if self._snapshots else 0,
        }

        session_path = output_dir / "copilot_session.json"
        session_path.write_text(json.dumps(session_data, indent=2, ensure_ascii=False))

        # Also save the checkpoint log
        self._checkpoint_log.save(output_dir / "checkpoint_log.json")

        logger.info(f"Co-pilot session saved to {session_path}")

    def format_enhanced_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Format a checkpoint with co-pilot enhancements.

        Adds impact preview, cross-checkpoint hints, and quality forecast
        to the standard checkpoint format.
        """
        from litreview.pipeline.checkpoints import format_checkpoint_for_user

        # Standard checkpoint formatting
        base = format_checkpoint_for_user(checkpoint)

        # Add co-pilot enhancements
        enhancements = []

        # Cross-checkpoint hint
        hint = self.cross_checkpoint_hint(checkpoint.id)
        if hint:
            enhancements.append(hint)

        # Quality forecast (at key decision points)
        if checkpoint.id in (
            CheckpointID.FINAL_ARTICLE_SET,
            CheckpointID.FINAL_PREVIEW,
        ):
            enhancements.append(self.quality_forecast())

        if enhancements:
            return base + "\n\n---\n\n" + "\n\n".join(enhancements)
        return base


def _estimate_quality_score(
    articles: list[ArticleMetadata],
    subtopic_dist: dict[str, int],
    coverage_gaps: list[str],
) -> float:
    """Estimate overall review quality score (0-100)."""
    score = 0.0

    # Article count (max 25 points)
    count = len(articles)
    if count >= 50:
        score += 25
    elif count >= 30:
        score += 15 + (count - 30) * 0.5
    else:
        score += count * 0.5

    # Journal quality (max 25 points)
    citescores = [a.citescore for a in articles if a.citescore]
    if citescores:
        avg_cs = sum(citescores) / len(citescores)
        score += min(25, avg_cs * 3)

    # Subtopic coverage (max 25 points)
    important = [
        "epidemiology", "pathogenesis", "diagnosis", "treatment_conventional",
        "treatment_targeted", "prognosis",
    ]
    covered = sum(1 for c in important if c in subtopic_dist)
    score += (covered / len(important)) * 25

    # Diversity (max 25 points)
    if subtopic_dist:
        n_topics = len(subtopic_dist)
        score += min(25, n_topics * 3)

    return min(100, score)
