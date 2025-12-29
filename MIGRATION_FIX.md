# Fix for "relation does not exist" Error

## The Problem

You're seeing errors like:
```
ERROR: relation "core_userprofile" does not exist
```

This means the database tables haven't been created yet - migrations haven't run successfully.

## Solution

### Step 1: Check Migration Status

The startup script now shows migration status. Check Railway logs to see:
1. Which migrations are pending
2. Which migrations have been applied
3. If there are any migration errors

### Step 2: Force Migrations to Run

If migrations aren't running automatically, you have several options:

#### Option A: Using Railway CLI (Recommended)

1. Install Railway CLI (if not installed):
   ```bash
   npm i -g @railway/cli
   ```
   Or using other methods: https://docs.railway.app/develop/cli

2. Login to Railway:
   ```bash
   railway login
   ```

3. Link to your project:
   ```bash
   railway link
   ```

4. Run migrations:
   ```bash
   railway run python manage.py migrate
   ```

#### Option B: Add Temporary Migration Check to start.sh

Add this temporarily to your `start.sh` before starting gunicorn to debug:

```bash
echo "Verifying migrations applied..."
python manage.py migrate --run-syncdb  # This ensures all tables exist
```

#### Option C: Use Railway's Web Terminal (if available)

Some Railway plans have a web terminal:
1. Go to Railway Dashboard → Your Service
2. Look for "Terminal" or "Shell" tab
3. Run: `python manage.py migrate`

#### Option D: Trigger Redeploy

Sometimes a fresh deployment fixes migration issues:
1. Go to Railway Dashboard → Your Service
2. Click "Settings" → "Redeploy" or "Deploy"
3. Watch the logs to ensure migrations run successfully

### Step 3: Check Database Connection

Ensure PostgreSQL is properly connected:
- Go to Railway Dashboard
- Verify PostgreSQL service is running (green status)
- Check that `DATABASE_URL` environment variable is set (Railway sets this automatically)

### Step 4: Verify All Migrations Are Applied

Using Railway CLI:
```bash
railway run python manage.py showmigrations
```

Or add temporarily to `start.sh` to see in logs:
```bash
echo "Migration status:"
python manage.py showmigrations
```

All migrations should show `[X]` (checked) not `[ ]` (unchecked).

### Step 5: If Database Is Empty

If the database is completely empty, you may need to:

1. **Check if PostgreSQL service exists:**
   - Go to Railway Dashboard
   - Ensure you have a PostgreSQL service added
   - If not, add one: "New" → "Database" → "Add PostgreSQL"

2. **Verify DATABASE_URL is set:**
   - Go to your service → "Variables"
   - Check that `DATABASE_URL` exists (Railway sets this automatically when you add PostgreSQL)

3. **Reset and rerun migrations:**
   If needed, you can reset the database (⚠️ THIS WILL DELETE ALL DATA):
   ```bash
   # Using Railway CLI:
   railway run python manage.py migrate core zero  # Unapply core migrations
   railway run python manage.py migrate  # Reapply all migrations
   ```
   
   Or temporarily add to `start.sh` before gunicorn starts:
   ```bash
   echo "Resetting and rerunning migrations..."
   python manage.py migrate core zero || true  # Unapply (ignore errors)
   python manage.py migrate  # Reapply all migrations
   ```

## Common Issues

### Issue 1: Migrations Run But Tables Don't Exist

**Cause:** Database connection issue or migrations failed silently

**Fix:**
- Check Railway logs for migration errors
- Verify database connection
- Ensure PostgreSQL service is running

### Issue 2: "No such table: django_migrations"

**Cause:** Database is completely new/empty

**Fix:**
- Run `python manage.py migrate` manually
- This creates the django_migrations table first, then creates all app tables

### Issue 3: Migration Conflicts

**Cause:** Database state doesn't match migration files

**Fix:**
- Check migration status with `python manage.py showmigrations`
- Look for migrations marked as applied but tables missing
- You may need to fake migrations or reset the database

### Issue 4: Permission Errors

**Cause:** Database user doesn't have CREATE TABLE permissions

**Fix:**
- Railway PostgreSQL should have proper permissions automatically
- If issues persist, check Railway PostgreSQL settings

## Prevention

The startup script (`start.sh`) now:
1. Shows migration status before running migrations
2. Runs migrations with proper error handling
3. Exits if migrations fail (prevents app from starting with broken database)

## Next Steps After Fixing

Once migrations run successfully:
1. Create a superuser (if not already created automatically)
2. Access the admin panel at `/admin/`
3. Verify all models are accessible

## Getting Help

If migrations still fail:
1. Check Railway logs for the full error message
2. Run `python manage.py showmigrations` to see which migrations are applied
3. Check if there are any migration files in `core/migrations/` that might be causing issues
4. Share the error message from logs for further assistance

