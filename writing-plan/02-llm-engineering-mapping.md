# LLM Engineering Techniques → Our Implementation

How established prompt engineering / LLM engineering techniques map to our pipeline.
This framing positions the paper as a practical application of the LLM engineering discipline.

## Technique Mapping

| LLM Engineering Technique | Our Implementation | Paper Section |
|--------------------------|-------------------|---------------|
| **Multi-agent orchestration** | 8 parallel writing agents, 5 haiku extraction agents, repair agents | 2.4 |
| **Structured output prompting** | Haiku JSON extraction (study_type, sample_size, thresholds, dosing) | 2.3 |
| **Model routing** (right model for right task) | Haiku for extraction/judging (cheap, fast), Sonnet for writing (quality) | 2.4 |
| **Prompt decomposition** | Section dispatcher splits 50 articles into domain-specific context per agent | 2.4 |
| **LLM-as-judge** | PRISMA compliance evaluation, article inclusion/exclusion judging | 2.5 |
| **Self-repair / reflexion loop** | Audit → identify gaps → generate fix prompts → dispatch repair → re-audit | 2.5 |
| **Human-in-the-loop design** | 9 checkpoints with multiple-choice, defaults for auto-mode, decision logging | 2.6 |
| **Retrieval-augmented generation** | Full abstracts + structured extracted data fed to each writing agent | 2.3, 2.4 |
| **Embedding-based retrieval** | PubMedBert (pritamdeka/S-PubMedBert-MS-MARCO) semantic scoring | 2.2 |
| **Cascading fallback** | Scimago CSV → OpenAlex API → CiteScore for journal quality | 2.2 |
| **Batch processing** | Articles batched by 10 for haiku extraction, sections batched by subtopic | 2.3 |
| **Context window management** | Modular includes prevent single-agent context overflow | 2.4 |

## References to Cite for Each Technique

- Multi-agent: "Virtual Scientists: Multi-Agent System for Science" (ACL 2025)
- Structured output: "The Prompt Report" (arXiv 2406.06608) — taxonomy of 58 techniques
- LLM-as-judge: "Judging LLM-as-a-Judge" (NeurIPS 2024)
- Self-repair: "Reflexion: Language Agents with Verbal Reinforcement Learning" (NeurIPS 2023)
- RAG: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (NeurIPS 2020)
- Embedding: "S-PubMedBert-MS-MARCO" (pritamdeka, HuggingFace)
- Prompt engineering survey: arXiv 2402.07927
