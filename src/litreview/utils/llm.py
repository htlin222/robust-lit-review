"""Haiku subagent dispatch helpers.

This module does NOT call the Anthropic API directly.
Instead, it generates prompts and result file paths for Claude Code
to dispatch as `model: "haiku"` subagents via the Agent tool.

Architecture:
  Python generates prompt + output path
  → SKILL.md dispatches Agent(model="haiku", prompt=...)
  → Haiku writes JSON result to output path
  → Python reads and parses the result

This keeps LLM calls within Claude Code's billing/context,
avoids needing ANTHROPIC_API_KEY, and uses the cheapest model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SubagentTask:
    """A task to be dispatched to a haiku subagent."""

    task_id: str  # Unique identifier
    description: str  # Short description (3-5 words) for Agent tool
    prompt: str  # Full prompt for the subagent
    output_path: Path  # Where the subagent should write its JSON result
    model: str = "haiku"  # Model to use


def parse_json_result(output_path: Path) -> dict | None:
    """Parse a JSON result file written by a subagent."""
    if not output_path.exists():
        logger.warning(f"Subagent result not found: {output_path}")
        return None
    try:
        text = output_path.read_text(encoding="utf-8").strip()
        # Handle case where agent wrote markdown-wrapped JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
        return json.loads(text)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse subagent result {output_path}: {e}")
        return None


def batch_parse_results(output_dir: Path, prefix: str) -> list[dict]:
    """Parse all result files matching a prefix in a directory."""
    results = []
    for path in sorted(output_dir.glob(f"{prefix}*.json")):
        data = parse_json_result(path)
        if data is not None:
            results.append(data)
    return results
