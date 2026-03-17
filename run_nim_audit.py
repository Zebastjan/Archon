#!/usr/bin/env python3
"""Direct Nim audit for Omnibus repository"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the python/src directory to path
sys.path.insert(0, '/app/python/src')
os.chdir('/app/python')

# Set up environment
os.environ['PYTHONPATH'] = '/app/python/src'

# Now imports should work
from services.database.db_connector import get_database_connector

async def get_repo_id(repo_name: str) -> str | None:
    """Get repo ID from database"""
    db = get_database_connector()
    result = await db.fetch(
        "SELECT id FROM archon_code_repos WHERE name = $1",
        repo_name
    )
    if result:
        return str(result[0]['id'])
    return None

async def run_nim_audit():
    """Run Nim audit using tree-sitter based analysis"""
    repo_path = Path('/repos/Omnibus')
    
    if not repo_path.exists():
        print(f"ERROR: Repository not found at {repo_path}")
        return
    
    # Get all .nim files
    nim_files = list(repo_path.rglob('*.nim'))
    nim_files = [f for f in nim_files if '.git' not in str(f)]
    
    print(f"Found {len(nim_files)} Nim files to analyze")
    
    # Import and run the audit
    from services.nim_audit_service import NimAuditService
    
    service = NimAuditService()
    findings = await service.audit_repository(str(repo_path))
    
    # Group by rule
    by_rule = {}
    for f in findings:
        rule = f.get('rule_id', 'unknown')
        severity = f.get('severity', 'info')
        key = (rule, severity)
        if key not in by_rule:
            by_rule[key] = []
        by_rule[key].append(f)
    
    print(f"\n{'='*60}")
    print(f"TOTAL FINDINGS: {len(findings)}")
    print(f"UNIQUE RULES: {len(by_rule)}")
    print(f"{'='*60}\n")
    
    # Sort by count
    sorted_rules = sorted(by_rule.items(), key=lambda x: -len(x[1]))
    
    for (rule, severity), items in sorted_rules[:30]:
        count = len(items)
        print(f"\n[{severity.upper()}] {rule}: {count} findings")
        print("-" * 50)
        
        # Show up to 3 samples
        for i, item in enumerate(items[:3]):
            file_path = item.get('file_path', 'unknown')
            line = item.get('line_number', 0)
            message = item.get('message', 'No message')
            code = item.get('code_snippet', '')[:100].replace('\n', ' ')
            
            print(f"  Sample {i+1}: {file_path}:{line}")
            print(f"    Message: {message[:80]}")
            print(f"    Code: {code}...")
            print()
    
    # Save detailed results
    output = {
        'total_findings': len(findings),
        'rules_found': len(by_rule),
        'grouped_findings': {
            f"{rule}|{severity}": {
                'count': len(items),
                'samples': items[:5]
            }
            for (rule, severity), items in sorted_rules
        }
    }
    
    output_path = Path('/tmp/omnibus_nim_audit.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_path}")

if __name__ == '__main__':
    asyncio.run(run_nim_audit())
