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

    def __str__(self):
        return f"{self.name} - {self.academic_year}"

    class Meta:
        unique_together = ['school', 'term_number', 'academic_year']
        ordering = ['-academic_year', 'term_number']


class FeeCategory(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_categories')
    CATEGORY_CHOICES = [
        ('tuition', 'Tuition'),
        ('transport', 'Transport'),
        ('meals', 'Meals'),
        ('activities', 'Activities'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    is_optional = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ['category_type', 'name']
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - KES {self.base_fare}"

    class Meta:
        ordering = ['name']
        unique_together = ['school', 'name']


class Activity(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='activities')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    charge = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Charge per term for this activity'
    )
    is_mandatory = models.BooleanField(
        default=False,
        help_text='If checked, all students will be automatically assigned this activity unless they have an exception'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        mandatory_text = " (Mandatory)" if self.is_mandatory else ""
        return f"{self.name} - KES {self.charge}{mandatory_text}"

    class Meta:
        verbose_name_plural = "Activities"
        ordering = ['is_mandatory', 'name']
        unique_together = ['school', 'name']


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        unique_together = ['school', 'user']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.school.name})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


class Student(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    student_id = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='students')
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
    
    # Fee Preferences
    pays_meals = models.BooleanField(default=True)
    pays_activities = models.BooleanField(default=True)
    
    # Activities (ManyToMany - student can have multiple activities)
    activities = models.ManyToManyField(
        'Activity',
        related_name='students',
        blank=True,
        help_text='Activities assigned to this student'
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
        return f"{self.student_id} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class ActivityException(models.Model):
    """Model to track exceptions for mandatory activities"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='activity_exceptions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='activity_exceptions')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='exceptions')
    reason = models.TextField(help_text='Reason for exemption from this mandatory activity')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.student.full_name} - {self.activity.name} (Exception)"
    
    class Meta:
        unique_together = ['school', 'student', 'activity']
        ordering = ['student', 'activity']


class StudentMethods:
    """Helper methods for Student model"""
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

    class Meta:
        ordering = ['grade', 'first_name', 'last_name']
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

# @receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # You may want to set a default school or handle this in registration
        UserProfile.objects.create(user=instance, school=School.objects.first())


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
    class_teacher = models.CharField(max_length=100, blank=True, null=True)
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
