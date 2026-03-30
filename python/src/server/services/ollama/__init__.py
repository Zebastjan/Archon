"""Ollama Service Module

Specialized services for Ollama provider management including:
- Model discovery and capability detection
- Multi-instance health monitoring
- Dimension-aware embedding routing

This package provides comprehensive model discovery, validation, and
capability detection for Ollama instances.

Usage:
    from src.server.services.ollama import ModelDiscoveryService

    service = ModelDiscoveryService()
    models = await service.discover_models("http://localhost:11434")
"""

from .caching import ModelCache
from .capability_testing import CapabilityTester
from .details import ModelDetailsFetcher
from .discovery import DiscoveryService
from .health import HealthChecker
from .models import InstanceHealthStatus, ModelCapabilities, OllamaModel
from .multi_instance import MultiInstanceDiscovery
from .service import ModelDiscoveryService, model_discovery_service

__all__ = [
    # Main service
    "ModelDiscoveryService",
    "model_discovery_service",
    # Data models
    "OllamaModel",
    "ModelCapabilities",
    "InstanceHealthStatus",
    # Sub-services (for advanced usage)
    "ModelCache",
    "CapabilityTester",
    "DiscoveryService",
    "HealthChecker",
    "MultiInstanceDiscovery",
    "ModelDetailsFetcher",
]
