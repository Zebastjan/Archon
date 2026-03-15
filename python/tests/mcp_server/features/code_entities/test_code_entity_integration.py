"""Integration tests for code entity functionality.

These tests use the actual language parsing infrastructure with realistic
code samples to ensure the full pipeline works correctly.
"""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server.services.code_entity_service import CodeEntityService
from src.server.services.languages import CodeEntity, CodeRelationship


# =============================================================================
# Realistic Code Samples
# =============================================================================

PYTHON_SAMPLE = '''
"""User authentication module."""

from typing import Optional
import hashlib

class UserAuthenticator:
    """Handles user authentication logic."""
    
    def __init__(self, db_connection: str):
        self.db = db_connection
    
    async def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        """Authenticate a user with username and password.
        
        Args:
            username: The user's username
            password: The user's password
            
        Returns:
            User data dict if authenticated, None otherwise
        """
        hashed = self._hash_password(password)
        return await self._verify_credentials(username, hashed)
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    async def _verify_credentials(self, username: str, hashed_pw: str) -> Optional[dict]:
        """Verify credentials against database."""
        # Database lookup would go here
        return None


class TokenManager:
    """Manages JWT tokens for authenticated users."""
    
    def __init__(self, secret_key: str):
        self.secret = secret_key
    
    def generate_token(self, user_id: str) -> str:
        """Generate a new JWT token for a user."""
        return f"token_{user_id}"
    
    def validate_token(self, token: str) -> bool:
        """Validate a JWT token."""
        return token.startswith("token_")


def create_authenticator(db_url: str) -> UserAuthenticator:
    """Factory function to create an authenticator."""
    return UserAuthenticator(db_url)
'''

TYPESCRIPT_SAMPLE = '''
/**
 * User service for managing user data
 */

import { Database } from './database';
import { User, UserCreateInput } from './types';

export class UserService {
    private db: Database;
    
    constructor(database: Database) {
        this.db = database;
    }
    
    async findById(id: string): Promise<User | null> {
        return this.db.query('SELECT * FROM users WHERE id = $1', [id]);
    }
    
    async createUser(input: UserCreateInput): Promise<User> {
        const user = await this.db.insert('users', input);
        return user;
    }
    
    async updateUser(id: string, data: Partial<User>): Promise<User> {
        return this.db.update('users', id, data);
    }
    
    async deleteUser(id: string): Promise<boolean> {
        return this.db.delete('users', id);
    }
}

export interface UserValidator {
    validate(user: User): boolean;
}

export class EmailValidator implements UserValidator {
    validate(user: User): boolean {
        return user.email.includes('@');
    }
}
'''

JAVASCRIPT_SAMPLE = '''
/**
 * Utility functions for data processing
 */

const _ = require('lodash');

/**
 * Process raw data into formatted output
 * @param {Object} data - Raw input data
 * @returns {Object} Formatted output
 */
function processData(data) {
    const cleaned = cleanData(data);
    const transformed = transformData(cleaned);
    return formatOutput(transformed);
}

/**
 * Clean and normalize input data
 */
function cleanData(data) {
    return _.pickBy(data, val => val !== null && val !== undefined);
}

/**
 * Transform data structure
 */
function transformData(data) {
    return Object.entries(data).map(([key, value]) => ({
        name: key,
        value: value
    }));
}

/**
 * Format final output
 */
function formatOutput(items) {
    return {
        items,
        count: items.length,
        timestamp: Date.now()
    };
}

class DataProcessor {
    constructor(config) {
        this.config = config;
    }
    
    async processBatch(items) {
        const results = [];
        for (const item of items) {
            results.push(await this.processItem(item));
        }
        return results;
    }
    
    async processItem(item) {
        return processData(item);
    }
}

module.exports = { processData, DataProcessor };
'''


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_code_files():
    """Create temporary code files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create Python file
        py_file = base / "auth.py"
        py_file.write_text(PYTHON_SAMPLE)
        
        # Create TypeScript file
        ts_file = base / "user_service.ts"
        ts_file.write_text(TYPESCRIPT_SAMPLE)
        
        # Create JavaScript file
        js_file = base / "processor.js"
        js_file.write_text(JAVASCRIPT_SAMPLE)
        
        yield base


@pytest.fixture
def mock_db_connector():
    """Create a mock database connector."""
    mock = MagicMock()
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.fetchval = AsyncMock(return_value=0)
    return mock


# =============================================================================
# Language Extraction Tests
# =============================================================================

class TestLanguageExtraction:
    """Tests for language-specific code extraction."""
    
    def test_python_extraction(self, temp_code_files):
        """Test extracting entities from Python code."""
        from src.server.services.languages import get_language_for_file
        
        py_file = temp_code_files / "auth.py"
        lang_support = get_language_for_file(str(py_file))
        
        assert lang_support is not None
        assert lang_support.language_id == "python"
        
        content = py_file.read_text()
        entities, relationships = lang_support.extract_entities_and_relationships(
            content, str(py_file)
        )
        
        # Verify entities found (methods are prefixed with class name)
        entity_names = {e.name for e in entities}
        assert "UserAuthenticator" in entity_names
        assert "TokenManager" in entity_names
        assert "UserAuthenticator.authenticate_user" in entity_names
        assert "UserAuthenticator._hash_password" in entity_names
        assert "create_authenticator" in entity_names
        
        # Verify entity types
        classes = [e for e in entities if e.entity_type == "class"]
        functions = [e for e in entities if e.entity_type == "function"]
        methods = [e for e in entities if e.entity_type == "method"]
        
        assert len(classes) == 2  # UserAuthenticator, TokenManager
        assert len(functions) >= 1  # create_authenticator
        assert len(methods) >= 3  # authenticate_user, _hash_password, etc.
    
    def test_typescript_extraction(self, temp_code_files):
        """Test extracting entities from TypeScript code."""
        from src.server.services.languages import get_language_for_file
        
        ts_file = temp_code_files / "user_service.ts"
        lang_support = get_language_for_file(str(ts_file))
        
        assert lang_support is not None
        assert lang_support.language_id == "typescript"
        
        content = ts_file.read_text()
        entities, relationships = lang_support.extract_entities_and_relationships(
            content, str(ts_file)
        )
        
        # Verify entities found (methods are prefixed with class name)
        entity_names = {e.name for e in entities}
        assert "UserService" in entity_names
        assert "UserValidator" in entity_names  # Interface
        assert "EmailValidator" in entity_names
        assert "UserService.findById" in entity_names
        assert "UserService.createUser" in entity_names
    
    def test_javascript_extraction(self, temp_code_files):
        """Test extracting entities from JavaScript code."""
        from src.server.services.languages import get_language_for_file
        
        js_file = temp_code_files / "processor.js"
        lang_support = get_language_for_file(str(js_file))
        
        assert lang_support is not None
        # Note: JavaScript is handled by TypeScript parser
        assert lang_support.language_id == "typescript"
        
        content = js_file.read_text()
        entities, relationships = lang_support.extract_entities_and_relationships(
            content, str(js_file)
        )
        
        # Verify entities found
        entity_names = {e.name for e in entities}
        assert "processData" in entity_names
        assert "DataProcessor" in entity_names
        assert "cleanData" in entity_names
        assert "DataProcessor.processBatch" in entity_names
    
    def test_relationship_extraction(self, temp_code_files):
        """Test extracting relationships between entities."""
        from src.server.services.languages import get_language_for_file
        
        py_file = temp_code_files / "auth.py"
        lang_support = get_language_for_file(str(py_file))
        content = py_file.read_text()
        
        entities, relationships = lang_support.extract_entities_and_relationships(
            content, str(py_file)
        )
        
        # Should have some relationships (e.g., method calls within class)
        # The exact count depends on the parser implementation
        assert isinstance(relationships, list)
        
        # Verify relationship structure if any exist
        for rel in relationships:
            assert isinstance(rel, CodeRelationship)
            assert rel.source_name
            assert rel.target_name
            assert rel.relationship_type in [
                "CALLS", "INHERITS", "IMPORTS", "DEFINES", "USES",
                "DECORATES", "RETURNS", "ACCEPTS", "RAISES", "IMPLEMENTS"
            ]


# =============================================================================
# Service Layer Tests
# =============================================================================

class TestCodeEntityService:
    """Tests for CodeEntityService with mocked database."""
    
    @pytest.mark.asyncio
    async def test_find_entity_by_name(self, mock_db_connector):
        """Test finding entities by name."""
        # Setup mock return value
        mock_db_connector.fetch.return_value = [
            {
                "id": "uuid-1",
                "name": "UserService",
                "entity_type": "class",
                "language": "python",
                "file_path": "src/service.py",
                "line_start": 1,
                "line_end": 20,
            }
        ]
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            results = await service.find_entity_by_name(
                repo_id="repo-1",
                name="User",
            )
        
        assert len(results) == 1
        assert results[0]["name"] == "UserService"
        mock_db_connector.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_entity_by_id(self, mock_db_connector):
        """Test getting a single entity by ID."""
        mock_db_connector.fetchrow.return_value = {
            "id": "uuid-1",
            "name": "UserService",
            "entity_type": "class",
            "language": "python",
            "file_path": "src/service.py",
            "line_start": 1,
            "line_end": 20,
            "source_code": "class UserService:\n    pass",
        }
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            result = await service.get_entity_by_id("uuid-1")
        
        assert result is not None
        assert result["name"] == "UserService"
        assert result["source_code"] == "class UserService:\n    pass"
    
    @pytest.mark.asyncio
    async def test_get_entity_by_id_not_found(self, mock_db_connector):
        """Test getting a non-existent entity."""
        mock_db_connector.fetchrow.return_value = None
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            result = await service.get_entity_by_id("non-existent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_entities_in_file(self, mock_db_connector):
        """Test listing entities in a file."""
        mock_db_connector.fetch.return_value = [
            {
                "id": "uuid-1",
                "name": "UserService",
                "entity_type": "class",
                "language": "python",
                "file_path": "src/service.py",
                "line_start": 1,
                "line_end": 20,
            },
            {
                "id": "uuid-2",
                "name": "get_user",
                "entity_type": "function",
                "language": "python",
                "file_path": "src/service.py",
                "line_start": 22,
                "line_end": 30,
            },
        ]
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            results = await service.list_entities_in_file(
                repo_id="repo-1",
                file_path="src/service.py",
            )
        
        assert len(results) == 2
        assert results[0]["name"] == "UserService"
        assert results[1]["name"] == "get_user"
    
    @pytest.mark.asyncio
    async def test_get_repository_stats(self, mock_db_connector):
        """Test getting repository statistics."""
        # Setup mock returns for different queries
        mock_db_connector.fetch.side_effect = [
            # by_type query
            [
                {"entity_type": "class", "count": 10},
                {"entity_type": "function", "count": 50},
            ],
            # by_language query
            [
                {"language": "python", "count": 40},
                {"language": "typescript", "count": 20},
            ],
        ]
        mock_db_connector.fetchval.side_effect = [
            60,  # total entities
            25,  # relationship count
            15,  # file count
        ]
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            stats = await service.get_repository_stats("repo-1")
        
        assert stats["repo_id"] == "repo-1"
        assert stats["total_entities"] == 60
        assert stats["total_files"] == 15
        assert stats["by_type"]["class"] == 10
        assert stats["by_type"]["function"] == 50
        assert stats["by_language"]["python"] == 40
        assert stats["total_relationships"] == 25
    
    @pytest.mark.asyncio
    async def test_get_entity_relationships(self, mock_db_connector):
        """Test getting entity relationships."""
        # Mock outgoing relationships
        mock_db_connector.fetch.side_effect = [
            # Outgoing
            [
                {
                    "relationship_id": "rel-1",
                    "related_entity_id": "uuid-2",
                    "relationship_type": "CALLS",
                    "entity_name": "helper_function",
                    "entity_type": "function",
                    "file_path": "src/utils.py",
                    "metadata": {},
                }
            ],
            # Incoming (empty for this test)
            [],
        ]
        
        service = CodeEntityService()
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            relationships = await service.get_entity_relationships(
                entity_id="uuid-1",
                direction="both",
            )
        
        assert len(relationships) == 1
        assert relationships[0]["relationship_type"] == "CALLS"
        assert relationships[0]["entity_name"] == "helper_function"


# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================

class TestExtractionPipeline:
    """Tests for the full extraction and storage pipeline."""
    
    @pytest.mark.asyncio
    async def test_extract_and_store_entities(self, temp_code_files, mock_db_connector):
        """Test the full extraction and storage flow."""
        from src.server.services.languages import get_language_for_file
        
        py_file = temp_code_files / "auth.py"
        content = py_file.read_text()
        
        # Extract entities
        lang_support = get_language_for_file(str(py_file))
        entities, relationships = lang_support.extract_entities_and_relationships(
            content, str(py_file)
        )
        
        # Setup mock to return entity IDs on insert
        entity_ids = [{"id": f"entity-{i}"} for i in range(len(entities))]
        mock_db_connector.fetchrow.side_effect = entity_ids
        
        service = CodeEntityService()
        
        # Mock file content getter
        async def get_content(repo_id, commit_sha, file_path):
            return content
        
        with patch.object(service, '_get_db', return_value=mock_db_connector):
            results = await service.extract_and_store_entities(
                repo_id="repo-1",
                commit_sha="abc123",
                file_paths=[str(py_file)],
                file_content_getter=get_content,
            )
        
        assert results["processed"] == 1
        assert results["entities_created"] == len(entities)
        assert len(results["errors"]) == 0
    
    def test_entity_dataclass_structure(self):
        """Test that CodeEntity dataclass has expected structure."""
        entity = CodeEntity(
            name="test_function",
            entity_type="function",
            line_start=1,
            line_end=10,
            signature="def test_function():",
            docstring="Test docstring",
            source_code="def test_function():\n    pass",
        )
        
        assert entity.name == "test_function"
        assert entity.entity_type == "function"
        assert entity.line_start == 1
        assert entity.line_end == 10
        # Verify file_path is not a field (it's passed separately to storage)
        assert not hasattr(entity, 'file_path') or entity.file_path is None
    
    def test_relationship_dataclass_structure(self):
        """Test that CodeRelationship dataclass has expected structure."""
        rel = CodeRelationship(
            source_name="caller",
            target_name="callee",
            relationship_type="CALLS",
            metadata={"line": 42},
        )
        
        assert rel.source_name == "caller"
        assert rel.target_name == "callee"
        assert rel.relationship_type == "CALLS"
        assert rel.metadata == {"line": 42}


# =============================================================================
# Language Support Tests
# =============================================================================

class TestLanguageSupport:
    """Tests for language support detection."""
    
    @pytest.mark.parametrize("filename,expected_lang", [
        ("test.py", "python"),
        ("test.ts", "typescript"),
        ("test.tsx", "typescript"),
        ("test.js", "typescript"),  # JavaScript handled by TypeScript parser
        ("test.jsx", "typescript"),  # JSX handled by TypeScript parser
        ("unknown.xyz", None),
    ])
    def test_language_detection(self, filename, expected_lang):
        """Test that file extensions map to correct languages."""
        from src.server.services.languages import get_language_for_file
        
        lang_support = get_language_for_file(filename)
        
        if expected_lang:
            assert lang_support is not None
            assert lang_support.language_id == expected_lang
        else:
            assert lang_support is None
    
    def test_all_supported_languages(self):
        """Test that expected languages are supported."""
        from src.server.services.languages import get_language_registry
        
        registry = get_language_registry()
        supported = registry.list_languages()
        
        # Check that core languages are supported
        assert "python" in supported
        assert "typescript" in supported
        
        # Log what languages are actually available
        print(f"Supported languages: {supported}")
