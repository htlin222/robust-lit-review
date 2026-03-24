from __future__ import annotations
import logging
import re
from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)

def sanitize_bibtex_value(value: str) -> str:
    """Escape special BibTeX characters."""
    special = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_"}
    for char, escaped in special.items():
        value = value.replace(char, escaped)
    return value

def article_to_bibtex(article: ArticleMetadata) -> str:
    """Convert an ArticleMetadata to a BibTeX entry string."""
    key = article.citation_key
    authors = " and ".join(article.authors) if article.authors else "Unknown"

    fields = [
        f"  author = {{{sanitize_bibtex_value(authors)}}}",
        f"  title = {{{sanitize_bibtex_value(article.title)}}}",
        f"  journal = {{{sanitize_bibtex_value(article.journal)}}}",
        f"  year = {{{article.year or 'n.d.'}}}",
    ]

    if article.volume:
        fields.append(f"  volume = {{{article.volume}}}")
    if article.issue:
        fields.append(f"  number = {{{article.issue}}}")
    if article.pages:
        fields.append(f"  pages = {{{article.pages}}}")
    if article.doi:
        fields.append(f"  doi = {{{article.doi}}}")
    if article.pmid:
        fields.append(f"  pmid = {{{article.pmid}}}")
    if article.is_open_access and article.oa_url:
        fields.append(f"  url = {{{article.oa_url}}}")

    return f"@article{{{key},\n" + ",\n".join(fields) + "\n}"

def generate_bibtex(articles: list[ArticleMetadata]) -> str:
    """Generate a complete BibTeX file from a list of articles."""
    entries = []
    seen_keys = set()

    for article in articles:
        key = article.citation_key
        # Handle duplicate keys
        if key in seen_keys:
            suffix = 1
            while f"{key}{chr(96+suffix)}" in seen_keys:
                suffix += 1
            key = f"{key}{chr(96+suffix)}"
        seen_keys.add(key)
        entries.append(article_to_bibtex(article))

    header = "% Auto-generated BibTeX file from Robust Literature Review Pipeline\n"
    header += f"% Total references: {len(entries)}\n\n"
    return header + "\n\n".join(entries) + "\n"

def count_references(bibtex_content: str) -> int:
    """Count the number of references in a BibTeX string."""
    return len(re.findall(r"@\w+\{", bibtex_content))
