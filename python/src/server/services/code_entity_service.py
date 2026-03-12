"""Code Entity Service

Manages extraction, storage, and retrieval of code entities and their relationships
from git repositories. Integrates Tree-sitter language parsing with the existing
git repository infrastructure.
"""

from datetime import UTC, datetime
from typing import Any

from supabase import Client

from ...config.logfire_config import get_logger
from .client_manager import get_supabase_client
from .languages import CodeEntity, CodeRelationship, get_language_for_file
from .languages.language_support import ParseError

logger = get_logger(__name__)


class CodeEntityService:
    """Service for managing code entities and relationships.
    
    Provides functionality to:
    - Extract entities from source files using Tree-sitter
    - Store entities with multi-dimensional embeddings
    - Store relationships (CALLS, INHERITS, IMPORTS, etc.)
    - Query entities by repository, type, language
    - Perform semantic search over code
    - Traverse relationships (find callers, callees, implementations)
    
    Example:
        >>> service = CodeEntityService()
        >>> await service.extract_and_store_entities(
        ...     repo_id="uuid",
        ...     commit_sha="abc123",
        ...     file_paths=["src/main.py", "src/utils.py"]
        ... )
    """
    
    def __init__(self, supabase_client: Client | None = None):
        """Initialize code entity service.
        
        Args:
            supabase_client: Optional Supabase client instance
        """
        self.supabase = supabase_client or get_supabase_client()
        self._logger = logger.bind(service="code_entity")
        self._logger.debug("code_entity_service_initialized")
    
    async def extract_and_store_entities(
        self,
        repo_id: str,
        commit_sha: str,
        file_paths: list[str],
        file_content_getter: callable,
    ) -> dict[str, Any]:
        """Extract and store code entities from multiple files.
        
        Extracts entities and relationships from source files and stores them
        in the database with multi-dimensional embeddings support.
        
        Args:
            repo_id: Repository UUID
            commit_sha: Git commit SHA
            file_paths: List of file paths to process
            file_content_getter: Async function to get file content (repo_id, commit_sha, file_path) -> str
            
        Returns:
            Dict with extraction results:
            - processed: Number of files processed
            - entities_created: Total entities created
            - relationships_created: Total relationships created
            - errors: List of errors encountered
            
        Example:
            >>> async def get_content(repo_id, commit_sha, file_path):
            ...     # Implementation that returns file content
            ...     return content
            >>> 
            >>> result = await service.extract_and_store_entities(
            ...     repo_id="uuid",
            ...     commit_sha="abc123",
            ...     file_paths=["src/main.py"],
            ...     file_content_getter=get_content
            ... )
        """
        results = {
            "processed": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": [],
        }
        
        for file_path in file_paths:
            try:
                # Check if language is supported
                lang_support = get_language_for_file(file_path)
                if not lang_support:
                    self._logger.debug(
                        "skipping_unsupported_file",
                        file=file_path,
                    )
                    continue
                
                # Get file content
                try:
                    content = await file_content_getter(repo_id, commit_sha, file_path)
                except Exception as e:
                    results["errors"].append({
                        "file": file_path,
                        "error": f"Failed to get content: {e}",
                    })
                    continue
                
                if not content:
                    continue
                
                # Extract entities
                try:
                    entities, relationships = lang_support.extract_entities_and_relationships(
                        content, file_path
                    )
                except ParseError as e:
                    results["errors"].append({
                        "file": file_path,
                        "error": f"Parse error: {e}",
                    })
                    continue
                
                # Store entities (and get their IDs for relationship linking)
                entity_id_map = {}
                for entity in entities:
                    entity_record = await self._store_entity(
                        repo_id=repo_id,
                        commit_sha=commit_sha,
                        file_path=file_path,
                        language=lang_support.language_id,
                        entity=entity,
                    )
                    if entity_record:
                        entity_id_map[entity.name] = entity_record["id"]
                        results["entities_created"] += 1
                
                # Store relationships (resolving names to IDs)
                for relationship in relationships:
                    source_id = entity_id_map.get(relationship.source_name)
                    target_id = entity_id_map.get(relationship.target_name)
                    
                    if source_id and target_id:
                        await self._store_relationship(
                            source_id=source_id,
                            target_id=target_id,
                            relationship_type=relationship.relationship_type,
                            metadata=relationship.metadata,
                        )
                        results["relationships_created"] += 1
                    else:
                        # Relationship references external entity (not in current file)
                        # Could store as "unresolved" or look up in database
                        self._logger.debug(
                            "unresolved_relationship",
                            source=relationship.source_name,
                            target=relationship.target_name,
                            file=file_path,
                        )
                
                results["processed"] += 1
                
            except Exception as e:
                self._logger.exception(
                    "extraction_failed",
                    file=file_path,
                    error=str(e),
                )
                results["errors"].append({
                    "file": file_path,
                    "error": str(e),
                })
        
        self._logger.info(
            "extraction_complete",
            repo_id=repo_id,
            commit_sha=commit_sha,
            **results,
        )
        
        return results
    
    async def _store_entity(
        self,
        repo_id: str,
        commit_sha: str,
        file_path: str,
        language: str,
        entity: CodeEntity,
    ) -> dict[str, Any] | None:
        """Store a code entity in the database.
        
        Args:
            repo_id: Repository UUID
            commit_sha: Git commit SHA
            file_path: File path within repo
            language: Programming language
            entity: CodeEntity to store
            
        Returns:
            Created entity record with ID, or None if failed
        """
        try:
            data = {
                "repo_id": repo_id,
                "file_path": file_path,
                "line_start": entity.line_start,
                "line_end": entity.line_end,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "signature": entity.signature,
                "docstring": entity.docstring,
                "source_code": entity.source_code,
                "language": language,
                "commit_sha": commit_sha,
                "metadata": entity.metadata,
                # Embeddings will be added separately
                "embedding_model": None,
                "embedding_dimension": None,
            }
            
            response = self.supabase.table("archon_code_entities").insert(data).execute()
            
            if response.data:
                self._logger.debug(
                    "entity_stored",
                    entity_id=response.data[0]["id"],
                    name=entity.name,
                    type=entity.entity_type,
                )
                return response.data[0]
            else:
                self._logger.warning(
                    "entity_insert_failed",
                    name=entity.name,
                    file=file_path,
                )
                return None
                
        except Exception as e:
            self._logger.exception(
                "store_entity_failed",
                name=entity.name,
                file=file_path,
                error=str(e),
            )
            return None
    
    async def _store_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: dict,
    ) -> dict[str, Any] | None:
        """Store a relationship in the database.
        
        Args:
            source_id: Source entity UUID
            target_id: Target entity UUID
            relationship_type: Type of relationship (CALLS, INHERITS, etc.)
            metadata: Additional metadata
            
        Returns:
            Created relationship record, or None if failed
        """
        try:
            data = {
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relationship_type": relationship_type,
                "metadata": metadata,
            }
            
            response = self.supabase.table("archon_code_relationships").insert(data).execute()
            
            if response.data:
                self._logger.debug(
                    "relationship_stored",
                    relationship_id=response.data[0]["id"],
                    source=source_id,
                    target=target_id,
                    type=relationship_type,
                )
                return response.data[0]
            else:
                self._logger.warning(
                    "relationship_insert_failed",
                    source=source_id,
                    target=target_id,
                )
                return None
                
        except Exception as e:
            self._logger.exception(
                "store_relationship_failed",
                source=source_id,
                target=target_id,
                error=str(e),
            )
            return None
    
    async def generate_embeddings(
        self,
        repo_id: str,
        commit_sha: str,
        embedding_model: str = "text-embedding-3-small",
        embedding_dimension: int = 1536,
    ) -> dict[str, Any]:
        """Generate embeddings for code entities.
        
        Fetches entities without embeddings and generates them using
        the specified embedding model. Updates the appropriate column
        based on embedding_dimension.
        
        Args:
            repo_id: Repository UUID
            commit_sha: Git commit SHA (to only embed current commit)
            embedding_model: Model name to use
            embedding_dimension: Dimension (384, 768, 1024, 1536, 3072)
            
        Returns:
            Dict with embedding generation results
            
        Note:
            This should be called after extract_and_store_entities.
            Uses batch processing for efficiency.
        """
        # This is a placeholder - actual implementation would integrate
        # with the existing embedding service
        self._logger.warning(
            "generate_embeddings_not_implemented",
            repo_id=repo_id,
            model=embedding_model,
        )
        
        return {
            "processed": 0,
            "model": embedding_model,
            "dimension": embedding_dimension,
        }
    
    async def find_entity_by_name(
        self,
        repo_id: str,
        name: str,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find entities by name in a repository.
        
        Args:
            repo_id: Repository UUID
            name: Entity name (can be partial match)
            entity_type: Optional filter by entity type
            
        Returns:
            List of matching entity records
        """
        try:
            query = self.supabase.table("archon_code_entities").select("*").eq("repo_id", repo_id)
            
            # Use ILIKE for case-insensitive partial matching
            query = query.ilike("name", f"%{name}%")
            
            if entity_type:
                query = query.eq("entity_type", entity_type)
            
            response = query.execute()
            
            return response.data or []
            
        except Exception as e:
            self._logger.exception(
                "find_entity_failed",
                repo_id=repo_id,
                name=name,
                error=str(e),
            )
            return []
    
    async def get_entity_by_id(
        self,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """Get a single entity by its ID.
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            Entity record or None if not found
        """
        try:
            response = self.supabase.table("archon_code_entities").select("*").eq("id", entity_id).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            self._logger.exception(
                "get_entity_by_id_failed",
                entity_id=entity_id,
                error=str(e),
            )
            return None
    
    async def get_entity_relationships(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get relationships for an entity.
        
        Uses the database function get_entity_relationships.
        
        Args:
            entity_id: Entity UUID
            relationship_types: Optional filter by types
            direction: 'incoming', 'outgoing', or 'both'
            
        Returns:
            List of relationship records with related entity info
        """
        try:
            response = self.supabase.rpc(
                "get_entity_relationships",
                {
                    "entity_id": entity_id,
                    "relationship_types": relationship_types,
                    "direction": direction,
                }
            ).execute()
            
            return response.data or []
            
        except Exception as e:
            self._logger.exception(
                "get_relationships_failed",
                entity_id=entity_id,
                error=str(e),
            )
            return []
    
    async def search_entities(
        self,
        query_embedding: list[float],
        embedding_dimension: int = 1536,
        match_count: int = 10,
        repo_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search entities by semantic similarity.
        
        Uses the database function match_archon_code_entities_multi.
        
        Args:
            query_embedding: Query vector
            embedding_dimension: Dimension of the embedding
            match_count: Maximum results to return
            repo_filter: Optional repository UUID filter
            
        Returns:
            List of matching entities with similarity scores
        """
        try:
            response = self.supabase.rpc(
                "match_archon_code_entities_multi",
                {
                    "query_embedding": query_embedding,
                    "embedding_dimension": embedding_dimension,
                    "match_count": match_count,
                    "filter": {},
                    "repo_filter": repo_filter,
                }
            ).execute()
            
            return response.data or []
            
        except Exception as e:
            self._logger.exception(
                "search_entities_failed",
                dimension=embedding_dimension,
                error=str(e),
            )
            return []
