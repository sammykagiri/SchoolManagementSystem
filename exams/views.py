from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Sum, Count, F
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import ExamType, Exam, Gradebook, GradebookSummary
from .serializers import (
    ExamTypeSerializer, ExamSerializer, GradebookSerializer, GradebookSummarySerializer
)
from core.models import Student, Term, SchoolClass
from timetable.models import Subject


class ExamTypeViewSet(viewsets.ModelViewSet):
    serializer_class = ExamTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = ExamType.objects.filter(school=school)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class ExamViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Exam.objects.filter(school=school).select_related(
            'term', 'exam_type', 'subject', 'school_class', 'created_by'
        )
        
        term_id = self.request.query_params.get('term_id')
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        
        return queryset.order_by('-exam_date', 'subject')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school, created_by=self.request.user)


class GradebookViewSet(viewsets.ModelViewSet):
    serializer_class = GradebookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Gradebook.objects.filter(school=school).select_related(
            'student', 'exam', 'exam__subject', 'exam__term', 'entered_by'
        )
        
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        exam_id = self.request.query_params.get('exam_id')
        if exam_id:
            queryset = queryset.filter(exam_id=exam_id)
        
        term_id = self.request.query_params.get('term_id')
        if term_id:
            queryset = queryset.filter(exam__term_id=term_id)
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(exam__subject_id=subject_id)
        
        return queryset.order_by('student', 'exam')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school, entered_by=self.request.user)

    @action(detail=False, methods=['post'])
    def bulk_enter(self, request):
        """Bulk enter grades for multiple students"""
        school = request.user.profile.school
        exam_id = request.data.get('exam_id')
        grades_data = request.data.get('grades', [])
        
        if not exam_id:
            return Response({'error': 'exam_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        created_count = 0
        updated_count = 0
        
        for grade_data in grades_data:
            student_id = grade_data.get('student_id')
            marks_obtained = grade_data.get('marks_obtained')
            remarks = grade_data.get('remarks', '')
            
            gradebook, created = Gradebook.objects.update_or_create(
                school=school,
                student_id=student_id,
                exam_id=exam_id,
                defaults={
                    'marks_obtained': marks_obtained,
                    'remarks': remarks,
                    'entered_by': request.user,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return Response({
            'message': f'Entered grades for {len(grades_data)} students',
            'created': created_count,
            'updated': updated_count
        })


class GradebookSummaryViewSet(viewsets.ModelViewSet):
    serializer_class = GradebookSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = GradebookSummary.objects.filter(school=school).select_related(
            'student', 'term', 'subject'
        )
        
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        term_id = self.request.query_params.get('term_id')
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        
        return queryset.order_by('student', 'term', 'subject')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate gradebook summaries for a term"""
        school = request.user.profile.school
        term_id = request.data.get('term_id')
        subject_id = request.data.get('subject_id')
        
        if not term_id:
            return Response({'error': 'term_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        term = Term.objects.get(id=term_id, school=school)
        students = Student.objects.filter(school=school, is_active=True)
        
        if subject_id:
            subjects = Subject.objects.filter(id=subject_id, school=school)
        else:
            subjects = Subject.objects.filter(school=school, is_active=True)
        
        created_count = 0
        
        for student in students:
            for subject in subjects:
                # Get all gradebooks for this student, term, and subject
                gradebooks = Gradebook.objects.filter(
                    school=school,
                    student=student,
                    exam__term=term,
                    exam__subject=subject
                )
                
                if not gradebooks.exists():
                    continue
                
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
                    school=school,
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
                
                if created:
                    created_count += 1
        
        return Response({
            'message': f'Generated gradebook summaries for {created_count} student-subject combinations',
            'term': term.name
        })


# UI Views
@login_required
def exam_list(request):
    """List exams"""
    school = request.user.profile.school
    exams = Exam.objects.filter(school=school).select_related(
        'term', 'exam_type', 'subject', 'school_class'
    ).order_by('-exam_date', 'subject')
    
    term_id = request.GET.get('term_id', '')
    if term_id:
        exams = exams.filter(term_id=term_id)
    
    subject_id = request.GET.get('subject_id', '')
    if subject_id:
        exams = exams.filter(subject_id=subject_id)
    
    class_id = request.GET.get('class_id', '')
    if class_id:
        exams = exams.filter(school_class_id=class_id)
    
    paginator = Paginator(exams, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'terms': terms,
        'subjects': subjects,
        'classes': classes,
        'term_id': term_id,
        'subject_id': subject_id,
        'class_id': class_id,
    }
    return render(request, 'exams/exam_list.html', context)


@login_required
def gradebook_list(request):
    """List gradebook entries"""
    school = request.user.profile.school
    gradebooks = Gradebook.objects.filter(school=school).select_related(
        'student', 'exam', 'exam__subject', 'exam__term'
    ).order_by('student', 'exam')
    
    student_id = request.GET.get('student_id', '')
    if student_id:
        gradebooks = gradebooks.filter(student_id=student_id)
    
    exam_id = request.GET.get('exam_id', '')
    if exam_id:
        gradebooks = gradebooks.filter(exam_id=exam_id)
    
    term_id = request.GET.get('term_id', '')
    if term_id:
        gradebooks = gradebooks.filter(exam__term_id=term_id)
    
    paginator = Paginator(gradebooks, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name')
    exams = Exam.objects.filter(school=school).order_by('-exam_date')
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    
    context = {
        'page_obj': page_obj,
        'students': students,
        'exams': exams,
        'terms': terms,
        'student_id': student_id,
        'exam_id': exam_id,
        'term_id': term_id,
    }
    return render(request, 'exams/gradebook_list.html', context)


@login_required
def gradebook_summary_list(request):
    """List gradebook summaries"""
    school = request.user.profile.school
    summaries = GradebookSummary.objects.filter(school=school).select_related(
        'student', 'term', 'subject'
    ).order_by('student', 'term', 'subject')
    
    student_id = request.GET.get('student_id', '')
    if student_id:
        summaries = summaries.filter(student_id=student_id)
    
    term_id = request.GET.get('term_id', '')
    if term_id:
        summaries = summaries.filter(term_id=term_id)
    
    subject_id = request.GET.get('subject_id', '')
    if subject_id:
        summaries = summaries.filter(subject_id=subject_id)
    
    paginator = Paginator(summaries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name')
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'students': students,
        'terms': terms,
        'subjects': subjects,
        'student_id': student_id,
        'term_id': term_id,
        'subject_id': subject_id,
    }
    return render(request, 'exams/gradebook_summary_list.html', context)
