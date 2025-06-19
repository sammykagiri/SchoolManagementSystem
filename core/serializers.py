from rest_framework import serializers
from .models import (
    School, Grade, Term, FeeCategory, TransportRoute, Student, FeeStructure, StudentFee, SchoolClass
)

class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['id', 'name', 'address', 'email', 'phone']

class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'name', 'description']

class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = [
            'id', 'name', 'term_number', 'academic_year', 'start_date', 'end_date', 'is_active'
        ]

class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'category_type', 'description', 'is_optional']

class TransportRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportRoute
        fields = ['id', 'name', 'description', 'base_fare', 'is_active']

class StudentSerializer(serializers.ModelSerializer):
    grade = GradeSerializer(read_only=True)
    grade_id = serializers.PrimaryKeyRelatedField(
        queryset=Grade.objects.all(), source='grade', write_only=True
    )
    transport_route = TransportRouteSerializer(read_only=True)
    transport_route_id = serializers.PrimaryKeyRelatedField(
        queryset=TransportRoute.objects.all(), source='transport_route', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'first_name', 'last_name', 'gender', 'date_of_birth',
            'grade', 'grade_id', 'admission_date', 'parent_name', 'parent_phone', 'parent_email',
            'address', 'transport_route', 'transport_route_id', 'uses_transport', 'pays_meals', 'pays_activities', 'is_active'
        ]
        read_only_fields = ['id', 'student_id', 'grade', 'transport_route']

class FeeStructureSerializer(serializers.ModelSerializer):
    grade = GradeSerializer(read_only=True)
    grade_id = serializers.PrimaryKeyRelatedField(queryset=Grade.objects.all(), source='grade', write_only=True)
    term = TermSerializer(read_only=True)
    term_id = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all(), source='term', write_only=True)
    fee_category = FeeCategorySerializer(read_only=True)
    fee_category_id = serializers.PrimaryKeyRelatedField(queryset=FeeCategory.objects.all(), source='fee_category', write_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            'id', 'grade', 'grade_id', 'term', 'term_id', 'fee_category', 'fee_category_id', 'amount', 'is_active'
        ]
        read_only_fields = ['id', 'grade', 'term', 'fee_category']

class StudentFeeSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), source='student', write_only=True)
    term = TermSerializer(read_only=True)
    term_id = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all(), source='term', write_only=True)
    fee_category = FeeCategorySerializer(read_only=True)
    fee_category_id = serializers.PrimaryKeyRelatedField(queryset=FeeCategory.objects.all(), source='fee_category', write_only=True)

    class Meta:
        model = StudentFee
        fields = [
            'id', 'student', 'student_id', 'term', 'term_id', 'fee_category', 'fee_category_id',
            'amount_charged', 'amount_paid', 'due_date', 'is_paid', 'balance', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student', 'term', 'fee_category', 'balance', 'is_overdue', 'created_at', 'updated_at']

class SchoolClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = '__all__'
