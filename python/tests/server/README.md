# Tree-Sitter Test Suites

This directory contains isolated pytest suites for validating Archon's Tree-Sitter
integration at multiple levels.

## Test Matrix

| Suite | Marker | Command | Purpose |
| --- | --- | --- | --- |
| Infrastructure | `tree_sitter_unit` | `pytest --confcutdir=tests/server tests/server/test_tree_sitter_infrastructure.py -q` | Language loading, parser basics, query sampling |
| Chunking scaffold | `tree_sitter_integration` | `pytest --confcutdir=tests/server tests/server/services/crawling/test_tree_sitter_chunking.py -q` | Syntax-aware captures, future chunker boundary checks |

Once the Dockling chunker integration lands, replace the xfailed placeholder in
`test_tree_sitter_chunking.py` with real assertions.

## Marker usage

```bash
# Run only the Tree-Sitter infrastructure unit tests
pytest -m tree_sitter_unit

# Run Tree-Sitter chunking integration tests (once chunker is ready)
pytest -m tree_sitter_integration
```

Because these suites rely on the lightweight `tests/server/conftest.py`, they avoid
pulling in heavy global fixtures and optional dependencies.
