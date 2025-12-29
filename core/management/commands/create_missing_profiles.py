"""
Management command to create UserProfile for users who don't have one.
This is useful for fixing existing users after enabling the profile creation signal.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, School


class Command(BaseCommand):
    help = 'Create UserProfile for users who do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id',
            type=int,
            help='ID of the school to assign to users without profiles. If not provided, uses the first school.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating profiles',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        school_id = options.get('school_id')
        
        # Get the school to assign
        if school_id:
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'School with ID {school_id} does not exist.')
                )
                return
        else:
            school = School.objects.first()
            if not school:
                self.stdout.write(
                    self.style.ERROR('No schools found. Please create a school first.')
                )
                return
        
        # Find users without profiles
        users_without_profiles = User.objects.filter(profile__isnull=True)
        count = users_without_profiles.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles.')
            )
            return
        
        self.stdout.write(
            f'Found {count} user(s) without profiles.'
        )
        if school:
            self.stdout.write(
                f'Will assign school: {school.name} (ID: {school.id})'
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN - No profiles will be created.')
            )
            for user in users_without_profiles:
                self.stdout.write(f'  - Would create profile for: {user.username} ({user.email})')
            return
        
        # Create profiles
        created_count = 0
        for user in users_without_profiles:
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'school': school}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created profile for: {user.username}')
                )
            else:
                self.stdout.write(
                    f'Profile already exists for: {user.username}'
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created {created_count} profile(s).'
            )
        )
