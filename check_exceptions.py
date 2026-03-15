#!/usr/bin/env python3
"""Script to identify false positive exception-not-logged findings."""

import subprocess
import os

def get_findings():
    """Get all Exception Not Logged findings from database."""
    result = subprocess.run([
        '/usr/bin/psql', '-h', 'localhost', '-p', '5434', '-U', 'archon', '-d', 'archon', '-c',
        """
        SELECT 
            aft.id,
            af.file_path,
            af.line_start
        FROM archon_audit_finding_tasks aft
        JOIN archon_audit_findings af ON aft.finding_id = af.id
        JOIN archon_audit_rules ar ON af.rule_id = ar.id
        WHERE ar.rule_id = 'exception-not-logged'
        AND aft.review_status = 'pending_review'
        """
    ], capture_output=True, text=True, env={'PGPASSWORD': 'archon_local_dev'})
    
    lines = result.stdout.strip().split('\n')[2:]  # Skip header and separator
    findings = []
    for line in lines:
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 3:
                finding_id = parts[0].strip()
                file_path = parts[1].strip()
                line_start = int(parts[2].strip())
                findings.append((finding_id, file_path, line_start))
    
    return findings

def check_for_logging(file_path, line_start):
    """Check if logging exists within 25 lines after the flagged line."""
    try:
        full_path = f'/home/zebastjan/dev/archon/{file_path}'
        if not os.path.exists(full_path):
            return False
            
        with open(full_path, 'r') as f:
            content_lines = f.readlines()
        
        # Check lines 0-25 after the flagged line for logging
        start_check = line_start - 1  # Convert to 0-based
        end_check = min(start_check + 25, len(content_lines))
        
        for i in range(start_check, end_check):
            line = content_lines[i]
            if 'logger.' in line or 'search_logger.' in line:
                return True
        
        return False
    except Exception as e:
        print(f"Error checking {file_path}:{line_start} - {e}")
        return False

def main():
    print("Analyzing Exception Not Logged findings...")
    
    findings = get_findings()
    print(f"Total findings to check: {len(findings)}")
    
    false_positives = []
    genuine_issues = []
    
    for finding_id, file_path, line_start in findings:
        if check_for_logging(file_path, line_start):
            false_positives.append(finding_id)
        else:
            genuine_issues.append(finding_id)
    
    print(f"\nResults:")
    print(f"False positives (have logger): {len(false_positives)}")
    print(f"Genuine issues (no logger): {len(genuine_issues)}")
    
    if len(false_positives) + len(genuine_issues) > 0:
        fp_rate = len(false_positives) / (len(false_positives) + len(genuine_issues)) * 100
        print(f"False positive rate: {fp_rate:.1f}%")
    
    # Save false positive IDs to file
    with open('/tmp/false_positive_ids.txt', 'w') as f:
        for fp_id in false_positives:
            f.write(f"'{fp_id}',\n")
    
    print(f"\nFalse positive IDs saved to /tmp/false_positive_ids.txt")
    
    # Show sample of false positives
    print(f"\nSample false positives (first 10):")
    for i, fp_id in enumerate(false_positives[:10]):
        print(f"  {i+1}. {fp_id}")

if __name__ == "__main__":
    main()
