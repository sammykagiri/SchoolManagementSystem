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
        Override _save to ensure files are uploaded with public-read ACL
        The parent class should handle ACL automatically via AWS_DEFAULT_ACL,
        but we ensure it's set correctly
        """
        # Parent's _save will use AWS_DEFAULT_ACL from settings
        name = super()._save(name, content)
        
        # Double-check ACL is set (parent should handle this, but ensure it)
        acl = getattr(settings, 'AWS_DEFAULT_ACL', 'public-read')
        if acl:
            try:
                # Build the full key path
                if self.location:
                    key = f"{self.location}/{name}".lstrip('/')
                else:
                    key = name.lstrip('/')
                
                # Set ACL after upload
                self.connection.put_object_acl(
                    Bucket=self.bucket_name,
                    Key=key,
                    ACL=acl
                )
            except Exception as e:
                # If setting ACL fails, log but don't fail the upload
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to set ACL for {key}: {e}")
        
        return name

