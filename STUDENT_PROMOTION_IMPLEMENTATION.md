# Student Promotion / Academic Year Rollover - Implementation Plan

## 1. Database Schema Changes

### New Models Required

#### 1.1 AcademicYear Model
```python
class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='academic_years')
    name = models.CharField(max_length=50)  # e.g., "2023-2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)  # Only one can be current
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['school', 'name']
        ordering = ['-start_date']
```

#### 1.2 StudentClassEnrollment Model (Pivot Table)
```python
class StudentClassEnrollment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retained', 'Retained'),
        ('promoted', 'Promoted'),
        ('graduated', 'Graduated'),
        ('left', 'Left School'),
        ('dropped', 'Dropped Out'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='enrollments')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    section = models.ForeignKey('Section', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    roll_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    enrollment_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'academic_year']
        ordering = ['roll_number', 'student__first_name']
```

#### 1.3 Section Model (if not exists)
```python
class Section(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sections')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=50)  # e.g., "A", "B", "Morning", "Afternoon"
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['school_class', 'name']
```

#### 1.4 PromotionLog Model (Audit Trail)
```python
class PromotionLog(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='promotion_logs')
    from_academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='promotions_from')
    to_academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='promotions_to')
    promoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='promotions')
    promotion_type = models.CharField(max_length=20, choices=[
        ('automatic', 'Automatic'),
        ('manual', 'Manual'),
        ('bulk', 'Bulk'),
    ])
    total_students = models.PositiveIntegerField()
    promoted_count = models.PositiveIntegerField()
    retained_count = models.PositiveIntegerField()
    graduated_count = models.PositiveIntegerField()
    left_count = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
```

### Migration Strategy

1. **Create AcademicYear model** - New table
2. **Create Section model** (if needed) - New table
3. **Create StudentClassEnrollment model** - New table
4. **Create PromotionLog model** - New table
5. **Migrate existing data**:
   - Extract academic years from Term.academic_year
   - Create AcademicYear records
   - Create StudentClassEnrollment records from current Student.grade + Student.school_class
   - Link to current academic year

## 2. Business Logic Flow

### 2.1 Promotion Service Structure

```
core/services/promotion_service.py
├── PromotionService (main service class)
│   ├── validate_promotion_prerequisites()
│   ├── get_eligible_students()
│   ├── calculate_promotion_targets()
│   ├── preview_promotion()
│   ├── execute_promotion()
│   └── rebalance_sections()
├── PromotionPreview (data class)
└── PromotionResult (data class)
```

### 2.2 Promotion Workflow

1. **Selection Phase**
   - Select source academic year (current)
   - Select target academic year (next)
   - Choose promotion mode: automatic/manual/bulk

2. **Preview Phase**
   - Show eligible students
   - Show promotion targets (grade + class + section)
   - Show exceptions (retained, graduated, left)
   - Allow manual adjustments

3. **Confirmation Phase**
   - Review summary
   - Confirm execution
   - Show estimated time

4. **Execution Phase**
   - Create new enrollments
   - Update student status
   - Handle section rebalancing
   - Create audit log
   - Send notifications (optional)

### 2.3 Edge Cases Handling

1. **Retained Students**: Keep in same grade, mark as 'retained'
2. **Graduated Students**: Move to highest grade → mark as 'graduated', set is_active=False
3. **Left School**: Mark enrollment as 'left', keep historical record
4. **Missing Next Grade**: Alert user, allow custom grade assignment
5. **Section Capacity**: Auto-rebalance or alert if over capacity
6. **Concurrent Promotions**: Use database transactions, lock records
7. **Rollback**: Keep old enrollments, mark new ones as 'pending' until confirmed

## 3. Code Structure

### 3.1 Service Layer

```python
# core/services/promotion_service.py

from django.db import transaction
from django.utils import timezone
from dataclasses import dataclass
from typing import List, Dict, Optional
from decimal import Decimal

@dataclass
class PromotionPreview:
    student_id: int
    student_name: str
    current_grade: str
    current_class: str
    target_grade: str
    target_class: str
    action: str  # 'promote', 'retain', 'graduate', 'leave'
    notes: str

@dataclass
class PromotionResult:
    success: bool
    promoted_count: int
    retained_count: int
    graduated_count: int
    left_count: int
    errors: List[str]
    log_id: Optional[int]

class PromotionService:
    def __init__(self, school, user):
        self.school = school
        self.user = user
    
    def validate_prerequisites(self, from_year, to_year):
        """Validate that promotion can proceed"""
        # Check academic years exist
        # Check to_year is after from_year
        # Check no active promotion in progress
        # Check students have enrollments
        pass
    
    def get_eligible_students(self, academic_year, exclude_statuses=None):
        """Get students eligible for promotion"""
        # Get all active enrollments for academic year
        # Exclude retained, graduated, left
        pass
    
    def calculate_promotion_targets(self, students, target_year):
        """Calculate where each student should be promoted"""
        # For each student:
        #   - Get next grade (or same if retained)
        #   - Get appropriate class
        #   - Get section (rebalance if needed)
        pass
    
    def preview_promotion(self, from_year, to_year, student_ids=None):
        """Generate promotion preview without committing"""
        # Get eligible students
        # Calculate targets
        # Return preview data
        pass
    
    @transaction.atomic
    def execute_promotion(self, preview_data, promotion_type='automatic'):
        """Execute the promotion"""
        # Create new enrollments
        # Update old enrollments status
        # Handle graduates
        # Rebalance sections
        # Create audit log
        # Return result
        pass
    
    def rebalance_sections(self, grade, target_year, students):
        """Rebalance students across sections"""
        # Get available sections
        # Distribute students evenly
        # Respect capacity limits
        pass
```

### 3.2 Views Structure

```python
# core/views.py (add promotion views)

@login_required
def promotion_wizard_step1(request):
    """Step 1: Select academic years"""
    pass

@login_required
def promotion_wizard_step2(request):
    """Step 2: Select students and mode"""
    pass

@login_required
def promotion_preview(request):
    """Step 3: Preview promotion"""
    pass

@login_required
def promotion_execute(request):
    """Step 4: Execute promotion"""
    pass

@login_required
def promotion_history(request):
    """View promotion history"""
    pass
```

## 4. Frontend Flow

### 4.1 Multi-Step Wizard

**Step 1: Academic Year Selection**
- Select "From" academic year (current)
- Select "To" academic year (next)
- Show year details (dates, student counts)

**Step 2: Promotion Mode & Filters**
- Choose mode: Automatic / Manual / Bulk
- Filter by grade, class, section
- Exclude specific students
- Set default actions (retain, graduate, etc.)

**Step 3: Preview & Adjust**
- Table showing all students
- Columns: Name, Current Grade/Class, Target Grade/Class, Action, Notes
- Allow inline editing of targets
- Show warnings (missing grade, capacity issues)
- Summary statistics

**Step 4: Confirmation**
- Final summary
- Estimated time
- Confirmation checkbox
- Execute button

**Step 5: Results**
- Success/error messages
- Promotion log details
- Link to view new enrollments

## 5. Edge Cases & Safety

### 5.1 Transaction Safety
- Use `@transaction.atomic` for entire promotion
- Rollback on any error
- Keep old enrollments intact

### 5.2 Data Integrity
- Validate all foreign keys exist
- Check section capacity before assignment
- Ensure roll numbers are unique per class
- Prevent duplicate enrollments

### 5.3 Concurrency
- Use `select_for_update()` for critical sections
- Check for concurrent promotions
- Lock academic year records during promotion

### 5.4 Graduation Logic
- Identify highest grade in school
- Mark students in highest grade as graduated
- Set is_active=False on student
- Create final enrollment with 'graduated' status

### 5.5 Section Rebalancing
- Calculate optimal distribution
- Respect capacity limits
- Maintain alphabetical/roll number order where possible
- Alert if manual intervention needed

## 6. Implementation Steps

1. ✅ Create models (AcademicYear, StudentClassEnrollment, Section, PromotionLog)
2. ✅ Create and run migrations
3. ✅ Create data migration to populate initial enrollments
4. ✅ Create PromotionService
5. ✅ Create views (wizard steps)
6. ✅ Create templates
7. ✅ Add URL routes
8. ✅ Add admin integration
9. ✅ Add tests
10. ✅ Documentation

## 7. Testing Checklist

- [ ] Promote all students automatically
- [ ] Promote with manual selections
- [ ] Retain specific students
- [ ] Graduate highest grade students
- [ ] Handle students who left
- [ ] Section rebalancing
- [ ] Roll number assignment
- [ ] Concurrent promotion prevention
- [ ] Transaction rollback on error
- [ ] Audit log creation
- [ ] Historical data preservation

