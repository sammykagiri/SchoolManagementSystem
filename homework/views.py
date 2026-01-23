"""
Views for homework module
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Assignment, AssignmentSubmission
from .forms import AssignmentForm, AssignmentSubmissionForm, GradeSubmissionForm
from .serializers import AssignmentSerializer, AssignmentSubmissionSerializer
from .services import HomeworkService
from core.decorators import permission_required
from core.models import Student, SchoolClass
from timetable.models import Subject


# API ViewSets
class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Assignment.objects.filter(school=school).select_related(
            'subject', 'school_class', 'teacher'
        )
        
        # Filter by class
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        
        # Filter by subject
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        
        # Filter by teacher
        if self.request.user.profile.role == 'teacher':
            queryset = queryset.filter(teacher=self.request.user)
        
        return queryset.order_by('-due_date')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school, teacher=self.request.user)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get assignment statistics"""
        assignment = self.get_object()
        stats = HomeworkService.get_submission_statistics(assignment)
        return Response(stats)


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = AssignmentSubmission.objects.filter(school=school).select_related(
            'assignment', 'student', 'graded_by'
        )
        
        # Filter by assignment
        assignment_id = self.request.query_params.get('assignment_id')
        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        
        # Filter by student (for student role)
        if self.request.user.profile.role == 'student':
            # Get student linked to user
            try:
                student = Student.objects.get(user=self.request.user, school=school)
                queryset = queryset.filter(student=student)
            except Student.DoesNotExist:
                queryset = queryset.none()
        
        # Filter by student (for parent role)
        if self.request.user.profile.role == 'parent':
            # Get parent's children
            children = Student.objects.filter(
                school=school,
                parents__user=self.request.user
            )
            queryset = queryset.filter(student__in=children)
        
        return queryset.order_by('-submitted_at')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)

    @action(detail=True, methods=['post'])
    def grade(self, request, pk=None):
        """Grade a submission"""
        submission = self.get_object()
        marks = request.data.get('marks_obtained')
        feedback = request.data.get('feedback', '')
        
        if marks is None:
            return Response({'error': 'marks_obtained is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        submission.marks_obtained = marks
        submission.feedback = feedback
        submission.graded_by = request.user
        submission.save()
        
        return Response({'message': 'Submission graded successfully'})


# UI Views
@login_required
@permission_required('view', 'assignment')
def assignment_list(request):
    """List all assignments"""
    school = request.user.profile.school
    role = request.user.profile.role
    
    assignments = Assignment.objects.filter(school=school).select_related(
        'subject', 'school_class', 'teacher'
    )
    
    # Filter by teacher if role is teacher
    if role == 'teacher':
        assignments = assignments.filter(teacher=request.user)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        assignments = assignments.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(subject__name__icontains=search_query)
        )
    
    # Filter by class
    class_id = request.GET.get('class_id', '')
    if class_id:
        assignments = assignments.filter(school_class_id=class_id)
    
    # Filter by subject
    subject_id = request.GET.get('subject_id', '')
    if subject_id:
        assignments = assignments.filter(subject_id=subject_id)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        assignments = assignments.filter(is_active=True)
    elif status_filter == 'inactive':
        assignments = assignments.filter(is_active=False)
    elif status_filter == 'overdue':
        assignments = assignments.filter(due_date__lt=timezone.now())
    
    paginator = Paginator(assignments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'classes': classes,
        'subjects': subjects,
        'search_query': search_query,
        'class_id': class_id,
        'subject_id': subject_id,
        'status_filter': status_filter,
    }
    return render(request, 'homework/assignment_list.html', context)


@login_required
@permission_required('add', 'assignment')
def assignment_create(request):
    """Create new assignment"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES, school=school, teacher=request.user)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.school = school
            assignment.teacher = request.user
            assignment.save()
            
            messages.success(request, f'Assignment "{assignment.title}" created successfully.')
            return redirect('homework:assignment_detail', assignment_id=assignment.id)
    else:
        form = AssignmentForm(school=school, teacher=request.user)
    
    context = {
        'form': form,
        'title': 'Create Assignment',
    }
    return render(request, 'homework/assignment_form.html', context)


@login_required
@permission_required('view', 'assignment')
def assignment_detail(request, assignment_id):
    """View assignment details"""
    school = request.user.profile.school
    assignment = get_object_or_404(Assignment, id=assignment_id, school=school)
    
    # Check if teacher can view (if role is teacher, must be the creator)
    if request.user.profile.role == 'teacher' and assignment.teacher != request.user:
        messages.error(request, 'You do not have permission to view this assignment.')
        return redirect('homework:assignment_list')
    
    # Get submissions
    submissions = AssignmentSubmission.objects.filter(
        assignment=assignment
    ).select_related('student', 'graded_by').order_by('-submitted_at')
    
    # Get statistics
    stats = HomeworkService.get_submission_statistics(assignment)
    
    context = {
        'assignment': assignment,
        'submissions': submissions,
        'stats': stats,
    }
    return render(request, 'homework/assignment_detail.html', context)


@login_required
@permission_required('change', 'assignment')
def assignment_update(request, assignment_id):
    """Update assignment"""
    school = request.user.profile.school
    assignment = get_object_or_404(Assignment, id=assignment_id, school=school)
    
    # Check permission
    if request.user.profile.role == 'teacher' and assignment.teacher != request.user:
        messages.error(request, 'You do not have permission to edit this assignment.')
        return redirect('homework:assignment_list')
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES, instance=assignment, school=school, teacher=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Assignment "{assignment.title}" updated successfully.')
            return redirect('homework:assignment_detail', assignment_id=assignment.id)
    else:
        form = AssignmentForm(instance=assignment, school=school, teacher=request.user)
    
    context = {
        'form': form,
        'assignment': assignment,
        'title': 'Update Assignment',
    }
    return render(request, 'homework/assignment_form.html', context)


@login_required
@permission_required('delete', 'assignment')
def assignment_delete(request, assignment_id):
    """Delete assignment"""
    school = request.user.profile.school
    assignment = get_object_or_404(Assignment, id=assignment_id, school=school)
    
    # Check permission
    if request.user.profile.role == 'teacher' and assignment.teacher != request.user:
        messages.error(request, 'You do not have permission to delete this assignment.')
        return redirect('homework:assignment_list')
    
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Assignment deleted successfully.')
        return redirect('homework:assignment_list')
    
    context = {'assignment': assignment}
    return render(request, 'homework/assignment_confirm_delete.html', context)


@login_required
@permission_required('view', 'submission')
def submission_list(request):
    """List submissions (Admin/Teacher only for MVP)"""
    school = request.user.profile.school
    role = request.user.profile.role
    
    # Get student(s) - for parent, get all children; for student, get their own
    if role == 'parent':
        students = Student.objects.filter(
            school=school,
            parents__user=request.user,
            is_active=True
        )
    elif role == 'student':
        # For student role - get student linked to user
        try:
            student = Student.objects.get(user=request.user, school=school, is_active=True)
            students = Student.objects.filter(id=student.id)
        except Student.DoesNotExist:
            students = Student.objects.none()
    else:
        students = Student.objects.none()
    
    submissions = AssignmentSubmission.objects.filter(
        school=school,
        student__in=students
    ).select_related('assignment', 'student').order_by('-submitted_at')
    
    # Filter by assignment
    assignment_id = request.GET.get('assignment_id', '')
    if assignment_id:
        submissions = submissions.filter(assignment_id=assignment_id)
    
    paginator = Paginator(submissions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'assignment_id': assignment_id,
        'role': role,
    }
    return render(request, 'homework/submission_list.html', context)


@login_required
@permission_required('add', 'submission')
def submission_create(request, assignment_id):
    """Create submission on behalf of student (Admin/Teacher only for MVP)"""
    school = request.user.profile.school
    assignment = get_object_or_404(Assignment, id=assignment_id, school=school)
    
    # For MVP: Admin/Teacher can create submissions on behalf of students
    # Get student from query parameter
    student_id = request.GET.get('student_id')
    if not student_id:
        messages.error(request, 'Please select a student.')
        return redirect('homework:assignment_detail', assignment_id=assignment_id)
    
    student = get_object_or_404(Student, id=student_id, school=school, is_active=True)
    
    # Check if already submitted
    existing = AssignmentSubmission.objects.filter(
        assignment=assignment,
        student=student
    ).first()
    
    if existing:
        messages.info(request, 'You have already submitted this assignment.')
        return redirect('homework:submission_detail', submission_id=existing.id)
    
    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.school = school
            submission.assignment = assignment
            submission.student = student
            submission.save()
            
            messages.success(request, 'Assignment submitted successfully.')
            return redirect('homework:submission_detail', submission_id=submission.id)
    else:
        form = AssignmentSubmissionForm()
    
    context = {
        'form': form,
        'assignment': assignment,
        'student': student,
    }
    return render(request, 'homework/submission_form.html', context)


@login_required
@permission_required('view', 'submission')
def submission_detail(request, submission_id):
    """View submission details (Admin/Teacher only for MVP)"""
    school = request.user.profile.school
    submission = get_object_or_404(AssignmentSubmission, id=submission_id, school=school)
    
    context = {
        'submission': submission,
    }
    return render(request, 'homework/submission_detail.html', context)


@login_required
@permission_required('change', 'submission')
def grade_submission(request, submission_id):
    """Grade a submission"""
    school = request.user.profile.school
    submission = get_object_or_404(AssignmentSubmission, id=submission_id, school=school)
    
    # Check permission - teacher must be assignment creator
    if request.user.profile.role == 'teacher' and submission.assignment.teacher != request.user:
        messages.error(request, 'You do not have permission to grade this submission.')
        return redirect('homework:assignment_detail', assignment_id=submission.assignment.id)
    
    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=submission, assignment=submission.assignment)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.graded_by = request.user
            submission.save()
            
            messages.success(request, 'Submission graded successfully.')
            return redirect('homework:assignment_detail', assignment_id=submission.assignment.id)
    else:
        form = GradeSubmissionForm(instance=submission, assignment=submission.assignment)
    
    context = {
        'form': form,
        'submission': submission,
    }
    return render(request, 'homework/grade_submission.html', context)
