"""Audit API endpoints for Archon

Handles:
- Semgrep-based code audits (replaces legacy regex-based rules)
- Finding triage and review workflow
- Triage memory for pattern learning
- False negative tracking (meta-audit)
- Rule quality metrics

Key Principles:
- Server endpoints only - no direct MCP coupling
- HTTP interface for inter-service communication
- Async processing where appropriate
- Comprehensive Logfire monitoring
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.logfire_config import get_logger, logfire

logger = get_logger(__name__)

# Import service (lazy import to avoid circular deps)
# from ..services.semgrep_service import get_semgrep_service

router = APIRouter(prefix="/api", tags=["audit"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RunAuditRequest(BaseModel):
    repo_id: str
    rulesets: list[str] | None = None  # Defaults to p/ci for PR gate
    exclude_patterns: list[str] | None = None
    include_db_audit: bool | None = None  # Enable DB security audit layer


class TriageFindingRequest(BaseModel):
    decision: str  # confirmed_issue, intentional, false_positive, wont_fix
    rationale: str
    reviewer: str = "user"


class RecordFalseNegativeRequest(BaseModel):
    bug_type: str
    bug_description: str
    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str = ""
    discovered_by: str = "manual"
    root_cause: str = ""


class TriageMemoryResponse(BaseModel):
    suggested_decision: str | None
    confidence: float | None
    similar_cases: int
    rationale: str | None


# =============================================================================
# HEALTH & STATUS
# =============================================================================

@router.get("/audit/health")
async def audit_health():
    """Health check for audit service."""
    try:
        # Check if semgrep is available
        import subprocess
        result = subprocess.run(
            ["semgrep", "--version"],
            capture_output=True,
            timeout=5
        )
        semgrep_available = result.returncode == 0
        semgrep_version = result.stdout.decode().strip() if semgrep_available else None
        
        logfire.debug(f"Audit health check | semgrep_available={semgrep_available}")
        
        return {
            "status": "healthy" if semgrep_available else "degraded",
            "service": "audit",
            "semgrep_available": semgrep_available,
            "semgrep_version": semgrep_version,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except FileNotFoundError:
        return {
            "status": "unhealthy",
            "service": "audit",
            "semgrep_available": False,
            "error": "Semgrep not installed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logfire.error(f"Audit health check failed | error={str(e)}")
        return {
            "status": "error",
            "service": "audit",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# =============================================================================
# AUDIT EXECUTION
# =============================================================================

@router.post("/audit/run")
async def run_audit(request: RunAuditRequest):
    """
    Run a comprehensive audit on a repository.
    
    This runs multiple audit layers:
    - Semgrep security/static analysis
    - Coverage checks (pytest-cov or c8)
    - Test companion checks
    - Methodology-specific rules
    - Nim audit (if Nim files present)
    - Semantic drift check (stub)
    
    Default ruleset is 'p/ci' for high-confidence findings suitable for PR gates.
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        from ..services.coverage_service import get_coverage_service
        from ..services.companion_check_service import get_companion_check_service
        from ..services.nim_audit_service import get_nim_audit_service
        from ..services.database import get_database_connector
        import json
        
        logfire.info(
            f"Starting multi-layer audit | repo_id={request.repo_id}"
        )
        
        # Get repo info using Postgres directly
        db = get_database_connector()
        repo_result = await db.fetchrow(
            "SELECT id, local_path, name, methodology FROM archon_code_repos WHERE id = $1",
            request.repo_id
        )
        
        if not repo_result:
            raise HTTPException(status_code=404, detail=f"Repository {request.repo_id} not found")
        
        repo_path = repo_result["local_path"]
        repo_name = repo_result["name"]
        
        # Parse methodology from JSON string if needed
        methodology_raw = repo_result.get("methodology")
        if methodology_raw and isinstance(methodology_raw, str):
            try:
                methodology = json.loads(methodology_raw)
            except json.JSONDecodeError:
                methodology = {}
        elif methodology_raw and isinstance(methodology_raw, dict):
            methodology = methodology_raw
        else:
            methodology = {}
        
        results = {
            "repo_id": request.repo_id,
            "repo_name": repo_name,
            "layers": [],
        }
        
        # 1. Semgrep Security Audit
        logfire.info(f"Running Semgrep audit on {repo_name}")
        semgrep_service = get_semgrep_service()
        semgrep_findings = semgrep_service.run_audit(
            repo_path=repo_path,
            repo_id=UUID(request.repo_id),
            rulesets=request.rulesets or ["p/ci"],
            exclude_patterns=request.exclude_patterns,
        )
        semgrep_saved = semgrep_service.save_findings(
            findings=semgrep_findings,
            repo_id=UUID(request.repo_id),
        )
        results["layers"].append({
            "source": "semgrep",
            "findings_count": len(semgrep_findings),
            "saved_count": semgrep_saved,
        })
        
        # 2. Coverage Audit (if enabled in methodology)
        if methodology.get("enforce", []).count("coverage") > 0:
            logfire.info(f"Running coverage audit on {repo_name}")
            coverage_service = get_coverage_service()
            coverage_result = coverage_service.run_coverage_audit(
                repo_path=repo_path,
                repo_id=UUID(request.repo_id),
            )
            results["layers"].append({
                "source": coverage_result.get("source", "coverage"),
                "findings_count": coverage_result.get("findings_count", 0),
                "saved_count": coverage_result.get("saved_count", 0),
            })
        
        # 3. Test Companion Check (if enabled in methodology)
        if methodology.get("enforce", []).count("test_companions") > 0:
            logfire.info(f"Running companion check on {repo_name}")
            companion_service = get_companion_check_service()
            companion_result = companion_service.run_companion_check(
                repo_path=repo_path,
                repo_id=UUID(request.repo_id),
            )
            results["layers"].append({
                "source": "companion-check",
                "findings_count": companion_result.get("findings_count", 0),
                "saved_count": companion_result.get("saved_count", 0),
            })
        
        # 4. Nim Audit (3 layers)
        nim_files = list(Path(repo_path).rglob("*.nim"))
        nim_enabled = methodology.get("nim_enabled", False) or len(nim_files) > 0

        if nim_enabled and nim_files:
            logfire.info(f"Running 3-layer Nim audit on {repo_name} ({len(nim_files)} files)")

            # Layer 4a: Nimalyzer pragma checks
            try:
                from ..services.nimalyzer_service import get_nimalyzer_service
                nimalyzer_service = get_nimalyzer_service()
                nimalyzer_findings = nimalyzer_service.run_pragma_check(
                    repo_path=repo_path,
                    repo_id=UUID(request.repo_id),
                )
                nimalyzer_saved = nimalyzer_service.save_findings(
                    findings=nimalyzer_findings,
                    repo_id=UUID(request.repo_id),
                )
                results["layers"].append({
                    "source": "nimalyzer",
                    "findings_count": len(nimalyzer_findings),
                    "saved_count": nimalyzer_saved,
                })
            except Exception as e:
                logger.warning(f"Nimalyzer layer failed: {e}")
                results["layers"].append({
                    "source": "nimalyzer",
                    "findings_count": 0,
                    "error": str(e),
                })

            # Layer 4b: Semgrep generic mode Nim rules
            try:
                semgrep_nim_findings = semgrep_service.run_audit(
                    repo_path=repo_path,
                    repo_id=UUID(request.repo_id),
                    rulesets=["python/src/server/semgrep_rules/nim"],
                    exclude_patterns=["tests/", "test/", "*.test.nim"],
                )
                semgrep_nim_saved = semgrep_service.save_findings(
                    findings=semgrep_nim_findings,
                    repo_id=UUID(request.repo_id),
                )
                results["layers"].append({
                    "source": "semgrep-nim-generic",
                    "findings_count": len(semgrep_nim_findings),
                    "saved_count": semgrep_nim_saved,
                })
            except Exception as e:
                logger.warning(f"Semgrep Nim layer failed: {e}")
                results["layers"].append({
                    "source": "semgrep-nim-generic",
                    "findings_count": 0,
                    "error": str(e),
                })

            # Layer 4c: Tree-sitter Nim audit (existing service)
            try:
                nim_service = get_nim_audit_service()
                nim_result = nim_service.run_nim_audit(
                    repo_path=repo_path,
                    repo_id=UUID(request.repo_id),
                )
                results["layers"].append({
                    "source": "nim-tree-sitter-audit",
                    "findings_count": nim_result.get("findings_count", 0),
                    "saved_count": nim_result.get("saved_count", 0),
                })
            except Exception as e:
                logger.warning(f"Tree-sitter Nim layer failed: {e}")
                results["layers"].append({
                    "source": "nim-tree-sitter-audit",
                    "findings_count": 0,
                    "error": str(e),
                })
        
        # 5. DB Security Audit (if enabled or Python/JS files present)
        db_audit_enabled = request.include_db_audit if request.include_db_audit is not None else methodology.get("db_audit_enabled", True)
        python_files = list(Path(repo_path).rglob("*.py"))
        js_files = list(Path(repo_path).rglob("*.js")) + list(Path(repo_path).rglob("*.ts"))
        
        if db_audit_enabled and (python_files or js_files):
            logfire.info(f"Running DB security audit on {repo_name}")
            
            db_rulesets = [
                "p/python",  # Python security patterns
                "p/javascript",  # JS security patterns
                "p/typescript",  # TS security patterns
                "python/src/server/semgrep_rules/db",  # Custom DB rules
            ]
            
            # Exclude test files for DB audit
            db_exclude_patterns = [
                "tests/", "test/", "*_test.py", "*.test.ts", "*.test.js",
                "fixtures/", "mocks/", "conftest.py",
            ]
            
            try:
                db_findings = semgrep_service.run_audit(
                    repo_path=repo_path,
                    repo_id=UUID(request.repo_id),
                    rulesets=db_rulesets,
                    exclude_patterns=db_exclude_patterns,
                )
                
                # Filter to DB-related findings only
                db_related_patterns = [
                    "sql", "injection", "query", "execute", "cursor",
                    "psycopg", "asyncpg", "postgres", "sqlite", "mysql",
                ]
                db_findings_filtered = [
                    f for f in db_findings 
                    if any(p in f.check_id.lower() for p in db_related_patterns)
                    or any(p in f.message.lower() for p in db_related_patterns)
                ]
                
                db_saved = semgrep_service.save_findings(
                    findings=db_findings_filtered,
                    repo_id=UUID(request.repo_id),
                )
                results["layers"].append({
                    "source": "db-security-audit",
                    "findings_count": len(db_findings_filtered),
                    "saved_count": db_saved,
                    "rules_used": db_rulesets,
                })
            except Exception as e:
                logger.warning(f"DB audit layer failed: {e}")
                results["layers"].append({
                    "source": "db-security-audit",
                    "findings_count": 0,
                    "error": str(e),
                })
        
        # 6. Semantic Drift Check (stub)
        logfire.debug(f"Running semantic drift check (stub) on {repo_name}")
        drift_result = await semgrep_service.check_semantic_drift(
            repo_id=request.repo_id,
            entity_id="*",  # Check all entities
        )
        results["layers"].append({
            "source": "semantic-drift",
            "findings_count": len(drift_result),
            "status": "stub",
        })
        
        # Calculate totals
        total_findings = sum(layer["findings_count"] for layer in results["layers"])
        total_saved = sum(layer.get("saved_count", 0) for layer in results["layers"])
        
        logfire.info(
            f"Audit complete | repo_id={request.repo_id} | total_findings={total_findings}"
        )
        
        return {
            "status": "success",
            "repo_id": request.repo_id,
            "repo_name": repo_name,
            "methodology": methodology.get("primary", "unknown"),
            "total_findings": total_findings,
            "total_saved": total_saved,
            "layers": results["layers"],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Audit run failed | repo_id={request.repo_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/findings")
async def list_findings(
    repo_id: str | None = None,
    status: str = "open",
    severity: str | None = None,
    check_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List Semgrep findings for review.
    
    Query Parameters:
        repo_id: Filter by repository
        status: open, triaged, or suppressed
        severity: ERROR, WARNING, or INFO
        check_id: Filter by specific rule
        limit: Maximum results (default 50)
        offset: Pagination offset
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        logfire.debug(
            f"Listing findings | repo_id={repo_id} | status={status} | severity={severity}"
        )
        
        service = get_semgrep_service()
        
        # Build query parameters
        findings = service.get_findings_for_review(
            repo_id=UUID(repo_id) if repo_id else None,
            status=status,
            limit=limit,
            severity=severity,
        )
        
        # Filter by check_id if specified
        if check_id:
            findings = [f for f in findings if f.get("semgrep_check_id") == check_id]
        
        # Apply offset
        findings = findings[offset:offset + limit]
        
        logfire.debug(f"Found {len(findings)} findings matching criteria")
        
        return {
            "findings": findings,
            "count": len(findings),
            "filters": {
                "repo_id": repo_id,
                "status": status,
                "severity": severity,
                "check_id": check_id,
            },
        }
        
    except Exception as e:
        logfire.error(f"Failed to list findings | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/findings/{finding_id}")
async def get_finding(finding_id: str):
    """Get detailed information about a specific finding."""
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        service = get_semgrep_service()
        finding = service.get_finding_by_id(UUID(finding_id))
        
        if not finding:
            raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
        
        # Get triage suggestion if available
        suggestion = await service.suggest_triage_decision(UUID(finding_id))
        
        return {
            "finding": finding,
            "triage_suggestion": suggestion,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get finding | finding_id={finding_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


# =============================================================================
# TRIAGE WORKFLOW
# =============================================================================

@router.post("/audit/findings/{finding_id}/triage")
async def triage_finding(finding_id: str, request: TriageFindingRequest):
    """
    Triage a finding and store decision in triage memory.
    
    Decisions:
        confirmed_issue: Real bug that needs fixing
        intentional: Valid code by design (e.g., architectural pattern)
        false_positive: Tool misfired, not actually a problem
        wont_fix: Valid issue but accepted as tech debt
    
    The decision and rationale are stored in triage memory to inform
    future triage suggestions via semantic similarity.
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        if request.decision not in ("confirmed_issue", "intentional", "false_positive", "wont_fix"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision: {request.decision}. Must be one of: confirmed_issue, intentional, false_positive, wont_fix"
            )
        
        logfire.info(
            f"Triaging finding | finding_id={finding_id} | decision={request.decision} | reviewer={request.reviewer}"
        )
        
        service = get_semgrep_service()
        
        success = await service.triage_finding(
            finding_id=UUID(finding_id),
            decision=request.decision,
            rationale=request.rationale,
            reviewer=request.reviewer,
            store_in_memory=True,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to triage finding")
        
        return {
            "status": "success",
            "finding_id": finding_id,
            "decision": request.decision,
            "message": f"Finding triaged as {request.decision}",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to triage finding | finding_id={finding_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/findings/{finding_id}/suggest")
async def suggest_triage(finding_id: str):
    """
    Get a triage suggestion based on similar past decisions.
    
    Uses semantic similarity of code patterns to find previous triage
    decisions and suggests the most common decision.
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        service = get_semgrep_service()
        suggestion = await service.suggest_triage_decision(UUID(finding_id))
        
        if not suggestion:
            return {
                "suggested_decision": None,
                "confidence": None,
                "similar_cases": 0,
                "rationale": "No similar patterns found in triage memory",
            }
        
        return suggestion
        
    except Exception as e:
        logfire.error(f"Failed to suggest triage | finding_id={finding_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


# =============================================================================
# FALSE NEGATIVE TRACKING (META-AUDIT)
# =============================================================================

@router.post("/audit/false-negatives")
async def record_false_negative(repo_id: str, request: RecordFalseNegativeRequest):
    """
    Record a bug that slipped past the audit.
    
    This is the core of the meta-audit system - tracking what we missed
    so we can improve our detection rules over time.
    
    Example:
        Bug Type: race_condition
        Description: Concurrent access to shared cache without synchronization
        Root Cause: No rule for shared mutable state detection
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        logfire.info(
            f"Recording false negative | repo_id={repo_id} | bug_type={request.bug_type}"
        )
        
        service = get_semgrep_service()
        
        fn_id = service.record_false_negative(
            repo_id=UUID(repo_id),
            bug_type=request.bug_type,
            bug_description=request.bug_description,
            file_path=request.file_path,
            line_start=request.line_start,
            line_end=request.line_end,
            code_snippet=request.code_snippet,
            discovered_by=request.discovered_by,
            root_cause=request.root_cause,
        )
        
        if not fn_id:
            raise HTTPException(status_code=500, detail="Failed to record false negative")
        
        return {
            "status": "success",
            "false_negative_id": str(fn_id),
            "message": "False negative recorded for meta-audit analysis",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to record false negative | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/false-negatives")
async def list_false_negatives(
    repo_id: str | None = None,
    bug_type: str | None = None,
    limit: int = 50,
):
    """List recorded false negatives (bugs that slipped past audits)."""
    try:
        from ..services.database import get_database_connector
        
        db = get_database_connector()
        
        query = "SELECT * FROM archon_audit_false_negatives"
        params = []
        
        if repo_id:
            query += " WHERE repo_id = $1"
            params.append(repo_id)
        if bug_type:
            if params:
                query += " AND bug_type = $2"
            else:
                query += " WHERE bug_type = $1"
            params.append(bug_type)
        
        query += " ORDER BY discovered_at DESC"
        if params:
            query += f" LIMIT ${len(params) + 1}"
        else:
            query += " LIMIT $1"
        params.append(limit)
        
        result = await db.fetch(query, *params)
        
        return {
            "false_negatives": [dict(r) for r in result],
            "count": len(result),
        }
        
    except Exception as e:
        logfire.error(f"Failed to list false negatives | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/audit/false-negatives/{fn_id}/analyze")
async def analyze_false_negative(fn_id: str, repo_path: str):
    """
    Analyze if Semgrep would catch a false negative now.
    
    Re-runs Semgrep on the specific file to see if current rules
    would detect the bug. Updates the false negative record with results.
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        service = get_semgrep_service()
        
        result = service.analyze_false_negative(
            false_negative_id=UUID(fn_id),
            repo_path=repo_path,
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "false_negative_id": fn_id,
            "analysis": result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to analyze false negative | fn_id={fn_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


# =============================================================================
# RULE QUALITY METRICS
# =============================================================================

@router.get("/audit/rule-quality")
async def get_rule_quality(
    min_findings: int = 5,
    fp_threshold: float = 0.5,
):
    """
    Get quality metrics for all audit rules.
    
    Query Parameters:
        min_findings: Minimum findings to consider (default 5)
        fp_threshold: False positive threshold for flagging (default 0.5)
    
    Returns metrics including:
        - Total findings per rule
        - Precision (confirmed / total)
        - False positive rate
        - Recommendations (DISABLE, REVIEW, GOOD, MONITOR)
    """
    try:
        from ..services.semgrep_service import get_semgrep_service
        
        service = get_semgrep_service()
        
        # Get full quality report
        report = service.get_rule_quality_report()
        
        # Get rules that should be disabled
        rules_to_disable = service.get_rules_to_disable(
            fp_threshold=fp_threshold,
            min_findings=min_findings,
        )
        
        logfire.info(
            f"Rule quality report | rules_analyzed={len(report)} | rules_flagged={len(rules_to_disable)}"
        )
        
        return {
            "rules_analyzed": len(report),
            "rules_flagged": len(rules_to_disable),
            "rules_to_disable": rules_to_disable,
            "thresholds": {
                "min_findings": min_findings,
                "fp_threshold": fp_threshold,
            },
            "report": report,
        }
        
    except Exception as e:
        logfire.error(f"Failed to get rule quality | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/rule-quality/{check_id}")
async def get_rule_quality_detail(check_id: str):
    """Get detailed quality metrics for a specific rule."""
    try:
        from ..services.database import get_database_connector
        
        service = get_semgrep_service()
        
        # Get rule quality record using Postgres directly
        db = get_database_connector()
        result = await db.fetchrow(
            "SELECT * FROM archon_audit_rule_quality WHERE check_id = $1",
            check_id
        )
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Rule {check_id} not found in quality metrics")
        
        # Get sample findings for this rule
        sample_findings = service.get_findings_by_check_id(check_id, limit=5)
        
        return {
            "rule": dict(result),
            "sample_findings": sample_findings,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get rule quality detail | check_id={check_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


# =============================================================================
# AUDIT SUMMARY
# =============================================================================

@router.get("/audit/summary")
async def get_audit_summary(repo_id: str | None = None):
    """Get summary statistics for audits."""
    try:
        from ..services.semgrep_service import get_semgrep_service
        from uuid import UUID
        
        service = get_semgrep_service()
        
        summary = service.get_audit_summary(
            repo_id=UUID(repo_id) if repo_id else None
        )
        
        return {
            "summary": summary,
            "repo_id": repo_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logfire.error(f"Failed to get audit summary | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/audit/triage-memory")
async def get_triage_memory_stats():
    """Get statistics about the triage memory system."""
    try:
        from ..services.database import get_database_connector
        
        db = get_database_connector()
        
        # Get counts by decision type using Postgres
        decisions_result = await db.fetch(
            "SELECT decision, COUNT(*) as count FROM archon_audit_triage_memory GROUP BY decision"
        )
        
        # Get total count
        total_result = await db.fetchval("SELECT COUNT(*) FROM archon_audit_triage_memory")
        
        # Get validated count
        validated_result = await db.fetchval(
            "SELECT COUNT(*) FROM archon_audit_triage_memory WHERE was_validated = true"
        )
        
        # Build by_decision dict
        by_decision = {
            "confirmed_issue": 0,
            "intentional": 0,
            "false_positive": 0,
            "wont_fix": 0,
        }
        for row in decisions_result:
            by_decision[row["decision"]] = row["count"]
        
        return {
            "total_memories": total_result or 0,
            "validated_memories": validated_result or 0,
            "by_decision": by_decision,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logfire.error(f"Failed to get triage memory stats | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
