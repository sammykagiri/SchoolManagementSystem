from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AttendanceViewSet, AttendanceSummaryViewSet,
    attendance_list, mark_attendance, attendance_summary,
    attendance_edit, attendance_delete
)

app_name = 'attendance'

router = DefaultRouter()
router.register(r'api/attendances', AttendanceViewSet, basename='api-attendance')
router.register(r'api/attendance-summaries', AttendanceSummaryViewSet, basename='api-attendance-summary')

urlpatterns = [
    path('', attendance_list, name='attendance_list'),
    path('mark/', mark_attendance, name='mark_attendance'),
    path('summary/', attendance_summary, name='attendance_summary'),
    path('<int:attendance_id>/edit/', attendance_edit, name='attendance_edit'),
    path('<int:attendance_id>/delete/', attendance_delete, name='attendance_delete'),
    path('', include(router.urls)),
]

