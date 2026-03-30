#!/usr/bin/env python3
"""Test Nim language support"""
import sys
from pathlib import Path

# Add python/src to path
SRC_PATH = Path(__file__).parent / "python" / "src"
sys.path.insert(0, str(SRC_PATH))

# Test 1: Check tree-sitter-language-pack
try:
    from tree_sitter_language_pack import get_language
    lang = get_language('nim')
    print(f"✓ tree-sitter-language-pack nim loaded: {type(lang).__name__}")
except Exception as e:
    print(f"✗ tree-sitter-language-pack error: {e}")
    sys.exit(1)

# Test 2: Check NimLanguageSupport
try:
    from server.services.languages.nim_support import NimLanguageSupport
    support = NimLanguageSupport()
    print(f"✓ NimLanguageSupport initialized")
    print(f"  language_id: {support.language_id}")
    print(f"  extensions: {support.file_extensions}")
except Exception as e:
    print(f"✗ NimLanguageSupport error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Parse sample Nim code
sample = '''
type
  Person = object
    name: string
    age: int

proc greet(p: Person): string =
  result = "Hello, " & p.name
'''

try:
    entities, relationships = support.extract_entities_and_relationships(sample, "test.nim")
    print(f"✓ Parsed sample Nim code")
    print(f"  Entities: {len(entities)}")
    for e in entities:
        print(f"    - {e.entity_type}: {e.name}")
    print(f"  Relationships: {len(relationships)}")
except Exception as e:
    print(f"✗ Parse error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All Nim tests passed!")
