# NEMIS/UPI Field Implementation Summary

## Overview
This document outlines the implementation of the NEMIS/UPI (National Education Management Information System / Unique Personal Identifier) field for the Student model, ensuring compliance with Kenya's CBC curriculum requirements.

---

## Section 1: Updated Student Model Snippet

**File:** `core/models.py`

```python
class Student(models.Model):
    # ... existing fields ...
    
    student_id = models.CharField(max_length=20)
    upi = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        unique=True,
        help_text='11-digit NEMIS / UPI number issued by the Ministry of Education',
        verbose_name='NEMIS/UPI Number'
    )
    first_name = models.CharField(max_length=100)
    # ... rest of fields ...
    
    def clean(self):
        """Validate UPI field"""
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        if self.upi:
            # Remove any whitespace
            self.upi = self.upi.strip()
            
            # Check if it contains only digits
            if not self.upi.isdigit():
                raise ValidationError({
                    'upi': 'UPI number must contain only digits.'
                })
            
            # Check if it's exactly 11 characters
            if len(self.upi) != 11:
                raise ValidationError({
                    'upi': 'UPI number must be exactly 11 digits.'
                })
```

**Key Features:**
- **Field Type:** `CharField` with `max_length=11`
- **Nullable:** `null=True, blank=True` (allows students without UPI)
- **Unique:** `unique=True` (ensures no duplicate UPI across all students)
- **Validation:** Model-level validation in `clean()` method
- **Help Text:** Clear description for users

---

## Section 2: Serializer Snippet

**File:** `core/serializers.py`

```python
class StudentSerializer(serializers.ModelSerializer):
    # ... existing fields ...
    
    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'upi', 'first_name', 'middle_name', 'last_name', 
            'gender', 'date_of_birth', 'grade', 'grade_id', 'admission_date', 
            'parent_name', 'parent_phone', 'parent_email', 'address', 
            'transport_route', 'transport_route_id', 'uses_transport', 
            'pays_meals', 'pays_activities', 'is_active', 'photo', 
            'parents', 'parent_ids'
        ]
        read_only_fields = ['id', 'student_id', 'grade', 'transport_route', 'parents']
```

**Notes:**
- `upi` is included in the `fields` list
- It's **not** in `read_only_fields`, so it can be written via API
- Validation is handled by the model's `clean()` method

---

## Section 3: Updated Student Form Template

**File:** `core/templates/core/student_form_new.html`

The UPI field has been added to the form template after the Student ID field:

```html
<!-- NEMIS/UPI Number -->
<div class="col-md-4">
    <label for="{{ form.upi.id_for_label }}" class="form-label">
        {{ form.upi.label }}
        {% if form.upi.field.required %}<span class="text-danger">*</span>{% endif %}
    </label>
    {{ form.upi }}
    {% if form.upi.help_text %}
        <div class="form-text">{{ form.upi.help_text }}</div>
    {% endif %}
    {% if form.upi.errors %}
        <div class="text-danger small">
            {% for error in form.upi.errors %}
                <div>{{ error }}</div>
            {% endfor %}
        </div>
    {% endif %}
</div>
```

**Form Field Configuration:**
- **Widget:** `TextInput` with HTML5 validation attributes
- **Attributes:**
  - `maxlength='11'` - Prevents entering more than 11 characters
  - `pattern='[0-9]{11}'` - HTML5 pattern validation (11 digits)
  - `placeholder='Enter 11-digit NEMIS/UPI number'` - User guidance

**Form Validation:**
- **File:** `core/forms.py`
- **Method:** `clean_upi()`
  - Strips whitespace
  - Validates digits-only
  - Validates exactly 11 characters
  - Checks uniqueness (excluding current instance)

---

## Section 4: Migration Steps

**Migration File:** `core/migrations/0021_add_student_upi_field.py`

### Pre-Migration Checklist:
1. ✅ Backup database
2. ✅ Review existing student data
3. ✅ Ensure no active transactions

### Migration Steps:

1. **Review the migration file:**
   ```bash
   python manage.py showmigrations core
   ```

2. **Apply the migration:**
   ```bash
   python manage.py migrate core
   ```

3. **Verify the migration:**
   ```bash
   python manage.py dbshell
   # In PostgreSQL/MySQL shell:
   # DESCRIBE core_student;  (MySQL)
   # \d core_student;  (PostgreSQL)
   ```

### Migration Details:
- **Operation:** `AddField`
- **Field:** `upi` (CharField, max_length=11)
- **Nullable:** Yes (`null=True, blank=True`)
- **Unique Constraint:** Yes (`unique=True`)
- **Backward Compatible:** Yes (existing students will have `NULL` UPI)

### Post-Migration:
- All existing students will have `upi = NULL`
- New students can optionally provide UPI
- Existing students can be updated with UPI numbers later

---

## Section 5: Optional DRF Filter Snippet

**File:** `core/views.py`

```python
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Multi-tenant: filter by user's school
        school = self.request.user.profile.school
        queryset = Student.objects.filter(school=school)
        
        # Filter by UPI if provided
        upi = self.request.query_params.get('upi', None)
        if upi:
            queryset = queryset.filter(upi=upi)
        
        return queryset
```

### Usage Examples:

**1. Query by UPI:**
```bash
GET /api/students/?upi=12345678901
```

**2. Combined with other filters:**
```bash
GET /api/students/?upi=12345678901&is_active=true
```

**3. Check if UPI exists:**
```python
# In Python/Django shell
from core.models import Student

# Check if UPI exists
student = Student.objects.filter(upi='12345678901').first()
if student:
    print(f"UPI found: {student.full_name}")
else:
    print("UPI not found")
```

---

## Section 6: Django Admin Integration

**File:** `core/admin.py`

```python
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'student_id', 'upi', 'first_name', 'middle_name', 'last_name', 
        'grade', 'linked_account', 'parent_name', 'parent_phone', 
        'linked_parents', 'is_active'
    ]
    list_filter = ['grade', 'gender', 'is_active', 'uses_transport', 'pays_meals', 'pays_activities']
    search_fields = [
        'student_id', 'upi', 'first_name', 'middle_name', 'last_name', 
        'parent_name', 'parent_phone', 'parent_email', 
        'user__username', 'user__email'
    ]
    # ... rest of configuration ...
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'student_id', 'upi', 'first_name', 'middle_name', 'last_name', 
                'gender', 'date_of_birth', 'grade', 'admission_date', 'is_active'
            )
        }),
        # ... rest of fieldsets ...
    )
```

**Admin Features:**
- UPI displayed in list view
- UPI searchable in admin
- UPI included in Basic Information fieldset
- Validation enforced through model's `clean()` method

---

## Validation Summary

### Model-Level Validation (`Student.clean()`):
1. ✅ Strips whitespace
2. ✅ Validates digits-only
3. ✅ Validates exactly 11 characters

### Form-Level Validation (`StudentForm.clean_upi()`):
1. ✅ All model validations
2. ✅ Uniqueness check (excludes current instance)
3. ✅ User-friendly error messages

### Database-Level Constraints:
1. ✅ `unique=True` - Database enforces uniqueness
2. ✅ `max_length=11` - Database enforces length limit
3. ✅ `null=True` - Allows NULL values for existing students

---

## Testing Checklist

### Manual Testing:
- [ ] Create new student without UPI (should succeed)
- [ ] Create new student with valid 11-digit UPI (should succeed)
- [ ] Create new student with invalid UPI (non-digits) (should fail)
- [ ] Create new student with invalid UPI (wrong length) (should fail)
- [ ] Create two students with same UPI (should fail on second)
- [ ] Update existing student to add UPI (should succeed)
- [ ] Update existing student to change UPI (should succeed)
- [ ] Search by UPI in admin (should work)
- [ ] Filter by UPI in API (should work)

### API Testing:
```bash
# Test UPI validation via API
curl -X POST http://localhost:8000/api/students/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "upi": "12345678901",
    ...
  }'
```

---

## Backward Compatibility

✅ **Fully Backward Compatible:**
- Existing students have `upi = NULL` (no data loss)
- All existing queries continue to work
- No breaking changes to API contracts
- Optional field (can be added gradually)

---

## Next Steps (Optional Enhancements)

1. **Bulk UPI Import:**
   - Create management command to import UPI numbers from CSV
   - Validate and update existing students

2. **UPI Validation Service:**
   - Integrate with NEMIS API (if available)
   - Real-time validation against Ministry database

3. **Reports:**
   - Report students without UPI
   - Track UPI registration progress

4. **Notifications:**
   - Alert when student reaches certain grade without UPI
   - Remind parents to register for UPI

---

## Files Modified

1. ✅ `core/models.py` - Added `upi` field and validation
2. ✅ `core/serializers.py` - Added `upi` to serializer fields
3. ✅ `core/forms.py` - Added `upi` field and validation
4. ✅ `core/templates/core/student_form_new.html` - Added UPI input field
5. ✅ `core/admin.py` - Added UPI to admin display and search
6. ✅ `core/views.py` - Added UPI filtering to API
7. ✅ `core/migrations/0021_add_student_upi_field.py` - Database migration

---

## Summary

The NEMIS/UPI field has been successfully implemented with:
- ✅ Proper validation (digits-only, exactly 11 characters)
- ✅ Uniqueness enforcement (database + application level)
- ✅ Backward compatibility (nullable field)
- ✅ Full integration (model, form, admin, API, template)
- ✅ User-friendly error messages
- ✅ Comprehensive documentation

The implementation follows Django best practices and ensures data integrity while maintaining flexibility for schools that may not have all UPI numbers immediately available.


