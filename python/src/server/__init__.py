"""Server package entrypoint."""

from __future__ import annotations

from importlib import import_module

# Provide lightweight accessors without importing heavy optional dependencies.

def _lazy_import(name: str):
    def _loader():
        return import_module(name)

    class _ModuleProxy:
        def __getattr__(self, item):
            module = import_module(name)
            return getattr(module, item)

        def __dir__(self):
            module = import_module(name)
            return sorted(set(dir(module)))

    return _ModuleProxy()


utils = _lazy_import("src.server.utils")
services = _lazy_import("src.server.services")

__all__ = ["utils", "services"]
