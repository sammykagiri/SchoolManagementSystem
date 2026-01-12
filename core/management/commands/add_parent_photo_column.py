"""
Management command to add the photo column to core_parent table.
This is a safe, idempotent command that can be run multiple times.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Add photo column to core_parent table if it does not exist'

    def handle(self, *args, **options):
        self.stdout.write('Checking if photo column exists in core_parent table...')
        
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
                    self.stdout.write(
                        self.style.SUCCESS('✓ Column photo already exists in core_parent table')
                    )
                    return
                
                # Column doesn't exist, add it
                self.stdout.write('Column photo does not exist. Adding it now...')
                cursor.execute("""
                    ALTER TABLE core_parent 
                    ADD COLUMN photo VARCHAR(100) NULL
                """)
                
                self.stdout.write(
                    self.style.SUCCESS('✓ Successfully added photo column to core_parent table')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error adding photo column: {str(e)}')
            )
            raise
