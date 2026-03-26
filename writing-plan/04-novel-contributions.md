# Novel Contributions vs Published Work

## What exists (published 2024-2025)

| Paper | What they did | What they DON'T do |
|-------|-------------|-------------------|
| otto-SR (medRxiv 2025) | LLM screening (96.7% sensitivity) + extraction (93.1% accuracy) | No manuscript writing, no PRISMA audit, no multi-DB search |
| JAMIA 2025 (LLM emergence) | Survey of 172 studies using LLMs for SR | No pipeline implementation |
| JAMIA 2025 (Enhancing SLR) | 5-module system for HTA submissions | PubMed only, PICO screening, no full manuscript |
| ASReview (Nature MI 2020) | Active learning for screening | Screening only, no writing, no compliance |
| LitLLM (2024) | RAG-based review writing | No search, no quality filtering, no PRISMA |

## What we add (first in literature)

### 1. End-to-End Pipeline (search → submission-ready PDF)
No published tool produces a complete, formatted manuscript from a topic input.
Others stop at screening OR extraction OR writing — never all three integrated.

### 2. PRISMA 2020 Self-Audit Loop
No published tool automatically checks its own output against PRISMA guidelines.
We audit 27 items, generate fix instructions, dispatch repair agents, and re-audit.

### 3. Multi-Agent Modular Writing Architecture
No published tool uses parallel LLM agents with domain-specific context splitting.
We dispatch 8 independent writers, each receiving only its subtopic's articles,
then assemble via Quarto includes. This solves context overflow and enables parallelism.

### 4. LLM Model Routing for Cost/Quality Optimization
No published SR tool uses different models for different tasks.
We use Haiku (cheap, fast) for extraction/judging and Sonnet (quality) for writing.

### 5. Human-in-the-Loop with Structured Checkpoints
No published SR automation tool offers systematic decision points with
multiple-choice options and decision logging for reproducibility.

### 6. Automated Journal Quality Assessment
No published tool combines Scimago + OpenAlex + CiteScore for journal filtering
with configurable quartile thresholds (default Q1).

## One-sentence pitch

"We present the first open-source pipeline that harnesses multi-agent LLM engineering
to automate the complete systematic review workflow — from multi-database search to
PRISMA-compliant, submission-ready manuscript — with built-in self-auditing and
human-in-the-loop quality assurance."
