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
        'school_class', 'subject', 'teacher', 'time_slot'
    ).order_by('school_class', 'time_slot__day', 'time_slot__period_number')
    
    class_id = request.GET.get('class_id', '')
    if class_id:
        timetables = timetables.filter(school_class_id=class_id)
    
    day = request.GET.get('day', '')
    if day:
        timetables = timetables.filter(time_slot__day=day)
    
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('name')
    
    # Group by class and day
    timetable_dict = {}
    for tt in timetables:
        class_name = tt.school_class.name
        day_name = tt.time_slot.get_day_display()
        if class_name not in timetable_dict:
            timetable_dict[class_name] = {}
        if day_name not in timetable_dict[class_name]:
            timetable_dict[class_name][day_name] = []
        timetable_dict[class_name][day_name].append(tt)
    
    context = {
        'timetable_dict': timetable_dict,
        'classes': classes,
        'class_id': class_id,
        'day': day,
    }
    return render(request, 'timetable/timetable_list.html', context)


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
    
    context = {
        'classes': classes,
        'subjects': subjects,
        'teachers': teachers,
        'time_slots': time_slots,
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
    
    # Filter by break status
    show_breaks = request.GET.get('show_breaks', 'false').lower() == 'true'
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
        days_to_create = []
        if all_days:
            days_to_create = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        elif selected_days:
            days_to_create = selected_days
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
def timeslot_generate(request):
    """Generate generic time slots for all days"""
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Default time slots configuration
        # You can customize these default times
        default_periods = [
            {'period': 1, 'start': '08:00', 'end': '08:40'},
            {'period': 2, 'start': '08:40', 'end': '09:20'},
            {'period': 3, 'start': '09:20', 'end': '10:00'},
            {'period': 4, 'start': '10:00', 'end': '10:40'},
            {'period': 5, 'start': '11:00', 'end': '11:40'},
            {'period': 6, 'start': '11:40', 'end': '12:20'},
            {'period': 7, 'start': '12:20', 'end': '13:00'},
            {'period': 8, 'start': '13:00', 'end': '13:40'},
        ]
        
        # Default breaks
        default_breaks = [
            {'name': 'Morning Break', 'start': '10:40', 'end': '11:00'},
            {'name': 'Lunch Break', 'start': '13:40', 'end': '14:20'},
        ]
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        created_count = 0
        skipped_count = 0
        
        for day in days:
            # Create periods
            for period_data in default_periods:
                # Check if time slot already exists
                if not TimeSlot.objects.filter(
                    school=school, 
                    day=day, 
                    period_number=period_data['period'],
                    is_break=False
                ).exists():
                    TimeSlot.objects.create(
                        school=school,
                        day=day,
                        start_time=period_data['start'],
                        end_time=period_data['end'],
                        period_number=period_data['period'],
                        is_break=False
                    )
                    created_count += 1
                else:
                    skipped_count += 1
            
            # Create breaks
            for break_data in default_breaks:
                # Check if break already exists (by time range and break name)
                if not TimeSlot.objects.filter(
                    school=school,
                    day=day,
                    start_time=break_data['start'],
                    end_time=break_data['end'],
                    is_break=True,
                    break_name=break_data['name']
                ).exists():
                    # Find the maximum period number for this day (including breaks)
                    max_period = TimeSlot.objects.filter(
                        school=school, 
                        day=day
                    ).aggregate(Max('period_number'))['period_number__max'] or 0
                    
                    # Find next available period number that doesn't conflict
                    next_period = max_period + 1
                    # Ensure it doesn't conflict with existing periods
                    while TimeSlot.objects.filter(
                        school=school,
                        day=day,
                        period_number=next_period
                    ).exists():
                        next_period += 1
                    
                    TimeSlot.objects.create(
                        school=school,
                        day=day,
                        start_time=break_data['start'],
                        end_time=break_data['end'],
                        period_number=next_period,
                        is_break=True,
                        break_name=break_data['name']
                    )
                    created_count += 1
                else:
                    skipped_count += 1
        
        if created_count > 0:
            messages.success(request, f'Successfully created {created_count} generic time slots! You can now customize them as needed.')
        if skipped_count > 0:
            messages.info(request, f'Skipped {skipped_count} time slots that already exist.')
        
        return redirect('timetable:timeslot_list')
    
    # GET request - show confirmation page
    existing_count = TimeSlot.objects.filter(school=school).count()
    return render(request, 'timetable/timeslot_generate.html', {
        'existing_count': existing_count,
    })
