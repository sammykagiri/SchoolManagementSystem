"""
Quick script to check storage configuration on Railway
Run: python manage.py shell < check_storage.py
Or copy-paste into Django shell
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.core.files.storage import default_storage

print("=" * 60)
print("STORAGE CONFIGURATION CHECK")
print("=" * 60)
print()
print("Environment Variables:")
print(f"  USE_S3 (raw): {os.environ.get('USE_S3', 'NOT SET')!r}")
print(f"  AWS_ACCESS_KEY_ID: {'SET' if os.environ.get('AWS_ACCESS_KEY_ID') else 'NOT SET'}")
print(f"  AWS_SECRET_ACCESS_KEY: {'SET' if os.environ.get('AWS_SECRET_ACCESS_KEY') else 'NOT SET'}")
print(f"  AWS_STORAGE_BUCKET_NAME: {os.environ.get('AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
print(f"  AWS_S3_ENDPOINT_URL: {os.environ.get('AWS_S3_ENDPOINT_URL', 'NOT SET')}")
print(f"  AWS_S3_REGION_NAME: {os.environ.get('AWS_S3_REGION_NAME', 'NOT SET')}")
print()
print("Django Settings:")
print(f"  USE_S3: {getattr(settings, 'USE_S3', 'NOT SET')}")
print(f"  DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET')}")
print(f"  MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'NOT SET')}")
print(f"  MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'NOT SET')}")
print()
print("Storage Backend:")
print(f"  Class: {default_storage.__class__.__name__}")
print(f"  Module: {default_storage.__class__.__module__}")
if hasattr(default_storage, 'bucket_name'):
    print(f"  Bucket: {default_storage.bucket_name}")
if hasattr(default_storage, 'location'):
    print(f"  Location: {default_storage.location}")
print()
print("=" * 60)
if getattr(settings, 'USE_S3', False):
    print("✓ S3 storage is ENABLED")
    print("  New uploads will go to Railway bucket")
else:
    print("✗ S3 storage is DISABLED")
    print("  Files will be stored locally")
    print("  Set USE_S3=True in Railway environment variables")
print("=" * 60)

