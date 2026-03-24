"""Zotero API client for bibliography management."""

from __future__ import annotations

import logging
from typing import Self

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from litreview.models import ArticleMetadata

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Async client for the Zotero Web API v3."""

    def __init__(
        self,
        api_key: str,
        library_type: str = "user",
        library_id: str = "",
        collection_key: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.library_type = library_type
        self.library_id = library_id
        self.collection_key = collection_key
        self._client = httpx.AsyncClient(
            base_url=f"https://api.zotero.org/{library_type}s/{library_id}",
            headers={
                "Zotero-API-Key": api_key,
                "Zotero-API-Version": "3",
            },
            timeout=30.0,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def create_collection(
        self, name: str, parent_key: str | None = None
    ) -> str:
        """Create a new Zotero collection and return its key.

        Args:
            name: Display name for the collection.
            parent_key: Optional parent collection key for nesting.

        Returns:
            The key string of the newly created collection.
        """
        payload: dict = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key

        try:
            response = await self._client.post(
                "/collections",
                json=[payload],
            )
            response.raise_for_status()
            data = response.json()

            success = data.get("success", {})
            if "0" in success:
                key = success["0"]
                logger.info("Created Zotero collection '%s' with key %s", name, key)
                return key

            failed = data.get("failed", {})
            msg = f"Failed to create collection: {failed}"
            raise RuntimeError(msg)

        except httpx.HTTPStatusError as exc:
            logger.error("Zotero create_collection HTTP error: %s", exc.response.status_code)
            raise
        except httpx.HTTPError as exc:
            logger.error("Zotero create_collection request error: %s", exc)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def add_items(self, items: list[dict]) -> list[dict]:
        """Add items to the Zotero library.

        Args:
            items: List of Zotero-formatted item dicts.

        Returns:
            List of successfully created item objects.
        """
        created: list[dict] = []

        # Zotero API accepts max 50 items per request
        for batch_start in range(0, len(items), 50):
            batch = items[batch_start : batch_start + 50]
            try:
                response = await self._client.post("/items", json=batch)
                response.raise_for_status()
                data = response.json()

                success = data.get("successful", {})
                created.extend(success.values())

                failed = data.get("failed", {})
                if failed:
                    logger.warning(
                        "Failed to add %d items in batch starting at %d: %s",
                        len(failed),
                        batch_start,
                        failed,
                    )
            except httpx.HTTPStatusError as exc:
                logger.error("Zotero add_items HTTP error: %s", exc.response.status_code)
                raise
            except httpx.HTTPError as exc:
                logger.error("Zotero add_items request error: %s", exc)
                raise

        logger.info("Added %d items to Zotero library", len(created))
        return created

    async def article_to_zotero_item(self, article: ArticleMetadata) -> dict:
        """Convert an ArticleMetadata instance to a Zotero journalArticle item.

        Returns a dict conforming to the Zotero Web API item schema.
        """
        creators = [
            {"creatorType": "author", "name": author}
            for author in article.authors
        ]

        item: dict = {
            "itemType": "journalArticle",
            "title": article.title,
            "creators": creators,
            "abstractNote": article.abstract,
            "publicationTitle": article.journal,
            "date": str(article.year) if article.year else "",
            "DOI": article.doi or "",
            "url": article.oa_url or "",
            "accessDate": "",
            "tags": [{"tag": article.source_db.value}],
        }

        if article.volume:
            item["volume"] = article.volume
        if article.issue:
            item["issue"] = article.issue
        if article.pages:
            item["pages"] = article.pages

        if self.collection_key:
            item["collections"] = [self.collection_key]

        return item

    async def export_to_collection(
        self, articles: list[ArticleMetadata], collection_name: str
    ) -> str:
        """Create a collection and add all articles to it.

        Args:
            articles: Articles to export.
            collection_name: Name for the new Zotero collection.

        Returns:
            The key of the created collection.
        """
        collection_key = await self.create_collection(collection_name)

        # Store the collection key so article_to_zotero_item uses it
        original_key = self.collection_key
        self.collection_key = collection_key

        try:
            items = [await self.article_to_zotero_item(a) for a in articles]
            await self.add_items(items)
        finally:
            self.collection_key = original_key

        logger.info(
            "Exported %d articles to Zotero collection '%s' (%s)",
            len(articles),
            collection_name,
            collection_key,
        )
        return collection_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def get_collection_bibtex(self, collection_key: str) -> str:
        """Retrieve items in a collection as BibTeX.

        Args:
            collection_key: The Zotero collection key.

        Returns:
            BibTeX-formatted string of all items in the collection.
        """
        try:
            response = await self._client.get(
                f"/collections/{collection_key}/items",
                headers={"Accept": "application/x-bibtex"},
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Zotero get_collection_bibtex HTTP error: %s", exc.response.status_code
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Zotero get_collection_bibtex request error: %s", exc)
            raise
