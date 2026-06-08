"""Render a ClaimAppraisal (appraisal.json) into the verdict-style static site.

Headless: the same upstream appraisal.json drives both this web renderer and the
Quarto print path. The site is a single page with all four writeup variants
(pro/lay x zh/en) in the DOM; JS toggles visibility. PRISMA is an inline SVG.

CLI: ``lit-review build-site appraisal.json -o output/site``
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from litreview.pipeline.prisma_svg import build_prisma_svg

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "templates" / "web"

_HEADERS = """/*
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:
/assets/*
  Cache-Control: public, max-age=31536000, immutable
"""

_REQUIRED_TOP_KEYS = ("claim", "disclaimer", "pico", "references")


def _validate(data: dict) -> None:
    missing = [k for k in _REQUIRED_TOP_KEYS if k not in data]
    if missing:
        raise ValueError(f"appraisal.json missing required keys: {missing}")
    if not isinstance(data["pico"], list) or not data["pico"]:
        raise ValueError("appraisal.json 'pico' must be a non-empty list")


def render_site(
    appraisal_path: Path,
    output_dir: Path,
    template_dir: Path | None = None,
) -> Path:
    """Render *appraisal_path* into ``output_dir`` and return the index path."""
    template_dir = template_dir or _TEMPLATE_DIR
    data = json.loads(Path(appraisal_path).read_text(encoding="utf-8"))
    _validate(data)

    # Pre-compute the PRISMA SVG for each PICO (template stays logic-light).
    for pico in data["pico"]:
        pico["prisma_svg"] = build_prisma_svg(pico.get("prisma", {}))

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # The PRISMA SVG is pre-escaped, trusted markup we generated ourselves.
    env.filters["safe_svg"] = lambda s: s
    template = env.get_template("site.html.j2")
    html = template.render(a=data)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    index = output_dir / "index.html"
    index.write_text(html, encoding="utf-8")

    # Copy static assets
    assets_src = template_dir / "assets"
    if assets_src.is_dir():
        assets_dst = output_dir / "assets"
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)

    # Cloudflare Pages headers
    (output_dir / "_headers").write_text(_HEADERS, encoding="utf-8")

    logger.info("Rendered site -> %s (%d PICO sections)", index, len(data["pico"]))
    return index
