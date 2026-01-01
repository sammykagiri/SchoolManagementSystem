"""
Custom storage backends for Railway Object Storage (S3-compatible)
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class RailwayStorage(S3Boto3Storage):
    """
    Custom S3 storage backend for Railway Object Storage
    Railway uses S3-compatible API but requires custom endpoint URL
    
    django-storages doesn't natively support custom endpoints, so we need
    to override the connection property. However, we must be careful to
    match the parent class's connection structure exactly.
    """
    def __init__(self, *args, **kwargs):
        # Set location before calling super
        self.location = getattr(settings, 'AWS_LOCATION', 'media')
        super().__init__(*args, **kwargs)
        # Initialize connection with custom endpoint after parent init
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize the connection with Railway endpoint"""
        import boto3
        from botocore.config import Config
        
        endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        if endpoint_url:
            # Create connection with custom endpoint
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
            region_name = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            
            self._connection = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                endpoint_url=endpoint_url.rstrip('/'),
                region_name=region_name,
                config=Config(signature_version='s3v4')
            )
    
    @property
    def connection(self):
        """Return connection with Railway endpoint"""
        # If we have a custom connection, use it
        if hasattr(self, '_connection') and self._connection is not None:
            return self._connection
        # Otherwise use parent's connection
        return super().connection
    
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
