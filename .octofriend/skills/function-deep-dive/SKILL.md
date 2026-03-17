# Function Deep Dive Skill

Comprehensive analysis of a single function or method including source code, complexity metrics, and relationship mapping.

## When to Use

Use this skill when:
- Understanding how a specific function works
- Debugging an issue in a function
- Planning changes to a function
- Reviewing a function's implementation
- Assessing a function's complexity and risk

## When NOT to Use

Do NOT use when:
- Exploring a codebase broadly (use codebase-discovery)
- Auditing the whole codebase (use quick-health-check)
- Finding functions by behavior (use codebase_search_by_semantics)
- You only need the function signature (use codebase_find_entity only)

## Workflow

### Step 1: Locate Function

First, identify the function:

```
codebase_find_entity(repo_id, name="<function_name>", entity_type="function")
```

**If multiple results**: Ask user to clarify which one, or present options with file paths.

**If single result**: Proceed to Step 2.

### Step 2: Deep Analysis Batch

Run these calls in parallel:

```
codebase_get_entity_details(entity_id, include_source=True)
codebase_get_entity_context(entity_id, include_callers=True, include_callees=True, max_depth=1)
code_audit_analyze_entity(entity_id)
```

These are independent and can be batched.

### Step 3: Analysis

From the results:

1. **Entity Details**: Source code, signature, docstring, location
2. **Entity Context**: Callers (who calls this) and callees (what this calls)
3. **Complexity Metrics**: Lines of code, cyclomatic complexity, TODOs

### Step 4: Presentation

Structure your response:

```markdown
# Function Analysis: [function_name]

**Location**: [file_path]:[line_start]-[line_end]
**Language**: [language]
**Signature**: [signature]

## Complexity Metrics
- Lines of Code: [X]
- Cyclomatic Complexity: [Y]
- TODO/FIXME Count: [Z]
- [Other metrics from code_audit_analyze_entity]

## Documentation
[Docstring if present, or note if missing]

## Source Code
```[language]
[source_code from entity_details]
```

## Call Graph

### Called By ([count] callers)
[List callers from entity_context]
- [caller_name] in [file]:[line]

### Calls ([count] callees)
[List callees from entity_context]
- [callee_name] in [file]:[line]

## Analysis
[Your analysis of the function]
- Purpose and behavior
- Key logic patterns
- Potential issues or concerns
- Relationship to surrounding code
```

## Batching Rules

**MUST batch Step 2 calls** - they are independent:
- `codebase_get_entity_details` + `codebase_get_entity_context` + `code_audit_analyze_entity`

**Tool call limit**:
- Step 1 (locate): 1 call
- Step 2 (deep dive): 1 batch call (3 parallel calls)
- Total: 2 calls

## Depth Configuration

For `codebase_get_entity_context`, choose depth based on use case:

| Use Case | max_depth | Rationale |
|----------|-----------|-----------|
| Quick understanding | 1 | See immediate callers/callees |
| Impact analysis | 2 | Understand broader impact |
| Deep refactoring | 3 | Full dependency graph |

Default: max_depth=1

## Error Handling

| Error | Action |
|-------|--------|
| Function not found | Try partial match or ask user |
| Multiple matches | Present options with file paths |
| No source available | Note "Source code not indexed" |
| No callers/callees | Report "No relationships found" |

## Example Invocation

User: "Explain the register_code_entity_tools function"

Claude: [calls codebase_find_entity(repo_id="abc-123", name="register_code_entity_tools")]
→ Returns 1 entity with id "ent-456"

Claude: [batches codebase_get_entity_details, codebase_get_entity_context, code_audit_analyze_entity]

Claude: "# Function Analysis: register_code_entity_tools

**Location**: python/src/mcp_server/features/code_entities/tools.py:25-87
**Language**: python
**Signature**: `def register_code_entity_tools(mcp: FastMCP) -> None`

## Complexity Metrics
- Lines of Code: 62
- Cyclomatic Complexity: 2
- TODO/FIXME Count: 0

## Documentation
Registers code entity MCP tools.

Args:
    mcp: FastMCP server instance

## Source Code
```python
def register_code_entity_tools(mcp: FastMCP) -> None:
    logger.info("registering_code_entity_tools")
    
    @mcp.tool()
    async def codebase_find_entity(...):
        ...
    
    # ... 5 more tool registrations
```

## Call Graph

### Called By (2 callers)
- `register_modules` in mcp_server.py:180
- `test_register_tools` in test_code_entities.py:45

### Calls (1 callee)
- `CodeEntityService` (constructor) in tools.py:47

## Analysis
This is a registration function that sets up 6 MCP tools for code entity operations. It's well-structured with low complexity. Each inner function follows a consistent pattern: log entry, call service, format response. The function is only called during MCP server initialization."
