from rest_framework import serializers
from .models import ExamType, Exam, Gradebook, GradebookSummary
from core.serializers import StudentSerializer, SchoolClassSerializer
from timetable.serializers import SubjectSerializer


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = ['id', 'name', 'code', 'weight', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExamSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    exam_type = ExamTypeSerializer(read_only=True)
    exam_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    term_academic_year = serializers.CharField(source='term.academic_year', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'term', 'term_name', 'term_academic_year', 'exam_type', 'exam_type_id',
            'name', 'subject', 'subject_id', 'school_class', 'school_class_id',
            'exam_date', 'max_marks', 'passing_marks', 'instructions',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'term_name', 'term_academic_year', 'subject', 'exam_type', 'school_class', 'created_at', 'updated_at']

    def create(self, validated_data):
        subject_id = validated_data.pop('subject_id', None)
        exam_type_id = validated_data.pop('exam_type_id', None)
        school_class_id = validated_data.pop('school_class_id', None)
        
        if subject_id:
            from timetable.models import Subject
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        if exam_type_id:
            validated_data['exam_type'] = ExamType.objects.get(id=exam_type_id)
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        subject_id = validated_data.pop('subject_id', None)
        exam_type_id = validated_data.pop('exam_type_id', None)
        school_class_id = validated_data.pop('school_class_id', None)
        
        if subject_id:
            from timetable.models import Subject
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        if exam_type_id:
            validated_data['exam_type'] = ExamType.objects.get(id=exam_type_id)
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        
        return super().update(instance, validated_data)


class GradebookSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    exam = ExamSerializer(read_only=True)
    exam_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    is_passing = serializers.BooleanField(read_only=True)
    entered_by_username = serializers.CharField(source='entered_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Gradebook
        fields = [
            'id', 'student', 'student_id', 'exam', 'exam_id',
            'marks_obtained', 'grade', 'percentage', 'is_passing',
            'remarks', 'entered_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'exam', 'percentage', 'is_passing', 'grade', 'created_at', 'updated_at']

    def create(self, validated_data):
        student_id = validated_data.pop('student_id', None)
        exam_id = validated_data.pop('exam_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if exam_id:
            validated_data['exam'] = Exam.objects.get(id=exam_id)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        student_id = validated_data.pop('student_id', None)
        exam_id = validated_data.pop('exam_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if exam_id:
            validated_data['exam'] = Exam.objects.get(id=exam_id)
        
        return super().update(instance, validated_data)


class GradebookSummarySerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    term_academic_year = serializers.CharField(source='term.academic_year', read_only=True)

    class Meta:
        model = GradebookSummary
        fields = [
            'id', 'student', 'student_id', 'term', 'term_name', 'term_academic_year',
            'subject', 'subject_id', 'total_marks', 'marks_obtained',
            'average_percentage', 'final_grade', 'rank', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'term_name', 'term_academic_year', 'subject', 'created_at', 'updated_at']

    def create(self, validated_data):
        student_id = validated_data.pop('student_id', None)
        subject_id = validated_data.pop('subject_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if subject_id:
            from timetable.models import Subject
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        student_id = validated_data.pop('student_id', None)
        subject_id = validated_data.pop('subject_id', None)
        
        if student_id:
            from core.models import Student
            validated_data['student'] = Student.objects.get(id=student_id)
        if subject_id:
            from timetable.models import Subject
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        
        return super().update(instance, validated_data)
