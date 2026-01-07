# Fix for 400 Bad Request Error

## The Problem

Django's `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` don't support wildcard patterns like `*.railway.app`.

## The Solution

### For ALLOWED_HOSTS

Django supports a **leading dot pattern** to allow all subdomains. Use:
- `.railway.app` (with a leading dot, NOT `*.railway.app`)

This will allow all subdomains like:
- `your-app.railway.app`
- `anything.railway.app`
- `*.up.railway.app`

### For CSRF_TRUSTED_ORIGINS

**CSRF_TRUSTED_ORIGINS does NOT support wildcards or patterns** - it needs the exact domain with `https://`.

You must use your actual Railway domain, for example:
- `https://your-app-name.railway.app`
- `https://your-app-name.up.railway.app`

## Correct Environment Variables

In Railway dashboard → Your Service → Variables, set:

```
DEBUG=False
```

```
ALLOWED_HOSTS=.railway.app,.up.railway.app
```

**IMPORTANT:** Replace `your-actual-domain.railway.app` with your REAL Railway domain from your dashboard!

```
CSRF_TRUSTED_ORIGINS=https://your-actual-domain.railway.app
```

## How to Find Your Railway Domain

1. Go to Railway dashboard
2. Click on your service
3. Go to "Settings" → "Domains"
4. You'll see your domain (e.g., `school-management-production.up.railway.app`)
5. Copy that exact domain and use it in `CSRF_TRUSTED_ORIGINS`

## Example

If your Railway domain is `school-management-production.up.railway.app`, set:

```
ALLOWED_HOSTS=.railway.app,.up.railway.app
CSRF_TRUSTED_ORIGINS=https://school-management-production.up.railway.app
```

## After Making Changes

1. Save the environment variables in Railway
2. Railway will automatically redeploy
3. The 400 error should be fixed

## Note

The code has been updated to automatically convert `*.railway.app` to `.railway.app` for ALLOWED_HOSTS, but for CSRF_TRUSTED_ORIGINS, you **must** provide the exact domain - there's no workaround for this.









