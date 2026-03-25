"""LLM-as-judge for PRISMA 2020 audit.

Replaces keyword matching with haiku subagent evaluation.
Each PRISMA item is judged by a haiku agent reading the actual section text.

Usage from SKILL.md:
1. Python: tasks = generate_judge_tasks(sections_dir, output_dir)
2. Claude Code: dispatch each task as Agent(model="haiku", prompt=task.prompt)
3. Python: results = collect_judge_results(output_dir)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from litreview.pipeline.prisma_audit import PRISMA_ITEMS, AuditItem, _generate_fix_instruction
from litreview.utils.llm import SubagentTask, parse_json_result

logger = logging.getLogger(__name__)

JUDGE_PROMPT_TEMPLATE = """You are a PRISMA 2020 compliance reviewer.

Evaluate whether this manuscript section adequately addresses the following PRISMA item:

**PRISMA Item {number} ({section}):**
{description}

**Manuscript text to evaluate:**
---
{section_text}
---

Respond ONLY with this JSON (no markdown):
{{
  "item_number": "{number}",
  "status": "<pass|partial|fail>",
  "evidence": "<Quote or describe the specific text that addresses this item, or explain why it fails>",
  "suggestion": "<If partial or fail: specific text to add. If pass: empty string>"
}}

Judging criteria:
- PASS: The item is clearly and explicitly addressed with sufficient detail
- PARTIAL: The item is mentioned but lacks specificity or completeness
- FAIL: The item is not addressed at all in the provided text"""


def generate_judge_tasks(
    sections_dir: Path,
    output_dir: Path,
) -> list[SubagentTask]:
    """Generate haiku subagent tasks for PRISMA judging.

    Groups items by section file and creates one task per batch
    to minimize agent count (typically 5-6 agents instead of 36).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read section files
    file_contents: dict[str, str] = {}
    for qmd_file in sections_dir.glob("*.qmd"):
        file_contents[qmd_file.name] = qmd_file.read_text(encoding="utf-8")
    main_qmd = sections_dir.parent / "literature_review.qmd"
    if main_qmd.exists():
        file_contents["literature_review.qmd"] = main_qmd.read_text(encoding="utf-8")

    # Group items by primary section file
    file_items: dict[str, list[AuditItem]] = {}
    for item in PRISMA_ITEMS:
        primary_file = item.required_in[0] if item.required_in else "02-methods.qmd"
        file_items.setdefault(primary_file, []).append(item)

    tasks = []
    for filename, items in file_items.items():
        section_text = file_contents.get(filename, "")
        if not section_text:
            continue

        # Truncate very long sections to fit haiku context
        if len(section_text) > 8000:
            section_text = section_text[:8000] + "\n[...truncated...]"

        # Build batch prompt for all items in this file
        item_prompts = []
        for item in items:
            item_prompts.append(
                f"Item {item.number} ({item.section}): {item.description}"
            )

        output_path = output_dir / f"judge_{filename}.json"

        prompt = (
            f"You are a PRISMA 2020 compliance reviewer.\n\n"
            f"Evaluate whether the following manuscript section adequately addresses "
            f"each of the PRISMA items listed below.\n\n"
            f"**Manuscript section ({filename}):**\n---\n{section_text}\n---\n\n"
            f"**PRISMA items to evaluate:**\n"
            + "\n".join(f"- {p}" for p in item_prompts)
            + "\n\n"
            f"Respond ONLY with a JSON array (no markdown). One object per item:\n"
            f'[{{"item_number": "1", "status": "pass|partial|fail", '
            f'"evidence": "quote or explanation", '
            f'"suggestion": "what to add if partial/fail, empty if pass"}}]\n\n'
            f"Write the JSON result to: {output_path}"
        )

        tasks.append(SubagentTask(
            task_id=f"judge_{filename}",
            description=f"PRISMA judge: {filename[:25]}",
            prompt=prompt,
            output_path=output_path,
            model="haiku",
        ))

    logger.info(f"Generated {len(tasks)} PRISMA judge tasks for haiku agents")
    return tasks


def collect_judge_results(output_dir: Path) -> list[AuditItem]:
    """Collect and parse results from haiku judge agents.

    Returns list of AuditItems with LLM-determined status.
    """
    all_results: dict[str, AuditItem] = {}

    # Initialize with all items
    for item in PRISMA_ITEMS:
        all_results[item.number] = AuditItem(
            number=item.number,
            section=item.section,
            description=item.description,
            required_in=item.required_in,
            check_keywords=item.check_keywords,
            status="unchecked",
        )

    # Parse judge results
    for result_path in sorted(output_dir.glob("judge_*.json")):
        raw = parse_json_result(result_path)
        if raw is None:
            continue

        # Handle both single dict and array
        items_data = raw if isinstance(raw, list) else [raw]

        for item_data in items_data:
            number = str(item_data.get("item_number", ""))
            if number in all_results:
                audit_item = all_results[number]
                audit_item.status = item_data.get("status", "unchecked")
                audit_item.evidence = item_data.get("evidence", "")
                suggestion = item_data.get("suggestion", "")
                if suggestion and audit_item.status in ("fail", "partial"):
                    audit_item.fix_instruction = suggestion
                elif audit_item.status in ("fail", "partial"):
                    audit_item.fix_instruction = _generate_fix_instruction(audit_item)

    # Items not judged fall back to N/A for sensitivity items
    for item in all_results.values():
        if item.status == "unchecked":
            if item.number in ("13f", "20c", "20d"):
                item.status = "n/a"
                item.evidence = "Narrative synthesis — not applicable"
            else:
                item.status = "fail"
                item.evidence = "Not evaluated by judge agent"
                item.fix_instruction = _generate_fix_instruction(item)

    results = list(all_results.values())
    passed = sum(1 for i in results if i.status == "pass")
    failed = sum(1 for i in results if i.status == "fail")
    logger.info(f"LLM PRISMA audit: {passed} passed, {failed} failed")
    return results
