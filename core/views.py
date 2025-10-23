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
from rest_framework import viewsets, permissions
from .serializers import (
    SchoolSerializer, GradeSerializer, TermSerializer, FeeCategorySerializer,
    TransportRouteSerializer, StudentSerializer, FeeStructureSerializer, StudentFeeSerializer, SchoolClassSerializer
)
from .forms import StudentForm
import json
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.permissions import BasePermission


class IsSuperUser(BasePermission):
    """Allows access only to superusers."""
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


@login_required
def dashboard(request):
    """Main dashboard view"""
    school = request.user.profile.school
    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_terms = Term.objects.filter(school=school).count()
    total_grades = Grade.objects.filter(school=school).count()
    current_term = Term.objects.filter(school=school, is_active=True).first()
    if current_term:
        total_fees_charged = StudentFee.objects.filter(school=school, term=current_term).aggregate(
            total=Sum('amount_charged')
        )['total'] or 0
        total_fees_paid = StudentFee.objects.filter(school=school, term=current_term).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        overdue_fees = StudentFee.objects.filter(
            school=school,
            term=current_term,
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).count()
    else:
        total_fees_charged = 0
        total_fees_paid = 0
        overdue_fees = 0
    recent_students = Student.objects.filter(school=school, is_active=True).order_by('-created_at')[:5]
    overdue_payments = StudentFee.objects.filter(
        school=school,
        is_paid=False,
        due_date__lt=timezone.now().date()
    ).select_related('student', 'fee_category', 'term')[:10]
    context = {
        'total_students': total_students,
        'total_terms': total_terms,
        'total_grades': total_grades,
        'current_term': current_term,
        'total_fees_charged': total_fees_charged,
        'total_fees_paid': total_fees_paid,
        'overdue_fees': overdue_fees,
        'recent_students': recent_students,
        'overdue_payments': overdue_payments,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def student_list(request):
    """List all students"""
    school = request.user.profile.school
    students = Student.objects.filter(school=school, is_active=True).select_related('grade', 'transport_route')
    
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
def student_detail(request, student_id):
    """Student detail view"""
    student = get_object_or_404(Student, student_id=student_id)
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
def student_create(request):
    """Create new student using Django form"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        form = StudentForm(request.POST, school=school)
        if form.is_valid():
            try:
                # Auto-generate student_id
                last_student = Student.objects.filter(school=school).exclude(student_id='').order_by('-id').first()
                if last_student and last_student.student_id and last_student.student_id.isdigit():
                    next_id = int(last_student.student_id) + 1
                    student_id = str(next_id).zfill(5)
                else:
                    student_id = '00001'
                
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
def student_update(request, student_id):
    """Update student"""
    student = get_object_or_404(Student, student_id=student_id)
    
    if request.method == 'POST':
        # Handle form submission
        student.first_name = request.POST.get('first_name')
        student.last_name = request.POST.get('last_name')
        student.gender = request.POST.get('gender')
        student.date_of_birth = request.POST.get('date_of_birth')
        student.grade_id = request.POST.get('grade')
        student.admission_date = request.POST.get('admission_date')
        student.parent_name = request.POST.get('parent_name')
        student.parent_phone = request.POST.get('parent_phone')
        student.parent_email = request.POST.get('parent_email')
        student.address = request.POST.get('address')
        student.uses_transport = request.POST.get('uses_transport') == 'on'
        student.pays_meals = request.POST.get('pays_meals') == 'on'
        student.pays_activities = request.POST.get('pays_activities') == 'on'
        
        transport_route_id = request.POST.get('transport_route')
        if transport_route_id:
            student.transport_route_id = transport_route_id
        else:
            student.transport_route = None
        
        try:
            student.save()
            messages.success(request, f'Student {student.full_name} updated successfully.')
            return redirect('core:student_detail', student_id=student.student_id)
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    grades = Grade.objects.all()
    transport_routes = TransportRoute.objects.filter(is_active=True)
    
    context = {
        'student': student,
        'grades': grades,
        'transport_routes': transport_routes,
        'title': 'Update Student'
    }
    return render(request, 'core/student_form.html', context)


@login_required
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
def term_list(request):
    """List all terms"""
    school = request.user.profile.school
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    
    context = {'terms': terms}
    return render(request, 'core/term_list.html', context)


@login_required
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
def fee_structure_list(request):
    """List fee structures"""
    fee_structures = FeeStructure.objects.filter(is_active=True).select_related(
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
                grade_id=grade_id,
                term_id=term_id,
                fee_category_id=fee_category_id,
                amount=amount
            )
            messages.success(request, 'Fee structure created successfully.')
            return redirect('core:fee_structure_list')
        except Exception as e:
            messages.error(request, f'Error creating fee structure: {str(e)}')
    
    grades = Grade.objects.all()
    terms = Term.objects.all().order_by('-academic_year', '-term_number')
    fee_categories = FeeCategory.objects.all()
    
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
        # Auto-generate student_id
        last_student = Student.objects.filter(school=school).exclude(student_id='').order_by('-id').first()
        if last_student and last_student.student_id and last_student.student_id.isdigit():
            next_id = int(last_student.student_id) + 1
            student_id = str(next_id).zfill(5)
        else:
            student_id = '00001'
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
def class_list(request):
    school = request.user.profile.school
    classes = SchoolClass.objects.filter(school=school).select_related('grade')
    return render(request, 'core/class_list.html', {'classes': classes})

@login_required
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
def class_delete(request, class_id):
    school = request.user.profile.school
    school_class = get_object_or_404(SchoolClass, id=class_id, school=school)
    if request.method == 'POST':
        school_class.delete()
        messages.success(request, 'Class deleted successfully!')
        return redirect('core:class_list')
    return render(request, 'core/class_confirm_delete.html', {'school_class': school_class})
