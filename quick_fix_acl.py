# Quick fix for Access Denied error
# Copy and paste this entire block into Django shell: python manage.py shell

from django.core.files.storage import default_storage
from core.models import School

storage = default_storage
print(f"Bucket: {storage.bucket_name}")

# Fix Adelaide school logo
school = School.objects.filter(name__icontains="adelaide").first()
if school and school.logo:
    file_key = school.logo.name
    print(f"Fixing: {file_key}")
    
    try:
        storage.connection.put_object_acl(
            Bucket=storage.bucket_name,
            Key=file_key,
            ACL='public-read'
        )
        print(f"✓ Success! ACL updated to public-read")
        print(f"URL: {school.logo.url}")
        print("Try accessing the URL now - it should work!")
    except Exception as e:
        print(f"✗ Error: {e}")
else:
    print("School not found or has no logo")


