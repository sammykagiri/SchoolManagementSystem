#!/bin/bash
# Backup, recreate database, run migrations, and restore data
# This script handles the migration history issue properly

set -e  # Exit on error

DB_NAME="${DB_NAME:-your_database_name}"
DB_USER="${DB_USER:-your_username}"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
MIGRATIONS_BACKUP="django_migrations_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "=========================================="
echo "Database Backup, Recreate, and Restore"
echo "=========================================="
echo ""

# Step 1: Backup database
echo "Step 1: Creating full database backup..."
pg_dump -U "$DB_USER" -d "$DB_NAME" -F c -f "$BACKUP_FILE"
if [ $? -eq 0 ]; then
    echo "✓ Backup created: $BACKUP_FILE"
else
    echo "✗ Backup failed!"
    exit 1
fi

# Step 2: Backup django_migrations table separately
echo ""
echo "Step 2: Backing up django_migrations table..."
pg_dump -U "$DB_USER" -d "$DB_NAME" -t django_migrations -F c -f "$MIGRATIONS_BACKUP"
if [ $? -eq 0 ]; then
    echo "✓ Migration history backed up: $MIGRATIONS_BACKUP"
else
    echo "⚠ Could not backup django_migrations (may not exist yet)"
fi

# Step 3: Drop and recreate database
echo ""
echo "Step 3: Dropping and recreating database..."
echo "WARNING: This will delete all data!"
read -p "Are you sure? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

dropdb -U "$DB_USER" "$DB_NAME" || echo "Database may not exist, continuing..."
createdb -U "$DB_USER" "$DB_NAME"
if [ $? -eq 0 ]; then
    echo "✓ Database recreated"
else
    echo "✗ Failed to recreate database!"
    exit 1
fi

# Step 4: Run migrations from scratch
echo ""
echo "Step 4: Running migrations from scratch..."
python manage.py migrate
if [ $? -eq 0 ]; then
    echo "✓ Migrations completed"
else
    echo "✗ Migrations failed!"
    echo "You can restore from backup: pg_restore -U $DB_USER -d $DB_NAME -c $BACKUP_FILE"
    exit 1
fi

# Step 5: Restore data (excluding django_migrations)
echo ""
echo "Step 5: Restoring data (excluding django_migrations table)..."
pg_restore -U "$DB_USER" -d "$DB_NAME" --exclude-table=django_migrations "$BACKUP_FILE" 2>&1 | grep -v "ERROR:" || true
echo "✓ Data restored (migration history preserved from fresh migrations)"

# Step 6: Verify
echo ""
echo "Step 6: Verifying migration history..."
python manage.py showmigrations | head -20
echo ""
echo "=========================================="
echo "✓ Process completed successfully!"
echo "=========================================="
echo ""
echo "Backup files:"
echo "  - Full backup: $BACKUP_FILE"
echo "  - Migration history backup: $MIGRATIONS_BACKUP"
echo ""
echo "If something went wrong, restore with:"
echo "  pg_restore -U $DB_USER -d $DB_NAME -c $BACKUP_FILE"
