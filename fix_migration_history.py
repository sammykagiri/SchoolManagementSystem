#!/usr/bin/env python
"""
Script to fix inconsistent migration history.

The issue: communications.0002_initial was applied before receivables.0001_initial,
but communications.0002_initial depends on receivables.0001_initial.

This script will:
1. Check if receivables.0001_initial needs to be faked
2. Provide instructions for fixing the migration history
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.db.migrations.recorder import MigrationRecorder

def check_migration_status():
    """Check which migrations are applied"""
    recorder = MigrationRecorder(connection)
    applied = recorder.applied_migrations()
    
    receivables_0001_applied = ('receivables', '0001_initial') in applied
    communications_0002_applied = ('communications', '0002_initial') in applied
    
    print("Current Migration Status:")
    print(f"  receivables.0001_initial: {'✓ Applied' if receivables_0001_applied else '✗ Not Applied'}")
    print(f"  communications.0002_initial: {'✓ Applied' if communications_0002_applied else '✗ Not Applied'}")
    print()
    
    if communications_0002_applied and not receivables_0001_applied:
        print("ERROR: communications.0002_initial is applied but receivables.0001_initial is not!")
        print("This is the inconsistent state causing the error.")
        print()
        print("Solution:")
        print("Option 1 (Recommended if receivables tables don't exist yet):")
        print("  1. Unapply communications.0002_initial:")
        print("     python manage.py migrate communications 0001_initial")
        print("  2. Apply receivables migrations:")
        print("     python manage.py migrate receivables")
        print("  3. Re-apply communications.0002_initial:")
        print("     python manage.py migrate communications")
        print()
        print("Option 2 (If receivables tables already exist from manual creation):")
        print("  1. Fake receivables.0001_initial:")
        print("     python manage.py migrate receivables 0001_initial --fake")
        print("  2. Continue with normal migrations:")
        print("     python manage.py migrate")
        return False
    elif receivables_0001_applied and communications_0002_applied:
        print("Both migrations are applied. The issue may be resolved.")
        return True
    else:
        print("Migration state looks okay. You can run normal migrations:")
        print("  python manage.py migrate")
        return True

if __name__ == '__main__':
    check_migration_status()
