"""CLI interface for the literature review pipeline."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from litreview.config import get_config
from litreview.pipeline.orchestrator import run_pipeline
from litreview.pipeline.quarto_renderer import write_outputs, render_quarto
from litreview.utils.statistics import format_statistics_table

app = typer.Typer(name="lit-review", help="Robust Literature Review Pipeline")
console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command()
def review(
    topic: str = typer.Argument(..., help="Research topic for the literature review"),
    terms: list[str] = typer.Option(None, "--term", "-t", help="Additional search terms"),
    max_results: int = typer.Option(100, "--max-results", "-n", help="Max results per database"),
    min_quartile: str = typer.Option("Q1", "--min-quartile", "-q", help="Minimum SJR quartile (Q1, Q2, Q3, Q4)"),
    min_citescore: float = typer.Option(3.0, "--min-citescore", help="Minimum CiteScore fallback threshold"),
    target: int = typer.Option(50, "--target", help="Target number of articles"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o", help="Output directory"),
    render: bool = typer.Option(True, "--render/--no-render", help="Render Quarto to PDF/DOCX"),
    ai_screen: bool = typer.Option(False, "--ai-screen/--no-ai-screen", help="Enable AI PICO screening (P1)"),
    explore_gaps: bool = typer.Option(False, "--explore-gaps/--no-explore-gaps", help="Enable research gap exploration (P2)"),
    copilot: bool = typer.Option(False, "--copilot/--no-copilot", help="Enable enhanced co-pilot mode (P3)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Run a complete literature review on a topic."""
    setup_logging(verbose)

    config = get_config()
    config.max_results_per_db = max_results
    config.min_quartile = min_quartile
    config.min_citescore = min_citescore
    config.target_articles = target
    config.output_dir = output_dir
    config.enable_ai_screening = ai_screen
    config.explore_gaps = explore_gaps
    config.copilot_mode = copilot

    # Show configuration
    keys = config.validate_keys()
    console.print(Panel(f"[bold]Literature Review: {topic}[/bold]", style="blue"))

    table = Table(title="API Configuration")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    for service, configured in keys.items():
        status = "[green]configured[/green]" if configured else "[red]missing[/red]"
        table.add_row(service, status)
    console.print(table)

    # Run pipeline
    with console.status("[bold green]Running pipeline..."):
        output = asyncio.run(run_pipeline(topic, terms, config))

    # Write files
    console.print("\n[bold]Writing outputs...[/bold]")
    paths = write_outputs(output, output_dir)
    for name, path in paths.items():
        console.print(f"  {name}: {path}")

    # Render
    if render:
        console.print("\n[bold]Rendering Quarto...[/bold]")
        rendered = render_quarto(output_dir)
        for fmt, path in rendered.items():
            console.print(f"  {fmt}: {path}")

    # Show statistics
    console.print(Panel(format_statistics_table(output.statistics), title="Review Statistics"))
    console.print(f"\n[bold green]Done![/bold green] {len(output.articles)} articles reviewed.")


@app.command()
def validate(
    bib_file: Path = typer.Argument(..., help="BibTeX file to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Validate all DOIs in a BibTeX file."""
    import re

    setup_logging(verbose)

    from litreview.utils.doi_validator import batch_validate_dois

    content = bib_file.read_text()
    dois = re.findall(r"doi\s*=\s*\{([^}]+)\}", content)

    console.print(f"Found {len(dois)} DOIs to validate")

    with console.status("[bold green]Validating DOIs..."):
        results = asyncio.run(batch_validate_dois(dois))

    valid = sum(1 for v in results.values() if v)
    invalid = [doi for doi, v in results.items() if not v]

    console.print(f"\n[green]{valid}[/green] valid, [red]{len(invalid)}[/red] invalid")
    for doi in invalid:
        console.print(f"  [red]Invalid:[/red] {doi}")


@app.command()
def check_config():
    """Check API key configuration."""
    config = get_config()
    keys = config.validate_keys()

    table = Table(title="API Configuration")
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    for service, configured in keys.items():
        status = "[green]OK[/green]" if configured else "[red]MISSING[/red]"
        table.add_row(service, status)
    console.print(table)


if __name__ == "__main__":
    app()
