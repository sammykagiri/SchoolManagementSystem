# CBC Subject Alignment - Implementation Summary

## ✅ Implementation Complete

All CBC alignment changes have been successfully implemented. The system is ready for migration.

## Changes Implemented

### 1. Models Updated (`timetable/models.py`)

#### New Models:
- **`SubjectPathway`**: CBC pathways (STEM, Social Sciences, Arts & Sports)
- **`StudentSubjectSelection`**: Tracks student subject selections per term with mutual exclusivity validation

#### Updated `Subject` Model:
- ✅ `learning_level` - CBC learning levels (Early Years, Lower Primary, Upper Primary, Junior Secondary)
- ✅ `knec_code` - Official KNEC subject codes (unique, numeric)
- ✅ `is_compulsory` - Compulsory/Optional flag (default: True)
- ✅ `is_religious_education` - Religious education flag
- ✅ `religious_type` - CRE/IRE/HRE selection
- ✅ `pathway` - ForeignKey to SubjectPathway
- ✅ `applicable_grades` - ManyToMany to Grade
- ✅ Validation logic in `clean()` method
- ✅ Database indexes for performance

### 2. Migrations Created

**Migration**: `0005_subject_applicable_grades_subject_is_compulsory_and_more.py`
- Adds all new CBC fields to Subject model
- Creates SubjectPathway model
- Creates StudentSubjectSelection model
- Adds database indexes
- Adds unique constraint for KNEC codes

**Status**: Ready to apply (not yet applied)

### 3. Serializers Updated (`timetable/serializers.py`)

- ✅ `SubjectSerializer` - Includes all new CBC fields with display names
- ✅ `SubjectPathwaySerializer` - New serializer for pathways
- ✅ `StudentSubjectSelectionSerializer` - New serializer for student selections
- ✅ Validation logic in serializers

### 4. Views Updated (`timetable/views.py`)

#### Updated `SubjectViewSet`:
- ✅ Filter by `learning_level`
- ✅ Filter by `is_compulsory`
- ✅ Filter by `pathway_id`
- ✅ Filter by `grade_id`
- ✅ Filter by `is_religious_education`
- ✅ Filter by `religious_type`
- ✅ Search by `knec_code`

#### New ViewSets:
- ✅ `SubjectPathwayViewSet` - CRUD for pathways
- ✅ `StudentSubjectSelectionViewSet` - CRUD for student selections with filters

### 5. Admin Updated (`timetable/admin.py`)

- ✅ `SubjectAdmin` - Updated with new fields, filters, and fieldsets
- ✅ `SubjectPathwayAdmin` - New admin for pathways
- ✅ `StudentSubjectSelectionAdmin` - New admin for student selections

### 6. URLs Updated (`timetable/urls.py`)

- ✅ Added API routes for pathways: `/api/pathways/`
- ✅ Added API routes for student selections: `/api/student-selections/`

### 7. Management Command Created

**Command**: `populate_subject_grades.py`
- Populates `applicable_grades` from existing timetables
- Supports dry-run mode
- Can process specific school or all schools

## Next Steps

### 1. Apply Migrations

```bash
python manage.py migrate timetable
```

### 2. Populate Data (Optional)

After migration, populate `applicable_grades` from existing timetables:

```bash
# Dry run first
python manage.py populate_subject_grades --dry-run

# Apply for all schools
python manage.py populate_subject_grades

# Or for specific school
python manage.py populate_subject_grades --school-id 1
```

### 3. Create Initial Pathways (Optional)

For Junior Secondary schools, create pathways:

```python
from timetable.models import SubjectPathway
from core.models import School

school = School.objects.get(id=1)  # Your school ID

SubjectPathway.objects.get_or_create(
    school=school,
    name='stem',
    defaults={'description': 'STEM Pathway'}
)

SubjectPathway.objects.get_or_create(
    school=school,
    name='social_sciences',
    defaults={'description': 'Social Sciences Pathway'}
)

SubjectPathway.objects.get_or_create(
    school=school,
    name='arts_sports',
    defaults={'description': 'Arts & Sports Pathway'}
)
```

### 4. Update Existing Subjects (Optional)

Manually update existing subjects with:
- `learning_level` based on their grade associations
- `knec_code` if you have official KNEC codes
- `is_compulsory` flag
- `is_religious_education` and `religious_type` for CRE/IRE/HRE subjects

## Backward Compatibility

✅ **All changes are backward compatible:**
- All new fields are nullable/optional
- Existing fields preserved
- Existing API endpoints unchanged
- Existing functionality continues to work

## API Usage Examples

### Filter subjects by learning level:
```
GET /timetable/api/subjects/?learning_level=lower_primary
```

### Filter subjects by grade:
```
GET /timetable/api/subjects/?grade_id=1
```

### Filter compulsory subjects:
```
GET /timetable/api/subjects/?is_compulsory=true
```

### Filter religious education subjects:
```
GET /timetable/api/subjects/?is_religious_education=true&religious_type=CRE
```

### Get student subject selections:
```
GET /timetable/api/student-selections/?student_id=1&term_id=1
```

## Testing Checklist

- [ ] Run migrations successfully
- [ ] Verify existing subjects still work
- [ ] Test creating new subjects with CBC fields
- [ ] Test religious education mutual exclusivity validation
- [ ] Test API filters
- [ ] Test pathway creation and assignment
- [ ] Test student subject selection
- [ ] Verify admin interface works with new fields

## Files Modified

1. `timetable/models.py` - Models updated
2. `timetable/serializers.py` - Serializers updated
3. `timetable/views.py` - Views updated
4. `timetable/admin.py` - Admin updated
5. `timetable/urls.py` - URLs updated
6. `timetable/management/commands/populate_subject_grades.py` - New command

## Files Created

1. `timetable/migrations/0005_subject_applicable_grades_subject_is_compulsory_and_more.py`
2. `timetable/management/__init__.py`
3. `timetable/management/commands/__init__.py`
4. `timetable/management/commands/populate_subject_grades.py`

## Notes

- The `code` field remains for backward compatibility (internal codes)
- `knec_code` is separate and globally unique (official KNEC codes)
- Religious education validation only applies to new `StudentSubjectSelection` entries
- Existing timetables are unaffected by the changes
- All new features are optional and can be adopted gradually
