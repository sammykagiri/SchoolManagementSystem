from django.contrib import admin
from .models import Grade, Term, FeeCategory, TransportRoute, Student, FeeStructure, StudentFee, SchoolClass


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['name', 'term_number', 'academic_year', 'start_date', 'end_date', 'is_active']
    list_filter = ['is_active', 'term_number', 'academic_year']
    search_fields = ['name', 'academic_year']
    ordering = ['-academic_year', '-term_number']


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'is_optional', 'created_at']
    list_filter = ['category_type', 'is_optional']
    search_fields = ['name', 'description']
    ordering = ['category_type', 'name']


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_fare', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'first_name', 'last_name', 'grade', 'parent_name', 'parent_phone', 'is_active']
    list_filter = ['grade', 'gender', 'is_active', 'uses_transport', 'pays_meals', 'pays_activities']
    search_fields = ['student_id', 'first_name', 'last_name', 'parent_name', 'parent_phone', 'parent_email']
    ordering = ['grade', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('student_id', 'first_name', 'last_name', 'gender', 'date_of_birth', 'grade', 'admission_date', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('parent_name', 'parent_phone', 'parent_email', 'address')
        }),
        ('Transport & Fees', {
            'fields': ('transport_route', 'uses_transport', 'pays_meals', 'pays_activities')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['grade', 'term', 'fee_category', 'amount', 'is_active']
    list_filter = ['grade', 'term', 'fee_category__category_type', 'is_active']
    search_fields = ['grade__name', 'term__name', 'fee_category__name']
    ordering = ['grade', 'term', 'fee_category']


@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'fee_category', 'amount_charged', 'amount_paid', 'balance', 'is_paid', 'is_overdue']
    list_filter = ['term', 'fee_category', 'is_paid']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name']
    ordering = ['student', 'term', 'fee_category']
    readonly_fields = ['balance', 'is_overdue', 'created_at', 'updated_at']
    
    def balance(self, obj):
        return obj.balance
    balance.short_description = 'Balance'
    
    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'


admin.site.register(SchoolClass)
