"""Render the claim appraisal into the 4+2R blueprint static site.

Reuses the original site's style.css + app.js + citation/TOC/mode machinery
(templates/blueprint/), and feeds it our SR data: chapter HTML fragments +
an AMA reference list. The renderer is mechanical — chapter prose is authored
upstream (by the SR writers); this just assembles the deployable site.

Output layout (Cloudflare-Pages-ready):
  index.html
  chapters/<id>.html        (one per chapter, fetched by app.js)
  assets/style.css, app.js, sr-supplement.css
  assets/chapters.js        (window.__CHAPTER_LIST__ + __CHAPTERS__ fallback)
  assets/references.js      (window.__REFS__)
  _headers
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_BLUEPRINT = Path(__file__).resolve().parents[3] / "templates" / "blueprint"

_HEADERS = """/*
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
/assets/*
  Cache-Control: public, max-age=31536000, immutable
"""


@dataclass
class Chapter:
    id: str           # e.g. "ch0"
    file: str         # e.g. "chapters/00-summary.html"
    html: str         # full <section class="chapter">...</section>


@dataclass
class SiteMeta:
    title: str = "4+2R 代謝飲食法 — 系統性文獻評析 (SR)"
    brand_strong: str = "4+2R 代謝飲食法 · 系統性評析"
    brand_small: str = "Systematic-review-grade critical appraisal"
    description: str = ""
    base_url: str = "https://verdict-4plus2r-sr.pages.dev"
    og_title: str = "「4+2R 代謝飲食法」系統性文獻評析"
    og_description: str = "九大主張，1056 篇檢索 → 165 篇 Q1（≥2016）逐篇 CrossRef 驗證 → GRADE → /argdown 稽核。專業／民眾雙版本。"
    gen_date: str = "2026-06-09"
    source_badges: list[str] = field(default_factory=lambda: [
        "Scopus · PubMed · Embase", "Q1 · ≥2016", "CrossRef-verified",
        "GRADE-style", "OpenEvidence 對照", "AMA",
    ])
    ref_note_html: str = (
        '本評析的文獻均為 <strong>Q1 期刊、2016 年後</strong>，'
        '並逐篇經 <strong>CrossRef</strong> 確認存在（防杜虛構引用），'
        'DOI 經 doi.org 解析。點擊內文 <span class="cite-demo">[1]</span> 可跳至對應文獻。'
    )
    footer_html: str = (
        '<p>本報告為實證文獻評析，<strong>非個別醫療建議</strong>。'
        '減重前（尤其有慢性腎臟病、膽道疾病、孕哺、糖尿病用藥者）請諮詢醫師。</p>'
    )


def _shell(meta: SiteMeta) -> str:
    badges = "\n        ".join(
        f'<span class="src-badge">{b}</span>' for b in meta.source_badges
    )
    return f"""<!doctype html>
<html lang="zh-Hant-TW">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{meta.title}</title>
  <meta name="description" content="{meta.description}" />
  <link rel="canonical" href="{meta.base_url}/" />

  <meta property="og:type" content="article" />
  <meta property="og:locale" content="zh_TW" />
  <meta property="og:site_name" content="實證醫學評析" />
  <meta property="og:title" content="{meta.og_title}" />
  <meta property="og:description" content="{meta.og_description}" />
  <meta property="og:url" content="{meta.base_url}/" />
  <meta property="og:image" content="{meta.base_url}/assets/og-image.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="{meta.og_title}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{meta.og_title}" />
  <meta name="twitter:description" content="{meta.og_description}" />
  <meta name="twitter:image" content="{meta.base_url}/assets/og-image.png" />

  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%230e7c86'/%3E%3Ctext x='32' y='42' font-family='Arial,sans-serif' font-size='24' font-weight='900' fill='white' text-anchor='middle'%3ESR%3C/text%3E%3C/svg%3E" />
  <link rel="stylesheet" href="assets/style.css" />
  <link rel="stylesheet" href="assets/sr-supplement.css" />
</head>
<body class="mode-pro">
  <a class="skip-link" href="#main">跳至內容</a>

  <header class="topbar">
    <div class="topbar-inner">
      <button id="navToggle" class="nav-toggle" aria-label="開關目錄" aria-expanded="false">☰</button>
      <div class="brand">
        <span class="brand-mark">SR</span>
        <div class="brand-txt">
          <strong>{meta.brand_strong}</strong>
          <small>{meta.brand_small}</small>
        </div>
      </div>
      <div class="mode-switch" role="group" aria-label="閱讀版本切換">
        <button class="mode-btn is-active" data-mode="pro" aria-pressed="true">專業人員版</button>
        <button class="mode-btn" data-mode="public" aria-pressed="false">民眾版</button>
      </div>
    </div>
  </header>

  <div class="layout">
    <aside id="sidebar" class="sidebar" aria-label="章節目錄">
      <div class="sidebar-head">目錄 Contents</div>
      <nav id="toc" class="toc"></nav>
      <div class="sidebar-foot">
        {badges}
      </div>
    </aside>

    <main id="main" class="main" tabindex="-1">
      <article id="report" class="report">
        <div id="loadStatus" class="load-status">正在載入各章節…</div>
        <section id="references" class="chapter references-chapter" data-title="參考文獻">
          <h2 class="ch-title"><span class="ch-num">§</span> 參考文獻 References (AMA)</h2>
          <p class="ref-note">共 <span id="refCount">0</span> 篇，{meta.ref_note_html}</p>
          <ol id="refList" class="ref-list"></ol>
        </section>
      </article>
      <footer class="page-foot">
        {meta.footer_html}
        <p class="gen-note">研究與整合：robust-lit-review 工作流（Scopus·PubMed·Embase → Q1·≥2016 → DOI·CrossRef 驗證 → GRADE）＋ OpenEvidence 交叉查核 ｜ 報告生成日 {meta.gen_date}</p>
      </footer>
    </main>
  </div>

  <div id="citePop" class="cite-pop" role="tooltip" hidden></div>
  <button id="toTop" class="to-top" aria-label="回到頂端" hidden>↑</button>

  <script src="assets/references.js"></script>
  <script src="assets/chapters.js" onerror="window.__CHAPTERS__=window.__CHAPTERS__||{{}}"></script>
  <script src="assets/pico-studies.js" onerror="window.__PICO_STUDIES__=window.__PICO_STUDIES__||{{}}"></script>
  <script src="assets/app.js"></script>
  <script src="assets/prisma-popup.js" defer></script>
</body>
</html>
"""


def render_blueprint_site(
    meta: SiteMeta,
    chapters: list[Chapter],
    refs: list[dict],
    output_dir: Path,
) -> Path:
    """Assemble the deployable site. Returns the index.html path."""
    output_dir = Path(output_dir)
    (output_dir / "chapters").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)

    # index shell
    index = output_dir / "index.html"
    index.write_text(_shell(meta), encoding="utf-8")

    # chapter fragment files + offline bundle
    bundle: dict[str, str] = {}
    chapter_list: list[dict] = []
    for ch in chapters:
        (output_dir / ch.file).parent.mkdir(parents=True, exist_ok=True)
        (output_dir / ch.file).write_text(ch.html, encoding="utf-8")
        bundle[ch.id] = ch.html
        chapter_list.append({"id": ch.id, "file": ch.file})

    chapters_js = (
        "window.__CHAPTER_LIST__ = " + json.dumps(chapter_list, ensure_ascii=False) + ";\n"
        "window.__CHAPTERS__ = " + json.dumps(bundle, ensure_ascii=False) + ";\n"
    )
    (output_dir / "assets" / "chapters.js").write_text(chapters_js, encoding="utf-8")

    refs_js = "window.__REFS__ = " + json.dumps(refs, ensure_ascii=False, indent=1) + ";\n"
    (output_dir / "assets" / "references.js").write_text(refs_js, encoding="utf-8")

    # static blueprint assets
    for name in ("style.css", "app.js", "sr-supplement.css", "prisma-popup.js", "og-image.png"):
        src = _BLUEPRINT / "assets" / name
        if src.exists():
            shutil.copyfile(src, output_dir / "assets" / name)

    (output_dir / "_headers").write_text(_HEADERS, encoding="utf-8")

    logger.info("Blueprint site rendered -> %s (%d chapters, %d refs)",
                index, len(chapters), len(refs))
    return index
