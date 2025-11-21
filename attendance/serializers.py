from rest_framework import serializers
from .models import Attendance, AttendanceSummary
from core.serializers import StudentSerializer, SchoolClassSerializer


class AttendanceSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    marked_by_username = serializers.CharField(source='marked_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_id', 'school_class', 'school_class_id',
            'date', 'status', 'remarks', 'marked_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'school_class', 'created_at', 'updated_at']

    def create(self, validated_data):
        student_id = validated_data.pop('student_id', None)
        school_class_id = validated_data.pop('school_class_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        student_id = validated_data.pop('student_id', None)
        school_class_id = validated_data.pop('school_class_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        
        return super().update(instance, validated_data)


class AttendanceSummarySerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    term_academic_year = serializers.CharField(source='term.academic_year', read_only=True)

    class Meta:
        model = AttendanceSummary
        fields = [
            'id', 'student', 'student_id', 'term', 'term_name', 'term_academic_year',
            'total_days', 'days_present', 'days_absent', 'days_late', 'days_excused',
            'attendance_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'term_name', 'term_academic_year', 'created_at', 'updated_at']

    def create(self, validated_data):
        student_id = validated_data.pop('student_id', None)
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        student_id = validated_data.pop('student_id', None)
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        return super().update(instance, validated_data)
