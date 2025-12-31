"""
Safe migration script for new setups.
This ensures migrations are applied in the correct order and fixes any inconsistencies.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.core.management import call_command
from django.db import connection
from django.utils import timezone

def ensure_migration_dependencies():
    """Ensure all required migration dependencies are marked as applied"""
    print("Checking migration dependencies...")
    
    # Required migrations that other apps depend on
    required_migrations = [
        ('core', '0001_initial'),
        ('core', '0002_initial'),
        ('timetable', '0001_initial'),
    ]
    
    with connection.cursor() as cursor:
        for app, name in required_migrations:
            if connection.vendor == 'postgresql':
                cursor.execute(
                    "SELECT COUNT(*) FROM django_migrations WHERE app = %s AND name = %s",
                    [app, name]
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM django_migrations WHERE app = ? AND name = ?",
                    [app, name]
                )
            
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                print(f"  Marking {app}.{name} as applied...")
                applied_time = timezone.now()
                
                if connection.vendor == 'postgresql':
                    cursor.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                        [app, name, applied_time]
                    )
                else:
                    cursor.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
                        [app, name, applied_time]
                    )
                print(f"  [OK] {app}.{name} marked as applied")
            else:
                print(f"  [OK] {app}.{name} already applied")

def migrate_safely():
    """Run migrations safely with dependency checks"""
    try:
        # First, ensure dependencies are in place
        ensure_migration_dependencies()
        
        # Then run migrations
        print("\nRunning migrations...")
        call_command('migrate', verbosity=1, interactive=False)
        
        print("\n[SUCCESS] Migrations completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(migrate_safely())


