"""
CBC-Aligned Subject Models
This file shows the updated models for CBC alignment.
To apply: Copy the changes to timetable/models.py
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from core.models import School, SchoolClass, Grade, Term, Student


class SubjectPathway(models.Model):
    """CBC Subject Pathways for Junior Secondary"""
    
    PATHWAY_CHOICES = [
        ('stem', 'STEM (Science, Technology, Engineering, Mathematics)'),
        ('social_sciences', 'Social Sciences'),
        ('arts_sports', 'Arts & Sports'),
    ]
    
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='subject_pathways'
    )
    name = models.CharField(
        max_length=50,
        choices=PATHWAY_CHOICES
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        unique_together = ['school', 'name']
        ordering = ['name']


class Subject(models.Model):
    """Model for school subjects - CBC aligned"""
    
    # CBC Learning Levels
    LEARNING_LEVEL_CHOICES = [
        ('early_years', 'Early Years (Pre-Primary 1-2)'),
        ('lower_primary', 'Lower Primary (Grade 1-3)'),
        ('upper_primary', 'Upper Primary (Grade 4-6)'),
        ('junior_secondary', 'Junior Secondary (Grade 7-9)'),
    ]
    
    # Religious Education Types
    RELIGIOUS_TYPE_CHOICES = [
        ('CRE', 'Christian Religious Education'),
        ('IRE', 'Islamic Religious Education'),
        ('HRE', 'Hindu Religious Education'),
    ]
    
    # Existing fields (preserved)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=20, 
        blank=True,
        help_text='Internal subject code (e.g., MATH, ENG)'
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # NEW: CBC-specific fields
    learning_level = models.CharField(
        max_length=20,
        choices=LEARNING_LEVEL_CHOICES,
        blank=True,
        null=True,
        help_text='CBC learning level this subject applies to'
    )
    
    knec_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text='Official KNEC subject code (e.g., 101 for Mathematics)'
    )
    
    is_compulsory = models.BooleanField(
        default=True,
        help_text='Whether this subject is compulsory or optional'
    )
    
    is_religious_education = models.BooleanField(
        default=False,
        help_text='Whether this is a religious education subject'
    )
    
    religious_type = models.CharField(
        max_length=10,
        choices=RELIGIOUS_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text='Type of religious education (only if is_religious_education=True)'
    )
    
    pathway = models.ForeignKey(
        SubjectPathway,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
        help_text='Subject pathway (optional, for Junior Secondary)'
    )
    
    # NEW: ManyToMany for grades (replaces indirect relationship)
    applicable_grades = models.ManyToManyField(
        Grade,
        related_name='subjects',
        blank=True,
        help_text='Grades this subject applies to'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name
    
    def clean(self):
        """Validation logic"""
        # If religious education, must have religious_type
        if self.is_religious_education and not self.religious_type:
            raise ValidationError({
                'religious_type': 'Religious type is required when subject is marked as religious education.'
            })
        
        # If not religious education, religious_type should be empty
        if not self.is_religious_education and self.religious_type:
            raise ValidationError({
                'religious_type': 'Religious type should only be set for religious education subjects.'
            })
        
        # KNEC code should be numeric
        if self.knec_code:
            if not self.knec_code.isdigit():
                raise ValidationError({
                    'knec_code': 'KNEC code should be numeric.'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = [
            ('school', 'name'),
        ]
        constraints = [
            # Existing: unique code per school when provided
            models.UniqueConstraint(
                fields=['school', 'code'],
                condition=~models.Q(code=''),
                name='unique_school_code_when_provided'
            ),
            # NEW: unique KNEC code (globally, as KNEC codes are standardized)
            models.UniqueConstraint(
                fields=['knec_code'],
                condition=~models.Q(knec_code__isnull=True) & ~models.Q(knec_code=''),
                name='unique_knec_code_when_provided'
            ),
        ]
        ordering = ['name']
        indexes = [
            models.Index(fields=['learning_level'], name='subject_learning_level_idx'),
            models.Index(fields=['is_compulsory'], name='subject_is_compulsory_idx'),
            models.Index(fields=['is_religious_education', 'religious_type'], name='subject_religious_idx'),
        ]


class StudentSubjectSelection(models.Model):
    """Track student subject selections per term (for religious education mutual exclusivity)"""
    
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='student_subject_selections'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='subject_selections'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='student_subject_selections'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='student_selections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        """Validate mutual exclusivity for religious education"""
        # Only validate if subject is religious education
        if not self.subject.is_religious_education:
            return
        
        # Check if student already has a different religious education subject for this term
        existing_selection = StudentSubjectSelection.objects.filter(
            school=self.school,
            student=self.student,
            term=self.term,
            subject__is_religious_education=True
        ).exclude(id=self.id if self.id else None).first()
        
        if existing_selection:
            if existing_selection.subject.religious_type != self.subject.religious_type:
                raise ValidationError(
                    f'Student already has {existing_selection.subject.get_religious_type_display()} '
                    f'selected for this term. Only one religious education subject is allowed per term.'
                )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['school', 'student', 'term', 'subject']
        indexes = [
            models.Index(fields=['student', 'term'], name='student_term_idx'),
            models.Index(fields=['subject', 'term'], name='subject_term_idx'),
        ]
        ordering = ['student', 'term', 'subject']
    
    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} - {self.term.name}"


# Keep existing Teacher, TimeSlot, and Timetable models unchanged
