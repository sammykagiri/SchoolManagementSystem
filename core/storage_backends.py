"""
Custom storage backends for Railway Object Storage (S3-compatible)
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class RailwayStorage(S3Boto3Storage):
    """
    Custom S3 storage backend for Railway Object Storage
    Railway uses S3-compatible API but requires custom endpoint URL
    
    Note: django-storages may support AWS_S3_ENDPOINT_URL in newer versions,
    but we override url() to ensure correct Railway URL format.
    """
    def __init__(self, *args, **kwargs):
        # Set location before calling super
        self.location = getattr(settings, 'AWS_LOCATION', 'media')
        super().__init__(*args, **kwargs)
    
    def url(self, name):
        """
        Override url method to generate correct Railway storage URL
        Railway storage URLs follow: https://storage.railway.app/bucket-name/path/to/file
        """
        endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
        
        if endpoint_url and bucket_name:
            endpoint_url = endpoint_url.rstrip('/')
            location = getattr(self, 'location', 'media')
            file_path = f"{location}/{name}".lstrip('/') if location else name.lstrip('/')
            return f"{endpoint_url}/{bucket_name}/{file_path}"
        
        return super().url(name)
