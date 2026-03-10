"""Fixture generators for git integration tests."""

from tests.git_integration.fixtures.generators.divergent_files import (
    DivergentFilesFixture,
    create_divergent_files_fixture,
)
from tests.git_integration.fixtures.generators.edge_cases import (
    EdgeCasesFixture,
    create_edge_cases_fixture,
)
from tests.git_integration.fixtures.generators.file_deletions import (
    FileDeletionsFixture,
    create_file_deletions_fixture,
)
from tests.git_integration.fixtures.generators.merge_scenarios import (
    MergeScenariosFixture,
    create_merge_scenarios_fixture,
)

__all__ = [
    "DivergentFilesFixture",
    "create_divergent_files_fixture",
    "EdgeCasesFixture",
    "create_edge_cases_fixture",
    "FileDeletionsFixture",
    "create_file_deletions_fixture",
    "MergeScenariosFixture",
    "create_merge_scenarios_fixture",
]
