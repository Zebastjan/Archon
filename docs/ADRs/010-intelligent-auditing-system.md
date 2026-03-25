# ADR-010: Intelligent Code Auditing System

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

A code auditing system already exists with:
- Base auditor (metrics calculation, rule execution)
- Findings tracking (open/resolved/false_positive status)
- LLM-powered summarization (orchestrated_repo_health_check)

This ADR formalizes the architecture and identifies gaps.

## Decision

Maintain and formalize the existing 3-layer architecture.

### Layer 1: Base Auditor

**Purpose:** Run static analysis and pattern detection on code.

**Components:**
- `CodeMetricsService` - calculates cyclomatic complexity, LOC, comment ratios
- `SemgrepService` - runs security/ruleset scans
- `AuditRules` - custom rules in database

**Existing Implementation:**
- `python/src/server/services/code_metrics_service.py`
- `python/src/server/services/semgrep_service.py`
- Tables: `archon_audit_rules`, `archon_audit_findings`

**Tools:**
- `code_audit_calculate_metrics(repo_id)` - compute metrics
- `code_audit_run(repo_id, ruleset)` - execute audit rules
- `db_security_audit(repo_id)` - SQL injection patterns

### Layer 2: Meta-Audit (LLM Review)

**Purpose:** LLM reviews raw findings to filter noise, deduplicate, prioritize.

**Existing Implementation:**
- `orchestrated_repo_health_check(repo_id, focus)` - LLM-enhanced summary
- Uses local Ollama model via orchestrator service

**Process:**
1. Run base audit → raw findings
2. Send findings to LLM with prompt: "Review these findings, filter false positives, prioritize real issues"
3. LLM returns curated list with confidence scores

### Layer 3: Feedback Loop

**Purpose:** Track dismissed findings → correlate with later bugs.

**Status:** NOT YET IMPLEMENTED - see ADR-011

### Audit Flow

```
Agent runs: repo_health_check(repo_id, focus="security")
                    ↓
        Layer 1: Base Auditor
        - Semgrep scans
        - Metrics calculation
        - Returns raw findings
                    ↓
        Layer 2: Meta-Audit (LLM)
        - Reviews findings
        - Filters noise
        - Returns curated list
                    ↓
        Returns: health_score, highlights, recommendations
```

### MCP Tools Summary

| Tool | Purpose |
|------|---------|
| `repo_health_check` | Full audit with scores |
| `orchestrated_repo_health_check` | LLM-enhanced (recommended) |
| `code_audit_calculate_metrics` | Metrics only |
| `code_audit_run` | Rules execution |
| `code_audit_get_findings` | Query findings |
| `code_audit_acknowledge_finding` | Mark finding status |
| `db_security_audit` | Security-focused |

### Database Schema (Existing)

```sql
archon_audit_rules (
    id, rule_id, name, description, category, severity, is_active
)

archon_audit_findings (
    id, rule_id, repo_id, severity, message, 
    file_path, line_start, status, created_at
)
```

## Consequences

### Positive
- Comprehensive audit system already in place
- Multi-layer: raw analysis + intelligent filtering
- LLM summarization for actionable results

### Negative
- Feedback loop not yet implemented (ADR-011)
- Some duplication between tools

## Related Decisions

- ADR-011: Audit Feedback Loop and Learning
- ADR-009: Commit-Automation Pipeline (includes audit stage)

## Implementation Checklist

- [x] Layer 1: Base auditor implemented
- [x] Layer 2: Meta-audit via orchestrator
- [ ] Layer 3: Feedback loop (ADR-011)
- [ ] Document tool usage in skills/
