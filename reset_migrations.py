"""
Script to reset migrations and database.
This will:
1. Delete all migration files (except __init__.py)
2. Delete the database file
3. Create fresh migrations
4. Apply migrations

WARNING: This will delete all data in your database!
"""
import os
import shutil
import sys
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent

# Apps with migrations
APPS_WITH_MIGRATIONS = [
    'core',
    'attendance',
    'communications',
    'exams',
    'homework',
    'receivables',
    'timetable',
]

def delete_migration_files():
    """Delete all migration files except __init__.py"""
    print("=" * 60)
    print("Step 1: Deleting migration files...")
    print("=" * 60)
    
    deleted_count = 0
    for app_name in APPS_WITH_MIGRATIONS:
        migrations_dir = PROJECT_ROOT / app_name / 'migrations'
        
        if not migrations_dir.exists():
            print(f"  [WARNING] {app_name}/migrations/ does not exist, skipping...")
            continue
        
        # Delete all files except __init__.py
        for file in migrations_dir.iterdir():
            if file.is_file() and file.name != '__init__.py':
                try:
                    file.unlink()
                    print(f"  [OK] Deleted {file}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  [ERROR] Error deleting {file}: {e}")
    
    print(f"\nDeleted {deleted_count} migration files.")
    print()

def delete_database():
    """Delete the database file or drop database tables"""
    print("=" * 60)
    print("Step 2: Deleting database...")
    print("=" * 60)
    
    # Try to detect database type
    try:
        import django
        from django.conf import settings
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
        django.setup()
        
        from django.db import connection
        
        db_engine = connection.vendor  # 'sqlite', 'postgresql', etc.
        
        if db_engine == 'sqlite':
            # Delete SQLite database file
            db_files = [
                PROJECT_ROOT / 'db.sqlite3',
                PROJECT_ROOT / 'db.sqlite',
                PROJECT_ROOT / 'database.db',
            ]
            
            deleted = False
            for db_file in db_files:
                if db_file.exists():
                    try:
                        db_file.unlink()
                        print(f"  [OK] Deleted {db_file.name}")
                        deleted = True
                    except Exception as e:
                        print(f"  [ERROR] Error deleting {db_file.name}: {e}")
            
            if not deleted:
                print("  [INFO] No SQLite database file found")
        else:
            # For PostgreSQL/MySQL, drop all tables
            print(f"  [INFO] Using {db_engine.upper()} database")
            print("  [WARNING] You'll need to manually drop tables or recreate the database")
            print("  [INFO] For PostgreSQL, you can run:")
            print("     DROP SCHEMA public CASCADE;")
            print("     CREATE SCHEMA public;")
            print("     GRANT ALL ON SCHEMA public TO postgres;")
            print("     GRANT ALL ON SCHEMA public TO public;")
    except Exception as e:
        print(f"  [WARNING] Could not detect database type: {e}")
        # Fallback: try to delete SQLite files
        db_files = [
            PROJECT_ROOT / 'db.sqlite3',
            PROJECT_ROOT / 'db.sqlite',
            PROJECT_ROOT / 'database.db',
        ]
        
        for db_file in db_files:
            if db_file.exists():
                try:
                    db_file.unlink()
                    print(f"  [OK] Deleted {db_file.name}")
                except Exception as e:
                    print(f"  [ERROR] Error deleting {db_file.name}: {e}")
    
    print()

def run_makemigrations():
    """Run makemigrations"""
    print("=" * 60)
    print("Step 3: Creating fresh migrations...")
    print("=" * 60)
    
    import subprocess
    result = subprocess.run(
        [sys.executable, 'manage.py', 'makemigrations'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode != 0:
        print("  [ERROR] makemigrations failed!")
        return False
    
    print("  [OK] makemigrations completed successfully")
    print()
    return True

def run_migrate():
    """Run migrate"""
    print("=" * 60)
    print("Step 4: Applying migrations...")
    print("=" * 60)
    
    import subprocess
    result = subprocess.run(
        [sys.executable, 'manage.py', 'migrate'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode != 0:
        print("  [ERROR] migrate failed!")
        return False
    
    print("  [OK] migrate completed successfully")
    print()
    return True

def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("MIGRATION RESET SCRIPT")
    print("=" * 60)
    print("\n[WARNING] This will delete all migration files and database data!")
    print()
    
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Aborted.")
        return
    
    try:
        # Step 1: Delete migration files
        delete_migration_files()
        
        # Step 2: Delete database
        delete_database()
        
        # Step 3: Create migrations
        if not run_makemigrations():
            print("Failed at makemigrations step. Please check the errors above.")
            return
        
        # Step 4: Apply migrations
        if not run_migrate():
            print("Failed at migrate step. Please check the errors above.")
            return
        
        print("=" * 60)
        print("SUCCESS! Migrations have been reset.")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Create a superuser: python manage.py createsuperuser")
        print("  2. Load initial data (if needed): python manage.py loaddata <fixture>")
        print()
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

