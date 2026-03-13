"""Embedding Service

Generates embeddings for code entities using Ollama or OpenAI.
Supports multiple dimensions for different embedding models.
"""

import os
from typing import Any

import aiohttp

import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings.
    
    Supports:
    - Ollama (local): nomic-embed-text, mxbai-embed-large, etc.
    - OpenAI (cloud): text-embedding-3-small, text-embedding-3-large
    """
    
    # Model configurations: (dimension, provider)
    MODELS = {
        # Ollama models
        "nomic-embed-text": (768, "ollama"),
        "mxbai-embed-large": (1024, "ollama"),
        "bge-large": (1024, "ollama"),
        "bge-m3": (1024, "ollama"),
        
        # OpenAI models
        "text-embedding-3-small": (1536, "openai"),
        "text-embedding-3-large": (3072, "openai"),
    }
    
    def __init__(
        self,
        ollama_url: str | None = None,
        ollama_model: str | None = None,
        openai_api_key: str | None = None,
        openai_model: str | None = None,
    ):
        """Initialize embedding service.
        
        Args:
            ollama_url: Ollama endpoint (default: from env OLLAMA_URL)
            ollama_model: Default Ollama model (default: from env OLLAMA_EMBEDDING_MODEL)
            openai_api_key: OpenAI API key (default: from env OPENAI_API_KEY)
            openai_model: OpenAI model (default: text-embedding-3-small)
        """
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_model = openai_model or "text-embedding-3-small"
        
        self._http_session: aiohttp.ClientSession | None = None
        self._logger = logger
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def close(self):
        """Close HTTP session."""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
    
    def get_model_dimension(self, model: str) -> int:
        """Get embedding dimension for a model."""
        return self.MODELS.get(model, (768, "ollama"))[0]
    
    def get_model_provider(self, model: str) -> str:
        """Get provider for a model."""
        return self.MODELS.get(model, (768, "ollama"))[1]
    
    async def generate(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float] | None:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            model: Model to use (default: from config)
            
        Returns:
            Embedding vector or None on error
        """
        model = model or self.ollama_model
        provider = self.get_model_provider(model)
        
        if provider == "ollama":
            return await self._generate_ollama(text, model)
        elif provider == "openai":
            return await self._generate_openai(text, model)
        else:
            self._logger.error(f"Unknown provider: {provider}")
            return None
    
    async def _generate_ollama(
        self,
        text: str,
        model: str,
    ) -> list[float] | None:
        """Generate embedding using Ollama."""
        try:
            session = await self._get_session()
            url = f"{self.ollama_url}/api/embeddings"
            
            payload = {
                "model": model,
                "prompt": text,
            }
            
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._logger.error(f"Ollama error: {response.status} - {error_text}")
                    return None
                
                result = await response.json()
                embedding = result.get("embedding")
                
                if embedding:
                    self._logger.debug(f"Generated embedding with {model}: {len(embedding)} dims")
                    return embedding
                else:
                    self._logger.error("No embedding in Ollama response")
                    return None
                    
        except aiohttp.ClientError as e:
            self._logger.error(f"Ollama connection error: {e}")
            return None
        except Exception as e:
            self._logger.exception(f"Ollama embedding error: {e}")
            return None
    
    async def _generate_openai(
        self,
        text: str,
        model: str,
    ) -> list[float] | None:
        """Generate embedding using OpenAI."""
        if not self.openai_api_key:
            self._logger.error("OpenAI API key not configured")
            return None
        
        try:
            session = await self._get_session()
            url = "https://api.openai.com/v1/embeddings"
            
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": model,
                "input": text,
            }
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._logger.error(f"OpenAI error: {response.status} - {error_text}")
                    return None
                
                result = await response.json()
                data = result.get("data", [])
                
                if data:
                    embedding = data[0].get("embedding")
                    self._logger.debug(f"Generated embedding with {model}: {len(embedding)} dims")
                    return embedding
                else:
                    self._logger.error("No data in OpenAI response")
                    return None
                    
        except aiohttp.ClientError as e:
            self._logger.error(f"OpenAI connection error: {e}")
            return None
        except Exception as e:
            self._logger.exception(f"OpenAI embedding error: {e}")
            return None
    
    async def generate_batch(
        self,
        texts: list[str],
        model: str | None = None,
        batch_size: int = 10,
    ) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            model: Model to use
            batch_size: Number of texts to process at once
            
        Returns:
            List of embeddings (None for failed items)
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Process batch
            batch_results = await asyncio.gather(*[
                self.generate(text, model) for text in batch
            ])
            
            results.extend(batch_results)
            
            if i + batch_size < len(texts):
                self._logger.debug(f"Processed {i + len(batch)}/{len(texts)} embeddings")
        
        return results
    
    async def generate_for_code_entity(
        self,
        name: str,
        signature: str | None,
        docstring: str | None,
        source_code: str | None,
        model: str | None = None,
    ) -> list[float] | None:
        """Generate embedding optimized for code entity.
        
        Creates a rich text representation combining name, signature,
        and docstring for better semantic search.
        
        Args:
            name: Entity name
            signature: Function/class signature
            docstring: Documentation string
            source_code: Full source code
            model: Model to use
            
        Returns:
            Embedding vector
        """
        # Build rich text representation
        parts = [f"Name: {name}"]
        
        if signature:
            parts.append(f"Signature: {signature}")
        
        if docstring:
            # Truncate long docstrings
            doc = docstring[:500] if len(docstring) > 500 else docstring
            parts.append(f"Documentation: {doc}")
        
        if source_code:
            # Include first few lines of source
            lines = source_code.split("\n")[:10]
            code_snippet = "\n".join(lines)
            if len(source_code) > 500:
                code_snippet += "\n..."
            parts.append(f"Code:\n{code_snippet}")
        
        text = "\n\n".join(parts)
        return await self.generate(text, model)


import asyncio


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    
    return _embedding_service


async def generate_embeddings_for_repo(
    repo_id: str,
    model: str | None = None,
    batch_size: int = 10,
) -> dict[str, Any]:
    """Generate embeddings for all entities in a repository.
    
    Args:
        repo_id: Repository ID
        model: Model to use (default: from env)
        batch_size: Batch size for processing
        
    Returns:
        Results dict with counts
    """
    from .database.db_connector import get_database_connector, initialize_database
    from .code_entity_service import CodeEntityService
    
    await initialize_database()
    db = get_database_connector()
    await db.initialize()
    
    embedding_service = get_embedding_service()
    code_service = CodeEntityService()
    
    model = model or embedding_service.ollama_model
    dimension = embedding_service.get_model_dimension(model)
    
    # Get entities without embeddings
    entities = await db.fetch(
        """
        SELECT id, name, signature, docstring, source_code, entity_type
        FROM archon_code_entities
        WHERE repo_id = $1
        AND embedding_model IS NULL
        """,
        repo_id
    )
    
    if not entities:
        return {"status": "no_entities", "processed": 0}
    
    logger.info(f"Generating embeddings for {len(entities)} entities using {model} ({dimension}d)")
    
    processed = 0
    failed = 0
    
    # Process in batches
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i + batch_size]
        
        for entity in batch:
            try:
                # Generate embedding
                embedding = await embedding_service.generate_for_code_entity(
                    name=entity["name"],
                    signature=entity.get("signature"),
                    docstring=entity.get("docstring"),
                    source_code=entity.get("source_code"),
                    model=model,
                )
                
                if embedding:
                    # Determine column based on dimension
                    column_map = {
                        384: "embedding_384",
                        768: "embedding_768",
                        1024: "embedding_1024",
                        1536: "embedding_1536",
                        3072: "embedding_3072",
                    }
                    
                    column = column_map.get(dimension, "embedding_768")
                    
                    # Update entity with embedding
                    await db.execute(
                        f"""
                        UPDATE archon_code_entities
                        SET {column} = $1::vector,
                            embedding_model = $2,
                            embedding_dimension = $3
                        WHERE id = $4
                        """,
                        embedding, model, dimension, entity["id"]
                    )
                    
                    processed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.exception(f"Failed to generate embedding for {entity['name']}: {e}")
                failed += 1
        
        if (i // batch_size) % 10 == 0:
            logger.info(f"Processed {i + len(batch)}/{len(entities)} entities")
    
    await embedding_service.close()
    
    return {
        "status": "success",
        "processed": processed,
        "failed": failed,
        "model": model,
        "dimension": dimension,
    }
