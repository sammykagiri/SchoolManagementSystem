"""
Serializers for homework module
"""
from rest_framework import serializers
from .models import Assignment, AssignmentSubmission
from core.serializers import StudentSerializer
from timetable.serializers import SubjectSerializer
from core.models import Student, SchoolClass
from timetable.models import Subject


class AssignmentSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source='subject', write_only=True
    )
    school_class_name = serializers.CharField(source='school_class.name', read_only=True)
    school_class_id = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), source='school_class', write_only=True
    )
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    submission_count = serializers.IntegerField(read_only=True)
    pending_submissions_count = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'subject', 'subject_id', 'school_class', 'school_class_name',
            'school_class_id', 'teacher', 'teacher_name', 'due_date', 'max_marks', 'attachment',
            'is_active', 'submission_count', 'pending_submissions_count', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'subject', 'school_class', 'teacher', 'submission_count',
                           'pending_submissions_count', 'is_overdue', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            school = request.user.profile.school
            if school:
                self.fields['subject_id'].queryset = Subject.objects.filter(school=school, is_active=True)
                self.fields['school_class_id'].queryset = SchoolClass.objects.filter(school=school, is_active=True)


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment = AssignmentSerializer(read_only=True)
    assignment_id = serializers.PrimaryKeyRelatedField(
        queryset=Assignment.objects.all(), source='assignment', write_only=True
    )
    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), source='student', write_only=True
    )
    graded_by_name = serializers.CharField(source='graded_by.get_full_name', read_only=True, allow_null=True)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'assignment', 'assignment_id', 'student', 'student_id', 'submission_file',
            'submission_text', 'submitted_at', 'marks_obtained', 'feedback', 'graded_by',
            'graded_by_name', 'graded_at', 'status', 'percentage', 'is_late',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'assignment', 'student', 'submitted_at', 'graded_by',
                           'graded_at', 'percentage', 'is_late', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            school = request.user.profile.school
            if school:
                self.fields['assignment_id'].queryset = Assignment.objects.filter(school=school)
                self.fields['student_id'].queryset = Student.objects.filter(school=school, is_active=True)

