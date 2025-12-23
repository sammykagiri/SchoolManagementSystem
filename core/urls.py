from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    SchoolViewSet, GradeViewSet, TermViewSet, FeeCategoryViewSet, TransportRouteViewSet,
    StudentViewSet, FeeStructureViewSet, StudentFeeViewSet, SchoolClassViewSet
)
from rest_framework.routers import DefaultRouter

app_name = 'core'

router = DefaultRouter()
router.register(r'api/schools', SchoolViewSet, basename='api-school')
router.register(r'api/grades', GradeViewSet, basename='api-grade')
router.register(r'api/terms', TermViewSet, basename='api-term')
router.register(r'api/fee-categories', FeeCategoryViewSet, basename='api-feecategory')
router.register(r'api/transport-routes', TransportRouteViewSet, basename='api-transportroute')
router.register(r'api/students', StudentViewSet, basename='api-student')
router.register(r'api/fee-structures', FeeStructureViewSet, basename='api-feestructure')
router.register(r'api/student-fees', StudentFeeViewSet, basename='api-studentfee')
router.register(r'api/classes', SchoolClassViewSet, basename='api-class')

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<str:student_id>/', views.student_detail, name='student_detail'),
    path('students/<str:student_id>/update/', views.student_update, name='student_update'),
    path('students/<str:student_id>/delete/', views.student_delete, name='student_delete'),
    
    # Grades
    path('grades/', views.grade_list, name='grade_list'),
    path('grades/<int:grade_id>/edit/', views.grade_edit, name='grade_edit'),
    path('grades/<int:grade_id>/delete/', views.grade_delete, name='grade_delete'),
    
    # Terms
    path('terms/', views.term_list, name='term_list'),
    path('terms/add/', views.term_add, name='term_add'),
    path('terms/<int:term_id>/edit/', views.term_edit, name='term_edit'),
    path('terms/<int:term_id>/delete/', views.term_delete, name='term_delete'),
    
    # Fee Structures
    path('fee-structures/', views.fee_structure_list, name='fee_structure_list'),
    path('generate-fees/', views.generate_student_fees, name='generate_student_fees'),
    
    # API endpoints
    path('api/dashboard/', views.api_dashboard, name='api_dashboard'),
    path('api/students/<str:student_id>/fees/', views.get_student_fees, name='get_student_fees'),
    path('api/transport-routes/', views.get_transport_routes, name='get_transport_routes'),

    # Authentication
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='auth/logout.html'), name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='auth/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='auth/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html'), name='password_reset_complete'),

    # User Profile
    path('accounts/profile/', views.profile_view, name='profile'),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(template_name='auth/change_password.html'), name='change_password'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='auth/password_reset_done.html'), name='password_change_done'),

    # School (user profile update)
    path('school/update/', views.school_update, name='school_update'),
    path('school/add/', views.school_add, name='school_add'),

    # Admin - Schools
    path('manage/schools/', views.school_admin_list, name='school_admin_list'),
    path('manage/schools/<int:school_id>/edit/', views.school_admin_edit, name='school_admin_edit'),
    path('manage/schools/<int:school_id>/delete/', views.school_admin_delete, name='school_admin_delete'),

    # API endpoints for school create/update (admin only)
    path('api/schools/create/', views.api_school_create, name='api_school_create'),
    path('api/schools/<int:pk>/update/', views.api_school_update, name='api_school_update'),

    # Classes
    path('classes/', views.class_list, name='class_list'),
    path('classes/add/', views.class_add, name='class_add'),
    path('classes/<int:class_id>/edit/', views.class_edit, name='class_edit'),
    path('classes/<int:class_id>/delete/', views.class_delete, name='class_delete'),
    
    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    
    # Role Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/<int:role_id>/permissions/', views.role_permissions, name='role_permissions'),
]

urlpatterns += router.urls