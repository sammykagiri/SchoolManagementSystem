"""
Service classes for business logic separation
All business logic should be in these service classes, not in views
"""
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import date, timedelta
from .models import School, Student, Term, StudentFee, Grade, SchoolClass
from attendance.models import Attendance, AttendanceSummary
from exams.models import Exam, Gradebook, GradebookSummary
from payments.models import Payment


class DashboardService:
    """Service for dashboard data aggregation"""
    
    @staticmethod
    def get_dashboard_data(school, user):
        """Get all dashboard statistics"""
        current_term = Term.objects.filter(school=school, is_active=True).first()
        
        # Student statistics
        total_students = Student.objects.filter(school=school, is_active=True).count()
        recent_students = Student.objects.filter(
            school=school, is_active=True
        ).order_by('-created_at')[:5]
        
        # Fee statistics
        fee_stats = DashboardService._get_fee_statistics(school, current_term)
        
        # Attendance statistics
        attendance_stats = DashboardService._get_attendance_statistics(school, current_term)
        
        # Exam statistics
        exam_stats = DashboardService._get_exam_statistics(school, current_term)
        
        # Payment statistics
        payment_stats = DashboardService._get_payment_statistics(school, current_term)
        
        return {
            'total_students': total_students,
            'total_terms': Term.objects.filter(school=school).count(),
            'total_grades': Grade.objects.filter(school=school).count(),
            'current_term': current_term,  # Return the actual Term object for template use
            'current_term_display': f"{current_term.name} ({current_term.academic_year})" if current_term else None,
            'current_term_dict': {
                'id': current_term.id if current_term else None,
                'name': current_term.name if current_term else None,
                'academic_year': current_term.academic_year if current_term else None,
            } if current_term else None,
            'recent_students': [
                {
                    'id': s.id,
                    'student_id': s.student_id,
                    'full_name': s.full_name,
                    'grade': s.grade.name,
                }
                for s in recent_students
            ],
            'fee_statistics': fee_stats,
            'attendance_statistics': attendance_stats,
            'exam_statistics': exam_stats,
            'payment_statistics': payment_stats,
        }
    
    @staticmethod
    def _get_fee_statistics(school, current_term):
        """Get fee-related statistics"""
        if not current_term:
            return {
                'total_charged': 0,
                'total_paid': 0,
                'total_balance': 0,
                'overdue_count': 0,
            }
        
        fees = StudentFee.objects.filter(school=school, term=current_term)
        
        total_charged = fees.aggregate(total=Sum('amount_charged'))['total'] or 0
        total_paid = fees.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_balance = total_charged - total_paid
        overdue_count = fees.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
        
        return {
            'total_charged': float(total_charged),
            'total_paid': float(total_paid),
            'total_balance': float(total_balance),
            'overdue_count': overdue_count,
        }
    
    @staticmethod
    def _get_attendance_statistics(school, current_term):
        """Get attendance statistics"""
        if not current_term:
            return {
                'today_present': 0,
                'today_absent': 0,
                'term_attendance_percentage': 0,
            }
        
        today = timezone.now().date()
        today_attendance = Attendance.objects.filter(
            school=school,
            date=today
        )
        
        today_present = today_attendance.filter(status='present').count()
        today_absent = today_attendance.filter(status='absent').count()
        
        # Get term attendance percentage
        term_attendances = Attendance.objects.filter(
            school=school,
            date__gte=current_term.start_date,
            date__lte=current_term.end_date
        )
        
        total_days = term_attendances.count()
        present_days = term_attendances.filter(status='present').count()
        term_attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        return {
            'today_present': today_present,
            'today_absent': today_absent,
            'term_attendance_percentage': round(term_attendance_percentage, 2),
        }
    
    @staticmethod
    def _get_exam_statistics(school, current_term):
        """Get exam statistics"""
        if not current_term:
            return {
                'total_exams': 0,
                'upcoming_exams': 0,
                'average_performance': 0,
            }
        
        exams = Exam.objects.filter(school=school, term=current_term)
        total_exams = exams.count()
        
        today = timezone.now().date()
        upcoming_exams = exams.filter(exam_date__gte=today).count()
        
        # Get average performance
        gradebooks = Gradebook.objects.filter(
            school=school,
            exam__term=current_term
        )
        
        if gradebooks.exists():
            avg_performance = gradebooks.aggregate(
                avg=Avg('percentage')
            )['avg'] or 0
        else:
            avg_performance = 0
        
        return {
            'total_exams': total_exams,
            'upcoming_exams': upcoming_exams,
            'average_performance': round(avg_performance, 2),
        }
    
    @staticmethod
    def _get_payment_statistics(school, current_term):
        """Get payment statistics"""
        if not current_term:
            return {
                'today_payments': 0,
                'month_payments': 0,
                'pending_payments': 0,
            }
        
        today = timezone.now().date()
        today_payments = Payment.objects.filter(
            school=school,
            payment_date__date=today,
            status='completed'
        ).count()
        
        month_start = today.replace(day=1)
        month_payments = Payment.objects.filter(
            school=school,
            payment_date__date__gte=month_start,
            payment_date__date__lte=today,
            status='completed'
        ).count()
        
        pending_payments = Payment.objects.filter(
            school=school,
            status__in=['pending', 'processing']
        ).count()
        
        return {
            'today_payments': today_payments,
            'month_payments': month_payments,
            'pending_payments': pending_payments,
        }


class StudentService:
    """Service for student-related business logic"""
    
    @staticmethod
    def generate_student_id(school):
        """Generate unique student ID"""
        last_student = Student.objects.filter(
            school=school
        ).exclude(student_id='').order_by('-id').first()
        
        if last_student and last_student.student_id and last_student.student_id.isdigit():
            next_id = int(last_student.student_id) + 1
            return str(next_id).zfill(5)
        return '00001'


class TeacherService:
    """Service for teacher-related business logic"""
    
    @staticmethod
    def generate_employee_id(school):
        """Generate unique employee ID for teachers"""
        from timetable.models import Teacher
        last_teacher = Teacher.objects.filter(
            school=school
        ).exclude(employee_id='').order_by('-id').first()
        
        if last_teacher and last_teacher.employee_id:
            # Extract numeric part if exists (e.g., "EMP001" -> "001")
            import re
            match = re.search(r'\d+', last_teacher.employee_id)
            if match:
                next_id = int(match.group()) + 1
                return f"EMP{str(next_id).zfill(3)}"
        return 'EMP001'
    
    @staticmethod
    def get_student_statistics(student):
        """Get comprehensive statistics for a student"""
        # Fee statistics
        fees = StudentFee.objects.filter(student=student)
        total_charged = fees.aggregate(total=Sum('amount_charged'))['total'] or 0
        total_paid = fees.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_balance = total_charged - total_paid
        
        # Attendance statistics
        attendances = Attendance.objects.filter(student=student)
        total_days = attendances.count()
        present_days = attendances.filter(status='present').count()
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        # Exam statistics
        gradebooks = Gradebook.objects.filter(student=student)
        if gradebooks.exists():
            avg_performance = gradebooks.aggregate(avg=Avg('percentage'))['avg'] or 0
        else:
            avg_performance = 0
        
        return {
            'fee_statistics': {
                'total_charged': float(total_charged),
                'total_paid': float(total_paid),
                'total_balance': float(total_balance),
            },
            'attendance_statistics': {
                'total_days': total_days,
                'present_days': present_days,
                'attendance_percentage': round(attendance_percentage, 2),
            },
            'exam_statistics': {
                'average_performance': round(avg_performance, 2),
                'total_exams': gradebooks.count(),
            },
        }

