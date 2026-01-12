#!/usr/bin/env python
"""
Quick fix script to add photo column to core_parent table.
Run this directly on Railway if migrations aren't working.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection

def add_photo_column():
    """Add photo column to core_parent table if it doesn't exist"""
    try:
        with connection.cursor() as cursor:
            # Check if column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND table_name = 'core_parent' 
                AND column_name = 'photo'
            """)
            
            if cursor.fetchone():
                print("✓ Column photo already exists in core_parent table")
                return True
            
            # Column doesn't exist, add it
            print("Column photo does not exist. Adding it now...")
            cursor.execute("""
                ALTER TABLE core_parent 
                ADD COLUMN photo VARCHAR(100) NULL
            """)
            
            print("✓ Successfully added photo column to core_parent table")
            return True
            
    except Exception as e:
        print(f"✗ Error adding photo column: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = add_photo_column()
    sys.exit(0 if success else 1)
