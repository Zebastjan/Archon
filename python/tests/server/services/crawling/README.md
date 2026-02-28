# Tree-Sitter Chunking Integration Tests

The tests in this directory exercise Tree-Sitter-based captures that the Dockling
chunker will eventually consume. They currently run against synthetic source
snippets and include a placeholder `xfail` that will be replaced once the chunker
integration is ready.

## Running the suite

```bash
pytest --confcutdir=tests/server tests/server/services/crawling/test_tree_sitter_chunking.py -q
```

or via marker:

```bash
pytest -m tree_sitter_integration
```

The tests rely on the lightweight `tests/server/conftest.py` to avoid importing the
fully configured Archon app or optional dependencies (e.g., OpenAI clients).
