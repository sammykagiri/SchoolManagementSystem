from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.template.loader import render_to_string
from django.conf import settings
from .models import (
    School, Grade, Term, FeeCategory, TransportRoute, Student, FeeStructure, StudentFee, SchoolClass,
    Activity, ActivityException
)
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
from .services import DashboardService, StudentService
from .decorators import role_required


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
    
    # Calculate all-time fee totals (not just current term)
    from django.db.models import Sum
    all_fees = StudentFee.objects.filter(school=school)
    total_fees_charged = all_fees.aggregate(total=Sum('amount_charged'))['total'] or 0
    total_fees_paid = all_fees.aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # Get overdue payments for template
    overdue_payments = StudentFee.objects.filter(
        school=school,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).select_related('student', 'fee_category', 'term')[:10]
    
    # Get overdue count
    overdue_fees = StudentFee.objects.filter(
        school=school,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    context = {
        **dashboard_data,
        'total_fees_charged': float(total_fees_charged),
        'total_fees_paid': float(total_fees_paid),
        'overdue_fees': overdue_fees,
        'overdue_payments': overdue_payments,
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
        school=school,
        is_active=True
    ).select_related('grade', 'transport_route').prefetch_related('parents__user')
    
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
    }
    
    return render(request, 'core/student_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def student_detail(request, student_id):
    """Student detail view"""
    student = get_object_or_404(
        Student.objects.select_related('grade', 'transport_route').prefetch_related('parents__user'),
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
    grades = Grade.objects.all()
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        try:
            Grade.objects.create(name=name, description=description)
            messages.success(request, 'Grade created successfully.')
            return redirect('core:grade_list')
        except Exception as e:
            messages.error(request, f'Error creating grade: {str(e)}')
    
    context = {'grades': grades}
    return render(request, 'core/grade_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def grade_edit(request, grade_id):
    """Edit a grade"""
    grade = get_object_or_404(Grade, id=grade_id)
    
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
    grade = get_object_or_404(Grade, id=grade_id)
    
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
        Term.objects.create(
            school=school,
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
        school=school,
        is_active=True
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
def fee_structure_edit(request, fee_structure_id):
    """Edit a fee structure"""
    school = request.user.profile.school
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id, school=school, is_active=True)
    
    if request.method == 'POST':
        grade_id = request.POST.get('grade')
        term_id = request.POST.get('term')
        fee_category_id = request.POST.get('fee_category')
        amount = request.POST.get('amount')
        
        if not all([grade_id, term_id, fee_category_id, amount]):
            messages.error(request, 'Please fill in all fields.')
        else:
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
    
    context = {
        'fee_structure': fee_structure,
        'grades': Grade.objects.filter(school=school),
        'terms': Term.objects.filter(school=school).order_by('-academic_year', '-term_number'),
        'fee_categories': FeeCategory.objects.filter(school=school),
    }
    return render(request, 'core/fee_structure_form.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_structure_delete(request, fee_structure_id):
    """Delete (soft delete) a fee structure"""
    school = request.user.profile.school
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id, school=school, is_active=True)
    
    if request.method == 'POST':
        fee_structure.is_active = False
        fee_structure.save()
        messages.success(request, 'Fee structure deleted successfully.')
        return redirect('core:fee_structure_list')
    
    context = {
        'fee_structure': fee_structure,
    }
    return render(request, 'core/fee_structure_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_list(request):
    """List and create transport routes"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        base_fare = request.POST.get('base_fare')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not base_fare:
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                TransportRoute.objects.create(
                    school=school,
                    name=name,
                    description=description,
                    base_fare=base_fare,
                    is_active=is_active
                )
                messages.success(request, 'Transport route created successfully.')
                return redirect('core:transport_route_list')
            except Exception as e:
                messages.error(request, f'Error creating transport route: {str(e)}')
    
    transport_routes = TransportRoute.objects.filter(school=school).order_by('name')
    context = {
        'transport_routes': transport_routes,
    }
    return render(request, 'core/transport_route_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_edit(request, route_id):
    """Edit a transport route"""
    school = request.user.profile.school
    route = get_object_or_404(TransportRoute, id=route_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        base_fare = request.POST.get('base_fare')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not base_fare:
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                route.name = name
                route.description = description
                route.base_fare = base_fare
                route.is_active = is_active
                route.save()
                messages.success(request, 'Transport route updated successfully.')
                return redirect('core:transport_route_list')
            except Exception as e:
                messages.error(request, f'Error updating transport route: {str(e)}')
    
    context = {
        'route': route,
    }
    return render(request, 'core/transport_route_form.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def transport_route_delete(request, route_id):
    """Delete a transport route"""
    school = request.user.profile.school
    route = get_object_or_404(TransportRoute, id=route_id, school=school)
    
    # Check if route is used by any students
    students_using_route = Student.objects.filter(transport_route=route, school=school).count()
    
    if request.method == 'POST':
        if students_using_route > 0:
            messages.error(request, f'Cannot delete route. {students_using_route} student(s) are using this route.')
            return redirect('core:transport_route_list')
        route.delete()
        messages.success(request, 'Transport route deleted successfully.')
        return redirect('core:transport_route_list')
    
    context = {
        'route': route,
        'students_using_route': students_using_route,
    }
    return render(request, 'core/transport_route_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def activity_list(request):
    """List and create activities"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        charge = request.POST.get('charge')
        is_mandatory = request.POST.get('is_mandatory') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not charge:
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                Activity.objects.create(
                    school=school,
                    name=name,
                    description=description,
                    charge=charge,
                    is_mandatory=is_mandatory,
                    is_active=is_active
                )
                messages.success(request, 'Activity created successfully.')
                return redirect('core:activity_list')
            except Exception as e:
                messages.error(request, f'Error creating activity: {str(e)}')
    
    activities = Activity.objects.filter(school=school).order_by('is_mandatory', 'name')
    context = {
        'activities': activities,
    }
    return render(request, 'core/activity_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def activity_edit(request, activity_id):
    """Edit an activity"""
    school = request.user.profile.school
    activity = get_object_or_404(Activity, id=activity_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        charge = request.POST.get('charge')
        is_mandatory = request.POST.get('is_mandatory') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not charge:
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                activity.name = name
                activity.description = description
                activity.charge = charge
                activity.is_mandatory = is_mandatory
                activity.is_active = is_active
                activity.save()
                messages.success(request, 'Activity updated successfully.')
                return redirect('core:activity_list')
            except Exception as e:
                messages.error(request, f'Error updating activity: {str(e)}')
    
    context = {
        'activity': activity,
    }
    return render(request, 'core/activity_form.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def activity_delete(request, activity_id):
    """Delete an activity"""
    school = request.user.profile.school
    activity = get_object_or_404(Activity, id=activity_id, school=school)
    
    # Check if activity is assigned to any students
    students_with_activity = Student.objects.filter(activities=activity, school=school).count()
    
    if request.method == 'POST':
        if students_with_activity > 0:
            messages.error(request, f'Cannot delete activity. {students_with_activity} student(s) are assigned to this activity.')
            return redirect('core:activity_list')
        activity.delete()
        messages.success(request, 'Activity deleted successfully.')
        return redirect('core:activity_list')
    
    context = {
        'activity': activity,
        'students_with_activity': students_with_activity,
    }
    return render(request, 'core/activity_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def fee_category_list(request):
    """List and create fee categories"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_type = request.POST.get('category_type')
        description = request.POST.get('description', '')
        is_optional = request.POST.get('is_optional') == 'on'
        
        if not name or not category_type:
            messages.error(request, 'Please fill in all required fields.')
        else:
            try:
                FeeCategory.objects.create(
                    school=school,
                    name=name,
                    category_type=category_type,
                    description=description,
                    is_optional=is_optional
                )
                messages.success(request, 'Fee category created successfully.')
                return redirect('core:fee_category_list')
            except Exception as e:
                messages.error(request, f'Error creating fee category: {str(e)}')
    
    fee_categories = FeeCategory.objects.filter(school=school).order_by('category_type', 'name')
    
    context = {
        'fee_categories': fee_categories,
        'category_types': FeeCategory.CATEGORY_CHOICES,
    }
    return render(request, 'core/fee_category_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def generate_student_fees(request):
    """Generate student fees for a term"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        grade_id = request.POST.get('grade_id')
        
        if term_id and grade_id:
            term = get_object_or_404(Term, id=term_id, school=school)
            grade = get_object_or_404(Grade, id=grade_id, school=school)
            
            # Get fee structure for this grade and term
            fee_structures = FeeStructure.objects.filter(
                grade=grade,
                term=term,
                is_active=True
            )
            
            # Get students in this grade
            students = Student.objects.filter(grade=grade, school=school, is_active=True).prefetch_related('activities')
            
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
                        school=school,
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
                
                # Generate fees for individual activities
                if student.pays_activities:
                    # Get all activities for this student (including mandatory ones)
                    student_activities = student.activities.filter(is_active=True)
                    mandatory_activities = Activity.objects.filter(
                        school=school,
                        is_mandatory=True,
                        is_active=True
                    )
                    
                    # Add mandatory activities that student doesn't have exceptions for
                    for activity in mandatory_activities:
                        if not ActivityException.objects.filter(
                            school=school,
                            student=student,
                            activity=activity
                        ).exists():
                            student_activities = student_activities | Activity.objects.filter(id=activity.id)
                    
                    # Create fee for each activity
                    for activity in student_activities.distinct():
                        # Get or create fee category for this specific activity
                        activity_category, _ = FeeCategory.objects.get_or_create(
                            school=school,
                            name=f"{activity.name} Activity",
                            category_type='activities',
                            defaults={'description': f'Fee for {activity.name} activity'}
                        )
                        
                        student_fee, created = StudentFee.objects.get_or_create(
                            school=school,
                            student=student,
                            term=term,
                            fee_category=activity_category,
                            defaults={
                                'amount_charged': activity.charge,
                                'due_date': term.end_date,
                            }
                        )
                        
                        if created:
                            created_count += 1
            
            messages.success(request, f'Generated {created_count} fee records for {grade.name} in {term.name}.')
            return redirect('core:fee_structure_list')
    
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    grades = Grade.objects.filter(school=school)
    
    context = {'terms': terms, 'grades': grades}
    return render(request, 'core/generate_student_fees.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def student_fee_list(request):
    """List all student fees with payment tracking - grouped by student"""
    school = request.user.profile.school
    
    student_fees = StudentFee.objects.filter(school=school).select_related(
        'student', 'term', 'fee_category', 'student__grade'
    )
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        student_fees = student_fees.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    # Filter by term
    term_filter = request.GET.get('term', '')
    if term_filter:
        student_fees = student_fees.filter(term_id=term_filter)
    
    # Filter by grade
    grade_filter = request.GET.get('grade', '')
    if grade_filter:
        student_fees = student_fees.filter(student__grade_id=grade_filter)
    
    # Filter by payment status
    status_filter = request.GET.get('status', '')
    if status_filter == 'paid':
        student_fees = student_fees.filter(is_paid=True)
    elif status_filter == 'unpaid':
        student_fees = student_fees.filter(is_paid=False)
    elif status_filter == 'overdue':
        from django.utils import timezone
        student_fees = student_fees.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        )
    
    # Group fees by student and calculate totals
    from django.db.models import Sum, Count, Max
    from django.utils import timezone
    
    students_with_fees = Student.objects.filter(
        school=school,
        student_fees__in=student_fees
    ).distinct().select_related('grade').prefetch_related('student_fees')
    
    # Apply same filters to students query
    if search_query:
        students_with_fees = students_with_fees.filter(
            Q(student_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    if grade_filter:
        students_with_fees = students_with_fees.filter(grade_id=grade_filter)
    
    # Calculate totals for each student
    student_totals = []
    for student in students_with_fees:
        student_fee_list = student_fees.filter(student=student)
        
        # Apply term filter if specified
        if term_filter:
            student_fee_list = student_fee_list.filter(term_id=term_filter)
        
        # Apply status filter
        if status_filter == 'paid':
            student_fee_list = student_fee_list.filter(is_paid=True)
        elif status_filter == 'unpaid':
            student_fee_list = student_fee_list.filter(is_paid=False)
        elif status_filter == 'overdue':
            student_fee_list = student_fee_list.filter(
                is_paid=False,
                due_date__lt=timezone.now().date()
            )
        
        if student_fee_list.exists():
            totals = student_fee_list.aggregate(
                total_charged=Sum('amount_charged'),
                total_paid=Sum('amount_paid'),
                fee_count=Count('id'),
                has_overdue=Max('due_date')
            )
            
            total_balance = totals['total_charged'] - totals['total_paid']
            has_overdue = False
            if totals['has_overdue']:
                has_overdue = any(
                    not fee.is_paid and fee.due_date < timezone.now().date()
                    for fee in student_fee_list
                )
            
            all_paid = all(fee.is_paid for fee in student_fee_list)
            
            student_totals.append({
                'student': student,
                'fees': student_fee_list.order_by('-term__academic_year', '-term__term_number', 'fee_category__name'),
                'total_charged': totals['total_charged'] or 0,
                'total_paid': totals['total_paid'] or 0,
                'total_balance': total_balance,
                'fee_count': totals['fee_count'],
                'is_paid': all_paid,
                'has_overdue': has_overdue,
            })
    
    # Sort by student name
    student_totals.sort(key=lambda x: (x['student'].first_name, x['student'].last_name))
    
    # Pagination
    paginator = Paginator(student_totals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    grades = Grade.objects.filter(school=school)
    
    context = {
        'page_obj': page_obj,
        'terms': terms,
        'grades': grades,
        'search_query': search_query,
        'term_filter': term_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
    }
    return render(request, 'core/student_fee_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def student_fee_statement(request, student_id):
    """View fee statement for a student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, school=school, student_id=student_id)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    term_filter = request.GET.get('term')
    
    # Get student fees
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('-term__academic_year', '-term__term_number', 'fee_category__name')
    
    # Apply filters
    if term_filter:
        student_fees = student_fees.filter(term_id=term_filter)
    if start_date:
        student_fees = student_fees.filter(created_at__date__gte=start_date)
    if end_date:
        student_fees = student_fees.filter(created_at__date__lte=end_date)
    
    # Calculate totals
    totals = student_fees.aggregate(
        total_charged=Sum('amount_charged'),
        total_paid=Sum('amount_paid')
    )
    total_charged = totals['total_charged'] or 0
    total_paid = totals['total_paid'] or 0
    total_balance = total_charged - total_paid
    
    # Get payments for this student
    from payments.models import Payment
    payments = Payment.objects.filter(
        school=school,
        student=student
    ).select_related('student_fee__fee_category', 'student_fee__term').order_by('-payment_date')
    
    # Apply date filters to payments
    if start_date:
        payments = payments.filter(payment_date__date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__date__lte=end_date)
    
    # Get all terms for filter dropdown
    terms = Term.objects.filter(school=school).order_by('-academic_year', '-term_number')
    
    context = {
        'student': student,
        'school': school,
        'student_fees': student_fees,
        'payments': payments,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'terms': terms,
        'start_date': start_date,
        'end_date': end_date,
        'term_filter': term_filter,
        'statement_date': timezone.now().date(),
    }
    return render(request, 'core/student_fee_statement.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def student_fee_statement_pdf(request, student_id):
    """Download fee statement as PDF"""
    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        import os
    except ImportError:
        messages.error(request, 'PDF generation library not installed. Please install weasyprint.')
        return redirect('core:student_fee_statement', student_id=student_id)
    
    school = request.user.profile.school
    student = get_object_or_404(Student, school=school, student_id=student_id)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    term_filter = request.GET.get('term')
    
    # Get student fees
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('-term__academic_year', '-term__term_number', 'fee_category__name')
    
    # Apply filters
    if term_filter:
        student_fees = student_fees.filter(term_id=term_filter)
    if start_date:
        student_fees = student_fees.filter(created_at__date__gte=start_date)
    if end_date:
        student_fees = student_fees.filter(created_at__date__lte=end_date)
    
    # Calculate totals
    totals = student_fees.aggregate(
        total_charged=Sum('amount_charged'),
        total_paid=Sum('amount_paid')
    )
    total_charged = totals['total_charged'] or 0
    total_paid = totals['total_paid'] or 0
    total_balance = total_charged - total_paid
    
    # Get payments
    from payments.models import Payment
    payments = Payment.objects.filter(
        school=school,
        student=student
    ).select_related('student_fee__fee_category', 'student_fee__term').order_by('-payment_date')
    
    if start_date:
        payments = payments.filter(payment_date__date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__date__lte=end_date)
    
    context = {
        'student': student,
        'school': school,
        'student_fees': student_fees,
        'payments': payments,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'total_balance_abs': abs(total_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # Render HTML
    html_string = render_to_string('core/student_fee_statement_pdf.html', context)
    
    # Generate PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()
    
    # Create response
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"fee_statement_{student.student_id}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@role_required('super_admin', 'school_admin', 'accountant')
def student_fee_statement_email(request, student_id):
    """Email fee statement to parent"""
    school = request.user.profile.school
    student = get_object_or_404(Student, school=school, student_id=student_id)
    
    if not student.parent_email:
        messages.error(request, 'Student has no parent email address.')
        return redirect('core:student_fee_statement', student_id=student_id)
    
    # Get date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    term_filter = request.GET.get('term')
    
    # Get student fees
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('-term__academic_year', '-term__term_number', 'fee_category__name')
    
    # Apply filters
    if term_filter:
        student_fees = student_fees.filter(term_id=term_filter)
    if start_date:
        student_fees = student_fees.filter(created_at__date__gte=start_date)
    if end_date:
        student_fees = student_fees.filter(created_at__date__lte=end_date)
    
    # Calculate totals
    totals = student_fees.aggregate(
        total_charged=Sum('amount_charged'),
        total_paid=Sum('amount_paid')
    )
    total_charged = totals['total_charged'] or 0
    total_paid = totals['total_paid'] or 0
    total_balance = total_charged - total_paid
    
    # Get payments
    from payments.models import Payment
    payments = Payment.objects.filter(
        school=school,
        student=student
    ).select_related('student_fee__fee_category', 'student_fee__term').order_by('-payment_date')
    
    if start_date:
        payments = payments.filter(payment_date__date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__date__lte=end_date)
    
    try:
        from communications.services import CommunicationService
        
        # Generate PDF
        try:
            from weasyprint import HTML
            from django.template.loader import render_to_string
            import io
            
            context = {
                'student': student,
                'school': school,
                'student_fees': student_fees,
                'payments': payments,
                'total_charged': total_charged,
                'total_paid': total_paid,
                'total_balance': total_balance,
                'total_balance_abs': abs(total_balance),
                'start_date': start_date,
                'end_date': end_date,
                'statement_date': timezone.now().date(),
            }
            
            html_string = render_to_string('core/student_fee_statement_pdf.html', context)
            html = HTML(string=html_string, base_url=request.build_absolute_uri())
            pdf_buffer = io.BytesIO()
            html.write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
            # Create email content
            subject = f"Fee Statement - {student.full_name} - {school.name}"
            content = f"""
Dear {student.parent_name or 'Parent/Guardian'},

Please find attached the fee statement for {student.full_name} ({student.student_id}).

Summary:
- Total Charged: KES {total_charged:,.2f}
- Total Paid: KES {total_paid:,.2f}
- Balance: KES {total_balance:,.2f}

Please review the attached statement for detailed information.

Best regards,
{school.name} Administration
            """
            
            # Send email with PDF attachment
            from django.core.mail import EmailMessage
            email = EmailMessage(
                subject=subject,
                body=content,
                from_email=settings.EMAIL_HOST_USER,
                to=[student.parent_email]
            )
            email.attach(
                f"fee_statement_{student.student_id}_{timezone.now().strftime('%Y%m%d')}.pdf",
                pdf_buffer.read(),
                'application/pdf'
            )
            email.send()
            
            # Log the email
            communication_service = CommunicationService()
            communication_service.email_service.send_email(
                recipient_email=student.parent_email,
                subject=subject,
                content=content,
                student=student,
                sent_by=request.user
            )
            
            messages.success(request, f'Fee statement sent successfully to {student.parent_email}.')
            
        except ImportError:
            # Fallback: send email without PDF if weasyprint not available
            subject = f"Fee Statement - {student.full_name} - {school.name}"
            content = f"""
Dear {student.parent_name or 'Parent/Guardian'},

Fee Statement for {student.full_name} ({student.student_id})

Summary:
- Total Charged: KES {total_charged:,.2f}
- Total Paid: KES {total_paid:,.2f}
- Balance: KES {total_balance:,.2f}

Please log in to the school portal to view the detailed statement.

Best regards,
{school.name} Administration
            """
            
            communication_service = CommunicationService()
            communication_service.email_service.send_email(
                recipient_email=student.parent_email,
                subject=subject,
                content=content,
                student=student,
                sent_by=request.user
            )
            
            messages.success(request, f'Fee statement sent successfully to {student.parent_email}.')
            
    except Exception as e:
        messages.error(request, f'Error sending email: {str(e)}')
    
    return redirect('core:student_fee_statement', student_id=student_id)


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
    classes = SchoolClass.objects.filter(school=school).select_related('grade')
    return render(request, 'core/class_list.html', {'classes': classes})

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
        class_teacher = request.POST.get('class_teacher', '').strip()
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
            return render(request, 'core/class_form.html', {'grades': grades, 'post': request.POST, 'school_class': None})
        SchoolClass.objects.create(school=school, grade_id=grade_id, name=name, class_teacher=class_teacher, description=description)
        messages.success(request, 'Class added successfully!')
        return redirect('core:class_list')
    return render(request, 'core/class_form.html', {'grades': grades, 'post': {}, 'school_class': None})

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
        class_teacher = request.POST.get('class_teacher', '').strip()
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
            return render(request, 'core/class_form.html', {'grades': grades, 'post': request.POST, 'school_class': school_class})
        school_class.name = name
        school_class.grade_id = grade_id
        school_class.class_teacher = class_teacher
        school_class.description = description
        school_class.save()
        messages.success(request, 'Class updated successfully!')
        return redirect('core:class_list')
    return render(request, 'core/class_form.html', {'grades': grades, 'school_class': school_class})

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


# User Management Views
@login_required
@role_required('super_admin', 'school_admin')
def user_list(request):
    """List all users"""
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    return render(request, 'core/users/user_list.html', {'users': users})


@login_required
@role_required('super_admin', 'school_admin')
def user_create(request):
    """Create a new user with role assignment"""
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                # Create user first
                user = user_form.save()
                
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
        profile_form = UserProfileForm()
    
    return render(request, 'core/users/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': 'Create New User',
        'user': None
    })


@login_required
@role_required('super_admin', 'school_admin')
def user_edit(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            
            messages.success(request, f"User {user.username} updated successfully!")
            return redirect('core:user_list')
    else:
        user_form = UserEditForm(instance=user)
        profile_form = UserProfileForm(instance=user.profile)
    
    return render(request, 'core/users/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': f'Edit User: {user.username}',
        'user': user
    })


@login_required
@role_required('super_admin', 'school_admin')
def user_delete(request, user_id):
    """Delete a user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"User {username} deleted successfully!")
        return redirect('core:user_list')
    
    return render(request, 'core/users/user_confirm_delete.html', {'user': user})


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
            grouped_permissions[perm.resource_type] = []
        
        # Add permission with checked status
        grouped_permissions[perm.resource_type].append({
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
