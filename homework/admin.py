from django.contrib import admin
from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'school_class', 'teacher', 'due_date', 'is_active', 'submission_count']
    list_filter = ['is_active', 'subject', 'school_class', 'due_date']
    search_fields = ['title', 'description', 'subject__name', 'school_class__name']
    readonly_fields = ['created_at', 'updated_at', 'submission_count', 'pending_submissions_count']
    ordering = ['-due_date', 'subject']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'subject', 'school_class', 'teacher')
        }),
        ('Details', {
            'fields': ('due_date', 'max_marks', 'attachment', 'is_active')
        }),
        ('Statistics', {
            'fields': ('submission_count', 'pending_submissions_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'assignment', 'submitted_at', 'marks_obtained', 'status', 'graded_by']
    list_filter = ['status', 'submitted_at', 'assignment__subject', 'assignment__school_class']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id', 'assignment__title']
    readonly_fields = ['submitted_at', 'graded_at', 'created_at', 'updated_at', 'percentage', 'is_late']
    ordering = ['-submitted_at']
    
    fieldsets = (
        ('Submission Information', {
            'fields': ('assignment', 'student', 'submission_file', 'submission_text', 'submitted_at', 'is_late')
        }),
        ('Grading', {
            'fields': ('marks_obtained', 'percentage', 'feedback', 'graded_by', 'graded_at', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
