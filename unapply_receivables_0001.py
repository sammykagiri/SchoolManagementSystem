#!/usr/bin/env python
"""
Unapply receivables.0001_initial so it can be run properly.

This removes receivables.0001_initial from migration history,
allowing it to be run fresh and create the tables.

Usage:
    python unapply_receivables_0001.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection

def unapply_receivables_0001():
    """Unapply receivables.0001_initial if tables don't exist"""
    with connection.cursor() as cursor:
        # Check if 0001_initial is marked as applied
        cursor.execute("""
            SELECT COUNT(*) FROM django_migrations 
            WHERE app = 'receivables' AND name = '0001_initial'
        """)
        is_applied = cursor.fetchone()[0] > 0
        
        if not is_applied:
            # Already unapplied, nothing to do
            return True
        
        # Check if tables from 0001_initial actually exist
        expected_tables = [
            'receivables_payment',
            'receivables_mpesapayment',
            'receivables_paymentreceipt',
            'receivables_paymentreminder',
        ]
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = ANY(%s)
        """, [expected_tables])
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        # Check if all expected tables exist
        all_tables_exist = all(table in existing_tables for table in expected_tables)
        
        if all_tables_exist:
            # Tables exist, migration is correctly applied
            return True
        
        # Tables don't exist but migration is marked as applied - unapply it and all dependent migrations
        print("⚠ receivables.0001_initial is marked as applied but tables don't exist")
        print("  Unapplying receivables.0001_initial and all subsequent receivables migrations...")
        
        # Unapply all receivables migrations (they all depend on 0001_initial)
        cursor.execute("""
            DELETE FROM django_migrations 
            WHERE app = 'receivables'
        """)
        connection.commit()
        
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"✓ Unapplied {deleted} receivables migration(s) (removed from migration history)")
            print("  Migrations will run fresh and create the tables")
            return True
        else:
            print("✗ Failed to unapply receivables migrations")
            return False

if __name__ == '__main__':
    try:
        success = unapply_receivables_0001()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
