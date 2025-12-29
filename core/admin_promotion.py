"""
Admin registrations for promotion-related models
Append this to core/admin.py
"""

from django.contrib import admin
from .models import AcademicYear, Section, StudentClassEnrollment, PromotionLog


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_active', 'is_current', 'school', 'created_at']
    list_filter = ['is_active', 'is_current', 'school']
    search_fields = ['name', 'school__name']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'school_class', 'capacity', 'is_active', 'school']
    list_filter = ['is_active', 'school_class__grade', 'school']
    search_fields = ['name', 'school_class__name']
    ordering = ['school_class__grade__name', 'school_class__name', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StudentClassEnrollment)
class StudentClassEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'academic_year', 'grade', 'school_class', 'section', 'roll_number', 'status', 'enrollment_date']
    list_filter = ['status', 'academic_year', 'grade', 'school_class', 'enrollment_date']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id', 'academic_year__name']
    ordering = ['-academic_year__start_date', 'grade__name', 'roll_number', 'student__first_name']
    readonly_fields = ['enrollment_date', 'created_at', 'updated_at']


@admin.register(PromotionLog)
class PromotionLogAdmin(admin.ModelAdmin):
    list_display = ['from_academic_year', 'to_academic_year', 'promotion_type', 'total_students', 
                   'promoted_count', 'retained_count', 'graduated_count', 'left_count', 
                   'promoted_by', 'created_at']
    list_filter = ['promotion_type', 'created_at', 'school']
    search_fields = ['from_academic_year__name', 'to_academic_year__name', 'promoted_by__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

