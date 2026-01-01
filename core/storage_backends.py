"""
Custom storage backends for Railway Object Storage (S3-compatible)
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from urllib.parse import urljoin


class RailwayStorage(S3Boto3Storage):
    """
    Custom S3 storage backend for Railway Object Storage
    Railway uses S3-compatible API but requires custom endpoint URL
    """
    def __init__(self, *args, **kwargs):
        # Set location for media files before calling super
        self.location = getattr(settings, 'AWS_LOCATION', 'media')
        super().__init__(*args, **kwargs)
    
    def get_connection(self):
        """Get boto3 connection with Railway endpoint"""
        import boto3
        from botocore.config import Config
        
        # Get endpoint URL from settings
        endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        
        # Get credentials from settings
        access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        region_name = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        # Create S3 client with custom endpoint
        return boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url.rstrip('/') if endpoint_url else None,
            region_name=region_name,
            config=Config(signature_version='s3v4') if endpoint_url else None
        )
    
    @property
    def connection(self):
        """Override connection property to use Railway endpoint"""
        if not hasattr(self, '_connection') or self._connection is None:
            self._connection = self.get_connection()
        return self._connection
    
    def url(self, name):
        """
        Override url method to generate correct Railway storage URL
        Railway storage URLs follow: https://storage.railway.app/bucket-name/path/to/file
        """
        # Get endpoint URL and bucket name from settings
        endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
        
        if endpoint_url and bucket_name:
            # Construct Railway storage URL
            # Format: https://storage.railway.app/bucket-name/location/filename
            endpoint_url = endpoint_url.rstrip('/')
            location = getattr(self, 'location', 'media')
            
            # Build the file path: location + name
            if location:
                file_path = f"{location}/{name}".lstrip('/')
            else:
                file_path = name.lstrip('/')
            
            # Railway storage URL format
            url = f"{endpoint_url}/{bucket_name}/{file_path}"
            return url
        
        # Fallback to parent's url method
        return super().url(name)
    
    def _save(self, name, content):
        """
        Override _save - parent class should handle ACL via AWS_DEFAULT_ACL setting
        """
        # Parent's _save will use AWS_DEFAULT_ACL from settings
        return super()._save(name, content)
