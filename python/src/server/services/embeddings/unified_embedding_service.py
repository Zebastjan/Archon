"""
Unified Embedding Service - Supports multiple providers and storage backends

Providers:
- Ollama (BGE-Large, 1024 dims) - primary, local
- OpenAI (optional, cloud) - fallback

Storage:
- pgvector (fast, requires extension)
- JSONB (fallback, universal)
- In-memory LRU cache (speed layer)
"""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.server.config.yaml_config import get_config
from src.server.services.database import get_database_connector

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""
    
    @abstractmethod
    async def generate(self, text: str) -> list[float]:
        """Generate embedding for text."""
        pass
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Number of dimensions."""
        pass
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier."""
        pass


class OllamaProvider(EmbeddingProvider):
    """Ollama embedding provider (BGE-Large, local)."""
    
    def __init__(self, model: str = "bge-large", url: str | None = None):
        self.model = model
        self.url = url or "http://localhost:11434"
        self._dims = 1024  # BGE-Large
    
    async def generate(self, text: str) -> list[float]:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/embeddings",
                json={"model": self.model, "prompt": text[:8192]},
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
            return result["embedding"]
    
    @property
    def dimensions(self) -> int:
        return self._dims
    
    @property
    def model_id(self) -> str:
        return self.model


class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider (cloud, optional)."""
    
    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None):
        self.model = model
        self.api_key = api_key
        self._dims = 1536 if "3-small" in model else 3072
    
    async def generate(self, text: str) -> list[float]:
        import httpx
        
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": text[:8191]},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result["data"][0]["embedding"]
    
    @property
    def dimensions(self) -> int:
        return self._dims
    
    @property
    def model_id(self) -> str:
        return self.model


class EmbeddingCache:
    """In-memory LRU cache for embeddings."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: dict[str, np.ndarray] = {}
        self._access_order: list[str] = []
    
    def _make_key(self, text: str, model: str) -> str:
        return hashlib.md5(f"{model}:{text}".encode()).hexdigest()
    
    def get(self, text: str, model: str) -> np.ndarray | None:
        key = self._make_key(text, model)
        if key in self._cache:
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
    
    def set(self, text: str, model: str, embedding: np.ndarray) -> None:
        key = self._make_key(text, model)
        if key in self._cache:
            self._access_order.remove(key)
        while len(self._access_order) >= self.max_size:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = embedding
        self._access_order.append(key)


class UnifiedEmbeddingService:
    """Main embedding service."""
    
    def __init__(self):
        self.config = get_config()
        self.cache = EmbeddingCache()
        self._provider: EmbeddingProvider | None = None
        self._has_pgvector: bool | None = None
    
    async def _check_pgvector(self) -> bool:
        if self._has_pgvector is not None:
            return self._has_pgvector
        try:
            db = get_database_connector()
            await db.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await db.fetchval("SELECT '[1,2,3]'::vector(3)")
            self._has_pgvector = True
            logger.info("pgvector available")
        except Exception:
            self._has_pgvector = False
            logger.warning("pgvector not available - using JSONB")
        return self._has_pgvector
    
    def _get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            ollama_url = self.config.external.ollama.url
            self._provider = OllamaProvider(
                model=self.config.external.ollama.embedding_model,
                url=ollama_url
            )
        return self._provider
    
    async def generate(
        self,
        text: str,
        use_cache: bool = True,
        store: bool = False,
        item_id: str | None = None,
        item_type: str | None = None,
    ) -> list[float]:
        """Generate embedding for text."""
        provider = self._get_provider()
        model_id = provider.model_id
        
        if use_cache:
            cached = self.cache.get(text, model_id)
            if cached is not None:
                return cached.tolist()
        
        embedding = await provider.generate(text)
        
        if use_cache:
            self.cache.set(text, model_id, np.array(embedding))
        
        if store and item_id:
            await self._store_embedding(item_id, item_type or "unknown", model_id, embedding)
        
        return embedding
    
    async def _store_embedding(
        self, item_id: str, item_type: str, model_id: str, embedding: list[float],
        chunk_index: int = 0
    ) -> None:
        db = get_database_connector()
        has_pgvector = await self._check_pgvector()
        
        if has_pgvector:
            # Convert list to string representation for pgvector: '[0.1,0.2,...]'
            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
            await db.execute(
                """INSERT INTO archon_embeddings (item_id, item_type, model_id, embedding, chunk_index)
                VALUES ($1, $2, $3, $4::vector, $5)
                ON CONFLICT (item_id, model_id, chunk_index) DO UPDATE SET embedding = $4::vector""",
                item_id, item_type, model_id, embedding_str, chunk_index
            )
        else:
            await db.execute(
                """INSERT INTO archon_embeddings (item_id, item_type, model_id, embedding)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (item_id, model_id) DO UPDATE SET embedding = $4""",
                item_id, item_type, model_id, json.dumps(embedding)
            )
    
    async def search_similar(
        self, query_embedding: list[float], model_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        db = get_database_connector()
        has_pgvector = await self._check_pgvector()
        
        if has_pgvector:
            # Convert list to string for pgvector
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
            rows = await db.fetch(
                """SELECT item_id, item_type, 1 - (embedding <=> $1::vector) as similarity
                FROM archon_embeddings WHERE model_id = $2
                ORDER BY embedding <=> $1::vector LIMIT $3""",
                embedding_str, model_id, top_k
            )
            return [dict(row) for row in rows]
        else:
            # Slow JSONB search
            rows = await db.fetch(
                "SELECT item_id, item_type, embedding FROM archon_embeddings WHERE model_id = $1",
                model_id
            )
            query_vec = np.array(query_embedding)
            results = []
            for row in rows:
                emb = np.array(json.loads(row["embedding"]))
                similarity = np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb))
                results.append({"item_id": row["item_id"], "item_type": row["item_type"], "similarity": float(similarity)})
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]


_embedding_service: UnifiedEmbeddingService | None = None

def get_unified_embedding_service() -> UnifiedEmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = UnifiedEmbeddingService()
    return _embedding_service
