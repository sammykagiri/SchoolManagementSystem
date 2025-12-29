# Fix for Missing Migrations Error

## The Problem

You're seeing this error in Railway logs:
```
Your models in app(s): 'attendance', 'communications', 'core', 'exams', 'homework', 'payments', 'timetable' have changes that are not yet reflected in a migration, and so won't be applied.
Run 'manage.py makemigrations' to make new migrations, and then re-run 'manage.py migrate' to apply them.
```

This means migration files haven't been created for your models.

## Solution

### Option 1: Create Migrations Locally and Commit (Recommended)

This is the proper way to handle migrations:

1. **Create migrations locally:**
   ```bash
   python manage.py makemigrations
   ```

2. **Verify migrations were created:**
   ```bash
   # Check that migration files exist in each app's migrations folder
   ls core/migrations/
   ls attendance/migrations/
   ls communications/migrations/
   # etc.
   ```

3. **Commit and push migrations:**
   ```bash
   git add */migrations/*.py
   git commit -m "Add migrations for all apps"
   git push
   ```

4. **Railway will automatically deploy** with the migrations included

### Option 2: Auto-Create Migrations in Production (Quick Fix)

I've updated `start.sh` to automatically create migrations if they're missing. This will:

1. Check if migrations need to be created
2. Run `makemigrations` if needed
3. Then run `migrate` to apply them

**Note:** While this works, it's better to commit migrations to your repository so they're version-controlled.

## What I've Updated

The `start.sh` script now:
1. Checks if migrations need to be created
2. Runs `makemigrations` if there are uncommitted model changes
3. Then runs `migrate` to apply all migrations

## After Fixing

Once migrations are created and applied:
1. ✅ All database tables will be created
2. ✅ The `core_userprofile` table will exist
3. ✅ Your application will start without 500 errors
4. ✅ All models will work correctly

## Verify Migrations Are Applied

After deployment, check Railway logs for:
```
Creating migrations for apps with model changes...
Migrations for 'core': ...
Running migrations...
  Applying core.0001_initial... OK
  Applying core.0002_... OK
  ...
Migrations completed successfully.
Found X core tables: core_userprofile, core_school, ...
```

## Best Practice

For production deployments:
- ✅ Create migrations locally
- ✅ Commit migrations to git
- ✅ Push to repository
- ✅ Let Railway deploy with migrations included

This ensures:
- Migrations are version-controlled
- All environments use the same migrations
- You have a clear history of database changes

## If You Still Have Issues

If migrations still aren't being created or applied:

1. **Check that migration files are committed:**
   ```bash
   git status
   # Make sure */migrations/*.py files are tracked
   ```

2. **Check Railway logs** for any errors during makemigrations or migrate

3. **Verify database connection** is working (migrations need database access)

4. **Check for migration conflicts** - if migrations were partially applied, you may need to reset

