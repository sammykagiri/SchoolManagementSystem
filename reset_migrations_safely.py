#!/usr/bin/env python
"""
Safely reset migrations for an app.

This script:
1. Deletes migration files (except __init__.py)
2. Creates new initial migration
3. Fakes the migration (marks as applied without running, since tables exist)

WARNING: Only use this if you're sure the database schema matches your models!

Usage:
    python reset_migrations_safely.py receivables
    python reset_migrations_safely.py communications
"""

import os
import sys
import django
import shutil
from pathlib import Path

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.core.management import call_command
from django.db import connection

def reset_app_migrations(app_name):
    """Reset migrations for a specific app"""
    print(f"\n{'='*60}")
    print(f"Resetting migrations for app: {app_name}")
    print(f"{'='*60}\n")
    
    # Step 1: Check if app exists
    app_path = Path(__file__).parent / app_name
    migrations_dir = app_path / 'migrations'
    
    if not app_path.exists():
        print(f"✗ App '{app_name}' not found!")
        return False
    
    if not migrations_dir.exists():
        print(f"✗ Migrations directory not found for '{app_name}'!")
        return False
    
    # Step 2: Backup migration files (optional safety measure)
    backup_dir = migrations_dir.parent / f'migrations_backup_{app_name}'
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(migrations_dir, backup_dir)
    print(f"✓ Backed up migrations to {backup_dir}")
    
    # Step 3: Delete migration files (except __init__.py)
    migration_files = [f for f in migrations_dir.iterdir() 
                      if f.is_file() and f.name.endswith('.py') and f.name != '__init__.py']
    
    for mig_file in migration_files:
        print(f"  Deleting {mig_file.name}...")
        mig_file.unlink()
    
    print(f"✓ Deleted {len(migration_files)} migration files")
    
    # Step 4: Delete migration records from database
    print(f"\nDeleting migration records from database...")
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM django_migrations 
            WHERE app = %s
        """, [app_name])
        deleted_count = cursor.rowcount
        connection.commit()
        print(f"✓ Deleted {deleted_count} migration records from database")
    
    # Step 5: Create new initial migration
    print(f"\nCreating new initial migration...")
    try:
        call_command('makemigrations', app_name, verbosity=1)
        print(f"✓ Created new initial migration")
    except Exception as e:
        print(f"✗ Failed to create migration: {e}")
        print(f"  Restoring from backup...")
        if backup_dir.exists():
            shutil.rmtree(migrations_dir)
            shutil.copytree(backup_dir, migrations_dir)
        return False
    
    # Step 6: Fake apply the migration (since tables already exist)
    print(f"\nFaking migration application (tables already exist)...")
    try:
        # Get the new migration file name
        new_migrations = [f for f in migrations_dir.iterdir() 
                        if f.is_file() and f.name.endswith('.py') and f.name != '__init__.py']
        if new_migrations:
            new_mig_name = new_migrations[0].stem
            call_command('migrate', app_name, new_mig_name, '--fake', verbosity=1)
            print(f"✓ Faked migration {new_mig_name}")
        else:
            print("✗ No new migration file found!")
            return False
    except Exception as e:
        print(f"✗ Failed to fake migration: {e}")
        return False
    
    print(f"\n{'='*60}")
    print(f"✓ Successfully reset migrations for {app_name}")
    print(f"{'='*60}\n")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python reset_migrations_safely.py <app_name>")
        print("Example: python reset_migrations_safely.py receivables")
        sys.exit(1)
    
    app_name = sys.argv[1]
    
    # Confirm
    response = input(f"Are you sure you want to reset migrations for '{app_name}'? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        sys.exit(0)
    
    try:
        success = reset_app_migrations(app_name)
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
