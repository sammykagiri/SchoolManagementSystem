# Subject Level Management - User Guide

## Overview

New views have been created to help manage subjects organized by CBC learning levels. This provides a structured way to view, filter, and manage subjects according to Kenya's CBC curriculum.

## New Views and Features

### 1. **Subject Level Overview** (`subject_level_overview`)

**URL**: `/timetable/subjects/overview/`

**Purpose**: Dashboard showing statistics and quick access for each learning level.

**Features**:
- Statistics for each learning level (total, active, compulsory, optional subjects)
- Template count for each level
- Applicable grades count
- Quick links to view subjects by level
- Highlights subjects without learning levels

**Access**: "View by Level" button on subject list page

---

### 2. **Subjects by Learning Level** (`subject_by_level`)

**URL**: `/timetable/subjects/level/<learning_level>/`

**Purpose**: View and manage subjects for a specific learning level.

**Features**:
- Filtered list of subjects for the selected level
- Shows applicable grades for that level
- Filters by type (compulsory/optional) and status (active/inactive)
- Search functionality
- Quick sync with templates
- Statistics for the level

**Example URLs**:
- `/timetable/subjects/level/lower_primary/` - Lower Primary subjects
- `/timetable/subjects/level/upper_primary/` - Upper Primary subjects
- `/timetable/subjects/level/junior_secondary/` - Junior Secondary subjects

---

### 3. **Bulk Update Learning Levels** (`subject_bulk_update_level`)

**URL**: `/timetable/subjects/bulk-update-level/`

**Purpose**: Assign learning levels to multiple subjects at once.

**Features**:
- Select multiple subjects
- Assign them to a learning level
- Useful for organizing existing subjects
- Shows current learning level (if any) for each subject

**Use Cases**:
- Organizing existing subjects that don't have learning levels
- Moving subjects between levels
- Batch assignment after initial setup

---

### 4. **Sync with Templates** (`subject_sync_with_templates`)

**URL**: `/timetable/subjects/sync/<learning_level>/`

**Purpose**: Update existing subjects with missing information from CBC templates.

**Features**:
- Only updates empty/missing fields
- Preserves existing data
- Updates: codes, KNEC codes, descriptions, learning levels
- Shows which subjects will be synced before confirming

**Use Cases**:
- After generating subjects, sync to fill in missing KNEC codes
- Update subjects created manually with template data
- Ensure consistency with CBC standards

---

### 5. **Enhanced Subject List** (`subject_list`)

**Updated Features**:
- **Filters**:
  - By learning level
  - By type (compulsory/optional)
  - By status (active/inactive)
  - Search by name, code, or KNEC code
- **Statistics Cards**: Total, active, compulsory, optional counts
- **Quick Access Links**: Buttons to view subjects by each learning level
- **Enhanced Table**: Shows learning level, type, and more details

---

## Navigation Flow

```
Subject List
    ├── View by Level → Level Overview
    │       ├── Lower Primary → Subjects by Level (Lower Primary)
    │       ├── Upper Primary → Subjects by Level (Upper Primary)
    │       ├── Junior Secondary → Subjects by Level (Junior Secondary)
    │       └── Early Years → Subjects by Level (Early Years)
    │
    ├── Generate CBC Subjects → Generate from Templates
    │
    ├── Bulk Update Levels → Assign levels to multiple subjects
    │
    └── Individual Subject → Edit/View/Delete
```

## Usage Examples

### Example 1: View All Lower Primary Subjects

1. Go to **Subjects** page
2. Click **"View by Level"**
3. Click **"Lower Primary"** card
4. See all Lower Primary subjects with filters

### Example 2: Organize Existing Subjects

1. Go to **Subjects** page
2. Click **"Bulk Update Learning Levels"**
3. Select subjects that need learning levels
4. Choose a learning level (e.g., "Lower Primary")
5. Click **"Update Learning Levels"**

### Example 3: Sync Subjects with Templates

1. Go to **Subjects** → **View by Level** → **Lower Primary**
2. Click **"Sync with Templates"** button
3. Review which subjects will be updated
4. Click **"Sync Subjects"**
5. Missing fields (codes, KNEC codes) will be filled from templates

### Example 4: Filter Subjects

1. Go to **Subjects** page
2. Use filters:
   - Select "Lower Primary" from Learning Level dropdown
   - Select "Compulsory" from Type dropdown
   - Click **"Filter"**
3. See only compulsory Lower Primary subjects

## Benefits

✅ **Organized Management**: Subjects grouped by CBC learning levels
✅ **Easy Navigation**: Quick access to subjects by level
✅ **Bulk Operations**: Update multiple subjects at once
✅ **Template Sync**: Keep subjects aligned with CBC standards
✅ **Better Filtering**: Find subjects quickly with multiple filters
✅ **Statistics**: Overview of subject distribution across levels

## Files Created

1. `timetable/views_subject_management.py` - New management views
2. `timetable/templates/timetable/subject_level_overview.html` - Level overview page
3. `timetable/templates/timetable/subject_by_level.html` - Subjects by level page
4. `timetable/templates/timetable/subject_bulk_update_level.html` - Bulk update page
5. `timetable/templates/timetable/subject_sync_confirm.html` - Sync confirmation page

## Files Modified

1. `timetable/views.py` - Enhanced `subject_list` with filters
2. `timetable/templates/timetable/subject_list.html` - Added filters and statistics
3. `timetable/urls.py` - Added new URL patterns

## API Endpoints

All views are accessible via web interface. The existing API endpoints (`/api/subjects/`) also support filtering by learning level:

```
GET /timetable/api/subjects/?learning_level=lower_primary
GET /timetable/api/subjects/?is_compulsory=true&learning_level=upper_primary
```

## Future Enhancements

Potential improvements:
- Export subjects by level
- Import subjects from CSV with learning levels
- Subject templates customization UI
- Grade-to-level mapping configuration
- Subject prerequisites by level



