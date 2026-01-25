#!/usr/bin/env python
"""
Fix migration history inconsistency by directly updating the database.

This script bypasses Django's migration consistency check by directly
manipulating the django_migrations table.

Usage:
    python fix_migration_history_db.py
"""

import os
import sys
import django
from django.db import connection

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

def fix_migration_history():
    """Fix the inconsistent migration history"""
    with connection.cursor() as cursor:
        # Check if communications.0002_initial is recorded
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations 
            WHERE app = 'communications' AND name = '0002_initial'
        """)
        comm_0002_exists = cursor.fetchone()[0] > 0
        
        if not comm_0002_exists:
            print("✗ communications.0002_initial is not recorded. This is unexpected.")
            return False
        
        # Get the applied timestamp from communications.0002_initial
        cursor.execute("""
            SELECT applied FROM django_migrations 
            WHERE app = 'communications' AND name = '0002_initial'
        """)
        result = cursor.fetchone()
        if not result:
            print("✗ Could not find communications.0002_initial timestamp")
            return False
        
        comm_timestamp = result[0]
        # Use a timestamp BEFORE communications.0002_initial to satisfy dependency order
        from datetime import timedelta
        applied_timestamp = comm_timestamp - timedelta(seconds=1)
        print(f"Using timestamp {applied_timestamp} (before communications.0002_initial at {comm_timestamp})")
        
        # Check database backend to use appropriate syntax
        db_backend = connection.vendor
        
        # Check if receivables.0001_initial exists and update its timestamp if needed
        cursor.execute("""
            SELECT applied FROM django_migrations 
            WHERE app = 'receivables' AND name = '0001_initial'
        """)
        existing = cursor.fetchone()
        
        if existing:
            existing_timestamp = existing[0]
            print(f"Found receivables.0001_initial with timestamp: {existing_timestamp}")
            print(f"communications.0002_initial timestamp: {comm_timestamp}")
            # If existing timestamp is AFTER or EQUAL to communications.0002_initial, update it
            if existing_timestamp >= comm_timestamp:
                print(f"Updating receivables.0001_initial timestamp from {existing_timestamp} to {applied_timestamp}")
                cursor.execute("""
                    UPDATE django_migrations 
                    SET applied = %s 
                    WHERE app = 'receivables' AND name = '0001_initial'
                """, [applied_timestamp])
                # Verify the update
                cursor.execute("""
                    SELECT applied FROM django_migrations 
                    WHERE app = 'receivables' AND name = '0001_initial'
                """)
                updated = cursor.fetchone()
                if updated:
                    print(f"✓ Updated receivables.0001_initial timestamp to {updated[0]}")
                else:
                    print("✗ Failed to verify timestamp update")
            else:
                print(f"✓ receivables.0001_initial already exists with correct timestamp ({existing_timestamp} < {comm_timestamp})")
        else:
            # Insert receivables.0001_initial into migration history
            print("Inserting receivables.0001_initial into migration history...")
            try:
                if db_backend == 'postgresql':
                    # Use DO UPDATE to ensure timestamp is set correctly even if it exists
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('receivables', '0001_initial', %s)
                        ON CONFLICT (app, name) DO UPDATE SET applied = EXCLUDED.applied
                    """, [applied_timestamp])
                else:
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('receivables', '0001_initial', %s)
                    """, [applied_timestamp])
                print("✓ Inserted/Updated receivables.0001_initial")
            except Exception as e:
                # If it already exists, try to update it
                error_str = str(e).lower()
                if 'unique' in error_str or 'duplicate' in error_str or 'already exists' in error_str:
                    print("  (receivables.0001_initial already exists, updating timestamp...)")
                    cursor.execute("""
                        UPDATE django_migrations 
                        SET applied = %s 
                        WHERE app = 'receivables' AND name = '0001_initial'
                    """, [applied_timestamp])
                    print("✓ Updated receivables.0001_initial timestamp")
                else:
                    raise
        
        # Also check and insert receivables.0002 if it exists and communications depends on it
        # Check what receivables migrations exist in the filesystem
        receivables_migrations_dir = os.path.join(
            os.path.dirname(__file__), 
            'receivables', 
            'migrations'
        )
        
        if os.path.exists(receivables_migrations_dir):
            migration_files = [f for f in os.listdir(receivables_migrations_dir) 
                              if f.startswith('000') and f.endswith('.py')]
            migration_files.sort()
            
            for mig_file in migration_files:
                mig_name = mig_file.replace('.py', '')
                if mig_name == '__init__':
                    continue
                
                # Check if already recorded
                cursor.execute("""
                    SELECT applied FROM django_migrations 
                    WHERE app = 'receivables' AND name = %s
                """, [mig_name])
                existing_mig = cursor.fetchone()
                
                if not existing_mig:
                    print(f"Inserting receivables.{mig_name} into migration history...")
                    try:
                        if db_backend == 'postgresql':
                            cursor.execute("""
                                INSERT INTO django_migrations (app, name, applied)
                                VALUES ('receivables', %s, %s)
                                ON CONFLICT (app, name) DO NOTHING
                            """, [mig_name, applied_timestamp])
                        else:
                            cursor.execute("""
                                INSERT INTO django_migrations (app, name, applied)
                                VALUES ('receivables', %s, %s)
                            """, [mig_name, applied_timestamp])
                        print(f"✓ Inserted receivables.{mig_name}")
                    except Exception as e:
                        # If it already exists, that's fine
                        error_str = str(e).lower()
                        if 'unique' in error_str or 'duplicate' in error_str or 'already exists' in error_str:
                            print(f"  (receivables.{mig_name} already exists in migration history)")
                        else:
                            raise
                else:
                    existing_timestamp = existing_mig[0]
                    # Ensure this migration is also before communications.0002_initial
                    if existing_timestamp >= comm_timestamp:
                        print(f"Updating receivables.{mig_name} timestamp from {existing_timestamp} to {applied_timestamp}")
                        cursor.execute("""
                            UPDATE django_migrations 
                            SET applied = %s 
                            WHERE app = 'receivables' AND name = %s
                        """, [applied_timestamp, mig_name])
                        print(f"✓ Updated receivables.{mig_name} timestamp")
                    else:
                        print(f"  (receivables.{mig_name} already exists with correct timestamp)")
        
        connection.commit()
        print("✓ Migration history has been fixed!")
        print("\nNow you can run:")
        print("  python manage.py migrate")
        return True

if __name__ == '__main__':
    try:
        fix_migration_history()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
