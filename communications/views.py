from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import CommunicationTemplate, EmailMessage, SMSMessage, CommunicationLog
from .services import CommunicationService
from core.models import Student
from core.decorators import role_required
import json
import logging

logger = logging.getLogger(__name__)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def communications_dashboard(request):
    """Communications dashboard"""
    school = request.user.profile.school
    
    # Get recent statistics
    recent_emails = EmailMessage.objects.filter(school=school).order_by('-created_at')[:5]
    recent_sms = SMSMessage.objects.filter(school=school).order_by('-created_at')[:5]
    recent_logs = CommunicationLog.objects.filter(school=school).order_by('-created_at')[:5]
    
    # Get counts
    total_templates = CommunicationTemplate.objects.filter(school=school).count()
    total_emails = EmailMessage.objects.filter(school=school).count()
    total_sms = SMSMessage.objects.filter(school=school).count()
    total_logs = CommunicationLog.objects.filter(school=school).count()
    
    context = {
        'recent_emails': recent_emails,
        'recent_sms': recent_sms,
        'recent_logs': recent_logs,
        'total_templates': total_templates,
        'total_emails': total_emails,
        'total_sms': total_sms,
        'total_logs': total_logs,
    }
    return render(request, 'communications/dashboard.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def template_list(request):
    """List communication templates"""
    school = request.user.profile.school
    templates = CommunicationTemplate.objects.filter(school=school).order_by('message_type', 'name')
    
    # Filter by template type
    template_type = request.GET.get('type', '')
    if template_type:
        templates = templates.filter(template_type=template_type)
    
    # Filter by message type
    message_type = request.GET.get('message_type', '')
    if message_type:
        templates = templates.filter(message_type=message_type)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        template_type = request.POST.get('template_type')
        message_type = request.POST.get('message_type')
        subject = request.POST.get('subject', '')
        content = request.POST.get('content')
        
        try:
            CommunicationTemplate.objects.create(
                school=school,
                name=name,
                template_type=template_type,
                message_type=message_type,
                subject=subject,
                content=content,
                created_by=request.user
            )
            messages.success(request, 'Template created successfully.')
            return redirect('communications:template_list')
        except Exception as e:
            messages.error(request, f'Error creating template: {str(e)}')
    
    context = {
        'templates': templates,
        'template_type': template_type,
        'message_type': message_type,
    }
    return render(request, 'communications/template_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def template_detail(request, template_id):
    """Template detail view"""
    school = request.user.profile.school
    template = get_object_or_404(CommunicationTemplate, school=school, id=template_id)
    
    context = {
        'template': template,
    }
    return render(request, 'communications/template_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def template_update(request, template_id):
    """Update template"""
    school = request.user.profile.school
    template = get_object_or_404(CommunicationTemplate, school=school, id=template_id)
    
    if request.method == 'POST':
        template.name = request.POST.get('name')
        template.template_type = request.POST.get('template_type')
        template.message_type = request.POST.get('message_type')
        template.subject = request.POST.get('subject', '')
        template.content = request.POST.get('content')
        template.is_active = request.POST.get('is_active') == 'on'
        
        try:
            template.save()
            messages.success(request, 'Template updated successfully.')
            return redirect('communications:template_detail', template_id=template.id)
        except Exception as e:
            messages.error(request, f'Error updating template: {str(e)}')
    
    context = {
        'template': template,
    }
    return render(request, 'communications/template_form.html', context)


@login_required
@role_required('super_admin', 'school_admin')
def template_delete(request, template_id):
    """Delete template"""
    school = request.user.profile.school
    template = get_object_or_404(CommunicationTemplate, school=school, id=template_id)
    
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted successfully.')
        return redirect('communications:template_list')
    
    context = {
        'template': template,
    }
    return render(request, 'communications/template_confirm_delete.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def email_list(request):
    """List email messages"""
    school = request.user.profile.school
    emails = EmailMessage.objects.filter(school=school).select_related(
        'student', 'template', 'payment', 'payment_reminder'
    ).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        emails = emails.filter(
            Q(recipient_email__icontains=search_query) |
            Q(subject__icontains=search_query) |
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        emails = emails.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(emails, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'communications/email_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def email_detail(request, email_id):
    """Email detail view"""
    school = request.user.profile.school
    email = get_object_or_404(EmailMessage, school=school, id=email_id)
    
    context = {
        'email': email,
    }
    return render(request, 'communications/email_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def sms_list(request):
    """List SMS messages"""
    school = request.user.profile.school
    sms_messages = SMSMessage.objects.filter(school=school).select_related(
        'student', 'template', 'payment', 'payment_reminder'
    ).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        sms_messages = sms_messages.filter(
            Q(recipient_phone__icontains=search_query) |
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        sms_messages = sms_messages.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(sms_messages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'communications/sms_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def sms_detail(request, sms_id):
    """SMS detail view"""
    school = request.user.profile.school
    sms = get_object_or_404(SMSMessage, school=school, id=sms_id)
    
    context = {
        'sms': sms,
    }
    return render(request, 'communications/sms_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def communication_log_list(request):
    """List communication logs"""
    school = request.user.profile.school
    logs = CommunicationLog.objects.filter(school=school).select_related(
        'student', 'template', 'email_message', 'sms_message'
    ).order_by('-created_at')
    
    # Filter by communication type
    comm_type = request.GET.get('type', '')
    if comm_type:
        logs = logs.filter(communication_type=comm_type)
    
    # Pagination
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'comm_type': comm_type,
    }
    return render(request, 'communications/log_list.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def communication_log_detail(request, log_id):
    """Communication log detail view"""
    school = request.user.profile.school
    log = get_object_or_404(CommunicationLog, school=school, id=log_id)
    
    context = {
        'log': log,
    }
    return render(request, 'communications/log_detail.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def send_email(request, student_id):
    """Send custom email to student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, school=school, id=student_id)
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        content = request.POST.get('content')
        template_id = request.POST.get('template')
        
        if not subject or not content:
            messages.error(request, 'Subject and content are required.')
            return redirect('core:student_detail', student_id=student.student_id)
        
        try:
            template = None
            if template_id:
                # Validate template_id is a number
                try:
                    template_id_int = int(template_id)
                    template = CommunicationTemplate.objects.get(school=school, id=template_id_int)
                except (ValueError, CommunicationTemplate.DoesNotExist):
                    # Invalid template_id - ignore it and continue without template
                    pass
            
            # Collect all recipient emails with their corresponding parent objects
            # Use dict to map email to parent for personalization
            email_to_parent = {}  # Maps email -> Parent object (or None for student.parent_email)
            
            # Add student.parent_email if present (no specific parent object)
            if student.parent_email:
                email_to_parent[student.parent_email] = None
            
            # Add emails from all linked Parent objects
            if student.parents.exists():
                for parent in student.parents.all():
                    if parent.email:
                        email_to_parent[parent.email] = parent
                    elif parent.user.email:
                        email_to_parent[parent.user.email] = parent
            
            if not email_to_parent:
                messages.error(request, 'No email address found for this student\'s parent(s). Please ensure the student has a parent email or linked parent account with an email address.')
                return redirect('core:student_detail', student_id=student.student_id)
            
            # Get student's total balance for {amount} placeholder
            from django.db.models import Sum
            from decimal import Decimal
            from core.models import StudentFee
            student_fees = StudentFee.objects.filter(student=student)
            total_charged = student_fees.aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
            total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
            total_balance = total_charged - total_paid
            amount_str = f"KES {total_balance:,.2f}" if total_balance > 0 else ''
            
            # Get earliest due date for {due_date} placeholder
            earliest_due_date = student_fees.filter(is_paid=False).order_by('due_date').first()
            due_date_str = earliest_due_date.due_date.strftime('%Y-%m-%d') if earliest_due_date else ''
            
            # Send email to all recipients with personalized content
            communication_service = CommunicationService()
            success_count = 0
            error_count = 0
            
            for recipient_email, parent_obj in email_to_parent.items():
                try:
                    # Get parent name for this specific recipient
                    if parent_obj:
                        # Use the specific parent's full name
                        parent_name = parent_obj.full_name
                    else:
                        # Fall back to student.parent_name for student.parent_email
                        parent_name = student.parent_name
                        # Try to get from first linked parent if available
                        if student.parents.exists():
                            first_parent = student.parents.first()
                            if first_parent:
                                parent_name = first_parent.full_name
                    
                    # Build context for placeholder replacement per recipient
                    context = {
                        'student_name': student.full_name,
                        'parent_name': parent_name,
                        'school_name': school.name,
                        'amount': amount_str,
                        'due_date': due_date_str,
                        'due_name': due_date_str,  # Alias for due_date
                    }
                    
                    # Replace placeholders in subject and content for this recipient
                    try:
                        # Use format with SafeDict to handle missing placeholders gracefully
                        class SafeDict(dict):
                            def __missing__(self, key):
                                # Return the original placeholder if not found
                                return '{' + key + '}'
                        
                        safe_context = SafeDict(context)
                        personalized_subject = subject.format(**safe_context)
                        personalized_content = content.format(**safe_context)
                    except (KeyError, ValueError) as e:
                        # If format fails, log but continue with original content
                        logger.warning(f'Error replacing placeholders in email to {recipient_email}: {str(e)}')
                        # Try with basic replacements only
                        try:
                            personalized_subject = subject.format(**context)
                            personalized_content = content.format(**context)
                        except Exception:
                            # Keep original if replacement fails
                            personalized_subject = subject
                            personalized_content = content
                    
                    success = communication_service.email_service.send_email(
                        recipient_email=recipient_email,
                        subject=personalized_subject,
                        content=personalized_content,
                        student=student,
                        template=template,
                        sent_by=request.user
                    )
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    logger.error(f'Error sending email to {recipient_email}: {str(e)}')
                    error_count += 1
            
            # Show appropriate messages
            if success_count > 0 and error_count == 0:
                if len(email_to_parent) == 1:
                    messages.success(request, 'Email sent successfully.')
                else:
                    messages.success(request, f'Email sent successfully to {success_count} recipient(s).')
            elif success_count > 0 and error_count > 0:
                messages.warning(request, f'Email sent to {success_count} recipient(s), but failed to send to {error_count} recipient(s).')
            else:
                messages.error(request, 'Failed to send email to all recipients.')
                
        except Exception as e:
            messages.error(request, f'Error sending email: {str(e)}')
    
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['email', 'both'],
        is_active=True
    )
    
    context = {
        'student': student,
        'templates': templates,
    }
    return render(request, 'communications/send_email.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def send_sms(request, student_id):
    """Send custom SMS to student"""
    school = request.user.profile.school
    student = get_object_or_404(Student, school=school, id=student_id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        template_id = request.POST.get('template')
        
        if not content:
            messages.error(request, 'Content is required.')
            return redirect('core:student_detail', student_id=student.student_id)
        
        try:
            template = None
            if template_id:
                # Validate template_id is a number
                try:
                    template_id_int = int(template_id)
                    template = CommunicationTemplate.objects.get(school=school, id=template_id_int)
                except (ValueError, CommunicationTemplate.DoesNotExist):
                    # Invalid template_id - ignore it and continue without template
                    pass
            
            communication_service = CommunicationService()
            success = communication_service.sms_service.send_sms(
                recipient_phone=student.parent_phone,
                content=content,
                student=student,
                template=template,
                sent_by=request.user
            )
            
            if success:
                messages.success(request, 'SMS sent successfully.')
            else:
                messages.error(request, 'Failed to send SMS.')
                
        except Exception as e:
            messages.error(request, f'Error sending SMS: {str(e)}')
    
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['sms', 'both'],
        is_active=True
    )
    
    context = {
        'student': student,
        'templates': templates,
    }
    return render(request, 'communications/send_sms.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def get_template_content(request, template_id):
    """API endpoint to get template content as JSON"""
    school = request.user.profile.school
    try:
        template = CommunicationTemplate.objects.get(school=school, id=template_id)
        return JsonResponse({
            'success': True,
            'subject': template.subject or '',
            'content': template.content or '',
        })
    except CommunicationTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Template not found'
        }, status=404)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def bulk_email(request):
    """Bulk email to multiple students"""
    school = request.user.profile.school
    
    # Get filters from GET parameters
    grade_id = request.GET.get('grade', '')
    class_id = request.GET.get('class', '')
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    
    # Get all students with prefetched parents for efficient template access
    students = Student.objects.filter(school=school).select_related('grade', 'school_class').prefetch_related('parents', 'parents__user')
    
    # Apply filters
    if not show_inactive:
        students = students.filter(is_active=True)
    if grade_id:
        students = students.filter(grade_id=grade_id)
    if class_id:
        students = students.filter(school_class_id=class_id)
    
    # Get grades and classes for filters
    from core.models import Grade, SchoolClass
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    
    # Get templates
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['email', 'both'],
        is_active=True
    )
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        content = request.POST.get('content')
        template_id = request.POST.get('template')
        selected_students = request.POST.getlist('students')
        
        if not subject or not content:
            messages.error(request, 'Subject and content are required.')
        elif not selected_students:
            messages.error(request, 'Please select at least one student.')
        else:
            try:
                template = None
                if template_id:
                    # Validate template_id is a number
                    try:
                        template_id_int = int(template_id)
                        template = CommunicationTemplate.objects.get(school=school, id=template_id_int)
                    except (ValueError, CommunicationTemplate.DoesNotExist):
                        # Invalid template_id - ignore it and continue without template
                        pass
                
                communication_service = CommunicationService()
                success_count = 0
                error_count = 0
                
                # Send email to each selected student
                for student_id in selected_students:
                    try:
                        student = Student.objects.prefetch_related('parents', 'parents__user').get(school=school, id=student_id)
                        
                        # Collect all recipient emails with their corresponding parent objects
                        # Use dict to map email to parent for personalization
                        email_to_parent = {}  # Maps email -> Parent object (or None for student.parent_email)
                        
                        # Add student.parent_email if present (no specific parent object)
                        if student.parent_email:
                            email_to_parent[student.parent_email] = None
                        
                        # Add emails from all linked Parent objects
                        if student.parents.exists():
                            for parent in student.parents.all():
                                if parent.email:
                                    email_to_parent[parent.email] = parent
                                elif parent.user.email:
                                    email_to_parent[parent.user.email] = parent
                        
                        # Get student's total balance for {amount} placeholder
                        from django.db.models import Sum
                        from decimal import Decimal
                        from core.models import StudentFee
                        student_fees = StudentFee.objects.filter(student=student)
                        total_charged = student_fees.aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
                        total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
                        total_balance = total_charged - total_paid
                        amount_str = f"KES {total_balance:,.2f}" if total_balance > 0 else ''
                        
                        # Get earliest due date for {due_date} placeholder
                        earliest_due_date = student_fees.filter(is_paid=False).order_by('due_date').first()
                        due_date_str = earliest_due_date.due_date.strftime('%Y-%m-%d') if earliest_due_date else ''
                        
                        # Send email to all recipients for this student with personalized content
                        if email_to_parent:
                            student_success = True
                            for recipient_email, parent_obj in email_to_parent.items():
                                try:
                                    # Get parent name for this specific recipient
                                    if parent_obj:
                                        # Use the specific parent's full name
                                        parent_name = parent_obj.full_name
                                    else:
                                        # Fall back to student.parent_name for student.parent_email
                                        parent_name = student.parent_name
                                        # Try to get from first linked parent if available
                                        if student.parents.exists():
                                            first_parent = student.parents.first()
                                            if first_parent:
                                                parent_name = first_parent.full_name
                                    
                                    # Build context for placeholder replacement per recipient
                                    student_context = {
                                        'student_name': student.full_name,
                                        'parent_name': parent_name,
                                        'school_name': school.name,
                                        'amount': amount_str,
                                        'due_date': due_date_str,
                                        'due_name': due_date_str,  # Alias for due_date
                                    }
                                    
                                    # Replace placeholders in subject and content for this recipient
                                    try:
                                        # Use format with SafeDict to handle missing placeholders gracefully
                                        class SafeDict(dict):
                                            def __missing__(self, key):
                                                # Return the original placeholder if not found
                                                return '{' + key + '}'
                                        
                                        safe_context = SafeDict(student_context)
                                        personalized_subject = subject.format(**safe_context)
                                        personalized_content = content.format(**safe_context)
                                    except (KeyError, ValueError) as e:
                                        # If format fails, log but continue with original content
                                        logger.warning(f'Error replacing placeholders in bulk email to {recipient_email} for student {student_id}: {str(e)}')
                                        # Try with basic replacements only
                                        try:
                                            personalized_subject = subject.format(**student_context)
                                            personalized_content = content.format(**student_context)
                                        except Exception:
                                            # Keep original if replacement fails
                                            personalized_subject = subject
                                            personalized_content = content
                                    
                                    success = communication_service.email_service.send_email(
                                        recipient_email=recipient_email,
                                        subject=personalized_subject,
                                        content=personalized_content,
                                        student=student,
                                        template=template,
                                        sent_by=request.user
                                    )
                                    if not success:
                                        student_success = False
                                        error_count += 1
                                except Exception as e:
                                    logger.error(f'Error sending bulk email to {recipient_email} for student {student_id}: {str(e)}')
                                    student_success = False
                                    error_count += 1
                            
                            if student_success:
                                success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f'Error sending bulk email to student {student_id}: {str(e)}')
                        error_count += 1
                
                if success_count > 0:
                    messages.success(request, f'Successfully sent {success_count} email(s).')
                if error_count > 0:
                    messages.warning(request, f'Failed to send {error_count} email(s).')
                    
            except Exception as e:
                messages.error(request, f'Error sending bulk emails: {str(e)}')
    
    context = {
        'students': students.order_by('first_name', 'last_name'),
        'grades': grades,
        'classes': classes,
        'templates': templates,
        'selected_grade': grade_id,
        'selected_class': class_id,
        'show_inactive': show_inactive,
    }
    return render(request, 'communications/bulk_email.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def bulk_sms(request):
    """Bulk SMS to multiple students"""
    school = request.user.profile.school
    
    # Get filters from GET parameters
    grade_id = request.GET.get('grade', '')
    class_id = request.GET.get('class', '')
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    
    # Get all students
    students = Student.objects.filter(school=school).select_related('grade', 'school_class')
    
    # Apply filters
    if not show_inactive:
        students = students.filter(is_active=True)
    if grade_id:
        students = students.filter(grade_id=grade_id)
    if class_id:
        students = students.filter(school_class_id=class_id)
    
    # Get grades and classes for filters
    from core.models import Grade, SchoolClass
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    
    # Get templates
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['sms', 'both'],
        is_active=True
    )
    
    if request.method == 'POST':
        content = request.POST.get('content')
        template_id = request.POST.get('template')
        selected_students = request.POST.getlist('students')
        
        if not content:
            messages.error(request, 'Content is required.')
        elif not selected_students:
            messages.error(request, 'Please select at least one student.')
        else:
            try:
                template = None
                if template_id:
                    # Validate template_id is a number
                    try:
                        template_id_int = int(template_id)
                        template = CommunicationTemplate.objects.get(school=school, id=template_id_int)
                    except (ValueError, CommunicationTemplate.DoesNotExist):
                        # Invalid template_id - ignore it and continue without template
                        pass
                
                communication_service = CommunicationService()
                success_count = 0
                error_count = 0
                
                # Send SMS to each selected student
                for student_id in selected_students:
                    try:
                        student = Student.objects.get(school=school, id=student_id)
                        if student.parent_phone:
                            success = communication_service.sms_service.send_sms(
                                recipient_phone=student.parent_phone,
                                content=content,
                                student=student,
                                template=template,
                                sent_by=request.user
                            )
                            if success:
                                success_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f'Error sending bulk SMS to student {student_id}: {str(e)}')
                        error_count += 1
                
                if success_count > 0:
                    messages.success(request, f'Successfully sent {success_count} SMS(s).')
                if error_count > 0:
                    messages.warning(request, f'Failed to send {error_count} SMS(s).')
                    
            except Exception as e:
                messages.error(request, f'Error sending bulk SMS: {str(e)}')
    
    context = {
        'students': students.order_by('first_name', 'last_name'),
        'grades': grades,
        'classes': classes,
        'templates': templates,
        'selected_grade': grade_id,
        'selected_class': class_id,
        'show_inactive': show_inactive,
    }
    return render(request, 'communications/bulk_sms.html', context)
