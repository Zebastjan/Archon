"""Code Entity Service

Manages extraction, storage, and retrieval of code entities and their relationships
from git repositories. Integrates Tree-sitter language parsing with the existing
git repository infrastructure.
"""

from datetime import UTC, datetime
from typing import Any

from supabase import Client

from src.server.config.logfire_config import get_logger
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
    """
    
    def __init__(self, supabase_client: Client | None = None):
        """Initialize code entity service.
        
        Args:
            supabase_client: Optional Supabase client instance
        """
        self.supabase = supabase_client or get_supabase_client()
        self._logger = logger
        self._logger.debug("code_entity_service_initialized")
    
    async def extract_and_store_entities(
        self,
        repo_id: str,
        commit_sha: str,
        file_paths: list[str],
        file_content_getter: callable,
    ) -> dict[str, Any]:
        """Extract and store code entities from multiple files."""
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
                    self._logger.debug(f"skipping_unsupported_file file={file_path}")
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
                        self._logger.debug(f"unresolved_relationship source={relationship.source_name} target={relationship.target_name} file={file_path}")
                
                results["processed"] += 1
                
            except Exception as e:
                self._logger.exception(f"extraction_failed file={file_path} error={e}")
                results["errors"].append({
                    "file": file_path,
                    "error": str(e),
                })
        
        self._logger.info(f"extraction_complete repo_id={repo_id} processed={results['processed']} entities={results['entities_created']} relationships={results['relationships_created']}")
        
        return results
    
    async def _store_entity(
        self,
        repo_id: str,
        commit_sha: str,
        file_path: str,
        language: str,
        entity: CodeEntity,
    ) -> dict[str, Any] | None:
        """Store a code entity in the database."""
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
                # Embeddings will be added separately
                "embedding_model": None,
                "embedding_dimension": None,
            }
            
            response = self.supabase.table("archon_code_entities").insert(data).execute()
            
            if response.data:
                self._logger.debug(f"entity_stored entity_id={response.data[0]['id']} name={entity.name} type={entity.entity_type}")
                return response.data[0]
            else:
                self._logger.warning(f"entity_insert_failed name={entity.name} file={file_path}")
                return None
                
        except Exception as e:
            self._logger.exception(f"store_entity_failed name={entity.name} file={file_path} error={e}")
            return None
    
    async def _store_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: dict,
    ) -> dict[str, Any] | None:
        """Store a relationship in the database."""
        try:
            data = {
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relationship_type": relationship_type,
                "metadata": metadata,
            }
            
            response = self.supabase.table("archon_code_relationships").insert(data).execute()
            
            if response.data:
                self._logger.debug(f"relationship_stored relationship_id={response.data[0]['id']} source={source_id} target={target_id} type={relationship_type}")
                return response.data[0]
            else:
                self._logger.warning(f"relationship_insert_failed source={source_id} target={target_id}")
                return None
                
        except Exception as e:
            self._logger.exception(f"store_relationship_failed source={source_id} target={target_id} error={e}")
            return None
    
    async def generate_embeddings(
        self,
        repo_id: str,
        commit_sha: str,
        embedding_model: str = "text-embedding-3-small",
        embedding_dimension: int = 1536,
    ) -> dict[str, Any]:
        """Generate embeddings for code entities."""
        self._logger.warning(f"generate_embeddings_not_implemented repo_id={repo_id} model={embedding_model}")
        
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
        """Find entities by name in a repository."""
        try:
            query = self.supabase.table("archon_code_entities").select("*").eq("repo_id", repo_id)
            
            # Use ILIKE for case-insensitive partial matching
            query = query.ilike("name", f"%{name}%")
            
            if entity_type:
                query = query.eq("entity_type", entity_type)
            
            response = query.execute()
            
            return response.data or []
            
        except Exception as e:
            self._logger.exception(f"find_entity_failed repo_id={repo_id} name={name} error={e}")
            return []
    
    async def get_entity_by_id(
        self,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """Get a single entity by its ID."""
        try:
            response = self.supabase.table("archon_code_entities").select("*").eq("id", entity_id).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            self._logger.exception(f"get_entity_by_id_failed entity_id={entity_id} error={e}")
            return None
    
    async def get_entity_relationships(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get relationships for an entity."""
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
            self._logger.exception(f"get_relationships_failed entity_id={entity_id} error={e}")
            return []
    
    async def search_entities(
        self,
        query_embedding: list[float],
        embedding_dimension: int = 1536,
        match_count: int = 10,
        repo_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search entities by semantic similarity."""
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
            self._logger.exception(f"search_entities_failed dimension={embedding_dimension} error={e}")
            return []
