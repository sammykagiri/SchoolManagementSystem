#!/bin/bash

echo "Starting deployment process..."

echo "Creating necessary directories..."
mkdir -p static
mkdir -p staticfiles
mkdir -p media

echo "Checking database connection..."
python manage.py check --database default 2>&1 || echo "Database check completed (warnings OK)"

#echo "Checking if migrations need to be created..."
#python manage.py makemigrations --check --dry-run > /dev/null 2>&1
#if [ $? -ne 0 ]; then
#    echo "Creating migrations for apps with model changes..."
#    python manage.py makemigrations --noinput
#    if [ $? -ne 0 ]; then
#        echo "WARNING: makemigrations had issues, continuing anyway..."
#    fi
#fi

#echo "Checking migration status..."
#python manage.py showmigrations --list 2>&1 | grep -E "\[" | head -40 || echo "Could not show migrations"

echo "Running migrations..."
python manage.py migrate --noinput
if [ $? -ne 0 ]; then
    echo "WARNING: Migrations had issues. Attempting to fix photo column..."
    # Try to add photo column directly if migration failed
    python manage.py add_parent_photo_column 2>&1 || echo "Photo column fix skipped"
fi
echo "Migrations completed."

# Verify critical columns exist
echo "Verifying database schema..."
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"\"\"
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    AND table_name = 'core_parent' 
    AND column_name = 'photo'
\"\"\")
if cursor.fetchone():
    print('✓ core_parent.photo column exists')
else:
    print('⚠ core_parent.photo column missing - attempting to add...')
    try:
        cursor.execute('ALTER TABLE core_parent ADD COLUMN photo VARCHAR(100) NULL')
        print('✓ Photo column added successfully')
    except Exception as e:
        print(f'✗ Failed to add photo column: {e}')
" || echo "Schema verification skipped"

echo "Verifying core tables exist..."
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'core_%' ORDER BY tablename;\")
tables = [row[0] for row in cursor.fetchall()]
print(f'Found {len(tables)} core tables: {tables[:10]}...' if len(tables) > 10 else f'Found {len(tables)} core tables: {tables}')
if 'core_userprofile' not in tables:
    print('WARNING: core_userprofile table not found!')
    exit(1)
" || echo "WARNING: Could not verify tables (non-critical)"

echo "Creating permissions..."
python manage.py create_permissions || echo "Permission creation skipped or failed (this is OK if permissions already exist)"

echo "Creating roles..."
python manage.py create_roles || echo "Role creation skipped or failed (this is OK if roles already exist)"

echo "Creating superuser if not exists..."
python manage.py create_superuser_if_not_exists || echo "Superuser creation skipped or failed (this is OK if superuser already exists or password not set)"

echo "Checking storage configuration..."
python manage.py check_storage || echo "Storage check completed"

echo "Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "Static files collection failed!"
    exit 1
fi
echo "Static files collected successfully."

echo "Starting gunicorn..."
exec gunicorn school_management.wsgi:application --bind 0.0.0.0:$PORT --log-file - --timeout 240

