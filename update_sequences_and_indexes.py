"""
Script to update sequences and indexes after renaming tables
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection

def update_sequences():
    """Update sequences to match new table names"""
    print("=" * 60)
    print("Updating Sequences and Indexes")
    print("=" * 60)
    print()
    
    sequences_to_rename = [
        ('payments_payment_id_seq', 'receivables_payment_id_seq'),
        ('payments_mpesapayment_id_seq', 'receivables_mpesapayment_id_seq'),
        ('payments_paymentreceipt_id_seq', 'receivables_paymentreceipt_id_seq'),
        ('payments_paymentreminder_id_seq', 'receivables_paymentreminder_id_seq'),
    ]
    
    with connection.cursor() as cursor:
        # Get all sequences that start with payments_
        cursor.execute("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public' 
            AND sequence_name LIKE 'payments_%'
        """)
        existing_sequences = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(existing_sequences)} sequences with 'payments_' prefix")
        
        renamed_count = 0
        for old_seq, new_seq in sequences_to_rename:
            if old_seq in existing_sequences:
                try:
                    # Check if new sequence exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.sequences 
                            WHERE sequence_schema = 'public' 
                            AND sequence_name = %s
                        )
                    """, [new_seq])
                    new_exists = cursor.fetchone()[0]
                    
                    if not new_exists:
                        print(f"Renaming sequence {old_seq} -> {new_seq}...")
                        cursor.execute(f'ALTER SEQUENCE "{old_seq}" RENAME TO "{new_seq}"')
                        # Update the sequence owner
                        cursor.execute(f'ALTER SEQUENCE "{new_seq}" OWNED BY "{new_seq.replace("_id_seq", "")}.id"')
                        renamed_count += 1
                        print(f"[OK] Renamed sequence {old_seq} to {new_seq}")
                    else:
                        print(f"[SKIP] {new_seq} already exists")
                except Exception as e:
                    print(f"[WARNING] Could not rename sequence {old_seq}: {e}")
        
        # Also handle any other sequences
        for seq in existing_sequences:
            if seq not in [old for old, new in sequences_to_rename]:
                new_seq = seq.replace('payments_', 'receivables_', 1)
                try:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.sequences 
                            WHERE sequence_schema = 'public' 
                            AND sequence_name = %s
                        )
                    """, [new_seq])
                    new_exists = cursor.fetchone()[0]
                    
                    if not new_exists:
                        print(f"Renaming sequence {seq} -> {new_seq}...")
                        cursor.execute(f'ALTER SEQUENCE "{seq}" RENAME TO "{new_seq}"')
                        renamed_count += 1
                        print(f"[OK] Renamed sequence {seq} to {new_seq}")
                except Exception as e:
                    print(f"[WARNING] Could not rename sequence {seq}: {e}")
        
        connection.commit()
        print()
        print(f"Updated {renamed_count} sequence(s)")
        print("=" * 60)
        print()

if __name__ == '__main__':
    try:
        update_sequences()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
