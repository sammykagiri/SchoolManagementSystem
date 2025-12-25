from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubjectViewSet, TeacherViewSet, TimeSlotViewSet, TimetableViewSet,
    timetable_list, subject_list, subject_detail, subject_add, subject_edit, subject_delete, teacher_list
)

app_name = 'timetable'

router = DefaultRouter()
router.register(r'api/subjects', SubjectViewSet, basename='api-subject')
router.register(r'api/teachers', TeacherViewSet, basename='api-teacher')
router.register(r'api/time-slots', TimeSlotViewSet, basename='api-timeslot')
router.register(r'api/timetables', TimetableViewSet, basename='api-timetable')

urlpatterns = [
    path('', timetable_list, name='timetable_list'),
    path('subjects/', subject_list, name='subject_list'),
    path('subjects/<int:subject_id>/', subject_detail, name='subject_detail'),
    path('subjects/add/', subject_add, name='subject_add'),
    path('subjects/<int:subject_id>/edit/', subject_edit, name='subject_edit'),
    path('subjects/<int:subject_id>/delete/', subject_delete, name='subject_delete'),
    path('teachers/', teacher_list, name='teacher_list'),
    path('', include(router.urls)),
]

