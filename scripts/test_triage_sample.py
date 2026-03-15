#!/usr/bin/env python
"""Test auto-triage on a small sample batch to assess accuracy and prompt quality.

This script:
1. Fetches a sample of findings (default 10)
2. Runs Liquid 8B triage with current prompts
3. Shows AI decisions with rationale
4. Displays full finding details for human assessment
5. Collects accuracy feedback
6. Suggests prompt improvements

Usage:
    uv run python scripts/test_triage_sample.py <project_id> [sample_size]
"""

import json
import sys
import urllib.request
from datetime import datetime
from typing import Any

sys.path.insert(0, '/home/zebastjan/dev/archon/python')

from src.server.services.audit_workflow_service import get_audit_workflow_service


class TriageTester:
    """Test AI-assisted triage on sample findings."""
    
    def __init__(self, project_id: str, sample_size: int = 10):
        self.project_id = project_id
        self.sample_size = sample_size
        self.local_llm_url = "http://localhost:11434"
        self.local_llm_model = "kahnwong/lfm2:8b-a1b"
        
        # Fetch workflow service
        self.workflow = get_audit_workflow_service()
        
        # Results storage
        self.sample_findings = []
        self.ai_decisions = []
        self.human_assessments = []
    
    def get_sample_findings(self) -> list[dict]:
        """Fetch a representative sample for testing."""
        
        # Get diverse sample across different rules
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
            ORDER BY
                CASE af.severity 
                    WHEN 'critical' THEN 1 
                    WHEN 'error' THEN 2 
                    WHEN 'warning' THEN 3 
                    ELSE 4 
                END
            LIMIT %s
        """
        
        conn = self.workflow._get_db()
        with conn.cursor() as cur:
            cur.execute(query, (self.project_id, self.sample_size * 3))  # Get extra for diversity
            cols = [desc[0] for desc in cur.description]
            all_items = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        # Select diverse sample (one from each major rule)
        selected = {}
        rules_seen = {}
        
        for item in all_items:
            rule_id = item.get('rule_id')
            if rule_id not in rules_seen:
                rules_seen[rule_id] = []
            if len(rules_seen[rule_id]) < 2:  # Up to 2 per rule
                selected[len(selected)] = item
                rules_seen[rule_id].append(item)
            if len(selected) >= self.sample_size:
                break
        
        self.sample_findings = list(selected.values())
        
        # Add code context for each
        for item in self.sample_findings:
            snippet = item.get('code_snippet') or ''
            if not snippet or len(snippet) < 10:
                # Try to fetch more context
                item['code_context'] = f"Line {item['line_start']}: {item['finding_message']}"
            else:
                item['code_context'] = snippet[:400]
            
            # Add priority hint
            item['priority_hint'] = self._get_priority_hint(item)
        
        print(f"✓ Fetched {len(self.sample_findings)} sample findings")
        print(f"  Rules in sample: {', '.join(set(item.get('rule_id') for item in self.sample_findings))}")
        print()
        
        return self.sample_findings
    
    def _get_priority_hint(self, item: dict) -> str:
        """Get priority hint for the LLM."""
        if item['category'] == 'security':
            return "Security-critical: default to y unless clearly intentional"
        elif item['rule_id'] in ['broad-except', 'async-exception-swallowed']:
            return "Exception violations that hide bugs should be y unless top-level handler"
        elif item['rule_id'] == 'assert-missing-in-test':
            return "Tests without assertions provide no value - likely y"
        elif item['rule_id'] == 'assert-mock-not-verified':
            return "Unverified mocks may give false confidence - likely y"
        return "Use judgment based on code context"
    
    def build_prompt(
        self,
        items: list[dict],
        enable_tool_calls: bool = False,
    ) -> str:
        """Build prompt for LLM triage."""
        
        prompt = """You are a code quality expert reviewing audit findings. For each finding, decide:

y = confirmed_issue (must fix - real problem that should be addressed)
n = false_positive (pattern matched incorrectly - not actually a problem)
i = intentional (valid code by design, legitimate exception)
w = wont_fix (valid finding but not worth fixing - accepted tech debt)
s = skip (defers to human review - uncertain)

"""
        
        if enable_tool_calls:
            prompt += """You have tools available to investigate further:
- Get full function/code details
- Analyze related code
- Check call sites and usage

Use tools when uncertain or to verify your judgment.
"""
        
        prompt += """

Respond with JSON array:
[
  {"finding_id": "uuid", "decision": "y", "rationale": "short 10-20 words", "confidence": 0.8},
  ...
]

Decision Guidelines:
"""
        
        guidelines = {
            'security': "- Security/exception violations: Default y unless clearly intentional",
            'exception': "- Broad exceptions: y unless top-level handler with proper routing",
            'test': "- Test assertion issues: y if test has no assertions or mock is unverified",
            'general': "- Mark 'n' only when pattern clearly doesn't apply to code context",
            'intentional': "- Mark 'i' when code is unusual but correct (document edge case)",
            'wontfix': "- Mark 'w' for legacy or acceptable tech debt when cost > benefit",
            'uncertain': "- When uncertain, use 's' - better defer than misclassify",
            'confidence': "- Include confidence score (0.0-1.0) with your decision",
        }
        
        for key, value in guidelines.items():
            prompt += f"{value}\n"
        
        prompt += "\nNow review these findings:\n"
        
        for i, item in enumerate(items):
            prompt += f"\n--- Finding {i+1} ---\n"
            prompt += f"Finding ID: {item.get('work_item_id')}\n"
            prompt += f"Rule: {item.get('rule_id')} ({item['rule_name']})\n"
            prompt += f"Category: {item.get('category')} [{item['severity']}]\n"
            prompt += f"File: {item.get('file_path')}:{item.get('line_start')}\n"
            prompt += f"Message: {item.get('finding_message')}\n"
            prompt += f"\nCode Context:\n{item.get('code_context')[:300]}\n"
            
            if item.get('rationale'):
                prompt += f"\nRule Rationale: {item['rationale'][:150]}\n"
            if item.get('suggested_action'):
                prompt += f"Suggested Fix: {item['suggested_action'][:100]}\n"
            
            prompt += f"Priority Hint: {item.get('priority_hint', '')}\n"
        
        prompt += "\n\nRespond with JSON array including confidence (0.0-1.0):\n"
        
        return prompt
    
    def call_local_llm(self, prompt: str) -> dict | None:
        """Call local LLM via urllib."""
        try:
            url = f"{self.local_llm_url}/api/generate"
            data = json.dumps({
                "model": self.local_llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2048,
                }
            }).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    response_text = result.get("response", "")
                    return response_text
                else:
                    print(f"✗ LLM API error: {response.status_code}")
                    return None
                
        except Exception as e:
            print(f"✗ Failed to call local LLM: {e}")
            return None
    
    def parse_llm_response(
        self,
        response_text: str,
        expected_ids: list[str],
    ) -> list[dict]:
        """Parse LLM response with confidence scores."""
        
        decisions = []
        
        try:
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and item.get('finding_id') in expected_ids:
                            decisions.append({
                                'finding_id': item.get('finding_id'),
                                'decision': item.get('decision'),
                                'rationale': item.get('rationale', ''),
                                'confidence': float(item.get('confidence', 0.7)),
                            })
            
        except Exception as e:
            print(f"✗ Failed to parse LLM response: {e}")
        
        return decisions
    
    def display_sample_findings(self):
        """Display sample findings for human evaluation."""
        
        print("\n" + "=" * 80)
        print("SAMPLE FINDINGS FOR EVALUATION")
        print("=" * 80 + "\n")
        
        for i, item in enumerate(self.sample_findings, 1):
            print(f"--- Sample {i} ---")
            print(f"Rule:        {item.get('rule_id')} ({item.get('rule_name')})")
            print(f"Category:    {item.get('category')} [{item.get('severity')}]")
            print(f"File:        {item.get('file_path')}:{item.get('line_start')}")
            print(f"\nMessage:     {item.get('finding_message')}")
            print(f"\nCode Context:\n{item.get('code_context')[:400]}...\n")
            
            if i < len(self.sample_findings):
                print("-" * 80)
    
    def display_ai_decisions(self, decisions: list[dict]):
        """Display AI decisions for human review."""
        
        print("\n" + "=" * 80)
        print("AI DECISIONS FROM LIQUID 8B")
        print("=" * 80 + "\n")
        
        for i, item in enumerate(self.sample_findings, 1):
            item_id = item.get('work_item_id')
            decision = next((d for d in decisions if d['finding_id'] == item_id), None)
            
            label_map = {
                'y': 'YES (must fix)',
                'n': 'NO (false positive)',
                'i': 'INTENTIONAL',
                'w': 'WONT FIX',
                's': 'SKIP (uncertain)',
            }
            
            if decision:
                label = decision.get('decision')
                confidence = decision.get('confidence', 0)
                rationale = decision.get('rationale', '')
                
                print(f"--- Sample {i} ---")
                print(f"Rule:        {item.get('rule_id')}")
                print(f"AI Decision: {label_map.get(label, label)}")
                print(f"Confidence:  {confidence:.0%}")
                print(f"Rationale:   {rationale}")
            else:
                print(f"--- Sample {i} ---")
                print(f"Rule:        {item.get('rule_id')}")
                print(f"AI Decision: (missing)")
            
            print()
    
    def collect_human_assessments(self, decisions: list[dict]):
        """Collect human judgment on AI decisions."""
        
        print("=" * 80)
        print("HUMAN ASSESSMENT - AI ACCURACY")
        print("=" * 80)
        print("\nFor each sample, rate the AI decision:")
        print("  1 = Correct, 2 = Wrong decision, 3 = Wrong rationale")
        print("  (or press Enter to skip)\n")
        
        accurate_count = 0
        wrong_decision_count = 0
        wrong_rationale_count = 0
        skipped_count = 0
        
        self.human_assessments = []
        
        for i, item in enumerate(self.sample_findings, 1):
            item_id = item.get('work_item_id')
            decision = next((d for d in decisions if d['finding_id'] == item_id), None)
            
            if not decision:
                continue
            
            label = decision.get('decision')
            rationale = decision.get('rationale', '')
            
            print(f"\n--- Sample {i}: {item.get('rule_id')} ---")
            print(f"File:         {item.get('file_path')}:{item.get('line_start')}")
            print(f"AI Decision:  {label} - {rationale}")
            
            rating = input(f"Rating [1=correct, 2=wrong_decision, 3=wrong_rationale]: ").strip()
            
            if not rating:
                skipped_count += 1
                print("  (skipped)")
                continue
            
            rating = int(rating)
            
            assessment = {
                'sample': i,
                'rule_id': item.get('rule_id'),
                'ai_decision': label,
                'ai_rationale': rationale,
                'rating': rating,
            }
            
            self.human_assessments.append(assessment)
            
            if rating == 1:
                accurate_count += 1
                print("  ✓ Correct!")
            elif rating == 2:
                wrong_decision_count += 1
                print("  ✗ Wrong decision")
            elif rating == 3:
                wrong_rationale_count += 1
                print("  ⚠ Wrong rationale")
    
        # Summary
        print("\n" + "=" * 80)
        print("ACCURACY SUMMARY")
        print("=" * 80)
        
        total_rated = accurate_count + wrong_decision_count + wrong_rationale_count
        if total_rated > 0:
            accuracy = accurate_count / total_rated
            print(f"Accuracy: {accuracy:.0%} ({accurate_count}/{total_rated} correct)")
        else:
            print("No ratings provided")
        
        print(f"  Correct decisions: {accurate_count}")
        print(f"  Wrong decisions:   {wrong_decision_count}")
        print(f"  Wrong rationales: {wrong_rationale_count}")
        print(f"  Skipped: {skipped_count}")
    
    def run_test(self, enable_tool_calls: bool = False):
        """Run full test cycle."""
        
        print("🧪 AI-ASSISTED TRIAGE TEST CYCLE")
        print("=" * 80)
        print(f"Project: {self.project_id}")
        print(f"Sample size: {self.sample_size}")
        print(f"Model: {self.local_llm_model}")
        print()
        
        # Step 1: Get sample
        print("Step 1: Fetching sample findings...")
        items = self.get_sample_findings()
        
        if not items:
            print("✗ No findings to test")
            return
        
        # Step 2: Display samples for context
        print("\nStep 2: Displaying sample findings...")
        self.display_sample_findings()
        
        # Step 3: Build prompt and call LLM
        print("\nStep 3: Running Liquid 8B triage...")
        prompt = self.build_prompt(items, enable_tool_calls=enable_tool_calls)
        
        print("  Calling LLM...")
        response = self.call_local_llm(prompt)
        
        if not response:
            print("✗ LLM returned no response")
            return
        
        # Step 4: Parse decisions
        print("\n  Parsing AI decisions...")
        expected_ids = [item['work_item_id'] for item in items]
        decisions = self.parse_llm_response(response, expected_ids)
        
        print(f"  Parsed {len(decisions)} decisions")
        
        # Step 5: Display AI decisions
        print("\nStep 4: Displaying AI decisions...")
        self.display_ai_decisions(decisions)
        
        # Step 6: Collect human assessment
        if len(decisions) > 0:
            print("\nStep 5: Collecting human assessments...")
            self.collect_human_assessments(decisions)
        
        # Step 7: Suggest improvements
        self.suggest_improvements()
    
    def suggest_improvements(self):
        """Suggest prompt improvements based on results."""
        
        print("\n" + "=" * 80)
        print("SUGGESTED IMPROVEMENTS")
        print("=" * 80 + "\n")
        
        if not self.human_assessments:
            print("Run assessment first to get suggestions")
            return
        
        # Analyze by rule
        by_rule = {}
        for assessment in self.human_assessments:
            rule = assessment['rule_id']
            rating = assessment['rating']
            if rule not in by_rule:
                by_rule[rule] = {'correct': 0, 'wrong': 0, 'total': 0}
            by_rule[rule]['total'] += 1
            if rating == 1:
                by_rule[rule]['correct'] += 1
            else:
                by_rule[rule]['wrong'] += 1
        
        print("Performance by rule:")
        for rule, stats in by_rule.items():
            if stats['total'] > 0:
                accuracy = stats['correct'] / stats['total']
                print(f"  {rule}: {accuracy:.0%} ({stats['correct']}/{stats['total']})")
        
        print("\nPrompt improvements to consider:")
        
        # Check for common issues
        wrong_decision = [a for a in self.human_assessments if a['rating'] == 2]
        wrong_rationale = [a for a in self.human_assessments if a['rating'] == 3]
        
        if wrong_decision:
            print(f"\n⚠ Wrong decisions ({len(wrong_decision)}):")
            print("  1. Add more code context (expand snippet)")
            print("  2. Clarify when exception handling is intentional")
            print("  3. Add 'confidence threshold' - ask tools when < 0.7")
            print("  4. Emphasize looking at surrounding function logic")
        
        if wrong_rationale:
            print(f"\n⚠ Wrong rationales ({len(wrong_rationale)}):")
            print("  1. Request more specific reasoning (show why)")
            print("  2. Ask model to explain edge cases considered")
            print("  3. Reference specific code patterns")
        
        print("\nTool calling suggestions:")
        print("  1. Enable tools for decisions with confidence < 0.7")
        print("  2. Let model fetch full function when analyzing exception handlers")
        print("  3. Allow model to check adjacent code for context")
        print("  4. But keep it simple - don't over-engineer")


def main():
    """Main entry point."""
    
    project_id = sys.argv[1] if len(sys.argv) > 1 else "750913d5-92f6-4478-ab98-f2a79285198d"
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    tester = TriageTester(project_id, sample_size)
    tester.run_test(enable_tool_calls=False)


if __name__ == "__main__":
    main()
