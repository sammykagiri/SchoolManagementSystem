from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AssignmentViewSet, AssignmentSubmissionViewSet,
    assignment_list, assignment_create, assignment_detail, assignment_update, assignment_delete,
    submission_list, submission_create, submission_detail, grade_submission
)

app_name = 'homework'

router = DefaultRouter()
router.register(r'api/assignments', AssignmentViewSet, basename='api-assignment')
router.register(r'api/submissions', AssignmentSubmissionViewSet, basename='api-submission')

urlpatterns = [
    # UI Views
    path('', assignment_list, name='assignment_list'),
    path('create/', assignment_create, name='assignment_create'),
    path('<int:assignment_id>/', assignment_detail, name='assignment_detail'),
    path('<int:assignment_id>/edit/', assignment_update, name='assignment_update'),
    path('<int:assignment_id>/delete/', assignment_delete, name='assignment_delete'),
    path('<int:assignment_id>/submit/', submission_create, name='submission_create'),
    
    # Submissions
    path('submissions/', submission_list, name='submission_list'),
    path('submissions/<int:submission_id>/', submission_detail, name='submission_detail'),
    path('submissions/<int:submission_id>/grade/', grade_submission, name='grade_submission'),
    
    # API endpoints
    path('', include(router.urls)),
]

