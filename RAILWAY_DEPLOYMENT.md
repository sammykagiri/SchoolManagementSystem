# Railway Deployment Guide for School Management System

This guide will help you deploy the School Management System to Railway platform.

## Prerequisites

1. A Railway account (sign up at https://railway.app)
2. Git repository (GitHub, GitLab, or Bitbucket)
3. Your project code committed and pushed to the repository

## Files Created for Railway Deployment

The following files have been created/updated for Railway deployment:

- `Procfile` - Defines how Railway should run your application
- `railway.json` - Railway-specific configuration
- `Dockerfile` - Container configuration for the application
- `start.sh` - Startup script that runs migrations and starts the server
- `test.sh` - Test script for debugging
- `requirements.txt` - Updated with `gunicorn` and `whitenoise`
- `school_management/settings.py` - Updated with WhiteNoise and production settings
- `school_management/urls.py` - Updated to serve media files in production

## Step-by-Step Deployment

### 1. Push Your Code to Git Repository

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push
```

### 2. Create a New Project on Railway

1. Go to https://railway.app and log in
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or your Git provider)
4. Select your repository
5. Railway will automatically detect the Dockerfile and start building

### 3. Add PostgreSQL Database

1. In your Railway project dashboard, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically create a PostgreSQL database
4. The `DATABASE_URL` environment variable will be automatically set

### 4. Configure Environment Variables

Go to your service → "Variables" tab and add the following environment variables:

#### Required Variables:

- `SECRET_KEY` - Django secret key (generate a strong random key)
  ```bash
  # You can generate one using Python:
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```

- `DEBUG` - Set to `False` for production
  ```
  DEBUG=False
  ```

- `ALLOWED_HOSTS` - Your Railway domain (Railway will provide this)
  ```
  ALLOWED_HOSTS=*.railway.app,your-custom-domain.com
  ```
  After deployment, Railway will provide your app URL. Update this with your actual domain.

- `CSRF_TRUSTED_ORIGINS` - Your Railway domain with https://
  ```
  CSRF_TRUSTED_ORIGINS=https://your-app-name.railway.app
  ```
  Update this after deployment with your actual Railway URL.

#### Optional Variables (if you're using these features):

- Email Configuration:
  - `EMAIL_HOST`
  - `EMAIL_PORT`
  - `EMAIL_USE_TLS`
  - `EMAIL_HOST_USER`
  - `EMAIL_HOST_PASSWORD`

- Celcom SMS Configuration:
  - `CELCOM_URL_SENDSMS`
  - `CELCOM_URL_GETBALANCE`
  - `CELCOM_API_KEY`
  - `CELCOM_PARTNER_ID`
  - `CELCOM_SHORTCODE`
  - `CELCOM_COMPANY_PHONE`

- M-Pesa Configuration:
  - `MPESA_CONSUMER_KEY`
  - `MPESA_CONSUMER_SECRET`
  - `MPESA_BUSINESS_SHORT_CODE`
  - `MPESA_PASSKEY`
  - `MPESA_ENVIRONMENT`

**Note:** Railway automatically sets `DATABASE_URL`, `PORT`, and `RAILWAY_ENVIRONMENT` - you don't need to set these manually.

### 5. Deploy

Railway will automatically deploy your application when you push to your connected branch. You can also trigger a deployment manually from the Railway dashboard.

### 6. Create Superuser

After deployment, you need to create a superuser to access the admin panel:

1. Go to your service in Railway dashboard
2. Click on the "Deployments" tab
3. Click on the latest deployment
4. Go to "Logs" tab
5. Click "Open Shell" or use Railway CLI:

```bash
railway run python manage.py createsuperuser
```

Or you can add this to your `start.sh` script temporarily to create a superuser automatically (not recommended for production).

### 7. Verify Deployment

1. Check the deployment logs for any errors
2. Visit your Railway app URL (provided in the dashboard)
3. Test the application functionality
4. Access the admin panel at `/admin/`

## Post-Deployment Configuration

### Update CSRF_TRUSTED_ORIGINS

After your first deployment, Railway will provide your app URL. Update the `CSRF_TRUSTED_ORIGINS` environment variable with your actual Railway URL:

```
CSRF_TRUSTED_ORIGINS=https://your-app-name.railway.app
```

### Media Files Storage

**Important:** Railway uses ephemeral storage, meaning uploaded files (like school logos, student photos) will be lost when the container restarts.

#### Option 1: Railway Volumes (Recommended for Railway)

1. Go to your Railway project dashboard
2. Click "New" → "Volume"
3. Set mount path: `/app/media`
4. Attach the volume to your service
5. Update `MEDIA_ROOT` in settings.py if needed

#### Option 2: Cloud Storage (Best for Production)

Use AWS S3, Cloudinary, or similar service for persistent media storage. This ensures files are never lost.

**Using Cloudinary (Easiest):**

1. Sign up at https://cloudinary.com (free tier available)
2. Add to `requirements.txt`:
   ```
   cloudinary
   django-cloudinary-storage
   ```
3. Update `settings.py`:
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'cloudinary_storage',
       'cloudinary',
       # ... rest of apps
   ]
   
   CLOUDINARY_STORAGE = {
       'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
       'API_KEY': config('CLOUDINARY_API_KEY'),
       'API_SECRET': config('CLOUDINARY_API_SECRET'),
   }
   
   DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
   ```
4. Add environment variables in Railway:
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`

### Custom Domain (Optional)

1. Go to your service → "Settings" → "Domains"
2. Click "Generate Domain" or add your custom domain
3. Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` with your custom domain

## Monitoring and Logs

- **Logs**: View logs in Railway dashboard → Your service → "Logs" tab
- **Metrics**: Railway provides metrics on CPU, memory, and network usage
- **Deployments**: View deployment history in "Deployments" tab

## Troubleshooting

### Deployment Fails

1. Check the build logs for errors
2. Verify all environment variables are set correctly
3. Ensure `requirements.txt` is correct and all dependencies are listed
4. Check that the `Dockerfile` is valid

### Static Files Not Loading

- WhiteNoise should handle static files automatically
- Verify `STATIC_ROOT` is set correctly
- Check that `collectstatic` runs successfully in the logs

### Database Connection Issues

- Verify `DATABASE_URL` is automatically set by Railway (check in Variables)
- Ensure PostgreSQL service is running
- Check database connection in logs

### Media Files Not Uploading/Displaying

- Remember that Railway uses ephemeral storage by default
- Consider using Railway Volumes or Cloud Storage (see above)
- Check file permissions and `MEDIA_ROOT` setting

### 500 Internal Server Error

1. Check application logs in Railway dashboard
2. Verify `DEBUG=False` is set (but check logs for detailed errors)
3. Ensure all required environment variables are set
4. Check database migrations ran successfully

## Environment Variables Reference

Here's a complete list of environment variables used by the application:

### Required:
- `SECRET_KEY` - Django secret key
- `DEBUG` - Set to `False` for production
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `CSRF_TRUSTED_ORIGINS` - Comma-separated list of trusted origins

### Automatically Set by Railway:
- `DATABASE_URL` - PostgreSQL connection string
- `PORT` - Port number (usually 8080)
- `RAILWAY_ENVIRONMENT` - Environment name

### Optional (Email):
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`

### Optional (SMS - Celcom):
- `CELCOM_URL_SENDSMS`
- `CELCOM_URL_GETBALANCE`
- `CELCOM_API_KEY`
- `CELCOM_PARTNER_ID`
- `CELCOM_SHORTCODE`
- `CELCOM_COMPANY_PHONE`

### Optional (M-Pesa):
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_BUSINESS_SHORT_CODE`
- `MPESA_PASSKEY`
- `MPESA_ENVIRONMENT`

## Additional Resources

- Railway Documentation: https://docs.railway.app
- Django Deployment Checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- WhiteNoise Documentation: http://whitenoise.evans.io/

## Notes

- The application uses WhiteNoise for serving static files in production
- Media files are served through Django (consider using cloud storage for production)
- Database migrations run automatically on each deployment
- The application uses PostgreSQL (provided by Railway)
- All security settings are configured for production (HTTPS, secure cookies, etc.)

