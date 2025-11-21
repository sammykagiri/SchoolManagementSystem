from django.contrib import admin
from .models import Attendance, AttendanceSummary


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'status', 'school_class', 'marked_by', 'created_at']
    list_filter = ['status', 'date', 'school']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id']
    date_hierarchy = 'date'
    ordering = ['-date', 'student']


@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'total_days', 'days_present', 'attendance_percentage']
    list_filter = ['term', 'school']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id']
    ordering = ['-term', 'student']
