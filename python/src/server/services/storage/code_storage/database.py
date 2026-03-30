"""Database operations for code examples.

Handles storing code examples and their embeddings in the database.
"""

from typing import Any

from ....config.logfire_config import search_logger
from ...database.db_connector import get_database_connector

# Module-level singleton for database access
db_connector = get_database_connector()


async def add_code_examples_to_supabase(
    urls: list[str],
    chunk_numbers: list[int],
    code_examples: list[str],
    summaries: list[str] | None = None,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    """Add code examples to the database with their metadata.

    Args:
        urls: List of document URLs
        chunk_numbers: List of chunk numbers corresponding to each example
        code_examples: List of code example strings
        summaries: Optional list of code summaries
        languages: Optional list of programming languages

    Returns:
        Result dictionary with success status and details
    """
    if not urls or not chunk_numbers or not code_examples:
        return {"success": False, "error": "Missing required parameters", "inserted": 0}

    if len(urls) != len(chunk_numbers) or len(urls) != len(code_examples):
        return {"success": False, "error": "Mismatched array lengths", "inserted": 0}

    try:
        # Get database connection
        inserted = 0
        errors = []

        async with db_connector.acquire() as conn:
            for i, (url, chunk_num, code) in enumerate(zip(urls, chunk_numbers, code_examples)):
                try:
                    summary = summaries[i] if summaries and i < len(summaries) else None
                    language = languages[i] if languages and i < len(languages) else "text"

                    # Insert code example
                    await conn.execute(
                        """
                        INSERT INTO code_examples (
                            document_url, chunk_number, code_content,
                            summary, language, created_at
                        ) VALUES ($1, $2, $3, $4, $5, NOW())
                        ON CONFLICT (document_url, chunk_number) DO UPDATE SET
                            code_content = EXCLUDED.code_content,
                            summary = EXCLUDED.summary,
                            language = EXCLUDED.language,
                            updated_at = NOW()
                        """,
                        url,
                        chunk_num,
                        code,
                        summary,
                        language,
                    )
                    inserted += 1

                except Exception as e:
                    error_msg = f"Error inserting code example {i}: {str(e)}"
                    search_logger.warning(error_msg)
                    errors.append(error_msg)

        result = {
            "success": len(errors) == 0,
            "inserted": inserted,
            "total": len(code_examples),
            "errors": errors if errors else None,
        }

        search_logger.info(f"Added {inserted} code examples to database")
        return result

    except Exception as e:
        search_logger.error(f"Failed to add code examples: {e}")
        return {"success": False, "error": str(e), "inserted": 0}


async def get_code_examples_for_document(url: str) -> list[dict[str, Any]]:
    """Retrieve all code examples for a specific document.

    Args:
        url: Document URL

    Returns:
        List of code example records
    """
    try:
        async with db_connector.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code_content, summary, language, chunk_number, created_at
                FROM code_examples
                WHERE document_url = $1
                ORDER BY chunk_number
                """,
                url,
            )

            return [
                {
                    "code": row["code_content"],
                    "summary": row["summary"],
                    "language": row["language"],
                    "chunk_number": row["chunk_number"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    except Exception as e:
        search_logger.error(f"Failed to get code examples for {url}: {e}")
        return []


async def delete_code_examples_for_document(url: str) -> bool:
    """Delete all code examples for a specific document.

    Args:
        url: Document URL

    Returns:
        True if successful, False otherwise
    """
    try:
        async with db_connector.acquire() as conn:
            await conn.execute("DELETE FROM code_examples WHERE document_url = $1", url)
            return True

    except Exception as e:
        search_logger.error(f"Failed to delete code examples for {url}: {e}")
        return False
