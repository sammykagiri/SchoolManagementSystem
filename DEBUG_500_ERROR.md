# Debugging 500 Server Error on Railway

A 500 Internal Server Error means something went wrong on the server. Here's how to debug it:

## Step 1: Check Railway Logs

1. Go to Railway Dashboard → Your Service
2. Click on "Logs" tab
3. Look for error messages, stack traces, or exceptions
4. Common errors to look for:
   - Database connection errors
   - Missing environment variables
   - Import errors
   - Static files collection errors
   - Migration errors

## Step 2: Common Causes and Fixes

### 1. Database Connection Issues

**Symptoms:**
- `django.db.utils.OperationalError`
- `connection refused`
- `database does not exist`

**Fix:**
- Verify PostgreSQL service is running in Railway
- Check that `DATABASE_URL` is automatically set (Railway sets this when you add PostgreSQL)
- Ensure migrations ran successfully

### 2. Missing Environment Variables

**Symptoms:**
- `decouple.UndefinedValueError`
- `SECRET_KEY` errors
- Configuration errors

**Fix:**
Verify these required variables are set:
- `SECRET_KEY` - Must be set!
- `DEBUG=False` - For production
- `ALLOWED_HOSTS` - Your Railway domain
- `CSRF_TRUSTED_ORIGINS` - Your Railway URL with https://

### 3. Static Files Issues

**Symptoms:**
- `WhiteNoise` errors
- Static files not found

**Fix:**
- Check that `collectstatic` ran successfully in logs
- Verify `STATIC_ROOT` is set correctly
- Ensure `whitenoise` is in `requirements.txt`

### 4. Application Errors

**Symptoms:**
- Python exceptions in logs
- Import errors
- Model errors

**Fix:**
- Check the full stack trace in logs
- Verify all dependencies are in `requirements.txt`
- Check for syntax errors in your code

### 5. Superuser Creation Errors

**Symptoms:**
- Errors during startup
- Database constraint violations

**Fix:**
- The superuser creation command now handles errors gracefully
- If it fails, the app will still start (it just won't create the superuser)
- Check logs for specific error messages

## Step 3: Enable Debug Mode Temporarily

To see detailed error messages, temporarily set:

```
DEBUG=True
```

**⚠️ WARNING:** Only do this temporarily to debug! Never leave DEBUG=True in production.

This will show you the full error page with stack traces.

## Step 4: Check Specific Areas

### Database Migrations

Check if migrations completed:
```bash
# In Railway logs, look for:
"Migrations completed successfully."
```

If migrations failed, fix the migration issues first.

### Static Files Collection

Check if static files were collected:
```bash
# In Railway logs, look for:
"Static files collected successfully."
```

### Application Startup

Check if Gunicorn started:
```bash
# In Railway logs, look for:
"Starting gunicorn..."
```

## Step 5: Test Database Connection

If you suspect database issues, you can test the connection by adding this to `start.sh` temporarily:

```bash
echo "Testing database connection..."
python manage.py check --database default
```

## Step 6: Common Error Messages and Solutions

### "No such table: django_migrations"
**Solution:** Run migrations: `python manage.py migrate`

### "SECRET_KEY must not be empty"
**Solution:** Set `SECRET_KEY` environment variable

### "DisallowedHost at /"
**Solution:** Update `ALLOWED_HOSTS` with your Railway domain

### "CSRF verification failed"
**Solution:** Update `CSRF_TRUSTED_ORIGINS` with your Railway URL

### "ModuleNotFoundError"
**Solution:** Add missing package to `requirements.txt`

### "OperationalError: could not connect to server"
**Solution:** Check PostgreSQL service is running and `DATABASE_URL` is set

## Step 7: Get Detailed Error Information

If you can't see the error in logs, add this to your `start.sh` before starting gunicorn:

```bash
echo "Running Django system check..."
python manage.py check --deploy
```

This will check for common deployment issues.

## Step 8: Check Railway Service Status

1. Go to Railway Dashboard
2. Check if your service shows as "Running" (green)
3. Check resource usage (CPU, Memory)
4. Verify PostgreSQL service is also running

## Quick Checklist

- [ ] PostgreSQL service is running
- [ ] `DATABASE_URL` is set (automatic with Railway PostgreSQL)
- [ ] `SECRET_KEY` is set
- [ ] `DEBUG=False` (or `DEBUG=True` temporarily for debugging)
- [ ] `ALLOWED_HOSTS` includes your Railway domain
- [ ] `CSRF_TRUSTED_ORIGINS` includes your Railway URL with https://
- [ ] All required packages are in `requirements.txt`
- [ ] Migrations completed successfully
- [ ] Static files collected successfully
- [ ] Gunicorn started successfully

## Still Having Issues?

1. **Share the error logs** from Railway (copy the relevant error messages)
2. **Check the exact error** - look for the first error in the stack trace
3. **Verify environment variables** - make sure all required ones are set
4. **Test locally** - try running the app locally with the same environment variables

## Getting Help

When asking for help, provide:
1. The exact error message from Railway logs
2. The stack trace (if available)
3. Your environment variables (without sensitive values like passwords)
4. The step where it fails (migrations, static files, startup, etc.)









