from django.core.management.base import BaseCommand
from core.models import Permission


class Command(BaseCommand):
    help = 'Create or remove permissions for resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--remove',
            help='Resource type to remove (e.g., student, payment, etc.)'
        )

    def handle(self, *args, **kwargs):
        # Check if we're removing a resource
        resource_to_remove = kwargs.get('remove')
        if resource_to_remove:
            # Remove all permissions for this resource
            deleted, _ = Permission.objects.filter(resource_type=resource_to_remove).delete()
            if deleted:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully removed all permissions for resource: {resource_to_remove}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'No permissions found for resource: {resource_to_remove}'
                    )
                )
            return

        # Define all resources that need permissions
        resources = [
            'student',
            'grade',
            'term',
            'class',
            'fee_structure',
            'fee',
            'payment',
            'receipt',
            'reminder',
            'attendance',
            'subject',
            'teacher',
            'timetable',
            'exam',
            'gradebook',
            'assignment',
            'submission',
            'template',
            'email',
            'sms',
            'log',
            'dashboard',
            'report',
            'user_management',
            'role_management',
            'school_management',
            'parent',
            'parent_portal',
        ]

        # Define permission types
        permission_types = ['view', 'add', 'change', 'delete']

        # Create permissions for each resource
        for resource in resources:
            for perm_type in permission_types:
                permission, created = Permission.objects.get_or_create(
                    permission_type=perm_type,
                    resource_type=resource
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created permission: {perm_type}_{resource}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Permission already exists: {perm_type}_{resource}'
                        )
                    )

        self.stdout.write(self.style.SUCCESS('Successfully created all permissions'))

