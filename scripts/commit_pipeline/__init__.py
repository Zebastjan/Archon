"""Commit Pipeline - Async post-commit stages.

Runs after commit_with_review() to:
1. Check doc maintenance
2. Report test coverage gaps
3. Run code audit

Results written to .archon/hooks/last-run.json
"""

from .orchestrator import run_pipeline

__all__ = ["run_pipeline"]
