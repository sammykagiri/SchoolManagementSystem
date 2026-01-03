from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import models
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from .models import (
    School, Grade, Term, FeeCategory, TransportRoute, Student, FeeStructure, StudentFee, SchoolClass,
    AcademicYear, Section, StudentClassEnrollment, PromotionLog
)
from payments.models import Payment
from timetable.models import Teacher
from rest_framework import viewsets, permissions
from .serializers import (
    SchoolSerializer, GradeSerializer, TermSerializer, FeeCategorySerializer,
    TransportRouteSerializer, StudentSerializer, FeeStructureSerializer, StudentFeeSerializer, SchoolClassSerializer
)
from .forms import StudentForm, UserForm, UserEditForm, UserProfileForm, ParentRegistrationForm, ParentEditForm
from .models import Role, Permission, Parent
from django.contrib.auth.models import User
import json
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework import permissions
# Import existing services from services.py file
# We need to import it as a submodule to handle relative imports
import sys
import importlib.util
from pathlib import Path

# Ensure 'core' is in sys.modules for relative imports
if 'core' not in sys.modules:
    import core
    sys.modules['core'] = core

# Load services.py as a module
services_file = Path(__file__).parent / 'services.py'
spec = importlib.util.spec_from_file_location("core.services_file", str(services_file))
services_module = importlib.util.module_from_spec(spec)
sys.modules['core.services_file'] = services_module
spec.loader.exec_module(services_module)

DashboardService = services_module.DashboardService
StudentService = services_module.StudentService
TeacherService = services_module.TeacherService

# Import new promotion service from services package
from .services.promotion_service import PromotionService, PromotionPreview, PromotionResult
from .decorators import role_required
# Import promotion views
from .views_promotion import (
    promotion_wizard_step1, promotion_wizard_step2, promotion_preview,
    promotion_confirm, promotion_history
)
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
    # Ensure user has a profile
    from .models import UserProfile
    if not hasattr(request.user, 'profile'):
        # Create a profile if it doesn't exist
        default_school = School.objects.first()
        UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'school': default_school}
        )
        request.user.refresh_from_db()
    
    school = request.user.profile.school
    
    # If user doesn't have a school assigned and is not superadmin, redirect
    # (This should be caught by decorator, but handle it here as well for safety)
    if not school:
        if is_superadmin_user(request.user):
            # Superadmin without school - redirect to manage schools
            messages.info(request, 'Please assign yourself to a school or manage schools.')
            return redirect('core:school_admin_list')
        else:
            messages.error(request, 'You must be assigned to a school to access the dashboard.')
            return redirect('core:dashboard')
    
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
            Q(upi__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(parent_name__icontains=search_query) |
            Q(parent_phone__icontains=search_query)
        )
    
    # Filter by grade
    grade_filter = request.GET.get('grade', '')
    if grade_filter:
        students = students.filter(grade_id=grade_filter)
    
    # Filter by class
    class_filter = request.GET.get('class', '')
    if class_filter:
        students = students.filter(school_class_id=class_filter)
    
    # Order by active status first, then by name
    students = students.order_by('-is_active', 'first_name', 'middle_name', 'last_name')
    
    # Pagination
    paginator = Paginator(students, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get grades and classes for the school
    school = request.user.profile.school
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    
    # Check if both grades and classes exist (required for adding students)
    can_add_student = grades.exists() and classes.exists()
    
    context = {
        'page_obj': page_obj,
        'grades': grades,
        'classes': classes,
        'can_add_student': can_add_student,
        'search_query': search_query,
        'grade_filter': grade_filter,
        'class_filter': class_filter,
        'show_inactive': show_inactive,
    }
    
    return render(request, 'core/student_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def student_detail(request, student_id):
    """Student detail view"""
    school = request.user.profile.school
    student = get_object_or_404(
        Student.objects.select_related('grade', 'transport_route', 'school_class', 'school_class__class_teacher').prefetch_related('parents__user'),
        student_id=student_id,
        school=school
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
    
    # Check if grades and classes exist
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    
    if not grades.exists():
        messages.error(request, 'No grades found. Please create at least one grade before adding students.')
        return redirect('core:student_list')
    
    if not classes.exists():
        messages.error(request, 'No classes found. Please create at least one class before adding students.')
        return redirect('core:student_list')
    
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
                
                # Save many-to-many relationships (parents, optional_fee_categories)
                form.save_m2m()
                
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
                # Check if transport route changed
                old_route = student.transport_route
                new_route = form.cleaned_data.get('transport_route')  # This is already a TransportRoute object or None
                
                # Compare by ID to handle None cases
                old_route_id = old_route.id if old_route else None
                new_route_id = new_route.id if new_route else None
                route_changed = (old_route_id != new_route_id)
                
                # Check if optional fees changed (BEFORE saving)
                old_optional_fees = set(student.optional_fee_categories.values_list('id', flat=True))
                new_optional_fees_raw = request.POST.getlist('optional_fee_categories')
                new_optional_fees = set([int(f) for f in new_optional_fees_raw if f and f.isdigit()])
                optional_fees_changed = (old_optional_fees != new_optional_fees)
                
                # Check if user selected terms to apply transport fee changes to (BEFORE saving)
                apply_to_terms_raw = request.POST.getlist('apply_transport_to_terms')
                # Filter out empty strings and convert to integers
                apply_to_terms = [int(t) for t in apply_to_terms_raw if t and t.isdigit()]
                
                # Check if user selected terms to apply optional fee changes to (BEFORE saving)
                apply_optional_fees_to_terms_raw = request.POST.getlist('apply_optional_fees_to_terms')
                # Filter out empty strings and convert to integers
                apply_optional_fees_to_terms = [int(t) for t in apply_optional_fees_to_terms_raw if t and t.isdigit()]
                
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Student update - Route changed: {route_changed}, Old route ID: {old_route_id}, New route ID: {new_route_id}")
                logger.debug(f"Student update - Apply to terms raw: {apply_to_terms_raw}, Processed: {apply_to_terms}")
                
                # Save the student
                form.save()
                
                # Save many-to-many relationships (parents, optional_fee_categories)
                form.save_m2m()

                # Refresh student from database to get updated transport_route
                student.refresh_from_db()

                # Process fees if terms were selected (user explicitly selected terms via modal)
                # The modal only shows when route changes, so if terms are selected, route must have changed
                if apply_to_terms:
                    # Process fees - if terms are selected, it means modal was shown, which only happens on route change
                    logger.debug(f"Processing transport fees for {len(apply_to_terms)} term(s)")
                    # Get transport category
                    transport_category = FeeCategory.objects.filter(
                        school=school,
                        category_type='transport'
                    ).first()
                    
                    if transport_category:
                        updated_count = 0
                        deleted_count = 0
                        
                        for term_id in apply_to_terms:
                            try:
                                term = Term.objects.get(id=term_id, school=school)
                                
                                # Use the updated student.transport_route after save
                                current_route = student.transport_route
                                
                                if current_route and current_route.is_currently_active():
                                    # Add or update transport fee
                                    transport_amount = current_route.base_fare
                                    student_fee, created = StudentFee.objects.get_or_create(
                                        school=school,
                                        student=student,
                                        term=term,
                                        fee_category=transport_category,
                                        defaults={
                                            'amount_charged': transport_amount,
                                            'due_date': term.end_date,
                                        }
                                    )
                                    
                                    if not created:
                                        student_fee.amount_charged = transport_amount
                                        student_fee.save()
                                    
                                    updated_count += 1
                                else:
                                    # Remove transport fee (route was removed or is inactive)
                                    deleted = StudentFee.objects.filter(
                                        school=school,
                                        student=student,
                                        term=term,
                                        fee_category=transport_category
                                    ).delete()
                                    
                                    if deleted[0] > 0:
                                        deleted_count += deleted[0]
                            except Term.DoesNotExist:
                                continue
                            except Exception as e:
                                # Log any errors but continue processing other terms
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.error(f"Error processing term {term_id}: {str(e)}")
                                continue
                        
                        if updated_count > 0 or deleted_count > 0:
                            fee_msg = []
                            if updated_count > 0:
                                fee_msg.append(f'{updated_count} term(s) updated')
                            if deleted_count > 0:
                                fee_msg.append(f'{deleted_count} transport fee(s) removed')
                            messages.success(
                                request, 
                                f'Student {student.full_name} updated successfully. Transport fees: {", ".join(fee_msg)}.'
                            )
                        else:
                            messages.warning(request, f'Student {student.full_name} updated successfully, but no transport fees were created or updated. Please check if the transport route is active and the terms are valid.')
                    else:
                        messages.warning(request, f'Student {student.full_name} updated successfully, but transport fee category not found. Please create a transport fee category first.')
                elif route_changed:
                    # Route changed but no terms selected - just update student
                    messages.success(request, f'Student {student.full_name} updated successfully. Transport route changed but no terms were selected for fee updates.')
                
                # Process optional fee changes if terms were selected
                if apply_optional_fees_to_terms and optional_fees_changed:
                    logger.info(f"Processing optional fee changes for {len(apply_optional_fees_to_terms)} term(s)")
                    added_count = 0
                    removed_count = 0
                    
                    # Get fee structures for the selected terms and grades
                    fee_structures = FeeStructure.objects.filter(
                        school=school,
                        term_id__in=apply_optional_fees_to_terms,
                        grade=student.grade,
                        fee_category_id__in=new_optional_fees.union(old_optional_fees),
                        is_active=True
                    ).select_related('fee_category', 'term')
                    
                    for term_id in apply_optional_fees_to_terms:
                        try:
                            term = Term.objects.get(id=term_id, school=school)
                            
                            # Get fee structures for this term
                            term_structures = fee_structures.filter(term_id=term_id)
                            
                            # Add fees for newly selected optional categories
                            added_categories = new_optional_fees - old_optional_fees
                            for category_id in added_categories:
                                structure = term_structures.filter(fee_category_id=category_id).first()
                                if structure:
                                    student_fee, created = StudentFee.objects.get_or_create(
                                        school=school,
                                        student=student,
                                        term=term,
                                        fee_category_id=category_id,
                                        defaults={
                                            'amount_charged': structure.amount,
                                            'due_date': term.end_date,
                                        }
                                    )
                                    if created:
                                        added_count += 1
                            
                            # Remove fees for deselected optional categories
                            removed_categories = old_optional_fees - new_optional_fees
                            for category_id in removed_categories:
                                deleted = StudentFee.objects.filter(
                                    school=school,
                                    student=student,
                                    term=term,
                                    fee_category_id=category_id
                                ).delete()
                                if deleted[0] > 0:
                                    removed_count += deleted[0]
                        except Term.DoesNotExist:
                            continue
                        except Exception as e:
                            logger.error(f"Error processing optional fees for term {term_id}: {str(e)}")
                            continue
                    
                    if added_count > 0 or removed_count > 0:
                        fee_msg = []
                        if added_count > 0:
                            fee_msg.append(f'{added_count} optional fee(s) added')
                        if removed_count > 0:
                            fee_msg.append(f'{removed_count} optional fee(s) removed')
                        messages.success(
                            request,
                            f'Student {student.full_name} updated successfully. Optional fees: {", ".join(fee_msg)}.'
                        )
                    elif optional_fees_changed and not apply_optional_fees_to_terms:
                        # Optional fees changed but no terms selected
                        messages.success(request, f'Student {student.full_name} updated successfully. Optional fee categories changed but no terms were selected for fee updates.')
                
                if not route_changed and not (apply_optional_fees_to_terms and optional_fees_changed):
                    # No route change and no optional fee changes processed
                    messages.success(request, f'Student {student.full_name} updated successfully.')
                
                return redirect('core:student_detail', student_id=student.student_id)
            except Exception as e:
                messages.error(request, f'Error updating student: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentForm(instance=student, school=school)
    
    # Get terms for transport fee update selection
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    
    context = {
        'form': form,
        'student': student,
        'title': 'Update Student',
        'terms': terms,
    }
    return render(request, 'core/student_form_new.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def student_delete(request, student_id):
    """Delete student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
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
def term_generate(request):
    """Generate multiple terms generically for an academic year"""
    school = request.user.profile.school
    from datetime import date
    from django.utils import timezone
    
    # Determine default academic year
    current_year = timezone.now().year
    existing_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct()
    
    # Check if current year exists, if so default to next year
    current_year_str = f"{current_year}-{current_year + 1}"
    next_year_str = f"{current_year + 1}-{current_year + 2}"
    default_year = next_year_str if current_year_str in existing_years else current_year_str
    
    if request.method == 'POST':
        academic_year = request.POST.get('academic_year', '').strip()
        num_terms = request.POST.get('num_terms', '')
        
        errors = []
        
        # Validate academic year
        if not academic_year:
            errors.append('Academic year is required.')
        
        # Validate number of terms
        if not num_terms or not num_terms.isdigit():
            errors.append('Number of terms is required and must be a valid number.')
        else:
            num_terms = int(num_terms)
            if num_terms < 1 or num_terms > 9:  # Limited by term_number max_length=1
                errors.append('Number of terms must be between 1 and 9.')
        
        # Collect term dates
        term_dates = []
        if num_terms and isinstance(num_terms, int):
            for i in range(1, num_terms + 1):
                start_date = request.POST.get(f'term_{i}_start_date', '').strip()
                end_date = request.POST.get(f'term_{i}_end_date', '').strip()
                
                if not start_date:
                    errors.append(f'Start date for Term {i} is required.')
                if not end_date:
                    errors.append(f'End date for Term {i} is required.')
                
                if start_date and end_date:
                    try:
                        from datetime import datetime
                        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                        
                        if start_dt > end_dt:
                            errors.append(f'Term {i}: Start date cannot be after end date.')
                        
                        term_dates.append({
                            'term_number': str(i),
                            'start_date': start_date,
                            'end_date': end_date,
                            'start_dt': start_dt,
                            'end_dt': end_dt,
                        })
                    except ValueError:
                        errors.append(f'Term {i}: Invalid date format.')
        
        # Check for overlapping dates
        if not errors and len(term_dates) > 1:
            for i, term1 in enumerate(term_dates):
                for j, term2 in enumerate(term_dates[i+1:], start=i+1):
                    if (term1['start_dt'] <= term2['end_dt'] and term1['end_dt'] >= term2['start_dt']):
                        errors.append(f'Term {i+1} and Term {j+1} have overlapping dates.')
        
        # Check if terms already exist
        if not errors:
            existing_terms = []
            for term_data in term_dates:
                if Term.objects.filter(school=school, term_number=term_data['term_number'], academic_year=academic_year).exists():
                    existing_terms.append(f"Term {term_data['term_number']}")
            
            if existing_terms:
                errors.append(f'The following terms already exist for {academic_year}: {", ".join(existing_terms)}.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            # Re-render form with errors - preserve term dates
            term_dates_json = []
            for td in term_dates:
                term_dates_json.append({
                    'term_number': td['term_number'],
                    'start_date': td['start_date'],
                    'end_date': td['end_date'],
                })
            
            context = {
                'academic_year': request.POST.get('academic_year', default_year),
                'num_terms': request.POST.get('num_terms', ''),
                'term_dates': term_dates_json,
            }
            return render(request, 'core/term_generate.html', context)
        
        # Generate terms
        created_terms = []
        skipped_terms = []
        
        term_name_map = {
            '1': 'First Term', '2': 'Second Term', '3': 'Third Term',
            '4': 'Fourth Term', '5': 'Fifth Term', '6': 'Sixth Term',
            '7': 'Seventh Term', '8': 'Eighth Term', '9': 'Ninth Term'
        }
        
        for term_data in term_dates:
            term_number = term_data['term_number']
            term_name = term_name_map.get(term_number, f'Term {term_number}')
            
            # Check if it already exists
            if Term.objects.filter(school=school, term_number=term_number, academic_year=academic_year).exists():
                skipped_terms.append(f"Term {term_number}")
            else:
                try:
                    Term.objects.create(
                        school=school,
                        name=term_name,
                        term_number=term_number,
                        academic_year=academic_year,
                        start_date=term_data['start_date'],
                        end_date=term_data['end_date'],
                        is_active=False  # Default to inactive, user can activate later
                    )
                    created_terms.append(f"Term {term_number}")
                except Exception as e:
                    from django.db import IntegrityError
                    if isinstance(e, IntegrityError):
                        skipped_terms.append(f"Term {term_number}")
                    else:
                        messages.error(request, f'Error creating Term {term_number}: {str(e)}')
        
        # Build appropriate messages
        if created_terms and skipped_terms:
            messages.success(request, f'Successfully created {len(created_terms)} term(s): {", ".join(created_terms)}.')
            messages.info(request, f'Skipped {len(skipped_terms)} term(s) that already exist: {", ".join(skipped_terms)}.')
        elif created_terms:
            messages.success(request, f'Successfully created {len(created_terms)} term(s): {", ".join(created_terms)}.')
        elif skipped_terms:
            messages.warning(request, f'All {len(skipped_terms)} term(s) already exist. No new terms were created.')
        else:
            messages.warning(request, 'No terms were created.')
        
        return redirect('core:term_list')
    
    # GET request - show the form
    return render(request, 'core/term_generate.html', {
        'academic_year': default_year,
        'term_dates': [],
    })


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
    ).order_by('term__academic_year', 'term__term_number', 'grade__name', 'fee_category__name')
    
    # Filter by academic year, grade, and term
    academic_year_filter = request.GET.get('academic_year', '')
    grade_filter = request.GET.get('grade', '')
    term_filter = request.GET.get('term', '')
    
    if academic_year_filter:
        fee_structures = fee_structures.filter(term__academic_year=academic_year_filter)
    if grade_filter:
        fee_structures = fee_structures.filter(grade_id=grade_filter)
    if term_filter:
        fee_structures = fee_structures.filter(term_id=term_filter)
    
    grades = Grade.objects.filter(school=school)
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    fee_categories = FeeCategory.objects.filter(school=school)
    
    # Get unique academic years from terms
    academic_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    # Get grades that have fee structures (for filtering)
    grades_with_structures = Grade.objects.filter(
        school=school,
        fee_structures__is_active=True
    ).distinct().order_by('name')
    
    # Get terms that have fee structures (for filtering)
    terms_with_structures = Term.objects.filter(
        school=school,
        fee_structures__is_active=True
    ).distinct().order_by('-academic_year', '-term_number')
    
    # Get terms grouped by academic year for JavaScript filtering
    import json
    terms_by_year = {}
    for term in terms:
        if term.academic_year not in terms_by_year:
            terms_by_year[term.academic_year] = []
        terms_by_year[term.academic_year].append({
            'id': term.id,
            'term_number': term.term_number,
            'academic_year': term.academic_year
        })
    terms_by_year_json = json.dumps(terms_by_year)
    
    # Get all terms for JavaScript (when no year filter)
    all_terms_json = json.dumps([{
        'id': term.id,
        'term_number': term.term_number,
        'academic_year': term.academic_year
    } for term in terms_with_structures])
    
    context = {
        'fee_structures': fee_structures,
        'grades': grades,
        'terms': terms,
        'fee_categories': fee_categories,
        'academic_years': academic_years,
        'terms_by_year_json': terms_by_year_json,
        'all_terms_json': all_terms_json,
        'grades_with_structures': grades_with_structures,
        'terms_with_structures': terms_with_structures,
        'academic_year_filter': academic_year_filter,
        'grade_filter': grade_filter,
        'term_filter': term_filter,
    }
    return render(request, 'core/fee_structure_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_structure_edit(request, fee_structure_id):
    """Edit a fee structure"""
    school = request.user.profile.school
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id, school=school)
    
    if request.method == 'POST':
        grade_id = request.POST.get('grade')
        term_id = request.POST.get('term')
        fee_category_id = request.POST.get('fee_category')
        amount = request.POST.get('amount')
        
        try:
            fee_structure.grade_id = grade_id
            fee_structure.term_id = term_id
            fee_structure.fee_category_id = fee_category_id
            fee_structure.amount = amount
            fee_structure.save()
            messages.success(request, 'Fee structure updated successfully.')
            return redirect('core:fee_structure_list')
        except Exception as e:
            messages.error(request, f'Error updating fee structure: {str(e)}')
    
    grades = Grade.objects.filter(school=school)
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    fee_categories = FeeCategory.objects.filter(school=school)
    
    context = {
        'fee_structure': fee_structure,
        'grades': grades,
        'terms': terms,
        'fee_categories': fee_categories,
    }
    return render(request, 'core/fee_structure_form.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_structure_delete(request, fee_structure_id):
    """Delete a fee structure"""
    school = request.user.profile.school
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id, school=school)
    
    if request.method == 'POST':
        try:
            fee_structure.delete()
            messages.success(request, 'Fee structure deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting fee structure: {str(e)}')
        return redirect('core:fee_structure_list')
    
    context = {
        'fee_structure': fee_structure,
    }
    return render(request, 'core/fee_structure_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_category_list(request):
    """List and manage fee categories"""
    school = request.user.profile.school
    fee_categories = FeeCategory.objects.filter(school=school).order_by('category_type', 'name')
    
    context = {
        'fee_categories': fee_categories,
        'category_choices': FeeCategory.CATEGORY_CHOICES,
    }
    return render(request, 'core/fee_category_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_category_add(request):
    """Add a new fee category"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_type = request.POST.get('category_type', '').strip()
        description = request.POST.get('description', '').strip()
        is_optional = bool(request.POST.get('is_optional'))
        
        errors = []
        if not name:
            errors.append('Fee category name is required.')
        if not category_type:
            errors.append('Category type is required.')
        
        # Check for duplicates
        if name and category_type:
            if FeeCategory.objects.filter(school=school, name=name, category_type=category_type).exists():
                errors.append('A fee category with this name and type already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/fee_category_form.html', {
                'category': None,
                'post': request.POST,
                'category_choices': FeeCategory.CATEGORY_CHOICES,
            })
        
        try:
            FeeCategory.objects.create(
                school=school,
                name=name,
                category_type=category_type,
                description=description,
                is_optional=is_optional,
                apply_by_default=apply_by_default if is_optional else False  # Only apply if optional
            )
            messages.success(request, 'Fee category created successfully!')
            return redirect('core:fee_category_list')
        except Exception as e:
            messages.error(request, f'Error creating fee category: {str(e)}')
            return render(request, 'core/fee_category_form.html', {
                'category': None,
                'post': request.POST,
                'category_choices': FeeCategory.CATEGORY_CHOICES,
            })
    
    return render(request, 'core/fee_category_form.html', {
        'category': None,
        'post': {},
        'category_choices': FeeCategory.CATEGORY_CHOICES,
    })


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_category_edit(request, category_id):
    """Edit an existing fee category"""
    school = request.user.profile.school
    category = get_object_or_404(FeeCategory, id=category_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_type = request.POST.get('category_type', '').strip()
        description = request.POST.get('description', '').strip()
        is_optional = bool(request.POST.get('is_optional'))
        apply_by_default = bool(request.POST.get('apply_by_default'))
        
        errors = []
        if not name:
            errors.append('Fee category name is required.')
        if not category_type:
            errors.append('Category type is required.')
        
        # Check for duplicates (excluding current category)
        if name and category_type:
            if FeeCategory.objects.filter(school=school, name=name, category_type=category_type).exclude(id=category.id).exists():
                errors.append('A fee category with this name and type already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/fee_category_form.html', {
                'category': category,
                'post': request.POST,
                'category_choices': FeeCategory.CATEGORY_CHOICES,
            })
        
        try:
            category.name = name
            category.category_type = category_type
            category.description = description
            category.is_optional = is_optional
            category.apply_by_default = apply_by_default if is_optional else False  # Only apply if optional
            category.save()
            messages.success(request, 'Fee category updated successfully!')
            return redirect('core:fee_category_list')
        except Exception as e:
            messages.error(request, f'Error updating fee category: {str(e)}')
            return render(request, 'core/fee_category_form.html', {
                'category': category,
                'post': request.POST,
                'category_choices': FeeCategory.CATEGORY_CHOICES,
            })
    
    return render(request, 'core/fee_category_form.html', {
        'category': category,
        'post': {},
        'category_choices': FeeCategory.CATEGORY_CHOICES,
    })


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_category_delete(request, category_id):
    """Delete a fee category"""
    school = request.user.profile.school
    category = get_object_or_404(FeeCategory, id=category_id, school=school)
    
    if request.method == 'POST':
        is_transport = category.category_type == 'transport'
        
        # For transport categories, allow deletion (they're managed via routes now)
        # But clean up related fee structures and warn about student fees
        if is_transport:
            # Delete related fee structures (transport is route-based now)
            fee_structures_count = FeeStructure.objects.filter(fee_category=category).count()
            if fee_structures_count > 0:
                FeeStructure.objects.filter(fee_category=category).delete()
                messages.warning(request, f'Deleted {fee_structures_count} fee structure(s) associated with this transport category.')
            
            # Check if category is used in student fees
            student_fees_count = StudentFee.objects.filter(fee_category=category).count()
            if student_fees_count > 0:
                messages.error(
                    request, 
                    f'Cannot delete "{category.name}" because it is used in {student_fees_count} student fee record(s). '
                    'Please remove or update these student fees first, or they will continue to reference a deleted category.'
                )
                return redirect('core:fee_category_list')
        else:
            # For non-transport categories, check both fee structures and student fees
            if FeeStructure.objects.filter(fee_category=category).exists():
                messages.error(request, f'Cannot delete "{category.name}" because it is used in fee structures.')
                return redirect('core:fee_category_list')
            
            if StudentFee.objects.filter(fee_category=category).exists():
                messages.error(request, f'Cannot delete "{category.name}" because it is used in student fees.')
                return redirect('core:fee_category_list')
        
        try:
            category.delete()
            messages.success(request, 'Fee category deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting fee category: {str(e)}')
        
        return redirect('core:fee_category_list')
    
    # Show confirmation page
    context = {
        'category': category,
    }
    return render(request, 'core/fee_category_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def generate_student_fees(request):
    """Generate student fees - create fee structures for terms and grades"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Get selected term
        term_id = request.POST.get('term_id')
        if not term_id:
            messages.error(request, 'Please select a term.')
            return redirect('core:generate_student_fees')
        
        term = get_object_or_404(Term, id=term_id, school=school)
        
        # Process fee amounts for each grade and category
        created_count = 0
        updated_count = 0
        
        # Get all grades and fee categories
        grades = Grade.objects.filter(school=school)
        fee_categories = FeeCategory.objects.filter(school=school)
        
        for grade in grades:
            for category in fee_categories:
                # Get amount from form (format: amount_{term_id}_{grade_id}_{category_id})
                field_name = f'amount_{term.id}_{grade.id}_{category.id}'
                amount_str = request.POST.get(field_name, '').strip()
                
                if amount_str:
                    try:
                        amount = float(amount_str)
                        if amount < 0:
                            continue
                        
                        # Create or update fee structure
                        fee_structure, created = FeeStructure.objects.get_or_create(
                            school=school,
                            grade=grade,
                            term=term,
                            fee_category=category,
                            defaults={'amount': amount, 'is_active': True}
                        )
                        
                        if not created:
                            fee_structure.amount = amount
                            fee_structure.is_active = True
                            fee_structure.save()
                            updated_count += 1
                        else:
                            created_count += 1
                    except ValueError:
                        continue
        
        if created_count > 0 or updated_count > 0:
            messages.success(
                request, 
                f'Successfully saved {created_count} new and {updated_count} updated fee structures for {term.academic_year} - Term {term.term_number}.'
            )
        else:
            messages.info(request, 'No fee structures were saved. Please enter amounts for at least one grade and category.')
        
        return redirect('core:generate_student_fees')
    
    # GET request - display form
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    grades = Grade.objects.filter(school=school).order_by('name')
    # Exclude transport categories - transport fees are route-based
    fee_categories = FeeCategory.objects.filter(school=school).exclude(category_type='transport').order_by('category_type', 'name')
    
    # Get existing fee structures for display (will be loaded via JavaScript when term is selected)
    # We'll pass this as JSON for JavaScript to use
    existing_structures_json = {}
    if terms.exists():
        structures = FeeStructure.objects.filter(
            school=school,
            term__in=terms
        ).select_related('term', 'grade', 'fee_category')
        
        for structure in structures:
            term_key = str(structure.term.id)
            if term_key not in existing_structures_json:
                existing_structures_json[term_key] = {}
            grade_key = str(structure.grade.id)
            if grade_key not in existing_structures_json[term_key]:
                existing_structures_json[term_key][grade_key] = {}
            category_key = str(structure.fee_category.id)
            existing_structures_json[term_key][grade_key][category_key] = float(structure.amount)
    
    context = {
        'terms': terms,
        'grades': grades,
        'fee_categories': fee_categories,
        'existing_structures_json': json.dumps(existing_structures_json)
    }
    return render(request, 'core/generate_student_fees.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def get_previous_term_fees(request):
    """API endpoint to get fee structures from a previous term for copying"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    term_id = request.GET.get('term_id')
    if not term_id:
        return JsonResponse({'error': 'Term ID is required'}, status=400)
    
    school = request.user.profile.school
    term = get_object_or_404(Term, id=term_id, school=school)
    
    # Get fee structures for this term (exclude transport - it's route-based)
    fee_structures = FeeStructure.objects.filter(
        school=school,
        term=term,
        is_active=True
    ).exclude(fee_category__category_type='transport').select_related('grade', 'fee_category')
    
    # Format as {grade_id}_{category_id: amount}
    data = {}
    for structure in fee_structures:
        key = f"{structure.grade.id}_{structure.fee_category.id}"
        data[key] = float(structure.amount)
    
    return JsonResponse({'fees': data})


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def generate_student_fees_from_structures(request):
    """Generate StudentFee records from FeeStructure for all students in a term"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        grade_id = request.POST.get('grade_id', '')
        
        if not term_id:
            messages.error(request, 'Please select a term.')
            return redirect('core:fee_structure_list')
        
        term = get_object_or_404(Term, id=term_id, school=school)
        
        # Get fee structures for this term (exclude transport - it's route-based)
        fee_structures = FeeStructure.objects.filter(
            school=school,
            term=term,
            is_active=True
        ).exclude(fee_category__category_type='transport').select_related('grade', 'fee_category')
        
        # Filter by grade if specified
        if grade_id:
            fee_structures = fee_structures.filter(grade_id=grade_id)
            students = Student.objects.filter(school=school, grade_id=grade_id, is_active=True)
        else:
            # Get all students in grades that have fee structures
            grade_ids = fee_structures.values_list('grade_id', flat=True).distinct()
            students = Student.objects.filter(school=school, grade_id__in=grade_ids, is_active=True)
        
        created_count = 0
        skipped_count = 0
        
        # Get transport category for transport fees
        transport_category = FeeCategory.objects.filter(
            school=school,
            category_type='transport'
        ).first()
        
        deleted_count = 0
        
        for student in students:
            # Process fee structures for this student's grade
            student_grade_structures = fee_structures.filter(grade=student.grade)
            
            for fee_structure in student_grade_structures:
                category = fee_structure.fee_category
                
                # Check if fee is optional and if student should pay it
                if category.is_optional:
                    # Check if student has opted into this optional category
                    student_opted_in = category in student.optional_fee_categories.all()
                    
                    if not student_opted_in:
                        # Remove fee if student hasn't opted in
                        StudentFee.objects.filter(
                            school=school,
                            student=student,
                            term=term,
                            fee_category=category
                        ).delete()
                        skipped_count += 1
                        continue
                
                # Create or update student fee
                student_fee, created = StudentFee.objects.get_or_create(
                    school=school,
                    student=student,
                    term=term,
                    fee_category=category,
                    defaults={
                        'amount_charged': fee_structure.amount,
                        'due_date': term.end_date,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update amount if it changed
                    if student_fee.amount_charged != fee_structure.amount:
                        student_fee.amount_charged = fee_structure.amount
                        student_fee.save()
            
            # Handle transport fees
            if transport_category:
                # Check if student has an active transport route
                has_active_route = (
                    student.transport_route and 
                    student.transport_route.is_currently_active()
                )
                
                if has_active_route:
                    # Student has an active route - create or update transport fee
                    transport_amount = student.transport_route.base_fare
                    
                    student_fee, created = StudentFee.objects.get_or_create(
                        school=school,
                        student=student,
                        term=term,
                        fee_category=transport_category,
                        defaults={
                            'amount_charged': transport_amount,
                            'due_date': term.end_date,
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        # Update amount if route fare changed
                        if student_fee.amount_charged != transport_amount:
                            student_fee.amount_charged = transport_amount
                            student_fee.save()
                else:
                    # Student doesn't have an active route - remove transport fee if it exists
                    deleted_transport_fees = StudentFee.objects.filter(
                        school=school,
                        student=student,
                        term=term,
                        fee_category=transport_category
                    ).delete()
                    
                    if deleted_transport_fees[0] > 0:
                        deleted_count += deleted_transport_fees[0]
        
        if grade_id:
            grade = Grade.objects.get(id=grade_id)
            message_parts = [f'Generated {created_count} student fee records for {grade.name} in {term.academic_year} - Term {term.term_number}.']
            if skipped_count > 0:
                message_parts.append(f'{skipped_count} optional fees skipped based on student preferences.')
            if deleted_count > 0:
                message_parts.append(f'{deleted_count} transport fee(s) removed for students without routes.')
            messages.success(request, ' '.join(message_parts))
        else:
            message_parts = [f'Generated {created_count} student fee records for {term.academic_year} - Term {term.term_number}.']
            if skipped_count > 0:
                message_parts.append(f'{skipped_count} optional fees skipped based on student preferences.')
            if deleted_count > 0:
                message_parts.append(f'{deleted_count} transport fee(s) removed for students without routes.')
            messages.success(request, ' '.join(message_parts))
        
        return redirect('core:fee_structure_list')
    
    # GET request - show form
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    grades = Grade.objects.filter(school=school).order_by('name')
    
    context = {
        'terms': terms,
        'grades': grades,
    }
    return render(request, 'core/generate_student_fees_from_structures.html', context)


@login_required
@login_required
def profile_view(request):
    """User profile view"""
    user = request.user
    profile = getattr(user, 'profile', None)
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'auth/profile.html', context)


# API views for AJAX requests
@login_required
def get_student_fees(request, student_id):
    """Get student fees as JSON"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
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
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_list(request):
    """List and manage transport routes"""
    school = request.user.profile.school
    transport_routes = TransportRoute.objects.filter(school=school).order_by('name')
    
    context = {
        'transport_routes': transport_routes,
    }
    return render(request, 'core/transport_route_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_add(request):
    """Add a new transport route"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        base_fare = request.POST.get('base_fare', '').strip()
        is_active = bool(request.POST.get('is_active'))
        active_start_date = request.POST.get('active_start_date', '').strip()
        active_end_date = request.POST.get('active_end_date', '').strip()
        
        errors = []
        if not name:
            errors.append('Route name is required.')
        if not base_fare:
            errors.append('Base fare is required.')
        else:
            try:
                base_fare = float(base_fare)
                if base_fare < 0:
                    errors.append('Base fare must be a positive number.')
            except ValueError:
                errors.append('Base fare must be a valid number.')
        
        # Validate dates
        start_date = None
        end_date = None
        if active_start_date:
            try:
                from datetime import datetime
                start_date = datetime.strptime(active_start_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid start date format.')
        
        if active_end_date:
            try:
                from datetime import datetime
                end_date = datetime.strptime(active_end_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid end date format.')
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            errors.append('Start date cannot be after end date.')
        
        # Check for duplicates
        if name and TransportRoute.objects.filter(school=school, name=name).exists():
            errors.append('A transport route with this name already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/transport_route_form.html', {
                'route': None,
                'post': request.POST,
            })
        
        try:
            TransportRoute.objects.create(
                school=school,
                name=name,
                description=description,
                base_fare=base_fare,
                is_active=is_active,
                active_start_date=start_date,
                active_end_date=end_date
            )
            messages.success(request, 'Transport route created successfully!')
            return redirect('core:transport_route_list')
        except Exception as e:
            messages.error(request, f'Error creating transport route: {str(e)}')
            return render(request, 'core/transport_route_form.html', {
                'route': None,
                'post': request.POST,
            })
    
    return render(request, 'core/transport_route_form.html', {
        'route': None,
        'post': {},
    })


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_edit(request, route_id):
    """Edit an existing transport route"""
    school = request.user.profile.school
    route = get_object_or_404(TransportRoute, id=route_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        base_fare = request.POST.get('base_fare', '').strip()
        is_active = bool(request.POST.get('is_active'))
        active_start_date = request.POST.get('active_start_date', '').strip()
        active_end_date = request.POST.get('active_end_date', '').strip()
        
        errors = []
        if not name:
            errors.append('Route name is required.')
        if not base_fare:
            errors.append('Base fare is required.')
        else:
            try:
                base_fare = float(base_fare)
                if base_fare < 0:
                    errors.append('Base fare must be a positive number.')
            except ValueError:
                errors.append('Base fare must be a valid number.')
        
        # Validate dates
        start_date = None
        end_date = None
        if active_start_date:
            try:
                from datetime import datetime
                start_date = datetime.strptime(active_start_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid start date format.')
        
        if active_end_date:
            try:
                from datetime import datetime
                end_date = datetime.strptime(active_end_date, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid end date format.')
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            errors.append('Start date cannot be after end date.')
        
        # Check for duplicates (excluding current route)
        if name and TransportRoute.objects.filter(school=school, name=name).exclude(id=route.id).exists():
            errors.append('A transport route with this name already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/transport_route_form.html', {
                'route': route,
                'post': request.POST,
            })
        
        try:
            route.name = name
            route.description = description
            route.base_fare = base_fare
            route.is_active = is_active
            route.active_start_date = start_date
            route.active_end_date = end_date
            route.save()
            messages.success(request, 'Transport route updated successfully!')
            return redirect('core:transport_route_list')
        except Exception as e:
            messages.error(request, f'Error updating transport route: {str(e)}')
            return render(request, 'core/transport_route_form.html', {
                'route': route,
                'post': request.POST,
            })
    
    return render(request, 'core/transport_route_form.html', {
        'route': route,
        'post': {},
    })


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_delete(request, route_id):
    """Delete a transport route"""
    school = request.user.profile.school
    route = get_object_or_404(TransportRoute, id=route_id, school=school)
    
    if request.method == 'POST':
        # Check if route is assigned to any students
        if Student.objects.filter(transport_route=route).exists():
            messages.error(request, f'Cannot delete "{route.name}" because it is assigned to one or more students.')
            return redirect('core:transport_route_list')
        
        try:
            route.delete()
            messages.success(request, 'Transport route deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting transport route: {str(e)}')
        
        return redirect('core:transport_route_list')
    
    # Show confirmation page
    context = {
        'route': route,
    }
    return render(request, 'core/transport_route_confirm_delete.html', context)


@login_required
def get_transport_routes(request):
    """Get transport routes as JSON"""
    from django.utils import timezone
    today = timezone.now().date()
    routes = TransportRoute.objects.filter(
        is_active=True
    ).filter(
        models.Q(active_start_date__isnull=True) | models.Q(active_start_date__lte=today)
    ).filter(
        models.Q(active_end_date__isnull=True) | models.Q(active_end_date__gte=today)
    )
    routes_data = [{'id': route.id, 'name': route.name, 'base_fare': float(route.base_fare)} for route in routes]
    return JsonResponse({'routes': routes_data})


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Multi-tenant: filter by user's school
        school = self.request.user.profile.school
        queryset = Student.objects.filter(school=school)
        
        # Filter by UPI if provided
        upi = self.request.query_params.get('upi', None)
        if upi:
            queryset = queryset.filter(upi=upi)
        
        return queryset

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
        today = timezone.now().date()
        return TransportRoute.objects.filter(
            school=school,
            is_active=True
        ).filter(
            models.Q(active_start_date__isnull=True) | models.Q(active_start_date__lte=today)
        ).filter(
            models.Q(active_end_date__isnull=True) | models.Q(active_end_date__gte=today)
        )


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
        primary_color = request.POST.get('primary_color', '#0d6efd').strip()
        secondary_color = request.POST.get('secondary_color', '').strip()
        use_color_scheme = bool(request.POST.get('use_color_scheme'))
        use_secondary_on_headers = bool(request.POST.get('use_secondary_on_headers'))
        errors = []
        if not name:
            errors.append('School name is required.')
        # Validate color format (hex code)
        if primary_color and not primary_color.startswith('#'):
            errors.append('Primary color must be a valid hex code starting with #.')
        elif primary_color and len(primary_color) != 7:
            errors.append('Primary color must be a valid hex code (e.g., #0d6efd).')
        if secondary_color and not secondary_color.startswith('#'):
            errors.append('Secondary color must be a valid hex code starting with #.')
        elif secondary_color and len(secondary_color) != 7:
            errors.append('Secondary color must be a valid hex code (e.g., #6c757d).')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_form.html', {'school': school})
        school.name = name
        school.address = address
        school.email = email
        school.phone = phone
        school.primary_color = primary_color
        school.secondary_color = secondary_color if secondary_color else None
        school.use_color_scheme = use_color_scheme
        school.use_secondary_on_headers = use_secondary_on_headers
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
        primary_color = request.POST.get('primary_color', '#0d6efd').strip()
        secondary_color = request.POST.get('secondary_color', '').strip()
        use_color_scheme = bool(request.POST.get('use_color_scheme'))
        use_secondary_on_headers = bool(request.POST.get('use_secondary_on_headers'))
        errors = []
        if not name:
            errors.append('School name is required.')
        if School.objects.filter(name=name).exists():
            errors.append('A school with this name already exists.')
        if email and School.objects.filter(email=email).exists():
            errors.append('A school with this email already exists.')
        # Validate color format (hex code)
        if primary_color and not primary_color.startswith('#'):
            errors.append('Primary color must be a valid hex code starting with #.')
        elif primary_color and len(primary_color) != 7:
            errors.append('Primary color must be a valid hex code (e.g., #0d6efd).')
        if secondary_color and not secondary_color.startswith('#'):
            errors.append('Secondary color must be a valid hex code starting with #.')
        elif secondary_color and len(secondary_color) != 7:
            errors.append('Secondary color must be a valid hex code (e.g., #6c757d).')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_add_form.html', {'post': request.POST})
        School.objects.create(
            name=name, 
            address=address, 
            email=email, 
            phone=phone, 
            logo=logo,
            primary_color=primary_color,
            secondary_color=secondary_color if secondary_color else None,
            use_color_scheme=use_color_scheme,
            use_secondary_on_headers=use_secondary_on_headers
        )
        messages.success(request, 'School added successfully!')
        return redirect('core:school_admin_list')
    return render(request, 'core/school_add_form.html', {'post': {}})


@staff_member_required
def school_admin_list(request):
    """List all schools and allow admin to edit or assign users to schools"""
    from django.contrib.auth.models import User
    from django.shortcuts import redirect
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
                # Redirect to reload the page and show updated data
                return redirect('core:school_admin_list')
            except Exception as e:
                messages.error(request, f'Error: {e}')
    context = {'schools': schools, 'users': users}
    return render(request, 'core/school_admin_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def parent_list(request):
    """List all parents/guardians"""
    school = request.user.profile.school
    parents = Parent.objects.filter(
        school=school
    ).select_related('user').prefetch_related('children')
    
    # Filter by active status (default: show active only)
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    if not show_inactive:
        parents = parents.filter(is_active=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        parents = parents.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Order by active status first, then by name
    parents = parents.order_by('-is_active', 'user__first_name', 'user__last_name')
    
    # Pagination
    paginator = Paginator(parents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'show_inactive': show_inactive,
    }
    
    return render(request, 'core/parent_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def parent_detail(request, parent_id):
    """View parent/guardian details"""
    school = request.user.profile.school
    parent = get_object_or_404(
        Parent.objects.select_related('user', 'school').prefetch_related('children__grade', 'children__school_class'),
        id=parent_id,
        school=school
    )
    
    # Get all children linked to this parent
    children = parent.children.all().select_related('grade', 'school_class').order_by('first_name', 'last_name')
    
    context = {
        'parent': parent,
        'children': children,
    }
    
    return render(request, 'core/parent_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def parent_edit(request, parent_id):
    """Edit parent/guardian information"""
    school = request.user.profile.school
    parent = get_object_or_404(
        Parent.objects.select_related('user', 'school'),
        id=parent_id,
        school=school
    )
    
    if request.method == 'POST':
        print(f"=== PARENT EDIT POST REQUEST ===")
        print(f"POST data keys: {list(request.POST.keys())}")
        form = ParentEditForm(request.POST, instance=parent, school=school)
        if form.is_valid():
            print(f"Form is VALID")
            try:
                parent = form.save()
                
                # Handle student linking directly in the view (more reliable)
                raw_students = request.POST.getlist('students', [])
                print(f"DEBUG: POST students={raw_students}")
                # Filter out empty strings, None, and whitespace-only values
                raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                print(f"DEBUG: Filtered students={raw_students}")
                
                if raw_students:
                    try:
                        # Convert to integers and filter
                        student_ids = []
                        for sid in raw_students:
                            try:
                                student_id = int(sid)
                                student_ids.append(student_id)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            # Fetch students from database
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                parent.children.set(students)
                                parent.refresh_from_db()
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f'Error linking students to parent: {e}', exc_info=True)
                # Don't clear existing links if no students in POST - preserve existing relationships
                
                messages.success(request, f'Parent {parent.full_name} updated successfully.')
                return redirect('core:parent_detail', parent_id=parent.id)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error updating parent: {str(e)}', exc_info=True)
                messages.error(request, f'Error updating parent: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ParentEditForm(instance=parent, school=school)
    
    context = {
        'form': form,
        'parent': parent,
        'school': school,
    }
    return render(request, 'core/parent_edit.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def parent_register(request):
    """Register a new parent/guardian and optionally link to students"""
    # Determine the school
    school = None
    if hasattr(request.user, 'profile') and request.user.profile.school:
        school = request.user.profile.school
    
    if request.method == 'POST':
        # For superusers, get school from POST data
        if request.user.is_superuser and not school:
            school_id = request.POST.get('school')
            if school_id:
                school = get_object_or_404(School, id=school_id)
            else:
                messages.error(request, 'Please select a school.')
                form = ParentRegistrationForm(school=None)
                context = {
                    'form': form,
                    'school': None,
                    'schools': School.objects.all(),
                    'is_superuser': True
                }
                return render(request, 'core/parent_register.html', context)
        
        if not school:
            messages.error(request, 'School is required for parent registration.')
            form = ParentRegistrationForm(school=None)
            context = {
                'form': form,
                'school': None,
                'schools': School.objects.all() if request.user.is_superuser else [],
                'is_superuser': request.user.is_superuser
            }
            return render(request, 'core/parent_register.html', context)
        
        form = ParentRegistrationForm(request.POST, school=school)
        if form.is_valid():
            try:
                parent = form.save(commit=True, school=school)
                
                # Handle student linking directly in the view (more reliable)
                raw_students = request.POST.getlist('students', [])
                # Filter out empty strings, None, and whitespace-only values
                raw_students = [s for s in raw_students if s is not None and str(s).strip() != '']
                
                if raw_students:
                    try:
                        # Convert to integers and filter
                        student_ids = []
                        for sid in raw_students:
                            try:
                                student_id = int(sid)
                                student_ids.append(student_id)
                            except (ValueError, TypeError):
                                continue
                        
                        if student_ids:
                            # Fetch students from database
                            students = Student.objects.filter(
                                id__in=student_ids,
                                school=school,
                                is_active=True
                            )
                            if students.exists():
                                parent.children.set(students)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f'Error linking students to parent during registration: {e}', exc_info=True)
                
                messages.success(request, f'Parent account created successfully for {parent.user.get_full_name() or parent.user.username}.')
                return redirect('core:parent_register')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error creating parent account: {str(e)}', exc_info=True)
                messages.error(request, f'Error creating parent account: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ParentRegistrationForm(school=school)
    
    # Get all schools for superuser selection
    schools = School.objects.all() if request.user.is_superuser else []
    
    context = {
        'form': form,
        'school': school,
        'schools': schools,
        'is_superuser': request.user.is_superuser
    }
    return render(request, 'core/parent_register.html', context)


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
        primary_color = request.POST.get('primary_color', '#0d6efd').strip()
        secondary_color = request.POST.get('secondary_color', '').strip()
        use_color_scheme = bool(request.POST.get('use_color_scheme'))
        use_secondary_on_headers = bool(request.POST.get('use_secondary_on_headers'))
        errors = []
        if not name:
            errors.append('School name is required.')
        if School.objects.filter(name=name).exclude(id=school.id).exists():
            errors.append('A school with this name already exists.')
        if email and School.objects.filter(email=email).exclude(id=school.id).exists():
            errors.append('A school with this email already exists.')
        # Validate color format (hex code)
        if primary_color and not primary_color.startswith('#'):
            errors.append('Primary color must be a valid hex code starting with #.')
        elif primary_color and len(primary_color) != 7:
            errors.append('Primary color must be a valid hex code (e.g., #0d6efd).')
        if secondary_color and not secondary_color.startswith('#'):
            errors.append('Secondary color must be a valid hex code starting with #.')
        elif secondary_color and len(secondary_color) != 7:
            errors.append('Secondary color must be a valid hex code (e.g., #6c757d).')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/school_form.html', {'school': school})
        school.name = name
        school.address = address
        school.email = email
        school.phone = phone
        school.primary_color = primary_color
        school.secondary_color = secondary_color if secondary_color else None
        school.use_color_scheme = use_color_scheme
        school.use_secondary_on_headers = use_secondary_on_headers
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
    grades_queryset = Grade.objects.filter(school=school)
    
    # Sort grades naturally (handles numeric sorting: Grade 1, Grade 2, ..., Grade 10)
    import re
    def natural_sort_key(name):
        """Extract numbers for natural sorting"""
        parts = re.split(r'(\d+)', name)
        return [int(part) if part.isdigit() else part.lower() for part in parts]
    
    grades = sorted(grades_queryset, key=lambda g: natural_sort_key(g.name))
    
    if request.method == 'POST':
        # Check if grades exist
        if not grades_queryset.exists():
            messages.error(request, 'No grades found. Please create at least one grade before adding classes.')
            return redirect('core:class_list')
        
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
def class_generate(request):
    """Generate multiple classes generically based on grades and streams"""
    school = request.user.profile.school
    grades_queryset = Grade.objects.filter(school=school)
    
    # Check if grades exist
    if not grades_queryset.exists():
        messages.error(request, 'No grades found. Please create at least one grade before generating classes.')
        return redirect('core:class_list')
    
    # Sort grades naturally (handles numeric sorting: Grade 1, Grade 2, ..., Grade 10)
    import re
    def natural_sort_key(name):
        """Extract numbers for natural sorting"""
        parts = re.split(r'(\d+)', name)
        return [int(part) if part.isdigit() else part.lower() for part in parts]
    
    grades = sorted(grades_queryset, key=lambda g: natural_sort_key(g.name))
    
    if request.method == 'POST':
        all_grades = request.POST.get('all_grades') == 'on'
        selected_grades = request.POST.getlist('selected_grades')
        num_streams = request.POST.get('num_streams', '')
        stream_names_input = request.POST.get('stream_names', '').strip()
        
        errors = []
        
        # Validate number of streams
        if not num_streams or not num_streams.isdigit():
            errors.append('Number of streams is required and must be a valid number.')
        else:
            num_streams = int(num_streams)
            if num_streams < 1 or num_streams > 20:
                errors.append('Number of streams must be between 1 and 20.')
        
        # Validate stream names
        stream_names = []
        if stream_names_input:
            # Parse comma-separated stream names
            stream_names = [name.strip() for name in stream_names_input.split(',') if name.strip()]
            if len(stream_names) != num_streams:
                errors.append(f'Number of stream names ({len(stream_names)}) must match the number of streams ({num_streams}).')
        else:
            # Generate default stream names (A, B, C, ... or 1, 2, 3, ...)
            if num_streams <= 26:
                stream_names = [chr(65 + i) for i in range(num_streams)]  # A, B, C, ...
            else:
                stream_names = [str(i + 1) for i in range(num_streams)]  # 1, 2, 3, ...
        
        # Determine which grades to process
        if all_grades:
            grades_to_process = list(grades)
        elif selected_grades:
            grades_to_process = [g for g in grades if str(g.id) in selected_grades]
        else:
            errors.append('Please select at least one grade or choose "All Grades".')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/class_generate.html', {
                'grades': grades,
                'all_grades': all_grades,
                'selected_grades': selected_grades,
                'num_streams': request.POST.get('num_streams', ''),
                'stream_names': stream_names_input,
            })
        
        # Generate classes
        created_classes = []
        skipped_classes = []
        
        for grade in grades_to_process:
            for stream_name in stream_names:
                class_name = f"{grade.name} {stream_name}"
                
                # Check if class already exists
                if SchoolClass.objects.filter(school=school, grade=grade, name=class_name).exists():
                    skipped_classes.append(class_name)
                else:
                    try:
                        SchoolClass.objects.create(
                            school=school,
                            grade=grade,
                            name=class_name,
                            description=f'{grade.name} {stream_name}',
                            is_active=True
                        )
                        created_classes.append(class_name)
                    except Exception as e:
                        from django.db import IntegrityError
                        if isinstance(e, IntegrityError):
                            skipped_classes.append(class_name)
                        else:
                            messages.error(request, f'Error creating {class_name}: {str(e)}')
        
        # Build appropriate messages
        if created_classes and skipped_classes:
            messages.success(request, f'Successfully created {len(created_classes)} class(es).')
            messages.info(request, f'Skipped {len(skipped_classes)} class(es) that already exist.')
        elif created_classes:
            messages.success(request, f'Successfully created {len(created_classes)} class(es).')
        elif skipped_classes:
            messages.warning(request, f'All {len(skipped_classes)} class(es) already exist. No new classes were created.')
        else:
            messages.warning(request, 'No classes were created.')
        
        return redirect('core:class_list')
    
    return render(request, 'core/class_generate.html', {'grades': grades})


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement(request, student_id):
    """Generate fee statement for a student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance (all fees and payments before start_date)
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    return render(request, 'core/student_statement.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement_pdf(request, student_id):
    """Generate PDF version of student statement"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # For now, return HTML version. PDF generation can be added later with weasyprint or xhtml2pdf
    return render(request, 'core/student_statement_pdf.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement_email(request, student_id):
    """Email student statement"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    if not student.parent_email:
        messages.error(request, 'Student has no email address on file.')
        return redirect('core:student_statement', student_id=student_id)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # Render email template
    html_message = render_to_string('core/student_statement_email.html', context)
    
    # Send email
    subject = f'Fee Statement - {student.full_name} - {school.name}'
    try:
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty, using HTML)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.parent_email],
            html_message=html_message,
            fail_silently=False,
        )
        messages.success(request, f'Statement sent successfully to {student.parent_email}')
    except Exception as e:
        messages.error(request, f'Error sending email: {str(e)}')
    
    return redirect('core:student_statement', student_id=student_id)


def serve_media_file(request, path):
    """
    Serve media files from Railway storage (S3-compatible)
    This view proxies files from private Railway buckets to make them publicly accessible
    """
    from django.conf import settings
    
    # Only serve files when using S3 storage
    if not getattr(settings, 'USE_S3', False):
        raise Http404("Media file not found")
    
    try:
        # Open the file from storage
        file = default_storage.open(path)
        
        # Determine content type from file extension
        import mimetypes
        content_type, _ = mimetypes.guess_type(path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Read file content
        file_content = file.read()
        file.close()
        
        # Create response with appropriate headers
        response = HttpResponse(file_content, content_type=content_type)
        
        # Set cache headers (1 day)
        response['Cache-Control'] = 'public, max-age=86400'
        
        return response
    except Exception as e:
        # Log error and return 404
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving media file {path}: {e}")
        raise Http404("Media file not found")

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


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def class_bulk_delete(request):
    """Bulk delete classes"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        class_ids = request.POST.getlist('class_ids')
        
        if not class_ids:
            messages.error(request, 'No classes selected for deletion.')
            return redirect('core:class_list')
        
        # Verify all classes belong to the school
        classes_to_delete = SchoolClass.objects.filter(
            id__in=class_ids,
            school=school
        )
        
        deleted_count = classes_to_delete.count()
        
        if deleted_count == 0:
            messages.error(request, 'No valid classes found to delete.')
            return redirect('core:class_list')
        
        # Delete the classes
        classes_to_delete.delete()
        
        if deleted_count == 1:
            messages.success(request, f'{deleted_count} class deleted successfully!')
        else:
            messages.success(request, f'{deleted_count} classes deleted successfully!')
        
        return redirect('core:class_list')
    
    # GET request - redirect to class list
    return redirect('core:class_list')


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


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement(request, student_id):
    """Generate fee statement for a student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance (all fees and payments before start_date)
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    return render(request, 'core/student_statement.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement_pdf(request, student_id):
    """Generate PDF version of student statement"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # For now, return HTML version. PDF generation can be added later with weasyprint or xhtml2pdf
    return render(request, 'core/student_statement_pdf.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant', 'teacher')
def student_statement_email(request, student_id):
    """Email student statement"""
    school = request.user.profile.school
    student = get_object_or_404(Student, student_id=student_id, school=school)
    
    if not student.parent_email:
        messages.error(request, 'Student has no email address on file.')
        return redirect('core:student_statement', student_id=student_id)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # Render email template
    html_message = render_to_string('core/student_statement_email.html', context)
    
    # Send email
    subject = f'Fee Statement - {student.full_name} - {school.name}'
    try:
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty, using HTML)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.parent_email],
            html_message=html_message,
            fail_silently=False,
        )
        messages.success(request, f'Statement sent successfully to {student.parent_email}')
    except Exception as e:
        messages.error(request, f'Error sending email: {str(e)}')
    
    return redirect('core:student_statement', student_id=student_id)


def serve_media_file(request, path):
    """
    Serve media files from Railway storage (S3-compatible)
    This view proxies files from private Railway buckets to make them publicly accessible
    """
    from django.conf import settings
    
    # Only serve files when using S3 storage
    if not getattr(settings, 'USE_S3', False):
        raise Http404("Media file not found")
    
    try:
        # Open the file from storage
        file = default_storage.open(path)
        
        # Determine content type from file extension
        import mimetypes
        content_type, _ = mimetypes.guess_type(path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Read file content
        file_content = file.read()
        file.close()
        
        # Create response with appropriate headers
        response = HttpResponse(file_content, content_type=content_type)
        
        # Set cache headers (1 day)
        response['Cache-Control'] = 'public, max-age=86400'
        
        return response
    except Exception as e:
        # Log error and return 404
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving media file {path}: {e}")
        raise Http404("Media file not found")
# Parent Portal Views - To be added to core/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from .models import Parent, Student, StudentFee
from .decorators import role_required
from payments.models import Payment


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_dashboard(request):
    """Parent portal dashboard showing overview of children and fees"""
    parent = None
    is_superuser_view = False
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        # Allow superusers to access even without a Parent profile
        if request.user.is_superuser:
            is_superuser_view = True
            # For superusers, show aggregated data for all parents (or redirect to parent list)
            # For now, redirect to parent list so they can select a parent to view
            messages.info(request, 'As a superuser, you can view individual parent portals from the parent list.')
            return redirect('core:parent_list')
        else:
            messages.error(request, 'Parent profile not found. Please contact administrator.')
            return redirect('core:dashboard')
    
    # Get all children linked to this parent
    children = parent.children.all().select_related('grade', 'school_class', 'school_class__class_teacher').order_by('first_name', 'last_name')
    
    # Calculate fee statistics for all children
    all_student_fees = StudentFee.objects.filter(
        student__in=children,
        student__is_active=True
    ).select_related('fee_category', 'term', 'student')
    
    total_charged = all_student_fees.aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
    total_paid = all_student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_balance = total_charged - total_paid
    
    # Get overdue fees
    from django.utils import timezone
    overdue_fees = all_student_fees.filter(
        due_date__lt=timezone.now().date(),
        is_paid=False
    ).order_by('due_date')
    
    # Get recent payments
    recent_payments = Payment.objects.filter(
        student__in=children
    ).select_related('student', 'student_fee').order_by('-created_at')[:10]
    
    context = {
        'parent': parent,
        'children': children,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'overdue_fees': overdue_fees,
        'recent_payments': recent_payments,
        'is_superuser_view': is_superuser_view,
    }
    
    return render(request, 'core/parent_portal/dashboard.html', context)


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_student_fees(request, student_id):
    """View fee details for a specific child"""
    parent = None
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        # Allow superusers to access even without a Parent profile
        if not request.user.is_superuser:
            messages.error(request, 'Parent profile not found.')
            return redirect('core:parent_portal_dashboard')
    
    # Get student - for superusers, allow viewing any student; for parents, verify ownership
    if request.user.is_superuser and not parent:
        student = get_object_or_404(
            Student.objects.select_related('grade', 'school_class', 'school_class__class_teacher'),
            student_id=student_id
        )
    else:
        # Verify the student belongs to this parent
        student = get_object_or_404(
            Student.objects.select_related('grade', 'school_class', 'school_class__class_teacher'),
            student_id=student_id,
            parents=parent
        )
    
    # Get all fees for this student
    student_fees = StudentFee.objects.filter(
        student=student
    ).select_related('fee_category', 'term').order_by('-term__academic_year', '-term__term_number')
    
    # Calculate totals
    total_charged = student_fees.aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
    total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_balance = total_charged - total_paid
    
    # Get payments for this student
    payments = Payment.objects.filter(
        student=student
    ).select_related('student_fee').order_by('-created_at')
    
    context = {
        'parent': parent,
        'student': student,
        'student_fees': student_fees,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'payments': payments,
    }
    
    return render(request, 'core/parent_portal/student_fees.html', context)


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_student_statement(request, student_id):
    """View fee statement for a specific child (parent portal version)"""
    parent = None
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        # Allow superusers to access even without a Parent profile
        if not request.user.is_superuser:
            messages.error(request, 'Parent profile not found.')
            return redirect('core:parent_portal_dashboard')
    
    # Get student - for superusers, allow viewing any student; for parents, verify ownership
    if request.user.is_superuser and not parent:
        student = get_object_or_404(
            Student.objects.select_related('grade', 'school_class', 'school_class__class_teacher', 'school'),
            student_id=student_id
        )
        school = student.school
    else:
        # Verify the student belongs to this parent
        student = get_object_or_404(
            Student.objects.select_related('grade', 'school_class', 'school_class__class_teacher', 'school'),
            student_id=student_id,
            parents=parent
        )
        school = student.school
    
    # Get date filters
    from datetime import datetime
    from django.utils import timezone
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = None
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = None
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance (all fees and payments before start_date)
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            term__start_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    for fee in student_fees:
        if start_date and fee.term.start_date < start_date:
            continue
        if end_date and fee.term.start_date > end_date:
            continue
        
        transactions.append({
            'date': fee.term.start_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date() if hasattr(payment.payment_date, 'date') else payment.payment_date
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'parent': parent,
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    return render(request, 'core/parent_portal/student_statement.html', context)


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_student_performance(request, student_id):
    """View student performance/academic records"""
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, 'Parent profile not found.')
        return redirect('core:parent_portal_dashboard')
    
    # Verify the student belongs to this parent
    student = get_object_or_404(
        Student.objects.select_related('grade', 'school_class'),
        student_id=student_id,
        parents=parent
    )
    
    # TODO: Add academic records/performance data when that module is implemented
    # For now, just show basic student info
    
    context = {
        'parent': parent,
        'student': student,
    }
    
    return render(request, 'core/parent_portal/student_performance.html', context)


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_profile(request):
    """Parent profile management with verification for phone/email updates"""
    try:
        parent = Parent.objects.select_related('user', 'school').get(user=request.user)
    except Parent.DoesNotExist:
        # Superusers don't need a parent profile to access - redirect to dashboard
        if request.user.is_superuser:
            messages.info(request, 'As a superuser, you can manage parent profiles from the parent list.')
            return redirect('core:parent_list')
        messages.error(request, 'Parent profile not found.')
        return redirect('core:parent_portal_dashboard')
    
    if request.method == 'POST':
        # Handle profile update
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        preferred_contact_method = request.POST.get('preferred_contact_method', 'phone')
        
        # Check if phone or email changed (requires verification)
        phone_changed = phone != parent.phone
        email_changed = email != (parent.email or parent.user.email)
        
        # If phone or email changed, check if verification code was provided
        verification_code = request.POST.get('verification_code', '').strip()
        verification_type = request.POST.get('verification_type', '')
        
        if phone_changed or email_changed:
            if not verification_code:
                # Request verification code
                from core.verification_service import VerificationService
                
                if phone_changed:
                    verification = VerificationService.create_verification(
                        parent=parent,
                        verification_type='phone',
                        new_value=phone
                    )
                    if VerificationService.send_verification_code(verification):
                        messages.info(request, f'Verification code sent to {phone}. Please enter the code to update your phone number.')
                    else:
                        messages.error(request, 'Failed to send verification code. Please try again.')
                
                if email_changed:
                    verification = VerificationService.create_verification(
                        parent=parent,
                        verification_type='email',
                        new_value=email
                    )
                    if VerificationService.send_verification_code(verification):
                        messages.info(request, f'Verification code sent to {email}. Please check your email and enter the code to update your email address.')
                    else:
                        messages.error(request, 'Failed to send verification code. Please try again.')
                
                # Don't update yet, wait for verification
                context = {
                    'parent': parent,
                    'pending_phone': phone if phone_changed else parent.phone,
                    'pending_email': email if email_changed else (parent.email or parent.user.email),
                    'phone_changed': phone_changed,
                    'email_changed': email_changed,
                }
                return render(request, 'core/parent_portal/profile.html', context)
            else:
                # Verify the code
                from core.verification_service import VerificationService
                success, message = VerificationService.verify_code(
                    parent=parent,
                    verification_type=verification_type,
                    code=verification_code
                )
                
                if success:
                    messages.success(request, message)
                    # Update other fields
                    parent.address = address
                    parent.preferred_contact_method = preferred_contact_method
                    parent.save()
                else:
                    messages.error(request, message)
                    context = {
                        'parent': parent,
                        'pending_phone': phone if phone_changed else parent.phone,
                        'pending_email': email if email_changed else (parent.email or parent.user.email),
                        'phone_changed': phone_changed,
                        'email_changed': email_changed,
                    }
                    return render(request, 'core/parent_portal/profile.html', context)
        else:
            # No phone/email change, just update other fields
            parent.address = address
            parent.preferred_contact_method = preferred_contact_method
            parent.save()
            messages.success(request, 'Profile updated successfully.')
        
        return redirect('core:parent_portal_profile')
    
    context = {
        'parent': parent,
    }
    
    return render(request, 'core/parent_portal/profile.html', context)


@login_required
@role_required('parent', 'super_admin', 'school_admin')
def parent_portal_payment_initiate(request, student_id, fee_id):
    """Initiate M-Pesa payment for a student fee or total balance (fee_id=0)"""
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        if not request.user.is_superuser:
            return JsonResponse({'error': 'Parent profile not found.'}, status=403)
        parent = None
    
    # Verify the student belongs to this parent (or allow superuser)
    if request.user.is_superuser and not parent:
        student = get_object_or_404(Student, student_id=student_id)
    else:
        student = get_object_or_404(Student, student_id=student_id, parents=parent)
    
    # Handle total balance payment (fee_id=0) or specific fee payment
    if fee_id == 0:
        # Calculate total balance
        from django.db.models import Sum
        student_fees = StudentFee.objects.filter(student=student)
        total_charged = student_fees.aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        total_balance = total_charged - total_paid
        
        if total_balance <= 0:
            return JsonResponse({'error': 'No balance to pay.'}, status=400)
        
        # For total balance, we'll use the first unpaid fee as reference (or create a virtual fee object)
        # Create a virtual student_fee object for template compatibility
        class VirtualStudentFee:
            def __init__(self, student, total_balance):
                self.student = student
                self.amount_charged = total_charged
                self.amount_paid = total_paid
                self.balance = total_balance
                self.fee_category = type('obj', (object,), {'name': 'Total Balance'})()
                self.term = type('obj', (object,), {'academic_year': 'All Terms', 'term_number': ''})()
        
        student_fee = VirtualStudentFee(student, total_balance)
        is_total_balance = True
    else:
        # Get the specific fee
        student_fee = get_object_or_404(StudentFee, id=fee_id, student=student)
        
        if student_fee.balance <= 0:
            return JsonResponse({'error': 'No balance to pay.'}, status=400)
        is_total_balance = False
    
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        amount = request.POST.get('amount', '').strip()
        
        if not phone_number:
            return JsonResponse({'error': 'Phone number is required.'}, status=400)
        
        try:
            amount = Decimal(amount)
            if amount <= 0 or amount > student_fee.balance:
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
        except (ValueError, InvalidOperation):
            return JsonResponse({'error': 'Invalid amount format.'}, status=400)
        
        # Initiate M-Pesa STK Push
        try:
            from core.mpesa_service import MpesaService
            mpesa = MpesaService()
            
            # Generate account reference
            if is_total_balance:
                account_reference = f"TOTAL-{student.student_id}"
                transaction_desc = f"Total balance payment for {student.full_name}"
            else:
                account_reference = f"FEE-{student_fee.id}-{student.student_id}"
                transaction_desc = f"Fee payment for {student.full_name} - {student_fee.fee_category.name}"
            
            result = mpesa.initiate_stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc
            )
            
            if result.get('success'):
                # Store payment initiation record (you may want to create a PaymentInitiation model)
                # For now, just return success
                return JsonResponse({
                    'success': True,
                    'message': result.get('customer_message', 'Payment request sent. Please check your phone for M-Pesa prompt.'),
                    'checkout_request_id': result.get('checkout_request_id'),
                    'merchant_request_id': result.get('merchant_request_id')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result.get('error', 'Failed to initiate payment. Please try again.')
                }, status=400)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error initiating M-Pesa payment: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while initiating payment. Please contact the school.'
            }, status=500)
    
    context = {
        'parent': parent,
        'student': student,
        'student_fee': student_fee,
        'is_total_balance': is_total_balance,
    }
    
    return render(request, 'core/parent_portal/payment_initiate.html', context)


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa STK Push callback"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Log the callback for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'M-Pesa callback received: {data}')
        
        # Extract callback data
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        
        merchant_request_id = stk_callback.get('MerchantRequestID')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        # Extract payment details if successful
        if result_code == 0:
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            # Extract payment details
            amount = None
            mpesa_receipt_number = None
            transaction_date = None
            phone_number = None
            
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                
                if name == 'Amount':
                    amount = value
                elif name == 'MpesaReceiptNumber':
                    mpesa_receipt_number = value
                elif name == 'TransactionDate':
                    transaction_date = value
                elif name == 'PhoneNumber':
                    phone_number = value
            
            # Parse account reference to get fee ID
            # Format: FEE-{fee_id}-{student_id}
            account_reference = None
            for item in items:
                if item.get('Name') == 'AccountReference':
                    account_reference = item.get('Value')
                    break
            
            if account_reference and account_reference.startswith('FEE-'):
                try:
                    # Extract fee ID from reference (FEE-{fee_id}-{student_id})
                    parts = account_reference.split('-')
                    if len(parts) >= 2:
                        fee_id = int(parts[1])
                        student_fee = StudentFee.objects.get(id=fee_id)
                        
                        # Create payment record
                        from payments.models import Payment
                        payment = Payment.objects.create(
                            student=student_fee.student,
                            student_fee=student_fee,
                            amount=Decimal(str(amount)) / 100,  # M-Pesa returns amount in cents
                            payment_method='mpesa',
                            status='completed',
                            reference_number=mpesa_receipt_number,
                            payment_date=timezone.now(),
                            notes=f'M-Pesa payment via parent portal. Phone: {phone_number}'
                        )
                        
                        # Update student fee
                        student_fee.amount_paid += payment.amount
                        if student_fee.amount_paid >= student_fee.amount_charged:
                            student_fee.is_paid = True
                        student_fee.save()
                        
                        logger.info(f'Payment processed successfully: {payment.id} for fee {fee_id}')
                except Exception as e:
                    logger.error(f'Error processing payment from callback: {str(e)}')
        
        # Always return success to M-Pesa (they will retry if we return error)
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error processing M-Pesa callback: {str(e)}')
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})  # Return success to prevent retries

