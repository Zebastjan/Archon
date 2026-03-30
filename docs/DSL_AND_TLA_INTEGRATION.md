# DSL and TLA+ Integration Design

## Overview

This document outlines the approach for:
1. **Nim DSL tracking** - Capturing domain-specific language patterns in Nim macros/templates
2. **TLA+ integration** - Linking formal specifications to implementations
3. **Validation tracking** - Flagging when implementations drift from specs

## Nim DSL Support (Option A → B)

### Current State (Option A)

Nim support already captures rich metadata:
- `is_template`, `is_macro`, `is_iterator` flags
- `pragmas` list (e.g., `{.gcsafe.}`, `{.async.}`)
- `generic_params`
- `operator_kind` classification

### Enhanced Metadata Schema

```python
# In CodeEntity.metadata for Nim entities
{
    # Existing fields
    "is_template": True,
    "is_macro": False,
    "pragmas": ["gcsafe", "inline"],
    
    # New DSL tagging fields
    "dsl_tags": ["async", "validation", "serialization"],
    "dsl_flavor": "async_http",  # Detected pattern
    "dsl_complexity": "high",    # Based on nesting depth
    "macro_invocations": [
        {"name": "routes", "count": 5},
        {"name": "db", "count": 12}
    ],
    
    # Cross-reference info
    "implements_spec": "TLA_MutexSafety",  # Link to TLA+ spec
    "spec_validated": True,
    "last_validation_commit": "a1b2c3d4"
}
```

### DSL Detection Heuristics

Based on pragmas, naming patterns, and macro usage:

```python
DSL_PATTERNS = {
    "async": {
        "pragmas": ["async", "asyncdispatch"],
        "keywords": ["await", "future"],
        "macro_patterns": [r"^async", r"^await"]
    },
    "validation": {
        "pragmas": ["valid", "validate"],
        "keywords": ["validate", "check", "assert"],
        "macro_patterns": [r"^validate", r"^check"]
    },
    "serialization": {
        "pragmas": ["json", "marshal"],
        "keywords": ["toJson", "fromJson", "marshal"],
        "macro_patterns": [r"^json", r"^marshal"]
    },
    "orm_dsl": {
        "pragmas": ["db", "table", "column"],
        "keywords": ["select", "insert", "update", "delete"],
        "macro_patterns": [r"^db", r"^table", r"^column"]
    }
}
```

### Database Schema (for Option B evolution)

```sql
-- DSL pattern tracking
CREATE TABLE archon_dsl_patterns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_name text NOT NULL,
    language text NOT NULL,
    detection_rules jsonb NOT NULL,  -- Heuristics for detecting this DSL
    created_at timestamptz DEFAULT now()
);

-- Entity-to-DSL relationship
CREATE TABLE archon_entity_dsl_tags (
    entity_id uuid REFERENCES archon_code_entities(id) ON DELETE CASCADE,
    pattern_id uuid REFERENCES archon_dsl_patterns(id) ON DELETE CASCADE,
    confidence_score float,  -- 0.0 to 1.0
    detected_by text,        -- 'heuristic', 'manual', 'ai'
    PRIMARY KEY (entity_id, pattern_id)
);

-- DSL macro usage statistics
CREATE TABLE archon_dsl_usage (
    id uuid PRIMARY DEFAULT gen_random_uuid(),
    repo_id uuid REFERENCES archon_code_repos(id),
    macro_name text NOT NULL,
    file_path text NOT NULL,
    usage_count int DEFAULT 1,
    last_seen_at timestamptz DEFAULT now(),
    UNIQUE (repo_id, macro_name, file_path)
);
```

## TLA+ Integration

### TLA+ Entity Types

From `tla_support.py`:

- `specification_module` - Root MODULE
- `operator` - Regular operators
- `temporal_property` - []<> and WF/SF operators
- `invariant` - Safety properties
- `state_variable` - VARIABLE declarations
- `constant` - CONSTANT declarations
- `theorem` - THEOREM statements
- `axiom` - AXIOM statements
- `pluscal_algorithm` - PlusCal algorithms

### TLA+ → Implementation Linking

#### Schema

```sql
-- TLA+ specification entities (extends archon_code_entities)
-- Already captured in code_entities with language='tla+'

-- Link TLA+ specs to implementations
CREATE TABLE archon_spec_impl_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_entity_id uuid REFERENCES archon_code_entities(id),
    impl_entity_id uuid REFERENCES archon_code_entities(id),
    link_type text NOT NULL,  -- 'implements', 'validates', 'references'
    confidence float,         -- AI or heuristic confidence
    validated_at timestamptz,
    validation_status text,   -- 'valid', 'invalid', 'unknown', 'stale'
    last_checked_commit text,
    created_at timestamptz DEFAULT now()
);

-- Validation history
CREATE TABLE archon_validation_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_impl_link_id uuid REFERENCES archon_spec_impl_links(id),
    checked_at timestamptz DEFAULT now(),
    commit_sha text,
    status text,  -- 'valid', 'invalid', 'error'
    details jsonb
);
```

#### Linking Strategies

1. **Naming Convention Matching**:
   ```
   TLA+ Operator: MutexInvariant
   Nim Proc:      checkMutexInvariant
   ```

2. **Pragma Annotation** (manual/opt-in):
   ```nim
   proc acquireLock() {.implements: "TLA_MutexInvariant".}
   ```

3. **Semantic Similarity** (AI-assisted):
   - Compare TLA+ operator docstrings to Nim proc implementations
   - Use embeddings to find likely matches

4. **File Proximity**:
   - Spec file: `specs/MutexSafety.tla`
   - Impl file: `src/mutex.nim`
   - Link entities in related files

### Validation Tracking

#### What to Track

1. **Spec Changes**:
   - When TLA+ invariant changes
   - Flag related implementations as `validation_stale`

2. **Implementation Changes**:
   - When implementation changes
   - Flag as needing revalidation

3. **Validation Results**:
   - Manual validation (developer marks as validated)
   - Automated validation (TLC model checker results)
   - Heuristic validation (AI assessment)

#### Status Flags

```python
VALIDATION_STATUS = {
    "valid": "Implementation validated against spec",
    "invalid": "Implementation violates spec",
    "stale": "Spec or impl changed since last validation",
    "unknown": "No validation performed",
    "partial": "Partial validation (some cases checked)",
    "error": "Validation could not be performed"
}
```

#### Automation Levels

**Level 0: Manual** (current)
- Developer manually marks implementations as validated
- Manual review of spec drift

**Level 1: Heuristic** (Option A)
- Track when spec or impl changes
- Flag potential drift based on git history
- Simple naming convention matching

**Level 2: AI-Assisted** (Option B potential)
- Use local LLM (Liquid FM 8B) to:
  - Compare TLA+ operator to implementation
  - Assess semantic similarity
  - Suggest validation focus areas

**Level 3: Formal** (future)
- Integrate with TLC model checker
- Automatic trace generation
- Model-based testing

### Implementation Plan

#### Phase 1: Foundation (This PR)
1. ✅ TLA+ language support (tree-sitter grammar)
2. ✅ TLA+ entity extraction (operators, invariants, variables)
3. ✅ Basic metadata linking (naming conventions)
4. ✅ Schema for spec_impl_links table

#### Phase 2: Heuristic Validation
1. Detect spec/impl changes via git hooks
2. Auto-flag entities as `stale` on changes
3. Naming convention matching (MutexInvariant → checkMutexInvariant)
4. Dashboard showing validation status

#### Phase 3: AI-Assisted
1. Local LLM integration (Liquid FM 8B)
2. Semantic similarity matching
3. Validation suggestion generation
4. Confidence scoring

#### Phase 4: Formal Integration (long-term)
1. TLC model checker integration
2. Automated trace generation
3. Model-based test generation
4. Continuous validation pipeline

## Usage Examples

### Query: Find unvalidated implementations

```sql
SELECT 
    impl.name as impl_name,
    impl.file_path,
    spec.name as spec_name,
    link.validation_status
FROM archon_code_entities impl
JOIN archon_spec_impl_links link ON impl.id = link.impl_entity_id
JOIN archon_code_entities spec ON link.spec_entity_id = spec.id
WHERE link.validation_status IN ('stale', 'unknown', 'invalid')
ORDER BY link.last_checked_commit NULLS FIRST;
```

### Query: Find DSL usage patterns

```sql
SELECT 
    dsl.pattern_name,
    COUNT(*) as entity_count,
    AVG(edt.confidence_score) as avg_confidence
FROM archon_dsl_patterns dsl
JOIN archon_entity_dsl_tags edt ON dsl.id = edt.pattern_id
GROUP BY dsl.pattern_name
ORDER BY entity_count DESC;
```

### API: Get TLA+ validation status

```bash
GET /api/code/tla-validation?repo_id=xxx&status=stale

Response:
{
  "spec_impl_pairs": [
    {
      "spec": {
        "name": "MutexInvariant",
        "file": "specs/Mutex.tla",
        "line": 42
      },
      "implementation": {
        "name": "acquireLock",
        "file": "src/mutex.nim",
        "line": 15
      },
      "status": "stale",
      "last_validated": "2024-03-20T10:00:00Z",
      "reason": "Implementation changed in commit a1b2c3d"
    }
  ]
}
```

## Integration with Existing Systems

### Git Hooks

Extend `.git/hooks/post-commit` to:
1. Check if TLA+ specs changed
2. Flag related implementations as `stale`
3. Check if DSL-heavy files changed
4. Update DSL usage statistics

### MCP Tools

New MCP tools:
- `get_tla_validation_status` - Check spec/impl validation
- `find_unvalidated_implementations` - Find code needing validation
- `get_dsl_usage` - Analyze DSL patterns in codebase
- `suggest_tla_links` - AI-suggested spec-to-impl links

### Health Monitoring

Add checks:
- Unvalidated implementations count
- Spec drift detection
- DSL pattern coverage
- TLA+ file parsing errors

## Success Metrics

1. **TLA+ Coverage**: % of critical algorithms with TLA+ specs
2. **Validation Rate**: % of implementations validated against specs
3. **Drift Detection**: Time to detect spec/impl divergence
4. **DSL Adoption**: Usage patterns of internal DSLs
5. **False Positive Rate**: Incorrect staleness flags
