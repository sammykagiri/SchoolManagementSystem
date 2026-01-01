"""
Script to fix ACL for existing files in Railway storage
Run this in Django shell: python manage.py shell < fix_file_acl.py
Or copy-paste into Django shell
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.core.files.storage import default_storage
from core.models import School
from django.conf import settings

print("=" * 60)
print("Fixing ACL for existing files in Railway storage")
print("=" * 60)

# Check if using S3
if not getattr(settings, 'USE_S3', False):
    print("ERROR: USE_S3 is not enabled. This script only works with S3 storage.")
    exit(1)

# Get storage backend
storage = default_storage
print(f"Storage backend: {storage.__class__.__name__}")
print(f"Bucket name: {storage.bucket_name}")
print()

# Fix all school logos
schools = School.objects.filter(logo__isnull=False)
print(f"Found {schools.count()} schools with logos")
print()

for school in schools:
    if school.logo:
        file_key = school.logo.name  # e.g., 'media/school_logos/adelaide.png'
        print(f"Processing: {school.name}")
        print(f"  File key: {file_key}")
        
        try:
            # Update ACL to public-read
            storage.connection.put_object_acl(
                Bucket=storage.bucket_name,
                Key=file_key,
                ACL='public-read'
            )
            print(f"  ✓ ACL updated to public-read")
            
            # Verify the URL
            file_url = school.logo.url
            print(f"  URL: {file_url}")
            print()
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            print()

print("=" * 60)
print("Done! Try accessing the image URLs now.")
print("=" * 60)


