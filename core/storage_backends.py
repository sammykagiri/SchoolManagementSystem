"""
Custom storage backends for Railway Object Storage (S3-compatible)
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class RailwayStorage(S3Boto3Storage):
    """
    Custom S3 storage backend for Railway Object Storage
    Railway uses S3-compatible API but requires custom endpoint URL
    """
    def __init__(self, *args, **kwargs):
        # Set location for media files before calling super
        self.location = getattr(settings, 'AWS_LOCATION', 'media')
        super().__init__(*args, **kwargs)
    
    @property
    def connection(self):
        """Override connection property to use Railway endpoint"""
        if not hasattr(self, '_connection') or self._connection is None:
            import boto3
            from botocore.config import Config
            
            # Get endpoint URL from settings
            endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
            
            # Get credentials
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
            region_name = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            
            # Create S3 client with custom endpoint if provided
            if endpoint_url:
                self._connection = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    endpoint_url=endpoint_url.rstrip('/'),
                    region_name=region_name,
                    config=Config(signature_version='s3v4')
                )
            else:
                # Fallback to parent's connection method
                return super().connection
        
        return self._connection

