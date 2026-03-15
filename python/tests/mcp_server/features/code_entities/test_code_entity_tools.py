"""Comprehensive tests for code entity MCP tools.

These tests use realistic fixtures and battle-tested patterns from the git integration
tests. They test the actual functionality of the MCP tools with mocked services.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import Context

from src.mcp_server.features.code_entities.tools import register_code_entity_tools


# =============================================================================
# Realistic Test Fixtures
# =============================================================================

@dataclass
class MockCodeEntity:
    """Represents a realistic code entity for testing."""
    id: str
    name: str
    entity_type: str
    language: str
    file_path: str
    line_start: int
    line_end: int
    signature: str | None = None
    docstring: str | None = None
    source_code: str | None = None
    repo_id: str | None = None
    commit_sha: str | None = None


class MockDatabase:
    """In-memory mock database for realistic testing."""
    
    def __init__(self):
        self.entities: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []
    
    def add_entity(self, entity: MockCodeEntity) -> dict[str, Any]:
        """Add an entity and return the stored record."""
        record = {
            "id": entity.id or str(uuid.uuid4()),
            "name": entity.name,
            "entity_type": entity.entity_type,
            "language": entity.language,
            "file_path": entity.file_path,
            "line_start": entity.line_start,
            "line_end": entity.line_end,
            "signature": entity.signature,
            "docstring": entity.docstring,
            "source_code": entity.source_code,
            "repo_id": entity.repo_id,
            "commit_sha": entity.commit_sha or "abc123",
        }
        self.entities.append(record)
        return record
    
    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Add a relationship between entities."""
        record = {
            "id": str(uuid.uuid4()),
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "relationship_type": relationship_type,
            "metadata": metadata or {},
        }
        self.relationships.append(record)
        return record
    
    def find_by_name(self, repo_id: str, name: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Find entities by name (partial match)."""
        results = []
        name_lower = name.lower()
        for entity in self.entities:
            if entity["repo_id"] == repo_id and name_lower in entity["name"].lower():
                if entity_type is None or entity["entity_type"] == entity_type:
                    results.append(dict(entity))
        return results
    
    def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity by ID."""
        for entity in self.entities:
            if entity["id"] == entity_id:
                return dict(entity)
        return None
    
    def get_relationships(
        self,
        entity_id: str,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get relationships for an entity."""
        results = []
        
        if direction in ("outgoing", "both"):
            for rel in self.relationships:
                if rel["source_entity_id"] == entity_id:
                    target = self.get_by_id(rel["target_entity_id"])
                    if target:
                        results.append({
                            "relationship_id": rel["id"],
                            "related_entity_id": rel["target_entity_id"],
                            "relationship_type": rel["relationship_type"],
                            "entity_name": target["name"],
                            "entity_type": target["entity_type"],
                            "file_path": target["file_path"],
                            "metadata": rel["metadata"],
                        })
        
        if direction in ("incoming", "both"):
            for rel in self.relationships:
                if rel["target_entity_id"] == entity_id:
                    source = self.get_by_id(rel["source_entity_id"])
                    if source:
                        results.append({
                            "relationship_id": rel["id"],
                            "related_entity_id": rel["source_entity_id"],
                            "relationship_type": rel["relationship_type"],
                            "entity_name": source["name"],
                            "entity_type": source["entity_type"],
                            "file_path": source["file_path"],
                            "metadata": rel["metadata"],
                        })
        
        return results
    
    def list_entities_in_file(
        self,
        repo_id: str,
        file_path: str,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List entities in a specific file."""
        results = []
        for entity in self.entities:
            if entity["repo_id"] == repo_id and entity["file_path"] == file_path:
                if entity_type is None or entity["entity_type"] == entity_type:
                    results.append(dict(entity))
        # Sort by line_start
        results.sort(key=lambda e: e["line_start"])
        return results
    
    def get_stats(self, repo_id: str) -> dict[str, Any]:
        """Get repository statistics."""
        repo_entities = [e for e in self.entities if e["repo_id"] == repo_id]
        
        # Count by type
        by_type: dict[str, int] = {}
        by_language: dict[str, int] = {}
        files: set[str] = set()
        
        for entity in repo_entities:
            by_type[entity["entity_type"]] = by_type.get(entity["entity_type"], 0) + 1
            by_language[entity["language"]] = by_language.get(entity["language"], 0) + 1
            files.add(entity["file_path"])
        
        # Count relationships
        repo_entity_ids = {e["id"] for e in repo_entities}
        rel_count = sum(
            1 for rel in self.relationships
            if rel["source_entity_id"] in repo_entity_ids
        )
        
        return {
            "repo_id": repo_id,
            "total_entities": len(repo_entities),
            "total_files": len(files),
            "by_type": by_type,
            "by_language": by_language,
            "total_relationships": rel_count,
        }


@pytest.fixture
def mock_db():
    """Create a populated mock database with realistic entities."""
    db = MockDatabase()
    repo_id = "76abe5b8-693a-40e4-a3a3-c08289465d7d"
    
    # Add realistic Python service entities
    db.add_entity(MockCodeEntity(
        id="entity-001",
        name="CodeEntityService",
        entity_type="class",
        language="python",
        file_path="src/services/code_entity_service.py",
        line_start=1,
        line_end=50,
        signature="class CodeEntityService:",
        docstring="Service for managing code entities and relationships.",
        source_code="class CodeEntityService:\n    pass",
        repo_id=repo_id,
    ))
    
    db.add_entity(MockCodeEntity(
        id="entity-002",
        name="find_entity_by_name",
        entity_type="function",
        language="python",
        file_path="src/services/code_entity_service.py",
        line_start=52,
        line_end=75,
        signature="async def find_entity_by_name(self, repo_id: str, name: str)",
        docstring="Find entities by name in a repository.",
        source_code="async def find_entity_by_name(self, repo_id, name):\n    pass",
        repo_id=repo_id,
    ))
    
    db.add_entity(MockCodeEntity(
        id="entity-003",
        name="get_entity_by_id",
        entity_type="function",
        language="python",
        file_path="src/services/code_entity_service.py",
        line_start=77,
        line_end=90,
        signature="async def get_entity_by_id(self, entity_id: str)",
        docstring="Get a single entity by its ID.",
        source_code="async def get_entity_by_id(self, entity_id):\n    pass",
        repo_id=repo_id,
    ))
    
    # Add TypeScript entities
    db.add_entity(MockCodeEntity(
        id="entity-004",
        name="UserAuthentication",
        entity_type="class",
        language="typescript",
        file_path="src/auth/UserAuthentication.ts",
        line_start=1,
        line_end=30,
        signature="export class UserAuthentication",
        docstring="Handles user authentication logic.",
        source_code="export class UserAuthentication {\n}",
        repo_id=repo_id,
    ))
    
    db.add_entity(MockCodeEntity(
        id="entity-005",
        name="authenticateUser",
        entity_type="function",
        language="typescript",
        file_path="src/auth/UserAuthentication.ts",
        line_start=32,
        line_end=45,
        signature="async authenticateUser(username: string, password: string)",
        docstring="Authenticate a user with username and password.",
        source_code="async authenticateUser(username, password) {\n}",
        repo_id=repo_id,
    ))
    
    # Add relationships
    db.add_relationship("entity-002", "entity-003", "CALLS")
    db.add_relationship("entity-005", "entity-004", "USES")
    
    return db, repo_id


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server for testing."""
    mock = MagicMock()
    mock._tools = {}

    def tool_decorator():
        def decorator(func):
            mock._tools[func.__name__] = func
            return func
        return decorator

    mock.tool = tool_decorator
    return mock


@pytest.fixture
def mock_context():
    """Create a mock context for testing."""
    return MagicMock(spec=Context)


# =============================================================================
# Test Suite
# =============================================================================

class TestCodebaseFindEntity:
    """Tests for codebase_find_entity tool."""
    
    @pytest.mark.asyncio
    async def test_find_entity_by_exact_name(self, mock_mcp, mock_db, mock_context):
        """Test finding an entity by exact name match."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        assert find_entity is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(return_value=[db.entities[0]])
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id=repo_id,
                name="CodeEntityService",
            )
            
            assert result["success"] is True
            assert result["count"] == 1
            assert result["entities"][0]["name"] == "CodeEntityService"
    
    @pytest.mark.asyncio
    async def test_find_entity_partial_match(self, mock_mcp, mock_db, mock_context):
        """Test finding entities with partial name match."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            # Return entities with "entity" in the name
            instance.find_entity_by_name = AsyncMock(return_value=[
                e for e in db.entities if "entity" in e["name"].lower()
            ])
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id=repo_id,
                name="entity",
            )
            
            assert result["success"] is True
            assert result["count"] >= 2  # Should find multiple
    
    @pytest.mark.asyncio
    async def test_find_entity_with_type_filter(self, mock_mcp, mock_db, mock_context):
        """Test finding entities filtered by type."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(return_value=[
                e for e in db.entities if e["entity_type"] == "function"
            ])
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id=repo_id,
                name="",
                entity_type="function",
            )
            
            assert result["success"] is True
            assert all(e["entity_type"] == "function" for e in result["entities"])
    
    @pytest.mark.asyncio
    async def test_find_entity_with_language_filter(self, mock_mcp, mock_db, mock_context):
        """Test finding entities filtered by language."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(return_value=[
                e for e in db.entities if e["language"] == "typescript"
            ])
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id=repo_id,
                name="",
                language="typescript",
            )
            
            assert result["success"] is True
            assert all(e["language"] == "typescript" for e in result["entities"])
    
    @pytest.mark.asyncio
    async def test_find_entity_no_results(self, mock_mcp, mock_db, mock_context):
        """Test finding entities when no matches exist."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(return_value=[])
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id=repo_id,
                name="NonExistentEntity",
            )
            
            assert result["success"] is True
            assert result["count"] == 0
            assert result["entities"] == []


class TestCodebaseGetEntityDetails:
    """Tests for codebase_get_entity_details tool."""
    
    @pytest.mark.asyncio
    async def test_get_entity_details_without_source(self, mock_mcp, mock_db, mock_context):
        """Test getting entity details without source code."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_details = mock_mcp._tools.get("codebase_get_entity_details")
        assert get_details is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_by_id = AsyncMock(return_value=db.entities[0])
            mock_service.return_value = instance
            
            result = await get_details(
                entity_id="entity-001",
                include_source=False,
            )
            
            assert result["success"] is True
            assert "entity" in result
            assert result["entity"]["name"] == "CodeEntityService"
            assert "source_code" not in result["entity"]
    
    @pytest.mark.asyncio
    async def test_get_entity_details_with_source(self, mock_mcp, mock_db, mock_context):
        """Test getting entity details with source code included."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_details = mock_mcp._tools.get("codebase_get_entity_details")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_by_id = AsyncMock(return_value=db.entities[0])
            mock_service.return_value = instance
            
            result = await get_details(
                entity_id="entity-001",
                include_source=True,
            )
            
            assert result["success"] is True
            assert "source_code" in result["entity"]
            assert result["entity"]["source_code"] == "class CodeEntityService:\n    pass"
    
    @pytest.mark.asyncio
    async def test_get_entity_details_not_found(self, mock_mcp, mock_db, mock_context):
        """Test getting details for non-existent entity."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_details = mock_mcp._tools.get("codebase_get_entity_details")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_by_id = AsyncMock(return_value=None)
            mock_service.return_value = instance
            
            result = await get_details(
                entity_id="non-existent-id",
            )
            
            assert result["success"] is False
            assert "error" in result
            assert "not found" in result["error"].lower()


class TestCodebaseGetEntityContext:
    """Tests for codebase_get_entity_context tool."""
    
    @pytest.mark.asyncio
    async def test_get_entity_context_with_both_directions(self, mock_mcp, mock_db, mock_context):
        """Test getting entity context with both callers and callees."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_context = mock_mcp._tools.get("codebase_get_entity_context")
        assert get_context is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_relationships = AsyncMock(return_value=db.get_relationships("entity-002", "both"))
            mock_service.return_value = instance
            
            result = await get_context(
                entity_id="entity-002",
                include_callees=True,
                include_callers=True,
            )
            
            assert result["success"] is True
            assert "relationships" in result
    
    @pytest.mark.asyncio
    async def test_get_entity_context_no_relationships_requested(self, mock_mcp, mock_db, mock_context):
        """Test getting entity context when no directions are requested."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_context = mock_mcp._tools.get("codebase_get_entity_context")
        
        result = await get_context(
            entity_id="entity-002",
            include_callees=False,
            include_callers=False,
        )
        
        assert result["success"] is True
        assert result["relationships"] == []
        assert "note" in result


class TestCodebaseSearchBySemantics:
    """Tests for codebase_search_by_semantics tool."""
    
    @pytest.mark.asyncio
    async def test_search_by_semantics_success(self, mock_mcp, mock_db, mock_context):
        """Test semantic search with successful embedding generation."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        search = mock_mcp._tools.get("codebase_search_by_semantics")
        assert search is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service, \
             patch("src.mcp_server.features.code_entities.tools.EmbeddingService") as mock_embed:
            
            # Mock embedding service
            embed_instance = MagicMock()
            embed_result = MagicMock()
            embed_result.success = True
            embed_result.embeddings = [[0.1] * 1024]  # 1024-dim embedding
            embed_result.error = None
            embed_instance.get_embeddings = AsyncMock(return_value=embed_result)
            mock_embed.return_value = embed_instance
            
            # Mock code entity service
            service_instance = MagicMock()
            service_instance.search_entities = AsyncMock(return_value=[
                {
                    **db.entities[0],
                    "similarity": 0.95,
                }
            ])
            mock_service.return_value = service_instance
            
            result = await search(
                repo_id=repo_id,
                query="find user authentication",
                top_k=5,
            )
            
            assert result["success"] is True
            assert result["count"] >= 1
            assert "entities" in result
            assert result["entities"][0]["similarity"] == 0.95
    
    @pytest.mark.asyncio
    async def test_search_by_semantics_embedding_failure(self, mock_mcp, mock_db, mock_context):
        """Test semantic search when embedding generation fails."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        search = mock_mcp._tools.get("codebase_search_by_semantics")
        
        with patch("src.mcp_server.features.code_entities.tools.EmbeddingService") as mock_embed:
            embed_instance = MagicMock()
            embed_result = MagicMock()
            embed_result.success = False
            embed_result.embeddings = None
            embed_result.error = "Embedding service unavailable"
            embed_instance.get_embeddings = AsyncMock(return_value=embed_result)
            mock_embed.return_value = embed_instance
            
            result = await search(
                repo_id=repo_id,
                query="find user authentication",
            )
            
            assert result["success"] is False
            assert "error" in result
            assert "embedding" in result["error"].lower()


class TestCodebaseListEntitiesInFile:
    """Tests for codebase_list_entities_in_file tool."""
    
    @pytest.mark.asyncio
    async def test_list_entities_in_file_success(self, mock_mcp, mock_db, mock_context):
        """Test listing entities in a specific file."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        list_entities = mock_mcp._tools.get("codebase_list_entities_in_file")
        assert list_entities is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.list_entities_in_file = AsyncMock(return_value=[
                e for e in db.entities
                if e["file_path"] == "src/services/code_entity_service.py"
            ])
            mock_service.return_value = instance
            
            result = await list_entities(
                repo_id=repo_id,
                file_path="src/services/code_entity_service.py",
            )
            
            assert result["success"] is True
            assert result["count"] == 3  # We added 3 entities in this file
            assert result["file_path"] == "src/services/code_entity_service.py"
    
    @pytest.mark.asyncio
    async def test_list_entities_in_file_with_type_filter(self, mock_mcp, mock_db, mock_context):
        """Test listing entities with type filter."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        list_entities = mock_mcp._tools.get("codebase_list_entities_in_file")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.list_entities_in_file = AsyncMock(return_value=[
                e for e in db.entities
                if e["file_path"] == "src/services/code_entity_service.py"
                and e["entity_type"] == "function"
            ])
            mock_service.return_value = instance
            
            result = await list_entities(
                repo_id=repo_id,
                file_path="src/services/code_entity_service.py",
                entity_type="function",
            )
            
            assert result["success"] is True
            assert result["count"] == 2  # 2 functions in this file
            assert all(e["entity_type"] == "function" for e in result["entities"])
    
    @pytest.mark.asyncio
    async def test_list_entities_in_file_empty(self, mock_mcp, mock_db, mock_context):
        """Test listing entities in a file that has no entities."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        list_entities = mock_mcp._tools.get("codebase_list_entities_in_file")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.list_entities_in_file = AsyncMock(return_value=[])
            mock_service.return_value = instance
            
            result = await list_entities(
                repo_id=repo_id,
                file_path="nonexistent/file.py",
            )
            
            assert result["success"] is True
            assert result["count"] == 0
            assert result["entities"] == []


class TestCodebaseGetRepositoryStats:
    """Tests for codebase_get_repository_stats tool."""
    
    @pytest.mark.asyncio
    async def test_get_repository_stats_success(self, mock_mcp, mock_db, mock_context):
        """Test getting repository statistics."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_stats = mock_mcp._tools.get("codebase_get_repository_stats")
        assert get_stats is not None
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_repository_stats = AsyncMock(return_value=db.get_stats(repo_id))
            mock_service.return_value = instance
            
            result = await get_stats(repo_id=repo_id)
            
            assert result["success"] is True
            assert "stats" in result
            stats = result["stats"]
            assert stats["total_entities"] == 5
            assert stats["total_files"] == 2
            assert "by_type" in stats
            assert "by_language" in stats
            assert stats["by_type"]["class"] == 2
            assert stats["by_type"]["function"] == 3
    
    @pytest.mark.asyncio
    async def test_get_repository_stats_failure(self, mock_mcp, mock_db, mock_context):
        """Test getting stats when service fails."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        get_stats = mock_mcp._tools.get("codebase_get_repository_stats")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_repository_stats = AsyncMock(return_value={})
            mock_service.return_value = instance
            
            result = await get_stats(repo_id="invalid-repo-id")
            
            assert result["success"] is False
            assert "error" in result


class TestToolRegistration:
    """Tests for tool registration."""
    
    def test_all_tools_registered(self, mock_mcp):
        """Verify all expected tools are registered."""
        register_code_entity_tools(mock_mcp)
        
        expected_tools = [
            "codebase_find_entity",
            "codebase_get_entity_details",
            "codebase_get_entity_context",
            "codebase_search_by_semantics",
            "codebase_list_entities_in_file",
            "codebase_get_repository_stats",
        ]
        
        for tool_name in expected_tools:
            assert tool_name in mock_mcp._tools, f"Tool {tool_name} not registered"
    
    def test_tools_are_callable(self, mock_mcp):
        """Verify registered tools are callable."""
        register_code_entity_tools(mock_mcp)
        
        for tool_name, tool_func in mock_mcp._tools.items():
            assert callable(tool_func), f"Tool {tool_name} is not callable"


# =============================================================================
# Integration-Style Tests
# =============================================================================

class TestRealisticWorkflows:
    """Tests that simulate realistic usage workflows."""
    
    @pytest.mark.asyncio
    async def test_find_and_explore_workflow(self, mock_mcp, mock_db, mock_context):
        """Test a realistic workflow: find entity, then explore its context."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        get_context = mock_mcp._tools.get("codebase_get_entity_context")
        get_details = mock_mcp._tools.get("codebase_get_entity_details")
        
        # Step 1: Find the authentication function
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(return_value=[db.entities[4]])  # authenticateUser
            mock_service.return_value = instance
            
            find_result = await find_entity(
                repo_id=repo_id,
                name="authenticateUser",
            )
            
            assert find_result["success"] is True
            entity_id = find_result["entities"][0]["id"]
        
        # Step 2: Get entity details
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_by_id = AsyncMock(return_value=db.get_by_id(entity_id))
            mock_service.return_value = instance
            
            details_result = await get_details(entity_id=entity_id)
            assert details_result["success"] is True
            assert "entity" in details_result
        
        # Step 3: Explore context (what this function uses)
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.get_entity_relationships = AsyncMock(return_value=db.get_relationships(entity_id, "both"))
            mock_service.return_value = instance
            
            context_result = await get_context(entity_id=entity_id)
            assert context_result["success"] is True
            assert "relationships" in context_result
    
    @pytest.mark.asyncio
    async def test_explore_file_workflow(self, mock_mcp, mock_db, mock_context):
        """Test exploring all entities in a file."""
        db, repo_id = mock_db
        register_code_entity_tools(mock_mcp)
        
        list_entities = mock_mcp._tools.get("codebase_list_entities_in_file")
        get_details = mock_mcp._tools.get("codebase_get_entity_details")
        
        # Step 1: List all entities in the auth file
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.list_entities_in_file = AsyncMock(return_value=[
                e for e in db.entities
                if e["file_path"] == "src/auth/UserAuthentication.ts"
            ])
            mock_service.return_value = instance
            
            list_result = await list_entities(
                repo_id=repo_id,
                file_path="src/auth/UserAuthentication.ts",
            )
            
            assert list_result["success"] is True
            assert list_result["count"] == 2
            
            # Step 2: Get details for each entity
            for entity_summary in list_result["entities"]:
                full_entity = db.get_by_id(entity_summary["id"])
                
                with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service2:
                    instance2 = MagicMock()
                    instance2.get_entity_by_id = AsyncMock(return_value=full_entity)
                    mock_service2.return_value = instance2
                    
                    details_result = await get_details(entity_id=entity_summary["id"])
                    assert details_result["success"] is True


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in all tools."""
    
    @pytest.mark.asyncio
    async def test_service_exception_handling(self, mock_mcp, mock_context):
        """Test that service exceptions are handled gracefully."""
        register_code_entity_tools(mock_mcp)
        
        find_entity = mock_mcp._tools.get("codebase_find_entity")
        
        with patch("src.mcp_server.features.code_entities.tools.CodeEntityService") as mock_service:
            instance = MagicMock()
            instance.find_entity_by_name = AsyncMock(side_effect=Exception("Database connection failed"))
            mock_service.return_value = instance
            
            result = await find_entity(
                repo_id="any-repo",
                name="test",
            )
            
            assert result["success"] is False
            assert "error" in result
            assert "Database connection failed" in result["error"]
