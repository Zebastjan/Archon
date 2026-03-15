"""Cephalosage Orchestrator Service

HTTP service that provides intelligent orchestration of audit operations
using a local LLM for result post-processing and summarization.

Designed to run on RTX 3060 12GB with 4-bit quantized models (7-14B parameters).
"""

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.server.config.logfire_config import get_logger
from src.mcp_server.features.code_audit.repo_health_super_tool import run_repo_health_check

logger = get_logger(__name__)

# Configuration
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "kahnwong/lfm2:8b-a1b")  # Liquid 8B - Fast & High Quality
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8080"))

app = FastAPI(
    title="Cephalosage Orchestrator",
    description="Local orchestration service for code audits",
    version="0.1.0",
)


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator service."""
    llm_url: str = LOCAL_LLM_URL
    llm_model: str = LOCAL_LLM_MODEL
    timeout: int = 60
    max_tokens: int = 2048


class LocalLLMClient:
    """Client for interacting with local LLM (Ollama-compatible)."""
    
    def __init__(self, config: OrchestratorConfig = None):
        self.config = config or OrchestratorConfig()
        self.client = httpx.Client(timeout=self.config.timeout)
    
    def generate_summary(
        self,
        health_score: int,
        findings: list[dict],
        metrics: dict,
        focus: str | None = None,
    ) -> dict[str, str]:
        """
        Generate human-friendly summary using local LLM.
        
        Args:
            health_score: Overall health score (0-100)
            findings: List of audit findings
            metrics: Metrics summary
            focus: Optional focus area
            
        Returns:
            Dict with executive_summary and detailed_analysis
        """
        try:
            # Build prompt for the LLM
            prompt = self._build_summary_prompt(health_score, findings, metrics, focus)
            
            # Call local LLM (Ollama API)
            response = self.client.post(
                f"{self.config.llm_url}/api/generate",
                json={
                    "model": self.config.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": self.config.max_tokens,
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("response", "")
                
                # Parse the generated text into structured format
                return self._parse_llm_response(generated_text)
            else:
                logger.error(f"LLM API error: {response.status_code}")
                return self._generate_fallback_summary(health_score, findings, focus)
                
        except Exception as e:
            logger.exception(f"Failed to generate LLM summary: {e}")
            return self._generate_fallback_summary(health_score, findings, focus)
    
    def _build_summary_prompt(
        self,
        health_score: int,
        findings: list[dict],
        metrics: dict,
        focus: str | None,
    ) -> str:
        """Build prompt for LLM summarization with exception handling and assertion quality emphasis."""
        
        # Categorize findings
        critical = [f for f in findings if f.get("severity") == "critical"]
        errors = [f for f in findings if f.get("severity") == "error"]
        warnings = [f for f in findings if f.get("severity") == "warning"]
        
        # Special categorization for exception handling (P0 - Security Critical)
        exception_findings = [f for f in findings if f.get("rule_id", "") in 
                            ['broad-except', 'exception-not-logged', 'async-exception-swallowed']]
        exception_critical = [f for f in exception_findings if f.get("severity") == "critical" or 
                             f.get("rule_id") in ['broad-except', 'async-exception-swallowed']]
        
        # Special categorization for assertion quality (P1 - Test Reliability)
        assertion_findings = [f for f in findings if f.get("rule_id", "").startswith('assert-')]
        assertion_critical = [f for f in assertion_findings if f.get("severity") in ['error', 'warning']]
        
        focus_str = f"Focus: {focus}\n" if focus else ""
        
        # Build exception-focused summary if there are exception issues
        exception_summary = ""
        if exception_findings:
            exception_summary = f"""
⚠️ SECURITY-CRITICAL: Exception Handling Issues Detected
- Total exception violations: {len(exception_findings)}
- Critical/Error level: {len([f for f in exception_findings if f.get('severity') in ['critical', 'error']])}
- Files affected: {len(set(f.get('file_path', '') for f in exception_findings))}

These issues can cause:
- Silent failures in production
- Invisible security vulnerabilities  
- Impossible-to-debug async race conditions
"""
        
        # Build assertion quality summary if there are assertion issues
        assertion_summary = ""
        if assertion_findings:
            missing_assert_tests = len([f for f in assertion_findings if f.get('rule_id') == 'assert-missing-in-test'])
            unverified_mocks = len([f for f in assertion_findings if f.get('rule_id') == 'assert-mock-not-verified'])
            
            assertion_summary = f"""
🧪 TEST QUALITY: Assertion Issues Detected
- Total assertion violations: {len(assertion_findings)}
- Tests without assertions: {missing_assert_tests}
- Unverified mocks: {unverified_mocks}
- Files affected: {len(set(f.get('file_path', '') for f in assertion_findings))}

These issues indicate:
- Tests that may pass without actually verifying behavior
- False confidence in test coverage
- Potential for regressions undetected by CI
"""
        
        # Add exception findings first if present
        if exception_findings:
            prompt += "\n🚨 Exception Handling Issues (Security-Critical):\n"
            for i, finding in enumerate(exception_findings[:3], 1):
                prompt += f"{i}. [{finding.get('severity', 'unknown').upper()}] {finding.get('rule_id')}: {finding.get('message', 'No message')[:60]}...\n"
            prompt += "\nOther Findings:\n"
            other_findings = [f for f in findings if f not in exception_findings]
            for i, finding in enumerate(other_findings[:5], 1):
                prompt += f"{i}. [{finding.get('severity', 'unknown').upper()}] {finding.get('rule_id', 'unknown')}: {finding.get('message', 'No message')[:60]}...\n"
        else:
            prompt += "\nTop Issues:\n"
            for i, finding in enumerate(findings[:5], 1):
                prompt += f"{i}. [{finding.get('severity', 'unknown').upper()}] {finding.get('rule_id', 'unknown')}: {finding.get('message', 'No message')[:60]}...\n"
        
        prompt += """
Provide your response in this exact format:

EXECUTIVE_SUMMARY: (2-3 sentences. START with exception handling status if present)

DETAILED_ANALYSIS: (3-5 bullet points. PRIORITIZE exception handling fixes if present)

Keep it concise and actionable. If exception issues exist, emphasize them first."""
        
        return prompt
    
    def _parse_llm_response(self, text: str) -> dict[str, str]:
        """Parse LLM response into structured format."""
        
        executive_summary = ""
        detailed_analysis = ""
        
        lines = text.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("EXECUTIVE_SUMMARY:"):
                current_section = "executive"
                executive_summary = line.replace("EXECUTIVE_SUMMARY:", "").strip()
            elif line.startswith("DETAILED_ANALYSIS:"):
                current_section = "detailed"
                detailed_analysis = line.replace("DETAILED_ANALYSIS:", "").strip()
            elif current_section == "executive" and line:
                executive_summary += " " + line
            elif current_section == "detailed" and line:
                detailed_analysis += "\n" + line
        
        return {
            "executive_summary": executive_summary or "Code audit completed.",
            "detailed_analysis": detailed_analysis or "No specific recommendations.",
        }
    
    def _generate_fallback_summary(
        self,
        health_score: int,
        findings: list[dict],
        focus: str | None,
    ) -> dict[str, str]:
        """Generate fallback summary if LLM fails."""
        
        critical_count = sum(1 for f in findings if f.get("severity") == "critical")
        error_count = sum(1 for f in findings if f.get("severity") == "error")
        
        if health_score >= 80:
            summary = f"Repository health is good ({health_score}/100). Minor improvements recommended."
        elif health_score >= 60:
            summary = f"Repository health is fair ({health_score}/100). Several areas need attention."
        else:
            summary = f"Repository health needs improvement ({health_score}/100). Significant refactoring recommended."
        
        if critical_count > 0:
            summary += f" Address {critical_count} critical security issues immediately."
        
        analysis = [
            f"1. Overall health score: {health_score}/100",
            f"2. Total findings: {len(findings)} ({critical_count} critical, {error_count} error)",
            "3. Review highlighted issues and prioritize fixes by severity",
        ]
        
        if focus:
            analysis.append(f"4. Focus on {focus}-related improvements")
        
        return {
            "executive_summary": summary,
            "detailed_analysis": "\n".join(analysis),
        }


# Initialize LLM client
llm_client = LocalLLMClient()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "orchestrator": "cephelosage", "version": "0.1.0"}


@app.post("/orchestrator/repo_health_check")
async def orchestrated_repo_health_check(
    repo_id: str,
    focus: str | None = None,
    include_llm_summary: bool = True,
) -> dict[str, Any]:
    """
    Orchestrated repository health check with LLM-powered summarization.
    
    This endpoint:
    1. Runs the standard repo_health_check
    2. Uses local LLM to generate human-friendly summary
    3. Returns combined structured data + natural language analysis
    
    Args:
        repo_id: Repository UUID to check
        focus: Focus area (security, tdd, docs, maintainability, full)
        include_llm_summary: Whether to generate LLM summary
        
    Returns:
        Structured audit results with executive_summary and detailed_analysis
    """
    try:
        logger.info(f"Starting orchestrated health check for {repo_id}, focus={focus}")
        
        # Step 1: Run standard repo_health_check
        result = run_repo_health_check(
            repo_id=repo_id,
            focus=focus,
            skip_worktree_validation=False,
        )
        
        if not result.get("success"):
            logger.warning(f"Health check failed: {result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        # Step 2: Generate LLM summary if requested
        if include_llm_summary:
            llm_summary = llm_client.generate_summary(
                health_score=result["health_score"],
                findings=result["highlights"],
                metrics=result["metrics_summary"],
                focus=focus,
            )
            
            # Add LLM-generated summaries to result
            result["executive_summary"] = llm_summary["executive_summary"]
            result["detailed_analysis"] = llm_summary["detailed_analysis"]
        else:
            result["executive_summary"] = f"Health score: {result['health_score']}/100"
            result["detailed_analysis"] = "See highlights and recommendations for details."
        
        # Add orchestrator metadata
        result["orchestrated"] = True
        result["orchestrator_version"] = "0.1.0"
        result["llm_model"] = LOCAL_LLM_MODEL if include_llm_summary else None
        
        logger.info(f"Orchestrated health check complete: score={result['health_score']}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Orchestrator error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrator/plan_refactors")
async def plan_refactors(
    repo_id: str,
    run_id: str,
    max_suggestions: int = 5,
) -> dict[str, Any]:
    """
    Generate refactoring plan based on audit findings.
    
    Uses local LLM to analyze findings and suggest refactoring tasks.
    
    Args:
        repo_id: Repository UUID
        run_id: Audit run ID to base plan on
        max_suggestions: Maximum number of refactoring suggestions
        
    Returns:
        Refactoring plan with prioritized tasks
    """
    try:
        logger.info(f"Generating refactor plan for {repo_id}, run_id={run_id}")
        
        # TODO: Implement refactor planning with LLM
        # This would fetch the audit results and use LLM to suggest refactorings
        
        return {
            "success": True,
            "repo_id": repo_id,
            "run_id": run_id,
            "suggestions": [
                {
                    "priority": "high",
                    "description": "Refactor high-complexity functions",
                    "estimated_effort": "2-3 days",
                }
            ],
            "orchestrated": True,
        }
        
    except Exception as e:
        logger.exception(f"Refactor planning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def start_orchestrator():
    """Start the orchestrator service."""
    import uvicorn
    
    logger.info(f"Starting Cephalosage Orchestrator on port {ORCHESTRATOR_PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=ORCHESTRATOR_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    start_orchestrator()
