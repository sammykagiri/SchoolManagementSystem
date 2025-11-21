from django.db import models
from django.contrib.auth.models import User
from core.models import School, Student, SchoolClass, Term
from django.core.validators import MinValueValidator, MaxValueValidator


class ExamType(models.Model):
    """Model for exam types (e.g., Mid-term, Final, Quiz)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exam_types')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight percentage for this exam type"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.weight}%)"

    class Meta:
        unique_together = ['school', 'name']
        ordering = ['name']


class Exam(models.Model):
    """Model for exams"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exams')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='exams')
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE, related_name='exams')
    name = models.CharField(max_length=200)
    subject = models.ForeignKey('timetable.Subject', on_delete=models.CASCADE, related_name='exams')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='exams', null=True, blank=True)
    exam_date = models.DateField()
    max_marks = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=100,
        validators=[MinValueValidator(0)]
    )
    passing_marks = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=40,
        validators=[MinValueValidator(0)]
    )
    instructions = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.subject} - {self.term}"

    class Meta:
        ordering = ['-exam_date', 'subject']
        indexes = [
            models.Index(fields=['term', 'subject']),
            models.Index(fields=['exam_date']),
        ]


class Gradebook(models.Model):
    """Model for student grades/marks"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='gradebooks')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='gradebooks')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='gradebooks')
    marks_obtained = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    grade = models.CharField(max_length=5, blank=True)  # A, B, C, D, F
    remarks = models.TextField(blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.exam} - {self.marks_obtained}/{self.exam.max_marks}"

    @property
    def percentage(self):
        """Calculate percentage marks"""
        if self.exam.max_marks > 0:
            return (self.marks_obtained / self.exam.max_marks) * 100
        return 0

    @property
    def is_passing(self):
        """Check if student passed"""
        return self.marks_obtained >= self.exam.passing_marks

    def save(self, *args, **kwargs):
        """Auto-calculate grade based on percentage"""
        if not self.grade:
            percentage = self.percentage
            if percentage >= 90:
                self.grade = 'A'
            elif percentage >= 80:
                self.grade = 'B'
            elif percentage >= 70:
                self.grade = 'C'
            elif percentage >= 60:
                self.grade = 'D'
            else:
                self.grade = 'F'
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['school', 'student', 'exam']
        ordering = ['student', 'exam']
        indexes = [
            models.Index(fields=['student', 'exam']),
        ]


class GradebookSummary(models.Model):
    """Model for term-wise grade summaries"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='gradebook_summaries')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='gradebook_summaries')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='gradebook_summaries')
    subject = models.ForeignKey('timetable.Subject', on_delete=models.CASCADE, related_name='gradebook_summaries')
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    marks_obtained = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_grade = models.CharField(max_length=5, blank=True)
    rank = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.term} - {self.final_grade}"

    class Meta:
        unique_together = ['school', 'student', 'term', 'subject']
        ordering = ['student', 'term', 'subject']
