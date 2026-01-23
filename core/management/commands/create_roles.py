from django.core.management.base import BaseCommand
from core.models import Role, Permission, School


class Command(BaseCommand):
    help = 'Creates the default roles for the application. Can create for a specific school or all schools.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school',
            type=str,
            help='School ID or name to create roles for. If not specified, creates roles for all schools.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Create default roles for all existing schools (default behavior if no --school specified)',
        )

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

        # Determine which schools to create roles for
        schools_to_process = []
        
        if options['school']:
            # Create roles for a specific school
            school_identifier = options['school']
            try:
                # Try to find by ID first
                if school_identifier.isdigit():
                    school = School.objects.get(id=int(school_identifier))
                else:
                    # Try to find by name
                    school = School.objects.get(name=school_identifier)
                schools_to_process = [school]
            except School.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'School "{school_identifier}" not found.')
                )
                return
        else:
            # Create roles for all schools
            schools_to_process = School.objects.all()
            if not schools_to_process.exists():
                self.stdout.write(
                    self.style.WARNING('No schools found. Please create a school first.')
                )
                return
        
        # Create roles for each school
        total_created = 0
        total_updated = 0
        
        for school in schools_to_process:
            self.stdout.write(
                self.style.SUCCESS(f'\n=== Creating roles for school: {school.name} ===')
            )
            
            for role_name, config in roles_config.items():
                role, created = Role.objects.get_or_create(
                    name=role_name,
                    school=school,
                    defaults={
                        'description': config['description'],
                        'is_active': True
                    }
                )
                
                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Created role: {role.get_display_name()}')
                    )
                else:
                    total_updated += 1
                    self.stdout.write(
                        self.style.WARNING(f'  - Role already exists: {role.get_display_name()}')
                    )
                
                # Assign permissions (only if role was just created or permissions are empty)
                if created or role.permissions.count() == 0:
                    if config['permissions'] == ['*']:
                        # Super admin gets all permissions
                        all_permissions = Permission.objects.all()
                        role.permissions.set(all_permissions)
                        self.stdout.write(
                            self.style.SUCCESS(f'    → Assigned all permissions to {role.get_display_name()}')
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
                                        f'    ⚠ Permission {perm_codename} does not exist. Run create_permissions first.'
                                    )
                                )
                        
                        role.permissions.set(permission_list)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'    → Assigned {len(permission_list)} permissions to {role.get_display_name()}'
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'    → Skipped permission assignment (role already has permissions)')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully processed roles: {total_created} created, {total_updated} already existed'
            )
        )

