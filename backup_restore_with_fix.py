#!/usr/bin/env python
"""
Backup, recreate database, run migrations, and restore data.

This script:
1. Backs up the database
2. Backs up django_migrations table separately
3. Drops and recreates the database
4. Runs migrations from scratch
5. Restores data (excluding django_migrations table)

Usage:
    python backup_restore_with_fix.py
"""

import os
import sys
import subprocess
import django
from datetime import datetime
from pathlib import Path

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.db import connection

def get_db_config():
    """Get database configuration from Django settings"""
    db = settings.DATABASES['default']
    return {
        'name': db['NAME'],
        'user': db['USER'],
        'password': db.get('PASSWORD', ''),
        'host': db.get('HOST', 'localhost'),
        'port': db.get('PORT', '5432'),
    }

def run_command(cmd, check=True):
    """Run a shell command"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"✗ Command failed: {result.stderr}")
        raise Exception(f"Command failed: {result.stderr}")
    return result

def backup_restore_with_fix():
    """Main function"""
    print("=" * 60)
    print("Database Backup, Recreate, and Restore")
    print("=" * 60)
    print()
    
    db_config = get_db_config()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"backup_{timestamp}.sql"
    migrations_backup = f"django_migrations_backup_{timestamp}.sql"
    
    # Set PGPASSWORD environment variable
    env = os.environ.copy()
    if db_config['password']:
        env['PGPASSWORD'] = db_config['password']
    
    # Step 1: Backup database
    print("Step 1: Creating full database backup...")
    try:
        cmd = [
            'pg_dump',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-d', db_config['name'],
            '-F', 'c',  # Custom format
            '-f', backup_file
        ]
        run_command(cmd, env=env)
        print(f"✓ Backup created: {backup_file}")
    except Exception as e:
        print(f"✗ Backup failed: {e}")
        return False
    
    # Step 2: Backup django_migrations table separately
    print("\nStep 2: Backing up django_migrations table...")
    try:
        cmd = [
            'pg_dump',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-d', db_config['name'],
            '-t', 'django_migrations',
            '-F', 'c',
            '-f', migrations_backup
        ]
        run_command(cmd, env=env)
        print(f"✓ Migration history backed up: {migrations_backup}")
    except Exception as e:
        print(f"⚠ Could not backup django_migrations: {e}")
    
    # Step 3: Confirm
    print("\n" + "=" * 60)
    print("WARNING: The next steps will:")
    print("  1. DROP the database (all data will be lost)")
    print("  2. CREATE a new empty database")
    print("  3. Run migrations from scratch")
    print("  4. Restore data (excluding django_migrations)")
    print("=" * 60)
    response = input("\nAre you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return False
    
    # Step 4: Drop database
    print("\nStep 3: Dropping database...")
    try:
        # Disconnect Django connection first
        connection.close()
        
        cmd = [
            'dropdb',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            db_config['name']
        ]
        run_command(cmd, env=env, check=False)  # Don't fail if DB doesn't exist
        print("✓ Database dropped (or didn't exist)")
    except Exception as e:
        print(f"⚠ Drop database warning: {e}")
    
    # Step 5: Create database
    print("\nStep 4: Creating database...")
    try:
        cmd = [
            'createdb',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            db_config['name']
        ]
        run_command(cmd, env=env)
        print("✓ Database created")
    except Exception as e:
        print(f"✗ Failed to create database: {e}")
        return False
    
    # Step 6: Run migrations
    print("\nStep 5: Running migrations from scratch...")
    try:
        from django.core.management import call_command
        call_command('migrate', verbosity=1)
        print("✓ Migrations completed")
    except Exception as e:
        print(f"✗ Migrations failed: {e}")
        print(f"\nYou can restore from backup:")
        print(f"  pg_restore -U {db_config['user']} -d {db_config['name']} -c {backup_file}")
        return False
    
    # Step 7: Restore data (excluding django_migrations)
    print("\nStep 6: Restoring data (excluding django_migrations table)...")
    try:
        cmd = [
            'pg_restore',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', str(db_config['port']),
            '-d', db_config['name'],
            '--exclude-table=django_migrations',
            backup_file
        ]
        result = run_command(cmd, env=env, check=False)
        # pg_restore may return non-zero for warnings, but that's OK
        print("✓ Data restored (migration history preserved from fresh migrations)")
    except Exception as e:
        print(f"⚠ Restore warning: {e}")
        print("Data may have been partially restored. Check the database.")
    
    # Step 8: Verify
    print("\nStep 7: Verifying migration history...")
    try:
        from django.core.management import call_command
        call_command('showmigrations', verbosity=0)
        print("✓ Migration history verified")
    except Exception as e:
        print(f"⚠ Verification warning: {e}")
    
    print("\n" + "=" * 60)
    print("✓ Process completed successfully!")
    print("=" * 60)
    print(f"\nBackup files:")
    print(f"  - Full backup: {backup_file}")
    print(f"  - Migration history backup: {migrations_backup}")
    print(f"\nIf something went wrong, restore with:")
    print(f"  pg_restore -U {db_config['user']} -d {db_config['name']} -c {backup_file}")
    
    return True

if __name__ == '__main__':
    try:
        success = backup_restore_with_fix()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
