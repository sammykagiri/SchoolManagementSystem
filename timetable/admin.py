from django.contrib import admin
from .models import Subject, Teacher, TimeSlot, Timetable, SubjectPathway, StudentSubjectSelection


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'knec_code', 'learning_level', 
        'is_compulsory', 'is_religious_education', 'is_active', 'school'
    ]
    list_filter = [
        'is_active', 'school', 'learning_level', 
        'is_compulsory', 'is_religious_education', 'pathway'
    ]
    search_fields = ['name', 'code', 'knec_code']
    filter_horizontal = ['applicable_grades']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('school', 'name', 'code', 'knec_code', 'description', 'is_active')
        }),
        ('CBC Information', {
            'fields': ('learning_level', 'is_compulsory', 'applicable_grades', 'pathway')
        }),
        ('Religious Education', {
            'fields': ('is_religious_education', 'religious_type'),
            'classes': ('collapse',)
        }),
    )


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


@admin.register(SubjectPathway)
class SubjectPathwayAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'is_active']
    list_filter = ['is_active', 'school', 'name']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(StudentSubjectSelection)
class StudentSubjectSelectionAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'subject', 'created_at']
    list_filter = ['term', 'subject__is_religious_education', 'school']
    search_fields = ['student__first_name', 'student__last_name', 'subject__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['student', 'term', 'subject']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['school_class', 'subject', 'teacher', 'time_slot', 'room', 'is_active']
    list_filter = ['is_active', 'school', 'time_slot__day']
    search_fields = ['school_class__name', 'subject__name', 'teacher__first_name']
    ordering = ['school_class', 'time_slot__day', 'time_slot__period_number']
