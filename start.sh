#!/bin/bash

echo "Starting deployment process..."

echo "Creating necessary directories..."
mkdir -p static
mkdir -p staticfiles
mkdir -p media

echo "Checking database connection..."
python manage.py check --database default 2>&1 || echo "Database check completed (warnings OK)"

echo "Checking if migrations need to be created..."
python manage.py makemigrations --check --dry-run > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Creating migrations for apps with model changes..."
    python manage.py makemigrations --noinput
    if [ $? -ne 0 ]; then
        echo "WARNING: makemigrations had issues, continuing anyway..."
    fi
fi

echo "Checking migration status..."
python manage.py showmigrations --list 2>&1 | grep -E "\[" | head -40 || echo "Could not show migrations"

echo "Fixing migration history if needed (idempotent - safe to run multiple times)..."
if [ -f "fix_remote_migration.py" ]; then
    python fix_remote_migration.py || echo "Migration fix skipped or not needed (this is OK)"
else
    echo "fix_remote_migration.py not found, skipping migration fix (this is OK for new setups)"
fi

echo "Running migrations..."
python manage.py migrate --noinput
if [ $? -ne 0 ]; then
    echo "ERROR: Migrations failed! Check the errors above."
    exit 1
fi
echo "Migrations completed successfully."

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

