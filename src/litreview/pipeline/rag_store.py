"""RAG (Retrieval-Augmented Generation) store for literature review writing.

Indexes article abstracts and extracted data using PubMedBERT embeddings,
then retrieves top-K relevant articles per section query. This replaces
the naive "dump all articles" approach in review_writer.py with focused,
semantically-relevant context per section.

Backend priority:
  1. chromadb (persistent, fast) — if installed
  2. In-memory numpy cosine similarity (fallback, no extra deps)

Reuses the PubMedBERT model from semantic_selector.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from litreview.models import ArticleMetadata
from litreview.pipeline.enrichment import ExtractedData, build_rich_article_context

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"


class ArticleRAGStore:
    """Lightweight RAG layer for article retrieval during review writing.

    Indexes full abstracts + extracted data (not truncated), then retrieves
    top-K articles per query using semantic similarity.
    """

    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir
        self._model = None
        self._backend: _RAGBackend | None = None
        self._articles: list[ArticleMetadata] = []
        self._extracted_map: dict[str, ExtractedData] = {}

    def _load_model(self):
        """Lazy-load the PubMedBERT model."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "RAG store will use keyword fallback. "
                "Install with: uv pip install -e '.[semantic]'"
            )
            self._model = None

    def _get_article_key(self, article: ArticleMetadata) -> str:
        return article.doi or article.title

    def _build_doc_text(self, article: ArticleMetadata) -> str:
        """Build indexable text from article — full abstract, not truncated."""
        parts = [article.title]
        if article.abstract:
            parts.append(article.abstract)  # Full abstract, not truncated to 500
        if article.journal:
            parts.append(article.journal)
        return " ".join(parts)

    def index(
        self,
        articles: list[ArticleMetadata],
        extracted_map: dict[str, ExtractedData] | None = None,
    ) -> None:
        """Index articles for retrieval.

        Args:
            articles: Articles to index.
            extracted_map: Optional map of article key → ExtractedData.
        """
        self._articles = articles
        self._extracted_map = extracted_map or {}
        self._load_model()

        doc_texts = [self._build_doc_text(a) for a in articles]

        # Try chromadb backend first
        backend = self._try_chromadb_backend(articles, doc_texts)
        if backend is None:
            backend = self._numpy_backend(articles, doc_texts)
        self._backend = backend

        logger.info(f"RAG store indexed {len(articles)} articles via {backend.name}")

    def _try_chromadb_backend(
        self, articles: list[ArticleMetadata], doc_texts: list[str]
    ) -> _RAGBackend | None:
        """Try to initialize chromadb persistent backend."""
        try:
            import chromadb

            persist_dir = str(self._cache_dir) if self._cache_dir else None
            if persist_dir:
                client = chromadb.PersistentClient(path=persist_dir)
            else:
                client = chromadb.EphemeralClient()

            # Create or get collection
            collection_id = hashlib.md5(
                json.dumps([a.doi or a.title for a in articles], sort_keys=True).encode()
            ).hexdigest()[:12]
            collection = client.get_or_create_collection(
                name=f"litreview_{collection_id}",
                metadata={"hnsw:space": "cosine"},
            )

            # Check if already populated
            if collection.count() == len(articles):
                logger.info("RAG store: using cached chromadb embeddings")
                return _ChromaBackend(collection, articles, self._model)

            # Index with embeddings
            if self._model is not None:
                embeddings = self._model.encode(doc_texts, show_progress_bar=False).tolist()
                collection.add(
                    ids=[self._get_article_key(a) for a in articles],
                    embeddings=embeddings,
                    documents=doc_texts,
                )
            else:
                # Without model, chromadb can still do keyword search
                collection.add(
                    ids=[self._get_article_key(a) for a in articles],
                    documents=doc_texts,
                )

            return _ChromaBackend(collection, articles, self._model)

        except ImportError:
            logger.debug("chromadb not installed, falling back to numpy backend")
            return None
        except Exception as e:
            logger.warning(f"chromadb init failed: {e}, falling back to numpy backend")
            return None

    def _numpy_backend(
        self, articles: list[ArticleMetadata], doc_texts: list[str]
    ) -> _RAGBackend:
        """Initialize in-memory numpy cosine similarity backend."""
        if self._model is not None:
            embeddings = self._model.encode(doc_texts, show_progress_bar=False)
            return _NumpyBackend(articles, embeddings, self._model)
        else:
            return _KeywordBackend(articles, doc_texts)

    def retrieve(
        self,
        query: str,
        k: int = 15,
    ) -> list[tuple[ArticleMetadata, float]]:
        """Retrieve top-K articles most relevant to the query.

        Returns list of (article, similarity_score) tuples, sorted by relevance.
        """
        if self._backend is None:
            logger.warning("RAG store not indexed, returning all articles")
            return [(a, 1.0) for a in self._articles[:k]]
        return self._backend.retrieve(query, k)

    def retrieve_for_section(
        self,
        section_instructions: str,
        k: int = 15,
    ) -> list[tuple[ArticleMetadata, float]]:
        """Retrieve articles relevant to a specific section's writing instructions."""
        return self.retrieve(section_instructions, k)

    def build_tiered_context(
        self,
        query: str,
        all_articles: list[ArticleMetadata],
        focal_k: int = 15,
    ) -> str:
        """Build tiered context: rich for focal articles, summary for rest.

        This is the main entry point for review_writer.py integration.
        Focal articles get full rich context (abstract + extracted data).
        Background articles get a 1-line summary (citation key + title + year).
        """
        focal_results = self.retrieve(query, k=focal_k)
        focal_keys = {self._get_article_key(a) for a, _ in focal_results}

        parts = ["=== FOCAL ARTICLES (most relevant to this section) ===\n"]
        for i, (article, score) in enumerate(focal_results, 1):
            key = self._get_article_key(article)
            extracted = self._extracted_map.get(key, ExtractedData())
            rich = build_rich_article_context(article, extracted)
            parts.append(f"[{i}] (relevance: {score:.3f})\n{rich}\n")

        # Background articles: 1-line summary
        background = [
            a for a in all_articles
            if self._get_article_key(a) not in focal_keys
        ]
        if background:
            parts.append("\n=== BACKGROUND ARTICLES (available for citation) ===\n")
            for article in background:
                parts.append(
                    f"@{article.citation_key} — {article.title[:80]} "
                    f"({article.journal}, {article.year})"
                )

        return "\n".join(parts)


# ── Backend implementations ──────────────────────────────────────────


class _RAGBackend:
    """Abstract backend for RAG retrieval."""

    name: str = "base"

    def retrieve(self, query: str, k: int) -> list[tuple[ArticleMetadata, float]]:
        raise NotImplementedError


class _ChromaBackend(_RAGBackend):
    """Chromadb-backed retrieval."""

    name = "chromadb"

    def __init__(self, collection, articles: list[ArticleMetadata], model):
        self._collection = collection
        self._articles = articles
        self._key_to_article = {
            (a.doi or a.title): a for a in articles
        }
        self._model = model

    def retrieve(self, query: str, k: int) -> list[tuple[ArticleMetadata, float]]:
        k = min(k, len(self._articles))
        if self._model is not None:
            query_embedding = self._model.encode(query).tolist()
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
            )
        else:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
            )

        scored = []
        for doc_id, distance in zip(
            results["ids"][0], results["distances"][0]
        ):
            article = self._key_to_article.get(doc_id)
            if article:
                # chromadb returns distances; convert to similarity
                similarity = 1.0 - distance
                scored.append((article, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


class _NumpyBackend(_RAGBackend):
    """In-memory numpy cosine similarity backend."""

    name = "numpy"

    def __init__(self, articles: list[ArticleMetadata], embeddings, model):
        import numpy as np

        self._articles = articles
        self._embeddings = np.array(embeddings)
        self._model = model
        # Normalize for cosine similarity
        norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._normed = self._embeddings / norms

    def retrieve(self, query: str, k: int) -> list[tuple[ArticleMetadata, float]]:
        import numpy as np

        k = min(k, len(self._articles))
        query_emb = self._model.encode(query)
        query_emb = np.array(query_emb)
        query_norm = np.linalg.norm(query_emb)
        if query_norm > 0:
            query_emb = query_emb / query_norm

        similarities = self._normed @ query_emb
        top_indices = np.argsort(similarities)[::-1][:k]

        return [
            (self._articles[i], float(similarities[i]))
            for i in top_indices
        ]


class _KeywordBackend(_RAGBackend):
    """Fallback keyword matching when no embedding model is available."""

    name = "keyword"

    def __init__(self, articles: list[ArticleMetadata], doc_texts: list[str]):
        self._articles = articles
        self._doc_texts = [t.lower() for t in doc_texts]

    def retrieve(self, query: str, k: int) -> list[tuple[ArticleMetadata, float]]:
        k = min(k, len(self._articles))
        query_terms = set(query.lower().split())

        scored = []
        for i, doc_text in enumerate(self._doc_texts):
            matches = sum(1 for term in query_terms if term in doc_text)
            score = matches / len(query_terms) if query_terms else 0
            scored.append((self._articles[i], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
