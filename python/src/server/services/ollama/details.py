"""Model detail fetching and parsing from Ollama /api/show endpoint.

Handles comprehensive model information extraction including context lengths,
architecture details, capabilities, and parameter information.
"""

from typing import Any

import httpx

from ...config.logfire_config import get_logger
from .models import OllamaModel

logger = get_logger(__name__)


class ModelDetailsFetcher:
    """Fetches and parses comprehensive model details from Ollama API."""

    async def fetch_model_details(self, model: OllamaModel, instance_url: str) -> bool:
        """Fetch comprehensive model details from /api/show endpoint.

        Args:
            model: Model to enrich with details
            instance_url: Ollama instance URL

        Returns:
            True if details were successfully fetched, False otherwise
        """
        logger.info(f"Fetching detailed info for {model.name} from {instance_url}")
        try:
            detailed_info = await self._get_model_details_from_api(model.name, instance_url)
            if detailed_info:
                self._apply_details_to_model(model, detailed_info)
                logger.debug(
                    f"Enriched {model.name} with comprehensive data: "
                    f"context={model.context_window}, arch={model.architecture}"
                )
                return True
        except Exception as e:
            logger.debug(f"Could not get comprehensive details for {model.name}: {e}")

        return False

    async def _get_model_details_from_api(
        self, model_name: str, instance_url: str
    ) -> dict[str, Any] | None:
        """Get comprehensive information about a model from Ollama /api/show endpoint.

        Args:
            model_name: Name of the model
            instance_url: Ollama instance URL

        Returns:
            Model details dictionary with comprehensive real API data or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                # Remove /v1 suffix if present (Ollama native API doesn't use /v1)
                base_url = instance_url.rstrip("/").replace("/v1", "")
                show_url = f"{base_url}/api/show"

                payload = {"name": model_name}
                response = await client.post(show_url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    logger.debug(
                        f"Got /api/show response for {model_name}: keys={list(data.keys())}, "
                        f"model_info keys={list(data.get('model_info', {}).keys())[:10]}"
                    )

                    return self._parse_model_details(data, model_name)

        except Exception as e:
            logger.debug(f"Could not get comprehensive details for model {model_name}: {e}")

        return None

    def _parse_model_details(self, data: dict[str, Any], model_name: str) -> dict[str, Any]:
        """Parse raw API response into structured model details.

        Args:
            data: Raw API response data
            model_name: Name of the model

        Returns:
            Structured model details dictionary
        """
        # Extract sections from /api/show response
        details_section = data.get("details", {})
        model_info = data.get("model_info", {})
        parameters_raw = data.get("parameters", "")
        capabilities = data.get("capabilities", [])

        # Parse parameters string for custom context length (num_ctx)
        custom_context_length = self._extract_custom_context_length(parameters_raw)

        # Extract architecture-specific context lengths from model_info
        max_context_length = None
        base_context_length = None
        embedding_dimension = None

        for key, value in model_info.items():
            if key.endswith(".context_length"):
                max_context_length = value
            elif key.endswith(".rope.scaling.original_context_length"):
                base_context_length = value
            elif key.endswith(".embedding_length"):
                embedding_dimension = value

        # Determine current context length
        current_context_length = (
            custom_context_length
            if custom_context_length
            else (base_context_length if base_context_length else max_context_length)
        )

        # Build comprehensive parameters object
        parameters_obj = {
            "family": details_section.get("family"),
            "parameter_size": details_section.get("parameter_size"),
            "quantization": details_section.get("quantization_level"),
            "format": details_section.get("format"),
        }

        # Extract block count and attention heads
        block_count = self._extract_block_count(model_info)
        attention_heads = self._extract_attention_heads(model_info)

        details: dict[str, Any] = {
            "family": details_section.get("family"),
            "parameter_size": details_section.get("parameter_size"),
            "quantization": details_section.get("quantization_level"),
            "format": details_section.get("format"),
            "parent_model": details_section.get("parent_model"),
            "parameters": parameters_obj,
            "context_window": current_context_length,
            "max_context_length": max_context_length,
            "base_context_length": base_context_length,
            "custom_context_length": custom_context_length,
            "architecture": model_info.get("general.architecture"),
            "embedding_dimension": embedding_dimension,
            "parameter_count": model_info.get("general.parameter_count"),
            "file_type": model_info.get("general.file_type"),
            "quantization_version": model_info.get("general.quantization_version"),
            "basename": model_info.get("general.basename"),
            "size_label": model_info.get("general.size_label"),
            "license": model_info.get("general.license"),
            "finetune": model_info.get("general.finetune"),
            "capabilities": capabilities,
            "block_count": block_count,
            "attention_heads": attention_heads,
        }

        logger.info(
            f"Extracted comprehensive details for {model_name}: "
            f"context={current_context_length}, max={max_context_length}, "
            f"base={base_context_length}, arch={details['architecture']}, "
            f"blocks={block_count}, heads={attention_heads}"
        )

        return details

    def _extract_custom_context_length(self, parameters_raw: str) -> int | None:
        """Extract custom context length (num_ctx) from parameters string.

        Args:
            parameters_raw: Raw parameters string from API

        Returns:
            Custom context length or None
        """
        if not parameters_raw:
            return None

        for line in parameters_raw.split("\n"):
            line = line.strip()
            if line.startswith("num_ctx"):
                try:
                    return int(line.split()[-1])
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_block_count(self, model_info: dict[str, Any]) -> int | None:
        """Extract block count (layers) from model_info.

        Args:
            model_info: Model info dictionary from API

        Returns:
            Block count or None
        """
        for key, value in model_info.items():
            if (
                "block_count" in key
                or "num_layers" in key
                or key.endswith(".block_count")
                or key.endswith(".n_layer")
            ):
                return value
        return None

    def _extract_attention_heads(self, model_info: dict[str, Any]) -> int | None:
        """Extract attention heads count from model_info.

        Args:
            model_info: Model info dictionary from API

        Returns:
            Attention heads count or None
        """
        for key, value in model_info.items():
            if (
                key.endswith(".attention.head_count")
                or key.endswith(".n_head")
                or "attention_head" in key
            ) and not key.endswith("_kv"):
                return value
        return None

    def _apply_details_to_model(self, model: OllamaModel, detailed_info: dict[str, Any]) -> None:
        """Apply detailed info to model object.

        Args:
            model: Model to update
            detailed_info: Detailed information dictionary
        """
        model.context_window = detailed_info.get("context_window")
        model.max_context_length = detailed_info.get("max_context_length")
        model.base_context_length = detailed_info.get("base_context_length")
        model.custom_context_length = detailed_info.get("custom_context_length")
        model.architecture = detailed_info.get("architecture")
        model.block_count = detailed_info.get("block_count")
        model.attention_heads = detailed_info.get("attention_heads")
        model.format = detailed_info.get("format")
        model.parent_model = detailed_info.get("parent_model")
        model.family = detailed_info.get("family")
        model.parameter_size = detailed_info.get("parameter_size")
        model.quantization = detailed_info.get("quantization")
        model.parameter_count = detailed_info.get("parameter_count")
        model.file_type = detailed_info.get("file_type")
        model.quantization_version = detailed_info.get("quantization_version")
        model.basename = detailed_info.get("basename")
        model.size_label = detailed_info.get("size_label")
        model.license = detailed_info.get("license")
        model.finetune = detailed_info.get("finetune")
        model.embedding_dimension = detailed_info.get("embedding_dimension")

        # Update capabilities with real API capabilities if available
        api_capabilities = detailed_info.get("capabilities", [])
        if api_capabilities:
            combined_capabilities = list(set(model.capabilities + api_capabilities))
            model.capabilities = combined_capabilities

        # Update parameters
        if model.parameters:
            model.parameters.update(detailed_info.get("parameters", {}))
        else:
            model.parameters = detailed_info.get("parameters")
