"""
Service classes for homework module business logic
"""
from django.db.models import Count, Q, Avg
from django.utils import timezone
from .models import Assignment, AssignmentSubmission
from core.models import Student


class HomeworkService:
    """Service for homework-related business logic"""
    
    @staticmethod
    def get_teacher_assignments(teacher, school, active_only=True):
        """Get all assignments created by a teacher"""
        assignments = Assignment.objects.filter(
            school=school,
            teacher=teacher
        ).select_related('subject', 'school_class')
        
        if active_only:
            assignments = assignments.filter(is_active=True)
        
        return assignments.order_by('-due_date')
    
    @staticmethod
    def get_student_assignments(student, school, include_submitted=True):
        """Get all assignments for a student's class"""
        # Get student's class
        current_class = student.get_current_class()
        if not current_class:
            return Assignment.objects.none()
        
        assignments = Assignment.objects.filter(
            school=school,
            school_class=current_class,
            is_active=True
        ).select_related('subject', 'school_class', 'teacher')
        
        if include_submitted:
            return assignments.order_by('-due_date')
        
        # Only show assignments not yet submitted
        submitted_ids = AssignmentSubmission.objects.filter(
            student=student,
            assignment__in=assignments
        ).values_list('assignment_id', flat=True)
        
        return assignments.exclude(id__in=submitted_ids).order_by('-due_date')
    
    @staticmethod
    def get_class_assignments(school_class, school, active_only=True):
        """Get all assignments for a specific class"""
        assignments = Assignment.objects.filter(
            school=school,
            school_class=school_class
        ).select_related('subject', 'teacher')
        
        if active_only:
            assignments = assignments.filter(is_active=True)
        
        return assignments.order_by('-due_date')
    
    @staticmethod
    def get_submission_statistics(assignment):
        """Get statistics for an assignment"""
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        
        total_students = assignment.school_class.students.filter(
            school=assignment.school,
            is_active=True
        ).count()
        
        submitted_count = submissions.count()
        graded_count = submissions.filter(marks_obtained__isnull=False).count()
        pending_count = submitted_count - graded_count
        not_submitted_count = total_students - submitted_count
        
        avg_marks = None
        if graded_count > 0:
            avg_marks = submissions.filter(
                marks_obtained__isnull=False
            ).aggregate(avg=Avg('marks_obtained'))['avg']
        
        return {
            'total_students': total_students,
            'submitted_count': submitted_count,
            'graded_count': graded_count,
            'pending_count': pending_count,
            'not_submitted_count': not_submitted_count,
            'submission_rate': (submitted_count / total_students * 100) if total_students > 0 else 0,
            'average_marks': float(avg_marks) if avg_marks else None,
        }
    
    @staticmethod
    def get_student_submission_stats(student, school):
        """Get submission statistics for a student"""
        submissions = AssignmentSubmission.objects.filter(
            student=student,
            school=school
        ).select_related('assignment')
        
        total = submissions.count()
        graded = submissions.filter(marks_obtained__isnull=False).count()
        pending = total - graded
        late = submissions.filter(status='late').count()
        
        avg_percentage = None
        if graded > 0:
            graded_subs = submissions.filter(marks_obtained__isnull=False)
            percentages = [sub.percentage for sub in graded_subs if sub.percentage is not None]
            if percentages:
                avg_percentage = sum(percentages) / len(percentages)
        
        return {
            'total_submissions': total,
            'graded_count': graded,
            'pending_count': pending,
            'late_count': late,
            'average_percentage': round(avg_percentage, 2) if avg_percentage else None,
        }

