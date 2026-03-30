"""
Test SQL injection protection in DatabaseConnector convenience methods.

These tests verify that the validation functions properly reject
malicious table and column names while allowing valid ones.
"""

import pytest

from src.server.services.database.db_connector import (
    ALLOWED_TABLES,
    SQLInjectionError,
    _validate_identifier,
    _validate_table_name,
)


class TestValidateIdentifier:
    """Test the _validate_identifier function."""

    def test_valid_simple_identifier(self):
        """Should accept simple valid identifiers."""
        # These should not raise
        _validate_identifier("archon_sources", "table name")
        _validate_identifier("source_id", "column name")
        _validate_identifier("_private_col", "column name")
        _validate_identifier("CamelCase", "column name")

    def test_valid_with_numbers(self):
        """Should accept identifiers with numbers (not at start)."""
        _validate_identifier("archon_123", "table name")
        _validate_identifier("col_1", "column name")
        _validate_identifier("version_2_0", "column name")

    def test_rejects_empty_string(self):
        """Should reject empty identifiers."""
        with pytest.raises(SQLInjectionError, match="cannot be empty"):
            _validate_identifier("", "table name")

    def test_rejects_starts_with_number(self):
        """Should reject identifiers starting with numbers."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("123_table", "table name")

    def test_rejects_sql_injection_semicolon(self):
        """Should reject semicolons (common SQL injection)."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon; DROP TABLE", "table name")

    def test_rejects_sql_injection_dash(self):
        """Should reject dashes (SQL comment syntax)."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon--drop", "table name")

    def test_rejects_sql_injection_quote(self):
        """Should reject quotes (string termination)."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon'; DROP", "table name")

    def test_rejects_sql_injection_union(self):
        """Should reject UNION-based injection patterns."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon_sources UNION SELECT", "table name")

    def test_rejects_sql_injection_comment(self):
        """Should reject SQL comments."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon_sources /* comment */", "table name")

    def test_rejects_sql_injection_or(self):
        """Should reject OR-based injection."""
        with pytest.raises(SQLInjectionError):
            _validate_identifier("archon_sources OR 1=1", "table name")

    def test_rejects_non_string(self):
        """Should reject non-string values."""
        with pytest.raises(SQLInjectionError, match="must be a string"):
            _validate_identifier(123, "table name")

    def test_rejects_special_chars(self):
        """Should reject various special characters."""
        bad_chars = [
            "table.name",  # dot
            "table:name",  # colon
            "table/name",  # slash
            "table@name",  # at sign
            "table#name",  # hash
            "table$name",  # dollar sign
            "table%name",  # percent
            "table&name",  # ampersand
            "table*name",  # asterisk
            "table(name)",  # parentheses
            "table[name]",  # brackets
            "table{name}",  # braces
            "table'name",  # single quote
            'table"name',  # double quote
            "table`name",  # backtick
            "table name",  # space
            "table\tname",  # tab
            "table\nname",  # newline
        ]
        for bad in bad_chars:
            with pytest.raises(SQLInjectionError, msg=f"Should reject: {bad}"):
                _validate_identifier(bad, "column name")


class TestValidateTableName:
    """Test the _validate_table_name function."""

    def test_valid_archon_tables(self):
        """Should accept all allowed Archon tables."""
        for table in ALLOWED_TABLES:
            # These should not raise
            _validate_table_name(table)

    def test_rejects_unknown_table(self):
        """Should reject tables not in allowlist."""
        with pytest.raises(SQLInjectionError, match="not in the allowed tables"):
            _validate_table_name("users")

    def test_rejects_information_schema(self):
        """Should reject information_schema (sensitive)."""
        with pytest.raises(SQLInjectionError, match="not in the allowed tables"):
            _validate_table_name("information_schema.tables")

    def test_rejects_pg_catalog(self):
        """Should reject pg_catalog tables."""
        with pytest.raises(SQLInjectionError, match="not in the allowed tables"):
            _validate_table_name("pg_catalog.pg_tables")

    def test_rejects_injection_in_known_table_name(self):
        """Should reject even if it looks like an archon table but has injection."""
        with pytest.raises(SQLInjectionError):
            _validate_table_name("archon_sources; DROP TABLE archon_code_entities;")


class TestAllowedTablesList:
    """Test that the allowed tables list is comprehensive."""

    def test_all_tables_start_with_archon(self):
        """All allowed tables should start with 'archon_'."""
        for table in ALLOWED_TABLES:
            assert table.startswith("archon_"), f"Table {table} should start with 'archon_'"

    def test_no_duplicates(self):
        """Allowed tables should have no duplicates."""
        assert len(ALLOWED_TABLES) == len(set(ALLOWED_TABLES))

    def test_common_tables_present(self):
        """Common Archon tables should be in the list."""
        essential_tables = [
            "archon_code_entities",
            "archon_code_repos",
            "archon_code_relationships",
            "archon_settings",
            "archon_sources",
            "archon_crawled_pages",
        ]
        for table in essential_tables:
            assert table in ALLOWED_TABLES, f"Essential table {table} missing from allowlist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
