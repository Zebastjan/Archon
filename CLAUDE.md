# CLAUDE.md

Archon: AI agent framework built on Pydantic AI with Postgres/Supabase backends.

## Project Philosophy (Beta)

- **Fix forward** — Remove deprecated code immediately, no backwards compatibility
- **Fail fast and loud** — Service startup, auth, and data validation errors should crash
- **Complete but log** — Batch processing should finish the queue, report failures per item
- **Never store corrupted data** — Skip failed items entirely rather than storing nulls/bad embeddings

## Critical Constraints

**NEVER:**
- Store zero embeddings, null foreign keys, or malformed JSON
- Return None to indicate failure — raise with details instead
- Accept silent data corruption in critical services

**ALWAYS:**
- Use `uv` for Python dependency management
- Route DB operations through `db_connector.py` (Postgres/Supabase wrapper)
- Test on both X11 and Wayland when changing window management (if applicable)

## Architecture References

- Core patterns: `@PRPs/ai_docs/ARCHITECTURE.md`
- Data fetching: `@PRPs/ai_docs/DATA_FETCHING_ARCHITECTURE.md`
- Service pattern: `python/src/server/api_routes/` → `services/` → Database
