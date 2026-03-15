#!/usr/bin/env python3
"""
Auto-triage audit findings using local LLM with confidence scoring and detailed analysis.
"""

import json
import logging
import sys
import time
from typing import Any, Dict, List
import psycopg2
from httpx import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoTriageEngine:
    """Engine for auto-triaging audit findings with confidence scoring."""
    
    def __init__(
        self,
        db_url: str = "postgresql://archon:archon_local_dev@localhost:5434/archon",
        llm_url: str = "http://localhost:11434",
        llm_model: str = "kahnwong/lfm2:8b-a1b",
    ):
        self.db_url = db_url
        self.llm_url = llm_url
        self.llm_model = llm_model
        self.db_conn = psycopg2.connect(db_url)
        self.client = Client(timeout=120.0)
    
    def _get_db(self):
        """Get database connection."""
        return self.db_conn
    
    def _query(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute query and return results."""
        with self._get_db().cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            return []
    
    def _execute(self, query: str, params: tuple = ()):
        """Execute statement with commit."""
        with self._get_db().cursor() as cur:
            cur.execute(query, params)
            self.db_conn.commit()
    
    def calculate_optimal_batch_size(
        self,
        items: List[Dict],
        target_tokens: int = 600,
        max_batch_size: int = 10,
    ) -> int:
        """Calculate optimal batch size based on token estimation."""
        
        # Estimate tokens per item by building a sample prompt
        if not items:
            return 0
            
        # Sample first item to estimate size
        sample_prompt = self._build_triage_prompt([items[0]])
        base_prompt_size = len(sample_prompt)  # Includes all the static text
        
        # Calculate tokens for additional items
        sample_item_size = len(sample_prompt) - len(self._build_triage_prompt([]))
        tokens_per_item = sample_item_size / 4  # Rough estimate
        
        # Calculate how many items fit in target token budget
        available_tokens = target_tokens * 4  # Convert to chars
        max_items = int((available_tokens - base_prompt_size) / tokens_per_item) if tokens_per_item > 0 else 1
        
        # Clamp to reasonable bounds
        optimal_size = max(1, min(max_batch_size, max_items, len(items)))
        
        logger.info(f"Optimal batch size: {optimal_size} (target: {target_tokens} tokens, est per item: {tokens_per_item:.0f})")
        
        return optimal_size
    
    def get_pending_items(
        self,
        project_id: str,
        batch_size: int = 20,
        min_priority: int = 2,  # 1=critical, 2=error, 3=warning, 4=info
    ) -> List[Dict[str, Any]]:
        """Get pending items structured for LLM triage."""
        
        query = """
            SELECT
                aft.id as work_item_id,
                aft.finding_id,
                af.file_path,
                af.line_start,
                af.line_end,
                af.message as finding_message,
                af.code_snippet,
                af.severity,
                ar.rule_id,
                ar.name as rule_name,
                ar.category,
                ar.rationale,
                ar.remediation_guidance,
                aft.suggested_action
            FROM archon_audit_finding_tasks aft
            JOIN archon_audit_findings af ON aft.finding_id = af.id
            JOIN archon_audit_rules ar ON af.rule_id = ar.id
            WHERE aft.project_id = %s
            AND aft.review_status = 'pending_review'
            AND aft.suggested_label IS NULL
            ORDER BY 
                CASE af.severity 
                    WHEN 'critical' THEN 1 
                    WHEN 'error' THEN 2 
                    WHEN 'warning' THEN 3 
                    ELSE 4 
                END
            LIMIT %s
        """
        
        items = self._query(query, (project_id, batch_size))
        
        # Prepare structured format for LLM
        for item in items:
            item['code_context'] = (
                item.get('code_snippet') or 
                f"Line {item['line_start']}: {item['finding_message']}"
            )
            item['priority_hint'] = self._get_priority_hint(item)
        
        return items
    
    def _get_priority_hint(self, item: dict) -> str:
        """Get priority hint for the LLM."""
        if item['category'] == 'security':
            return "Security-critical violations should be marked y (must fix)"
        elif item['rule_id'] in ['broad-except', 'async-exception-swallowed']:
            return "Exception handling violations that can hide bugs should be marked y (must fix)"
        elif item['rule_id'] in ['assert-missing-in-test']:
            return "Tests without any assertions provide no value and should be marked y (must fix)"
        elif item['rule_id'] in ['assert-mock-not-verified']:
            return "Unverified mocks may provide false confidence - likely y (must fix)"
        return "Consider whether this finding represents a real issue"
    
    def _build_triage_prompt(
        self,
        items: List[Dict],
    ) -> str:
        """Build enhanced prompt for LLM triage with confidence scoring."""
        
        prompt = """You are triaging audit findings. Output JSON with confidence and detailed rationale:
{
  "findings": [
    {
      "id": "uuid", 
      "label": "y|n|i|w|u", 
      "confidence": 0.95,
      "rationale": "Brief explanation (10-20 words)",
      "issue_analysis": {
        "problem": "What specifically is wrong (if y)",
        "impact": "Why this matters (security, maintainability, etc.)",
        "evidence": "Code patterns that support this decision"
      }
    }
  ]
}

Guidelines:
- 20-40% of findings should be 'i' or 'w' (intentional/acceptable debt)
- 'y' requires detailed issue_analysis explaining the problem
- 'n' needs specific reason why pattern doesn't apply
- 'i' requires explanation of why this exception is valid
- 'w' needs justification of why it's acceptable tech debt
- 'u' only when genuinely uncertain after full context
- Confidence 0.85+ = certain, <0.85 = needs investigation

Examples:
{
  "id": "example-1",
  "label": "y",
  "confidence": 0.9,
  "rationale": "Unverified mock provides false confidence",
  "issue_analysis": {
    "problem": "Mock created but never verified with assert_called",
    "impact": "Test may pass without actually testing behavior",
    "evidence": "mock_obj.create() called, no verification follows"
  }
}
{
  "id": "example-2",
  "label": "i",
  "confidence": 0.95,
  "rationale": "Rate limit handler inspects and re-raises exceptions",
  "issue_analysis": {
    "problem": "Broad exception catch is intentional for rate limit detection",
    "impact": "Allows specific handling of rate limits while preserving other errors",
    "evidence": "except Exception as e: if 'rate_limit' in str(e): handle() else: raise"
  }
}

Findings to review:
"""
        
        for i, item in enumerate(items):
            prompt += f"\n--- {i+1} ---\n"
            prompt += f"ID: {item.get('work_item_id')}\n"
            prompt += f"Rule: {item.get('rule_id')} ({item['rule_name']})\n"
            prompt += f"File: {item.get('file_path')}:{item.get('line_start')}\n"
            prompt += f"Msg: {item.get('finding_message')[:100]}\n"
            # Enhanced context - get more of the function
            code = item.get('code_context', '')[:300] if item.get('code_context') else ''
            if code:
                prompt += f"Code: {code}\n"
        
        prompt += "\nJSON:"
        
        # Log prompt size metrics
        char_count = len(prompt)
        token_estimate = char_count // 4  # Rough estimate: 4 chars per token
        logger.info(f"Prompt size: {char_count} chars (~{token_estimate} tokens) for {len(items)} items")
        print(f"   Prompt: {char_count} chars (~{token_estimate} tokens)")
        
        return prompt
    
    def _call_local_llm(self, prompt: str) -> dict | None:
        """Call local LLM (Ollama-compatible API) with timing."""
        import time
        start_time = time.time()
        
        try:
            response = self.client.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024,
                    }
                }
            )
            
            elapsed = time.time() - start_time
            print(f"   LLM call: {elapsed:.1f}s")
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                logger.info(f"LLM response ({elapsed:.1f}s): {response_text[:200]}...")
                return response_text
            else:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(f"Failed to call local LLM after {elapsed:.1f}s: {e}")
            return None
    
    def _parse_llm_response(
        self,
        response_text: str,
        expected_ids: List[str],
    ) -> List[Dict]:
        """Parse enhanced LLM response with confidence and issue analysis."""
        
        decisions = []
        
        # Try to extract JSON from response
        try:
            # Handle markdown wrapping
            if '```json' in response_text:
                start_idx = response_text.find('```json') + 7
                end_idx = response_text.find('```', start_idx)
                if end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx].strip()
                else:
                    json_str = response_text[start_idx:].strip()
            else:
                # Find JSON object/array
                start_idx = response_text.find('{')
                if start_idx == -1:
                    start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if end_idx == 0:
                    end_idx = response_text.rfind('}') + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                else:
                    json_str = response_text
            
            parsed = json.loads(json_str)
            
            # Handle both {"findings": [...]} and direct array format
            findings = parsed.get('findings', parsed) if isinstance(parsed, dict) else parsed
            
            if isinstance(findings, list):
                for item in findings:
                    if isinstance(item, dict):
                        finding_id = item.get('id') or item.get('finding_id')
                        if finding_id in expected_ids:
                            decision = {
                                'finding_id': finding_id,
                                'decision': item.get('label') or item.get('decision'),
                                'rationale': item.get('rationale', ''),
                                'confidence': item.get('confidence', 0.5),
                                'issue_analysis': item.get('issue_analysis', {}),
                            }
                            decisions.append(decision)
            
            logger.info(f"Parsed {len(decisions)} decisions from LLM response")
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response text: {response_text[:1000]}")
        
        return decisions
    
    def apply_suggestions(
        self,
        decisions: List[Dict],
        reviewer: str = "auto_liquid8b",
    ) -> Dict:
        """Apply enhanced LLM suggestions with confidence and issue analysis."""
        
        errors = 0
        
        for decision in decisions:
            try:
                # Extract issue analysis components
                analysis = decision.get('issue_analysis', {})
                
                # Update with enhanced data
                self._execute("""
                    UPDATE archon_audit_finding_tasks
                    SET 
                        suggested_label = %s,
                        suggested_rationale = %s,
                        confidence_score = %s,
                        investigation_level = %s,
                        issue_problem = %s,
                        issue_impact = %s,
                        issue_evidence = %s,
                        investigation_path = %s,
                        review_notes = %s,
                        reviewed_by = %s,
                        reviewed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    decision['decision'],
                    decision['rationale'],
                    decision.get('confidence', 0.5),
                    1,  # Initial investigation level
                    analysis.get('problem', ''),
                    analysis.get('impact', ''),
                    analysis.get('evidence', ''),
                    json.dumps({'tools_used': [], 'iterations': 1}),
                    f"[AI: {decision['decision']}] {decision['rationale']}",
                    reviewer,
                    decision['finding_id']
                ))
                
                logger.debug(f"Enhanced triage for {decision['finding_id']}: {decision['decision']} (confidence: {decision.get('confidence', 0.5)})")
                
            except Exception as e:
                logger.error(f"Failed to apply enhanced decision for {decision['finding_id']}: {e}")
                errors += 1
        
        return {
            'applied': len(decisions),
            'errors': errors,
        }
    
    def _process_batch_items(
        self,
        items: List[Dict],
    ) -> Dict[str, Any]:
        """Process a single batch of items (extracted from process_batch)."""
        
        # Build prompt
        prompt = self._build_triage_prompt(items)
        
        # Call LLM
        response = self._call_local_llm(prompt)
        
        if not response:
            logger.error("LLM returned no response")
            return {
                'processed': 0,
                'error': 'llm_no_response',
            }
        
        # Parse decisions with enhanced data
        expected_ids = [item['work_item_id'] for item in items]
        
        # Debug: print first part of response
        print(f"   Response preview: {response[:200]}...")
        
        decisions = self._parse_llm_response(response, expected_ids)
        
        # Log confidence distribution
        if decisions:
            confidences = [d.get('confidence', 0.5) for d in decisions]
            avg_confidence = sum(confidences) / len(confidences)
            low_confidence = sum(1 for c in confidences if c < 0.85)
            labels = [d.get('decision', '?') for d in decisions]
            label_counts = {l: labels.count(l) for l in set(labels)}
            print(f"   Confidence: avg={avg_confidence:.2f}, low={low_confidence}/{len(decisions)}")
            print(f"   Labels: {label_counts}")
        
        # Apply enhanced suggestions
        result = self.apply_suggestions(decisions, reviewer="auto_liquid8b")
        
        logger.info(f"Applied {result['applied']} decisions")
        
        return {
            'processed': result['applied'],
            'errors': result.get('errors', 0),
        }
    
    def process_batch(
        self,
        project_id: str,
        batch_size: int = 3,
    ) -> Dict[str, Any]:
        """Process one batch of findings (legacy method for compatibility)."""
        
        logger.info(f"Starting batch triage for project {project_id}, batch_size={batch_size}")
        
        # Get pending items
        items = self.get_pending_items(project_id, batch_size)
        
        if not items:
            logger.info("No pending items to triage")
            return {
                'batch_complete': True,
                'processed': 0,
            }
        
        logger.info(f"Processing {len(items)} findings")
        
        return self._process_batch_items(items)
    
    def process_with_retry(
        self,
        project_id: str,
        max_retries: int = 3,
        target_tokens: int = 600,
    ) -> Dict[str, Any]:
        """Process findings with intelligent batching and retry logic."""
        
        total_processed = 0
        total_errors = 0
        batch_count = 0
        
        while True:
            # Get a larger sample to calculate optimal batch size
            sample_items = self.get_pending_items(project_id, 10)
            
            if not sample_items:
                logger.info("No more pending items to process")
                break
            
            # Calculate optimal batch size for this set
            batch_size = self.calculate_optimal_batch_size(sample_items, target_tokens)
            
            # Get the actual batch to process
            items = self.get_pending_items(project_id, batch_size)
            
            if not items:
                logger.info("No more pending items to process")
                break
            
            batch_count += 1
            logger.info(f"Processing batch {batch_count}: {len(items)} items")
            
            # Process batch with retry logic
            batch_processed = 0
            for attempt in range(max_retries):
                try:
                    result = self._process_batch_items(items)
                    batch_processed = result.get('processed', 0)
                    
                    if batch_processed > 0:
                        total_processed += batch_processed
                        logger.info(f"Batch {batch_count} complete: {batch_processed} processed")
                        break
                    elif attempt < max_retries - 1:
                        # Reduce batch size and retry
                        items = items[:len(items)//2] if len(items) > 1 else items
                        logger.warning(f"Batch {batch_count} attempt {attempt + 1} failed, retrying with {len(items)} items")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        total_errors += len(items)
                        logger.error(f"Batch {batch_count} failed after {max_retries} attempts")
                        
                except Exception as e:
                    logger.error(f"Batch {batch_count} attempt {attempt + 1} error: {e}")
                    if attempt == max_retries - 1:
                        total_errors += len(items)
                    else:
                        time.sleep(2 ** attempt)
            
            # Progress update every 10 batches
            if batch_count % 10 == 0:
                logger.info(f"Progress: {total_processed} processed, {total_errors} errors")
        
        return {
            'total_processed': total_processed,
            'total_errors': total_errors,
            'batches_processed': batch_count,
        }


def main():
    """Main entry point with enhanced triage."""
    
    # Parse arguments
    args = sys.argv[1:]
    project_id = None
    batch_size = 3  # Default to 3 items per batch
    
    for i, arg in enumerate(args):
        if not arg.startswith('-') and project_id is None:
            project_id = arg
        elif not arg.startswith('-') and batch_size == 3:
            try:
                batch_size = int(arg)
            except ValueError:
                pass
    
    if not project_id:
        print("Usage: uv run python scripts/auto_triage_audit_findings.py <project_id> [--batch-size N]")
        print("  Default batch size: 3 (adjust if context window issues)")
        print("\nProject ID for Archon cleanup: 750913d5-92f6-4478-ab98-f2a79285198d")
        sys.exit(1)
    
    engine = AutoTriageEngine()
    
    print(f"🤖 Auto-triaging findings for project {project_id}")
    print(f"   Batch size: {batch_size}")
    print(f"   Enhanced: confidence scoring + detailed analysis")
    print()
    
    result = engine.process_batch(project_id, batch_size)
    
    print(f"✅ Complete")
    print(f"   Processed: {result.get('processed', 0)}")
    print(f"   Batch complete: {result.get('batch_complete', False)}")


if __name__ == "__main__":
    main()
