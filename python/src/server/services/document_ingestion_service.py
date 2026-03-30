"""
Document Ingestion Service

Handles ingestion of documents into the knowledge base with:
- Text extraction and chunking
- Embedding generation
- Metadata extraction
- Source tracking
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any

from ..config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..services.embeddings.unified_embedding_service import get_unified_embedding_service
from .database import get_database_connector

logger = get_logger(__name__)


class DocumentIngestionService:
    """Service for ingesting documents into the knowledge base."""

    def __init__(self):
        self.embedding_service = get_unified_embedding_service()
        self.db = get_database_connector()

    async def ingest_text(
        self,
        content: str,
        title: str,
        source_url: str | None = None,
        metadata: dict | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> dict[str, Any]:
        """
        Ingest plain text into the knowledge base.

        Args:
            content: Text content to ingest
            title: Document title
            source_url: Optional source URL
            metadata: Optional metadata dict
            chunk_size: Chunk size in tokens
            chunk_overlap: Overlap between chunks

        Returns:
            Ingestion result with source_id and chunk count
        """
        try:
            safe_logfire_info(f"Starting document ingestion | title={title} | size={len(content)}")

            # Generate source ID
            source_id = str(uuid.uuid4())

            # Simple chunking strategy - split by paragraphs first, then by size
            chunks = self._chunk_text(content, chunk_size, chunk_overlap)

            safe_logfire_info(f"Text chunked | source_id={source_id} | chunks={len(chunks)}")

            # Use transaction for atomic ingestion
            # If any part fails, the entire operation is rolled back
            stored_chunks = 0
            async with self.db.transaction() as conn:
                # Create source record within transaction
                await conn.execute(
                    """
                    INSERT INTO archon_sources (
                        source_id, name, url, description
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    source_id,
                    title,
                    source_url or f"ingested://{title.replace(' ', '_')}",
                    f"Ingested document: {title}",
                )

                # Generate embeddings and store chunks within same transaction
                for i, chunk in enumerate(chunks):
                    try:
                        # Generate embedding
                        embedding = await self.embedding_service.generate(chunk)

                        if embedding is None:
                            safe_logfire_error(f"Embedding returned None for chunk {i}")
                            continue

                        logger.info(f"Generated embedding | chunk={i} | dims={len(embedding)}")

                        # Convert embedding list to PostgreSQL vector string
                        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"

                        # Store chunk with embedding
                        chunk_id = uuid.uuid4()
                        item_uuid = uuid.UUID(source_id)
                        await conn.execute(
                            """
                            INSERT INTO archon_embeddings (
                                id, item_id, item_type, chunk_index, total_chunks,
                                embedding, model_id
                            ) VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
                            """,
                            chunk_id,
                            item_uuid,
                            "source",
                            i,
                            len(chunks),
                            vector_str,
                            "bge-large",
                        )
                        stored_chunks += 1
                        logger.info(f"Stored chunk | chunk_id={chunk_id}")

                    except Exception as e:
                        logger.error(f"Failed to process chunk {i}: {e}")
                        safe_logfire_error(f"Failed to process chunk {i} | error={str(e)}")
                        # Re-raise to trigger transaction rollback
                        raise

            safe_logfire_info(
                f"Document ingestion complete | source_id={source_id} | chunks={stored_chunks}/{len(chunks)}"
            )

            return {
                "success": True,
                "source_id": source_id,
                "title": title,
                "chunks_total": len(chunks),
                "chunks_stored": stored_chunks,
            }

        except Exception as e:
            safe_logfire_error(f"Document ingestion failed | error={str(e)} | title={title}")
            return {"success": False, "error": str(e)}

    async def ingest_markdown(
        self,
        content: str,
        title: str,
        source_url: str | None = None,
        extract_code: bool = True,
    ) -> dict[str, Any]:
        """
        Ingest Markdown document with special handling for code blocks.

        Args:
            content: Markdown content
            title: Document title
            source_url: Optional source URL
            extract_code: Whether to extract code blocks separately

        Returns:
            Ingestion result
        """
        import re

        code_examples = []

        if extract_code:
            # Extract code blocks
            code_pattern = r"```(\w+)?\n(.*?)```"
            matches = re.findall(code_pattern, content, re.DOTALL)

            for lang, code in matches:
                code_examples.append(
                    {
                        "language": lang or "text",
                        "code": code.strip(),
                    }
                )

            # Remove code blocks for text chunking
            text_content = re.sub(code_pattern, "[code example]", content, flags=re.DOTALL)
        else:
            text_content = content

        # Ingest the text content
        result = await self.ingest_text(
            content=text_content,
            title=title,
            source_url=source_url,
            metadata={"format": "markdown", "code_examples_count": len(code_examples)},
        )

        # Note: Code examples are extracted but not stored separately
        # (archon_code_examples table doesn't exist yet)
        if result["success"] and code_examples:
            result["code_examples_count"] = len(code_examples)

        return result

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """
        Split text into chunks with overlap.

        Simple word-based chunking strategy.
        """
        words = text.split()
        chunks = []

        if len(words) <= chunk_size:
            return [text]

        i = 0
        while i < len(words):
            chunk_words = words[i : i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += chunk_size - overlap

        return chunks

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict]:
        """
        Search for similar documents.

        Args:
            query: Search query
            top_k: Number of results
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching chunks with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate(query)

            # Convert to vector string
            vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # Search using pgvector
            results = await self.db.fetch(
                """
                SELECT 
                    e.id,
                    e.item_id,
                    e.chunk_index,
                    1 - (e.embedding <=> $1::vector) as similarity
                FROM archon_embeddings e
                WHERE 1 - (e.embedding <=> $1::vector) > $2
                ORDER BY e.embedding <=> $1::vector
                LIMIT $3
                """,
                vector_str,
                similarity_threshold,
                top_k,
            )

            return [
                {
                    "id": str(row["id"]),
                    "source_id": str(row["item_id"]),
                    "chunk_index": row["chunk_index"],
                    "similarity": float(row["similarity"]),
                }
                for row in results
            ]

        except Exception as e:
            safe_logfire_error(f"Similarity search failed | error={str(e)}")
            return []


# Global instance
_ingestion_service: DocumentIngestionService | None = None


def get_document_ingestion_service() -> DocumentIngestionService:
    """Get singleton instance of DocumentIngestionService."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = DocumentIngestionService()
    return _ingestion_service
