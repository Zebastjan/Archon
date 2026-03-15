#!/usr/bin/env python3
import subprocess
import os

result = subprocess.run([
    '/usr/bin/psql', '-h', 'localhost', '-p', '5434', '-U', 'archon', '-d', 'archon',
    '-t', '-A', '-F', '|',
    '-c', """
    SELECT aft.id, af.file_path, af.line_start 
    FROM archon_audit_finding_tasks aft
    JOIN archon_audit_findings af ON aft.finding_id = af.id
    JOIN archon_audit_rules ar ON af.rule_id = ar.id
    WHERE ar.rule_id = 'exception-not-logged'
    AND aft.review_status = 'pending_review'
    ORDER BY af.file_path, af.line_start
    LIMIT 10;
    """
], capture_output=True, text=True, env={'PGPASSWORD': 'archon_local_dev'})

print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
