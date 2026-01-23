"""
Student Promotion Views
These views handle the multi-step promotion wizard
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import AcademicYear, Grade, SchoolClass, Section, StudentClassEnrollment, PromotionLog
from .services.promotion_service import PromotionService, PromotionPreview, PromotionResult
from .decorators import role_required, permission_required


@login_required
@role_required('super_admin', 'school_admin')
def promotion_wizard_step1(request):
    """Step 1: Select academic years for promotion"""
    school = request.user.profile.school
    
    academic_years = AcademicYear.objects.filter(school=school).order_by('-start_date')
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    
    if request.method == 'POST':
        from_year_id = request.POST.get('from_year')
        to_year_id = request.POST.get('to_year')
        
        if not from_year_id or not to_year_id:
            messages.error(request, 'Please select both source and target academic years.')
            return render(request, 'core/promotion/step1_select_years.html', {
                'academic_years': academic_years,
                'current_year': current_year,
            })
        
        # Store in session for next step
        request.session['promotion_from_year'] = int(from_year_id)
        request.session['promotion_to_year'] = int(to_year_id)
        
        return redirect('core:promotion_wizard_step2')
    
    context = {
        'academic_years': academic_years,
        'current_year': current_year,
    }
    return render(request, 'core/promotion/step1_select_years.html', context)


@login_required
@permission_required('change', 'student_promotion')
def promotion_wizard_step2(request):
    """Step 2: Select promotion mode and filters"""
    school = request.user.profile.school
    
    # Get years from session
    from_year_id = request.session.get('promotion_from_year')
    to_year_id = request.session.get('promotion_to_year')
    
    if not from_year_id or not to_year_id:
        messages.error(request, 'Please start from step 1.')
        return redirect('core:promotion_wizard_step1')
    
    try:
        from_year = AcademicYear.objects.get(pk=from_year_id, school=school)
        to_year = AcademicYear.objects.get(pk=to_year_id, school=school)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'Invalid academic year selected.')
        return redirect('core:promotion_wizard_step1')
    
    # Get grades and classes for filtering
    grades = Grade.objects.filter(school=school).order_by('name')
    classes = SchoolClass.objects.filter(school=school, is_active=True).order_by('grade__name', 'name')
    
    if request.method == 'POST':
        promotion_type = request.POST.get('promotion_type', 'automatic')
        grade_filter = request.POST.get('grade_filter', '')
        class_filter = request.POST.get('class_filter', '')
        retain_students = request.POST.getlist('retain_students')
        graduate_students = request.POST.getlist('graduate_students')
        leave_students = request.POST.getlist('leave_students')
        
        # Store in session
        request.session['promotion_type'] = promotion_type
        request.session['promotion_grade_filter'] = grade_filter
        request.session['promotion_class_filter'] = class_filter
        request.session['promotion_retain'] = [int(s) for s in retain_students]
        request.session['promotion_graduate'] = [int(s) for s in graduate_students]
        request.session['promotion_leave'] = [int(s) for s in leave_students]
        
        return redirect('core:promotion_preview')
    
    # Get eligible students for preview
    service = PromotionService(school, request.user)
    enrollments = service.get_eligible_students(from_year_id)
    
    context = {
        'from_year': from_year,
        'to_year': to_year,
        'grades': grades,
        'classes': classes,
        'enrollments': enrollments[:50],  # Preview first 50
        'total_students': enrollments.count(),
    }
    return render(request, 'core/promotion/step2_select_mode.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def promotion_preview(request):
    """Step 3: Preview promotion before execution"""
    school = request.user.profile.school
    
    # Get data from session
    from_year_id = request.session.get('promotion_from_year')
    to_year_id = request.session.get('promotion_to_year')
    promotion_type = request.session.get('promotion_type', 'automatic')
    grade_filter = request.session.get('promotion_grade_filter', '')
    class_filter = request.session.get('promotion_class_filter', '')
    retain_students = set(request.session.get('promotion_retain', []))
    graduate_students = set(request.session.get('promotion_graduate', []))
    leave_students = set(request.session.get('promotion_leave', []))
    
    if not from_year_id or not to_year_id:
        messages.error(request, 'Please start from step 1.')
        return redirect('core:promotion_wizard_step1')
    
    try:
        from_year = AcademicYear.objects.get(pk=from_year_id, school=school)
        to_year = AcademicYear.objects.get(pk=to_year_id, school=school)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'Invalid academic year selected.')
        return redirect('core:promotion_wizard_step1')
    
    # Initialize service
    service = PromotionService(school, request.user)
    
    # Validate prerequisites
    errors = service.validate_prerequisites(from_year_id, to_year_id)
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect('core:promotion_wizard_step1')
    
    # Get eligible students
    enrollments = service.get_eligible_students(from_year_id)
    
    # Apply filters
    if grade_filter:
        enrollments = enrollments.filter(grade_id=grade_filter)
    if class_filter:
        enrollments = enrollments.filter(school_class_id=class_filter)
    
    # Calculate promotion targets
    previews = service.calculate_promotion_targets(
        list(enrollments),
        to_year_id,
        retain_student_ids=retain_students,
        graduate_student_ids=graduate_students,
        leave_student_ids=leave_students
    )
    
    # Statistics
    stats = {
        'total': len(previews),
        'promote': sum(1 for p in previews if p.action == 'promote'),
        'retain': sum(1 for p in previews if p.action == 'retain'),
        'graduate': sum(1 for p in previews if p.action == 'graduate'),
        'leave': sum(1 for p in previews if p.action == 'leave'),
    }
    
    if request.method == 'POST':
        # Handle manual adjustments from preview
        adjustments = {}
        for key, value in request.POST.items():
            if key.startswith('target_grade_'):
                student_id = int(key.replace('target_grade_', ''))
                adjustments[student_id] = adjustments.get(student_id, {})
                adjustments[student_id]['grade'] = value
            elif key.startswith('target_class_'):
                student_id = int(key.replace('target_class_', ''))
                adjustments[student_id] = adjustments.get(student_id, {})
                adjustments[student_id]['class'] = value
            elif key.startswith('action_'):
                student_id = int(key.replace('action_', ''))
                adjustments[student_id] = adjustments.get(student_id, {})
                adjustments[student_id]['action'] = value
        
        # Update previews with adjustments
        for preview in previews:
            if preview.student_id in adjustments:
                adj = adjustments[preview.student_id]
                if 'grade' in adj:
                    preview.target_grade = adj['grade']
                if 'class' in adj:
                    preview.target_class = adj['class']
                if 'action' in adj:
                    preview.action = adj['action']
        
        # Store updated previews in session (as JSON-serializable data)
        request.session['promotion_previews'] = [
            {
                'student_id': p.student_id,
                'student_name': p.student_name,
                'student_id_code': p.student_id_code,
                'current_grade': p.current_grade,
                'current_class': p.current_class,
                'current_section': p.current_section,
                'current_roll_number': p.current_roll_number,
                'target_grade': p.target_grade,
                'target_class': p.target_class,
                'target_section': p.target_section,
                'target_roll_number': p.target_roll_number,
                'action': p.action,
                'notes': p.notes,
                'warnings': p.warnings,
            }
            for p in previews
        ]
        
        return redirect('core:promotion_confirm')
    
    context = {
        'from_year': from_year,
        'to_year': to_year,
        'promotion_type': promotion_type,
        'previews': previews,
        'stats': stats,
    }
    return render(request, 'core/promotion/step3_preview.html', context)


@login_required
@permission_required('change', 'student_promotion')
def promotion_confirm(request):
    """Step 4: Final confirmation before execution"""
    school = request.user.profile.school
    
    # Get data from session
    from_year_id = request.session.get('promotion_from_year')
    to_year_id = request.session.get('promotion_to_year')
    promotion_type = request.session.get('promotion_type', 'automatic')
    previews_data = request.session.get('promotion_previews', [])
    
    if not from_year_id or not to_year_id:
        messages.error(request, 'Please start from step 1.')
        return redirect('core:promotion_wizard_step1')
    
    if not previews_data:
        messages.error(request, 'No promotion data found. Please go back to preview.')
        return redirect('core:promotion_preview')
    
    try:
        from_year = AcademicYear.objects.get(pk=from_year_id, school=school)
        to_year = AcademicYear.objects.get(pk=to_year_id, school=school)
    except AcademicYear.DoesNotExist:
        messages.error(request, 'Invalid academic year selected.')
        return redirect('core:promotion_wizard_step1')
    
    # Reconstruct previews from session data
    previews = []
    for data in previews_data:
        preview = PromotionPreview(
            student_id=data['student_id'],
            student_name=data['student_name'],
            student_id_code=data['student_id_code'],
            current_grade=data['current_grade'],
            current_class=data['current_class'],
            current_section=data['current_section'],
            current_roll_number=data['current_roll_number'],
            target_grade=data['target_grade'],
            target_class=data['target_class'],
            target_section=data['target_section'],
            target_roll_number=data['target_roll_number'],
            action=data['action'],
            notes=data['notes'],
            warnings=data['warnings'],
        )
        previews.append(preview)
    
    # Statistics
    stats = {
        'total': len(previews),
        'promote': sum(1 for p in previews if p.action == 'promote'),
        'retain': sum(1 for p in previews if p.action == 'retain'),
        'graduate': sum(1 for p in previews if p.action == 'graduate'),
        'leave': sum(1 for p in previews if p.action == 'leave'),
    }
    
    if request.method == 'POST' and request.POST.get('confirm') == 'yes':
        # Execute promotion
        service = PromotionService(school, request.user)
        result = service.execute_promotion(
            from_year_id,
            to_year_id,
            previews,
            promotion_type
        )
        
        if result.success:
            messages.success(
                request,
                f'Promotion completed successfully! '
                f'Promoted: {result.promoted_count}, '
                f'Retained: {result.retained_count}, '
                f'Graduated: {result.graduated_count}, '
                f'Left: {result.left_count}'
            )
            
            # Clear session
            for key in ['promotion_from_year', 'promotion_to_year', 'promotion_type',
                       'promotion_grade_filter', 'promotion_class_filter',
                       'promotion_retain', 'promotion_graduate', 'promotion_leave',
                       'promotion_previews']:
                request.session.pop(key, None)
            
            if result.log_id:
                return redirect('core:promotion_history')
            return redirect('core:promotion_wizard_step1')
        else:
            messages.error(request, f'Promotion failed: {", ".join(result.errors)}')
            if result.warnings:
                for warning in result.warnings:
                    messages.warning(request, warning)
    
    context = {
        'from_year': from_year,
        'to_year': to_year,
        'promotion_type': promotion_type,
        'previews': previews,
        'stats': stats,
    }
    return render(request, 'core/promotion/step4_confirm.html', context)


@login_required
@permission_required('view', 'student_promotion_history')
def promotion_history(request):
    """View promotion history/logs"""
    school = request.user.profile.school
    
    logs = PromotionLog.objects.filter(school=school).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
    }
    return render(request, 'core/promotion/history.html', context)

