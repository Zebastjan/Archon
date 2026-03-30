#!/usr/bin/env python3
"""Check language registry status"""
import sys
sys.path.insert(0, '/home/zebastjan/dev/archon/python/src')

from server.services.languages.language_registry import get_language_registry

r = get_language_registry()
print("Languages:", r.list_languages())
print("Extensions:", r.list_extensions())
print("Nim support:", r.get_for_file('test.nim'))
