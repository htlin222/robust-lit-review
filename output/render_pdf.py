#!/usr/bin/env python3
"""Render the HER2 adjuvant treatment review QMD to PDF via markdown -> HTML -> PDF."""

import re
import markdown
from weasyprint import HTML, CSS

QMD_PATH = "/home/user/robust-lit-review/output/her2_adjuvant_treatment_review.qmd"
PDF_PATH = "/home/user/robust-lit-review/output/her2_adjuvant_treatment_review.pdf"

# Read QMD
with open(QMD_PATH) as f:
    raw = f.read()

# Strip YAML front matter
content = re.sub(r'^---.*?---\s*', '', raw, flags=re.DOTALL)

# Extract title/date from front matter
title_match = re.search(r'title:\s*"(.+?)"', raw)
subtitle_match = re.search(r'subtitle:\s*"(.+?)"', raw)
date_match = re.search(r'date:\s*"(.+?)"', raw)
title = title_match.group(1) if title_match else "Review"
subtitle = subtitle_match.group(1) if subtitle_match else ""
date = date_match.group(1) if date_match else ""

# Remove citation keys [@...] — replace with superscript numbers
cite_counter = {}
cite_num = [0]
def replace_cite(m):
    keys = m.group(1).split(';')
    nums = []
    for k in keys:
        k = k.strip().lstrip('@')
        if k not in cite_counter:
            cite_num[0] += 1
            cite_counter[k] = cite_num[0]
        nums.append(str(cite_counter[k]))
    return '<sup>[' + ','.join(nums) + ']</sup>'

content = re.sub(r'\[(@[\w;@ ]+)\]', replace_cite, content)

# Remove Quarto-specific directives
content = re.sub(r'\{\{<.*?>}\}', '', content)

# Convert LaTeX math to plain text approximations
content = content.replace('$\\Delta$', 'Δ')
content = content.replace('$\\geq$', '≥')

# Convert markdown to HTML
md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
html_body = md.convert(content)

# Build reference list
ref_html = "<h1>References</h1><ol>"
# Read bib file for reference info
import re as re2
with open("/home/user/robust-lit-review/output/her2_adjuvant_references.bib") as bf:
    bib = bf.read()

for key, num in sorted(cite_counter.items(), key=lambda x: x[1]):
    # Find entry in bib
    pattern = rf'@\w+\{{{re2.escape(key)},.*?(?=\n@|\Z)'
    match = re2.search(pattern, bib, re2.DOTALL)
    if match:
        entry = match.group(0)
        a = re2.search(r'author\s*=\s*\{(.+?)\}', entry)
        t = re2.search(r'title\s*=\s*\{(.+?)\}', entry)
        j = re2.search(r'journal\s*=\s*\{(.+?)\}', entry)
        y = re2.search(r'year\s*=\s*\{(\d+)\}', entry)
        d = re2.search(r'doi\s*=\s*\{(.+?)\}', entry)
        author = a.group(1).replace('{', '').replace('}', '') if a else "Unknown"
        ttl = t.group(1).replace('{', '').replace('}', '') if t else "Untitled"
        journal = j.group(1).replace('{', '').replace('}', '') if j else ""
        year = y.group(1) if y else ""
        doi = d.group(1) if d else ""
        ref_html += f"<li>{author}. {ttl}. <em>{journal}</em>. {year}."
        if doi:
            ref_html += f' DOI: <a href="https://doi.org/{doi}">{doi}</a>'
        ref_html += "</li>"
    else:
        ref_html += f"<li>{key}</li>"
ref_html += "</ol>"

# Remove the empty "References" heading from body (we add it in ref_html)
html_body = re2.sub(r'<h1[^>]*>\s*References\s*</h1>', '', html_body)

full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<div class="title-block">
  <h1 class="title">{title}</h1>
  <p class="subtitle">{subtitle}</p>
  <p class="date">{date}</p>
</div>
<hr>
{html_body}
{ref_html}
</body>
</html>
"""

css = CSS(string="""
@page {{
    size: letter;
    margin: 1in;
}}
body {{
    font-family: 'DejaVu Serif', Georgia, serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}}
.title-block {{
    text-align: center;
    margin-bottom: 1em;
}}
.title-block .title {{
    font-size: 18pt;
    margin-bottom: 0.2em;
}}
.title-block .subtitle {{
    font-size: 13pt;
    color: #555;
    margin: 0.2em 0;
}}
.title-block .date {{
    font-size: 11pt;
    color: #777;
}}
h1 {{ font-size: 16pt; margin-top: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }}
h2 {{ font-size: 13pt; margin-top: 1em; }}
h3 {{ font-size: 11pt; margin-top: 0.8em; }}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
}}
th, td {{
    border: 1px solid #999;
    padding: 6px 10px;
    text-align: left;
}}
th {{ background: #f0f0f0; font-weight: bold; }}
sup {{ font-size: 8pt; }}
ol {{ font-size: 10pt; }}
a {{ color: #1a5276; }}
""")

HTML(string=full_html).write_pdf(PDF_PATH, stylesheets=[css])
print(f"PDF written to {PDF_PATH}")
