from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from datetime import date, timedelta, datetime
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
def attendance_edit(request, attendance_id):
    """Edit an attendance record"""
    school = request.user.profile.school
    attendance = get_object_or_404(Attendance, id=attendance_id, school=school)
    
    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        status = request.POST.get('status', 'present')
        remarks = request.POST.get('remarks', '')
        class_id = request.POST.get('class_id', '')
        
        # Parse date string to date object
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            attendance_date = attendance.date
            messages.warning(request, 'Invalid date format. Using original date.')
        
        # Validate that the attendance date falls within a term's date range
        matching_term = Term.objects.filter(
            school=school,
            start_date__lte=attendance_date,
            end_date__gte=attendance_date
        ).first()
        
        if not matching_term:
            messages.error(
                request, 
                f'Cannot update attendance for {attendance_date.strftime("%B %d, %Y")}. '
                f'This date does not fall within any term\'s date range. '
                f'Please select a date that is within an active term period or update your term dates.'
            )
            # Redirect back to edit form with the invalid date
            redirect_url = f"{reverse('attendance:attendance_edit', args=[attendance_id])}?date={date_str}"
            return redirect(redirect_url)
        
        # Check if changing the date would create a duplicate
        # (same student, same date, but different attendance record)
        if attendance_date != attendance.date:
            existing_attendance = Attendance.objects.filter(
                school=school,
                student_id=attendance.student_id,
                date=attendance_date
            ).exclude(id=attendance_id).first()
            
            if existing_attendance:
                messages.error(
                    request,
                    f'Cannot update: An attendance record already exists for {attendance.student.full_name} on {attendance_date.strftime("%B %d, %Y")}. '
                    f'Please edit or delete the existing record first, or choose a different date.'
                )
                redirect_url = f"{reverse('attendance:attendance_edit', args=[attendance_id])}?date={date_str}"
                return redirect(redirect_url)
        
        # Update attendance
        attendance.date = attendance_date
        attendance.status = status
        attendance.remarks = remarks
        attendance.school_class_id = class_id if class_id else None
        attendance.marked_by = request.user
        attendance.save()
        
        messages.success(request, 'Attendance updated successfully!')
        return redirect('attendance:attendance_list')
    
    # GET request - show edit form
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    
    # Check if a date was provided in query params (for validation feedback)
    date_str = request.GET.get('date', '')
    date_to_check = attendance.date
    
    if date_str:
        try:
            date_to_check = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    
    # Check if date is valid
    matching_term = Term.objects.filter(
        school=school,
        start_date__lte=date_to_check,
        end_date__gte=date_to_check
    ).first()
    
    date_valid = matching_term is not None
    
    # Ensure date_str is in YYYY-MM-DD format for the template
    date_str_for_template = date_to_check.strftime('%Y-%m-%d')
    
    context = {
        'attendance': attendance,
        'classes': classes,
        'terms': terms,
        'matching_term': matching_term,
        'date_valid': date_valid,
        'attendance_date': date_to_check,
        'date': date_str_for_template,  # Add date string for template
    }
    return render(request, 'attendance/attendance_edit.html', context)


@login_required
def attendance_delete(request, attendance_id):
    """Delete an attendance record"""
    school = request.user.profile.school
    attendance = get_object_or_404(Attendance, id=attendance_id, school=school)
    
    if request.method == 'POST':
        student_name = attendance.student.full_name
        attendance_date = attendance.date
        attendance.delete()
        messages.success(request, f'Attendance for {student_name} on {attendance_date} has been deleted.')
        return redirect('attendance:attendance_list')
    
    context = {
        'attendance': attendance,
    }
    return render(request, 'attendance/attendance_confirm_delete.html', context)


@login_required
def mark_attendance(request):
    """Mark attendance for students"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        if not date_str:
            date_str = str(timezone.now().date())
        
        class_id = request.POST.get('class_id')
        students_data = request.POST.getlist('students')
        statuses = request.POST.getlist('status')
        remarks_list = request.POST.getlist('remarks')
        
        if not students_data:
            messages.error(request, 'No students selected.')
            return redirect('attendance:mark_attendance')
        
        # Parse date string to date object
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError) as e:
            # If date parsing fails, use current date and show warning
            attendance_date = timezone.now().date()
            messages.warning(request, f'Invalid date format. Using today\'s date: {attendance_date}')
        
        # Validate that the attendance date falls within a term's date range
        matching_term = Term.objects.filter(
            school=school,
            start_date__lte=attendance_date,
            end_date__gte=attendance_date
        ).first()
        
        if not matching_term:
            messages.error(
                request, 
                f'Cannot mark attendance for {attendance_date.strftime("%B %d, %Y")}. '
                f'This date does not fall within any term\'s date range. '
                f'Please select a date that is within an active term period or update your term dates.'
            )
            # Redirect back to mark attendance with the same date and class
            redirect_url = f"{reverse('attendance:mark_attendance')}?date={date_str}"
            if class_id:
                redirect_url += f"&class_id={class_id}"
            return redirect(redirect_url)
        
        created_count = 0
        updated_count = 0
        
        for i, student_id in enumerate(students_data):
            status_val = statuses[i] if i < len(statuses) else 'present'
            remarks = remarks_list[i] if i < len(remarks_list) else ''
            
            attendance, created = Attendance.objects.update_or_create(
                school=school,
                student_id=student_id,
                date=attendance_date,
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
        # Redirect to attendance list page
        return redirect('attendance:attendance_list')
    
    # GET request - show form
    class_id = request.GET.get('class_id', '')
    date_str = request.GET.get('date', '')
    
    # If no date provided, use today's date
    if not date_str:
        date_str = str(timezone.now().date())
    
    # Parse date string to date object
    attendance_date = None
    try:
        # Try parsing as YYYY-MM-DD format first (HTML date input format)
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        try:
            # Try parsing as DD/MM/YYYY format
            attendance_date = datetime.strptime(date_str, '%d/%m/%Y').date()
        except (ValueError, TypeError):
            try:
                # Try parsing as MM/DD/YYYY format
                attendance_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            except (ValueError, TypeError):
                # If all parsing fails, use current date
                attendance_date = timezone.now().date()
                date_str = str(attendance_date)
    
    # Ensure date_str is in YYYY-MM-DD format for the template
    date_str = attendance_date.strftime('%Y-%m-%d')
    
    # Check if the selected date falls within any term's date range
    # Note: We check all terms, not just active ones, to allow attendance for any term period
    matching_term = Term.objects.filter(
        school=school,
        start_date__lte=attendance_date,
        end_date__gte=attendance_date
    ).first()
    
    date_valid = matching_term is not None
    
    # Get all terms for reference
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    
    students = Student.objects.filter(school=school, is_active=True)
    if class_id:
        students = students.filter(grade__school_classes__id=class_id).distinct()
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    # Get existing attendance for the date
    existing_attendance = {}
    if attendance_date and date_valid:
        for att in Attendance.objects.filter(school=school, date=attendance_date).select_related('student'):
            existing_attendance[att.student_id] = {
                'status': att.status,
                'remarks': att.remarks or '',
            }
    
    # Prepare students with their existing attendance status
    students_with_attendance = []
    if date_valid:
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
        'attendance_date': attendance_date,  # Pass the date object for template formatting
        'date_valid': date_valid,
        'matching_term': matching_term,
        'terms': terms,
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def attendance_summary(request):
    """View attendance summaries - auto-generates summaries if missing"""
    school = request.user.profile.school
    from .services import AttendanceService
    from .models import Attendance
    
    # Auto-generate summaries for student-term combinations that have attendance
    # Get all attendance records and find their corresponding terms
    attendance_records = Attendance.objects.filter(school=school).select_related('student')
    
    # Track attendance records that don't match any term
    unmatched_attendance = []
    
    # Process each attendance record to ensure summaries are created/updated
    processed_combinations = set()
    for attendance in attendance_records:
        # Find which term this attendance belongs to
        term = Term.objects.filter(
            school=school,
            start_date__lte=attendance.date,
            end_date__gte=attendance.date
        ).first()
        
        if term:
            key = (attendance.student_id, term.id)
            if key not in processed_combinations:
                try:
                    student = Student.objects.get(id=attendance.student_id, school=school, is_active=True)
                    AttendanceService.update_attendance_summary(student, term)
                    processed_combinations.add(key)
                except Student.DoesNotExist:
                    continue
        else:
            # Track attendance that doesn't match any term
            unmatched_attendance.append(attendance.date)
    
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
    
    # Get terms and students for filters
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    students_list = Student.objects.filter(school=school, is_active=True).order_by('first_name')
    
    # Get unique unmatched dates for display
    unmatched_dates = sorted(set(unmatched_attendance)) if unmatched_attendance else []
    
    # Check if all summaries have 0 days (meaning no attendance matches term dates)
    all_zero = all(summary.total_days == 0 for summary in page_obj) if page_obj else False
    
    context = {
        'page_obj': page_obj,
        'terms': terms,
        'students': students_list,
        'term_id': term_id,
        'student_id': student_id,
        'unmatched_dates': unmatched_dates,
        'has_attendance': attendance_records.exists(),
        'all_zero': all_zero,
    }
    return render(request, 'attendance/attendance_summary.html', context)
