"""PRISMA 2020 checklist generator.

Auto-generates a completed PRISMA 2020 checklist (27 items) for any
systematic review, with section references mapped to the modular
Quarto output structure.
"""

from __future__ import annotations

PRISMA_CHECKLIST_TEMPLATE = '''# PRISMA 2020 Checklist

This systematic review was conducted and reported in accordance with the Preferred Reporting Items for Systematic Reviews and Meta-Analyses (PRISMA) 2020 statement. The following checklist documents compliance with each of the 27 items.

| Section | Item | Checklist Item | Reported on |
|---------|------|---------------|-------------|
| **TITLE** | | | |
| Title | 1 | Identify the report as a systematic review | Title page |
| **ABSTRACT** | | | |
| Abstract | 2 | Structured summary (background, objectives, methods, results, conclusions) | Abstract |
| **INTRODUCTION** | | | |
| Rationale | 3 | Describe the rationale for the review in the context of existing knowledge | Section 1, para 1--3 |
| Objectives | 4 | Provide an explicit statement of the objectives or questions the review addresses | Section 1, objectives list |
| **METHODS** | | | |
| Eligibility criteria | 5 | Specify inclusion and exclusion criteria for the review | Sections 2.4, 2.5 |
| Information sources | 6 | Specify all databases, registers, websites, and other sources searched | Section 2.2 |
| Search strategy | 7 | Present the full search strategies for all databases | Section 2.2 |
| Selection process | 8 | Specify methods used to decide whether a study met inclusion criteria | Section 2.3 |
| Data collection process | 9 | Specify methods used to collect data from reports | Section 2.7 |
| Data items | 10a | List and define all outcomes for which data were sought | Section 2.7 |
| | 10b | List and define all other variables for which data were sought | Section 2.7 |
| Study risk of bias assessment | 11 | Specify methods used to assess risk of bias in included studies | Section 2.6 |
| Effect measures | 12 | Specify for each outcome the effect measure(s) used in synthesis | Section 2.7 (narrative synthesis) |
| Synthesis methods | 13a | Describe the processes used to decide which studies were eligible for each synthesis | Section 2.3 |
| | 13b | Describe any methods required to prepare the data for presentation or synthesis | Section 2.7 |
| | 13c | Describe any methods used to tabulate or visually display results | Section 2.3 (PRISMA flow), Results tables |
| | 13d | Describe any methods used to synthesize results and provide a rationale | Section 2.7 (thematic narrative synthesis) |
| | 13e | Describe any methods used to explore possible causes of heterogeneity | Section 2.7 (thematic grouping) |
| | 13f | Describe any sensitivity analyses conducted to assess robustness | N/A (narrative synthesis) |
| Reporting bias assessment | 14 | Describe any methods used to assess risk of bias due to missing results | Discussion (limitations) |
| Certainty assessment | 15 | Describe any methods used to assess certainty in the body of evidence | Section 2.6 |
| **RESULTS** | | | |
| Study selection | 16a | Describe the results of the search and selection process, ideally using a flow diagram | Section 2.3, PRISMA Figure |
| | 16b | Cite studies that might appear to meet inclusion criteria, but which were excluded | Section 2.3 (exclusion categories) |
| Study characteristics | 17 | Cite each included study and present its characteristics | Sections 3--7 (cited throughout) |
| Risk of bias in studies | 18 | Present assessments of risk of bias for each included study | Section 2.6 |
| Results of individual studies | 19 | For all outcomes, present summary statistics and effect estimates per study | Sections 3--7 (specific data) |
| Results of syntheses | 20a | Briefly summarise the characteristics and risk of bias among contributing studies | Sections 3--7 (per-theme) |
| | 20b | Present results of all statistical syntheses conducted | Sections 3--7 (quantitative data) |
| | 20c | Present results of investigations of possible causes of heterogeneity | Sections 3--7 (thematic grouping) |
| | 20d | Present results of any sensitivity analyses | N/A (narrative synthesis) |
| Reporting biases | 21 | Present assessments of risk of bias due to missing results | Discussion (limitations) |
| Certainty of evidence | 22 | Present assessments of certainty in the body of evidence | Discussion (limitations) |
| **DISCUSSION** | | | |
| Discussion | 23a | Provide a general interpretation of the results in context of other evidence | Discussion (synthesis) |
| | 23b | Discuss any limitations of the evidence included in the review | Discussion (limitations) |
| | 23c | Discuss any limitations of the review processes used | Discussion (limitations) |
| | 23d | Discuss implications for practice, policy, and future research | Discussion (implications, future directions) |
| **OTHER INFORMATION** | | | |
| Registration and protocol | 24a | Provide registration information, or state not registered | {registration} |
| | 24b | Indicate where protocol can be accessed, or state not prepared | {protocol} |
| | 24c | Describe and explain any amendments to registration or protocol | N/A |
| Support | 25 | Describe sources of financial or non-financial support | {funding} |
| Competing interests | 26 | Declare any competing interests of review authors | {competing_interests} |
| Availability of data, code, and other materials | 27 | Report public availability of data collection forms, extracted data, analytic code | {data_availability} |

*Checklist adapted from: Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. BMJ. 2021;372:n71.*
'''


def generate_prisma_checklist(
    registration: str = "Not registered",
    protocol: str = "Protocol not prepared",
    funding: str = "No external funding",
    competing_interests: str = "No competing interests",
    data_availability: str = "",
    repo_url: str = "",
) -> str:
    """Generate a completed PRISMA 2020 checklist for the review."""
    if not data_availability:
        if repo_url:
            data_availability = (
                f"All code, search results, and rendered outputs are publicly available at "
                f"[{repo_url}]({repo_url})"
            )
        else:
            data_availability = "Available upon request"

    return PRISMA_CHECKLIST_TEMPLATE.format(
        registration=registration,
        protocol=protocol,
        funding=funding,
        competing_interests=competing_interests,
        data_availability=data_availability,
    )
