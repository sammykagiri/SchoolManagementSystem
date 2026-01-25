#!/usr/bin/env python
"""
Check if migration tables exist and fix migration history accordingly.

This script:
1. Checks which receivables tables actually exist in the database
2. Compares with migration history
3. Fakes migrations that should have created existing tables
4. Or marks migrations as unapplied if tables don't exist

Usage:
    python check_and_fix_missing_tables.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection

def check_tables_exist():
    """Check which receivables tables exist"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'receivables_%'
            ORDER BY table_name
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
    return existing_tables

def check_migration_history():
    """Check which receivables migrations are marked as applied"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, applied 
            FROM django_migrations 
            WHERE app = 'receivables'
            ORDER BY applied, name
        """)
        applied_migrations = {row[0]: row[1] for row in cursor.fetchall()}
    return applied_migrations

def fix_migration_history():
    """Fix migration history based on actual table existence"""
    print("=" * 60)
    print("Checking Receivables Tables and Migration History")
    print("=" * 60)
    print()
    
    # Check what tables exist
    existing_tables = check_tables_exist()
    print(f"Existing receivables tables: {existing_tables}")
    print()
    
    # Check migration history
    applied_migrations = check_migration_history()
    print(f"Applied migrations: {list(applied_migrations.keys())}")
    print()
    
    # Expected tables from 0001_initial
    expected_tables_0001 = [
        'receivables_payment',
        'receivables_mpesapayment',
        'receivables_paymentreceipt',
        'receivables_paymentreminder',
    ]
    
    # Check if 0001 tables exist
    tables_from_0001_exist = all(table in existing_tables for table in expected_tables_0001)
    
    if not tables_from_0001_exist:
        print("✗ Tables from receivables.0001_initial do NOT exist!")
        print("  Expected tables:", expected_tables_0001)
        print("  Existing tables:", existing_tables)
        print()
        
        if '0001_initial' in applied_migrations:
            print("⚠ receivables.0001_initial is marked as applied but tables don't exist!")
            print()
            print("Options:")
            print("  1. Unapply receivables.0001_initial (mark as not applied)")
            print("  2. Actually run receivables.0001_initial (create tables)")
            print()
            
            choice = input("What would you like to do? (1=unapply, 2=run, 3=cancel): ")
            
            if choice == '1':
                # Unapply 0001_initial
                with connection.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM django_migrations 
                        WHERE app = 'receivables' AND name = '0001_initial'
                    """)
                    connection.commit()
                print("✓ Unapplied receivables.0001_initial")
                print("  Now you can run: python manage.py migrate receivables")
                return True
            elif choice == '2':
                # Try to run 0001_initial
                print("Attempting to run receivables.0001_initial...")
                from django.core.management import call_command
                try:
                    call_command('migrate', 'receivables', '0001_initial', verbosity=1)
                    print("✓ Successfully ran receivables.0001_initial")
                    return True
                except Exception as e:
                    print(f"✗ Failed to run migration: {e}")
                    return False
            else:
                print("Cancelled.")
                return False
        else:
            print("✓ receivables.0001_initial is not marked as applied (correct state)")
            print("  You can run: python manage.py migrate receivables")
            return True
    else:
        print("✓ Tables from receivables.0001_initial exist")
        
        # Check if 0001_initial is marked as applied
        if '0001_initial' not in applied_migrations:
            print("⚠ Tables exist but receivables.0001_initial is NOT marked as applied!")
            print("  Fake-applying receivables.0001_initial...")
            
            from django.utils import timezone
            from datetime import timedelta
            
            # Get earliest migration timestamp or use current time
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT MIN(applied) FROM django_migrations
                """)
                result = cursor.fetchone()
                if result and result[0]:
                    applied_timestamp = result[0] - timedelta(seconds=1)
                else:
                    applied_timestamp = timezone.now() - timedelta(days=1)
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('receivables', '0001_initial', %s)
                """, [applied_timestamp])
                connection.commit()
            print(f"✓ Faked receivables.0001_initial with timestamp {applied_timestamp}")
            return True
        else:
            print("✓ receivables.0001_initial is correctly marked as applied")
            return True

if __name__ == '__main__':
    try:
        success = fix_migration_history()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
