"""Abstract enrichment and structured data extraction.

This module fetches full abstracts and extracts structured data points
(numbers, thresholds, sample sizes, key findings) to produce richer
context for the review writer — making ANY topic's output publication-quality.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)


@dataclass
class ExtractedData:
    """Structured data extracted from an article abstract."""

    # Quantitative findings
    sample_sizes: list[str] = field(default_factory=list)  # "n=342", "1,204 patients"
    percentages: list[str] = field(default_factory=list)  # "73% response rate"
    p_values: list[str] = field(default_factory=list)  # "p<0.001"
    confidence_intervals: list[str] = field(default_factory=list)  # "95% CI 1.2-3.4"
    hazard_ratios: list[str] = field(default_factory=list)  # "HR 0.65"
    odds_ratios: list[str] = field(default_factory=list)  # "OR 2.3"
    thresholds: list[str] = field(default_factory=list)  # "ferritin >10,000"
    dosing: list[str] = field(default_factory=list)  # "150 mg/m2 twice weekly"
    incidence: list[str] = field(default_factory=list)  # "1.2 per million"
    survival_rates: list[str] = field(default_factory=list)  # "5-year OS 61%"
    sensitivity_specificity: list[str] = field(default_factory=list)  # "93% sensitivity"

    # Study design
    study_type: str = ""  # RCT, cohort, case-control, review, meta-analysis, case series
    is_clinical_trial: bool = False

    # Key sentences
    key_findings: list[str] = field(default_factory=list)  # Most important result sentences
    conclusion: str = ""

    @property
    def has_quantitative_data(self) -> bool:
        return bool(
            self.sample_sizes or self.percentages or self.p_values
            or self.hazard_ratios or self.survival_rates
        )

    @property
    def data_richness_score(self) -> int:
        """Score 0-10 for how much extractable data this article has."""
        score = 0
        if self.sample_sizes:
            score += 2
        if self.percentages:
            score += 1
        if self.p_values:
            score += 2
        if self.thresholds:
            score += 2
        if self.dosing:
            score += 1
        if self.survival_rates or self.hazard_ratios:
            score += 2
        return min(score, 10)


# --- Regex patterns for data extraction ---

SAMPLE_SIZE_PATTERNS = [
    re.compile(r"[Nn]\s*=\s*[\d,]+"),
    re.compile(r"(\d[\d,]*)\s*(?:patients?|subjects?|participants?|individuals?|cases?|adults?)"),
    re.compile(r"(?:cohort|sample|population)\s+(?:of\s+)?(\d[\d,]*)", re.IGNORECASE),
]

PERCENTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*(?:"
    r"(?:response|survival|mortality|sensitivity|specificity|accuracy|"
    r"incidence|prevalence|reduction|improvement|remission|"
    r"overall|complete|partial|objective|progression|relapse)"
    r")",
    re.IGNORECASE,
)

P_VALUE_PATTERN = re.compile(r"[Pp]\s*[<>=≤≥]\s*0?\.\d+")
CI_PATTERN = re.compile(r"95%?\s*CI[:\s]+[\d.]+-[\d.]+", re.IGNORECASE)
HR_PATTERN = re.compile(r"(?:HR|hazard ratio)[:\s]+[\d.]+", re.IGNORECASE)
OR_PATTERN = re.compile(r"(?:OR|odds ratio)[:\s]+[\d.]+", re.IGNORECASE)

THRESHOLD_PATTERNS = [
    re.compile(r"(?:>|<|≥|≤|greater than|less than|above|below|threshold[:\s]+)\s*[\d,]+(?:\.\d+)?\s*(?:ng/mL|μg/L|U/mL|mg/dL|g/L|×\s*10)", re.IGNORECASE),
    re.compile(r"(?:ferritin|CRP|IL-\d+|sCD25|sIL-2R|triglyceride|fibrinogen)\s*(?:>|<|≥|≤|of)\s*[\d,]+", re.IGNORECASE),
]

DOSING_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mg(?:/m2|/kg)?|μg(?:/kg)?|g(?:/kg)?|IU)\s*"
    r"(?:(?:once|twice|three times)\s*(?:daily|weekly|monthly|per\s*\w+))?",
    re.IGNORECASE,
)

INCIDENCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:per|/)\s*(?:million|100[,\s]*000|1000|100)\s*"
    r"(?:population|person-years?|admissions?|patients?)?",
    re.IGNORECASE,
)

SURVIVAL_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%?\s*(?:\d+-year|overall|progression-free|event-free|disease-free)?\s*"
    r"(?:survival|OS|PFS|EFS|DFS)",
    re.IGNORECASE,
)

STUDY_TYPE_KEYWORDS = {
    "randomized controlled trial": "RCT",
    "randomised controlled trial": "RCT",
    "phase 1": "phase 1 trial",
    "phase 2": "phase 2 trial",
    "phase 3": "phase 3 trial",
    "phase I": "phase 1 trial",
    "phase II": "phase 2 trial",
    "phase III": "phase 3 trial",
    "meta-analysis": "meta-analysis",
    "systematic review": "systematic review",
    "retrospective": "retrospective study",
    "prospective": "prospective study",
    "cohort study": "cohort study",
    "case-control": "case-control study",
    "case series": "case series",
    "cross-sectional": "cross-sectional study",
    "observational": "observational study",
    "narrative review": "narrative review",
    "guideline": "clinical guideline",
    "consensus": "consensus statement",
    "recommendations": "expert recommendations",
}


def extract_data_from_abstract(article: ArticleMetadata) -> ExtractedData:
    """Extract structured data points from an article's abstract."""
    data = ExtractedData()
    text = article.abstract or ""
    title = article.title or ""
    combined = f"{title}. {text}"

    if not text:
        return data

    # Study type
    lower_combined = combined.lower()
    for keyword, stype in STUDY_TYPE_KEYWORDS.items():
        if keyword in lower_combined:
            data.study_type = stype
            if "trial" in stype or "RCT" in stype:
                data.is_clinical_trial = True
            break

    # Sample sizes
    for pattern in SAMPLE_SIZE_PATTERNS:
        matches = pattern.findall(text)
        data.sample_sizes.extend(m if isinstance(m, str) else m for m in matches[:3])

    # Percentages with context
    for match in PERCENTAGE_PATTERN.finditer(text):
        # Get surrounding context (±30 chars)
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 10)
        context = text[start:end].strip()
        data.percentages.append(context)

    # P-values
    data.p_values = P_VALUE_PATTERN.findall(text)[:5]

    # Confidence intervals
    data.confidence_intervals = CI_PATTERN.findall(text)[:5]

    # Hazard ratios
    data.hazard_ratios = HR_PATTERN.findall(text)[:3]

    # Odds ratios
    data.odds_ratios = OR_PATTERN.findall(text)[:3]

    # Thresholds
    for pattern in THRESHOLD_PATTERNS:
        data.thresholds.extend(pattern.findall(text)[:5])

    # Dosing
    data.dosing = DOSING_PATTERN.findall(text)[:5]

    # Incidence
    data.incidence = INCIDENCE_PATTERN.findall(text)[:3]

    # Survival rates
    data.survival_rates = SURVIVAL_PATTERN.findall(text)[:3]

    # Key findings: last 1-2 sentences (usually conclusion)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if sentences:
        data.conclusion = sentences[-1].strip()
        # Also grab sentences with numbers (likely key results)
        for s in sentences:
            if re.search(r"\d+(?:\.\d+)?%|\bp\s*[<>]|survival|mortality|efficacy|significant", s, re.IGNORECASE):
                data.key_findings.append(s.strip())
        data.key_findings = data.key_findings[:5]

    return data


def classify_article_subtopic(article: ArticleMetadata) -> list[str]:
    """Classify an article into subtopic categories based on title+abstract.

    Returns list of applicable categories for balanced topic coverage.
    """
    text = f"{article.title} {article.abstract}".lower()
    categories = []

    subtopic_keywords = {
        "epidemiology": ["incidence", "prevalence", "epidemiol", "mortality rate", "population-based", "nationwide", "registry", "cohort study"],
        "pathogenesis": ["pathogenesis", "pathophysiol", "mechanism", "immunopath", "cytokine", "interferon", "interleukin", "inflammasome", "macrophage activation", "nk cell", "cd8"],
        "diagnosis": ["diagnos", "criteria", "h-score", "hscore", "biomarker", "sensitivity", "specificity", "ferritin", "sil-2r", "scd25"],
        "classification": ["classif", "taxonomy", "nomenclature", "histiocyt", "revised"],
        "genetics": ["genetic", "mutation", "variant", "perforin", "prf1", "unc13d", "familial", "inherited", "exome", "sequencing"],
        "treatment_conventional": ["etoposide", "dexamethasone", "hlh-94", "hlh-2004", "chemotherapy", "protocol", "regimen"],
        "treatment_targeted": ["emapalumab", "anakinra", "ruxolitinib", "tocilizumab", "jak inhibitor", "il-1 block", "anti-ifn", "targeted therap"],
        "treatment_transplant": ["transplant", "hsct", "conditioning", "engraftment", "graft"],
        "infection_trigger": ["infection", "viral", "ebv", "epstein-barr", "cmv", "hiv", "covid", "sars-cov", "bacterial", "fungal"],
        "malignancy_trigger": ["lymphoma", "leukemia", "malignancy", "cancer", "tumor", "neoplasm"],
        "autoimmune_trigger": ["autoimmune", "rheumat", "lupus", "still disease", "macrophage activation syndrome", "mas", "sjia"],
        "iatrogenic": ["car-t", "car t", "chimeric antigen", "checkpoint", "immunotherapy", "crs", "cytokine release syndrome", "ici"],
        "prognosis": ["prognos", "outcome", "survival", "mortality", "predictor", "risk factor"],
        "review_guideline": ["review", "guideline", "recommendation", "consensus", "management", "overview"],
        "pediatric": ["pediatric", "paediatric", "child", "neonat", "infant", "juvenile"],
    }

    for category, keywords in subtopic_keywords.items():
        if any(kw in text for kw in keywords):
            categories.append(category)

    return categories or ["general"]


def ensure_balanced_coverage(
    articles: list[ArticleMetadata],
    target_count: int = 50,
    min_per_category: int = 2,
) -> list[ArticleMetadata]:
    """Select articles ensuring balanced coverage across subtopics.

    Instead of just taking the top N by citation count (which skews
    toward reviews and COVID articles), ensure at least min_per_category
    articles per subtopic, then fill remaining slots by citation count.
    """
    # Classify all articles
    classified: dict[str, list[ArticleMetadata]] = {}
    for article in articles:
        categories = classify_article_subtopic(article)
        for cat in categories:
            classified.setdefault(cat, []).append(article)

    # Sort each category by citations
    for cat in classified:
        classified[cat].sort(key=lambda a: a.citation_count or 0, reverse=True)

    selected: dict[str, ArticleMetadata] = {}  # doi -> article
    selected_dois = set()

    # Phase 1: Ensure minimum coverage per category
    important_categories = [
        "epidemiology", "pathogenesis", "diagnosis", "classification",
        "genetics", "treatment_conventional", "treatment_targeted",
        "treatment_transplant", "prognosis",
    ]

    for cat in important_categories:
        if cat not in classified:
            continue
        count = 0
        for article in classified[cat]:
            doi = article.doi or article.title
            if doi not in selected_dois and count < min_per_category:
                selected[doi] = article
                selected_dois.add(doi)
                count += 1

    # Phase 2: Fill remaining slots by citation count
    remaining = target_count - len(selected)
    all_sorted = sorted(articles, key=lambda a: a.citation_count or 0, reverse=True)
    for article in all_sorted:
        if remaining <= 0:
            break
        doi = article.doi or article.title
        if doi not in selected_dois:
            selected[doi] = article
            selected_dois.add(doi)
            remaining -= 1

    result = list(selected.values())
    result.sort(key=lambda a: a.citation_count or 0, reverse=True)

    # Log coverage
    final_categories: dict[str, int] = {}
    for article in result:
        for cat in classify_article_subtopic(article):
            final_categories[cat] = final_categories.get(cat, 0) + 1
    logger.info(f"Balanced selection: {len(result)} articles across {len(final_categories)} subtopics")
    for cat, count in sorted(final_categories.items()):
        logger.info(f"  {cat}: {count}")

    return result


def build_rich_article_context(article: ArticleMetadata, extracted: ExtractedData) -> str:
    """Build a rich context string for the AI writer, including extracted data."""
    parts = [
        f"[@{article.citation_key}]",
        f"Title: {article.title}",
        f"Authors: {', '.join(article.authors[:3])}{'...' if len(article.authors) > 3 else ''}",
        f"Journal: {article.journal} ({article.year})",
        f"Citations: {article.citation_count}",
    ]

    if extracted.study_type:
        parts.append(f"Study type: {extracted.study_type}")

    if article.abstract:
        parts.append(f"Abstract: {article.abstract}")

    if extracted.has_quantitative_data:
        parts.append("--- Extracted quantitative data ---")
        if extracted.sample_sizes:
            parts.append(f"Sample sizes: {'; '.join(extracted.sample_sizes[:3])}")
        if extracted.percentages:
            parts.append(f"Key percentages: {'; '.join(extracted.percentages[:3])}")
        if extracted.p_values:
            parts.append(f"P-values: {'; '.join(extracted.p_values[:3])}")
        if extracted.hazard_ratios:
            parts.append(f"Hazard ratios: {'; '.join(extracted.hazard_ratios[:3])}")
        if extracted.thresholds:
            parts.append(f"Thresholds: {'; '.join(extracted.thresholds[:3])}")
        if extracted.dosing:
            parts.append(f"Dosing: {'; '.join(extracted.dosing[:3])}")
        if extracted.survival_rates:
            parts.append(f"Survival: {'; '.join(extracted.survival_rates[:3])}")
        if extracted.incidence:
            parts.append(f"Incidence: {'; '.join(extracted.incidence[:3])}")
        if extracted.sensitivity_specificity:
            parts.append(f"Diagnostic accuracy: {'; '.join(extracted.sensitivity_specificity[:3])}")

    if extracted.key_findings:
        parts.append("--- Key findings ---")
        for finding in extracted.key_findings[:3]:
            parts.append(f"- {finding}")

    if extracted.conclusion:
        parts.append(f"Conclusion: {extracted.conclusion}")

    return "\n".join(parts)


async def fetch_missing_abstracts(
    articles: list[ArticleMetadata],
    scopus_api_key: str = "",
    pubmed_api_key: str = "",
) -> list[ArticleMetadata]:
    """Fetch full abstracts for articles that have truncated or missing abstracts.

    Scopus search results only return dc:description (truncated).
    PubMed EFetch returns full abstracts.
    This function backfills missing abstracts via the Scopus Abstract Retrieval API
    and PubMed EFetch for articles without abstracts.
    """
    import asyncio
    import httpx

    need_abstract = [a for a in articles if not a.abstract or len(a.abstract) < 100]
    if not need_abstract:
        logger.info("All articles have abstracts, skipping fetch")
        return articles

    logger.info(f"Fetching full abstracts for {len(need_abstract)}/{len(articles)} articles")
    semaphore = asyncio.Semaphore(5)

    async def fetch_scopus_abstract(article: ArticleMetadata) -> None:
        if not scopus_api_key or not article.scopus_id:
            return
        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"https://api.elsevier.com/content/abstract/scopus_id/{article.scopus_id}",
                        headers={"X-ELS-APIKey": scopus_api_key, "Accept": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("abstracts-retrieval-response", {})
                        abstract = data.get("coredata", {}).get("dc:description", "")
                        if abstract and len(abstract) > len(article.abstract or ""):
                            article.abstract = abstract
            except Exception:
                pass

    async def fetch_pubmed_abstract(article: ArticleMetadata) -> None:
        if not pubmed_api_key or not article.pmid:
            return
        async with semaphore:
            try:
                import xml.etree.ElementTree as ET
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                        params={
                            "db": "pubmed", "retmode": "xml", "rettype": "abstract",
                            "id": article.pmid, "api_key": pubmed_api_key,
                        },
                    )
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        abs_parts = root.findall(".//AbstractText")
                        if abs_parts:
                            abstract = " ".join(
                                (p.get("Label", "") + ": " if p.get("Label") else "") + (p.text or "")
                                for p in abs_parts
                            )
                            if len(abstract) > len(article.abstract or ""):
                                article.abstract = abstract
            except Exception:
                pass

    tasks = []
    for article in need_abstract:
        if article.scopus_id and scopus_api_key:
            tasks.append(fetch_scopus_abstract(article))
        elif article.pmid and pubmed_api_key:
            tasks.append(fetch_pubmed_abstract(article))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    after = sum(1 for a in articles if a.abstract and len(a.abstract) >= 100)
    logger.info(f"After abstract fetch: {after}/{len(articles)} have full abstracts")
    return articles


def enrich_articles(articles: list[ArticleMetadata]) -> list[tuple[ArticleMetadata, ExtractedData]]:
    """Extract structured data from all articles."""
    enriched = []
    for article in articles:
        data = extract_data_from_abstract(article)
        enriched.append((article, data))

    # Log stats
    with_data = sum(1 for _, d in enriched if d.has_quantitative_data)
    with_abstract = sum(1 for a, _ in enriched if a.abstract)
    avg_richness = sum(d.data_richness_score for _, d in enriched) / len(enriched) if enriched else 0
    logger.info(
        f"Enrichment: {len(enriched)} articles, {with_abstract} with abstracts, "
        f"{with_data} with quantitative data, avg richness: {avg_richness:.1f}/10"
    )

    return enriched
