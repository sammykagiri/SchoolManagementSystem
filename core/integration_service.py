"""
Integration service for cross-module communication and coordination
"""
from django.utils import timezone
from .models import Student, Term
from attendance.models import AttendanceSummary
from exams.models import GradebookSummary
from communications.services import CommunicationService


class IntegrationService:
    """Service for coordinating between different modules"""
    
    @staticmethod
    def check_low_attendance_and_notify(school, term, threshold_percentage=75):
        """
        Check for students with low attendance and optionally send notifications.
        Returns list of students with low attendance.
        """
        summaries = AttendanceSummary.objects.filter(
            school=school,
            term=term,
            attendance_percentage__lt=threshold_percentage
        ).select_related('student')
        
        low_attendance_students = []
        for summary in summaries:
            low_attendance_students.append({
                'student': summary.student,
                'attendance_percentage': summary.attendance_percentage,
                'days_absent': summary.days_absent,
            })
        
        return low_attendance_students
    
    @staticmethod
    def check_failing_students_and_notify(school, term, passing_percentage=40):
        """
        Check for students with failing grades and optionally send notifications.
        Returns list of students with failing grades.
        """
        summaries = GradebookSummary.objects.filter(
            school=school,
            term=term,
            average_percentage__lt=passing_percentage
        ).select_related('student', 'subject')
        
        failing_students = {}
        for summary in summaries:
            student_id = summary.student.id
            if student_id not in failing_students:
                failing_students[student_id] = {
                    'student': summary.student,
                    'failing_subjects': [],
                }
            failing_students[student_id]['failing_subjects'].append({
                'subject': summary.subject,
                'average_percentage': summary.average_percentage,
                'final_grade': summary.final_grade,
            })
        
        return list(failing_students.values())
    
    @staticmethod
    def get_student_comprehensive_report(student, term=None):
        """
        Get a comprehensive report for a student including:
        - Attendance statistics
        - Fee status
        - Exam performance
        - Overall summary
        """
        from .services import StudentService
        from attendance.services import AttendanceService
        from exams.services import GradebookService
        from core.models import StudentFee
        
        if not term:
            term = Term.objects.filter(school=student.school, is_active=True).first()
        
        # Get all statistics
        student_stats = StudentService.get_student_statistics(student)
        attendance_stats = AttendanceService.get_student_attendance_stats(student, term)
        performance_stats = GradebookService.get_student_performance_stats(student, term)
        
        # Get fee status
        if term:
            fees = StudentFee.objects.filter(student=student, term=term)
            total_charged = sum(f.amount_charged for f in fees)
            total_paid = sum(f.amount_paid for f in fees)
            total_balance = total_charged - total_paid
            overdue_fees = [f for f in fees if f.is_overdue]
        else:
            total_charged = 0
            total_paid = 0
            total_balance = 0
            overdue_fees = []
        
        # Get attendance summary if term exists
        attendance_summary = None
        if term:
            attendance_summary = AttendanceSummary.objects.filter(
                student=student,
                term=term
            ).first()
        
        # Get gradebook summaries if term exists
        gradebook_summaries = []
        if term:
            gradebook_summaries = GradebookSummary.objects.filter(
                student=student,
                term=term
            ).select_related('subject').order_by('subject__name')
        
        return {
            'student': student,
            'term': term,
            'attendance': {
                'stats': attendance_stats,
                'summary': attendance_summary,
            },
            'fees': {
                'total_charged': total_charged,
                'total_paid': total_paid,
                'total_balance': total_balance,
                'overdue_count': len(overdue_fees),
                'overdue_fees': overdue_fees,
            },
            'performance': {
                'stats': performance_stats,
                'summaries': gradebook_summaries,
            },
            'overall': {
                'attendance_percentage': attendance_stats.get('attendance_percentage', 0),
                'average_performance': performance_stats.get('average_percentage', 0),
                'fee_status': 'paid' if total_balance == 0 else 'pending',
            },
        }
    
    @staticmethod
    def send_attendance_alert(student, term, attendance_percentage):
        """
        Send alert to parent about low attendance.
        """
        communication_service = CommunicationService()
        
        # This would integrate with the communication service
        # For now, just return a flag indicating if notification should be sent
        if attendance_percentage < 75:
            return True
        return False
    
    @staticmethod
    def send_exam_results_notification(student, term):
        """
        Send exam results notification to parent.
        """
        # This would integrate with the communication service
        # to send exam results when they're published
        pass

