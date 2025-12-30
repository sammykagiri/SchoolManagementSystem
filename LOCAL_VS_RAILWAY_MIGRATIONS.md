# Local vs Railway Migrations

## The Issue

When you run `railway run python manage.py migrate` locally, you get an error:
```
could not translate host name "postgres.railway.internal" to address
```

This is **expected behavior** and **not a problem**!

## Why This Happens

The `DATABASE_URL` in Railway uses `postgres.railway.internal`, which is Railway's **internal network address**. This hostname:
- ✅ Works inside Railway containers (during deployment)
- ❌ Does NOT work from your local machine
- ✅ Is only accessible within Railway's network

## The Solution: Migrations Run Automatically

**You don't need to run migrations manually!** 

Migrations run automatically on Railway during each deployment via the `start.sh` script:

```bash
python manage.py migrate --noinput
```

This happens **inside Railway's network** where `postgres.railway.internal` is accessible.

## How to Verify Migrations Are Running

### Check Railway Logs

1. Go to Railway Dashboard → Your Service
2. Click "Logs" tab
3. Look for these messages during deployment:
   - "Checking migration status..."
   - "Running migrations..."
   - "Migrations completed successfully."
   - "Found X core tables: ..."

### What You Should See in Logs

If migrations are working, you'll see:
```
Checking migration status...
[ ] core.0001_initial
[ ] core.0002_...
...

Running migrations...
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, core, sessions, ...
Running migrations:
  Applying core.0001_initial... OK
  Applying core.0002_... OK
  ...
Migrations completed successfully.

Found X core tables: core_userprofile, core_school, ...
```

### If Migrations Are Failing

If you see errors in logs like:
- "Migrations failed!"
- Database connection errors
- "relation does not exist" errors

Then there's an issue that needs to be fixed. Check the error message in the logs.

## Running Migrations Locally (Optional)

If you want to run migrations locally against a **local database** (not Railway's database):

1. Create a local `.env` file (don't commit this):
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/local_db_name
   # OR use SQLite for local development:
   DATABASE_URL=sqlite:///db.sqlite3
   ```

2. Run migrations locally:
   ```bash
   python manage.py migrate
   ```

**Note:** This is for local development only. Production migrations run automatically on Railway.

## Running Migrations Against Railway Database Locally (Advanced)

If you really need to run migrations from your local machine against Railway's database (not recommended):

1. Get the **public database connection string** from Railway:
   - Go to Railway Dashboard → PostgreSQL service
   - Click "Connect" or "Variables"
   - Look for `DATABASE_URL` - it should have a public hostname (not `railway.internal`)

2. Set it temporarily in your local environment:
   ```bash
   # Windows PowerShell
   $env:DATABASE_URL="postgresql://user:password@public-hostname:port/dbname"
   python manage.py migrate
   ```

**Warning:** Be careful - you're running migrations against production data!

## Best Practice

✅ **Let migrations run automatically on Railway** during deployment
✅ **Check Railway logs** to verify they're running successfully
✅ **Run migrations locally** only against your local database for development

❌ Don't try to run `railway run python manage.py migrate` from your local machine - it won't work with internal hostnames

## Summary

The error you're seeing is **normal and expected**. Migrations run automatically on Railway during deployment, so you don't need to run them manually. Just check the Railway logs to confirm they're running successfully!


