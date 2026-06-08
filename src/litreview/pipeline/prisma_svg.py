"""PRISMA flow -> standalone web SVG (no LaTeX).

The TikZ ``.sty`` is kept for the PDF path; this renders the same counts as an
inline, accessible SVG for the web. Stage labels are bilingual: both languages
are emitted as ``<text data-lang>`` and CSS hides the inactive one.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

_STAGES = [
    ("identification", {"zh": "辨識", "en": "Identification"}),
    ("screening", {"zh": "篩選", "en": "Screening"}),
    ("eligibility", {"zh": "符合資格", "en": "Eligibility"}),
    ("included", {"zh": "納入", "en": "Included"}),
]


def _bilingual_text(x: int, y: int, label: dict[str, str], cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    zh = escape(label.get("zh", ""))
    en = escape(label.get("en", ""))
    return (
        f'<text x="{x}" y="{y}"{cls_attr} text-anchor="middle">'
        f'<tspan data-lang="zh">{zh}</tspan>'
        f'<tspan data-lang="en">{en}</tspan>'
        f"</text>"
    )


def build_prisma_svg(prisma: dict) -> str:
    """Return an inline SVG string for a PICO's PRISMA flow.

    ``prisma`` keys: identification, screening, eligibility, included, and an
    optional ``excluded`` map (e.g. {"screening": N, "eligibility": M}).
    """
    excluded = prisma.get("excluded", {}) or {}
    box_w, box_h, gap = 220, 64, 40
    x_main = 30
    x_excl = x_main + box_w + 70
    excl_w = 200
    height = len(_STAGES) * (box_h + gap) + gap
    width = x_excl + excl_w + 30

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" class="prisma-flow">',
        "<title>PRISMA flow diagram</title>",
        '<desc>Records through identification, screening, eligibility and inclusion.</desc>',
    ]

    y = gap
    centers: list[int] = []
    for key, label in _STAGES:
        count = int(prisma.get(key, 0) or 0)
        cy = y + box_h // 2
        centers.append(cy)
        parts.append(
            f'<rect x="{x_main}" y="{y}" width="{box_w}" height="{box_h}" rx="8" '
            f'class="prisma-box" fill="none" stroke="currentColor"/>'
        )
        parts.append(_bilingual_text(x_main + box_w // 2, cy - 6, label, cls="prisma-stage"))
        parts.append(
            f'<text x="{x_main + box_w // 2}" y="{cy + 16}" text-anchor="middle" '
            f'class="prisma-count">n = {count}</text>'
        )

        # Exclusion side-box (between screening->eligibility and eligibility->included)
        excl_n = excluded.get(key)
        if excl_n:
            ey = y + box_h + gap // 2 - 18
            parts.append(
                f'<rect x="{x_excl}" y="{ey}" width="{excl_w}" height="44" rx="6" '
                f'class="prisma-excl" fill="none" stroke="currentColor"/>'
            )
            parts.append(
                _bilingual_text(
                    x_excl + excl_w // 2, ey + 19,
                    {"zh": "排除", "en": "Excluded"}, cls="prisma-excl-label",
                )
            )
            parts.append(
                f'<text x="{x_excl + excl_w // 2}" y="{ey + 36}" text-anchor="middle" '
                f'class="prisma-count">n = {int(excl_n)}</text>'
            )
            parts.append(
                f'<line x1="{x_main + box_w}" y1="{cy}" x2="{x_excl}" y2="{ey + 22}" '
                f'class="prisma-arrow" stroke="currentColor"/>'
            )

        y += box_h + gap

    # Vertical arrows between stacked boxes
    for top, bottom in zip(centers, centers[1:]):
        parts.append(
            f'<line x1="{x_main + box_w // 2}" y1="{top + box_h // 2}" '
            f'x2="{x_main + box_w // 2}" y2="{bottom - box_h // 2}" '
            f'class="prisma-arrow" stroke="currentColor" marker-end="url(#prisma-arrowhead)"/>'
        )

    parts.append(
        '<defs><marker id="prisma-arrowhead" markerWidth="8" markerHeight="8" '
        'refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/>'
        "</marker></defs>"
    )
    parts.append("</svg>")
    return "".join(parts)
