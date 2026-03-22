"""
Ollama Integration Service

Manages Ollama connection, model availability, and health checks.
"""

import logging
from typing import Any

import httpx

from src.server.config.yaml_config import get_config

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for Ollama integration."""
    
    def __init__(self):
        self.config = get_config()
        self.url = self.config.external.ollama.url
        self.embedding_model = self.config.external.ollama.embedding_model
        self.chat_model = self.config.external.ollama.chat_model
    
    async def health_check(self) -> dict[str, Any]:
        """Check Ollama health and available models."""
        try:
            async with httpx.AsyncClient() as client:
                # Check if Ollama is running
                response = await client.get(f"{self.url}/api/tags", timeout=5.0)
                response.raise_for_status()
                
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                
                # Check if our models are available
                embedding_available = any(self.embedding_model in m for m in models)
                chat_available = any(self.chat_model in m for m in models)
                
                return {
                    "healthy": True,
                    "url": self.url,
                    "models": models,
                    "embedding_model": self.embedding_model,
                    "embedding_available": embedding_available,
                    "chat_model": self.chat_model,
                    "chat_available": chat_available,
                }
        except Exception as e:
            return {
                "healthy": False,
                "url": self.url,
                "error": str(e),
            }
    
    async def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama."""
        try:
            logger.info(f"Pulling Ollama model: {model}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/pull",
                    json={"name": model},
                    timeout=300.0  # Long timeout for model download
                )
                response.raise_for_status()
                logger.info(f"Successfully pulled {model}")
                return True
        except Exception as e:
            logger.error(f"Failed to pull model {model}: {e}")
            return False
    
    async def ensure_models(self) -> bool:
        """Ensure required models are available."""
        health = await self.health_check()
        
        if not health["healthy"]:
            logger.error(f"Ollama not available at {self.url}")
            return False
        
        # Pull embedding model if needed
        if not health["embedding_available"]:
            logger.info(f"Embedding model {self.embedding_model} not found, pulling...")
            if not await self.pull_model(self.embedding_model):
                return False
        
        # Pull chat model if needed
        if not health["chat_available"]:
            logger.info(f"Chat model {self.chat_model} not found, pulling...")
            if not await self.pull_model(self.chat_model):
                return False
        
        return True
    
    def get_install_instructions(self) -> str:
        """Get installation instructions for Ollama."""
        return """
Ollama is not running or not installed.

Install Ollama:
  curl -fsSL https://ollama.com/install.sh | sh

Start Ollama:
  ollama serve

Pull models:
  ollama pull bge-large
  ollama pull llama3.2

Or let Archon pull them automatically on startup.
"""


# Singleton
_ollama_service: OllamaService | None = None


def get_ollama_service() -> OllamaService:
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
