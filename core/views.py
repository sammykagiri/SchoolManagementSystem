from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from .models import (
    School, Grade, Term, FeeCategory, TransportRoute, Student, FeeStructure, StudentFee, SchoolClass
)
from timetable.models import Teacher
from rest_framework import viewsets, permissions
from .serializers import (
    SchoolSerializer, GradeSerializer, TermSerializer, FeeCategorySerializer,
    TransportRouteSerializer, StudentSerializer, FeeStructureSerializer, StudentFeeSerializer, SchoolClassSerializer
)
from .forms import StudentForm, UserForm, UserEditForm, UserProfileForm
from .models import Role, Permission
from django.contrib.auth.models import User
import json
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework import permissions
from .services import DashboardService, StudentService, TeacherService
from .decorators import role_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import LoginView


class CustomLoginView(LoginView):
    """Custom login view that redirects authenticated users"""
    template_name = 'auth/login.html'
    
    def dispatch(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)


def is_superadmin_user(user):
    """
    Check if a user is a superadmin (either Django superuser or has super_admin role)
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if hasattr(user, 'profile'):
        return user.profile.is_super_admin
    return False


class IsSuperUser(BasePermission):
    """Allows access only to superusers."""
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def dashboard(request):
    """Main dashboard view - uses service for business logic (Admin/Teacher only for MVP)"""
    school = request.user.profile.school
    dashboard_data = DashboardService.get_dashboard_data(school, request.user)
    
    # Extract fee statistics for template
    fee_stats = dashboard_data.get('fee_statistics', {})
    total_fees_charged = fee_stats.get('total_charged', 0)
    total_fees_paid = fee_stats.get('total_paid', 0)
    total_fees_pending = total_fees_charged - total_fees_paid
    overdue_fees = fee_stats.get('overdue_count', 0)
    
    # Get overdue payments for template
    overdue_payments = StudentFee.objects.filter(
        school=school,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).select_related('student', 'fee_category', 'term')[:10]
    
    # Get chart data - monthly fee trends for last 6 months
    from datetime import datetime, timedelta
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    
    chart_labels = []
    chart_paid = []
    chart_charged = []
    
    # Get last 6 months of data
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=180)
    
    monthly_fees = StudentFee.objects.filter(
        school=school,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total_charged=Sum('amount_charged'),
        total_paid=Sum('amount_paid')
    ).order_by('month')
    
    for item in monthly_fees:
        month_name = item['month'].strftime('%b %Y')
        chart_labels.append(month_name)
        chart_charged.append(float(item['total_charged'] or 0))
        chart_paid.append(float(item['total_paid'] or 0))
    
    # If no data, add placeholder
    if not chart_labels:
        chart_labels = ['No Data']
        chart_charged = [0]
        chart_paid = [0]
    
    # Get fee breakdown by category for current term
    current_term = dashboard_data.get('current_term')
    fee_by_category = []
    if current_term:
        from .models import FeeCategory
        category_breakdown = StudentFee.objects.filter(
            school=school,
            term=current_term
        ).values('fee_category__name').annotate(
            total_charged=Sum('amount_charged'),
            total_paid=Sum('amount_paid')
        ).order_by('-total_charged')
        
        for item in category_breakdown:
            fee_by_category.append({
                'category': item['fee_category__name'] or 'Unknown',
                'charged': float(item['total_charged'] or 0),
                'paid': float(item['total_paid'] or 0),
            })
    
    context = {
        **dashboard_data,
        'total_fees_charged': total_fees_charged,
        'total_fees_paid': total_fees_paid,
        'total_fees_pending': total_fees_pending,
        'overdue_fees': overdue_fees,
        'overdue_payments': overdue_payments,
        'chart_labels': json.dumps(chart_labels),
        'chart_charged': json.dumps(chart_charged),
        'chart_paid': json.dumps(chart_paid),
        'fee_by_category': json.dumps(fee_by_category),
    }
    return render(request, 'core/dashboard.html', context)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_dashboard(request):
    """API endpoint for dashboard data"""
    school = request.user.profile.school
    dashboard_data = DashboardService.get_dashboard_data(school, request.user)
    return Response(dashboard_data)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def student_list(request):
    """List all students"""
    school = request.user.profile.school
    students = Student.objects.filter(
        school=school
    ).select_related('grade', 'transport_route', 'school_class').prefetch_related('parents__user')
    
    # Filter by active status (default: show active only)
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    if not show_inactive:
        students = students.filter(is_active=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(student_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(parent_name__icontains=search_query) |
            Q(parent_phone__icontains=search_query)
        )
    
    # Filter by grade
    grade_filter = request.GET.get('grade', '')
    if grade_filter:
        students = students.filter(grade_id=grade_filter)
    
    # Order by active status first, then by name
    students = students.order_by('-is_active', 'first_name', 'last_name')
    
    # Pagination
    paginator = Paginator(students, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Debug: Check user's school and available grades
    school = request.user.profile.school
    print(f"User's school: {school.id} - {school.name}")
    grades = Grade.objects.filter(school=school)
    print(f"Grades for school {school.id}: {list(grades.values('id', 'name'))}")
    
    # If no grades for this school, show all grades for debugging
    if not grades.exists():
        print("No grades found for user's school, showing all grades for debugging")
        grades = Grade.objects.all()
    
    context = {
        'page_obj': page_obj,
        'grades': grades,
        'search_query': search_query,
        'grade_filter': grade_filter,
        'show_inactive': show_inactive,
    }
    
    return render(request, 'core/student_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def student_detail(request, student_id):
    """Student detail view"""
    student = get_object_or_404(
        Student.objects.select_related('grade', 'transport_route', 'school_class', 'school_class__class_teacher').prefetch_related('parents__user'),
        student_id=student_id
    )
    student_fees = StudentFee.objects.filter(student=student).select_related(
        'fee_category', 'term'
    ).order_by('-term__academic_year', '-term__term_number')
    
    # Calculate total statistics
    total_charged = student_fees.aggregate(total=Sum('amount_charged'))['total'] or 0
    total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_balance = total_charged - total_paid
    
    context = {
        'student': student,
        'student_fees': student_fees,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }
    
    return render(request, 'core/student_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def student_create(request):
    """Create new student using Django form"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            try:
                # Use service to generate student_id
                student_id = StudentService.generate_student_id(school)
                
                # Create student with auto-generated ID
                student = form.save(commit=False)
                student.school = school
                student.student_id = student_id
                student.save()
                
                messages.success(request, f'Student {student.full_name} created successfully.')
                return redirect('core:student_detail', student_id=student.student_id)
                
            except Exception as e:
                messages.error(request, f'Error creating student: {str(e)}')
    else:
        form = StudentForm(school=school)
    
    context = {
        'form': form,
        'title': 'Add New Student',
    }
    return render(request, 'core/student_form_new.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def student_update(request, student_id):
    """Update student using Django form"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student, school=school)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'Student {student.full_name} updated successfully.')
                return redirect('core:student_detail', student_id=student.student_id)
            except Exception as e:
                messages.error(request, f'Error updating student: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentForm(instance=student, school=school)
    
    context = {
        'form': form,
        'student': student,
        'title': 'Update Student',
    }
    return render(request, 'core/student_form_new.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def student_delete(request, student_id):
    """Delete student"""
    student = get_object_or_404(Student, student_id=student_id)
    
    if request.method == 'POST':
        student.is_active = False
        student.save()
        messages.success(request, f'Student {student.full_name} deactivated successfully.')
        return redirect('core:student_list')
    
    context = {'student': student}
    return render(request, 'core/student_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def grade_list(request):
    """List all grades"""
    school = request.user.profile.school
    grades = Grade.objects.filter(school=school)
    
    # Sort grades naturally (handles numeric sorting: Grade 1, Grade 2, ..., Grade 10)
    import re
    def natural_sort_key(name):
        """Extract numbers for natural sorting"""
        parts = re.split(r'(\d+)', name)
        return [int(part) if part.isdigit() else part.lower() for part in parts]
    
    grades = sorted(grades, key=lambda g: natural_sort_key(g.name))
    
    if request.method == 'POST':
        # Check if this is a bulk delete request
        if 'bulk_delete' in request.POST:
            grade_ids = request.POST.getlist('grade_ids')
            if grade_ids:
                # Get grades that belong to this school
                grades_to_delete = Grade.objects.filter(id__in=grade_ids, school=school)
                
                # Check which grades are used in classes, students, or fee structures
                from core.models import SchoolClass, Student, FeeStructure
                used_grades = []
                deletable_grades = []
                
                for grade in grades_to_delete:
                    usage_reasons = []
                    
                    # Check if used in classes
                    if SchoolClass.objects.filter(grade=grade).exists():
                        usage_reasons.append('classes')
                    
                    # Check if used in students
                    if Student.objects.filter(grade=grade).exists():
                        usage_reasons.append('students')
                    
                    # Check if used in fee structures
                    if FeeStructure.objects.filter(grade=grade).exists():
                        usage_reasons.append('fee structures')
                    
                    if usage_reasons:
                        used_grades.append((grade, usage_reasons))
                    else:
                        deletable_grades.append(grade)
                
                # Delete only grades that are not in use
                deleted_count = 0
                error_messages = []
                
                for grade in deletable_grades:
                    try:
                        grade.delete()
                        deleted_count += 1
                    except Exception as e:
                        error_messages.append(f'Error deleting {grade.name}: {str(e)}')
                
                # Build detailed error messages for used grades
                if used_grades:
                    grade_messages = []
                    for grade, reasons in used_grades:
                        reason_text = ', '.join(reasons)
                        grade_messages.append(f'{grade.name} (used in {reason_text})')
                    messages.error(request, f'Cannot delete {len(used_grades)} grade(s): {"; ".join(grade_messages)}.')
                
                if deleted_count > 0:
                    messages.success(request, f'Successfully deleted {deleted_count} grade(s)!')
                
                if error_messages:
                    for error_msg in error_messages:
                        messages.error(request, error_msg)
                
                return redirect('core:grade_list')
        else:
            # Regular grade creation
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            
            if not name:
                messages.error(request, 'Grade name is required.')
            else:
                # Normalize name for comparison (remove extra spaces, case-insensitive)
                normalized_name = ' '.join(name.split())
                
                # Check if grade with this name (exact or normalized) already exists
                from django.db.models import Q
                existing_grade = Grade.objects.filter(school=school).filter(
                    Q(name=name) | Q(name=normalized_name)
                ).first()
                
                if existing_grade:
                    messages.error(request, f'A grade with the name "{existing_grade.name}" already exists. Please choose a different name.')
                else:
                    try:
                        Grade.objects.create(school=school, name=normalized_name, description=description)
                        messages.success(request, 'Grade created successfully.')
                        return redirect('core:grade_list')
                    except Exception as e:
                        from django.db import IntegrityError
                        if isinstance(e, IntegrityError):
                            messages.error(request, f'A grade with this name already exists. Please choose a different name.')
                        else:
                            messages.error(request, f'Error creating grade: {str(e)}')
    
    context = {'grades': grades}
    return render(request, 'core/grade_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def grade_generate(request):
    """Generate multiple grades generically"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        grade_name = request.POST.get('grade_name', '').strip()
        highest_grade = request.POST.get('highest_grade', '')
        
        errors = []
        if not grade_name:
            errors.append('Grade name is required.')
        if not highest_grade or not highest_grade.isdigit():
            errors.append('Highest grade number is required and must be a valid number.')
        else:
            highest_grade = int(highest_grade)
            if highest_grade < 1 or highest_grade > 50:
                errors.append('Highest grade must be between 1 and 50.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            # Re-render form with errors
            return render(request, 'core/grade_generate.html', {
                'grade_name': request.POST.get('grade_name', ''),
                'highest_grade': request.POST.get('highest_grade', ''),
            })
        
        # Create grades, skipping ones that already exist
        created_grades = []
        skipped_grades = []
        error_count = 0
        
        for i in range(1, highest_grade + 1):
            grade_full_name = f"{grade_name} {i}"
            grade_variation = f"{grade_name}{i}"
            normalized_full = ' '.join(grade_full_name.split())
            normalized_variation = ' '.join(grade_variation.split())
            
            # Check if it already exists (with or without space, normalized)
            existing_grade = None
            if Grade.objects.filter(school=school, name=grade_full_name).exists():
                existing_grade = Grade.objects.filter(school=school, name=grade_full_name).first()
            elif Grade.objects.filter(school=school, name=grade_variation).exists():
                existing_grade = Grade.objects.filter(school=school, name=grade_variation).first()
            elif Grade.objects.filter(school=school, name=normalized_full).exists():
                existing_grade = Grade.objects.filter(school=school, name=normalized_full).first()
            elif Grade.objects.filter(school=school, name=normalized_variation).exists():
                existing_grade = Grade.objects.filter(school=school, name=normalized_variation).first()
            
            if existing_grade:
                skipped_grades.append(existing_grade.name)
            else:
                try:
                    Grade.objects.create(
                        school=school,
                        name=normalized_full,
                        description=f'{grade_name} {i}'
                    )
                    created_grades.append(normalized_full)
                except Exception as e:
                    from django.db import IntegrityError
                    if isinstance(e, IntegrityError):
                        skipped_grades.append(normalized_full)
                    else:
                        error_count += 1
                        messages.error(request, f'Error creating {grade_full_name}: {str(e)}')
        
        # Build appropriate messages
        if created_grades and skipped_grades:
            messages.success(request, f'Successfully created {len(created_grades)} grade(s): {", ".join(created_grades)}.')
            messages.info(request, f'Skipped {len(skipped_grades)} grade(s) that already exist: {", ".join(skipped_grades)}.')
        elif created_grades:
            messages.success(request, f'Successfully created {len(created_grades)} grade(s): {", ".join(created_grades)}.')
        elif skipped_grades:
            messages.warning(request, f'All {len(skipped_grades)} grade(s) already exist: {", ".join(skipped_grades)}. No new grades were created.')
        else:
            messages.warning(request, 'No grades were created.')
        
        return redirect('core:grade_list')
    
    return render(request, 'core/grade_generate.html')


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def grade_edit(request, grade_id):
    """Edit a grade"""
    school = request.user.profile.school
    grade = get_object_or_404(Grade, id=grade_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        try:
            grade.name = name
            grade.description = description
            grade.save()
            messages.success(request, 'Grade updated successfully.')
            return redirect('core:grade_list')
        except Exception as e:
            messages.error(request, f'Error updating grade: {str(e)}')
    
    context = {'grade': grade}
    return render(request, 'core/grade_edit.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def grade_delete(request, grade_id):
    """Delete a grade"""
    school = request.user.profile.school
    grade = get_object_or_404(Grade, id=grade_id, school=school)
    
    if request.method == 'POST':
        try:
            grade.delete()
            messages.success(request, 'Grade deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting grade: {str(e)}')
        return redirect('core:grade_list')
    
    context = {'grade': grade}
    return render(request, 'core/grade_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def term_list(request):
    """List all terms"""
    school = request.user.profile.school
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    
    context = {'terms': terms}
    return render(request, 'core/term_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def term_add(request):
    """Add new term"""
    school = request.user.profile.school
    TERM_CHOICES = [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')]
    if request.method == 'POST':
        term_number = request.POST.get('term_number', '').strip()
        academic_year = request.POST.get('academic_year', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        is_active = bool(request.POST.get('is_active'))
        errors = []
        if not term_number or not term_number.isdigit() or int(term_number) not in [1,2,3]:
            errors.append('Term number must be 1, 2, or 3.')
        if not academic_year:
            errors.append('Academic year is required.')
        if not start_date:
            errors.append('Start date is required.')
        if not end_date:
            errors.append('End date is required.')
        if start_date and end_date and start_date > end_date:
            errors.append('Start date cannot be after end date.')
        # Unique together check
        if Term.objects.filter(school=school, term_number=term_number, academic_year=academic_year).exists():
            errors.append('A term with this number and academic year already exists.')
        # Overlapping date check
        if start_date and end_date:
            overlapping = Term.objects.filter(
                school=school,
                academic_year=academic_year
            ).filter(
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            if overlapping.exists():
                errors.append('The term dates overlap with another term in the same academic year.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/term_form.html', {'term': None, 'post': request.POST, 'TERM_CHOICES': TERM_CHOICES})
        
        # Generate term name from term_number
        term_name_map = {'1': 'First Term', '2': 'Second Term', '3': 'Third Term'}
        term_name = term_name_map.get(term_number, f'Term {term_number}')
        
        Term.objects.create(
            school=school,
            name=term_name,
            term_number=term_number,
            academic_year=academic_year,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active
        )
        messages.success(request, 'Term added successfully!')
        return redirect('core:term_list')
    return render(request, 'core/term_form.html', {'term': None, 'post': {}, 'TERM_CHOICES': TERM_CHOICES})


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def term_edit(request, term_id):
    """Edit existing term"""
    school = request.user.profile.school
    term = get_object_or_404(Term, id=term_id, school=school)
    TERM_CHOICES = [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')]
    if request.method == 'POST':
        term_number = request.POST.get('term_number', '').strip()
        academic_year = request.POST.get('academic_year', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        is_active = bool(request.POST.get('is_active'))
        errors = []
        if not term_number or not term_number.isdigit() or int(term_number) not in [1,2,3]:
            errors.append('Term number must be 1, 2, or 3.')
        if not academic_year:
            errors.append('Academic year is required.')
        if not start_date:
            errors.append('Start date is required.')
        if not end_date:
            errors.append('End date is required.')
        if start_date and end_date and start_date > end_date:
            errors.append('Start date cannot be after end date.')
        # Unique together check (exclude current term)
        if Term.objects.filter(school=school, term_number=term_number, academic_year=academic_year).exclude(id=term.id).exists():
            errors.append('A term with this number and academic year already exists.')
        # Overlapping date check (exclude current term)
        if start_date and end_date:
            overlapping = Term.objects.filter(
                school=school,
                academic_year=academic_year
            ).exclude(id=term.id).filter(
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            if overlapping.exists():
                errors.append('The term dates overlap with another term in the same academic year.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/term_form.html', {'term': term, 'post': request.POST, 'TERM_CHOICES': TERM_CHOICES})
        
        # Generate term name from term_number
        term_name_map = {'1': 'First Term', '2': 'Second Term', '3': 'Third Term'}
        term_name = term_name_map.get(term_number, f'Term {term_number}')
        
        term.name = term_name
        term.term_number = term_number
        term.academic_year = academic_year
        term.start_date = start_date
        term.end_date = end_date
        term.is_active = is_active
        term.save()
        messages.success(request, 'Term updated successfully!')
        return redirect('core:term_list')
    return render(request, 'core/term_form.html', {'term': term, 'TERM_CHOICES': TERM_CHOICES})


@login_required
@role_required('super_admin', 'school_admin')
def term_delete(request, term_id):
    """Delete a term (soft delete)"""
    school = request.user.profile.school
    term = get_object_or_404(Term, id=term_id, school=school)
    if request.method == 'POST':
        term.delete()
        messages.success(request, 'Term deleted successfully!')
        return redirect('core:term_list')
    return render(request, 'core/term_confirm_delete.html', {'term': term})


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_structure_list(request):
    """List fee structures"""
    school = request.user.profile.school
    fee_structures = FeeStructure.objects.filter(
        is_active=True, school=school
    ).select_related(
        'grade', 'term', 'fee_category'
    ).order_by('grade__name', 'term__academic_year', 'term__term_number')
    
    # Filter by grade and term
    grade_filter = request.GET.get('grade', '')
    term_filter = request.GET.get('term', '')
    
    if grade_filter:
        fee_structures = fee_structures.filter(grade_id=grade_filter)
    if term_filter:
        fee_structures = fee_structures.filter(term_id=term_filter)
    
    if request.method == 'POST':
        grade_id = request.POST.get('grade')
        term_id = request.POST.get('term')
        fee_category_id = request.POST.get('fee_category')
        amount = request.POST.get('amount')
        
        try:
            FeeStructure.objects.create(
                school=school,
                grade_id=grade_id,
                term_id=term_id,
                fee_category_id=fee_category_id,
                amount=amount
            )
            messages.success(request, 'Fee structure created successfully.')
            return redirect('core:fee_structure_list')
        except Exception as e:
            messages.error(request, f'Error creating fee structure: {str(e)}')
    
    grades = Grade.objects.filter(school=school)
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    fee_categories = FeeCategory.objects.filter(school=school)
    
    context = {
        'fee_structures': fee_structures,
        'grades': grades,
        'terms': terms,
        'fee_categories': fee_categories,
        'grade_filter': grade_filter,
        'term_filter': term_filter,
    }
    return render(request, 'core/fee_structure_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def generate_student_fees(request):
    """Generate student fees for a term"""
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        grade_id = request.POST.get('grade_id')
        
        if term_id and grade_id:
            term = get_object_or_404(Term, id=term_id)
            grade = get_object_or_404(Grade, id=grade_id)
            
            # Get fee structure for this grade and term
            fee_structures = FeeStructure.objects.filter(
                grade=grade,
                term=term,
                is_active=True
            )
            
            # Get students in this grade
            students = Student.objects.filter(grade=grade, is_active=True)
            
            created_count = 0
            for student in students:
                for fee_structure in fee_structures:
                    # Check if student should pay this fee category
                    if fee_structure.fee_category.category_type == 'transport' and not student.uses_transport:
                        continue
                    if fee_structure.fee_category.category_type == 'meals' and not student.pays_meals:
                        continue
                    if fee_structure.fee_category.category_type == 'activities' and not student.pays_activities:
                        continue
                    
                    # Calculate amount (for transport, use route-specific amount)
                    amount = fee_structure.amount
                    if fee_structure.fee_category.category_type == 'transport' and student.transport_route:
                        amount = student.transport_route.base_fare
                    
                    # Create or update student fee
                    student_fee, created = StudentFee.objects.get_or_create(
                        school=student.school,
                        student=student,
                        term=term,
                        fee_category=fee_structure.fee_category,
                        defaults={
                            'amount_charged': amount,
                            'due_date': term.end_date,
                        }
                    )
                    
                    if created:
                        created_count += 1
            
            messages.success(request, f'Generated {created_count} fee records for {grade.name} in {term.name}.')
            return redirect('core:fee_structure_list')
    
    terms = Term.objects.all().order_by('-academic_year', '-term_number')
    grades = Grade.objects.all()
    
    context = {'terms': terms, 'grades': grades}
    return render(request, 'core/generate_student_fees.html', context)


@login_required
def profile_view(request):
    """User profile view"""
    return render(request, 'auth/profile.html')


# API views for AJAX requests
@login_required
def get_student_fees(request, student_id):
    """Get student fees as JSON"""
    student = get_object_or_404(Student, student_id=student_id)
    student_fees = StudentFee.objects.filter(student=student).select_related(
        'fee_category', 'term'
    )
    
    fees_data = []
    for fee in student_fees:
        fees_data.append({
            'id': fee.id,
            'fee_category': fee.fee_category.name,
            'term': f"{fee.term.name} - {fee.term.academic_year}",
            'amount_charged': float(fee.amount_charged),
            'amount_paid': float(fee.amount_paid),
            'balance': float(fee.balance),
            'due_date': fee.due_date.strftime('%Y-%m-%d'),
            'is_paid': fee.is_paid,
            'is_overdue': fee.is_overdue,
        })
    
    return JsonResponse({'fees': fees_data})


@login_required
def get_transport_routes(request):
    """Get transport routes as JSON"""
    routes = TransportRoute.objects.filter(is_active=True)
    routes_data = [{'id': route.id, 'name': route.name, 'base_fare': float(route.base_fare)} for route in routes]
    return JsonResponse({'routes': routes_data})


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Multi-tenant: filter by user's school
        school = self.request.user.profile.school
        return Student.objects.filter(school=school)

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        # Use service to generate student_id
        student_id = StudentService.generate_student_id(school)
        serializer.save(school=school, student_id=student_id)


class GradeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return Grade.objects.filter(school=school)


class TransportRouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TransportRoute.objects.all()
    serializer_class = TransportRouteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return TransportRoute.objects.filter(school=school, is_active=True)


class SchoolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperUser]


class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.all()
    serializer_class = TermSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return Term.objects.filter(school=school)

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class FeeCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return FeeCategory.objects.filter(school=school)


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return FeeStructure.objects.filter(school=school)

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class StudentFeeViewSet(viewsets.ModelViewSet):
    queryset = StudentFee.objects.all()
    serializer_class = StudentFeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return StudentFee.objects.filter(school=school)

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset = SchoolClass.objects.all()
    serializer_class = SchoolClassSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        return SchoolClass.objects.filter(school=school)

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


@login_required
def school_update(request):
    """Update school details (single record)"""
    school = request.user.profile.school
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        logo = request.FILES.get('logo')
        errors = []
        if not name:
            errors.append('School name is required.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_form.html', {'school': school})
        school.name = name
        school.address = address
        school.email = email
        school.phone = phone
        if logo:
            school.logo = logo
        school.save()
        messages.success(request, 'School details updated successfully!')
        return redirect('core:school_update')
    return render(request, 'core/school_form.html', {'school': school})


@staff_member_required
def school_add(request):
    """Add a new school (admin only)"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        logo = request.FILES.get('logo')
        errors = []
        if not name:
            errors.append('School name is required.')
        if School.objects.filter(name=name).exists():
            errors.append('A school with this name already exists.')
        if email and School.objects.filter(email=email).exists():
            errors.append('A school with this email already exists.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_add_form.html', {'post': request.POST})
        School.objects.create(name=name, address=address, email=email, phone=phone, logo=logo)
        messages.success(request, 'School added successfully!')
        return redirect('core:school_admin_list')
    return render(request, 'core/school_add_form.html', {'post': {}})


@staff_member_required
def school_admin_list(request):
    """List all schools and allow admin to edit or assign users to schools"""
    from django.contrib.auth.models import User
    schools = School.objects.all()
    users = User.objects.all().select_related('profile')
    if request.method == 'POST':
        # Handle user-school assignment
        user_id = request.POST.get('user_id')
        school_id = request.POST.get('school_id')
        if user_id and school_id:
            try:
                user = User.objects.get(id=user_id)
                school = School.objects.get(id=school_id)
                user.profile.school = school
                user.profile.save()
                messages.success(request, f'User {user.username} assigned to {school.name}.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
    context = {'schools': schools, 'users': users}
    return render(request, 'core/school_admin_list.html', context)


@staff_member_required
def school_admin_edit(request, school_id):
    """Edit a school (admin only)"""
    school = get_object_or_404(School, id=school_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        logo = request.FILES.get('logo')
        errors = []
        if not name:
            errors.append('School name is required.')
        if School.objects.filter(name=name).exclude(id=school.id).exists():
            errors.append('A school with this name already exists.')
        if email and School.objects.filter(email=email).exclude(id=school.id).exists():
            errors.append('A school with this email already exists.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_form.html', {'school': school})
        school.name = name
        school.address = address
        school.email = email
        school.phone = phone
        if logo:
            school.logo = logo
        try:
            school.save()
            messages.success(request, 'School updated successfully!')
            return redirect('core:school_admin_list')
        except Exception as e:
            messages.error(request, f'Error updating school: {str(e)}')
            return render(request, 'core/school_form.html', {'school': school})
    return render(request, 'core/school_form.html', {'school': school})


@staff_member_required
def school_admin_delete(request, school_id):
    """Delete a school (admin only)"""
    school = get_object_or_404(School, id=school_id)
    if request.method == 'POST':
        school.delete()
        messages.success(request, 'School deleted successfully!')
        return redirect('core:school_admin_list')
    return redirect('core:school_admin_list')


@api_view(['POST'])
@permission_classes([IsSuperUser])
def api_school_create(request):
    """Create a new school via API (superuser only)"""
    serializer = SchoolSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        # On success, redirect to the school admin list page
        from django.shortcuts import redirect
        return redirect('core:school_admin_list')
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsSuperUser])
def api_school_update(request, pk):
    """Update a school via API (superuser only)"""
    try:
        school = School.objects.get(pk=pk)
    except School.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = SchoolSerializer(school, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def class_list(request):
    school = request.user.profile.school
    grades = Grade.objects.filter(school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        grade_id = request.POST.get('grade')
        class_teacher_id = request.POST.get('class_teacher', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not name:
            errors.append('Class name is required.')
        if not grade_id or not grade_id.isdigit():
            errors.append('Grade is required.')
        if SchoolClass.objects.filter(school=school, grade_id=grade_id, name=name).exists():
            errors.append('A class with this name already exists in the selected grade.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            SchoolClass.objects.create(
                school=school,
                grade_id=grade_id,
                name=name,
                class_teacher_id=class_teacher_id if class_teacher_id and class_teacher_id.isdigit() else None,
                description=description if description else None,
                is_active=is_active
            )
            messages.success(request, 'Class added successfully!')
            return redirect('core:class_list')
    
    classes = SchoolClass.objects.filter(school=school).select_related('grade', 'class_teacher')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    return render(request, 'core/class_list.html', {'classes': classes, 'grades': grades, 'teachers': teachers})

@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def class_add(request):
    school = request.user.profile.school
    # Debug: Check user's school and available grades
    school = request.user.profile.school
    print(f"User's school: {school.id} - {school.name}")
    grades = Grade.objects.filter(school=school)
    print(f"Grades for school {school.id}: {list(grades.values('id', 'name'))}")
    
    # If no grades for this school, show all grades for debugging
    if not grades.exists():
        print("No grades found for user's school, showing all grades for debugging")
        grades = Grade.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        grade_id = request.POST.get('grade')
        class_teacher_id = request.POST.get('class_teacher', '')
        description = request.POST.get('description', '').strip()
        errors = []
        if not name:
            errors.append('Class name is required.')
        if not grade_id or not grade_id.isdigit():
            errors.append('Grade is required.')
        if SchoolClass.objects.filter(school=school, grade_id=grade_id, name=name).exists():
            errors.append('A class with this name already exists in the selected grade.')
        if errors:
            for error in errors:
                messages.error(request, error)
            teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
            return render(request, 'core/class_form.html', {'grades': grades, 'teachers': teachers, 'post': request.POST, 'school_class': None})
        SchoolClass.objects.create(school=school, grade_id=grade_id, name=name, class_teacher_id=class_teacher_id if class_teacher_id and class_teacher_id.isdigit() else None, description=description)
        messages.success(request, 'Class added successfully!')
        return redirect('core:class_list')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    return render(request, 'core/class_form.html', {'grades': grades, 'teachers': teachers, 'post': {}, 'school_class': None})

@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def class_edit(request, class_id):
    school = request.user.profile.school
    school_class = get_object_or_404(SchoolClass, id=class_id, school=school)
    # Debug: Check user's school and available grades
    school = request.user.profile.school
    print(f"User's school: {school.id} - {school.name}")
    grades = Grade.objects.filter(school=school)
    print(f"Grades for school {school.id}: {list(grades.values('id', 'name'))}")
    
    # If no grades for this school, show all grades for debugging
    if not grades.exists():
        print("No grades found for user's school, showing all grades for debugging")
        grades = Grade.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        grade_id = request.POST.get('grade')
        class_teacher_id = request.POST.get('class_teacher', '')
        description = request.POST.get('description', '').strip()
        errors = []
        if not name:
            errors.append('Class name is required.')
        if not grade_id or not grade_id.isdigit():
            errors.append('Grade is required.')
        if SchoolClass.objects.filter(school=school, grade_id=grade_id, name=name).exclude(id=school_class.id).exists():
            errors.append('A class with this name already exists in the selected grade.')
        if errors:
            for error in errors:
                messages.error(request, error)
            teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
            return render(request, 'core/class_form.html', {'grades': grades, 'teachers': teachers, 'post': request.POST, 'school_class': school_class})
        school_class.name = name
        school_class.grade_id = grade_id
        school_class.class_teacher_id = class_teacher_id if class_teacher_id and class_teacher_id.isdigit() else None
        school_class.description = description
        school_class.save()
        messages.success(request, 'Class updated successfully!')
        return redirect('core:class_list')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    return render(request, 'core/class_form.html', {'grades': grades, 'teachers': teachers, 'school_class': school_class})

@login_required
@role_required('super_admin', 'school_admin')
def class_delete(request, class_id):
    school = request.user.profile.school
    school_class = get_object_or_404(SchoolClass, id=class_id, school=school)
    if request.method == 'POST':
        school_class.delete()
        messages.success(request, 'Class deleted successfully!')
        return redirect('core:class_list')
    return render(request, 'core/class_confirm_delete.html', {'school_class': school_class})


# Teacher Management Views
@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def teacher_detail(request, teacher_id):
    """View teacher details"""
    school = request.user.profile.school
    teacher = get_object_or_404(Teacher, id=teacher_id, school=school)
    
    # Get classes taught by this teacher
    classes_taught = SchoolClass.objects.filter(class_teacher=teacher, school=school).select_related('grade')
    
    context = {
        'teacher': teacher,
        'classes_taught': classes_taught,
    }
    return render(request, 'core/teacher_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def teacher_list(request):
    """List all teachers"""
    school = request.user.profile.school
    teachers = Teacher.objects.filter(school=school).order_by('first_name', 'last_name')
    
    # Filter by active status
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    if not show_inactive:
        teachers = teachers.filter(is_active=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(employee_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    context = {
        'teachers': teachers,
        'show_inactive': show_inactive,
        'search_query': search_query,
    }
    return render(request, 'core/teacher_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def teacher_add(request):
    """Add a new teacher"""
    school = request.user.profile.school
    from timetable.models import Subject as TimetableSubject
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', '')
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '') or None
        date_of_joining = request.POST.get('date_of_joining', '') or None
        qualification = request.POST.get('qualification', '').strip()
        specialization_list = request.POST.getlist('specialization')
        specialization = ', '.join([s.strip() for s in specialization_list if s.strip()]) or None
        is_active = request.POST.get('is_active') == 'on'
        photo = request.FILES.get('photo')
        
        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            subjects = TimetableSubject.objects.filter(school=school, is_active=True).order_by('name')
            return render(request, 'core/teacher_form.html', {'post': request.POST, 'teacher': None, 'subjects': subjects})
        
        # Generate employee ID
        employee_id = TeacherService.generate_employee_id(school)
        
        # Check for duplicate employee_id
        while Teacher.objects.filter(employee_id=employee_id).exists():
            employee_id = TeacherService.generate_employee_id(school)
        
        teacher = Teacher.objects.create(
            school=school,
            employee_id=employee_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender if gender else None,
            email=email if email else None,
            phone=phone if phone else None,
            address=address if address else None,
            date_of_birth=date_of_birth,
            date_of_joining=date_of_joining,
            qualification=qualification if qualification else None,
            specialization=specialization if specialization else None,
            photo=photo,
            is_active=is_active
        )
        
        messages.success(request, f'Teacher {teacher.full_name} added successfully!')
        return redirect('core:teacher_list')
    
    subjects = TimetableSubject.objects.filter(school=school, is_active=True).order_by('name')
    selected_specializations = []
    return render(request, 'core/teacher_form.html', {
        'post': {}, 
        'teacher': None, 
        'subjects': subjects,
        'selected_specializations': selected_specializations
    })


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def teacher_edit(request, teacher_id):
    """Edit a teacher"""
    school = request.user.profile.school
    teacher = get_object_or_404(Teacher, id=teacher_id, school=school)
    from timetable.models import Subject as TimetableSubject
    
    if request.method == 'POST':
        teacher.first_name = request.POST.get('first_name', '').strip()
        teacher.last_name = request.POST.get('last_name', '').strip()
        teacher.gender = request.POST.get('gender', '') or None
        teacher.email = request.POST.get('email', '').strip() or None
        teacher.phone = request.POST.get('phone', '').strip() or None
        teacher.address = request.POST.get('address', '').strip() or None
        teacher.date_of_birth = request.POST.get('date_of_birth', '') or None
        teacher.date_of_joining = request.POST.get('date_of_joining', '') or None
        teacher.qualification = request.POST.get('qualification', '').strip() or None
        specialization_list = request.POST.getlist('specialization')
        teacher.specialization = ', '.join([s.strip() for s in specialization_list if s.strip()]) or None
        teacher.is_active = request.POST.get('is_active') == 'on'
        
        if 'photo' in request.FILES:
            teacher.photo = request.FILES['photo']
        
        errors = []
        if not teacher.first_name:
            errors.append('First name is required.')
        if not teacher.last_name:
            errors.append('Last name is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            subjects = TimetableSubject.objects.filter(school=school, is_active=True).order_by('name')
            specialization_list = request.POST.getlist('specialization')
            selected_specializations = [s.strip() for s in specialization_list if s.strip()]
            return render(request, 'core/teacher_form.html', {
                'post': request.POST, 
                'teacher': teacher, 
                'subjects': subjects,
                'selected_specializations': selected_specializations
            })
        
        teacher.save()
        messages.success(request, f'Teacher {teacher.full_name} updated successfully!')
        return redirect('core:teacher_list')
    
    subjects = TimetableSubject.objects.filter(school=school, is_active=True).order_by('name')
    # Parse existing specializations from comma-separated string
    selected_specializations = []
    if teacher and teacher.specialization:
        selected_specializations = [s.strip() for s in teacher.specialization.split(',') if s.strip()]
    return render(request, 'core/teacher_form.html', {
        'post': {}, 
        'teacher': teacher, 
        'subjects': subjects,
        'selected_specializations': selected_specializations
    })


@login_required
@role_required('super_admin', 'school_admin')
def teacher_delete(request, teacher_id):
    """Delete a teacher"""
    school = request.user.profile.school
    teacher = get_object_or_404(Teacher, id=teacher_id, school=school)
    
    if request.method == 'POST':
        teacher_name = teacher.full_name
        teacher.delete()
        messages.success(request, f'Teacher {teacher_name} deleted successfully!')
        return redirect('core:teacher_list')
    
    return render(request, 'core/teacher_confirm_delete.html', {'teacher': teacher})


# User Management Views
@login_required
@role_required('super_admin', 'school_admin')
def user_list(request):
    """List all users"""
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    
    # If user is a school admin (not superadmin), filter users
    if not is_superadmin_user(request.user):
        # School admins can only see users from their school
        school = request.user.profile.school
        if school:
            users = users.filter(profile__school=school)
        else:
            users = User.objects.none()  # No school assigned, show no users
        
        # Exclude superadmin users from the list
        # Get all user IDs that have super_admin role
        superadmin_user_ids = User.objects.filter(
            Q(is_superuser=True) | 
            Q(profile__roles__name='super_admin')
        ).values_list('id', flat=True).distinct()
        
        # Exclude those users
        users = users.exclude(id__in=superadmin_user_ids)
    
    return render(request, 'core/users/user_list.html', {
        'users': users,
        'is_superadmin': is_superadmin_user(request.user)
    })


@login_required
@role_required('super_admin', 'school_admin')
def user_create(request):
    """Create a new user with role assignment"""
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST, current_user=request.user)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                # Create user first
                user = user_form.save()
                
                # For school admins, ensure the school is set to their school
                if not is_superadmin_user(request.user):
                    if hasattr(request.user, 'profile') and request.user.profile.school:
                        # Override school assignment to ensure it's the admin's school
                        profile_form.cleaned_data['school'] = request.user.profile.school
                
                # Check if profile already exists
                if hasattr(user, 'profile'):
                    profile = user.profile
                    # Update existing profile
                    for field, value in profile_form.cleaned_data.items():
                        if field != 'roles':  # Skip roles field
                            setattr(profile, field, value)
                    profile.save()
                    # Update roles separately
                    profile.roles.set(profile_form.cleaned_data['roles'])
                else:
                    # Create new profile
                    profile = profile_form.save(commit=False)
                    profile.user = user
                    # Ensure school is set correctly for school admins
                    if not is_superadmin_user(request.user):
                        if hasattr(request.user, 'profile') and request.user.profile.school:
                            profile.school = request.user.profile.school
                    profile.save()
                    # Set roles after saving
                    profile.roles.set(profile_form.cleaned_data['roles'])
                
                messages.success(request, f"User {user.username} created successfully!")
                return redirect('core:user_list')
            except Exception as e:
                messages.error(request, f"Error creating user: {str(e)}")
        else:
            if 'password1' in user_form.errors or 'password2' in user_form.errors:
                messages.error(request, "Please provide a valid password and confirm it.")
            else:
                messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserForm()
        profile_form = UserProfileForm(current_user=request.user)
    
    return render(request, 'core/users/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': 'Create New User',
        'user': None,
        'is_superadmin': is_superadmin_user(request.user)
    })


@login_required
@role_required('super_admin', 'school_admin')
def user_edit(request, user_id):
    """Edit an existing user"""
    user_to_edit = get_object_or_404(User, id=user_id)
    
    # Prevent school admins from editing superadmin accounts
    if not is_superadmin_user(request.user) and is_superadmin_user(user_to_edit):
        messages.error(request, 'You do not have permission to edit superadmin accounts.')
        raise PermissionDenied("School admins cannot edit superadmin accounts.")
    
    # If school admin, ensure they can only edit users from their school
    if not is_superadmin_user(request.user):
        school = request.user.profile.school
        if not school or user_to_edit.profile.school != school:
            messages.error(request, 'You can only edit users from your school.')
            raise PermissionDenied("You can only edit users from your school.")
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user_to_edit)
        profile_form = UserProfileForm(request.POST, instance=user_to_edit.profile, current_user=request.user)
        
        if user_form.is_valid() and profile_form.is_valid():
            # Additional security check before saving
            if not is_superadmin_user(request.user) and is_superadmin_user(user_to_edit):
                messages.error(request, 'You do not have permission to edit superadmin accounts.')
                raise PermissionDenied("School admins cannot edit superadmin accounts.")
            
            # Check if school admin is trying to assign super_admin role
            if not is_superadmin_user(request.user):
                selected_roles = profile_form.cleaned_data.get('roles', [])
                if any(role.name == 'super_admin' for role in selected_roles):
                    messages.error(request, 'You do not have permission to assign the super_admin role.')
                    raise PermissionDenied("School admins cannot assign super_admin role.")
                
                # Prevent school admins from changing school assignment
                # Force school to remain as the admin's school
                admin_school = request.user.profile.school
                if admin_school:
                    profile_form.cleaned_data['school'] = admin_school
                    # Also check if they somehow tried to change it
                    original_school = user_to_edit.profile.school
                    if original_school and original_school != admin_school:
                        messages.error(request, 'You do not have permission to change the school assignment. Only superadmins can reassign users to different schools.')
                        raise PermissionDenied("School admins cannot change school assignment.")
            
            user_form.save()
            profile_form.save()
            
            messages.success(request, f"User {user_to_edit.username} updated successfully!")
            return redirect('core:user_list')
    else:
        user_form = UserEditForm(instance=user_to_edit)
        profile_form = UserProfileForm(instance=user_to_edit.profile, current_user=request.user)
    
    return render(request, 'core/users/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': f'Edit User: {user_to_edit.username}',
        'user': user_to_edit,
        'is_superadmin': is_superadmin_user(request.user)
    })


@login_required
@role_required('super_admin', 'school_admin')
def user_delete(request, user_id):
    """Delete a user"""
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # Prevent school admins from deleting superadmin accounts
    if not is_superadmin_user(request.user) and is_superadmin_user(user_to_delete):
        messages.error(request, 'You do not have permission to delete superadmin accounts.')
        raise PermissionDenied("School admins cannot delete superadmin accounts.")
    
    # If school admin, ensure they can only delete users from their school
    if not is_superadmin_user(request.user):
        school = request.user.profile.school
        if not school or user_to_delete.profile.school != school:
            messages.error(request, 'You can only delete users from your school.')
            raise PermissionDenied("You can only delete users from your school.")
    
    # Prevent users from deleting themselves
    if request.user.id == user_to_delete.id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('core:user_list')
    
    if request.method == 'POST':
        # Additional security check before deleting
        if not is_superadmin_user(request.user) and is_superadmin_user(user_to_delete):
            messages.error(request, 'You do not have permission to delete superadmin accounts.')
            raise PermissionDenied("School admins cannot delete superadmin accounts.")
        
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"User {username} deleted successfully!")
        return redirect('core:user_list')
    
    return render(request, 'core/users/user_confirm_delete.html', {'user': user_to_delete})


# Role Management Views
@login_required
@role_required('super_admin', 'school_admin')
def role_list(request):
    """List all roles"""
    roles = Role.objects.all()
    return render(request, 'core/roles/role_list.html', {'roles': roles})


@login_required
@role_required('super_admin', 'school_admin')
def role_permissions(request, role_id):
    """Manage permissions for a role"""
    role = get_object_or_404(Role, id=role_id)
    
    if request.method == 'POST':
        permission_ids = request.POST.getlist('permissions')
        role.permissions.clear()
        role.permissions.add(*Permission.objects.filter(id__in=permission_ids))
        messages.success(request, 'Role permissions updated successfully.')
        return redirect('core:role_list')
    
    # Get all permissions and group them by resource type
    all_permissions = Permission.objects.all().order_by('resource_type', 'permission_type')
    grouped_permissions = {}
    
    # Get the role's current permissions
    role_permissions = set(role.permissions.values_list('id', flat=True))
    
    # Group permissions by resource type
    for perm in all_permissions:
        if perm.resource_type not in grouped_permissions:
            grouped_permissions[perm.resource_type] = {
                'display_name': perm.resource_type.replace('_', ' ').title(),
                'items': []
            }
        
        # Add permission with checked status
        grouped_permissions[perm.resource_type]['items'].append({
            'id': perm.id,
            'permission_type': perm.permission_type,
            'resource_type': perm.resource_type,
            'codename': f"{perm.permission_type}_{perm.resource_type}",
            'checked': perm.id in role_permissions
        })
    
    return render(request, 'core/roles/role_permissions.html', {
        'role': role,
        'grouped_permissions': grouped_permissions
    })
