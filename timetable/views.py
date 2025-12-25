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
