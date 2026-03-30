"""Capability testing for Ollama models.

Provides comprehensive and fast capability detection for chat, embedding,
function calling, and structured output capabilities.
"""

import json

import httpx

from ...config.logfire_config import get_logger
from ..llm_provider_service import get_llm_client
from .models import ModelCapabilities

logger = get_logger(__name__)


class CapabilityTester:
    """Tests model capabilities via API calls."""

    async def test_embedding_capability_fast(self, model_name: str, instance_url: str) -> int | None:
        """Fast embedding capability test with reduced timeout and no retry.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            Embedding dimensions if supported, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5)) as client:  # Reduced timeout
                embed_url = f"{instance_url.rstrip('/')}/api/embeddings"
                payload = {
                    "model": model_name,
                    "prompt": "test",  # Shorter test prompt
                }
                response = await client.post(embed_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", [])
                    if isinstance(embedding, list) and len(embedding) > 0:
                        return len(embedding)
        except Exception as e:
            logger.debug(f"Embedding capability test failed for {model_name}: {e}")
            return None

    async def test_chat_capability_fast(self, model_name: str, instance_url: str) -> bool:
        """Fast chat capability test with minimal request.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            True if chat is supported, False otherwise
        """
        try:
            async with get_llm_client(provider="ollama") as client:
                client.base_url = f"{instance_url.rstrip('/')}/v1"
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=1,
                    timeout=5,  # Reduced timeout
                )
                return response.choices and len(response.choices) > 0
        except Exception as e:
            logger.debug(f"Chat capability test failed for {model_name}: {e}")
            return False

    async def test_structured_output_capability_fast(self, model_name: str, instance_url: str) -> bool:
        """Fast structured output test with minimal JSON request.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            True if structured output is supported, False otherwise
        """
        try:
            async with get_llm_client(provider="ollama") as client:
                client.base_url = f"{instance_url.rstrip('/')}/v1"
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": 'Return: {"ok":true}',  # Minimal JSON test
                        }
                    ],
                    max_tokens=10,
                    timeout=5,  # Reduced timeout
                    temperature=0.1,
                )
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    # Simple check for JSON-like structure
                    return content and ("{" in content and "}" in content)
        except Exception as e:
            logger.debug(f"Structured output test failed for {model_name}: {e}")
            return False

    async def test_embedding_capability(self, model_name: str, instance_url: str) -> int | None:
        """Test if a model supports embeddings and detect dimensions.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            Embedding dimensions if supported, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                embed_url = f"{instance_url.rstrip('/')}/api/embeddings"

                payload = {"model": model_name, "prompt": "test embedding"}

                response = await client.post(embed_url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", [])
                    if embedding:
                        dimensions = len(embedding)
                        logger.debug(f"Model {model_name} embedding dimensions: {dimensions}")
                        return dimensions

        except Exception as e:
            logger.debug(f"Model {model_name} does not support embeddings: {e}")

        return None

    async def test_chat_capability(self, model_name: str, instance_url: str) -> bool:
        """Test if a model supports chat completions.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            True if chat is supported, False otherwise
        """
        try:
            # Use OpenAI-compatible client for chat testing
            async with get_llm_client(provider="ollama") as client:
                # Set base_url for this specific instance
                client.base_url = f"{instance_url.rstrip('/')}/v1"

                response = await client.chat.completions.create(
                    model=model_name, messages=[{"role": "user", "content": "Hi"}], max_tokens=1, timeout=10
                )

                if response.choices and len(response.choices) > 0:
                    return True

        except Exception as e:
            logger.debug(f"Model {model_name} does not support chat: {e}")

        return False

    async def test_function_calling_capability(self, model_name: str, instance_url: str) -> bool:
        """Test if a model supports function/tool calling.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            True if function calling is supported, False otherwise
        """
        try:
            async with get_llm_client(provider="ollama") as client:
                # Set base_url for this specific instance
                client.base_url = f"{instance_url.rstrip('/')}/v1"

                # Define a simple test function
                test_function = {
                    "name": "get_current_time",
                    "description": "Get the current time",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                }

                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": "What time is it? Use the available function to get the current time.",
                        }
                    ],
                    tools=[{"type": "function", "function": test_function}],
                    max_tokens=50,
                    timeout=8,
                )

                # Check if the model attempted to use the function
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                        return True

        except Exception as e:
            logger.debug(f"Function calling test failed for {model_name}: {e}")

        return False

    async def test_structured_output_capability(self, model_name: str, instance_url: str) -> bool:
        """Test if a model can produce structured output.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            True if structured output is supported, False otherwise
        """
        try:
            async with get_llm_client(provider="ollama") as client:
                # Set base_url for this specific instance
                client.base_url = f"{instance_url.rstrip('/')}/v1"

                # Test structured JSON output
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": 'Return exactly this JSON structure with no additional text: {"name": "test", "value": 42, "active": true}',
                        }
                    ],
                    max_tokens=100,
                    timeout=8,
                    temperature=0.1,
                )

                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if content:
                        # Try to parse as JSON
                        try:
                            parsed = json.loads(content.strip())
                            if isinstance(parsed, dict) and "name" in parsed and "value" in parsed:
                                return True
                        except json.JSONDecodeError:
                            # Look for JSON-like patterns
                            if "{" in content and "}" in content and '"name"' in content:
                                return True

        except Exception as e:
            logger.debug(f"Structured output test failed for {model_name}: {e}")

        return False

    async def detect_capabilities_optimized(
        self, model_name: str, instance_url: str
    ) -> ModelCapabilities:
        """Optimized capability detection that prioritizes speed over comprehensive testing.
        Only tests the most likely capability first, then stops.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            ModelCapabilities object with detected capabilities
        """
        capabilities = ModelCapabilities()

        try:
            # Quick heuristic: if model name suggests embedding, test that first
            model_name_lower = model_name.lower()
            likely_embedding = any(pattern in model_name_lower for pattern in ["embed", "embedding", "bge", "e5"])

            if likely_embedding:
                # Test embedding capability first for likely embedding models
                embedding_dims = await self.test_embedding_capability_fast(model_name, instance_url)
                if embedding_dims:
                    capabilities.supports_embedding = True
                    capabilities.embedding_dimensions = embedding_dims
                    logger.debug(f"Fast embedding test: {model_name} supports embeddings with {embedding_dims}D")
                    # Cache immediately and return - don't test other capabilities
                    return capabilities

            # If not embedding or embedding test failed, test chat capability
            chat_supported = await self.test_chat_capability_fast(model_name, instance_url)
            if chat_supported:
                capabilities.supports_chat = True
                logger.debug(f"Fast chat test: {model_name} supports chat")

                # For chat models, do a quick structured output test (skip function calling for speed)
                structured_output_supported = await self.test_structured_output_capability_fast(
                    model_name, instance_url
                )
                if structured_output_supported:
                    capabilities.supports_structured_output = True
                    logger.debug(f"Fast structured test: {model_name} supports structured output")

        except Exception as e:
            logger.warning(f"Fast capability detection failed for {model_name}: {e}")
            # Default to chat capability if detection fails
            capabilities.supports_chat = True

        return capabilities

    async def detect_capabilities(self, model_name: str, instance_url: str) -> ModelCapabilities:
        """Detect capabilities of a specific model by testing its endpoints.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            ModelCapabilities object with detected capabilities
        """
        capabilities = ModelCapabilities()

        try:
            # Test embedding capability first (more specific)
            embedding_dims = await self.test_embedding_capability(model_name, instance_url)
            if embedding_dims:
                capabilities.supports_embedding = True
                capabilities.embedding_dimensions = embedding_dims
                logger.debug(f"Model {model_name} supports embeddings with {embedding_dims} dimensions")

            # Test chat capability
            chat_supported = await self.test_chat_capability(model_name, instance_url)
            if chat_supported:
                capabilities.supports_chat = True
                logger.debug(f"Model {model_name} supports chat")

                # Test advanced capabilities for chat models
                function_calling_supported = await self.test_function_calling_capability(model_name, instance_url)
                if function_calling_supported:
                    capabilities.supports_function_calling = True
                    logger.debug(f"Model {model_name} supports function calling")

                structured_output_supported = await self.test_structured_output_capability(model_name, instance_url)
                if structured_output_supported:
                    capabilities.supports_structured_output = True
                    logger.debug(f"Model {model_name} supports structured output")

        except Exception as e:
            logger.warning(f"Error detecting capabilities for {model_name}: {e}")
            # Default to chat capability if detection fails
            capabilities.supports_chat = True

        return capabilities
