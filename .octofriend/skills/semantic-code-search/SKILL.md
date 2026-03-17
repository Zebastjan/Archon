# Semantic Code Search Skill

Find code by describing what it does, rather than knowing its name.

## When to Use

Use this skill when:
- You know what a function does but not what it's called
- Looking for "the code that handles X"
- Finding implementation patterns
- Exploring code by concept/behavior
- Searching for similar implementations

## When NOT to Use

Do NOT use when:
- You know the exact function name (use codebase_find_entity)
- You need source code details (use function-deep-dive after finding)
- Looking for text patterns (use grep/shell tools)

## Tool Selection

**Primary**: `codebase_search_by_semantics`
- Uses vector embeddings to find semantically similar code
- Natural language queries work best
- Returns ranked results with similarity scores

## Query Construction

**Effective queries** are:
- **Short**: 2-5 keywords
- **Specific**: Focus on behavior, not implementation
- **Natural**: Describe what the code does

**Good queries**:
- "user authentication"
- "database connection pool"
- "HTTP request retry"
- "password hashing"
- "config file parsing"

**Bad queries**:
- "function that gets user from database and checks password and creates session"
- "def authenticate user password hash"

## Workflow

### Step 1: Semantic Search

```
codebase_search_by_semantics(
    repo_id,
    query="<behavior description>",
    entity_type="function",  # Optional: filter to functions
    top_k=10
)
```

### Step 2: Review Results

Present the ranked results:

```markdown
# Semantic Search Results: "[query]"

Found [N] matching entities:

## Top Matches

### 1. [entity_name] (Similarity: [X]%)
**Location**: [file_path]:[line_start]-[line_end]
**Signature**: [signature]
**Type**: [entity_type]

### 2. [entity_name] (Similarity: [X]%)
...
```

### Step 3: Deep Dive (Optional)

If user wants details on a specific result:

```
function-deep-dive on selected entity
```

## Result Interpretation

| Similarity Score | Interpretation |
|------------------|----------------|
| 90-100% | Very high match - likely correct |
| 80-89% | High match - probably relevant |
| 70-79% | Moderate match - review carefully |
| 60-69% | Weak match - may be unrelated |
| <60% | Low confidence - expand search or refine query |

## Batching Rules

**This skill uses a single call** for the primary search.

Optional follow-up for deep dive adds 1-2 more calls.

## Example Invocation

User: "Find the code that handles JWT token validation"

Claude: [calls codebase_search_by_semantics(repo_id, query="JWT token validation", top_k=10)]

Claude: "# Semantic Search Results: "JWT token validation"

Found 5 matching entities:

## Top Matches

### 1. verify_jwt_token (Similarity: 94%)
**Location**: auth/tokens.py:45-78
**Signature**: `def verify_jwt_token(token: str, secret: str) -> dict`
**Type**: function

### 2. decode_auth_token (Similarity: 89%)
**Location**: auth/utils.py:123-156
**Signature**: `def decode_auth_token(token: str) -> User`
**Type**: function

### 3. TokenValidator.validate (Similarity: 87%)
**Location**: auth/validator.py:23-67
**Signature**: `def validate(self, token: str) -> ValidationResult`
**Type**: method

### 4. parse_bearer_token (Similarity: 76%)
**Location**: middleware/auth.py:45-52
**Signature**: `def parse_bearer_token(header: str) -> str`
**Type**: function

### 5. refresh_access_token (Similarity: 71%)
**Location**: auth/tokens.py:89-112
**Signature**: `def refresh_access_token(refresh_token: str) -> str`
**Type**: function

The top 3 matches are highly relevant for JWT validation. Would you like me to deep dive into any of these?"
