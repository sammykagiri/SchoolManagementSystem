from rest_framework import viewsets, permissions
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Max
from .models import Subject, Teacher, TimeSlot, Timetable
from .serializers import SubjectSerializer, TeacherSerializer, TimeSlotSerializer, TimetableSerializer
from core.models import SchoolClass


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Subject.objects.filter(school=school)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TeacherViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Teacher.objects.filter(school=school).prefetch_related('subjects')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            queryset = queryset.filter(subjects__id=subject_id)
        
        return queryset.order_by('first_name', 'last_name')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TimeSlotViewSet(viewsets.ModelViewSet):
    serializer_class = TimeSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = TimeSlot.objects.filter(school=school)
        
        day = self.request.query_params.get('day')
        if day:
            queryset = queryset.filter(day=day)
        
        return queryset.order_by('day', 'period_number')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


class TimetableViewSet(viewsets.ModelViewSet):
    serializer_class = TimetableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = self.request.user.profile.school
        queryset = Timetable.objects.filter(school=school).select_related(
            'school_class', 'subject', 'teacher', 'time_slot'
        )
        
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        
        day = self.request.query_params.get('day')
        if day:
            queryset = queryset.filter(time_slot__day=day)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('school_class', 'time_slot__day', 'time_slot__period_number')

    def perform_create(self, serializer):
        school = self.request.user.profile.school
        serializer.save(school=school)


# UI Views
@login_required
def timetable_list(request):
    """List timetables"""
    school = request.user.profile.school
    timetables = Timetable.objects.filter(school=school, is_active=True).select_related(
        'school_class', 'school_class__grade', 'subject', 'teacher', 'time_slot'
    ).order_by('school_class', 'time_slot__day', 'time_slot__period_number')
    
    class_id = request.GET.get('class_id', '')
    if class_id:
        timetables = timetables.filter(school_class_id=class_id)
    
    grade_id = request.GET.get('grade_id', '')
    if grade_id:
        timetables = timetables.filter(school_class__grade_id=grade_id)
    
    day = request.GET.get('day', '')
    if day:
        timetables = timetables.filter(time_slot__day=day)
    
    # Get grades for filter dropdown
    from core.models import Grade
    grades = Grade.objects.filter(school=school).order_by('name')
    
    # Get classes - filter by grade if grade filter is applied
    classes = SchoolClass.objects.filter(school=school, is_active=True).select_related('grade').order_by('name')
    if grade_id:
        classes = classes.filter(grade_id=grade_id)
    
    # Get all time slots (including breaks) for the school, ordered by start time
    all_time_slots = TimeSlot.objects.filter(school=school).order_by('start_time', 'period_number').distinct()
    
    # Day order for consistent display - filter to selected day if day filter is applied
    all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_lower_map = {
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
        'sunday': 'Sunday'
    }
    if day and day in day_lower_map:
        day_order = [day_lower_map[day]]
    else:
        day_order = all_days
    
    # Group by class, then by time slot, then by day
    from collections import OrderedDict
    timetable_dict = OrderedDict()
    
    # Get all time slots grouped by day to build the complete structure
    # This ensures breaks are included even if they don't have timetable entries
    # Only process days that are in day_order (filtered if day filter is applied)
    all_slots_by_day = {}
    days_to_process = [d.lower() for d in day_order] if day else ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day_lower in days_to_process:
        day_slots = TimeSlot.objects.filter(school=school, day=day_lower).order_by('start_time', 'period_number')
        all_slots_by_day[day_lower] = day_slots
    
    # Process timetable entries
    # Create a mapping of class names to class objects for reference
    class_name_to_class = {}
    for c in classes:
        class_name_to_class[f"{c.name} ({c.grade.name})"] = c
    
    # Create a mapping of time slot keys to time slot IDs for each day
    # Only process days that are in day_order (filtered if day filter is applied)
    time_slot_id_map = {}  # {(start_time, end_time, period_number, is_break, day): time_slot_id}
    for day_lower in days_to_process:
        day_slots = TimeSlot.objects.filter(school=school, day=day_lower)
        for slot in day_slots:
            slot_key = (slot.start_time, slot.end_time, slot.period_number, slot.is_break, day_lower)
            time_slot_id_map[slot_key] = slot.id
    
    for tt in timetables:
        # Include grade in class name
        class_name = f"{tt.school_class.name} ({tt.school_class.grade.name})"
        time_slot = tt.time_slot
        start_time = time_slot.start_time
        end_time = time_slot.end_time
        day_name = time_slot.get_day_display()
        day_lower = time_slot.day
        
        # Create a unique key for time slot (using start_time for proper chronological ordering)
        time_slot_key = (start_time, end_time, time_slot.period_number, time_slot.is_break)
        
        if class_name not in timetable_dict:
            timetable_dict[class_name] = OrderedDict()
        
        if time_slot_key not in timetable_dict[class_name]:
            timetable_dict[class_name][time_slot_key] = {
                'period_number': time_slot.period_number,
                'start_time': start_time,
                'end_time': end_time,
                'is_break': time_slot.is_break,
                'break_name': time_slot.break_name if time_slot.is_break else None,
                'days': {},
                'class_id': tt.school_class.id,
            }
        timetable_dict[class_name][time_slot_key]['days'][day_name] = tt
    
    # For each class, add all time slots (including breaks) that exist but don't have timetable entries
    # This ensures breaks are shown even if they don't have entries
    for class_name, time_slots_data in timetable_dict.items():
        class_obj = class_name_to_class.get(class_name)
        if not class_obj:
            continue
            
        # Get all unique time slots across filtered days only
        for day_lower in days_to_process:
            day_name = day_lower_map.get(day_lower, day_lower.capitalize())
            day_slots = all_slots_by_day.get(day_lower, [])
            
            for slot in day_slots:
                time_slot_key = (slot.start_time, slot.end_time, slot.period_number, slot.is_break)
                
                # Add time slot structure if it doesn't exist
                if time_slot_key not in time_slots_data:
                    time_slots_data[time_slot_key] = {
                        'period_number': slot.period_number,
                        'start_time': slot.start_time,
                        'end_time': slot.end_time,
                        'is_break': slot.is_break,
                        'break_name': slot.break_name if slot.is_break else None,
                        'days': {},
                        'class_id': class_obj.id,
                    }
                
                # Store time slot ID for each day in the slot_data for "Add Entry" links
                # Only store for days in day_order (filtered days)
                if day_name in day_order:
                    slot_id_key = (slot.start_time, slot.end_time, slot.period_number, slot.is_break, day_lower)
                    if slot_id_key in time_slot_id_map:
                        if 'time_slot_ids' not in time_slots_data[time_slot_key]:
                            time_slots_data[time_slot_key]['time_slot_ids'] = {}
                        time_slots_data[time_slot_key]['time_slot_ids'][day_name] = time_slot_id_map[slot_id_key]
                    
                    # If it's a break and no timetable entry exists for this day, mark it
                    # Only mark for days in day_order (filtered days)
                    if slot.is_break and day_name not in time_slots_data[time_slot_key]['days']:
                        time_slots_data[time_slot_key]['days'][day_name] = None  # None means break exists but no entry
    
    # Sort each class's time slots by start time (chronological order)
    for class_name in timetable_dict:
        sorted_slots = OrderedDict(sorted(timetable_dict[class_name].items(), key=lambda x: (x[1]['start_time'], x[1]['period_number'])))
        timetable_dict[class_name] = sorted_slots
    
    # Ensure time slot IDs are stored only for filtered days (for empty cells to show Add Entry button)
    # Only add IDs for days that are in day_order (filtered if day filter is applied)
    for class_name, time_slots_data in timetable_dict.items():
        for time_slot_key, slot_data in time_slots_data.items():
            if 'time_slot_ids' not in slot_data:
                slot_data['time_slot_ids'] = {}
            # Only add time slot IDs for days in day_order (filtered days)
            for day_name in day_order:
                # Find the corresponding day_lower for this day_name
                day_lower = None
                for d_lower, d_name in day_lower_map.items():
                    if d_name == day_name:
                        day_lower = d_lower
                        break
                if day_lower:
                    slot_id_key = (slot_data['start_time'], slot_data['end_time'], slot_data['period_number'], slot_data['is_break'], day_lower)
                    if slot_id_key in time_slot_id_map:
                        slot_data['time_slot_ids'][day_name] = time_slot_id_map[slot_id_key]
    
    # Calculate statistics for sidebar summary
    from django.db.models import Count, Q
    from collections import Counter
    
    # Get all timetable entries for statistics (respecting filters)
    all_timetable_entries = Timetable.objects.filter(school=school, is_active=True)
    if class_id:
        all_timetable_entries = all_timetable_entries.filter(school_class_id=class_id)
    if grade_id:
        all_timetable_entries = all_timetable_entries.filter(school_class__grade_id=grade_id)
    if day:
        all_timetable_entries = all_timetable_entries.filter(time_slot__day=day)
    
    # Lessons per teacher
    teacher_stats_list = list(all_timetable_entries.filter(teacher__isnull=False).values(
        'teacher__first_name', 'teacher__last_name', 'teacher__employee_id'
    ).annotate(
        lesson_count=Count('id')
    ).order_by('-lesson_count', 'teacher__first_name', 'teacher__last_name'))
    teacher_stats = teacher_stats_list
    teacher_stats_remaining = max(0, len(teacher_stats_list) - 10) if len(teacher_stats_list) > 10 else 0
    
    # Lessons per subject
    subject_stats_list = list(all_timetable_entries.filter(subject__isnull=False).values(
        'subject__name', 'subject__code'
    ).annotate(
        lesson_count=Count('id')
    ).order_by('-lesson_count', 'subject__name'))
    subject_stats = subject_stats_list
    subject_stats_remaining = max(0, len(subject_stats_list) - 10) if len(subject_stats_list) > 10 else 0
    
    # Unassigned lessons (no teacher or no subject)
    # Note: subject is required (ForeignKey without null=True), so unassigned_no_subject should typically be 0
    unassigned_no_teacher = all_timetable_entries.filter(teacher__isnull=True).count()
    unassigned_no_subject = all_timetable_entries.filter(subject__isnull=True).count()
    # Total unassigned: entries missing either teacher or subject (or both)
    # Since each timetable entry is unique, we don't need distinct()
    unassigned_total = all_timetable_entries.filter(
        Q(teacher__isnull=True) | Q(subject__isnull=True)
    ).count()
    
    context = {
        'timetable_dict': timetable_dict,
        'classes': classes,
        'grades': grades,
        'class_id': class_id,
        'grade_id': grade_id,
        'day': day,
        'day_order': day_order,
        'all_time_slots': all_time_slots,
        'teacher_stats': teacher_stats,
        'teacher_stats_remaining': teacher_stats_remaining,
        'subject_stats': subject_stats,
        'subject_stats_remaining': subject_stats_remaining,
        'unassigned_no_teacher': unassigned_no_teacher,
        'unassigned_no_subject': unassigned_no_subject,
        'unassigned_total': unassigned_total,
    }
    return render(request, 'timetable/timetable_list.html', context)


@login_required
def timetable_print(request):
    """Printable timetable view - one class per page"""
    school = request.user.profile.school
    
    # Get filter parameters
    class_id = request.GET.get('class_id', '')
    grade_id = request.GET.get('grade_id', '')
    
    # Get timetables
    timetables = Timetable.objects.filter(school=school, is_active=True).select_related(
        'school_class', 'school_class__grade', 'subject', 'teacher', 'time_slot'
    ).order_by('school_class', 'time_slot__day', 'time_slot__period_number')
    
    if class_id:
        timetables = timetables.filter(school_class_id=class_id)
    
    if grade_id:
        timetables = timetables.filter(school_class__grade_id=grade_id)
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).select_related('grade').order_by('name')
    
    # Get all time slots grouped by day
    all_slots_by_day = {}
    for day_lower in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        day_slots = TimeSlot.objects.filter(school=school, day=day_lower).order_by('start_time', 'period_number')
        all_slots_by_day[day_lower] = day_slots
    
    # Day order for consistent display
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Group by class, then by time slot, then by day (same logic as timetable_list)
    from collections import OrderedDict
    timetable_dict = OrderedDict()
    
    # Create a mapping of time slot keys to time slot IDs for each day
    time_slot_id_map = {}
    for day_lower in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        day_slots = TimeSlot.objects.filter(school=school, day=day_lower)
        for slot in day_slots:
            slot_key = (slot.start_time, slot.end_time, slot.period_number, slot.is_break, day_lower)
            time_slot_id_map[slot_key] = slot.id
    
    # Process timetable entries
    class_name_to_class = {}
    for c in classes:
        class_name_to_class[f"{c.name} ({c.grade.name})"] = c
    
    for tt in timetables:
        class_name = f"{tt.school_class.name} ({tt.school_class.grade.name})"
        time_slot = tt.time_slot
        start_time = time_slot.start_time
        end_time = time_slot.end_time
        day_name = time_slot.get_day_display()
        day_lower = time_slot.day
        
        time_slot_key = (start_time, end_time, time_slot.period_number, time_slot.is_break)
        
        if class_name not in timetable_dict:
            timetable_dict[class_name] = OrderedDict()
        
        if time_slot_key not in timetable_dict[class_name]:
            timetable_dict[class_name][time_slot_key] = {
                'period_number': time_slot.period_number,
                'start_time': start_time,
                'end_time': end_time,
                'is_break': time_slot.is_break,
                'break_name': time_slot.break_name if time_slot.is_break else None,
                'days': {},
                'class_id': tt.school_class.id,
            }
        timetable_dict[class_name][time_slot_key]['days'][day_name] = tt
    
    # Add all time slots (including breaks) that don't have entries
    for class_name, time_slots_data in timetable_dict.items():
        class_obj = class_name_to_class.get(class_name)
        if not class_obj:
            continue
            
        for day_lower in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            day_name = day_order[['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(day_lower)]
            day_slots = all_slots_by_day.get(day_lower, [])
            
            for slot in day_slots:
                time_slot_key = (slot.start_time, slot.end_time, slot.period_number, slot.is_break)
                
                if time_slot_key not in time_slots_data:
                    time_slots_data[time_slot_key] = {
                        'period_number': slot.period_number,
                        'start_time': slot.start_time,
                        'end_time': slot.end_time,
                        'is_break': slot.is_break,
                        'break_name': slot.break_name if slot.is_break else None,
                        'days': {},
                        'class_id': class_obj.id,
                    }
                
                if slot.is_break and day_name not in time_slots_data[time_slot_key]['days']:
                    time_slots_data[time_slot_key]['days'][day_name] = None
    
    # Sort each class's time slots by start time
    for class_name in timetable_dict:
        sorted_slots = OrderedDict(sorted(timetable_dict[class_name].items(), key=lambda x: (x[1]['start_time'], x[1]['period_number'])))
        timetable_dict[class_name] = sorted_slots
    
    # Get school info for header
    from core.models import School
    school_obj = school
    
    context = {
        'timetable_dict': timetable_dict,
        'classes': classes,
        'class_id': class_id,
        'grade_id': grade_id,
        'day_order': day_order,
        'school': school_obj,
    }
    return render(request, 'timetable/timetable_print.html', context)


@login_required
def timetable_add(request):
    """Add a new timetable entry"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        school_class_id = request.POST.get('school_class', '').strip()
        subject_id = request.POST.get('subject', '').strip()
        teacher_id = request.POST.get('teacher', '').strip()
        time_slot_id = request.POST.get('time_slot', '').strip()
        room = request.POST.get('room', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not school_class_id:
            errors.append('Class is required.')
        if not subject_id:
            errors.append('Subject is required.')
        if not time_slot_id:
            errors.append('Time slot is required.')
        
        # Check for duplicate timetable entry (same class and time slot)
        if school_class_id and time_slot_id:
            if Timetable.objects.filter(school=school, school_class_id=school_class_id, time_slot_id=time_slot_id).exists():
                errors.append('A timetable entry already exists for this class and time slot.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            # Get all required data for form
            classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
            subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
            teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
            time_slots = TimeSlot.objects.filter(school=school, is_break=False).order_by('day', 'period_number')
            return render(request, 'timetable/timetable_form.html', {
                'classes': classes,
                'subjects': subjects,
                'teachers': teachers,
                'time_slots': time_slots,
                'post': request.POST,
            })
        
        # Create the timetable entry
        timetable = Timetable.objects.create(
            school=school,
            school_class_id=school_class_id,
            subject_id=subject_id,
            teacher_id=teacher_id if teacher_id else None,
            time_slot_id=time_slot_id,
            room=room if room else '',
            is_active=is_active
        )
        
        messages.success(request, f'Timetable entry created successfully!')
        return redirect('timetable:timetable_list')
    
    # GET request - show form
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    time_slots = TimeSlot.objects.filter(school=school, is_break=False).order_by('day', 'period_number')
    
    # Get pre-filled values from query parameters
    prefill_class_id = request.GET.get('class_id', '')
    prefill_time_slot_id = request.GET.get('time_slot_id', '')
    
    context = {
        'classes': classes,
        'subjects': subjects,
        'teachers': teachers,
        'time_slots': time_slots,
        'prefill_class_id': prefill_class_id,
        'prefill_time_slot_id': prefill_time_slot_id,
    }
    return render(request, 'timetable/timetable_form.html', context)


@login_required
def timetable_edit(request, timetable_id):
    """Edit an existing timetable entry"""
    school = request.user.profile.school
    timetable = get_object_or_404(Timetable, id=timetable_id, school=school)
    
    if request.method == 'POST':
        school_class_id = request.POST.get('school_class', '').strip()
        subject_id = request.POST.get('subject', '').strip()
        teacher_id = request.POST.get('teacher', '').strip()
        time_slot_id = request.POST.get('time_slot', '').strip()
        room = request.POST.get('room', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not school_class_id:
            errors.append('Class is required.')
        if not subject_id:
            errors.append('Subject is required.')
        if not time_slot_id:
            errors.append('Time slot is required.')
        
        # Check for duplicate timetable entry (same class and time slot, excluding current)
        if school_class_id and time_slot_id:
            if Timetable.objects.filter(school=school, school_class_id=school_class_id, time_slot_id=time_slot_id).exclude(id=timetable.id).exists():
                errors.append('A timetable entry already exists for this class and time slot.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            # Get all required data for form
            classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
            subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
            teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
            time_slots = TimeSlot.objects.filter(school=school).order_by('day', 'period_number')
            return render(request, 'timetable/timetable_form.html', {
                'timetable': timetable,
                'classes': classes,
                'subjects': subjects,
                'teachers': teachers,
                'time_slots': time_slots,
                'post': request.POST,
            })
        
        # Update the timetable entry
        timetable.school_class_id = school_class_id
        timetable.subject_id = subject_id
        timetable.teacher_id = teacher_id if teacher_id else None
        timetable.time_slot_id = time_slot_id
        timetable.room = room if room else ''
        timetable.is_active = is_active
        timetable.save()
        
        messages.success(request, f'Timetable entry updated successfully!')
        return redirect('timetable:timetable_list')
    
    # GET request - show form with existing data
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    time_slots = TimeSlot.objects.filter(school=school, is_break=False).order_by('day', 'period_number')
    
    context = {
        'timetable': timetable,
        'classes': classes,
        'subjects': subjects,
        'teachers': teachers,
        'time_slots': time_slots,
    }
    return render(request, 'timetable/timetable_form.html', context)


@login_required
def timetable_delete(request, timetable_id):
    """Delete a timetable entry"""
    school = request.user.profile.school
    timetable = get_object_or_404(Timetable, id=timetable_id, school=school)
    
    if request.method == 'POST':
        timetable.delete()
        messages.success(request, f'Timetable entry deleted successfully!')
        return redirect('timetable:timetable_list')
    
    return render(request, 'timetable/timetable_confirm_delete.html', {'timetable': timetable})


@login_required
def timetable_generate(request):
    """Generate generic timetable entries for selected classes and time slots"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Get selected classes
        all_classes = request.POST.get('all_classes') == 'on'
        selected_classes = request.POST.getlist('classes')
        
        # Get default subject (optional)
        default_subject_id = request.POST.get('default_subject', '').strip()
        
        # Determine which classes to create timetables for
        if all_classes:
            classes_to_create = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
        elif selected_classes:
            classes_to_create = SchoolClass.objects.filter(school=school, id__in=selected_classes, is_active=True).order_by('name')
        else:
            messages.error(request, 'Please select at least one class or choose "All Classes".')
            return redirect('timetable:timetable_generate')
        
        # Get all non-break time slots
        time_slots = TimeSlot.objects.filter(school=school, is_break=False).order_by('day', 'period_number')
        
        if not time_slots.exists():
            messages.error(request, 'No time slots found. Please create time slots first.')
            return redirect('timetable:timeslot_list')
        
        # Get or create placeholder subject if no default subject is selected
        if default_subject_id:
            try:
                default_subject = Subject.objects.get(id=default_subject_id, school=school)
            except Subject.DoesNotExist:
                messages.error(request, 'Selected default subject does not exist.')
                return redirect('timetable:timetable_generate')
        else:
            # Create or get placeholder subject
            default_subject, created = Subject.objects.get_or_create(
                school=school,
                name='To Be Assigned',
                defaults={
                    'code': 'TBA',
                    'description': 'Placeholder subject for timetable entries that need to be assigned',
                    'is_active': True
                }
            )
            if created:
                messages.info(request, 'Created placeholder subject "To Be Assigned" for unassigned timetable entries.')
        
        # Generate timetable entries
        created_count = 0
        skipped_count = 0
        
        for school_class in classes_to_create:
            for time_slot in time_slots:
                # Check if timetable entry already exists
                if Timetable.objects.filter(school=school, school_class=school_class, time_slot=time_slot).exists():
                    skipped_count += 1
                    continue
                
                # Create timetable entry
                Timetable.objects.create(
                    school=school,
                    school_class=school_class,
                    subject=default_subject,
                    teacher=None,
                    time_slot=time_slot,
                    room='',
                    is_active=True
                )
                created_count += 1
        
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} generic timetable entries! You can now assign subjects and teachers to them.')
        if skipped_count > 0:
            messages.info(request, f'Skipped {skipped_count} timetable entries that already exist.')
        
        return redirect('timetable:timetable_list')
    
    # GET request - show form
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    time_slots = TimeSlot.objects.filter(school=school, is_break=False).order_by('day', 'period_number')
    subjects = Subject.objects.filter(school=school, is_active=True).order_by('name')
    existing_count = Timetable.objects.filter(school=school).count()
    
    return render(request, 'timetable/timetable_generate.html', {
        'classes': classes,
        'time_slots': time_slots,
        'subjects': subjects,
        'existing_count': existing_count,
    })


@login_required
def subject_list(request):
    """List subjects"""
    school = request.user.profile.school
    subjects = Subject.objects.filter(school=school).order_by('name')
    
    context = {'subjects': subjects}
    return render(request, 'timetable/subject_list.html', context)


@login_required
def subject_detail(request, subject_id):
    """View subject details"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    context = {'subject': subject}
    return render(request, 'timetable/subject_detail.html', context)


@login_required
def subject_add(request):
    """Add a new subject"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not name:
            errors.append('Subject name is required.')
        
        # Check for duplicate subject name and code in the same school
        # First check if the exact combination exists (same subject with both name and code)
        exact_match = name and code and Subject.objects.filter(school=school, name=name, code=code).exists()
        name_exists = name and Subject.objects.filter(school=school, name=name).exists()
        code_exists = code and Subject.objects.filter(school=school, code=code).exists()
        
        if exact_match:
            errors.append('A subject with this name and code already exists.')
        elif name_exists:
            errors.append('A subject with this name already exists.')
        elif code_exists:
            errors.append('A subject with this code already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/subject_form.html', {
                'name': name,
                'code': code,
                'description': description,
                'is_active': is_active,
            })
        
        # Create the subject
        subject = Subject.objects.create(
            school=school,
            name=name,
            code=code,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Subject "{subject.name}" added successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_form.html')


@login_required
def subject_edit(request, subject_id):
    """Edit an existing subject"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        if not name:
            errors.append('Subject name is required.')
        
        # Check for duplicate subject name and code in the same school (excluding current subject)
        # First check if the exact combination exists (same subject with both name and code)
        exact_match = name and code and Subject.objects.filter(school=school, name=name, code=code).exclude(id=subject.id).exists()
        name_exists = name and Subject.objects.filter(school=school, name=name).exclude(id=subject.id).exists()
        code_exists = code and Subject.objects.filter(school=school, code=code).exclude(id=subject.id).exists()
        
        if exact_match:
            errors.append('A subject with this name and code already exists.')
        elif name_exists:
            errors.append('A subject with this name already exists.')
        elif code_exists:
            errors.append('A subject with this code already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/subject_form.html', {
                'subject': subject,
                'name': name,
                'code': code,
                'description': description,
                'is_active': is_active,
            })
        
        # Update the subject
        subject.name = name
        subject.code = code
        subject.description = description
        subject.is_active = is_active
        subject.save()
        
        messages.success(request, f'Subject "{subject.name}" updated successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_form.html', {
        'subject': subject,
        'name': subject.name,
        'code': subject.code,
        'description': subject.description,
        'is_active': subject.is_active,
    })


@login_required
def subject_delete(request, subject_id):
    """Delete a subject"""
    school = request.user.profile.school
    subject = get_object_or_404(Subject, id=subject_id, school=school)
    
    if request.method == 'POST':
        subject_name = subject.name
        subject.delete()
        messages.success(request, f'Subject "{subject_name}" deleted successfully!')
        return redirect('timetable:subject_list')
    
    return render(request, 'timetable/subject_confirm_delete.html', {'subject': subject})


@login_required
def teacher_list(request):
    """List teachers"""
    school = request.user.profile.school
    teachers = Teacher.objects.filter(school=school).prefetch_related('subjects').order_by('first_name', 'last_name')
    
    # Filter by active status (default: show active only)
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    if not show_inactive:
        teachers = teachers.filter(is_active=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(employee_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    context = {
        'teachers': teachers,
        'show_inactive': show_inactive,
        'search_query': search_query,
    }
    return render(request, 'timetable/teacher_list.html', context)


# Time Slot Management Views
@login_required
def timeslot_list(request):
    """List time slots"""
    school = request.user.profile.school
    time_slots = TimeSlot.objects.filter(school=school).order_by('day', 'period_number')
    
    # Filter by day
    day_filter = request.GET.get('day', '')
    if day_filter:
        time_slots = time_slots.filter(day=day_filter)
    
    # Filter by break status (default to True - show breaks by default)
    show_breaks = request.GET.get('show_breaks', 'true').lower() == 'true'
    if not show_breaks:
        time_slots = time_slots.filter(is_break=False)
    
    # Group by day for better display, ordered by day of week
    from collections import OrderedDict
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    time_slots_by_day = OrderedDict()
    
    # Initialize ordered dict with all days
    for day in day_order:
        time_slots_by_day[day] = []
    
    # Populate with actual time slots
    for slot in time_slots:
        day_name = slot.get_day_display()
        if day_name in time_slots_by_day:
            time_slots_by_day[day_name].append(slot)
    
    # Sort slots by start time when breaks are shown (chronological order)
    if show_breaks:
        for day_name in time_slots_by_day:
            time_slots_by_day[day_name].sort(key=lambda x: x.start_time)
    
    # Remove empty days
    time_slots_by_day = OrderedDict((day, slots) for day, slots in time_slots_by_day.items() if slots)
    
    context = {
        'time_slots_by_day': time_slots_by_day,
        'time_slots': time_slots,
        'day_filter': day_filter,
        'show_breaks': show_breaks,
    }
    return render(request, 'timetable/timeslot_list.html', context)


@login_required
def timeslot_add(request):
    """Add a new time slot"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Get selected days - can be single day, all days, or multiple selected days
        selected_days = request.POST.getlist('days')  # Multiple selection
        all_days = request.POST.get('all_days') == 'on'
        start_time = request.POST.get('start_time', '').strip()
        end_time = request.POST.get('end_time', '').strip()
        period_number = request.POST.get('period_number', '').strip()
        is_break = request.POST.get('is_break') == 'on'
        break_name = request.POST.get('break_name', '').strip()
        
        errors = []
        if not start_time:
            errors.append('Start time is required.')
        if not end_time:
            errors.append('End time is required.')
        if not is_break and not period_number:
            errors.append('Period number is required for non-break time slots.')
        
        # Determine which days to create time slots for
        # Priority: selected_days (even if "All Days" is checked, user may have unchecked some days)
        days_to_create = []
        if selected_days:
            days_to_create = selected_days
        elif all_days:
            days_to_create = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        else:
            errors.append('Please select at least one day or choose "All Days".')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/timeslot_form.html', {
                'selected_days': selected_days,
                'all_days': all_days,
                'start_time': start_time,
                'end_time': end_time,
                'period_number': period_number,
                'is_break': is_break,
                'break_name': break_name,
            })
        
        # Create time slots for each selected day
        created_count = 0
        skipped_count = 0
        for day in days_to_create:
            # Check for duplicate time slot (same school, day, and period number)
            if not is_break and period_number:
                if TimeSlot.objects.filter(school=school, day=day, period_number=period_number).exists():
                    skipped_count += 1
                    continue
            
            # For breaks, check by time range and break name
            if is_break:
                if TimeSlot.objects.filter(
                    school=school,
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                    is_break=True,
                    break_name=break_name
                ).exists():
                    skipped_count += 1
                    continue
                
                # Find next available period number for breaks
                max_period = TimeSlot.objects.filter(
                    school=school, 
                    day=day
                ).aggregate(Max('period_number'))['period_number__max'] or 0
                next_period = max_period + 1
                while TimeSlot.objects.filter(
                    school=school,
                    day=day,
                    period_number=next_period
                ).exists():
                    next_period += 1
                period_number = str(next_period)
            
            # Create the time slot
            TimeSlot.objects.create(
                school=school,
                day=day,
                start_time=start_time,
                end_time=end_time,
                period_number=int(period_number) if period_number else 0,
                is_break=is_break,
                break_name=break_name if is_break else ''
            )
            created_count += 1
        
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} time slot(s)!')
        if skipped_count > 0:
            messages.warning(request, f'Skipped {skipped_count} time slot(s) that already exist.')
        
        return redirect('timetable:timeslot_list')
    
    return render(request, 'timetable/timeslot_form.html')


@login_required
def timeslot_edit(request, timeslot_id):
    """Edit an existing time slot"""
    school = request.user.profile.school
    time_slot = get_object_or_404(TimeSlot, id=timeslot_id, school=school)
    
    if request.method == 'POST':
        day = request.POST.get('day', '').strip()
        start_time = request.POST.get('start_time', '').strip()
        end_time = request.POST.get('end_time', '').strip()
        period_number = request.POST.get('period_number', '').strip()
        is_break = request.POST.get('is_break') == 'on'
        break_name = request.POST.get('break_name', '').strip()
        
        errors = []
        if not day:
            errors.append('Day is required.')
        if not start_time:
            errors.append('Start time is required.')
        if not end_time:
            errors.append('End time is required.')
        if not is_break and not period_number:
            errors.append('Period number is required for non-break time slots.')
        
        # Check for duplicate time slot (same school, day, and period number, excluding current)
        if day and period_number:
            if TimeSlot.objects.filter(school=school, day=day, period_number=period_number).exclude(id=time_slot.id).exists():
                errors.append('A time slot with this day and period number already exists.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/timeslot_form.html', {
                'time_slot': time_slot,
                'day': day,
                'selected_days': [day] if day else [],
                'start_time': start_time,
                'end_time': end_time,
                'period_number': period_number,
                'is_break': is_break,
                'break_name': break_name,
            })
        
        # Update the time slot
        time_slot.day = day
        time_slot.start_time = start_time
        time_slot.end_time = end_time
        time_slot.period_number = int(period_number) if period_number else 0
        time_slot.is_break = is_break
        time_slot.break_name = break_name if is_break else ''
        time_slot.save()
        
        messages.success(request, f'Time slot updated successfully!')
        return redirect('timetable:timeslot_list')
    
    return render(request, 'timetable/timeslot_form.html', {
        'time_slot': time_slot,
        'day': time_slot.day,
        'selected_days': [time_slot.day],
        'start_time': time_slot.start_time.strftime('%H:%M'),
        'end_time': time_slot.end_time.strftime('%H:%M'),
        'period_number': time_slot.period_number,
        'is_break': time_slot.is_break,
        'break_name': time_slot.break_name,
    })


@login_required
def timeslot_delete(request, timeslot_id):
    """Delete a time slot"""
    school = request.user.profile.school
    time_slot = get_object_or_404(TimeSlot, id=timeslot_id, school=school)
    
    if request.method == 'POST':
        # Check if time slot is used in any timetable entries
        if Timetable.objects.filter(time_slot=time_slot).exists():
            messages.error(request, 'Cannot delete this time slot because it is being used in timetable entries.')
            return redirect('timetable:timeslot_list')
        
        time_slot.delete()
        messages.success(request, f'Time slot deleted successfully!')
        return redirect('timetable:timeslot_list')
    
    # Check if time slot is used
    is_used = Timetable.objects.filter(time_slot=time_slot).exists()
    
    return render(request, 'timetable/timeslot_confirm_delete.html', {
        'time_slot': time_slot,
        'is_used': is_used,
    })


@login_required
def timeslot_bulk_delete(request):
    """Bulk delete time slots"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        timeslot_ids = request.POST.getlist('timeslot_ids')
        
        if not timeslot_ids:
            messages.warning(request, 'No time slots selected for deletion.')
            return redirect('timetable:timeslot_list')
        
        # Get time slots that belong to this school
        time_slots = TimeSlot.objects.filter(id__in=timeslot_ids, school=school)
        
        # Check which time slots are used in timetables
        used_slots = []
        deletable_slots = []
        
        for slot in time_slots:
            if Timetable.objects.filter(time_slot=slot).exists():
                used_slots.append(slot)
            else:
                deletable_slots.append(slot)
        
        # Delete only slots that are not in use
        deleted_count = 0
        for slot in deletable_slots:
            slot.delete()
            deleted_count += 1
        
        if deleted_count > 0:
            messages.success(request, f'Successfully deleted {deleted_count} time slot(s)!')
        if used_slots:
            messages.error(request, f'Cannot delete {len(used_slots)} time slot(s) because they are being used in timetable entries.')
        
        return redirect('timetable:timeslot_list')
    
    return redirect('timetable:timeslot_list')


@login_required
def timeslot_generate(request):
    """Generate generic time slots for all days"""
    from datetime import datetime, timedelta
    
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Get form parameters
        start_time_str = request.POST.get('start_time', '').strip()
        num_periods = request.POST.get('num_periods', '').strip()
        period_duration = request.POST.get('period_duration', '').strip()  # in minutes
        
        # Get selected days
        all_days = request.POST.get('all_days') == 'on'
        selected_days = request.POST.getlist('days')
        
        # Get breaks data
        breaks_data = []
        break_count = int(request.POST.get('break_count', '0') or '0')
        for i in range(break_count):
            break_name = request.POST.get(f'break_{i}_name', '').strip()
            break_start = request.POST.get(f'break_{i}_start', '').strip()
            break_duration = request.POST.get(f'break_{i}_duration', '').strip()  # in minutes
            
            if break_name and break_start and break_duration:
                # Calculate break end time
                break_start_time = datetime.strptime(break_start, '%H:%M').time()
                break_duration_min = int(break_duration)
                break_end_time = (datetime.combine(datetime.today(), break_start_time) + 
                                 timedelta(minutes=break_duration_min)).time()
                breaks_data.append({
                    'name': break_name,
                    'start': break_start,
                    'end': break_end_time.strftime('%H:%M'),
                    'start_time_obj': break_start_time
                })
        
        # Determine which days to create time slots for
        # Priority: selected_days (even if "All Days" is checked, user may have unchecked some days)
        days_to_create = []
        if selected_days:
            days_to_create = selected_days
        elif all_days:
            days_to_create = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        else:
            days_to_create = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']  # Default to all days
        
        errors = []
        if not start_time_str:
            errors.append('Start time is required.')
        if not num_periods:
            errors.append('Number of periods is required.')
        if not period_duration:
            errors.append('Period duration is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'timetable/timeslot_generate.html', {
                'start_time': start_time_str,
                'num_periods': num_periods,
                'period_duration': period_duration,
                'break_count': break_count,
                'all_days': all_days,
                'selected_days': selected_days,
                'existing_count': TimeSlot.objects.filter(school=school).count(),
            })
        
        # Parse start time and calculate periods
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        period_duration_min = int(period_duration)
        num_periods_int = int(num_periods)
        
        # Sort breaks by start time
        breaks_data.sort(key=lambda x: x['start_time_obj'])
        
        # Generate periods and breaks together, adjusting period times when breaks occur
        all_slots = []
        current_time = datetime.combine(datetime.today(), start_time)
        period_num = 1
        break_index = 0
        
        for period_idx in range(num_periods_int):
            # Check if there's a break that should occur before this period starts
            while break_index < len(breaks_data):
                break_data = breaks_data[break_index]
                break_start = break_data['start_time_obj']
                break_end = datetime.strptime(break_data['end'], '%H:%M').time()
                
                # If break starts before or at current time, insert it
                if break_start <= current_time.time():
                    all_slots.append({
                        'type': 'break',
                        'name': break_data['name'],
                        'start': break_data['start'],
                        'end': break_data['end'],
                        'start_time_obj': break_start
                    })
                    # Move current time to after break ends
                    current_time = datetime.combine(datetime.today(), break_end)
                    break_index += 1
                else:
                    break
            
            # Calculate period start and end
            period_start = current_time.time()
            period_end = (current_time + timedelta(minutes=period_duration_min)).time()
            
            # Check if there's a break that occurs during this period
            if break_index < len(breaks_data):
                break_data = breaks_data[break_index]
                break_start = break_data['start_time_obj']
                break_end_time = datetime.strptime(break_data['end'], '%H:%M').time()
                
                # If break starts during this period (before period ends), adjust period end
                if break_start < period_end:
                    # Period ends at break start
                    period_end = break_start
                    all_slots.append({
                        'type': 'period',
                        'number': period_num,
                        'start': period_start.strftime('%H:%M'),
                        'end': period_end.strftime('%H:%M'),
                        'start_time_obj': period_start
                    })
                    # Insert the break
                    all_slots.append({
                        'type': 'break',
                        'name': break_data['name'],
                        'start': break_data['start'],
                        'end': break_data['end'],
                        'start_time_obj': break_start
                    })
                    # Move current time to after break ends for next period
                    current_time = datetime.combine(datetime.today(), break_end_time)
                    period_num += 1
                    break_index += 1
                    continue
            
            # No break during this period - add the full period
            all_slots.append({
                'type': 'period',
                'number': period_num,
                'start': period_start.strftime('%H:%M'),
                'end': period_end.strftime('%H:%M'),
                'start_time_obj': period_start
            })
            
            # Move to next period start
            current_time = datetime.combine(datetime.today(), period_end)
            period_num += 1
        
        # Add any remaining breaks that come after all periods
        while break_index < len(breaks_data):
            break_data = breaks_data[break_index]
            all_slots.append({
                'type': 'break',
                'name': break_data['name'],
                'start': break_data['start'],
                'end': break_data['end'],
                'start_time_obj': break_data['start_time_obj']
            })
            break_index += 1
        
        # Sort all slots by start time to ensure chronological order
        all_slots.sort(key=lambda x: x['start_time_obj'])
        
        # Use sorted list as periods
        periods = all_slots
        
        # Create time slots for selected days
        created_count = 0
        skipped_count = 0
        
        for day in days_to_create:
            # Get existing period numbers for this day to avoid conflicts
            existing_periods = set(
                TimeSlot.objects.filter(school=school, day=day)
                .values_list('period_number', flat=True)
            )
            
            # First, create all periods
            for period_data in periods:
                if period_data['type'] == 'period':
                    period_num = period_data['number']
                    # Check if time slot already exists
                    if period_num not in existing_periods:
                        try:
                            TimeSlot.objects.create(
                                school=school,
                                day=day,
                                start_time=period_data['start'],
                                end_time=period_data['end'],
                                period_number=period_num,
                                is_break=False
                            )
                            existing_periods.add(period_num)
                            created_count += 1
                        except Exception:
                            skipped_count += 1
                    else:
                        skipped_count += 1
            
            # Then, create all breaks (after periods to avoid conflicts)
            for period_data in periods:
                if period_data['type'] == 'break':
                    # Check if break already exists (by time and name)
                    if not TimeSlot.objects.filter(
                        school=school,
                        day=day,
                        start_time=period_data['start'],
                        end_time=period_data['end'],
                        is_break=True,
                        break_name=period_data['name']
                    ).exists():
                        # Find next available period number that doesn't conflict
                        # Start from max period number + 1
                        max_period = max(existing_periods) if existing_periods else 0
                        next_period = max_period + 1
                        
                        # Find the next available period number
                        while next_period in existing_periods:
                            next_period += 1
                        
                        try:
                            TimeSlot.objects.create(
                                school=school,
                                day=day,
                                start_time=period_data['start'],
                                end_time=period_data['end'],
                                period_number=next_period,
                                is_break=True,
                                break_name=period_data['name']
                            )
                            existing_periods.add(next_period)
                            created_count += 1
                        except Exception:
                            skipped_count += 1
                    else:
                        skipped_count += 1
        
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} generic time slots! You can now customize them as needed.')
        if skipped_count > 0:
            messages.info(request, f'Skipped {skipped_count} time slots that already exist.')
        
        return redirect('timetable:timeslot_list')
    
    # GET request - show form
    existing_count = TimeSlot.objects.filter(school=school).count()
    return render(request, 'timetable/timeslot_generate.html', {
        'existing_count': existing_count,
        'all_days': True,  # Default to all days checked
        'selected_days': [],  # Empty list means all days will be checked by default
    })
