"""
Student Promotion Service

Handles the business logic for promoting students from one academic year to another.
Includes validation, preview, execution, and section rebalancing.
"""

from django.db import transaction
from django.db.models import Q, Count, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromotionPreview:
    """Data class for promotion preview information"""
    student_id: int
    student_name: str
    student_id_code: str
    current_grade: str
    current_class: Optional[str]
    current_section: Optional[str]
    current_roll_number: Optional[int]
    target_grade: str
    target_class: Optional[str]
    target_section: Optional[str]
    target_roll_number: Optional[int]
    action: str  # 'promote', 'retain', 'graduate', 'leave'
    notes: str
    warnings: List[str]


@dataclass
class PromotionResult:
    """Result of a promotion operation"""
    success: bool
    promoted_count: int
    retained_count: int
    graduated_count: int
    left_count: int
    errors: List[str]
    warnings: List[str]
    log_id: Optional[int]


class PromotionService:
    """Service for handling student promotions between academic years"""

    def __init__(self, school, user):
        """
        Initialize promotion service
        
        Args:
            school: School instance
            user: User performing the promotion (for audit trail)
        """
        self.school = school
        self.user = user
        from core.models import AcademicYear, Grade, SchoolClass, Section
        
        self.AcademicYear = AcademicYear
        self.Grade = Grade
        self.SchoolClass = SchoolClass
        self.Section = Section

    def validate_prerequisites(self, from_year_id: int, to_year_id: int) -> List[str]:
        """
        Validate that promotion can proceed
        
        Args:
            from_year_id: Source academic year ID
            to_year_id: Target academic year ID
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        try:
            from_year = self.AcademicYear.objects.get(pk=from_year_id, school=self.school)
            to_year = self.AcademicYear.objects.get(pk=to_year_id, school=self.school)
        except self.AcademicYear.DoesNotExist:
            errors.append("One or both academic years not found.")
            return errors
        
        # Check to_year is after from_year
        if to_year.start_date <= from_year.end_date:
            errors.append("Target academic year must start after source academic year ends.")
        
        # Check for existing enrollments in target year
        from core.models import StudentClassEnrollment
        existing_count = StudentClassEnrollment.objects.filter(
            academic_year=to_year,
            status='active'
        ).count()
        
        if existing_count > 0:
            errors.append(f"Target academic year already has {existing_count} active enrollments. Please review before proceeding.")
        
        # Check that source year has enrollments
        source_count = StudentClassEnrollment.objects.filter(
            academic_year=from_year,
            status__in=['active', 'promoted']
        ).count()
        
        if source_count == 0:
            errors.append("Source academic year has no enrollments to promote.")
        
        return errors

    def get_eligible_students(self, academic_year_id: int, exclude_statuses: Optional[List[str]] = None) -> List:
        """
        Get students eligible for promotion from an academic year
        
        Args:
            academic_year_id: Academic year ID
            exclude_statuses: List of statuses to exclude (default: ['left', 'dropped', 'graduated'])
            
        Returns:
            QuerySet of StudentClassEnrollment objects
        """
        from core.models import StudentClassEnrollment
        
        if exclude_statuses is None:
            exclude_statuses = ['left', 'dropped', 'graduated']
        
        academic_year = self.AcademicYear.objects.get(pk=academic_year_id, school=self.school)
        
        enrollments = StudentClassEnrollment.objects.filter(
            academic_year=academic_year,
            student__school=self.school
        ).exclude(
            status__in=exclude_statuses
        ).select_related(
            'student', 'grade', 'school_class', 'section'
        ).order_by('grade__name', 'school_class__name', 'roll_number', 'student__first_name')
        
        return enrollments

    def get_next_grade(self, current_grade) -> Optional:
        """
        Get the next grade level for promotion
        
        Args:
            current_grade: Grade instance
            
        Returns:
            Next Grade instance or None if at highest grade
        """
        # Get all grades for the school, ordered by name
        grades = list(self.Grade.objects.filter(school=self.school).order_by('name'))
        
        try:
            current_index = grades.index(current_grade)
            if current_index < len(grades) - 1:
                return grades[current_index + 1]
            return None  # Already at highest grade
        except ValueError:
            return None

    def get_highest_grade(self):
        """Get the highest grade level in the school"""
        return self.Grade.objects.filter(school=self.school).order_by('name').last()

    def calculate_promotion_targets(
        self,
        enrollments: List,
        target_year_id: int,
        retain_student_ids: Optional[Set[int]] = None,
        graduate_student_ids: Optional[Set[int]] = None,
        leave_student_ids: Optional[Set[int]] = None
    ) -> List[PromotionPreview]:
        """
        Calculate promotion targets for students
        
        Args:
            enrollments: List of StudentClassEnrollment objects
            target_year_id: Target academic year ID
            retain_student_ids: Set of student IDs to retain
            graduate_student_ids: Set of student IDs to graduate
            leave_student_ids: Set of student IDs who left
            
        Returns:
            List of PromotionPreview objects
        """
        if retain_student_ids is None:
            retain_student_ids = set()
        if graduate_student_ids is None:
            graduate_student_ids = set()
        if leave_student_ids is None:
            leave_student_ids = set()
        
        target_year = self.AcademicYear.objects.get(pk=target_year_id, school=self.school)
        highest_grade = self.get_highest_grade()
        previews = []
        
        for enrollment in enrollments:
            student = enrollment.student
            warnings = []
            
            # Determine action
            if student.id in leave_student_ids:
                action = 'leave'
                target_grade = enrollment.grade.name
                target_class = enrollment.school_class.name if enrollment.school_class else None
                target_section = enrollment.section.name if enrollment.section else None
                target_roll_number = None
                notes = "Student left school"
            elif student.id in graduate_student_ids or (highest_grade and enrollment.grade == highest_grade):
                action = 'graduate'
                target_grade = enrollment.grade.name
                target_class = enrollment.school_class.name if enrollment.school_class else None
                target_section = None
                target_roll_number = None
                notes = "Student graduated"
            elif student.id in retain_student_ids:
                action = 'retain'
                target_grade = enrollment.grade.name
                target_class = enrollment.school_class.name if enrollment.school_class else None
                target_section = enrollment.section.name if enrollment.section else None
                target_roll_number = enrollment.roll_number
                notes = "Student retained in same grade"
            else:
                # Promote to next grade
                action = 'promote'
                next_grade = self.get_next_grade(enrollment.grade)
                
                if next_grade is None:
                    # At highest grade, graduate instead
                    action = 'graduate'
                    target_grade = enrollment.grade.name
                    target_class = enrollment.school_class.name if enrollment.school_class else None
                    target_section = None
                    target_roll_number = None
                    notes = "At highest grade - will graduate"
                    warnings.append("Student is at highest grade and will be graduated")
                else:
                    target_grade = next_grade.name
                    # Get first active class for next grade (can be adjusted later)
                    target_class_obj = self.SchoolClass.objects.filter(
                        grade=next_grade,
                        is_active=True
                    ).first()
                    target_class = target_class_obj.name if target_class_obj else None
                    target_section = None
                    target_roll_number = None
                    notes = f"Promoted from {enrollment.grade.name} to {next_grade.name}"
                    
                    if not target_class_obj:
                        warnings.append(f"No active class found for grade {next_grade.name}")
            
            preview = PromotionPreview(
                student_id=student.id,
                student_name=student.full_name,
                student_id_code=student.student_id,
                current_grade=enrollment.grade.name,
                current_class=enrollment.school_class.name if enrollment.school_class else None,
                current_section=enrollment.section.name if enrollment.section else None,
                current_roll_number=enrollment.roll_number,
                target_grade=target_grade,
                target_class=target_class,
                target_section=target_section,
                target_roll_number=target_roll_number,
                action=action,
                notes=notes,
                warnings=warnings
            )
            previews.append(preview)
        
        return previews

    def rebalance_sections(
        self,
        grade,
        school_class,
        target_year,
        student_count: int
    ) -> Dict[str, any]:
        """
        Rebalance students across sections for a class
        
        Args:
            grade: Grade instance
            school_class: SchoolClass instance
            target_year: AcademicYear instance
            student_count: Number of students to distribute
            
        Returns:
            Dict with section assignments
        """
        sections = self.Section.objects.filter(
            school_class=school_class,
            is_active=True
        ).order_by('name')
        
        if not sections.exists():
            return {}
        
        # Simple round-robin distribution
        section_list = list(sections)
        assignments = {}
        
        for i in range(student_count):
            section = section_list[i % len(section_list)]
            if section.name not in assignments:
                assignments[section.name] = []
            assignments[section.name].append(i + 1)  # Roll numbers start at 1
        
        return assignments

    @transaction.atomic
    def execute_promotion(
        self,
        from_year_id: int,
        to_year_id: int,
        previews: List[PromotionPreview],
        promotion_type: str = 'automatic'
    ) -> PromotionResult:
        """
        Execute the promotion
        
        Args:
            from_year_id: Source academic year ID
            to_year_id: Target academic year ID
            previews: List of PromotionPreview objects
            promotion_type: Type of promotion ('automatic', 'manual', 'bulk')
            
        Returns:
            PromotionResult object
        """
        from core.models import StudentClassEnrollment, Student, PromotionLog
        
        errors = []
        warnings = []
        promoted_count = 0
        retained_count = 0
        graduated_count = 0
        left_count = 0
        
        try:
            from_year = self.AcademicYear.objects.select_for_update().get(
                pk=from_year_id, school=self.school
            )
            to_year = self.AcademicYear.objects.select_for_update().get(
                pk=to_year_id, school=self.school
            )
        except self.AcademicYear.DoesNotExist as e:
            return PromotionResult(
                success=False,
                promoted_count=0,
                retained_count=0,
                graduated_count=0,
                left_count=0,
                errors=[f"Academic year not found: {str(e)}"],
                warnings=[],
                log_id=None
            )
        
        # Process each student
        for preview in previews:
            try:
                student = Student.objects.get(pk=preview.student_id, school=self.school)
                
                # Get current enrollment
                current_enrollment = StudentClassEnrollment.objects.filter(
                    student=student,
                    academic_year=from_year
                ).first()
                
                if not current_enrollment:
                    errors.append(f"Student {preview.student_name} has no enrollment in source year")
                    continue
                
                # Handle based on action
                if preview.action == 'leave':
                    # Mark as left
                    current_enrollment.status = 'left'
                    current_enrollment.save()
                    left_count += 1
                    
                elif preview.action == 'graduate':
                    # Mark as graduated
                    current_enrollment.status = 'graduated'
                    current_enrollment.save()
                    
                    # Create final enrollment record
                    StudentClassEnrollment.objects.create(
                        student=student,
                        academic_year=to_year,
                        grade=current_enrollment.grade,
                        school_class=current_enrollment.school_class,
                        section=None,
                        roll_number=None,
                        status='graduated',
                        notes="Graduated from school"
                    )
                    
                    # Mark student as inactive
                    student.is_active = False
                    student.save()
                    graduated_count += 1
                    
                elif preview.action == 'retain':
                    # Retain in same grade
                    current_enrollment.status = 'retained'
                    current_enrollment.save()
                    
                    # Create new enrollment in same grade
                    target_grade = current_enrollment.grade
                    target_class = current_enrollment.school_class
                    target_section = current_enrollment.section
                    
                    StudentClassEnrollment.objects.create(
                        student=student,
                        academic_year=to_year,
                        grade=target_grade,
                        school_class=target_class,
                        section=target_section,
                        roll_number=preview.target_roll_number,
                        status='active',
                        notes="Retained in same grade"
                    )
                    retained_count += 1
                    
                elif preview.action == 'promote':
                    # Promote to next grade
                    current_enrollment.status = 'promoted'
                    current_enrollment.save()
                    
                    # Get target grade
                    target_grade = self.Grade.objects.get(
                        school=self.school,
                        name=preview.target_grade
                    )
                    
                    # Get target class
                    target_class = None
                    if preview.target_class:
                        target_class = self.SchoolClass.objects.get(
                            school=self.school,
                            grade=target_grade,
                            name=preview.target_class
                        )
                    
                    # Get or assign section
                    target_section = None
                    if target_class and preview.target_section:
                        target_section = self.Section.objects.filter(
                            school_class=target_class,
                            name=preview.target_section
                        ).first()
                    
                    # Assign roll number if not set
                    roll_number = preview.target_roll_number
                    if roll_number is None and target_class:
                        # Get next available roll number
                        max_roll = StudentClassEnrollment.objects.filter(
                            academic_year=to_year,
                            school_class=target_class,
                            section=target_section
                        ).aggregate(Max('roll_number'))['roll_number__max']
                        roll_number = (max_roll or 0) + 1
                    
                    # Create new enrollment
                    StudentClassEnrollment.objects.create(
                        student=student,
                        academic_year=to_year,
                        grade=target_grade,
                        school_class=target_class,
                        section=target_section,
                        roll_number=roll_number,
                        status='active',
                        notes=f"Promoted from {current_enrollment.grade.name}"
                    )
                    
                    # Update student's grade and class
                    student.grade = target_grade
                    student.school_class = target_class
                    student.save()
                    promoted_count += 1
                    
            except Exception as e:
                error_msg = f"Error processing {preview.student_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        # Create audit log
        try:
            promotion_log = PromotionLog.objects.create(
                school=self.school,
                from_academic_year=from_year,
                to_academic_year=to_year,
                promoted_by=self.user,
                promotion_type=promotion_type,
                total_students=len(previews),
                promoted_count=promoted_count,
                retained_count=retained_count,
                graduated_count=graduated_count,
                left_count=left_count,
                notes=f"Promotion completed via {promotion_type} mode"
            )
            log_id = promotion_log.id
        except Exception as e:
            warnings.append(f"Could not create promotion log: {str(e)}")
            log_id = None
        
        success = len(errors) == 0
        
        return PromotionResult(
            success=success,
            promoted_count=promoted_count,
            retained_count=retained_count,
            graduated_count=graduated_count,
            left_count=left_count,
            errors=errors,
            warnings=warnings,
            log_id=log_id
        )

