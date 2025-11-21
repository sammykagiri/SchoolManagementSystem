from django.contrib import admin
from .models import Subject, Teacher, TimeSlot, Timetable


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'school']
    list_filter = ['is_active', 'school']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'first_name', 'last_name', 'email', 'is_active', 'school']
    list_filter = ['is_active', 'school']
    search_fields = ['first_name', 'last_name', 'employee_id', 'email']
    filter_horizontal = ['subjects']
    ordering = ['first_name', 'last_name']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['day', 'period_number', 'start_time', 'end_time', 'is_break', 'school']
    list_filter = ['day', 'is_break', 'school']
    ordering = ['day', 'period_number']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['school_class', 'subject', 'teacher', 'time_slot', 'room', 'is_active']
    list_filter = ['is_active', 'school', 'time_slot__day']
    search_fields = ['school_class__name', 'subject__name', 'teacher__first_name']
    ordering = ['school_class', 'time_slot__day', 'time_slot__period_number']
