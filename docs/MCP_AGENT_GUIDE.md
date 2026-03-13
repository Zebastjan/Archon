# MCP Agent Usage Guide for Archon Codebase Intelligence

## Quick Reference: When to Use Which Tool

| Situation | Tool | Example |
|-----------|------|---------|
| "Find function X" | `codebase_find_entity` | Find `extract_entities_and_relationships` |
| "What handles Y?" | `codebase_semantic_search` | "database connection pooling" |
| "How is X used?" | `codebase_find_callers` | Who calls `initialize_database`? |
| "What's in this file?" | `codebase_find_by_file` | What's in `code_entity_service.py`? |
| "Tell me about X" | `codebase_get_entity_context` | Full context for `CodeEntityService` |
| "How big is this repo?" | `codebase_repo_stats` | Archon-python stats |

## Repository IDs

- **archon-python**: `76abe5b8-693a-40e4-a3a3-c08289465d7d` (1478 entities)
- **archon-ui**: `59f97679-1483-4be6-822b-5798e6c29679` (1216 entities)

## Tool Details

### 1. codebase_find_entity
**When**: You know (approximately) the name of something.

**Examples**:
- "Find the function that extracts code entities"
- "Where is the database connector class?"
- "Show me all methods named 'initialize'"

**Usage**:
```json
{
  "repo_id": "76abe5b8-693a-40e4-a3a3-c08289465d7d",
  "query": "extract_entities",
  "entity_type": "method"  // optional: function, method, class, interface
}
```

**Returns**: List of matches with file paths and line numbers.

---

### 2. codebase_semantic_search
**When**: You know WHAT you want, but not the name.

**Examples**:
- "Find code that handles git commits"
- "Show me React components that manage state"
- "Database connection retry logic"

**Usage**:
```json
{
  "repo_id": "76abe5b8-693a-40e4-a3a3-c08289465d7d",
  "query": "handle failed database connections",
  "limit": 10
}
```

**Returns**: Ranked results with similarity scores (0-1).

---

### 3. codebase_get_entity_context
**When**: You found an entity and want the full picture.

**Use for**:
- Understanding what calls this function
- Seeing what this function calls
- Viewing source code and docstring
- Understanding inheritance

**Usage**:
```json
{
  "entity_id": "uuid-from-find-entity-result"
}
```

**Returns**: Full entity + relationships (callers, callees, inheritance).

---

### 4. codebase_find_callers
**When**: You want to know "who uses this?"

**Examples**:
- "Who calls the embedding service?"
- "What uses the database connector?"
- "Find all callers of `generate_embeddings`"

**Usage**:
```json
{
  "repo_id": "76abe5b8-693a-40e4-a3a3-c08289465d7d",
  "function_name": "generate_embeddings"
}
```

**Returns**: List of entities that call the specified function.

---

### 5. codebase_repo_stats
**When**: You need to understand codebase structure.

**Use for**:
- Getting an overview before diving in
- Understanding what languages are used
- Seeing entity type distribution

**Usage**:
```json
{
  "repo_id": "76abe5b8-693a-40e4-a3a3-c08289465d7d"
}
```

**Returns**: Counts by type and language.

---

## Agent Decision Tree

```
START: What do you need to know?
│
├─→ I know the EXACT or approximate name
│   └─→ USE: codebase_find_entity
│       └─→ Want more details?
│           └─→ USE: codebase_get_entity_context
│
├─→ I know the CONCEPT but not the name
│   └─→ USE: codebase_semantic_search
│       └─→ Found something interesting?
│           └─→ USE: codebase_get_entity_context
│
├─→ I want to know WHO USES something
│   └─→ USE: codebase_find_callers
│
├─→ I want to see what's in a FILE
│   └─→ USE: codebase_find_by_file
│
└─→ I want a HIGH-LEVEL overview
    └─→ USE: codebase_repo_stats
    └─→ USE: codebase_list_repos
```

## Common Workflows

### Workflow 1: Understanding a Feature
1. **semantic_search**: "handle git repository ingestion"
2. **find_entity**: Look for specific function names
3. **get_entity_context**: Deep dive into key functions
4. **find_callers**: Understand how it's used

### Workflow 2: Finding Impact
1. **find_entity**: Locate the function/class to change
2. **find_callers**: See all places that call it
3. **get_entity_context**: Understand the relationships

### Workflow 3: Exploring New Codebase
1. **repo_stats**: Get high-level view
2. **find_by_file**: Look at key files
3. **semantic_search**: Find relevant features
4. **get_entity_context**: Deep dive

## IDE-Specific Configuration

### Claude Code
Config at: `~/.claude-code/mcp-config.json`

### OpenCode
Config at: `~/.config/opencode/mcp-config.json`

### Windsurf
Config at: `~/.config/windsurf/mcp.json`

### OctoFriend
Config at: `~/.octofriend/mcp.json`

## Testing the Connection

```bash
# Check if MCP server is running
curl http://localhost:8051/health

# List available tools
curl http://localhost:8051/tools
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No results found" | Try semantic_search with different terms |
| "Entity not found" | Use find_entity with partial name |
| "Connection refused" | Check if archon-mcp is running (`docker ps`) |
| "Timeout" | Try more specific queries |

## Repository Prefixes

When agents ask about "our codebase", they're usually referring to:
- **Python backend**: `76abe5b8-693a-40e4-a3a3-c08289465d7d`
- **UI frontend**: `59f97679-1483-4be6-822b-5798e6c29679`

The agent should automatically determine which repo based on:
- File extension (.py vs .ts/.tsx)
- Path patterns (src/server vs archon-ui-main)
- Query context
