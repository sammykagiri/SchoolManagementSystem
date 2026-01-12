from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver


class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#0d6efd', help_text='Primary color for the school theme (hex code)')
    secondary_color = models.CharField(max_length=7, blank=True, null=True, help_text='Secondary color for the school theme (hex code)')
    use_color_scheme = models.BooleanField(default=False, help_text='Apply this color scheme to the application')
    use_secondary_on_headers = models.BooleanField(default=False, help_text='Apply secondary color to headers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_school_name'),
            models.UniqueConstraint(fields=['email'], name='unique_school_email'),
        ]


class Grade(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='grades')
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        unique_together = ['school', 'name']


class Term(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='terms')
    TERM_CHOICES = [
        ('1', 'First Term'),
        ('2', 'Second Term'),
        ('3', 'Third Term'),
    ]
    
    name = models.CharField(max_length=50)
    term_number = models.CharField(max_length=1, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9)  # e.g., "2023-2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_display_name(self):
        """Get the display name for the term, generating it from term_number if name is empty"""
        if self.name:
            return self.name
        term_name_map = {'1': 'First Term', '2': 'Second Term', '3': 'Third Term'}
        return term_name_map.get(self.term_number, f'Term {self.term_number}')
    
    def __str__(self):
        return f"{self.get_display_name()} - {self.academic_year}"

    class Meta:
        unique_together = ['school', 'term_number', 'academic_year']
        ordering = ['-academic_year', 'term_number']


class FeeCategoryType(models.Model):
    """Model for managing fee category types dynamically"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_category_types')
    name = models.CharField(max_length=100, help_text='Name of the fee category type (e.g., Tuition, Transport)')
    code = models.CharField(max_length=50, help_text='Short code for the type (e.g., tuition, transport)')
    description = models.TextField(blank=True, help_text='Optional description for this category type')
    is_active = models.BooleanField(default=True, help_text='Whether this category type is active and can be used')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Fee Category Type"
        verbose_name_plural = "Fee Category Types"
        ordering = ['name']
        unique_together = ['school', 'code']


class FeeCategory(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_categories')
    
    name = models.CharField(max_length=100)
    category_type = models.ForeignKey(FeeCategoryType, on_delete=models.PROTECT, related_name='fee_categories')
    description = models.TextField(blank=True)
    is_optional = models.BooleanField(default=False, help_text='If checked, this fee is optional and students can opt in/out')
    apply_by_default = models.BooleanField(default=False, help_text='If checked, optional fees will be selected by default when adding/editing students')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ['category_type__name', 'name']
        unique_together = ['school', 'name', 'category_type']


class TransportRoute(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='transport_routes')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    base_fare = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    active_start_date = models.DateField(null=True, blank=True, help_text='Start date when this route becomes active')
    active_end_date = models.DateField(null=True, blank=True, help_text='End date when this route becomes inactive')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_currently_active(self):
        """Check if route is currently active based on dates and is_active flag"""
        from django.utils import timezone
        today = timezone.now().date()
        
        if not self.is_active:
            return False
        
        if self.active_start_date and today < self.active_start_date:
            return False
        
        if self.active_end_date and today > self.active_end_date:
            return False
        
        return True

    def __str__(self):
        return f"{self.name} - KES {self.base_fare}"

    class Meta:
        ordering = ['name']
        unique_together = ['school', 'name']


class ParentManager(models.Manager):
    """Custom manager that defers photo field to avoid errors when column doesn't exist"""
    _photo_column_exists = None
    
    @classmethod
    def reset_photo_column_check(cls):
        """Reset the cached photo column check (useful after migrations)"""
        cls._photo_column_exists = None
    
    def get_queryset(self):
        # Cache the check result to avoid querying database on every call
        if ParentManager._photo_column_exists is None:
            from django.db import connection
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        AND table_name = 'core_parent' 
                        AND column_name = 'photo'
                    """)
                    ParentManager._photo_column_exists = cursor.fetchone() is not None
            except:
                # If check fails, assume column doesn't exist (safer)
                ParentManager._photo_column_exists = False
        
        queryset = super().get_queryset()
        if not ParentManager._photo_column_exists:
            # Defer photo field if column doesn't exist
            queryset = queryset.defer('photo')
        return queryset


class Parent(models.Model):
    """Parent/guardian profile linked to a user account."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='parent_profile'
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='parents'
    )
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('email', 'Email'),
        ],
        default='phone'
    )
    # Photo
    photo = models.ImageField(upload_to='parent_photos/', blank=True, null=True, help_text='Parent photo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom manager that defers photo field if column doesn't exist
    objects = ParentManager()

    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        unique_together = ['school', 'user']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.school.name})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


class ParentVerification(models.Model):
    """Model to store verification codes for parent phone/email updates"""
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='verifications')
    verification_type = models.CharField(
        max_length=20,
        choices=[
            ('phone', 'Phone'),
            ('email', 'Email'),
        ]
    )
    verification_code = models.CharField(max_length=10)
    new_value = models.CharField(max_length=255, help_text='New phone number or email address')
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['parent', 'verification_code', 'is_verified']),
        ]

    def __str__(self):
        return f"{self.parent.full_name} - {self.verification_type} - {self.verification_code}"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class Student(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    student_id = models.CharField(max_length=20)
    upi = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        unique=True,
        help_text='11-digit NEMIS / UPI number issued by the Ministry of Education',
        verbose_name='NEMIS/UPI Number'
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, help_text='Middle or other names (optional)')
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='students')
    school_class = models.ForeignKey(
        'SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        help_text='Assigned class (optional)'
    )
    admission_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # Contact Information
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=15)
    parent_email = models.EmailField(blank=True)
    address = models.TextField()
    
    # Transport Information
    transport_route = models.ForeignKey(
        TransportRoute, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students'
    )
    uses_transport = models.BooleanField(default=False)
    
    # Fee Preferences (legacy fields for backward compatibility)
    pays_meals = models.BooleanField(default=True)
    pays_activities = models.BooleanField(default=True)
    
    # Optional fee categories (many-to-many for flexible optional fee management)
    optional_fee_categories = models.ManyToManyField(
        FeeCategory,
        related_name='students_opted_in',
        blank=True,
        help_text='Optional fee categories this student has opted into'
    )
    
    # Photo
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True, help_text='Student photo')

    # Linked parent accounts (one parent can have multiple children)
    parents = models.ManyToManyField(
        'Parent',
        related_name='children',
        blank=True,
        help_text='Linked parent user accounts'
    )

    # Linked student user account (optional)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profile',
        help_text='Link to student user account (optional)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        name_parts = [self.first_name]
        if self.middle_name:
            name_parts.append(self.middle_name)
        name_parts.append(self.last_name)
        return f"{self.student_id} - {' '.join(name_parts)}"

    @property
    def full_name(self):
        name_parts = [self.first_name]
        if self.middle_name:
            name_parts.append(self.middle_name)
        name_parts.append(self.last_name)
        return ' '.join(name_parts)
    
    def get_school_classes(self):
        """Get all school classes for this student's grade"""
        return self.grade.school_classes.filter(is_active=True)
    
    def get_current_class(self):
        """Get the first active class for this student's grade (if multiple, returns first)"""
        classes = self.get_school_classes()
        return classes.first() if classes.exists() else None
    
    def get_subjects(self):
        """Get all subjects for this student's grade classes"""
        from timetable.models import Subject
        classes = self.get_school_classes()
        subject_ids = set()
        for school_class in classes:
            # Get subjects from timetables for this class
            timetables = school_class.timetables.filter(is_active=True)
            for timetable in timetables:
                subject_ids.add(timetable.subject_id)
        return Subject.objects.filter(id__in=subject_ids, school=self.school, is_active=True)
    
    def clean(self):
        """Validate UPI field"""
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        if self.upi:
            # Remove any whitespace
            self.upi = self.upi.strip()
            
            # Check if it contains only digits
            if not self.upi.isdigit():
                raise ValidationError({
                    'upi': 'UPI number must contain only digits.'
                })
            
            # Check if it's exactly 11 characters
            if len(self.upi) != 11:
                raise ValidationError({
                    'upi': 'UPI number must be exactly 11 digits.'
                })

    class Meta:
        ordering = ['grade', 'first_name', 'middle_name', 'last_name']
        unique_together = ['school', 'student_id']


class FeeStructure(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_structures')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='fee_structures')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='fee_structures')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='fee_structures')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.grade} - {self.term} - {self.fee_category} - KES {self.amount}"

    class Meta:
        unique_together = ['school', 'grade', 'term', 'fee_category']
        ordering = ['grade', 'term', 'fee_category']


class StudentFee(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='student_fees')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_fees')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='student_fees')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='student_fees')
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.fee_category} - {self.term}"

    @property
    def balance(self):
        return self.amount_charged - self.amount_paid

    @property
    def is_overdue(self):
        from django.utils import timezone
        return not self.is_paid and timezone.now().date() > self.due_date

    class Meta:
        unique_together = ['school', 'student', 'term', 'fee_category']
        ordering = ['student', 'term', 'fee_category']


class Role(models.Model):
    """Model to store available roles"""
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('school_admin', 'School Admin'),
        ('teacher', 'Teacher'),
        ('accountant', 'Accountant'),
        ('parent', 'Parent'),
        ('student', 'Student'),
    ]
    
    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    permissions = models.ManyToManyField('Permission', related_name='roles', blank=True)
    description = models.TextField(blank=True, help_text='Description of this role')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.get_display_name()
    
    def get_display_name(self):
        """Get the human-readable name for this role"""
        return dict(self.ROLE_CHOICES).get(self.name, self.name)
    
    def has_permission(self, permission_type, resource_type):
        """Check if this role has a specific permission"""
        return self.permissions.filter(
            permission_type=permission_type,
            resource_type=resource_type
        ).exists()
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'


class Permission(models.Model):
    """Model to store individual permissions"""
    PERMISSION_TYPES = [
        ('view', 'View'),
        ('add', 'Add'),
        ('change', 'Change'),
        ('delete', 'Delete'),
    ]
    
    RESOURCE_TYPES = [
        ('student', 'Student'),
        ('grade', 'Grade'),
        ('term', 'Term'),
        ('class', 'Class'),
        ('fee_structure', 'Fee Structure'),
        ('fee', 'Fee'),
        ('payment', 'Payment'),
        ('receipt', 'Receipt'),
        ('reminder', 'Reminder'),
        ('attendance', 'Attendance'),
        ('subject', 'Subject'),
        ('teacher', 'Teacher'),
        ('timetable', 'Timetable'),
        ('exam', 'Exam'),
        ('gradebook', 'Gradebook'),
        ('assignment', 'Assignment'),
        ('submission', 'Submission'),
        ('template', 'Template'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('log', 'Communication Log'),
        ('dashboard', 'Dashboard'),
        ('report', 'Report'),
        ('user_management', 'User Management'),
        ('role_management', 'Role Management'),
        ('school_management', 'School Management'),
    ]
    
    permission_type = models.CharField(max_length=20, choices=PERMISSION_TYPES)
    resource_type = models.CharField(max_length=30, choices=RESOURCE_TYPES)
    
    class Meta:
        unique_together = ('permission_type', 'resource_type')
        ordering = ['resource_type', 'permission_type']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return f"{self.get_permission_type_display()} {self.get_resource_type_display()}"
    
    @property
    def codename(self):
        """Generate a codename like 'add_student', 'view_payment', etc."""
        return f"{self.permission_type}_{self.resource_type}"


class UserProfile(models.Model):
    """User profile with role-based permissions"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    roles = models.ManyToManyField(Role, related_name='user_profiles', blank=True)
    # Keep role field for backward compatibility (will be deprecated)
    role = models.CharField(max_length=20, null=True, blank=True, help_text='Deprecated: Use roles instead')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        roles_display = ', '.join([role.get_display_name() for role in self.roles.all()])
        if not roles_display and self.role:
            # Fallback to old role field if no roles assigned
            roles_display = self.get_role_display() if hasattr(self, 'get_role_display') else self.role
        return f"{self.user.username} - {roles_display or 'No Roles'} - {self.school.name if self.school else 'No School'}"
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return self.roles.filter(name=role_name).exists()
    
    def get_roles_display(self):
        """Get comma-separated list of role display names"""
        return ', '.join([role.get_display_name() for role in self.roles.all()])
    
    @property
    def roles_list(self):
        """Return a list of role names for this user"""
        return [role.name for role in self.roles.all()]
    
    def has_permission(self, permission_type, resource_type):
        """Check if the user has a specific permission through any of their roles"""
        # Superusers have all permissions
        if self.user.is_superuser:
            return True
        
        # Check if any of the user's roles have this permission
        for role in self.roles.all():
            if role.has_permission(permission_type, resource_type):
                return True
        
        return False
    
    # Backward compatibility properties (check roles, fallback to old role field)
    @property
    def is_super_admin(self):
        if self.has_role('super_admin'):
            return True
        # Fallback to old role field
        return self.role == 'super_admin' if self.role else False
    
    @property
    def is_school_admin(self):
        if self.has_role('school_admin'):
            return True
        # Fallback to old role field
        return self.role == 'school_admin' if self.role else False
    
    @property
    def is_teacher(self):
        if self.has_role('teacher'):
            return True
        # Fallback to old role field
        return self.role == 'teacher' if self.role else False
    
    @property
    def is_accountant(self):
        if self.has_role('accountant'):
            return True
        # Fallback to old role field
        return self.role == 'accountant' if self.role else False
    
    @property
    def is_parent(self):
        if self.has_role('parent'):
            return True
        # Fallback to old role field
        return self.role == 'parent' if self.role else False
    
    @property
    def is_student(self):
        if self.has_role('student'):
            return True
        # Fallback to old role field
        return self.role == 'student' if self.role else False

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile when a User is created"""
    if created:
        # Only create if profile doesn't exist
        if not hasattr(instance, 'profile'):
            # Get the first school or None if no schools exist
            default_school = School.objects.first()
            UserProfile.objects.get_or_create(
                user=instance,
                defaults={'school': default_school}
            )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Only save if profile exists and avoid triggering during migrations
    if hasattr(instance, 'profile'):
        try:
            instance.profile.save()
        except Exception:
            # Ignore errors during migrations or if profile doesn't exist yet
            pass


class SchoolClass(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_classes')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='school_classes')
    name = models.CharField(max_length=100)
    class_teacher = models.ForeignKey(
        'timetable.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes_taught',
        help_text='Assigned class teacher'
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('school', 'grade', 'name')
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'

    def __str__(self):
        return f"{self.name} ({self.grade.name})"


class AcademicYear(models.Model):
    """Represents an academic year (e.g., 2023-2024)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='academic_years')
    name = models.CharField(max_length=50, help_text='e.g., "2023-2024"')
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False, help_text='Whether this academic year is currently active')
    is_current = models.BooleanField(default=False, help_text='The current academic year (only one can be current)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['school', 'name']
        ordering = ['-start_date']
        verbose_name = 'Academic Year'
        verbose_name_plural = 'Academic Years'

    def __str__(self):
        return f"{self.name} ({self.school.name})"

    def clean(self):
        """Validate academic year dates"""
        from django.core.exceptions import ValidationError
        if self.start_date >= self.end_date:
            raise ValidationError('End date must be after start date.')

    def save(self, *args, **kwargs):
        """Ensure only one academic year is marked as current"""
        self.full_clean()
        if self.is_current:
            # Unset other current academic years for this school
            AcademicYear.objects.filter(school=self.school, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class Section(models.Model):
    """Represents a section within a class (e.g., Section A, B, Morning, Afternoon)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sections')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=50, help_text='e.g., "A", "B", "Morning", "Afternoon"')
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Maximum number of students (optional)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['school_class', 'name']
        ordering = ['school_class__grade__name', 'school_class__name', 'name']
        verbose_name = 'Section'
        verbose_name_plural = 'Sections'

    def __str__(self):
        return f"{self.school_class.name} - {self.name}"

    @property
    def current_enrollment_count(self):
        """Get current number of active enrollments in this section"""
        from django.utils import timezone
        current_year = AcademicYear.objects.filter(school=self.school, is_current=True).first()
        if not current_year:
            return 0
        return self.enrollments.filter(
            academic_year=current_year,
            status='active'
        ).count()

    @property
    def is_full(self):
        """Check if section is at capacity"""
        if self.capacity is None:
            return False
        return self.current_enrollment_count >= self.capacity


class StudentClassEnrollment(models.Model):
    """Pivot table tracking student enrollment in classes across academic years"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retained', 'Retained'),
        ('promoted', 'Promoted'),
        ('graduated', 'Graduated'),
        ('left', 'Left School'),
        ('dropped', 'Dropped Out'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='enrollments')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    roll_number = models.PositiveIntegerField(null=True, blank=True, help_text='Roll number in class')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    enrollment_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Additional notes about this enrollment')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'academic_year']
        ordering = ['roll_number', 'student__first_name', 'student__last_name']
        verbose_name = 'Student Class Enrollment'
        verbose_name_plural = 'Student Class Enrollments'
        indexes = [
            models.Index(fields=['academic_year', 'status']),
            models.Index(fields=['grade', 'academic_year']),
            models.Index(fields=['school_class', 'section']),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name} ({self.grade.name})"

    def clean(self):
        """Validate enrollment data"""
        from django.core.exceptions import ValidationError
        # Ensure section belongs to school_class if both are provided
        if self.section and self.school_class and self.section.school_class != self.school_class:
            raise ValidationError('Section must belong to the selected school class.')
        # Ensure school_class belongs to grade if both are provided
        if self.school_class and self.school_class.grade != self.grade:
            raise ValidationError('School class must belong to the selected grade.')


class PromotionLog(models.Model):
    """Audit trail for student promotions"""
    PROMOTION_TYPE_CHOICES = [
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('bulk', 'Bulk'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='promotion_logs')
    from_academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='promotions_from')
    to_academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='promotions_to')
    promoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='promotions')
    promotion_type = models.CharField(max_length=20, choices=PROMOTION_TYPE_CHOICES, default='automatic')
    total_students = models.PositiveIntegerField(help_text='Total students processed')
    promoted_count = models.PositiveIntegerField(default=0)
    retained_count = models.PositiveIntegerField(default=0)
    graduated_count = models.PositiveIntegerField(default=0)
    left_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text='Additional notes about this promotion')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promotion Log'
        verbose_name_plural = 'Promotion Logs'

    def __str__(self):
        return f"Promotion: {self.from_academic_year.name} → {self.to_academic_year.name} ({self.created_at.date()})"
