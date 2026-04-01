"""Configuration management for the literature review pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _find_env_file() -> Path:
    """Walk up from CWD to find .env file."""
    current = Path.cwd()
    while current != current.parent:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent
    return Path.cwd() / ".env"


load_dotenv(_find_env_file())


class Config(BaseModel):
    """Pipeline configuration loaded from environment."""

    scopus_api_key: str = Field(default_factory=lambda: os.environ.get("SCOPUS_API_KEY", ""))
    pubmed_api_key: str = Field(default_factory=lambda: os.environ.get("PUBMED_API_KEY", ""))
    embase_api_key: str = Field(default_factory=lambda: os.environ.get("EMBASE_API_KEY", ""))
    unpaywall_email: str = Field(default_factory=lambda: os.environ.get("UNPAYWALL_EMAIL", ""))
    zotero_api_key: str = Field(default_factory=lambda: os.environ.get("ZOTERO_API_KEY", ""))
    zotero_library_type: str = Field(default_factory=lambda: os.environ.get("ZOTERO_LIBRARY_TYPE", "user"))
    zotero_library_id: str = Field(default_factory=lambda: os.environ.get("ZOTERO_LIBRARY_ID", ""))
    zotero_collection_key: str = Field(default_factory=lambda: os.environ.get("ZOTERO_COLLECTION_KEY", ""))

    # Quality thresholds
    min_quartile: str = Field(default="Q1", description="Minimum SJR quartile (Q1, Q2, Q3, Q4)")
    min_citescore: float = Field(default=3.0, description="Minimum CiteScore fallback for journal filtering")
    min_sjr: float = Field(default=0.5, description="Minimum SJR quartile threshold")
    max_results_per_db: int = Field(default=100, description="Max results per database search")
    target_articles: int = Field(default=50, description="Target number of articles for review")

    # AI-enhanced features (P0-P3)
    enable_ai_screening: bool = Field(default=False, description="Enable AI-powered PICO screening (P1)")
    explore_gaps: bool = Field(default=False, description="Enable research gap exploration (P2)")
    copilot_mode: bool = Field(default=False, description="Enable enhanced co-pilot checkpoints (P3)")
    screening_model: str = Field(default="claude-haiku-4-5-20251001", description="Model for screening tasks")

    # Output settings
    output_dir: Path = Field(default=Path("output"))
    template_dir: Path = Field(default=Path("templates"))

    def validate_keys(self) -> dict[str, bool]:
        """Check which API keys are configured."""
        return {
            "scopus": bool(self.scopus_api_key),
            "pubmed": bool(self.pubmed_api_key),
            "embase": bool(self.embase_api_key),
            "unpaywall": bool(self.unpaywall_email),
            "zotero": bool(self.zotero_api_key),
        }


def get_config() -> Config:
    """Get the pipeline configuration."""
    return Config()
