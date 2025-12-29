"""
Management command to create a superuser if one doesn't exist.
Uses environment variables for credentials.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates a superuser if one does not exist. Uses environment variables.'

    def handle(self, *args, **options):
        # Check if any superuser exists
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS('Superuser already exists. Skipping creation.')
            )
            return

        # Get credentials from environment variables
        username = config('DJANGO_SUPERUSER_USERNAME', default='admin')
        email = config('DJANGO_SUPERUSER_EMAIL', default='admin@example.com')
        password = config('DJANGO_SUPERUSER_PASSWORD', default='')

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    'DJANGO_SUPERUSER_PASSWORD not set. Skipping superuser creation.'
                )
            )
            return

        try:
            # Check if user with this username already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'User with username "{username}" already exists. Skipping creation.'
                    )
                )
                return
            
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created superuser: {username}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )
            # Don't raise the exception - just log it and continue
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))

