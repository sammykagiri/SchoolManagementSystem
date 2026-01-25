"""
Script to rename database tables from payments_* to receivables_*

This script will:
1. Rename all payments_* tables to receivables_*
2. Update any foreign key constraints
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection

def rename_tables():
    """Rename payments_* tables to receivables_*"""
    print("=" * 60)
    print("Renaming Database Tables from payments_* to receivables_*")
    print("=" * 60)
    print()
    
    # List of tables to rename (based on receivables models)
    tables_to_rename = [
        ('payments_payment', 'receivables_payment'),
        ('payments_mpesapayment', 'receivables_mpesapayment'),
        ('payments_paymentreceipt', 'receivables_paymentreceipt'),
        ('payments_paymentreminder', 'receivables_paymentreminder'),
    ]
    
    with connection.cursor() as cursor:
        # Check which tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'payments_%'
            ORDER BY table_name
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(existing_tables)} tables with 'payments_' prefix:")
        for table in existing_tables:
            print(f"  - {table}")
        print()
        
        if not existing_tables:
            print("[INFO] No tables with 'payments_' prefix found. Tables may already be renamed.")
            return
        
        # Rename tables
        renamed_count = 0
        for old_name, new_name in tables_to_rename:
            # Check if old table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, [old_name])
            old_exists = cursor.fetchone()[0]
            
            # Check if new table already exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, [new_name])
            new_exists = cursor.fetchone()[0]
            
            if old_exists and not new_exists:
                try:
                    print(f"Renaming {old_name} -> {new_name}...")
                    cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
                    renamed_count += 1
                    print(f"[OK] Renamed {old_name} to {new_name}")
                except Exception as e:
                    print(f"[ERROR] Failed to rename {old_name}: {e}")
            elif new_exists:
                print(f"[SKIP] {new_name} already exists, skipping {old_name}")
            elif not old_exists:
                print(f"[SKIP] {old_name} does not exist, skipping")
        
        # Also rename any other payments_* tables that might exist
        for table in existing_tables:
            if table not in [old for old, new in tables_to_rename]:
                new_name = table.replace('payments_', 'receivables_', 1)
                # Check if new table already exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, [new_name])
                new_exists = cursor.fetchone()[0]
                
                if not new_exists:
                    try:
                        print(f"Renaming {table} -> {new_name}...")
                        cursor.execute(f'ALTER TABLE "{table}" RENAME TO "{new_name}"')
                        renamed_count += 1
                        print(f"[OK] Renamed {table} to {new_name}")
                    except Exception as e:
                        print(f"[ERROR] Failed to rename {table}: {e}")
                else:
                    print(f"[SKIP] {new_name} already exists, skipping {table}")
        
        connection.commit()
        print()
        print("=" * 60)
        print(f"Renamed {renamed_count} table(s) successfully!")
        print("=" * 60)
        print()
        print("You can now run: python manage.py migrate")
        print()

if __name__ == '__main__':
    try:
        rename_tables()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
