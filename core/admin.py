from django.contrib import admin
from .models import (
    School, Grade, Term, FeeCategory, FeeCategoryType, TransportRoute, Student, FeeStructure, StudentFee, 
    SchoolClass, Role, Permission, UserProfile, Parent,
    AcademicYear, Section, StudentClassEnrollment, PromotionLog
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'email', 'phone', 'created_at']
    search_fields = ['name', 'short_name', 'email']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'short_name', 'email', 'phone', 'address')
        }),
        ('Branding', {
            'fields': ('logo', 'primary_color', 'secondary_color', 'use_color_scheme', 'use_secondary_on_headers')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


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


@admin.register(FeeCategoryType)
class FeeCategoryTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'school', 'created_at']
    list_filter = ['is_active', 'school']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'is_optional', 'created_at']
    list_filter = ['category_type', 'is_optional']
    search_fields = ['name', 'description']
    ordering = ['category_type__name', 'name']


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_fare', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'upi', 'first_name', 'middle_name', 'last_name', 'grade', 'linked_account', 'parent_name', 'parent_phone', 'linked_parents', 'is_active']
    list_filter = ['grade', 'gender', 'is_active', 'uses_transport', 'pays_meals', 'pays_activities']
    search_fields = ['student_id', 'upi', 'first_name', 'middle_name', 'last_name', 'parent_name', 'parent_phone', 'parent_email', 'user__username', 'user__email']
    ordering = ['grade', 'first_name', 'middle_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['parents']
    fieldsets = (
        ('Basic Information', {
            'fields': ('student_id', 'upi', 'first_name', 'middle_name', 'last_name', 'gender', 'date_of_birth', 'grade', 'admission_date', 'is_active')
        }),
        ('Linked Accounts', {
            'fields': ('user', 'parents')
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

    def linked_parents(self, obj):
        return ", ".join(parent.full_name for parent in obj.parents.all()) or "—"
    linked_parents.short_description = 'Linked Parents'

    def linked_account(self, obj):
        return obj.user.username if obj.user else "—"
    linked_account.short_description = 'Student Account'


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['grade', 'term', 'fee_category', 'amount', 'is_active']
    list_filter = ['grade', 'term', 'fee_category__category_type__name', 'is_active']
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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_display_name', 'is_active', 'permissions_count', 'users_count']
    list_filter = ['is_active', 'name']
    search_fields = ['name', 'description']
    filter_horizontal = ['permissions']
    readonly_fields = ['created_at', 'updated_at']
    
    def permissions_count(self, obj):
        return obj.permissions.count()
    permissions_count.short_description = 'Permissions'
    
    def users_count(self, obj):
        return obj.user_profiles.count()
    users_count.short_description = 'Users'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'permission_type', 'resource_type', 'roles_count']
    list_filter = ['permission_type', 'resource_type']
    search_fields = ['permission_type', 'resource_type']
    readonly_fields = ['codename', 'roles_count']
    
    def roles_count(self, obj):
        return obj.roles.count()
    roles_count.short_description = 'Roles'
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('permission_type', 'resource_type', 'codename')
        }),
        ('Statistics', {
            'fields': ('roles_count',),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'get_roles_display', 'is_active']
    list_filter = ['is_active', 'school', 'roles']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    filter_horizontal = ['roles']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'school', 'is_active')
        }),
        ('Roles', {
            'fields': ('roles',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'phone', 'email', 'is_active', 'children_count']
    list_filter = ['is_active', 'school']
    search_fields = ['user__username', 'user__email', 'phone', 'email']
    readonly_fields = ['created_at', 'updated_at', 'children_count']
    
    def children_count(self, obj):
        return obj.students.count()
    children_count.short_description = 'Children'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'school', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Statistics', {
            'fields': ('children_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


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
