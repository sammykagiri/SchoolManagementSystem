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
        Override url method to return Django media URL
        Files will be served through Django view since Railway buckets are private
        """
        # Return Django media URL - files will be served through Django view
        from django.urls import reverse
        # Build the media URL path
        return f"/media/{name}"
    
    def _save(self, name, content):
        """
        Override _save - parent class handles upload correctly
        Note: Railway buckets are private, so we use presigned URLs in url() method
        """
        return super()._save(name, content)
