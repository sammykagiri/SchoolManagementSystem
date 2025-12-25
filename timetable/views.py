from rest_framework import viewsets, permissions
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Subject, Teacher, TimeSlot, Timetable
from .serializers import SubjectSerializer, TeacherSerializer, TimeSlotSerializer, TimetableSerializer
from core.models import SchoolClass


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Subject.objects.filter(school=school)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TeacherViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Teacher.objects.filter(school=school).prefetch_related('subjects')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subjects__id=subject_id)
        
        return queryset.order_by('first_name', 'last_name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TimeSlotViewSet(viewsets.ModelViewSet):
    serializer_class = TimeSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = TimeSlot.objects.filter(school=school)
        
        day = self.request.query_params.get('day')
        if day:
            queryset = queryset.filter(day=day)
        
        return queryset.order_by('day', 'period_number')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TimetableViewSet(viewsets.ModelViewSet):
    serializer_class = TimetableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Timetable.objects.filter(school=school).select_related(
            'school_class', 'subject', 'teacher', 'time_slot'
        )
        
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        
        day = self.request.query_params.get('day')
        if day:
            queryset = queryset.filter(time_slot__day=day)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('school_class', 'time_slot__day', 'time_slot__period_number')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


# UI Views
@login_required
def timetable_list(request):
    """List timetables"""
    school = request.user.profile.school
    timetables = Timetable.objects.filter(school=school, is_active=True).select_related(
        'school_class', 'subject', 'teacher', 'time_slot'
    ).order_by('school_class', 'time_slot__day', 'time_slot__period_number')
    
    class_id = request.GET.get('class_id', '')
    if class_id:
        timetables = timetables.filter(school_class_id=class_id)
    
    day = request.GET.get('day', '')
    if day:
        timetables = timetables.filter(time_slot__day=day)
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    # Group by class and day
    timetable_dict = {}
    for tt in timetables:
        class_name = tt.school_class.name
        day_name = tt.time_slot.get_day_display()
        if class_name not in timetable_dict:
            timetable_dict[class_name] = {}
        if day_name not in timetable_dict[class_name]:
            timetable_dict[class_name][day_name] = []
        timetable_dict[class_name][day_name].append(tt)
    
    context = {
        'timetable_dict': timetable_dict,
        'classes': classes,
        'class_id': class_id,
        'day': day,
    }
    return render(request, 'timetable/timetable_list.html', context)


@login_required
def subject_list(request):
    """List subjects"""
    school = request.user.profile.school
    subjects = Subject.objects.filter(school=school).order_by('name')
    
    context = {'subjects': subjects}
    return render(request, 'timetable/subject_list.html', context)


@login_required
def subject_detail(request, subject_id):
    """View subject details"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    context = {'subject': subject}
    return render(request, 'timetable/subject_detail.html', context)


@login_required
def subject_add(request):
    """Add a new subject"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not name:
            errors.append('Subject name is required.')
        
        # Check for duplicate subject name and code in the same school
        # First check if the exact combination exists (same subject with both name and code)
        exact_match = name and code and Subject.objects.filter(school=school, name=name, code=code).exists()
        name_exists = name and Subject.objects.filter(school=school, name=name).exists()
        code_exists = code and Subject.objects.filter(school=school, code=code).exists()
        
        if exact_match:
            errors.append('A subject with this name and code already exists.')
        elif name_exists:
            errors.append('A subject with this name already exists.')
        elif code_exists:
            errors.append('A subject with this code already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/subject_form.html', {
                'name': name,
                'code': code,
                'description': description,
                'is_active': is_active,
            })
        
        # Create the subject
        subject = Subject.objects.create(
            school=school,
            name=name,
            code=code,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Subject "{subject.name}" added successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_form.html')


@login_required
def subject_edit(request, subject_id):
    """Edit an existing subject"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not name:
            errors.append('Subject name is required.')
        
        # Check for duplicate subject name and code in the same school (excluding current subject)
        # First check if the exact combination exists (same subject with both name and code)
        exact_match = name and code and Subject.objects.filter(school=school, name=name, code=code).exclude(id=subject.id).exists()
        name_exists = name and Subject.objects.filter(school=school, name=name).exclude(id=subject.id).exists()
        code_exists = code and Subject.objects.filter(school=school, code=code).exclude(id=subject.id).exists()
        
        if exact_match:
            errors.append('A subject with this name and code already exists.')
        elif name_exists:
            errors.append('A subject with this name already exists.')
        elif code_exists:
            errors.append('A subject with this code already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/subject_form.html', {
                'subject': subject,
                'name': name,
                'code': code,
                'description': description,
                'is_active': is_active,
            })
        
        # Update the subject
        subject.name = name
        subject.code = code
        subject.description = description
        subject.is_active = is_active
        subject.save()
        
        messages.success(request, f'Subject "{subject.name}" updated successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_form.html', {
        'subject': subject,
        'name': subject.name,
        'code': subject.code,
        'description': subject.description,
        'is_active': subject.is_active,
    })


@login_required
def subject_delete(request, subject_id):
    """Delete a subject"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    if request.method == 'POST':
        subject_name = subject.name
        subject.delete()
        messages.success(request, f'Subject "{subject_name}" deleted successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_confirm_delete.html', {'subject': subject})


@login_required
def teacher_list(request):
    """List teachers"""
    school = request.user.profile.school
    teachers = Teacher.objects.filter(school=school).prefetch_related('subjects').order_by('first_name', 'last_name')
    
    # Filter by active status (default: show active only)
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
    return render(request, 'timetable/teacher_list.html', context)
