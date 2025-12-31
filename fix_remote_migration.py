"""
Script to fix inconsistent migration history in remote database.
This marks core.0002_initial as applied in the database.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection
from django.utils import timezone

def fix_migration_history():
    """Fix the migration history by marking core.0002_initial as applied"""
    print("=" * 60)
    print("Fixing Migration History")
    print("=" * 60)
    
    with connection.cursor() as cursor:
        # Check if core.0002_initial is already recorded
        if connection.vendor == 'postgresql':
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = %s AND name = %s",
                ['core', '0002_initial']
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = ? AND name = ?",
                ['core', '0002_initial']
            )
        
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            # Insert the migration record
            applied_time = timezone.now()
            
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['core', '0002_initial', applied_time]
                )
            else:
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
                    ['core', '0002_initial', applied_time]
                )
            
            print("[OK] Successfully marked core.0002_initial as applied")
        else:
            print("[INFO] core.0002_initial is already marked as applied")
        
        # Also check and fix attendance.0002_initial if needed
        if connection.vendor == 'postgresql':
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = %s AND name = %s",
                ['attendance', '0002_initial']
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = ? AND name = ?",
                ['attendance', '0002_initial']
            )
        
        exists_attendance = cursor.fetchone()[0] > 0
        
        if not exists_attendance:
            applied_time = timezone.now()
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['attendance', '0002_initial', applied_time]
                )
            else:
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
                    ['attendance', '0002_initial', applied_time]
                )
            print("[OK] Successfully marked attendance.0002_initial as applied")
        else:
            print("[INFO] attendance.0002_initial is already marked as applied")
        
        # Check communications.0002_initial
        if connection.vendor == 'postgresql':
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = %s AND name = %s",
                ['communications', '0002_initial']
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = ? AND name = ?",
                ['communications', '0002_initial']
            )
        
        exists_communications = cursor.fetchone()[0] > 0
        
        if not exists_communications:
            applied_time = timezone.now()
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['communications', '0002_initial', applied_time]
                )
            else:
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
                    ['communications', '0002_initial', applied_time]
                )
            print("[OK] Successfully marked communications.0002_initial as applied")
        else:
            print("[INFO] communications.0002_initial is already marked as applied")
    
    print("\n" + "=" * 60)
    print("Migration history fixed!")
    print("=" * 60)
    print("\nYou can now run: python manage.py migrate")

if __name__ == '__main__':
    try:
        fix_migration_history()
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


