# Leverage MCP Code Intelligence Tools

Guide agents to use MCP code intelligence tools instead of reverting to shell commands.

## Prompt

```
You have powerful code intelligence tools available. Use them instead of
shell commands for better results:

## Finding Code

Instead of: grep -r "function_name"
Use: `codebase_find_entity(name="function_name")`

Instead of: grep -r "authentication" --include="*.py"
Use: `codebase_search_by_semantics(query="user authentication")`

## Understanding Code

Instead of: cat file.py + manual analysis
Use: `codebase_get_entity_context(entity_id="...")`

This gives you:
- Full source code
- Docstrings and signatures
- Who calls this function
- What this function calls
- Inheritance relationships

## Finding Relationships

Instead of: grep -r "my_function()" 
Use: `codebase_find_callers(function_name="my_function")`

Instead of: Manual analysis of imports
Use: `codebase_get_entity_context(id)` includes callees

## Exploring Codebase

Instead of: find . -name "*.py" | head -20
Use: `codebase_repo_stats(repo_id="...")`

Instead of: cat file.py | head -50
Use: `codebase_list_entities_in_file(repo_id="...", file_path="...")`

## Historical Analysis

Instead of: git log -p --follow file.py
Use: `codebase_entity_evolution(repo_id="...", entity_name="...")`

Instead of: git show HEAD:path/to/file
Use: `codebase_search_at_commit(repo_id="...", commit_sha="...", query="...")`

## When to Use Shell

Only fall back to shell commands when:
1. MCP tools can't handle the query
2. You need to run tests or build commands
3. You need git status or branch information
4. You need to create commits

## Efficiency Tips

1. Start broad with semantic search
2. Narrow with exact entity lookup
3. Understand relationships with context
4. Only use shell as last resort

## Example Workflow

```
User: "Find where user authentication is handled"

Agent:
  1. semantic_search("user authentication") → finds AuthService class
  2. get_entity_context(AuthService) → sees login() method
  3. find_callers(login) → finds API routes using it
  4. Now I have full picture without touching shell
```
```

## Tool Reference

| Task | Tool |
|------|------|
| Find by name | `codebase_find_entity(name)` |
| Search by concept | `codebase_search_by_semantics(query)` |
| Get full context | `codebase_get_entity_context(id)` |
| Find callers | `codebase_find_callers(name)` |
| List in file | `codebase_list_entities_in_file(path)` |
| Repo overview | `codebase_repo_stats(repo_id)` |
| Historical code | `codebase_search_at_commit(sha, query)` |
| Track changes | `codebase_entity_evolution(name)` |
