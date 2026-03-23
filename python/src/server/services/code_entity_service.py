"""Code Entity Service

Manages extraction, storage, and retrieval of code entities and their relationships
from git repositories. Integrates Tree-sitter language parsing with PostgreSQL.
"""

from typing import Any

import logging
from .database.db_connector import get_database_connector, initialize_database
from .languages import CodeEntity, CodeRelationship, get_language_for_file
from .languages.language_support import ParseError

logger = logging.getLogger(__name__)


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

    def __init__(self):
        """Initialize code entity service."""
        self._logger = logger
        self._db = None
        self._logger.debug("code_entity_service_initialized")

    async def _get_db(self):
        """Get or initialize database connection."""
        if self._db is None:
            await initialize_database()
            self._db = get_database_connector()
            await self._db.initialize()
        return self._db

    async def extract_and_store_entities(
        self,
        repo_id: str,
        commit_sha: str,
        file_paths: list[str],
        file_content_getter: callable,
        branch_name: str | None = None,
        parent_commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """Extract and store code entities from multiple files."""
        results = {
            "processed": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": [],
        }

        db = await self._get_db()

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
                    results["errors"].append(
                        {
                            "file": file_path,
                            "error": f"Failed to get content: {e}",
                        }
                    )
                    continue

                if not content:
                    continue

                # Extract entities
                try:
                    entities, relationships = lang_support.extract_entities_and_relationships(content, file_path)
                except ParseError as e:
                    results["errors"].append(
                        {
                            "file": file_path,
                            "error": f"Parse error: {e}",
                        }
                    )
                    continue

                # Store entities (and get their IDs for relationship linking)
                entity_id_map = {}
                for entity in entities:
                    entity_record = await self._store_entity(
                        db=db,
                        repo_id=repo_id,
                        commit_sha=commit_sha,
                        file_path=file_path,
                        language=lang_support.language_id,
                        entity=entity,
                        branch_name=branch_name,
                        parent_commit_sha=parent_commit_sha,
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
                            db=db,
                            source_id=source_id,
                            target_id=target_id,
                            relationship_type=relationship.relationship_type,
                            metadata=relationship.metadata,
                        )
                        results["relationships_created"] += 1
                    else:
                        # Relationship references external entity (not in current file)
                        self._logger.debug(
                            f"unresolved_relationship source={relationship.source_name} target={relationship.target_name} file={file_path}"
                        )

                results["processed"] += 1

            except Exception as e:
                self._logger.exception(f"extraction_failed file={file_path} error={e}")
                results["errors"].append(
                    {
                        "file": file_path,
                        "error": str(e),
                    }
                )

        self._logger.info(
            f"extraction_complete repo_id={repo_id} processed={results['processed']} entities={results['entities_created']} relationships={results['relationships_created']}"
        )
        return results

    async def _store_entity(
        self,
        db,
        repo_id: str,
        commit_sha: str,
        file_path: str,
        language: str,
        entity: CodeEntity,
        branch_name: str | None = None,
        parent_commit_sha: str | None = None,
    ) -> dict[str, Any] | None:
        """Store a code entity in the database."""
        try:
            import hashlib

            entity_identity = hashlib.md5(f"{repo_id}{file_path}{entity.name}{entity.entity_type}".encode()).hexdigest()

            query = """
                INSERT INTO archon_code_entities (
                    repo_id, file_path, line_start, line_end, entity_type,
                    name, signature, docstring, source_code, language, commit_sha,
                    embedding_model, embedding_dimension, entity_identity,
                    branch_name, parent_commit_sha
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id, repo_id, file_path, line_start, line_end, entity_type,
                          name, signature, docstring, source_code, language, commit_sha,
                          branch_name, parent_commit_sha
            """

            record = await db.fetchrow(
                query,
                repo_id,
                file_path,
                entity.line_start,
                entity.line_end,
                entity.entity_type,
                entity.name,
                entity.signature,
                entity.docstring,
                entity.source_code,
                language,
                commit_sha,
                None,  # embedding_model
                None,  # embedding_dimension
                entity_identity,
                branch_name,
                parent_commit_sha,
            )

            if record:
                entity_id = record["id"]
                self._logger.debug(f"entity_stored entity_id={entity_id} name={entity.name} type={entity.entity_type}")
                return dict(record)
            else:
                self._logger.warning(f"entity_insert_failed name={entity.name} file={file_path}")
                return None

        except Exception as e:
            self._logger.exception(f"store_entity_failed name={entity.name} file={file_path} error={e}")
            return None

    async def _store_relationship(
        self,
        db,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: dict,
    ) -> dict[str, Any] | None:
        """Store a relationship in the database."""
        try:
            query = """
                INSERT INTO archon_code_relationships 
                (source_entity_id, target_entity_id, relationship_type, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """

            import json

            record = await db.fetchrow(query, source_id, target_id, relationship_type, json.dumps(metadata))

            if record:
                self._logger.debug(
                    f"relationship_stored relationship_id={record['id']} source={source_id} target={target_id} type={relationship_type}"
                )
                return dict(record)
            else:
                self._logger.warning(f"relationship_insert_failed source={source_id} target={target_id}")
                return None

        except Exception as e:
            self._logger.exception(f"store_relationship_failed source={source_id} target={target_id} error={e}")
            return None

    async def store_entity_with_embedding(
        self,
        entity: CodeEntity,
        repo_id: str,
        commit_sha: str,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> str | None:
        """Store a code entity with optional embedding.

        Args:
            entity: The code entity to store
            repo_id: Repository ID
            commit_sha: Git commit SHA
            embedding: Optional embedding vector
            embedding_model: Name of the embedding model
            embedding_dimension: Dimension of the embedding

        Returns:
            Entity ID if stored successfully, None otherwise
        """
        try:
            db = await self._get_db()

            # Determine which embedding column to use
            embedding_column = None
            if embedding and embedding_dimension:
                if embedding_dimension == 384:
                    embedding_column = "embedding_384"
                elif embedding_dimension == 768:
                    embedding_column = "embedding_768"
                elif embedding_dimension == 1024:
                    embedding_column = "embedding_1024"
                elif embedding_dimension == 1536:
                    embedding_column = "embedding_1536"
                elif embedding_dimension == 3072:
                    embedding_column = "embedding_3072"

            # Build query dynamically based on whether we have an embedding
            if embedding_column:
                query = f"""
                    INSERT INTO archon_code_entities (
                        repo_id, file_path, line_start, line_end, entity_type,
                        name, signature, docstring, source_code, language, commit_sha,
                        {embedding_column}, embedding_model, embedding_dimension, entity_identity
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::vector, $13, $14, md5($1::text || $2 || $6 || $5))
                    RETURNING id
                """
                record = await db.fetchrow(
                    query,
                    repo_id,
                    entity.file_path,
                    entity.line_start,
                    entity.line_end,
                    entity.entity_type,
                    entity.name,
                    entity.signature,
                    entity.docstring,
                    entity.source_code,
                    entity.language,
                    commit_sha,
                    embedding,
                    embedding_model,
                    embedding_dimension,
                )
            else:
                query = """
                    INSERT INTO archon_code_entities (
                        repo_id, file_path, line_start, line_end, entity_type,
                        name, signature, docstring, source_code, language, commit_sha, entity_identity
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, md5($1::text || $2 || $6 || $5))
                    RETURNING id
                """
                record = await db.fetchrow(
                    query,
                    repo_id,
                    entity.file_path,
                    entity.line_start,
                    entity.line_end,
                    entity.entity_type,
                    entity.name,
                    entity.signature,
                    entity.docstring,
                    entity.source_code,
                    entity.language,
                    commit_sha,
                )

            if record:
                entity_id = record["id"]
                self._logger.debug(f"entity_stored entity_id={entity_id} name={entity.name}")
                return entity_id
            return None

        except Exception as e:
            self._logger.exception(f"store_entity_failed name={entity.name} error={e}")
            return None

    async def generate_embeddings(
        self,
        repo_id: str,
        commit_sha: str,
        embedding_model: str = "text-embedding-3-small",
        embedding_dimension: int = 1536,
    ) -> dict[str, Any]:
        """Generate embeddings for code entities.

        This is a placeholder - actual embedding generation should use
        an embedding service like Ollama or OpenAI.
        """
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
            db = await self._get_db()

            query = """
                SELECT * FROM archon_code_entities 
                WHERE repo_id = $1 
                AND name ILIKE $2
            """
            params = [repo_id, f"%{name}%"]

            if entity_type:
                query += " AND entity_type = $3"
                params.append(entity_type)

            query += " ORDER BY name"

            records = await db.fetch(query, *params)
            return [dict(r) for r in records]

        except Exception as e:
            self._logger.exception(f"find_entity_failed repo_id={repo_id} name={name} error={e}")
            return []

    async def get_entity_by_id(
        self,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """Get a single entity by its ID."""
        try:
            db = await self._get_db()

            query = "SELECT * FROM archon_code_entities WHERE id = $1"
            record = await db.fetchrow(query, entity_id)

            return dict(record) if record else None

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
            db = await self._get_db()
            results = []

            # Outgoing relationships
            if direction in ("outgoing", "both"):
                query = """
                    SELECT 
                        cr.id as relationship_id,
                        cr.target_entity_id as related_entity_id,
                        cr.relationship_type,
                        ce.name as entity_name,
                        ce.entity_type,
                        ce.file_path,
                        cr.metadata
                    FROM archon_code_relationships cr
                    JOIN archon_code_entities ce ON ce.id = cr.target_entity_id
                    WHERE cr.source_entity_id = $1
                """
                params = [entity_id]

                if relationship_types:
                    placeholders = [f"${i + 2}" for i in range(len(relationship_types))]
                    query += f" AND cr.relationship_type IN ({', '.join(placeholders)})"
                    params.extend(relationship_types)

                records = await db.fetch(query, *params)
                results.extend([dict(r) for r in records])

            # Incoming relationships
            if direction in ("incoming", "both"):
                query = """
                    SELECT 
                        cr.id as relationship_id,
                        cr.source_entity_id as related_entity_id,
                        cr.relationship_type,
                        ce.name as entity_name,
                        ce.entity_type,
                        ce.file_path,
                        cr.metadata
                    FROM archon_code_relationships cr
                    JOIN archon_code_entities ce ON ce.id = cr.source_entity_id
                    WHERE cr.target_entity_id = $1
                """
                params = [entity_id]

                if relationship_types:
                    placeholders = [f"${i + 2}" for i in range(len(relationship_types))]
                    query += f" AND cr.relationship_type IN ({', '.join(placeholders)})"
                    params.extend(relationship_types)

                records = await db.fetch(query, *params)
                results.extend([dict(r) for r in records])

            return results

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
        """Search entities by semantic similarity using pgvector."""
        try:
            db = await self._get_db()

            # Determine which embedding column to use
            embedding_column = {
                384: "embedding_384",
                768: "embedding_768",
                1024: "embedding_1024",
                1536: "embedding_1536",
                3072: "embedding_3072",
            }.get(embedding_dimension, "embedding_1536")

            # Convert embedding list to PostgreSQL vector literal string
            embedding_str = '[' + ','.join(str(float(x)) for x in query_embedding) + ']'

            query = f"""
                SELECT
                    id, repo_id, file_path, entity_type, name,
                    signature, docstring, source_code, language, commit_sha,
                    1 - ({embedding_column} <=> $1::vector) AS similarity
                FROM archon_code_entities
                WHERE {embedding_column} IS NOT NULL
                AND ($2::uuid IS NULL OR repo_id = $2)
                ORDER BY {embedding_column} <=> $1::vector
                LIMIT $3
            """

            records = await db.fetch(query, embedding_str, repo_filter, match_count)

            return [dict(r) for r in records]

        except Exception as e:
            self._logger.exception(f"search_entities_failed dimension={embedding_dimension} error={e}")
            return []

    async def list_entities_in_file(
        self,
        repo_id: str,
        file_path: str,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all code entities in a specific file.

        Args:
            repo_id: Repository UUID
            file_path: Path to the file within the repository
            entity_type: Optional filter by entity type

        Returns:
            List of entities in the file
        """
        try:
            db = await self._get_db()

            query = """
                SELECT * FROM archon_code_entities 
                WHERE repo_id = $1 
                AND file_path = $2
            """
            params = [repo_id, file_path]

            if entity_type:
                query += " AND entity_type = $3"
                params.append(entity_type)

            query += " ORDER BY line_start"

            records = await db.fetch(query, *params)
            return [dict(r) for r in records]

        except Exception as e:
            self._logger.exception(f"list_entities_in_file_failed repo_id={repo_id} file={file_path} error={e}")
            return []

    async def get_repository_stats(self, repo_id: str) -> dict[str, Any]:
        """Get statistics for a repository."""
        try:
            db = await self._get_db()

            # Count by type
            type_counts = await db.fetch(
                """
                SELECT entity_type, COUNT(*) as count
                FROM archon_code_entities
                WHERE repo_id = $1
                GROUP BY entity_type
                """,
                repo_id,
            )

            # Count by language
            lang_counts = await db.fetch(
                """
                SELECT language, COUNT(*) as count
                FROM archon_code_entities
                WHERE repo_id = $1
                GROUP BY language
                """,
                repo_id,
            )

            # Total entities
            total_count = await db.fetchval(
                """
                SELECT COUNT(*) FROM archon_code_entities
                WHERE repo_id = $1
                """,
                repo_id,
            )

            # Relationship count
            rel_count = await db.fetchval(
                """
                SELECT COUNT(*) FROM archon_code_relationships r
                JOIN archon_code_entities e ON e.id = r.source_entity_id
                WHERE e.repo_id = $1
                """,
                repo_id,
            )

            # File count (unique files with entities)
            file_count = await db.fetchval(
                """
                SELECT COUNT(DISTINCT file_path) FROM archon_code_entities
                WHERE repo_id = $1
                """,
                repo_id,
            )

            return {
                "repo_id": repo_id,
                "total_entities": total_count,
                "total_files": file_count,
                "by_type": {r["entity_type"]: r["count"] for r in type_counts},
                "by_language": {r["language"]: r["count"] for r in lang_counts},
                "total_relationships": rel_count,
            }

        except Exception as e:
            self._logger.exception(f"get_repository_stats_failed repo_id={repo_id} error={e}")
            return {}
