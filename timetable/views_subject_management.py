"""
Additional views for managing subjects by learning level
These views provide organized management of subjects grouped by CBC learning levels.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.decorators import permission_required
from django.db.models import Q, Count
from .models import Subject, SubjectPathway
from .cbc_subjects import (
    get_all_learning_levels, get_subjects_for_level, filter_grades_by_learning_level
)
from core.models import Grade


@login_required
@permission_required('view', 'subject')
def subject_by_level(request, learning_level):
    """View subjects for a specific learning level"""
    school = request.user.profile.school
    
    # Validate learning level
    valid_levels = get_all_learning_levels()
    if learning_level not in valid_levels:
        messages.error(request, f'Invalid learning level: {learning_level}')
        return redirect('timetable:subject_list')
    
    # Get subjects for this level
    subjects = Subject.objects.filter(
        school=school,
        learning_level=learning_level
    ).prefetch_related('applicable_grades', 'pathway').order_by('name')
    
    # Get filter parameters
    is_compulsory = request.GET.get('is_compulsory', '').strip()
    is_active = request.GET.get('is_active', '').strip()
    search_query = request.GET.get('search', '').strip()
    
    # Apply additional filters
    if is_compulsory:
        subjects = subjects.filter(is_compulsory=(is_compulsory.lower() == 'true'))
    
    if is_active:
        subjects = subjects.filter(is_active=(is_active.lower() == 'true'))
    
    if search_query:
        subjects = subjects.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(knec_code__icontains=search_query)
        )
    
    # Get applicable grades for this level
    all_grades = Grade.objects.filter(school=school).order_by('name')
    applicable_grades = filter_grades_by_learning_level(all_grades, learning_level)
    
    # Get level display name
    level_display = dict(Subject.LEARNING_LEVEL_CHOICES).get(learning_level, learning_level)
    
    # Statistics
    total_in_level = Subject.objects.filter(school=school, learning_level=learning_level).count()
    active_in_level = Subject.objects.filter(school=school, learning_level=learning_level, is_active=True).count()
    compulsory_in_level = Subject.objects.filter(school=school, learning_level=learning_level, is_compulsory=True).count()
    
    context = {
        'subjects': subjects,
        'learning_level': learning_level,
        'level_display': level_display,
        'applicable_grades': applicable_grades,
        'selected_is_compulsory': is_compulsory,
        'selected_is_active': is_active,
        'search_query': search_query,
        'total_in_level': total_in_level,
        'active_in_level': active_in_level,
        'compulsory_in_level': compulsory_in_level,
    }
    return render(request, 'timetable/subject_by_level.html', context)


@login_required
@permission_required('view', 'subject')
def subject_level_overview(request):
    """Overview of subjects organized by learning level"""
    school = request.user.profile.school
    learning_levels = get_all_learning_levels()
    
    # Get statistics for each level
    level_data = []
    for level in learning_levels:
        level_subjects = Subject.objects.filter(school=school, learning_level=level)
        level_display = dict(Subject.LEARNING_LEVEL_CHOICES).get(level, level)
        
        # Get applicable grades
        all_grades = Grade.objects.filter(school=school).order_by('name')
        applicable_grades = filter_grades_by_learning_level(all_grades, level)
        
        # Get template subjects count
        template_subjects = get_subjects_for_level(level)
        
        level_data.append({
            'level': level,
            'level_display': level_display,
            'total_subjects': level_subjects.count(),
            'active_subjects': level_subjects.filter(is_active=True).count(),
            'compulsory_subjects': level_subjects.filter(is_compulsory=True).count(),
            'optional_subjects': level_subjects.filter(is_compulsory=False).count(),
            'template_count': len(template_subjects),
            'applicable_grades_count': applicable_grades.count(),
            'has_subjects': level_subjects.exists(),
        })
    
    # Overall statistics
    all_subjects = Subject.objects.filter(school=school)
    total_subjects = all_subjects.count()
    subjects_with_level = all_subjects.exclude(learning_level__isnull=True).exclude(learning_level='').count()
    subjects_without_level = all_subjects.filter(Q(learning_level__isnull=True) | Q(learning_level='')).count()
    
    context = {
        'level_data': level_data,
        'total_subjects': total_subjects,
        'subjects_with_level': subjects_with_level,
        'subjects_without_level': subjects_without_level,
    }
    return render(request, 'timetable/subject_level_overview.html', context)


@login_required
def subject_bulk_update_level(request):
    """Bulk update learning level for multiple subjects"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        subject_ids = request.POST.getlist('subject_ids')
        new_level = request.POST.get('learning_level', '').strip()
        
        if not subject_ids:
            messages.error(request, 'No subjects selected.')
            return redirect('timetable:subject_list')
        
        if not new_level:
            messages.error(request, 'Please select a learning level.')
            return redirect('timetable:subject_list')
        
        # Validate learning level
        valid_levels = get_all_learning_levels()
        if new_level not in valid_levels:
            messages.error(request, 'Invalid learning level.')
            return redirect('timetable:subject_list')
        
        # Update subjects
        subjects = Subject.objects.filter(id__in=subject_ids, school=school)
        updated_count = subjects.update(learning_level=new_level)
        
        if updated_count > 0:
            messages.success(request, f'Successfully updated learning level for {updated_count} subject(s).')
        else:
            messages.warning(request, 'No subjects were updated.')
        
        return redirect('timetable:subject_list')
    
    # GET request - show form
    learning_levels = get_all_learning_levels()
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    
    return render(request, 'timetable/subject_bulk_update_level.html', {
        'learning_levels': learning_levels,
        'subjects': subjects,
    })


@login_required
def subject_sync_with_templates(request, learning_level):
    """Sync existing subjects with CBC templates (update missing fields)"""
    school = request.user.profile.school
    
    # Validate learning level
    valid_levels = get_all_learning_levels()
    if learning_level not in valid_levels:
        messages.error(request, f'Invalid learning level: {learning_level}')
        return redirect('timetable:subject_list')
    
    if request.method == 'POST':
        # Get template subjects
        templates = get_subjects_for_level(learning_level)
        
        updated_count = 0
        synced_subjects = []
        
        for template in templates:
            # Find matching subject by name
            try:
                subject = Subject.objects.get(school=school, name=template['name'])
                
                # Update fields if they're empty or different
                updated = False
                
                if not subject.code and template.get('code'):
                    subject.code = template['code']
                    updated = True
                
                if not subject.knec_code and template.get('knec_code'):
                    subject.knec_code = template['knec_code']
                    updated = True
                
                if not subject.learning_level:
                    subject.learning_level = learning_level
                    updated = True
                
                if not subject.description and template.get('description'):
                    subject.description = template['description']
                    updated = True
                
                if updated:
                    subject.save()
                    updated_count += 1
                    synced_subjects.append(subject.name)
            
            except Subject.DoesNotExist:
                continue
            except Subject.MultipleObjectsReturned:
                # Handle multiple subjects with same name
                subjects = Subject.objects.filter(school=school, name=template['name'])
                for subject in subjects:
                    if not subject.learning_level:
                        subject.learning_level = learning_level
                        subject.save()
                        updated_count += 1
                        synced_subjects.append(f"{subject.name} (ID: {subject.id})")
        
        if updated_count > 0:
            messages.success(
                request,
                f'Synced {updated_count} subject(s) with CBC templates for {dict(Subject.LEARNING_LEVEL_CHOICES).get(learning_level, learning_level)}.'
            )
        else:
            messages.info(request, 'No subjects needed syncing. All subjects are up to date.')
        
        return redirect('timetable:subject_by_level', learning_level=learning_level)
    
    # GET request - show confirmation
    templates = get_subjects_for_level(learning_level)
    existing_subjects = Subject.objects.filter(
        school=school,
        learning_level=learning_level
    ).values_list('name', flat=True)
    
    # Find subjects that can be synced
    syncable = []
    for template in templates:
        if template['name'] in existing_subjects:
            syncable.append(template['name'])
    
    level_display = dict(Subject.LEARNING_LEVEL_CHOICES).get(learning_level, learning_level)
    
    return render(request, 'timetable/subject_sync_confirm.html', {
        'learning_level': learning_level,
        'level_display': level_display,
        'syncable_subjects': syncable,
        'syncable_count': len(syncable),
    })



