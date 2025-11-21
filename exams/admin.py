from django.contrib import admin
from .models import ExamType, Exam, Gradebook, GradebookSummary


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'weight', 'is_active', 'school']
    list_filter = ['is_active', 'school']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'exam_type', 'exam_date', 'max_marks', 'school']
    list_filter = ['exam_type', 'exam_date', 'school', 'term']
    search_fields = ['name', 'subject__name']
    date_hierarchy = 'exam_date'
    ordering = ['-exam_date', 'subject']


@admin.register(Gradebook)
class GradebookAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'marks_obtained', 'grade', 'percentage', 'is_passing']
    list_filter = ['grade', 'school', 'exam__term']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id']
    ordering = ['student', 'exam']


@admin.register(GradebookSummary)
class GradebookSummaryAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'subject', 'average_percentage', 'final_grade', 'rank']
    list_filter = ['term', 'final_grade', 'school']
    search_fields = ['student__first_name', 'student__last_name', 'subject__name']
    ordering = ['student', 'term', 'subject']
