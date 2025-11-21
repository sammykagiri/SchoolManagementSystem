"""
Signals for attendance module
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Attendance
from .services import AttendanceService
from core.models import Term


@receiver(post_save, sender=Attendance)
def update_attendance_summary_on_save(sender, instance, created, **kwargs):
    """
    Automatically update attendance summary when attendance is saved.
    """
    # Find the term that this attendance date falls within
    term = Term.objects.filter(
        school=instance.school,
        start_date__lte=instance.date,
        end_date__gte=instance.date,
        is_active=True
    ).first()
    
    if term:
        AttendanceService.update_attendance_summary(instance.student, term)


@receiver(post_delete, sender=Attendance)
def update_attendance_summary_on_delete(sender, instance, **kwargs):
    """
    Automatically update attendance summary when attendance is deleted.
    """
    # Find the term that this attendance date falls within
    term = Term.objects.filter(
        school=instance.school,
        start_date__lte=instance.date,
        end_date__gte=instance.date,
        is_active=True
    ).first()
    
    if term:
        AttendanceService.update_attendance_summary(instance.student, term)

