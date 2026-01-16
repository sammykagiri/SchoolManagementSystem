from django.core.management.base import BaseCommand
from core.models import Role, Permission


class Command(BaseCommand):
    help = 'Creates the default roles for the application'

    def handle(self, *args, **options):
        # Define default roles with their permissions
        roles_config = {
            'super_admin': {
                'description': 'Super Administrator with full system access',
                'permissions': ['*']  # All permissions
            },
            'school_admin': {
                'description': 'School Administrator with full school access',
                'permissions': [
                    'view_student', 'add_student', 'change_student', 'delete_student',
                    'view_grade', 'add_grade', 'change_grade', 'delete_grade',
                    'view_term', 'add_term', 'change_term', 'delete_term',
                    'view_class', 'add_class', 'change_class', 'delete_class',
                    'view_fee_structure', 'add_fee_structure', 'change_fee_structure', 'delete_fee_structure',
                    'view_fee', 'add_fee', 'change_fee', 'delete_fee',
                    'view_payment', 'add_payment', 'change_payment', 'delete_payment',
                    'view_receipt', 'add_receipt', 'change_receipt', 'delete_receipt',
                    'view_reminder', 'add_reminder', 'change_reminder', 'delete_reminder',
                    'view_attendance', 'add_attendance', 'change_attendance', 'delete_attendance',
                    'view_subject', 'add_subject', 'change_subject', 'delete_subject',
                    'view_teacher', 'add_teacher', 'change_teacher', 'delete_teacher',
                    'view_timetable', 'add_timetable', 'change_timetable', 'delete_timetable',
                    'view_exam', 'add_exam', 'change_exam', 'delete_exam',
                    'view_gradebook', 'add_gradebook', 'change_gradebook', 'delete_gradebook',
                    'view_assignment', 'add_assignment', 'change_assignment', 'delete_assignment',
                    'view_submission', 'add_submission', 'change_submission', 'delete_submission',
                    'view_template', 'add_template', 'change_template', 'delete_template',
                    'view_email', 'add_email', 'change_email', 'delete_email',
                    'view_sms', 'add_sms', 'change_sms', 'delete_sms',
                    'view_log', 'add_log', 'change_log', 'delete_log',
                    'view_dashboard', 'view_report',
                    'view_user_management', 'add_user_management', 'change_user_management',
                ]
            },
            'teacher': {
                'description': 'Teacher with access to students, attendance, exams, and assignments',
                'permissions': [
                    'view_student', 'change_student',
                    'view_attendance', 'add_attendance', 'change_attendance',
                    'view_subject', 'view_teacher',
                    'view_timetable', 'add_timetable', 'change_timetable',
                    'view_exam', 'add_exam', 'change_exam',
                    'view_gradebook', 'add_gradebook', 'change_gradebook',
                    'view_assignment', 'add_assignment', 'change_assignment', 'delete_assignment',
                    'view_submission', 'add_submission', 'change_submission',
                    'view_template', 'view_email', 'add_email', 'view_sms', 'add_sms',
                    'view_dashboard',
                ]
            },
            'accountant': {
                'description': 'Accountant with access to fees and payments',
                'permissions': [
                    'view_student',
                    'view_fee_structure', 'add_fee_structure', 'change_fee_structure',
                    'view_fee', 'add_fee', 'change_fee',
                    'view_payment', 'add_payment', 'change_payment',
                    'view_receipt', 'add_receipt', 'change_receipt',
                    'view_reminder', 'add_reminder', 'change_reminder',
                    'view_dashboard', 'view_report',
                ]
            },
            'parent': {
                'description': 'Parent with view access to their children\'s information',
                'permissions': [
                    'view_student',
                    'view_attendance',
                    'view_gradebook',
                    'view_assignment', 'view_submission',
                    'view_dashboard',
                    'view_parent_portal',
                ]
            },
            'student': {
                'description': 'Student with view access to their own information',
                'permissions': [
                    'view_student',
                    'view_attendance',
                    'view_gradebook',
                    'view_assignment', 'add_submission',
                    'view_dashboard',
                ]
            },
        }

        # Create roles
        for role_name, config in roles_config.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'description': config['description'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created role: {role.get_display_name()}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Role already exists: {role.get_display_name()}')
                )
            
            # Assign permissions
            if config['permissions'] == ['*']:
                # Super admin gets all permissions
                all_permissions = Permission.objects.all()
                role.permissions.set(all_permissions)
                self.stdout.write(
                    self.style.SUCCESS(f'  Assigned all permissions to {role.get_display_name()}')
                )
            else:
                # Assign specific permissions
                permission_list = []
                for perm_codename in config['permissions']:
                    perm_type, resource_type = perm_codename.split('_', 1)
                    try:
                        permission = Permission.objects.get(
                            permission_type=perm_type,
                            resource_type=resource_type
                        )
                        permission_list.append(permission)
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Permission {perm_codename} does not exist. Run create_permissions first.'
                            )
                        )
                
                role.permissions.set(permission_list)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Assigned {len(permission_list)} permissions to {role.get_display_name()}'
                    )
                )

        self.stdout.write(self.style.SUCCESS('Successfully created all roles'))

