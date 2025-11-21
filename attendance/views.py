from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from datetime import date, timedelta
from .models import Attendance, AttendanceSummary
from .serializers import AttendanceSerializer, AttendanceSummarySerializer
from core.models import Student, Term, SchoolClass


class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Attendance.objects.filter(school=school).select_related(
            'student', 'school_class', 'marked_by'
        )
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by student
        student_id = self.request.query_params.get('student_id', None)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        # Filter by class
        class_id = self.request.query_params.get('class_id', None)
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-date', 'student')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        attendance = serializer.save(school=school, marked_by=self.request.user)
        # Summary will be updated automatically via signal

    @action(detail=False, methods=['post'])
    def bulk_mark(self, request):
        """Bulk mark attendance for multiple students"""
        school = request.user.profile.school
        date_str = request.data.get('date', str(timezone.now().date()))
        class_id = request.data.get('class_id')
        students_data = request.data.get('students', [])
        
        created_count = 0
        updated_count = 0
        
        for student_data in students_data:
            student_id = student_data.get('student_id')
            status_val = student_data.get('status', 'present')
            remarks = student_data.get('remarks', '')
            
            attendance, created = Attendance.objects.update_or_create(
                school=school,
                student_id=student_id,
                date=date_str,
                defaults={
                    'status': status_val,
                    'remarks': remarks,
                    'marked_by': request.user,
                    'school_class_id': class_id,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return Response({
            'message': f'Attendance marked for {len(students_data)} students',
            'created': created_count,
            'updated': updated_count
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get attendance statistics"""
        school = request.user.profile.school
        student_id = request.query_params.get('student_id')
        term_id = request.query_params.get('term_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        queryset = Attendance.objects.filter(school=school)
        
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        if term_id:
            term = Term.objects.get(id=term_id, school=school)
            queryset = queryset.filter(date__gte=term.start_date, date__lte=term.end_date)
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        total = queryset.count()
        present = queryset.filter(status='present').count()
        absent = queryset.filter(status='absent').count()
        late = queryset.filter(status='late').count()
        excused = queryset.filter(status='excused').count()
        
        attendance_percentage = (present / total * 100) if total > 0 else 0
        
        return Response({
            'total': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attendance_percentage': round(attendance_percentage, 2)
        })


class AttendanceSummaryViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = AttendanceSummary.objects.filter(school=school).select_related(
            'student', 'term'
        )
        
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        term_id = self.request.query_params.get('term_id')
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        
        return queryset.order_by('-term', 'student')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate attendance summary for a term"""
        school = request.user.profile.school
        term_id = request.data.get('term_id')
        
        if not term_id:
            return Response({'error': 'term_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        term = Term.objects.get(id=term_id, school=school)
        students = Student.objects.filter(school=school, is_active=True)
        
        created_count = 0
        
        for student in students:
            attendances = Attendance.objects.filter(
                school=school,
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
                school=school,
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
            
            if created:
                created_count += 1
        
        return Response({
            'message': f'Generated attendance summaries for {created_count} students',
            'term': term.name
        })


# UI Views
@login_required
def attendance_list(request):
    """List attendance records"""
    school = request.user.profile.school
    attendances = Attendance.objects.filter(school=school).select_related(
        'student', 'school_class', 'marked_by'
    ).order_by('-date', 'student')
    
    # Filter by date
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    
    # Filter by student
    student_id = request.GET.get('student_id', '')
    if student_id:
        attendances = attendances.filter(student_id=student_id)
    
    # Filter by class
    class_id = request.GET.get('class_id', '')
    if class_id:
        attendances = attendances.filter(school_class_id=class_id)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        attendances = attendances.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(attendances, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name')
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'students': students,
        'classes': classes,
        'date_from': date_from,
        'date_to': date_to,
        'student_id': student_id,
        'class_id': class_id,
        'status_filter': status_filter,
    }
    return render(request, 'attendance/attendance_list.html', context)


@login_required
def mark_attendance(request):
    """Mark attendance for students"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        date_str = request.POST.get('date', str(timezone.now().date()))
        class_id = request.POST.get('class_id')
        students_data = request.POST.getlist('students')
        statuses = request.POST.getlist('status')
        remarks_list = request.POST.getlist('remarks')
        
        if not students_data:
            messages.error(request, 'No students selected.')
            return redirect('attendance:mark_attendance')
        
        created_count = 0
        updated_count = 0
        
        for i, student_id in enumerate(students_data):
            status_val = statuses[i] if i < len(statuses) else 'present'
            remarks = remarks_list[i] if i < len(remarks_list) else ''
            
            attendance, created = Attendance.objects.update_or_create(
                school=school,
                student_id=student_id,
                date=date_str,
                defaults={
                    'status': status_val,
                    'remarks': remarks,
                    'marked_by': request.user,
                    'school_class_id': class_id if class_id else None,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        messages.success(request, f'Attendance marked for {len(students_data)} students ({created_count} new, {updated_count} updated)')
        return redirect('attendance:attendance_list')
    
    # GET request - show form
    class_id = request.GET.get('class_id', '')
    date_str = request.GET.get('date', str(timezone.now().date()))
    
    students = Student.objects.filter(school=school, is_active=True)
    if class_id:
        students = students.filter(grade__school_classes__id=class_id).distinct()
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    # Get existing attendance for the date
    existing_attendance = {}
    if date_str:
        for att in Attendance.objects.filter(school=school, date=date_str).select_related('student'):
            existing_attendance[att.student_id] = {
                'status': att.status,
                'remarks': att.remarks or '',
            }
    
    # Prepare students with their existing attendance status
    students_with_attendance = []
    for student in students.order_by('first_name', 'last_name'):
        existing = existing_attendance.get(student.id, {})
        student_data = {
            'student': student,
            'existing_status': existing.get('status', 'present'),
            'existing_remarks': existing.get('remarks', ''),
        }
        students_with_attendance.append(student_data)
    
    context = {
        'students_with_attendance': students_with_attendance,
        'classes': classes,
        'class_id': class_id,
        'date': date_str,
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def attendance_summary(request):
    """View attendance summaries"""
    school = request.user.profile.school
    summaries = AttendanceSummary.objects.filter(school=school).select_related(
        'student', 'term'
    ).order_by('-term', 'student')
    
    # Filter by term
    term_id = request.GET.get('term_id', '')
    if term_id:
        summaries = summaries.filter(term_id=term_id)
    
    # Filter by student
    student_id = request.GET.get('student_id', '')
    if student_id:
        summaries = summaries.filter(student_id=student_id)
    
    paginator = Paginator(summaries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name')
    
    context = {
        'page_obj': page_obj,
        'terms': terms,
        'students': students,
        'term_id': term_id,
        'student_id': student_id,
    }
    return render(request, 'attendance/attendance_summary.html', context)
