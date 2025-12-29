# CBC Subject Module Alignment Review

## Section 1: Summary of Gaps in Current Module

### Current Subject Model Structure
```python
class Subject(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)  # Generic code, not KNEC-specific
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Constraints:
    # - unique_together: ('school', 'name')
    # - UniqueConstraint: ('school', 'code') when code is not empty
```

### Identified Gaps

1. **CBC Learning Levels**: Missing
   - No field to categorize subjects by CBC level (Early Years, Lower Primary, Upper Primary, Junior Secondary)

2. **KNEC Subject Codes**: Partially addressed
   - Current `code` field is generic and not specifically for KNEC codes
   - Need separate `knec_code` field with proper uniqueness constraints

3. **Compulsory/Optional Classification**: Missing
   - No field to mark subjects as compulsory or optional

4. **Religious Education Tracking**: Missing
   - No mechanism to identify religious education subjects (CRE, IRE, HRE)
   - No model to track student selections per term
   - No validation for mutual exclusivity

5. **Pathway Support**: Missing
   - No pathway model (STEM, Social Sciences, Arts & Sports)
   - No relationship between subjects and pathways

6. **Multi-Grade Support**: Indirect only
   - Subjects are linked to grades via timetables → classes → grades
   - No direct ManyToMany relationship for explicit grade applicability

7. **API Filtering**: Limited
   - Current API only filters by `is_active`
   - Missing filters for level, compulsory status, pathway

---

## Section 2: Recommended Model Changes

### 2.1 Updated Subject Model

```python
# timetable/models.py

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
        'SubjectPathway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
        help_text='Subject pathway (optional, for Junior Secondary)'
    )
    
    # NEW: ManyToMany for grades (replaces indirect relationship)
    applicable_grades = models.ManyToManyField(
        'core.Grade',
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
        from django.core.exceptions import ValidationError
        
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
        
        # KNEC code should be unique (handled by unique=True, but validate format)
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
            models.Index(fields=['learning_level']),
            models.Index(fields=['is_compulsory']),
            models.Index(fields=['is_religious_education', 'religious_type']),
        ]
```

### 2.2 New Supporting Models

```python
# timetable/models.py

class SubjectPathway(models.Model):
    """CBC Subject Pathways for Junior Secondary"""
    
    PATHWAY_CHOICES = [
        ('stem', 'STEM (Science, Technology, Engineering, Mathematics)'),
        ('social_sciences', 'Social Sciences'),
        ('arts_sports', 'Arts & Sports'),
    ]
    
    school = models.ForeignKey(
        'core.School',
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


class StudentSubjectSelection(models.Model):
    """Track student subject selections per term (for religious education mutual exclusivity)"""
    
    school = models.ForeignKey(
        'core.School',
        on_delete=models.CASCADE,
        related_name='student_subject_selections'
    )
    student = models.ForeignKey(
        'core.Student',
        on_delete=models.CASCADE,
        related_name='subject_selections'
    )
    term = models.ForeignKey(
        'core.Term',
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
        from django.core.exceptions import ValidationError
        
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
            models.Index(fields=['student', 'term']),
            models.Index(fields=['subject', 'term']),
        ]
        ordering = ['student', 'term', 'subject']
```

---

## Section 3: Migration Plan

### 3.1 Migration Strategy

**Step 1: Add nullable fields (backward compatible)**
```python
# Migration: 0001_add_cbc_fields_to_subject.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('timetable', '0001_initial'),  # Adjust to your last migration
        ('core', '0001_initial'),  # Adjust to your last migration
    ]

    operations = [
        # Add new nullable fields
        migrations.AddField(
            model_name='subject',
            name='learning_level',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('early_years', 'Early Years (Pre-Primary 1-2)'),
                    ('lower_primary', 'Lower Primary (Grade 1-3)'),
                    ('upper_primary', 'Upper Primary (Grade 4-6)'),
                    ('junior_secondary', 'Junior Secondary (Grade 7-9)'),
                ],
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='knec_code',
            field=models.CharField(
                max_length=20,
                blank=True,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='is_compulsory',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='is_religious_education',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='subject',
            name='religious_type',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('CRE', 'Christian Religious Education'),
                    ('IRE', 'Islamic Religious Education'),
                    ('HRE', 'Hindu Religious Education'),
                ],
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='pathway',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name='subjects',
                to='timetable.subjectpathway',
            ),
        ),
    ]
```

**Step 2: Create SubjectPathway model**
```python
# Migration: 0002_create_subject_pathway.py

class Migration(migrations.Migration):
    dependencies = [
        ('timetable', '0001_add_cbc_fields_to_subject'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubjectPathway',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=50, choices=[...])),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(...)),
            ],
            options={
                'unique_together': {('school', 'name')},
            },
        ),
    ]
```

**Step 3: Add ManyToMany for grades**
```python
# Migration: 0003_add_applicable_grades.py

class Migration(migrations.Migration):
    dependencies = [
        ('timetable', '0002_create_subject_pathway'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='applicable_grades',
            field=models.ManyToManyField(
                blank=True,
                related_name='subjects',
                to='core.grade',
            ),
        ),
    ]
```

**Step 4: Add constraints and indexes**
```python
# Migration: 0004_add_cbc_constraints.py

class Migration(migrations.Migration):
    dependencies = [
        ('timetable', '0003_add_applicable_grades'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='subject',
            constraint=models.UniqueConstraint(
                condition=~models.Q(knec_code__isnull=True) & ~models.Q(knec_code=''),
                fields=['knec_code'],
                name='unique_knec_code_when_provided'
            ),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['learning_level'], name='subject_learning_level_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['is_compulsory'], name='subject_is_compulsory_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['is_religious_education', 'religious_type'], name='subject_religious_idx'),
        ),
    ]
```

**Step 5: Create StudentSubjectSelection model**
```python
# Migration: 0005_create_student_subject_selection.py

class Migration(migrations.Migration):
    dependencies = [
        ('timetable', '0004_add_cbc_constraints'),
        ('core', 'XXXX_previous_migration'),  # Adjust
    ]

    operations = [
        migrations.CreateModel(
            name='StudentSubjectSelection',
            fields=[
                ('id', models.BigAutoField(...)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(...)),
                ('student', models.ForeignKey(...)),
                ('term', models.ForeignKey(...)),
                ('subject', models.ForeignKey(...)),
            ],
            options={
                'unique_together': {('school', 'student', 'term', 'subject')},
                'indexes': [
                    models.Index(fields=['student', 'term'], name='student_term_idx'),
                    models.Index(fields=['subject', 'term'], name='subject_term_idx'),
                ],
            },
        ),
    ]
```

### 3.2 Data Migration Strategy

**For existing subjects:**
1. All existing subjects remain active (`is_active=True`)
2. All existing subjects default to `is_compulsory=True` (can be updated later)
3. `learning_level` can be set manually or inferred from grade associations
4. `code` field remains for backward compatibility
5. `knec_code` can be populated later

**Backward Compatibility:**
- Existing code using `subject.code` continues to work
- Existing timetables continue to function
- No breaking changes to API (new fields are optional)

---

## Section 4: Validation Logic

### 4.1 Model-Level Validation

```python
# timetable/models.py - Subject.clean() method (already shown in Section 2.1)

def clean(self):
    """Validation logic"""
    from django.core.exceptions import ValidationError
    
    # Religious education validation
    if self.is_religious_education and not self.religious_type:
        raise ValidationError({
            'religious_type': 'Religious type is required when subject is marked as religious education.'
        })
    
    if not self.is_religious_education and self.religious_type:
        raise ValidationError({
            'religious_type': 'Religious type should only be set for religious education subjects.'
        })
    
    # KNEC code format validation
    if self.knec_code:
        if not self.knec_code.isdigit():
            raise ValidationError({
                'knec_code': 'KNEC code should be numeric.'
            })
```

### 4.2 Form-Level Validation

```python
# timetable/forms.py (new file or add to existing)

from django import forms
from .models import Subject, StudentSubjectSelection
from core.models import Student, Term

class SubjectForm(forms.ModelForm):
    """Form for creating/editing subjects"""
    
    class Meta:
        model = Subject
        fields = [
            'name', 'code', 'knec_code', 'description', 'learning_level',
            'is_compulsory', 'is_religious_education', 'religious_type',
            'pathway', 'applicable_grades', 'is_active'
        ]
        widgets = {
            'applicable_grades': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        is_religious = cleaned_data.get('is_religious_education')
        religious_type = cleaned_data.get('religious_type')
        
        # Validate religious education fields
        if is_religious and not religious_type:
            raise forms.ValidationError({
                'religious_type': 'Religious type is required for religious education subjects.'
            })
        
        if not is_religious and religious_type:
            raise forms.ValidationError({
                'religious_type': 'Religious type should only be set for religious education subjects.'
            })
        
        return cleaned_data


class StudentSubjectSelectionForm(forms.ModelForm):
    """Form for student subject selection (with mutual exclusivity validation)"""
    
    class Meta:
        model = StudentSubjectSelection
        fields = ['student', 'term', 'subject']
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        term = cleaned_data.get('term')
        subject = cleaned_data.get('subject')
        
        if not all([student, term, subject]):
            return cleaned_data
        
        # Check mutual exclusivity for religious education
        if subject.is_religious_education:
            existing = StudentSubjectSelection.objects.filter(
                school=student.school,
                student=student,
                term=term,
                subject__is_religious_education=True
            ).exclude(
                id=self.instance.id if self.instance else None
            ).exclude(
                subject__religious_type=subject.religious_type
            ).first()
            
            if existing:
                raise forms.ValidationError(
                    f'Student already has {existing.subject.get_religious_type_display()} '
                    f'selected for {term.name}. Only one religious education subject is allowed per term.'
                )
        
        return cleaned_data
```

### 4.3 View-Level Validation

```python
# timetable/views.py - Update subject_add and subject_edit views

@login_required
def subject_add(request):
    """Add a new subject"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.school = school
            try:
                subject.full_clean()  # Run model validation
                subject.save()
                form.save_m2m()  # Save ManyToMany (applicable_grades)
                messages.success(request, f'Subject "{subject.name}" added successfully!')
                return redirect('timetable:subject_list')
            except ValidationError as e:
                for field, errors in e.error_dict.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error.message}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SubjectForm()
    
    # Get pathways and grades for form
    from core.models import Grade
    pathways = SubjectPathway.objects.filter(school=school, is_active=True)
    grades = Grade.objects.filter(school=school)
    
    return render(request, 'timetable/subject_form.html', {
        'form': form,
        'pathways': pathways,
        'grades': grades,
    })
```

### 4.4 API-Level Validation

```python
# timetable/serializers.py - Update SubjectSerializer

class SubjectSerializer(serializers.ModelSerializer):
    applicable_grades = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Grade.objects.all(),
        required=False
    )
    pathway_name = serializers.CharField(
        source='pathway.name',
        read_only=True
    )
    
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'knec_code', 'description',
            'learning_level', 'is_compulsory', 'is_religious_education',
            'religious_type', 'pathway', 'pathway_name',
            'applicable_grades', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
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
```

---

## Section 5: API Updates

### 5.1 Updated SubjectViewSet with Filters

```python
# timetable/views.py

class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Subject.objects.filter(school=school).prefetch_related(
            'applicable_grades', 'pathway'
        )
        
        # Existing filter
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # NEW: Filter by learning level
        learning_level = self.request.query_params.get('learning_level')
        if learning_level:
            queryset = queryset.filter(learning_level=learning_level)
        
        # NEW: Filter by compulsory status
        is_compulsory = self.request.query_params.get('is_compulsory')
        if is_compulsory is not None:
            queryset = queryset.filter(is_compulsory=is_compulsory.lower() == 'true')
        
        # NEW: Filter by pathway
        pathway_id = self.request.query_params.get('pathway_id')
        if pathway_id:
            queryset = queryset.filter(pathway_id=pathway_id)
        
        # NEW: Filter by grade
        grade_id = self.request.query_params.get('grade_id')
        if grade_id:
            queryset = queryset.filter(applicable_grades__id=grade_id).distinct()
        
        # NEW: Filter religious education subjects
        is_religious = self.request.query_params.get('is_religious_education')
        if is_religious is not None:
            queryset = queryset.filter(is_religious_education=is_religious.lower() == 'true')
        
        # NEW: Filter by religious type
        religious_type = self.request.query_params.get('religious_type')
        if religious_type:
            queryset = queryset.filter(religious_type=religious_type)
        
        # NEW: Search by KNEC code
        knec_code = self.request.query_params.get('knec_code')
        if knec_code:
            queryset = queryset.filter(knec_code=knec_code)
        
        return queryset.order_by('name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)
```

### 5.2 New StudentSubjectSelectionViewSet

```python
# timetable/views.py

class StudentSubjectSelectionViewSet(viewsets.ModelViewSet):
    """API for managing student subject selections"""
    serializer_class = StudentSubjectSelectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = StudentSubjectSelection.objects.filter(
            school=school
        ).select_related('student', 'term', 'subject')
        
        # Filter by student
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        # Filter by term
        term_id = self.request.query_params.get('term_id')
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        
        # Filter by subject
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        
        return queryset.order_by('student', 'term', 'subject')
    
    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)
```

### 5.3 Updated Serializers

```python
# timetable/serializers.py

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
        """Validation logic (as shown in Section 4.4)"""
        # ... validation code ...
        return data


class SubjectPathwaySerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubjectPathway
        fields = ['id', 'name', 'description', 'is_active', 'subjects_count']
        read_only_fields = ['id', 'subjects_count']
    
    def get_subjects_count(self, obj):
        return obj.subjects.filter(is_active=True).count()


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
```

### 5.4 URL Patterns

```python
# timetable/urls.py - Add new routes

urlpatterns = [
    # ... existing patterns ...
    
    # NEW: Subject pathways
    path('api/pathways/', views.SubjectPathwayViewSet.as_view({'get': 'list', 'post': 'create'}), name='pathway_list'),
    path('api/pathways/<int:pk>/', views.SubjectPathwayViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='pathway_detail'),
    
    # NEW: Student subject selections
    path('api/student-selections/', views.StudentSubjectSelectionViewSet.as_view({'get': 'list', 'post': 'create'}), name='student_selection_list'),
    path('api/student-selections/<int:pk>/', views.StudentSubjectSelectionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='student_selection_detail'),
]
```

---

## Section 6: Backward Compatibility Risks and Mitigation

### 6.1 Identified Risks

1. **Code Field Usage**
   - **Risk**: Existing code may use `subject.code` assuming it's always present
   - **Mitigation**: Keep `code` field, add `knec_code` as separate field
   - **Impact**: Low - `code` remains optional as before

2. **Subject-Grade Relationship**
   - **Risk**: Current system infers grades from timetables → classes → grades
   - **Mitigation**: Add `applicable_grades` ManyToMany but don't remove existing logic
   - **Impact**: Low - Can populate `applicable_grades` from existing timetables via data migration

3. **API Response Changes**
   - **Risk**: Adding new fields may break clients expecting specific structure
   - **Mitigation**: All new fields are optional/nullable, existing fields unchanged
   - **Impact**: Low - Backward compatible

4. **Religious Education Validation**
   - **Risk**: Existing students may have multiple religious subjects in timetables
   - **Mitigation**: Validation only applies to new `StudentSubjectSelection` model
   - **Impact**: Low - Existing timetables unaffected, new selections validated

5. **Form Changes**
   - **Risk**: Subject forms may need UI updates
   - **Mitigation**: New fields can be added gradually, existing fields remain
   - **Impact**: Medium - Requires template updates

### 6.2 Migration Safety Checklist

- [x] All new fields are nullable/optional
- [x] No existing fields removed
- [x] Existing constraints preserved
- [x] New constraints are additive only
- [x] Default values provided for boolean fields
- [x] Data migration script provided for `applicable_grades`
- [x] Validation logic is non-breaking (only validates new data)

### 6.3 Recommended Rollout Strategy

1. **Phase 1**: Deploy model changes (migrations 1-4)
   - Add fields, create pathways
   - No breaking changes
   - Existing functionality continues

2. **Phase 2**: Populate data
   - Run data migration to populate `applicable_grades` from existing timetables
   - Manually set `learning_level` for existing subjects
   - Optionally populate `knec_code` for known subjects

3. **Phase 3**: Deploy StudentSubjectSelection (migration 5)
   - Create model for tracking selections
   - Start using for new religious education enrollments

4. **Phase 4**: Update UI/Forms
   - Add new fields to subject forms
   - Add subject selection interface for students
   - Update filters and search

5. **Phase 5**: Enable validations
   - Activate religious education mutual exclusivity
   - Add validation warnings in UI

---

## Section 7: Additional Recommendations

### 7.1 Data Migration Script

```python
# timetable/management/commands/populate_subject_grades.py

from django.core.management.base import BaseCommand
from timetable.models import Subject
from core.models import School

class Command(BaseCommand):
    help = 'Populate applicable_grades for existing subjects based on timetables'
    
    def handle(self, *args, **options):
        for school in School.objects.all():
            subjects = Subject.objects.filter(school=school)
            for subject in subjects:
                # Get grades from timetables
                grades = set()
                for timetable in subject.timetables.filter(is_active=True):
                    if timetable.school_class and timetable.school_class.grade:
                        grades.add(timetable.school_class.grade)
                
                if grades:
                    subject.applicable_grades.set(grades)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated {subject.name}: {len(grades)} grade(s)'
                        )
                    )
```

### 7.2 Admin Updates

```python
# timetable/admin.py

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'knec_code', 'learning_level', 
        'is_compulsory', 'is_religious_education', 'is_active', 'school'
    ]
    list_filter = [
        'is_active', 'school', 'learning_level', 
        'is_compulsory', 'is_religious_education', 'pathway'
    ]
    search_fields = ['name', 'code', 'knec_code']
    filter_horizontal = ['applicable_grades']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('school', 'name', 'code', 'knec_code', 'description', 'is_active')
        }),
        ('CBC Information', {
            'fields': ('learning_level', 'is_compulsory', 'applicable_grades', 'pathway')
        }),
        ('Religious Education', {
            'fields': ('is_religious_education', 'religious_type'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SubjectPathway)
class SubjectPathwayAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'is_active']
    list_filter = ['is_active', 'school', 'name']
    search_fields = ['name', 'description']


@admin.register(StudentSubjectSelection)
class StudentSubjectSelectionAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'subject', 'created_at']
    list_filter = ['term', 'subject__is_religious_education', 'school']
    search_fields = ['student__first_name', 'student__last_name', 'subject__name']
    readonly_fields = ['created_at', 'updated_at']
```

---

## Summary

This alignment maintains backward compatibility while adding CBC-specific features. All changes are additive, with nullable fields and optional relationships. The system can be migrated incrementally without disrupting existing functionality.


