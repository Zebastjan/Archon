#!/usr/bin/env python3
"""
Interactive script for reviewing audit findings.

Usage:
    uv run python scripts/review_audit_findings.py [project_id]

Interactive commands:
    y  - Mark as confirmed_issue (create task and fix)
    n  - Mark as false_positive (pattern matched incorrectly)
    i  - Mark as intentional (valid by design)
    w  - Mark as wont_fix (accepted tech debt)
    s  - Skip for now
    q  - Quit
"""

import sys
from uuid import UUID

sys.path.insert(0, '/home/zebastjan/dev/archon/python')

from src.server.services.audit_workflow_service import (
    AuditWorkflowService,
    get_audit_workflow_service,
)


def print_finding(item, index, total):
    """Print a finding for review."""
    print("\n" + "=" * 70)
    print(f"Finding {index + 1} of {total}")
    print("=" * 70)
    print(f"Rule:        {item.rule_id} ({item.severity})")
    print(f"Category:    {item.category}")
    print(f"File:        {item.file_path}:{item.line_start}")
    print(f"\nMessage:     {item.finding_message}")
    print(f"\nContext:     {item.file_context}")
    print(f"\nSuggested:   {item.suggested_action}")
    
    # Show AI suggestion if available
    if hasattr(item, 'suggested_label') and item.suggested_label:
        label_map = {
            'y': 'YES - fix this',
            'n': 'NO - false positive', 
            'i': 'INTENTIONAL',
            'w': 'WONT FIX',
        }
        ai_decision = label_map.get(item.suggested_label, f'Unknown: {item.suggested_label}')
        print(f"\n🤖 AI Suggestion: {ai_decision}")
        if item.suggested_rationale:
            print(f"   Rationale: {item.suggested_rationale}")
    
    if item.rationale:
        print(f"\nRationale:   {item.rationale[:200]}...")
    print("\n" + "-" * 70)


def get_decision():
    """Get review decision from user."""
    print("\nCommands:")
    print("  Enter = Accept AI suggestion")
    print("  y     = Yes, must fix (confirmed_issue)")
    print("  1     = Override to YES (fix this)")
    print("  n     = No, false positive")
    print("  2     = Override to NO (false positive)")
    print("  i     = Intentional (valid code by design)")
    print("  3     = Override to INTENTIONAL")
    print("  w     = Won't fix (accepted tech debt)")
    print("  4     = Override to WONT FIX")
    print("  s     = Skip for now")
    print("  q     = Quit")
    print()
    
    while True:
        choice = input("Decision [Enter/y/n/i/w/s/q]: ").strip().lower()
        if choice in ('', 'y', 'n', 'i', 'w', 's', 'q', '1', '2', '3', '4'):
            return choice
        print("Invalid choice. Please use Enter/y/n/i/w/s/q or 1/2/3/4 to override.")


def main():
    """Main review loop."""
    # Default to Archon cleanup project
    project_id = "750913d5-92f6-4478-ab98-f2a79285198d"
    
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    
    print("=" * 70)
    print("AUDIT FINDING REVIEW")
    print("=" * 70)
    print(f"Project: {project_id}")
    print()
    
    service = get_audit_workflow_service()
    
    # show initial progress
    summary = service.get_progress_summary(project_id=project_id)
    print(f"Progress: {summary.percent_reviewed():.1f}% reviewed ({summary.total_findings - summary.pending_review}/{summary.total_findings})")
    print(f"  Pending review:   {summary.pending_review}")
    print(f"  Confirmed issues: {summary.confirmed_issue}")
    print(f"  Intentional:      {summary.intentional}")
    print(f"  False positives:  {summary.false_positive}")
    print(f"  Won't fix:        {summary.wont_fix}")
    print(f"  Fixed:            {summary.fixed}")
    print()
    
    # Get pending items (auto_suggested included)
    items = service.get_pending_review_items(project_id=project_id, limit=50)
    
    if not items:
        print("✅ All findings have been reviewed!")
        return
    
    print(f"Loaded {len(items)} findings for review.")
    print()
    
    reviewed_by = input("Your name (for review tracking): ").strip() or "reviewer"
    
    for i, item in enumerate(items):
        print_finding(item, i, len(items))
        
        decision = get_decision()
        
        if decision == 'q':
            print("\nQuitting. Progress saved.")
            break
        elif decision == 's':
            print("Skipping...")
            continue
        
        # Handle Enter = accept AI suggestion
        if decision == '' and hasattr(item, 'suggested_label') and item.suggested_label:
            decision = item.suggested_label
            print(f"✓ Accepted AI suggestion: {decision}")
        elif decision in ('1', '2', '3', '4'):
            # Override shortcuts
            override_map = {
                '1': 'y',  # Override to YES
                '2': 'n',  # Override to NO
                '3': 'i',  # Override to INTENTIONAL
                '4': 'w',  # Override to WONT FIX
            }
            decision = override_map[decision]
            print(f"✓ Override to: {decision}")
        
        # Map decision to status
        status_map = {
            'y': 'confirmed_issue',
            'n': 'false_positive',
            'i': 'intentional',
            'w': 'wont_fix',
        }
        
        if decision not in status_map:
            print(f"⚠️ Unknown decision '{decision}', skipping")
            continue
        
        status = status_map[decision]
        
        # Get notes
        if decision in ('i', 'w'):
            notes = input(f"Notes (why {status}): ").strip()
        else:
            notes = input("Notes (optional): ").strip() or None
        
        # Save review
        try:
            service.review_finding(item.id, status, reviewed_by, notes)
            print(f"✅ Marked as {status}")
            
            # If confirmed issue, offer to create task
            if decision == 'y':
                create_task = input("Create task now? [y/N]: ").strip().lower()
                if create_task == 'y':
                    task_id = service.create_task_from_finding(item.id, UUID(project_id), reviewed_by)
                    if task_id:
                        print(f"✅ Created task: {task_id}")
                    else:
                        print("⚠️ Failed to create task")
                        
        except Exception as e:
            print(f"❌ Error saving review: {e}")
    
    # Show final progress
    print("\n" + "=" * 70)
    print("REVIEW SESSION COMPLETE")
    print("=" * 70)
    summary = service.get_progress_summary(project_id=project_id)
    print(f"Progress: {summary.percent_reviewed():.1f}% reviewed")
    print(f"  Remaining to review: {summary.pending_review}")
    print()


if __name__ == "__main__":
    main()
