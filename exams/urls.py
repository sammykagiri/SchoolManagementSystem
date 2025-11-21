from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExamTypeViewSet, ExamViewSet, GradebookViewSet, GradebookSummaryViewSet,
    exam_list, gradebook_list, gradebook_summary_list
)

app_name = 'exams'

router = DefaultRouter()
router.register(r'api/exam-types', ExamTypeViewSet, basename='api-exam-type')
router.register(r'api/exams', ExamViewSet, basename='api-exam')
router.register(r'api/gradebooks', GradebookViewSet, basename='api-gradebook')
router.register(r'api/gradebook-summaries', GradebookSummaryViewSet, basename='api-gradebook-summary')

urlpatterns = [
    path('', exam_list, name='exam_list'),
    path('gradebooks/', gradebook_list, name='gradebook_list'),
    path('summaries/', gradebook_summary_list, name='gradebook_summary_list'),
    path('', include(router.urls)),
]

