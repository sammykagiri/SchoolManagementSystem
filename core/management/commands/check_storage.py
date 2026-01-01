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
        # Django 5.2+ uses STORAGES instead of DEFAULT_FILE_STORAGE
        storages = getattr(settings, 'STORAGES', {})
        default_storage_backend = storages.get('default', {}).get('BACKEND', 'NOT SET') if storages else getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET')
        self.stdout.write(f"  Default Storage Backend: {default_storage_backend}")
        self.stdout.write(f"  MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'NOT SET')}")
        self.stdout.write(f"  MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'NOT SET')}")
        self.stdout.write("")
        
        self.stdout.write("Storage Backend:")
        self.stdout.write(f"  Class: {default_storage.__class__.__name__}")
        self.stdout.write(f"  Module: {default_storage.__class__.__module__}")
        
        # Try to import and instantiate the configured storage backend
        storages = getattr(settings, 'STORAGES', {})
        configured_storage = storages.get('default', {}).get('BACKEND') if storages else getattr(settings, 'DEFAULT_FILE_STORAGE', None)
        if configured_storage:
            try:
                from django.utils.module_loading import import_string
                StorageClass = import_string(configured_storage)
                test_instance = StorageClass()
                self.stdout.write(f"  Configured storage class: {configured_storage}")
                self.stdout.write(f"  Can import: YES")
                if hasattr(test_instance, 'bucket_name'):
                    self.stdout.write(f"  Bucket: {test_instance.bucket_name}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ERROR importing {configured_storage}: {e}"))
                self.stdout.write(self.style.WARNING("  Django fell back to FileSystemStorage"))
        
        if hasattr(default_storage, 'bucket_name'):
            self.stdout.write(f"  Current bucket: {default_storage.bucket_name}")
        try:
            if hasattr(default_storage, 'location'):
                self.stdout.write(f"  Current location: {default_storage.location}")
        except (TypeError, AttributeError):
            pass  # location might fail if MEDIA_ROOT is None
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

