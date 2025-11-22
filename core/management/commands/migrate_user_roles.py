from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, Role


class Command(BaseCommand):
    help = 'Migrate existing users from old role field to new roles ManyToMany field'

    def handle(self, *args, **options):
        profiles = UserProfile.objects.all()
        migrated_count = 0
        
        for profile in profiles:
            # If user already has roles assigned, skip
            if profile.roles.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'User {profile.user.username} already has roles assigned. Skipping.'
                    )
                )
                continue
            
            # If user has old role field set, migrate it
            if profile.role:
                try:
                    role = Role.objects.get(name=profile.role)
                    profile.roles.add(role)
                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Migrated user {profile.user.username} from role "{profile.role}" to roles ManyToMany.'
                        )
                    )
                except Role.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Role "{profile.role}" not found for user {profile.user.username}. Skipping.'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'User {profile.user.username} has no role assigned. Skipping.'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully migrated {migrated_count} user(s) from old role field to new roles ManyToMany field.'
            )
        )

