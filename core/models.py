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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

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


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.school.name if self.school else 'No School'}"

# @receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # You may want to set a default school or handle this in registration
        UserProfile.objects.create(user=instance, school=School.objects.first())


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


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
