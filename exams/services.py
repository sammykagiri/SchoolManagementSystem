"""
Service classes for exams module business logic
"""
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from .models import Exam, Gradebook, GradebookSummary
from core.models import Student, Term
from timetable.models import Subject


class GradebookService:
    """Service for gradebook-related business logic"""
    
    @staticmethod
    def update_gradebook_summary(student, term, subject):
        """
        Update or create gradebook summary for a student in a term for a subject.
        This should be called whenever a grade is entered or updated.
        """
        gradebooks = Gradebook.objects.filter(
            school=student.school,
            student=student,
            exam__term=term,
            exam__subject=subject
        )
        
        if not gradebooks.exists():
            return None
        
        total_marks = sum(gb.exam.max_marks for gb in gradebooks)
        marks_obtained = sum(gb.marks_obtained for gb in gradebooks)
        average_percentage = (marks_obtained / total_marks * 100) if total_marks > 0 else 0
        
        # Calculate final grade
        if average_percentage >= 90:
            final_grade = 'A'
        elif average_percentage >= 80:
            final_grade = 'B'
        elif average_percentage >= 70:
            final_grade = 'C'
        elif average_percentage >= 60:
            final_grade = 'D'
        else:
            final_grade = 'F'
        
        summary, created = GradebookSummary.objects.update_or_create(
            school=student.school,
            student=student,
            term=term,
            subject=subject,
            defaults={
                'total_marks': total_marks,
                'marks_obtained': marks_obtained,
                'average_percentage': average_percentage,
                'final_grade': final_grade,
            }
        )
        
        return summary
    
    @staticmethod
    def generate_summaries_for_term(school, term, subject=None):
        """
        Generate gradebook summaries for all active students in a term.
        If subject is provided, only generate for that subject.
        """
        students = Student.objects.filter(school=school, is_active=True)
        
        if subject:
            subjects = Subject.objects.filter(id=subject.id, school=school)
        else:
            subjects = Subject.objects.filter(school=school, is_active=True)
        
        created_count = 0
        
        for student in students:
            for subj in subjects:
                # Check if summary exists before updating
                existing = GradebookSummary.objects.filter(
                    school=school,
                    student=student,
                    term=term,
                    subject=subj
                ).exists()
                summary = GradebookService.update_gradebook_summary(student, term, subj)
                if summary and not existing:
                    created_count += 1
        
        return created_count
    
    @staticmethod
    def get_student_performance_stats(student, term=None):
        """
        Get performance statistics for a student.
        If term is provided, stats are for that term only.
        """
        gradebooks = Gradebook.objects.filter(
            school=student.school,
            student=student
        )
        
        if term:
            gradebooks = gradebooks.filter(exam__term=term)
        
        if not gradebooks.exists():
            return {
                'total_exams': 0,
                'average_percentage': 0,
                'passing_count': 0,
                'failing_count': 0,
            }
        
        total_exams = gradebooks.count()
        avg_percentage = gradebooks.aggregate(avg=Avg('percentage'))['avg'] or 0
        passing_count = sum(1 for gb in gradebooks if gb.is_passing)
        failing_count = total_exams - passing_count
        
        return {
            'total_exams': total_exams,
            'average_percentage': round(avg_percentage, 2),
            'passing_count': passing_count,
            'failing_count': failing_count,
        }

