"""
LLM Provider Cache Module

Provides secure settings caching with TTL and validation.
"""

import hashlib
import json
import time
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)

# Secure settings cache with TTL and validation
_settings_cache: dict[str, tuple[Any, float, str]] = {}  # value, timestamp, checksum
_CACHE_TTL_SECONDS = 300  # 5 minutes
_cache_access_log: list[dict] = []  # Track cache access patterns for security monitoring


def _sanitize_for_log(text: str) -> str:
    """Basic text sanitization for logging."""
    if not text:
        return ""
    import re

    sanitized = re.sub(r"sk-[a-zA-Z0-9-_]{20,}", "[REDACTED]", text)
    sanitized = re.sub(r"xai-[a-zA-Z0-9-_]{20,}", "[REDACTED]", sanitized)
    return sanitized[:100]


def _calculate_cache_checksum(value: Any) -> str:
    """Calculate checksum for cache entry integrity validation."""
    # Convert value to JSON string for consistent hashing
    try:
        value_str = json.dumps(value, sort_keys=True, default=str)
        return hashlib.sha256(value_str.encode()).hexdigest()[:16]  # First 16 chars for efficiency
    except Exception:
        # Fallback for non-serializable objects
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _log_cache_access(key: str, action: str, hit: bool = None, security_event: str = None) -> None:
    """Log cache access for security monitoring."""
    access_entry = {
        "timestamp": time.time(),
        "key": _sanitize_for_log(key),
        "action": action,  # "get", "set", "invalidate", "clear"
        "hit": hit,  # For get operations
        "security_event": security_event,  # "checksum_mismatch", "expired", etc.
    }

    # Keep only last 100 access entries to prevent memory growth
    _cache_access_log.append(access_entry)
    if len(_cache_access_log) > 100:
        _cache_access_log.pop(0)

    # Log security events at warning level
    if security_event:
        safe_key = _sanitize_for_log(key)
        logger.warning(f"Cache security event: {security_event} for key '{safe_key}'")


def _get_cached_settings(key: str) -> Any | None:
    """Get cached settings if not expired and valid."""
    try:
        if key in _settings_cache:
            value, timestamp, stored_checksum = _settings_cache[key]
            current_time = time.time()

            # Check expiration with strict TTL enforcement
            if current_time - timestamp >= _CACHE_TTL_SECONDS:
                # Expired, remove from cache
                del _settings_cache[key]
                _log_cache_access(key, "get", hit=False, security_event="expired")
                return None

            # Verify cache entry integrity
            current_checksum = _calculate_cache_checksum(value)
            if current_checksum != stored_checksum:
                # Cache tampering detected, remove entry
                del _settings_cache[key]
                _log_cache_access(key, "get", hit=False, security_event="checksum_mismatch")
                logger.warning(f"Cache integrity check failed for key '{_sanitize_for_log(key)}'")
                return None

            _log_cache_access(key, "get", hit=True)
            return value

        _log_cache_access(key, "get", hit=False)
        return None

    except Exception as e:
        logger.warning(f"Error accessing cache for key '{_sanitize_for_log(key)}': {e}")
        return None


def _set_cached_settings(key: str, value: Any) -> None:
    """Set cached settings with integrity checksum."""
    try:
        checksum = _calculate_cache_checksum(value)
        _settings_cache[key] = (value, time.time(), checksum)
        _log_cache_access(key, "set")
        logger.debug(f"Cached settings for key '{_sanitize_for_log(key)}'")
    except Exception as e:
        logger.warning(f"Error caching settings for key '{_sanitize_for_log(key)}': {e}")


def clear_provider_cache() -> None:
    """Clear all provider-related caches."""
    global _settings_cache
    cache_size = len(_settings_cache)
    _settings_cache.clear()
    _log_cache_access("*", "clear")
    logger.info(f"Cleared {cache_size} entries from provider cache")


def invalidate_provider_cache(provider: str = None) -> None:
    """Invalidate cache entries for a specific provider or all providers."""
    global _settings_cache

    if provider:
        # Invalidate specific provider
        keys_to_remove = [key for key in _settings_cache.keys() if provider.lower() in key.lower()]
        for key in keys_to_remove:
            del _settings_cache[key]
            _log_cache_access(key, "invalidate")
        logger.info(f"Invalidated {len(keys_to_remove)} cache entries for provider '{provider}'")
    else:
        # Clear all provider-related caches
        provider_keys = [
            key
            for key in _settings_cache.keys()
            if any(p in key.lower() for p in ["provider", "embedding", "llm", "rag"])
        ]
        for key in provider_keys:
            del _settings_cache[key]
            _log_cache_access(key, "invalidate")
        logger.info(f"Invalidated {len(provider_keys)} provider cache entries")


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics for monitoring."""
    current_time = time.time()
    total_entries = len(_settings_cache)

    # Count expired entries
    expired_count = sum(
        1 for _, timestamp, _ in _settings_cache.values() if current_time - timestamp >= _CACHE_TTL_SECONDS
    )

    # Count recent access patterns
    recent_accesses = [
        entry
        for entry in _cache_access_log
        if current_time - entry["timestamp"] <= 60  # Last minute
    ]

    hit_count = sum(1 for entry in recent_accesses if entry.get("hit"))
    miss_count = len(recent_accesses) - hit_count

    # Security events in last hour
    security_events = [
        entry
        for entry in _cache_access_log
        if entry.get("security_event") and current_time - entry["timestamp"] <= 3600
    ]

    return {
        "total_entries": total_entries,
        "expired_entries": expired_count,
        "valid_entries": total_entries - expired_count,
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "recent_accesses_last_minute": len(recent_accesses),
        "recent_hits": hit_count,
        "recent_misses": miss_count,
        "hit_rate": hit_count / len(recent_accesses) if recent_accesses else 0,
        "security_events_last_hour": len(security_events),
        "access_log_size": len(_cache_access_log),
    }


def get_cache_security_report() -> dict[str, Any]:
    """Generate a security report for cache monitoring."""
    current_time = time.time()

    # Analyze all security events
    all_security_events = [entry for entry in _cache_access_log if entry.get("security_event")]

    # Group by event type
    event_counts = {}
    for entry in all_security_events:
        event_type = entry["security_event"]
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    # Recent events (last 15 minutes)
    recent_events = [entry for entry in all_security_events if current_time - entry["timestamp"] <= 900]

    # Check for suspicious patterns
    suspicious_patterns = []

    # High rate of checksum mismatches
    if event_counts.get("checksum_mismatch", 0) > 5:
        suspicious_patterns.append("High rate of checksum mismatches - potential tampering")

    # High rate of expired entries accessed
    if event_counts.get("expired", 0) > 20:
        suspicious_patterns.append("High rate of expired cache access - consider increasing TTL")

    return {
        "total_security_events": len(all_security_events),
        "events_by_type": event_counts,
        "recent_events_last_15min": len(recent_events),
        "suspicious_patterns_detected": suspicious_patterns,
        "recommendations": [
            "Monitor checksum_mismatch events for potential cache tampering",
            "Review expired event rate to optimize cache TTL",
            "Consider implementing cache encryption for sensitive data",
        ]
        if suspicious_patterns
        else [],
        "status": "review_required" if suspicious_patterns else "healthy",
    }
