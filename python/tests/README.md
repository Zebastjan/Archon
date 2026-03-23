# Archon Testing Guide

This document describes the testing conventions and patterns used in the Archon project.

## Test Categories

Tests are categorized using pytest markers:

| Marker | Description | When to Use |
|--------|-------------|-------------|
| `@pytest.mark.unit` | Unit tests with mocks | Testing isolated functions/classes |
| `@pytest.mark.integration` | Integration tests | Testing component interactions |
| `@pytest.mark.e2e` | End-to-end tests | Testing with live services |
| `@pytest.mark.slow` | Slow-running tests | Tests that take significant time |

## Running Tests

```bash
# Run all tests
pytest tests/

# Run only unit tests
pytest tests/ -m unit

# Run only integration tests
pytest tests/ -m integration

# Run only E2E tests
pytest tests/ -m e2e

# Run tests excluding slow tests
pytest tests/ -m "not slow"
```

## Test Organization

```
tests/
├── conftest.py              # Global fixtures and configuration
├── e2e/                     # End-to-end tests (requires live services)
│   ├── conftest.py
│   └── test_mcp_tools_e2e.py
├── git_integration/         # Git service tests (excellent pattern)
│   ├── conftest.py
│   ├── fixtures/
│   │   └── generators/      # Programmatic fixture generation
│   └── test_*.py
├── mcp_server/features/     # MCP tool tests
│   ├── code_audit/
│   ├── code_entities/
│   ├── documents/
│   └── ...
└── agent_work_orders/       # Agent workflow tests
```

## Testing Patterns

### Programmatic Fixtures (Recommended)

Follow the pattern from `tests/git_integration/` - create test fixtures programmatically:

```python
# fixtures/generators/my_feature.py
from pathlib import Path
import subprocess

def create_test_fixture(base_path: Path) -> MyFixture:
    """Create a test fixture with realistic data."""
    # Create actual files, git repos, etc.
    return MyFixture(...)
```

### Realistic Mock Objects

Use detailed mock objects that mirror real data:

```python
@dataclass
class MockCodeEntity:
    id: str
    name: str
    entity_type: str
    language: str
    file_path: str
    line_start: int
    line_end: int
```

### Test Isolation

Each test should create its own fixtures - don't share state between tests.

## MCP Tool Testing

When testing MCP tools, verify:

1. Tool registration (all tools are registered)
2. Tool functionality with mocked dependencies
3. Error handling and edge cases
4. Integration with real services (E2E)

```python
def test_all_tools_registered(mock_mcp):
    """Verify all MCP tools are registered."""
    register_my_tools(mock_mcp)
    expected_tools = ["tool_one", "tool_two"]
    for tool in expected_tools:
        assert tool in mock_mcp._tools
```

## Git Integration Tests (Best Reference)

The `tests/git_integration/` directory demonstrates the ideal pattern:

- **Programmatic fixture generation** - Creates real git repos on-the-fly
- **Comprehensive scenarios** - Branch divergence, merges, deletions, edge cases
- **Clear documentation** - Each generator has detailed docstrings
- **Test isolation** - Each test is independent

Study these files as the reference implementation:
- `fixtures/generators/divergent_files.py`
- `fixtures/generators/merge_scenarios.py`
- `test_git_repository_integration.py`

## CI/CD

Tests run in GitHub Actions (see `.github/workflows/ci.yml`):

- Backend tests with pytest + coverage
- Docker build verification
- Codecov integration

## Best Practices

1. **Use descriptive test names** - `test_project_creation_with_valid_data`
2. **One assertion per test** when possible - easier to debug
3. **Clean up after tests** - Remove temp files, close connections
4. **Document complex fixtures** - Explain what the fixture represents
5. **Use markers** - Categorize tests for selective execution
6. **Prefer programmatic fixtures** - More realistic than static data
