from django.db import models
from django.contrib.auth.models import User
from core.models import School, Student, SchoolClass
from django.utils import timezone
from datetime import date


class Attendance(models.Model):
    """Model for student attendance records"""
    ATTENDANCE_STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='attendances', null=True, blank=True)
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='present')
    remarks = models.TextField(blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.date} - {self.get_status_display()}"

    class Meta:
        ordering = ['-date', 'student']
        unique_together = ['school', 'student', 'date']
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['date', 'status']),
        ]


class AttendanceSummary(models.Model):
    """Model for attendance summaries by term"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='attendance_summaries')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_summaries')
    term = models.ForeignKey('core.Term', on_delete=models.CASCADE, related_name='attendance_summaries')
    total_days = models.IntegerField(default=0)
    days_present = models.IntegerField(default=0)
    days_absent = models.IntegerField(default=0)
    days_late = models.IntegerField(default=0)
    days_excused = models.IntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.term} - {self.attendance_percentage}%"

    class Meta:
        unique_together = ['school', 'student', 'term']
        ordering = ['-term', 'student']
