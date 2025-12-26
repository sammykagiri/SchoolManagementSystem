from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubjectViewSet, TeacherViewSet, TimeSlotViewSet, TimetableViewSet,
    timetable_list, timetable_add, timetable_edit, timetable_delete, timetable_generate, timetable_print,
    subject_list, subject_detail, subject_add, subject_edit, subject_delete, teacher_list,
    timeslot_list, timeslot_add, timeslot_edit, timeslot_delete, timeslot_generate, timeslot_bulk_delete
)

app_name = 'timetable'

router = DefaultRouter()
router.register(r'api/subjects', SubjectViewSet, basename='api-subject')
router.register(r'api/teachers', TeacherViewSet, basename='api-teacher')
router.register(r'api/time-slots', TimeSlotViewSet, basename='api-timeslot')
router.register(r'api/timetables', TimetableViewSet, basename='api-timetable')

urlpatterns = [
    path('', timetable_list, name='timetable_list'),
    path('add/', timetable_add, name='timetable_add'),
    path('generate/', timetable_generate, name='timetable_generate'),
    path('print/', timetable_print, name='timetable_print'),
    path('<int:timetable_id>/edit/', timetable_edit, name='timetable_edit'),
    path('<int:timetable_id>/delete/', timetable_delete, name='timetable_delete'),
    path('subjects/', subject_list, name='subject_list'),
    path('subjects/<int:subject_id>/', subject_detail, name='subject_detail'),
    path('subjects/add/', subject_add, name='subject_add'),
    path('subjects/<int:subject_id>/edit/', subject_edit, name='subject_edit'),
    path('subjects/<int:subject_id>/delete/', subject_delete, name='subject_delete'),
    path('teachers/', teacher_list, name='teacher_list'),
    path('time-slots/', timeslot_list, name='timeslot_list'),
    path('time-slots/add/', timeslot_add, name='timeslot_add'),
    path('time-slots/generate/', timeslot_generate, name='timeslot_generate'),
    path('time-slots/bulk-delete/', timeslot_bulk_delete, name='timeslot_bulk_delete'),
    path('time-slots/<int:timeslot_id>/edit/', timeslot_edit, name='timeslot_edit'),
    path('time-slots/<int:timeslot_id>/delete/', timeslot_delete, name='timeslot_delete'),
    path('', include(router.urls)),
]

