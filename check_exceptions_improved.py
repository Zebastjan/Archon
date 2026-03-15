#!/usr/bin/env python3
"""Improved script to identify false positive exception-not-logged findings."""

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
    """Check if logging exists within the same except block."""
    try:
        full_path = f'/home/zebastjan/dev/archon/{file_path}'
        if not os.path.exists(full_path):
            return False
            
        with open(full_path, 'r') as f:
            content_lines = f.readlines()
        
        # Find the except block
        start_check = line_start - 1  # Convert to 0-based
        
        # Look for the except line
        except_line_idx = None
        for i in range(max(0, start_check - 5), min(start_check + 5, len(content_lines))):
            if 'except Exception' in content_lines[i] or 'except:' in content_lines[i]:
                except_line_idx = i
                break
        
        if except_line_idx is None:
            return False
        
        # Scan forward until we find the end of the except block
        # (next except, next same-level code, or end of function)
        for i in range(except_line_idx + 1, min(except_line_idx + 50, len(content_lines))):
            line = content_lines[i].strip()
            
            # Check for logging
            if 'logger.' in line or 'search_logger.' in line:
                return True
            
            # Stop if we hit the next except block at same level
            if line.startswith('except ') and not line.startswith('except Exception'):
                break
                
            # Stop if we hit return/raise without indentation change
            if (line.startswith('return ') or line.startswith('raise ')) and i > except_line_idx + 1:
                # Check a few more lines for logging after return/raise
                for j in range(i + 1, min(i + 10, len(content_lines))):
                    if 'logger.' in content_lines[j] or 'search_logger.' in content_lines[j]:
                        return True
                break
        
        return False
    except Exception as e:
        print(f"Error checking {file_path}:{line_start} - {e}")
        return False

def main():
    print("Re-analyzing Exception Not Logged findings with improved detection...")
    
    findings = get_findings()
    print(f"Total findings to check: {len(findings)}")
    
    false_positives = []
    genuine_issues = []
    
    for finding_id, file_path, line_start in findings:
        if check_for_logging(file_path, line_start):
            false_positives.append(finding_id)
        else:
            genuine_issues.append(finding_id)
    
    print(f"\nImproved Results:")
    print(f"False positives (have logger): {len(false_positives)}")
    print(f"Genuine issues (no logger): {len(genuine_issues)}")
    
    if len(false_positives) + len(genuine_issues) > 0:
        fp_rate = len(false_positives) / (len(false_positives) + len(genuine_issues)) * 100
        print(f"False positive rate: {fp_rate:.1f}%")
    
    # Save false positive IDs to file
    with open('/tmp/improved_false_positive_ids.txt', 'w') as f:
        for fp_id in false_positives:
            f.write(f"'{fp_id}',\n")
    
    print(f"\nImproved false positive IDs saved to /tmp/improved_false_positive_ids.txt")

if __name__ == "__main__":
    main()
