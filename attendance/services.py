"""
Service classes for attendance module business logic
"""
from django.db.models import Count, Q
from django.utils import timezone
from .models import Attendance, AttendanceSummary
from core.models import Student, Term


class AttendanceService:
    """Service for attendance-related business logic"""
    
    @staticmethod
    def update_attendance_summary(student, term):
        """
        Update or create attendance summary for a student in a term.
        This should be called whenever attendance is marked or updated.
        """
        attendances = Attendance.objects.filter(
            school=student.school,
            student=student,
            date__gte=term.start_date,
            date__lte=term.end_date
        )
        
        total_days = attendances.count()
        days_present = attendances.filter(status='present').count()
        days_absent = attendances.filter(status='absent').count()
        days_late = attendances.filter(status='late').count()
        days_excused = attendances.filter(status='excused').count()
        
        attendance_percentage = (days_present / total_days * 100) if total_days > 0 else 0
        
        summary, created = AttendanceSummary.objects.update_or_create(
            school=student.school,
            student=student,
            term=term,
            defaults={
                'total_days': total_days,
                'days_present': days_present,
                'days_absent': days_absent,
                'days_late': days_late,
                'days_excused': days_excused,
                'attendance_percentage': attendance_percentage,
            }
        )
        
        return summary
    
    @staticmethod
    def generate_summaries_for_term(school, term):
        """
        Generate attendance summaries for all active students in a term.
        """
        students = Student.objects.filter(school=school, is_active=True)
        created_count = 0
        
        for student in students:
            # Check if summary exists before updating
            existing = AttendanceSummary.objects.filter(
                school=school,
                student=student,
                term=term
            ).exists()
            summary = AttendanceService.update_attendance_summary(student, term)
            if not existing:
                created_count += 1
        
        return created_count
    
    @staticmethod
    def get_student_attendance_stats(student, term=None):
        """
        Get attendance statistics for a student.
        If term is provided, stats are for that term only.
        """
        attendances = Attendance.objects.filter(
            school=student.school,
            student=student
        )
        
        if term:
            attendances = attendances.filter(
                date__gte=term.start_date,
                date__lte=term.end_date
            )
        
        total_days = attendances.count()
        days_present = attendances.filter(status='present').count()
        days_absent = attendances.filter(status='absent').count()
        days_late = attendances.filter(status='late').count()
        days_excused = attendances.filter(status='excused').count()
        
        attendance_percentage = (days_present / total_days * 100) if total_days > 0 else 0
        
        return {
            'total_days': total_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'days_late': days_late,
            'days_excused': days_excused,
            'attendance_percentage': round(attendance_percentage, 2),
        }

