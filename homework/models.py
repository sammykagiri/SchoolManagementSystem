"""
Homework/Assignment models
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import School, Student, SchoolClass
from timetable.models import Subject


class Assignment(models.Model):
    """Model for homework/assignments"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='assignments')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    max_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(0)]
    )
    attachment = models.FileField(upload_to='assignments/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.subject} - {self.school_class}"

    @property
    def is_overdue(self):
        """Check if assignment is past due date"""
        from django.utils import timezone
        return timezone.now() > self.due_date

    @property
    def submission_count(self):
        """Get count of submissions"""
        return self.submissions.count()

    @property
    def pending_submissions_count(self):
        """Get count of pending submissions"""
        return self.submissions.filter(marks_obtained__isnull=True).count()

    class Meta:
        ordering = ['-due_date', 'subject']
        indexes = [
            models.Index(fields=['school_class', 'due_date']),
            models.Index(fields=['subject', 'due_date']),
        ]


class AssignmentSubmission(models.Model):
    """Model for student assignment submissions"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('late', 'Late Submission'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='assignment_submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_file = models.FileField(upload_to='submissions/', blank=True, null=True)
    submission_text = models.TextField(blank=True, help_text='Text submission (if no file uploaded)')
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"

    @property
    def percentage(self):
        """Calculate percentage marks"""
        if self.marks_obtained is not None and self.assignment.max_marks > 0:
            return (self.marks_obtained / self.assignment.max_marks) * 100
        return None

    @property
    def is_late(self):
        """Check if submission is late"""
        return self.submitted_at > self.assignment.due_date

    def save(self, *args, **kwargs):
        """Auto-update status when graded"""
        if self.marks_obtained is not None and not self.graded_at:
            from django.utils import timezone
            self.status = 'graded'
            self.graded_at = timezone.now()
        elif self.is_late and self.status == 'submitted':
            self.status = 'late'
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['school', 'assignment', 'student']
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['student', 'submitted_at']),
        ]
