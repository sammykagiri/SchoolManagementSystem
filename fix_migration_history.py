"""
Script to fix migration history after renaming payments app to receivables.

This script will:
1. Mark receivables.0001_initial as applied (fake) since the tables already exist
2. Update any references in django_migrations table if needed
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

def fix_migration_history():
    """Fix the migration history after app rename"""
    print("=" * 60)
    print("Fixing Migration History After App Rename")
    print("=" * 60)
    print()
    
    with connection.cursor() as cursor:
        # Check if receivables.0001_initial is already recorded
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations 
            WHERE app = 'receivables' AND name = '0001_initial'
        """)
        receivables_exists = cursor.fetchone()[0] > 0
        
        # Check if payments.0001_initial exists (old app name)
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations 
            WHERE app = 'payments' AND name = '0001_initial'
        """)
        payments_exists = cursor.fetchone()[0] > 0
        
        print(f"Current state:")
        print(f"  - receivables.0001_initial in history: {receivables_exists}")
        print(f"  - payments.0001_initial in history: {payments_exists}")
        print()
        
        if receivables_exists:
            print("[OK] receivables.0001_initial already in migration history")
        else:
            if payments_exists:
                # Update the old payments migration to receivables
                print("Updating payments.0001_initial to receivables.0001_initial...")
                cursor.execute("""
                    UPDATE django_migrations 
                    SET app = 'receivables' 
                    WHERE app = 'payments' AND name = '0001_initial'
                """)
                print("[OK] Updated migration history")
            else:
                # Insert receivables.0001_initial as applied
                print("Adding receivables.0001_initial to migration history...")
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    SELECT 'receivables', '0001_initial', MAX(applied)
                    FROM django_migrations
                    WHERE app = 'core' AND name = '0001_initial'
                """)
                print("[OK] Added receivables.0001_initial to migration history")
        
        # Check for any other payments migrations
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations 
            WHERE app = 'payments'
        """)
        other_payments = cursor.fetchone()[0]
        
        if other_payments > 0:
            print(f"\nFound {other_payments} other migration(s) with 'payments' app name.")
            print("Updating all 'payments' migrations to 'receivables'...")
            cursor.execute("""
                UPDATE django_migrations 
                SET app = 'receivables' 
                WHERE app = 'payments'
            """)
            print("[OK] Updated all payments migrations to receivables")
        
        connection.commit()
        print()
        print("=" * 60)
        print("Migration history fixed successfully!")
        print("=" * 60)
        print()
        print("You can now run: python manage.py makemigrations")
        print()

if __name__ == '__main__':
    try:
        fix_migration_history()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
