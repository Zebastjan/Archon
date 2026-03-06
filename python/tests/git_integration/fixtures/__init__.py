"""Git Test Fixtures

Test repository fixtures for Git integration testing.

Usage:
    from tests.git_integration.fixtures.generator import generate_fixture, get_fixture_path

    # Generate a specific fixture
    repo_path = generate_fixture(get_fixture_path("simple-commits"))

    # Or generate all fixtures
    from tests.git_integration.fixtures.generator import generate_all_fixtures
    fixtures = generate_all_fixtures()
"""

from tests.git_integration.fixtures.generator import (
    generate_all_fixtures,
    generate_expected,
    generate_fixture,
    get_fixture_path,
    parse_spec,
)

__all__ = [
    "generate_all_fixtures",
    "generate_expected",
    "generate_fixture",
    "get_fixture_path",
    "parse_spec",
]
