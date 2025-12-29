from rest_framework import serializers
from .models import Subject, Teacher, TimeSlot, Timetable, SubjectPathway, StudentSubjectSelection
from core.serializers import SchoolClassSerializer
from core.models import Grade


class SubjectPathwaySerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubjectPathway
        fields = ['id', 'name', 'description', 'is_active', 'subjects_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'subjects_count', 'created_at', 'updated_at']
    
    def get_subjects_count(self, obj):
        return obj.subjects.filter(is_active=True).count()


class SubjectSerializer(serializers.ModelSerializer):
    applicable_grades = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Grade.objects.all(),
        required=False,
        allow_null=True
    )
    applicable_grades_names = serializers.SerializerMethodField()
    pathway_name = serializers.CharField(
        source='pathway.name',
        read_only=True
    )
    learning_level_display = serializers.CharField(
        source='get_learning_level_display',
        read_only=True
    )
    religious_type_display = serializers.CharField(
        source='get_religious_type_display',
        read_only=True
    )
    
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'knec_code', 'description',
            'learning_level', 'learning_level_display',
            'is_compulsory', 'is_religious_education',
            'religious_type', 'religious_type_display',
            'pathway', 'pathway_name',
            'applicable_grades', 'applicable_grades_names',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_applicable_grades_names(self, obj):
        return [grade.name for grade in obj.applicable_grades.all()]
    
    def validate(self, data):
        """Custom validation"""
        is_religious = data.get('is_religious_education', False)
        religious_type = data.get('religious_type')
        
        if is_religious and not religious_type:
            raise serializers.ValidationError({
                'religious_type': 'Religious type is required for religious education subjects.'
            })
        
        if not is_religious and religious_type:
            raise serializers.ValidationError({
                'religious_type': 'Religious type should only be set for religious education subjects.'
            })
        
        return data


class TeacherSerializer(serializers.ModelSerializer):
    subject_names = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'employee_id', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'subjects', 'subject_names', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_subject_names(self, obj):
        return [subject.name for subject in obj.subjects.all()]


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = [
            'id', 'day', 'start_time', 'end_time', 'period_number',
            'is_break', 'break_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TimetableSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    school_class_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    time_slot = TimeSlotSerializer(read_only=True)
    time_slot_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Timetable
        fields = [
            'id', 'school_class', 'school_class_id', 'subject', 'subject_id',
            'teacher', 'teacher_id', 'time_slot', 'time_slot_id', 'room',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school_class', 'subject', 'teacher', 'time_slot', 'created_at', 'updated_at']

    def create(self, validated_data):
        school_class_id = validated_data.pop('school_class_id', None)
        subject_id = validated_data.pop('subject_id', None)
        teacher_id = validated_data.pop('teacher_id', None)
        time_slot_id = validated_data.pop('time_slot_id', None)
        
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        if subject_id:
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        if teacher_id:
            validated_data['teacher'] = Teacher.objects.get(id=teacher_id)
        if time_slot_id:
            validated_data['time_slot'] = TimeSlot.objects.get(id=time_slot_id)
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        school_class_id = validated_data.pop('school_class_id', None)
        subject_id = validated_data.pop('subject_id', None)
        teacher_id = validated_data.pop('teacher_id', None)
        time_slot_id = validated_data.pop('time_slot_id', None)
        
        if school_class_id:
            from core.models import SchoolClass
            validated_data['school_class'] = SchoolClass.objects.get(id=school_class_id)
        if subject_id:
            validated_data['subject'] = Subject.objects.get(id=subject_id)
        if teacher_id:
            validated_data['teacher'] = Teacher.objects.get(id=teacher_id)
        if time_slot_id:
            validated_data['time_slot'] = TimeSlot.objects.get(id=time_slot_id)
        
        return super().update(instance, validated_data)


class StudentSubjectSelectionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source='student.full_name',
        read_only=True
    )
    subject_name = serializers.CharField(
        source='subject.name',
        read_only=True
    )
    term_name = serializers.CharField(
        source='term.name',
        read_only=True
    )
    
    class Meta:
        model = StudentSubjectSelection
        fields = [
            'id', 'student', 'student_name', 'term', 'term_name',
            'subject', 'subject_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
