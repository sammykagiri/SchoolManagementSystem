from django.db import models
from django.contrib.auth.models import User
from core.models import School, SchoolClass, Grade
from django.core.validators import MinValueValidator, MaxValueValidator


class Subject(models.Model):
    """Model for school subjects"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

    class Meta:
        unique_together = [
            ('school', 'name'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'code'],
                condition=~models.Q(code=''),
                name='unique_school_code_when_provided'
            ),
        ]
        ordering = ['name']


class Teacher(models.Model):
    """Model for teachers"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='teachers')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, related_name='teacher_profile', null=True, blank=True)
    employee_id = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    specialization = models.CharField(max_length=200, blank=True, help_text='Subject specialization or area of expertise')
    photo = models.ImageField(upload_to='teacher_photos/', blank=True, null=True)
    subjects = models.ManyToManyField(Subject, related_name='teachers', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['first_name', 'last_name']
        unique_together = ['school', 'employee_id']


class TimeSlot(models.Model):
    """Model for time slots in a day"""
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='time_slots')
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    period_number = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=50, blank=True)  # e.g., "Lunch", "Recess"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.is_break:
            return f"{self.get_day_display()} - {self.break_name} ({self.start_time} - {self.end_time})"
        return f"{self.get_day_display()} - Period {self.period_number} ({self.start_time} - {self.end_time})"

    class Meta:
        unique_together = ['school', 'day', 'period_number']
        ordering = ['day', 'period_number']


class Timetable(models.Model):
    """Model for class timetables"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='timetables')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='timetables')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetables')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetables')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='timetables')
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school_class} - {self.subject} - {self.time_slot}"

    class Meta:
        unique_together = ['school', 'school_class', 'time_slot']
        ordering = ['school_class', 'time_slot__day', 'time_slot__period_number']
