"""
Django management command to check storage configuration
Usage: python manage.py check_storage
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
import os


class Command(BaseCommand):
    help = 'Check storage configuration (S3/local)'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("STORAGE CONFIGURATION CHECK"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        
        self.stdout.write("Environment Variables:")
        use_s3_env = os.environ.get('USE_S3', 'NOT SET')
        self.stdout.write(f"  USE_S3 (raw): {use_s3_env!r}")
        self.stdout.write(f"  AWS_ACCESS_KEY_ID: {'SET' if os.environ.get('AWS_ACCESS_KEY_ID') else 'NOT SET'}")
        self.stdout.write(f"  AWS_SECRET_ACCESS_KEY: {'SET' if os.environ.get('AWS_SECRET_ACCESS_KEY') else 'NOT SET'}")
        self.stdout.write(f"  AWS_STORAGE_BUCKET_NAME: {os.environ.get('AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
        self.stdout.write(f"  AWS_S3_ENDPOINT_URL: {os.environ.get('AWS_S3_ENDPOINT_URL', 'NOT SET')}")
        self.stdout.write(f"  AWS_S3_REGION_NAME: {os.environ.get('AWS_S3_REGION_NAME', 'NOT SET')}")
        self.stdout.write("")
        
        self.stdout.write("Django Settings:")
        self.stdout.write(f"  USE_S3: {getattr(settings, 'USE_S3', 'NOT SET')}")
        self.stdout.write(f"  DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET')}")
        self.stdout.write(f"  MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'NOT SET')}")
        self.stdout.write(f"  MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'NOT SET')}")
        self.stdout.write("")
        
        self.stdout.write("Storage Backend:")
        self.stdout.write(f"  Class: {default_storage.__class__.__name__}")
        self.stdout.write(f"  Module: {default_storage.__class__.__module__}")
        if hasattr(default_storage, 'bucket_name'):
            self.stdout.write(f"  Bucket: {default_storage.bucket_name}")
        if hasattr(default_storage, 'location'):
            self.stdout.write(f"  Location: {default_storage.location}")
        self.stdout.write("")
        
        self.stdout.write("=" * 60)
        if getattr(settings, 'USE_S3', False):
            self.stdout.write(self.style.SUCCESS("[OK] S3 storage is ENABLED"))
            self.stdout.write("  New uploads will go to Railway bucket")
        else:
            self.stdout.write(self.style.ERROR("[X] S3 storage is DISABLED"))
            self.stdout.write("  Files will be stored locally")
            self.stdout.write("  Set USE_S3=True in Railway environment variables")
        self.stdout.write("=" * 60)

