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
    
    def _save(self, name, content):
        """
        Override _save to ensure files are uploaded with public-read ACL
        """
        # Call parent's _save method first - this handles the actual upload
        name = super()._save(name, content)
        
        # Ensure ACL is set to public-read for Railway
        # The parent's _save may have already set ACL, but we ensure it's correct
        try:
            acl = getattr(settings, 'AWS_DEFAULT_ACL', 'public-read')
            if acl:
                # Get the file key - django-storages stores relative to location
                # name from parent is relative to location (e.g., 'school_logos/file.png')
                # We need the full key path for S3
                file_key = self._normalize_name(name)  # This handles location prefix
                
                # Set ACL after upload
                self.connection.put_object_acl(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    ACL=acl
                )
                logger.debug(f"ACL set to {acl} for {file_key}")
        except Exception as e:
            # Log but don't fail the upload - ACL might already be set by parent
            logger.warning(f"Failed to set ACL for {name}: {e}")
        
        return name
