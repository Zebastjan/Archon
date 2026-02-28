# Git Integration Test Suite

This directory contains integration tests that exercise the Git ingestion layer
without invoking the chunker or downstream embedding pipeline. The goal is to
validate the Git repository service in isolation while Dockling/Tree-sitter work
is underway.

## What the tests cover

* Repository registration metadata (`GitRepositoryService.register_repository`)
* Commit synchronization into the Supabase mirror (`sync_commits`)
* File tree inspection and binary/text detection (`get_file_tree`)

Each test constructs a synthetic repository on the fly using `git init`, so no
network access or pre-baked fixtures are required.

## Running the tests

The suite installs its own minimal fixtures under this directory. To prevent the
project-wide `tests/conftest.py` from loading (it bootstraps FastAPI, Supabase,
and other services), invoke `pytest` with a `--confcutdir` that points here:

```bash
cd python
PYTHONPATH=$(pwd) pytest tests/git_integration -q --confcutdir=tests/git_integration
```

You can add this to a helper script or Makefile target such as `make test-git`
for easier use and CI automation.

## Next steps

* Mirror this structure for other subsystems (e.g., Docling + Tree-sitter) so
  they can be exercised independently.
* Once the chunker API stabilises, add a higher-level suite that composes the
  Git tests with chunking and RAG assertions.
