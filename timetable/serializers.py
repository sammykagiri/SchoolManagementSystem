from rest_framework import serializers
from .models import Subject, Teacher, TimeSlot, Timetable
from core.serializers import SchoolClassSerializer


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


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
