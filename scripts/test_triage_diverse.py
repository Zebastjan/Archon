#!/usr/bin/env python
"""Test auto-triage on a diverse sample across all audit categories.

This script ensures we test across:
- Security (exception-not-logged)
- Maintainability (broad-except)
- Testing (assert-mock-not-verified, assert-missing-in-test)
- Complexity (high complexity)
- Documentation (missing docs)
"""

import json
import sys
import urllib.request
from datetime import datetime
from typing import Any

sys.path.insert(0, '/home/zebastjan/dev/archon/python')

from src.server.services.audit_workflow_service import get_audit_workflow_service


class DiverseTriageTester:
    """Test AI-assisted triage on diverse sample across categories."""
    
    def __init__(self, project_id: str, sample_size: int = 15):
        self.project_id = project_id
        self.sample_size = sample_size
        self.local_llm_url = "http://localhost:11434"
        self.local_llm_model = "kahnwong/lfm2:8b-a1b"
        
        self.workflow = get_audit_workflow_service()
        self.sample_findings = []
    
    def get_diverse_sample(self) -> list[dict]:
        """Get diverse sample across all categories."""
        
        conn = self.workflow._get_db()
        
        # First get all categories
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ar.category
                FROM archon_audit_finding_tasks aft
                JOIN archon_audit_findings af ON aft.finding_id = af.id
                JOIN archon_audit_rules ar ON af.rule_id = ar.id
                WHERE aft.project_id = %s
                AND aft.review_status = 'pending_review'
            """, (self.project_id,))
            categories = [row[0] for row in cur.fetchall()]
        
        print(f"Detected {len(categories)} categories: {', '.join(categories)}")
        
        if len(categories) == 0:
            print("No categories found")
            return []
        
        # Sample from each category
        all_items = []
        items_per_category = max(1, self.sample_size // len(categories))
        
        for category in categories:
            with conn.cursor() as cur:
                cur.execute("""
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
                        r.name as rule_name,
                        ar.category,
                        ar.rationale,
                        ar.remediation_guidance,
                        aft.suggested_action
                    FROM archon_audit_finding_tasks aft
                    JOIN archon_audit_findings af ON aft.finding_id = af.id
                    JOIN archon_audit_rules ar ON af.rule_id = ar.id
                    JOIN archon_audit_rules r ON af.rule_id = ar.id
                    WHERE aft.project_id = %s
                    AND aft.review_status = 'pending_review'
                    AND ar.category = %s
                    ORDER BY
                        CASE af.severity
                            WHEN 'critical' THEN 1
                            WHEN 'error' THEN 2
                            WHEN 'warning' THEN 3
                            ELSE 4
                        END
                    LIMIT %s
                """, (self.project_id, category, items_per_category))
                
                cols = [desc[0] for desc in cur.description]
                items = [dict(zip(cols, row)) for row in cur.fetchall()]
                all_items.extend(items)
        
        # If we need more, get remaining items
        if len(all_items) < self.sample_size and len(categories) > 0:
            remaining = self.sample_size - len(all_items)
            with conn.cursor() as cur:
                cur.execute("""
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
                        r.name as rule_name,
                        ar.category,
                        ar.rationale,
                        ar.remediation_guidance,
                        aft.suggested_action
                    FROM archon_audit_finding_tasks aft
                    JOIN archon_audit_findings af ON aft.finding_id = af.id
                    JOIN archon_audit_rules ar ON af.rule_id = ar.id
                    JOIN archon_audit_rules r ON af.rule_id = ar.id
                    WHERE aft.project_id = %s
                    AND aft.review_status = 'pending_review'
                    AND NOT EXISTS (
                        SELECT 1 FROM (VALUES %s) AS v(id)
                        WHERE v.id = aft.id
                    )
                    ORDER BY RANDOM()
                    LIMIT %s
                """, (self.project_id, tuple([i['work_item_id'] for i in all_items]) if all_items else (), remaining))
                
                cols = [desc[0] for desc in cur.description]
                items = [dict(zip(cols, row)) for row in cur.fetchall()]
                all_items.extend(items)
        
        # Add context for each item
        for item in all_items:
            snippet = item.get('code_snippet') or ''
            if not snippet or len(snippet) < 10:
                item['code_context'] = f"Line {item['line_start']}: {item['finding_message']}"
            else:
                item['code_context'] = snippet[:400]
            
            item['priority_hint'] = self._get_priority_hint(item)
        
        self.sample_findings = all_items[:self.sample_size]
        
        print(f"✓ Fetched {len(self.sample_findings)} sample findings")
        
        # Show breakdown
        breakdown = {}
        for item in self.sample_findings:
            cat = item.get('category', 'unknown')
            cat = cat if cat else 'unknown'
            breakdown[cat] = breakdown.get(cat, 0) + 1
        
        print("  Breakdown:")
        for cat, count in sorted(breakdown.items()):
            print(f"    {cat}: {count}")
        print()
        
        return self.sample_findings
    
    def _get_priority_hint(self, item: dict) -> str:
        """Get priority hint for the LLM."""
        cat = item.get('category', '')
        rule_id = item.get('rule_id', '')
        
        hints = {
            'security': "Security-critical vulnerabilities must be fixed unless clearly intentional",
            'maintainability': "Maintainability issues: consider impact and effort - default y unless edge case",
            'testing': "Test quality issues: default to fix unless dealing with fixture/setup code",
            'complexity': "High complexity: default y if >15, consider if function is legitimately complex",
            'documentation': "Missing docs: y for public APIs, consider i for internal helpers",
        }
        
        # Rule-specific hints
        if rule_id == 'broad-except':
            return "Broad exception: y unless top-level with proper routing, or re-raises immediately"
        elif rule_id == 'exception-not-logged':
            return "Unlogged exception: y for internal handlers, may be i for top-level with external logging"
        elif rule_id == 'assert-missing-in-test':
            return "No assertions: y for unit tests, may be i for integration tests or fixtures"
        elif rule_id == 'assert-mock-not-verified':
            return "Unverified mock: y for test-specific mocks, may be i for shared fixtures"
        
        return hints.get(cat, "Use judgment based on code context and impact")
    
    def build_prompt(self, items: list[dict]) -> str:
        """Build comprehensive prompt for diverse findings."""
        
        prompt = """You are a code quality expert reviewing audit findings across multiple categories. For each finding, decide:

y = confirmed_issue (must fix - real problem)
n = false_positive (pattern matched incorrectly - not a problem)
i = intentional (valid by design, legitimate exception)
w = wont_fix (not worth fixing - accepted tech debt)
s = skip (defers to human review - uncertain)

Respond with JSON array:
[
  {"finding_id": "uuid", "decision": "y", "rationale": "short", "confidence": 0.8},
  ...
]

Guidelines:
"""
        
        guidelines = [
            "Security (exception-not-logged, broad-except): Default y unless clearly intentional top-level handler",
            "Testing (assert-mock-not-verified, assert-missing-in-test): Default y unless fixture/setup code",
            "Maintainability/Complexity: Consider impact and effort - obvious problems = y, edge cases = i/w",
            "Documentation: y for public APIs, i for internal helpers",
            "",
            "Mark 'n' only when pattern clearly doesn't apply to code context",
            "Mark 'i' when code is unusual but correct (document edge case)",
            "Mark 'w' when cost > benefit (legacy, deprecated, acceptable tech debt)",
            "Include confidence score (0.0-1.0) with each decision",
        ]
        
        for line in guidelines:
            prompt += f"{line}\n"
        
        prompt += "\nNow review these findings from different categories:\n"
        
        for i, item in enumerate(items):
            prompt += f"\n--- Finding {i+1} ---\n"
            prompt += f"Finding ID: {item.get('work_item_id')}\n"
            prompt += f"Category: {item.get('category')} [{item.get('severity')}]\n"
            prompt += f"Rule: {item.get('rule_id')} ({item.get('rule_name')})\n"
            prompt += f"File: {item.get('file_path')}:{item.get('line_start')}\n"
            prompt += f"Issue: {item.get('finding_message')}\n"
            prompt += f"\nCode:\n{item.get('code_context')[:300]}\n"
            
            if item.get('reasonale'):
                prompt += f"\nRule Context: {item['rationale'][:120]}\n"
            
            if item.get('suggested_action'):
                prompt += f"Fix: {item['suggested_action'][:80]}\n"
            
            prompt += f"Hint: {item.get('priority_hint', '')}\n"
        
        prompt += "\n\nRespond with decisions and confidence scores:\n"
        
        return prompt
    
    def call_local_llm(self, prompt: str) -> str | None:
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
            
            with urllib.request.urlopen(req, timeout=90) as response:
                if response.status == 200:
                    result = json.loads(response.read().decode('utf-8'))
                    return result.get("response", "")
                else:
                    print(f"✗ LLM API error: {response.status}")
                    return None
                
        except Exception as e:
            print(f"✗ Failed to call local LLM: {e}")
            return None
    
    def parse_llm_response(self, response_text: str, expected_ids: list[str]) -> list[dict]:
        """Parse LLM response."""
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
    
    def display_sample(self):
        """Display diverse sample."""
        print("\n" + "=" * 80)
        print("DIVERSE SAMPLE FINDINGS")
        print("=" * 80 + "\n")
        
        for i, item in enumerate(self.sample_findings, 1):
            print(f"--- Sample {i} [{item.get('category')}] ---")
            print(f"Rule:   {item.get('rule_id')} ({item.get('rule_name')})")
            print(f"File:   {item.get('file_path')}:{item.get('line_start')}")
            print(f"Issue:  {item.get('finding_message')}")
            print(f"Code:\n{item.get('code_context')[:300]}")
            print()
    
    def display_decisions(self, decisions: list[dict]):
        """Display AI decisions."""
        print("\n" + "=" * 80)
        print("AI DECISIONS FROM LIQUID 8B")
        print("=" * 80 + "\n")
        
        label_map = {
            'y': 'YES (must fix)',
            'n': 'NO (false positive)',
            'i': 'INTENTIONAL',
            'w': 'WONT FIX',
            's': 'SKIP (uncertain)',
        }
        
        for i, item in enumerate(self.sample_findings, 1):
            item_id = item.get('work_item_id')
            decision = next((d for d in decisions if d['finding_id'] == item_id), None)
            
            print(f"--- Sample {i}: {item.get('category')} - {item.get('rule_id')} ---")
            print(f"File: {item.get('file_path')}")
            
            if decision:
                label = decision.get('decision')
                confidence = decision.get('confidence', 0)
                rationale = decision.get('rationale', '')
                
                print(f"AI: {label_map.get(label, label)} ({confidence:.0%})")
                print(f"Why: {rationale}")
            else:
                print("AI: (missing)")
            
            print()
    
    def collect_assessment(self, decisions: list[dict]):
        """Collect human assessment."""
        print("=" * 80)
        print("ACCURACY ASSESSMENT")
        print("=" * 80)
        print("\nRate each AI decision:")
        print("  1 = Correct, 2 = Wrong decision, 3 = Wrong rationale (or Enter to skip)\n")
        
        accurate = 0
        wrong = 0
        wrong_rationale = 0
        skipped = 0
        
        for i, item in enumerate(self.sample_findings, 1):
            item_id = item.get('work_item_id')
            decision = next((d for d in decisions if d['finding_id'] == item_id), None)
            
            if not decision:
                continue
            
            label_map = {'y': 'YES', 'n': 'NO', 'i': 'INTENTIONAL', 'w': 'WONT FIX', 's': 'SKIP'}
            label = label_map.get(decision.get('decision'), decision.get('decision'))
            rationale = decision.get('rationale', '')
            
            print(f"\n--- Sample {i}: {item.get('category')} - {item.get('rule_id')} ---")
            print(f"AI: {label} - {rationale}")
            print(f"   File: {item.get('file_path')}")
            
            try:
                rating = input(f"Rating [Enter=skip]: ").strip()
                
                if not rating:
                    skipped += 1
                    continue
                
                rating = int(rating)
                
                if rating == 1:
                    accurate += 1
                    print("  ✓ Correct!")
                elif rating == 2:
                    wrong += 1
                    print("  ✗ Wrong decision")
                elif rating == 3:
                    wrong_rationale += 1
                    print("  ⚠ Wrong rationale")
            except EOFError:
                print("  (EOF, skipping)")
                skipped += 1
        
        # Summary
        total = accurate + wrong + wrong_rationale
        if total > 0:
            accuracy = accurate / total
            print(f"\nAccuracy: {accuracy:.0%} ({accurate}/{total} correct)")
        print(f"Correct: {accurate}, Wrong decision: {wrong}, Wrong rationale: {wrong_rationale}, Skipped: {skipped}")
    
    def run_test(self):
        """Run diverse test cycle."""
        
        print("🧪 DIVERSE SAMPLE TRIAGE TEST")
        print("=" * 80)
        print(f"Project: {self.project_id}")
        print(f"Sample: {self.sample_size} findings across categories")
        print(f"Model: {self.local_llm_model}")
        print()
        
        # Get diverse sample
        items = self.get_diverse_sample()
        if not items:
            return
        
        # Display
        self.display_sample()
        
        # Build prompt
        print("Calling Liquid 8B on diverse sample...")
        prompt = self.build_prompt(items)
        
        # Call LLM
        response = self.call_local_llm(prompt)
        
        if not response:
            print("✗ LLM failed")
            return
        
        # Parse
        expected_ids = [item['work_item_id'] for item in items]
        decisions = self.parse_llm_response(response, expected_ids)
        
        if not decisions:
            print("✗ No decisions parsed")
            return
        
        print(f"✓ Parsed {len(decisions)} decisions")
        
        # Display
        self.display_decisions(decisions)
        
        # Assess
        self.collect_assessment(decisions)
        
        # Analysis
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print("\nAfter reviewing the diverse sample:")
        print("1. Check accuracy by category (is Liquid 8B better/worse at certain types?)")
        print("2. Consider adding tool calls for low-confidence decisions")
        print("3. If accuracy > 80%, ready to scale to full 785 findings")
        print("4. If accuracy < 70%, refine prompts per category")


def main():
    project_id = sys.argv[1] if len(sys.argv) > 1 else "750913d5-92f6-4478-ab98-f2a79285198d"
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    
    tester = DiverseTriageTester(project_id, sample_size)
    tester.run_test()


if __name__ == "__main__":
    main()
