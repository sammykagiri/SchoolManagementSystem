"""
Custom storage backends for Railway Object Storage (S3-compatible)
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
import logging

logger = logging.getLogger(__name__)


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
    
    def _get_s3_client(self):
        """
        Get or create an S3 client for generating presigned URLs
        The connection property returns a Resource, but we need a Client
        """
        if not hasattr(self, '_s3_client'):
            import boto3
            
            endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
            region_name = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                endpoint_url=endpoint_url.rstrip('/') if endpoint_url else None,
                region_name=region_name,
            )
        return self._s3_client
    
    def url(self, name):
        """
        Override url method to generate presigned URLs for Railway storage
        Railway buckets are private by default, so we use presigned URLs for public access
        """
        # Build the file key
        file_key = self._normalize_name(name)
        
        # Generate presigned URL (expires in 1 year = 31536000 seconds)
        # This allows direct access to the file without making the bucket public
        try:
            client = self._get_s3_client()
            url = client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_key,
                },
                ExpiresIn=31536000  # 1 year expiration
            )
            return url
        except Exception as e:
            # Fallback to direct URL if presigned URL generation fails
            logger.warning(f"Failed to generate presigned URL for {name}: {e}")
            endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
            bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
            
            if endpoint_url and bucket_name:
                endpoint_url = endpoint_url.rstrip('/')
                location = getattr(self, 'location', 'media')
                file_path = f"{location}/{name}".lstrip('/') if location else name.lstrip('/')
                return f"{endpoint_url}/{bucket_name}/{file_path}"
            
            return super().url(name)
    
    def _save(self, name, content):
        """
        Override _save - parent class handles upload correctly
        Note: Railway buckets are private, so we use presigned URLs in url() method
        """
        return super()._save(name, content)
