from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from .models import CommunicationTemplate, EmailMessage, SMSMessage, CommunicationLog
from .services import CommunicationService
from core.models import Student, StudentFee, Grade, SchoolClass, TransportRoute
from core.decorators import role_required
from payments.models import Payment
from decimal import Decimal
from datetime import datetime
import json
import logging
import io
import os
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError as e:
    WEASYPRINT_AVAILABLE = False
    logger.warning(f'WeasyPrint import failed: {str(e)}')

logger = logging.getLogger(__name__)


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def communications_list(request):
    """Communications list page showing all communication options"""
    return render(request, 'communications/communications_list.html')


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
    
    # Check if this is a filter POST request (AJAX) vs email send POST
    is_filter_request = request.method == 'POST' and request.POST.get('filter_action') == 'apply'
    # Check for AJAX request - try both headers and META
    # Note: request.headers is Django 2.2+, request.META is more reliable
    x_requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')
    is_ajax = x_requested_with == 'XMLHttpRequest'
    
    # Get filters from POST (filtering) or empty (initial load/refresh)
    # Filters do NOT persist across page reloads - they reset on each fresh page load
    if is_filter_request:
        # Get filters from POST
        grade_ids = request.POST.getlist('grade', [])
        class_ids = request.POST.getlist('class', [])
        route_ids = request.POST.getlist('route', [])
        show_inactive = request.POST.get('show_inactive', 'false').lower() == 'true'
    else:
        # Fresh page load - reset all filters to defaults
        grade_ids = []
        class_ids = []
        route_ids = []
        show_inactive = False
    
    # Get all students with prefetched parents for efficient template access
    students = Student.objects.filter(school=school).select_related('grade', 'school_class', 'transport_route').prefetch_related('parents', 'parents__user')
    
    # Apply filters
    if not show_inactive:
        students = students.filter(is_active=True)
    if grade_ids:
        students = students.filter(grade_id__in=[int(g) for g in grade_ids if g.isdigit()])
    if class_ids:
        students = students.filter(school_class_id__in=[int(c) for c in class_ids if c.isdigit()])
    if route_ids:
        students = students.filter(transport_route_id__in=[int(r) for r in route_ids if r.isdigit()])
    
    # Get grades, classes, and transport routes for filters
    from core.models import Grade, SchoolClass, TransportRoute
    from django.utils import timezone
    from django.db.models import Q
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    today = timezone.now().date()
    routes = TransportRoute.objects.filter(
        school=school,
        is_active=True
    ).filter(
        Q(active_start_date__isnull=True) | Q(active_start_date__lte=today)
    ).filter(
        Q(active_end_date__isnull=True) | Q(active_end_date__gte=today)
    )
    
    # Get templates
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['email', 'both'],
        is_active=True
    )
    
    # Handle email sending POST (not filtering)
    if request.method == 'POST' and not is_filter_request:
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
                                    if success:
                                        success_count += 1  # Count each successful email send
                                    else:
                                        error_count += 1  # Count each failed email send
                                except Exception as e:
                                    logger.error(f'Error sending bulk email to {recipient_email} for student {student_id}: {str(e)}')
                                    error_count += 1  # Count each failed email send
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f'Error sending bulk email to student {student_id}: {str(e)}')
                        error_count += 1
                
                if success_count > 0:
                    if success_count == 1:
                        messages.success(request, 'Successfully sent 1 email.')
                    else:
                        messages.success(request, f'Successfully sent {success_count} emails.')
                if error_count > 0:
                    if error_count == 1:
                        messages.warning(request, 'Failed to send 1 email.')
                    else:
                        messages.warning(request, f'Failed to send {error_count} emails.')
                    
            except Exception as e:
                messages.error(request, f'Error sending bulk emails: {str(e)}')
            # Redirect to avoid resubmission on refresh
            return redirect('communications:bulk_email')
    
    # Prepare context
    context = {
        'students': students.order_by('first_name', 'last_name'),
        'grades': grades,
        'classes': classes,
        'routes': routes,
        'templates': templates,
        'selected_grades': [int(g) for g in grade_ids if g.isdigit()],
        'selected_classes': [int(c) for c in class_ids if c.isdigit()],
        'selected_routes': [int(r) for r in route_ids if r.isdigit()],
        'show_inactive': show_inactive,
    }
    
    # If AJAX filter request, return only the table HTML
    # Check this BEFORE rendering the full template
    if is_filter_request:
        if is_ajax:
            try:
                from django.template.loader import render_to_string
                table_html = render_to_string('communications/partials/bulk_email_table.html', context, request=request)
                return JsonResponse({'table_html': table_html})
            except Exception as e:
                logger.error(f'Error rendering bulk email table: {str(e)}', exc_info=True)
                return JsonResponse({'error': f'Error loading students: {str(e)}'}, status=500)
        else:
            # Filter request but not AJAX - might be a form submission, redirect to avoid duplicate
            logger.warning(f'Filter request without AJAX header - redirecting')
            return redirect('communications:bulk_email')
    
    return render(request, 'communications/bulk_email.html', context)


@login_required
@role_required('super_admin', 'school_admin', 'teacher')
def bulk_sms(request):
    """Bulk SMS to multiple students"""
    school = request.user.profile.school
    
    # Check if this is a filter POST request (AJAX) vs SMS send POST
    is_filter_request = request.method == 'POST' and request.POST.get('filter_action') == 'apply'
    # Check for AJAX request - try both headers and META
    # Note: request.headers is Django 2.2+, request.META is more reliable
    x_requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')
    is_ajax = x_requested_with == 'XMLHttpRequest'
    
    # Get filters from POST (filtering) or empty (initial load/refresh)
    # Filters do NOT persist across page reloads - they reset on each fresh page load
    if is_filter_request:
        # Get filters from POST
        grade_ids = request.POST.getlist('grade', [])
        class_ids = request.POST.getlist('class', [])
        route_ids = request.POST.getlist('route', [])
        show_inactive = request.POST.get('show_inactive', 'false').lower() == 'true'
    else:
        # Fresh page load - reset all filters to defaults
        grade_ids = []
        class_ids = []
        route_ids = []
        show_inactive = False
    
    # Get all students with prefetched parents for efficient template access
    students = Student.objects.filter(school=school).select_related('grade', 'school_class', 'transport_route').prefetch_related('parents', 'parents__user')
    
    # Apply filters
    if not show_inactive:
        students = students.filter(is_active=True)
    if grade_ids:
        students = students.filter(grade_id__in=[int(g) for g in grade_ids if g.isdigit()])
    if class_ids:
        students = students.filter(school_class_id__in=[int(c) for c in class_ids if c.isdigit()])
    if route_ids:
        students = students.filter(transport_route_id__in=[int(r) for r in route_ids if r.isdigit()])
    
    # Get grades, classes, and transport routes for filters
    from core.models import Grade, SchoolClass, TransportRoute
    from django.utils import timezone
    from django.db.models import Q
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    today = timezone.now().date()
    routes = TransportRoute.objects.filter(
        school=school,
        is_active=True
    ).filter(
        Q(active_start_date__isnull=True) | Q(active_start_date__lte=today)
    ).filter(
        Q(active_end_date__isnull=True) | Q(active_end_date__gte=today)
    )
    
    # Get templates
    templates = CommunicationTemplate.objects.filter(
        school=school,
        template_type__in=['sms', 'both'],
        is_active=True
    )
    
    # Handle SMS sending POST (not filtering)
    if request.method == 'POST' and not is_filter_request:
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
                        student = Student.objects.prefetch_related('parents', 'parents__user').get(school=school, id=student_id)
                        
                        # Collect all recipient phone numbers with their corresponding parent objects
                        # Use dict to map phone to parent for personalization
                        phone_to_parent = {}  # Maps phone -> Parent object (or None for student.parent_phone)
                        
                        # Add student.parent_phone if present (no specific parent object)
                        if student.parent_phone:
                            phone_to_parent[student.parent_phone] = None
                        
                        # Add phones from all linked Parent objects
                        if student.parents.exists():
                            for parent in student.parents.all():
                                if parent.phone:
                                    phone_to_parent[parent.phone] = parent
                        
                        # Replace placeholders per student
                        # Get parent name - try from linked parents first, then fall back to student.parent_name
                        parent_name = student.parent_name
                        if student.parents.exists():
                            # Use first parent's full name if available
                            first_parent = student.parents.first()
                            if first_parent:
                                parent_name = first_parent.full_name
                        
                        # Build context for placeholder replacement per student
                        student_context = {
                            'student_name': student.full_name,
                            'parent_name': parent_name,
                            'school_name': school.name,
                        }
                        
                        # Optional placeholders (will be left as-is if not provided)
                        placeholder_defaults = {
                            'amount': '',
                            'due_date': '',
                            'due_name': '',  # Alias for due_date if needed
                        }
                        
                        # Replace placeholders in content for this student
                        try:
                            # Use format with SafeDict to handle missing placeholders gracefully
                            class SafeDict(dict):
                                def __missing__(self, key):
                                    # Return the original placeholder if not found
                                    return '{' + key + '}'
                            
                            safe_context = SafeDict({**student_context, **placeholder_defaults})
                            personalized_content = content.format(**safe_context)
                        except (KeyError, ValueError) as e:
                            # If format fails, log but continue with original content
                            logger.warning(f'Error replacing placeholders in bulk SMS for student {student_id}: {str(e)}')
                            # Try with basic replacements only
                            try:
                                personalized_content = content.format(**student_context)
                            except Exception:
                                # Keep original if replacement fails
                                personalized_content = content
                        
                        # Send SMS to all recipients for this student
                        if phone_to_parent:
                            for recipient_phone, parent_obj in phone_to_parent.items():
                                try:
                                    success = communication_service.sms_service.send_sms(
                                        recipient_phone=recipient_phone,
                                        content=personalized_content,
                                        student=student,
                                        template=template,
                                        sent_by=request.user
                                    )
                                    if success:
                                        success_count += 1  # Count each successful SMS send
                                    else:
                                        error_count += 1  # Count each failed SMS send
                                except Exception as e:
                                    logger.error(f'Error sending bulk SMS to {recipient_phone} for student {student_id}: {str(e)}')
                                    error_count += 1  # Count each failed SMS send
                        else:
                            error_count += 1
                    except Exception as e:
                        logger.error(f'Error sending bulk SMS to student {student_id}: {str(e)}')
                        error_count += 1
                
                if success_count > 0:
                    if success_count == 1:
                        messages.success(request, 'Successfully sent 1 SMS.')
                    else:
                        messages.success(request, f'Successfully sent {success_count} SMS.')
                if error_count > 0:
                    if error_count == 1:
                        messages.warning(request, 'Failed to send 1 SMS.')
                    else:
                        messages.warning(request, f'Failed to send {error_count} SMS.')
                    
            except Exception as e:
                messages.error(request, f'Error sending bulk SMS: {str(e)}')
            # Redirect to avoid resubmission on refresh
            return redirect('communications:bulk_sms')
    
    # Prepare context
    context = {
        'students': students.order_by('first_name', 'last_name'),
        'grades': grades,
        'classes': classes,
        'routes': routes,
        'templates': templates,
        'selected_grades': [int(g) for g in grade_ids if g.isdigit()],
        'selected_classes': [int(c) for c in class_ids if c.isdigit()],
        'selected_routes': [int(r) for r in route_ids if r.isdigit()],
        'show_inactive': show_inactive,
    }
    
    # If AJAX filter request, return only the table HTML
    # Check this BEFORE rendering the full template
    if is_filter_request:
        if is_ajax:
            try:
                from django.template.loader import render_to_string
                table_html = render_to_string('communications/partials/bulk_sms_table.html', context, request=request)
                return JsonResponse({'table_html': table_html})
            except Exception as e:
                logger.error(f'Error rendering bulk SMS table: {str(e)}', exc_info=True)
                return JsonResponse({'error': f'Error loading students: {str(e)}'}, status=500)
        else:
            # Filter request but not AJAX - might be a form submission, redirect to avoid duplicate
            logger.warning(f'Filter request without AJAX header - redirecting')
            return redirect('communications:bulk_sms')
    
    return render(request, 'communications/bulk_sms.html', context)


def generate_student_statement_pdf(student, school, start_date=None, end_date=None, encrypt=False, password=None):
    """Generate PDF statement for a student"""
    if not WEASYPRINT_AVAILABLE:
        raise ImportError("WeasyPrint is not installed. Please install it using: pip install weasyprint. You may also need to install system dependencies. See: https://weasyprint.org/install/")
    
    # Get all student fees (debits)
    student_fees = StudentFee.objects.filter(
        school=school,
        student=student
    ).select_related('term', 'fee_category').order_by('term__academic_year', 'term__term_number', 'fee_category__name')
    
    # Get all payments (credits)
    payments = Payment.objects.filter(
        school=school,
        student=student,
        status='completed'
    ).select_related('student_fee__term', 'student_fee__fee_category').order_by('payment_date')
    
    # Calculate opening balance
    # Use due_date for fees to match the transaction date filtering
    opening_balance = Decimal('0.00')
    if start_date:
        opening_fees = StudentFee.objects.filter(
            school=school,
            student=student,
            due_date__lt=start_date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')
        
        opening_payments = Payment.objects.filter(
            school=school,
            student=student,
            status='completed',
            payment_date__date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        opening_balance = opening_fees - opening_payments
    
    # Filter by date range if provided
    transactions = []
    
    # Add fee transactions (debits)
    # Use due_date for filtering as it represents when the fee is due/charged
    for fee in student_fees:
        fee_date = fee.due_date
        if start_date and fee_date < start_date:
            continue
        if end_date and fee_date > end_date:
            continue
        
        transactions.append({
            'date': fee_date,
            'description': f"{fee.fee_category.name} - {fee.term.academic_year} Term {fee.term.term_number}",
            'reference': f"Fee-{fee.id}",
            'debit': fee.amount_charged,
            'credit': Decimal('0.00'),
            'type': 'fee'
        })
    
    # Add payment transactions (credits)
    for payment in payments:
        payment_date = payment.payment_date.date()
        if start_date and payment_date < start_date:
            continue
        if end_date and payment_date > end_date:
            continue
        
        transactions.append({
            'date': payment_date,
            'description': f"Payment - {payment.student_fee.fee_category.name}",
            'reference': payment.reference_number or str(payment.payment_id),
            'debit': Decimal('0.00'),
            'credit': payment.amount,
            'type': 'payment',
            'payment_method': payment.get_payment_method_display()
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = opening_balance
    for transaction in transactions:
        running_balance += transaction['debit'] - transaction['credit']
        transaction['balance'] = running_balance
    
    # Calculate totals
    total_debits = sum(t['debit'] for t in transactions)
    total_credits = sum(t['credit'] for t in transactions)
    closing_balance = opening_balance + total_debits - total_credits
    
    context = {
        'student': student,
        'school': school,
        'transactions': transactions,
        'opening_balance': opening_balance,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'closing_balance': closing_balance,
        'closing_balance_abs': abs(closing_balance),
        'start_date': start_date,
        'end_date': end_date,
        'statement_date': timezone.now().date(),
    }
    
    # Render HTML template
    html_string = render_to_string('core/student_statement_pdf.html', context)
    
    # Generate PDF
    html = HTML(string=html_string, base_url=os.path.dirname(__file__))
    pdf_bytes = html.write_pdf()
    
    # Apply encryption if requested
    if encrypt and password:
        try:
            from pypdf import PdfWriter, PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfWriter, PdfReader
            except ImportError:
                raise ImportError("pypdf or PyPDF2 is required for PDF encryption. Install with: pip install pypdf")
        
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        pdf_writer = PdfWriter()
        
        for page in pdf_reader.pages:
            pdf_writer.add_page(page)
        
        pdf_writer.encrypt(password)
        output_buffer = io.BytesIO()
        pdf_writer.write(output_buffer)
        pdf_bytes = output_buffer.getvalue()
    
    return pdf_bytes


@login_required
@role_required('super_admin', 'school_admin', 'teacher', 'accountant')
def bulk_estatement_email(request):
    """Bulk email e-statements (PDF) to multiple students"""
    school = request.user.profile.school
    
    if not WEASYPRINT_AVAILABLE:
        messages.error(request, 'WeasyPrint is not installed. Please install it using: pip install weasyprint')
        # Still render the page so user can see the error message
        today = timezone.now().date()
        grades = Grade.objects.filter(school=school)
        classes = SchoolClass.objects.filter(school=school, is_active=True)
        routes = TransportRoute.objects.filter(
            school=school,
            is_active=True
        ).filter(
            Q(active_start_date__isnull=True) | Q(active_start_date__lte=today)
        ).filter(
            Q(active_end_date__isnull=True) | Q(active_end_date__gte=today)
        )
        context = {
            'students': [],
            'grades': grades,
            'classes': classes,
            'routes': routes,
            'selected_grades': [],
            'selected_classes': [],
            'selected_routes': [],
            'show_inactive': False,
            'start_date': '',
            'end_date': '',
        }
        return render(request, 'communications/bulk_estatement_email.html', context)
    
    school = request.user.profile.school
    
    # Check if this is a filter POST request (AJAX) vs email send POST
    is_filter_request = request.method == 'POST' and request.POST.get('filter_action') == 'apply'
    x_requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')
    is_ajax = x_requested_with == 'XMLHttpRequest'
    
    # Get filters from POST (filtering) or empty (initial load/refresh)
    if is_filter_request:
        grade_ids = request.POST.getlist('grade', [])
        class_ids = request.POST.getlist('class', [])
        route_ids = request.POST.getlist('route', [])
        show_inactive = request.POST.get('show_inactive', 'false').lower() == 'true'
        start_date_str = request.POST.get('start_date', '')
        end_date_str = request.POST.get('end_date', '')
    else:
        grade_ids = []
        class_ids = []
        route_ids = []
        show_inactive = False
        start_date_str = ''
        end_date_str = ''
    
    # Parse date range
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Get all students with prefetched parents
    students = Student.objects.filter(school=school).select_related('grade', 'school_class', 'transport_route').prefetch_related('parents', 'parents__user')
    
    # Apply filters
    if not show_inactive:
        students = students.filter(is_active=True)
    if grade_ids:
        students = students.filter(grade_id__in=[int(g) for g in grade_ids if g.isdigit()])
    if class_ids:
        students = students.filter(school_class_id__in=[int(c) for c in class_ids if c.isdigit()])
    if route_ids:
        students = students.filter(transport_route_id__in=[int(r) for r in route_ids if r.isdigit()])
    
    # Get grades, classes, and transport routes for filters
    grades = Grade.objects.filter(school=school)
    classes = SchoolClass.objects.filter(school=school, is_active=True)
    today = timezone.now().date()
    routes = TransportRoute.objects.filter(
        school=school,
        is_active=True
    ).filter(
        Q(active_start_date__isnull=True) | Q(active_start_date__lte=today)
    ).filter(
        Q(active_end_date__isnull=True) | Q(active_end_date__gte=today)
    )
    
    # Handle email sending POST (not filtering)
    if request.method == 'POST' and not is_filter_request:
        selected_student_ids = request.POST.getlist('selected_students', [])
        encrypt_pdf = request.POST.get('encrypt_pdf', 'false').lower() == 'true'
        pdf_password = request.POST.get('pdf_password', '')
        email_subject = request.POST.get('subject', 'Fee Statement')
        email_content = request.POST.get('content', 'Please find attached your fee statement.')
        
        if not selected_student_ids:
            messages.error(request, 'Please select at least one student.')
        else:
            try:
                communication_service = CommunicationService()
                success_count = 0
                error_count = 0
                
                skipped_count = 0
                skipped_students = []
                
                for student_id in selected_student_ids:
                    try:
                        student = Student.objects.get(school=school, id=int(student_id))
                        
                        # Check if there are any transactions in the date range before generating PDF
                        fee_count = 0
                        payment_count = 0
                        
                        if start_date or end_date:
                            # Filter by date range
                            fee_query = StudentFee.objects.filter(school=school, student=student)
                            if start_date:
                                fee_query = fee_query.filter(due_date__gte=start_date)
                            if end_date:
                                fee_query = fee_query.filter(due_date__lte=end_date)
                            fee_count = fee_query.count()
                            
                            payment_query = Payment.objects.filter(
                                school=school,
                                student=student,
                                status='completed'
                            )
                            if start_date:
                                payment_query = payment_query.filter(payment_date__date__gte=start_date)
                            if end_date:
                                payment_query = payment_query.filter(payment_date__date__lte=end_date)
                            payment_count = payment_query.count()
                        else:
                            # No date filter - check if student has any fees/payments at all
                            fee_count = StudentFee.objects.filter(school=school, student=student).count()
                            payment_count = Payment.objects.filter(
                                school=school,
                                student=student,
                                status='completed'
                            ).count()
                        
                        # Skip if no transactions in date range
                        if fee_count == 0 and payment_count == 0:
                            skipped_count += 1
                            skipped_students.append(student.full_name)
                            continue
                        
                        # Generate PDF
                        pdf_bytes = generate_student_statement_pdf(
                            student=student,
                            school=school,
                            start_date=start_date,
                            end_date=end_date,
                            encrypt=encrypt_pdf,
                            password=pdf_password if encrypt_pdf else None
                        )
                        
                        # Get recipient emails
                        email_to_parent = {}
                        if student.parent_email:
                            email_to_parent[student.parent_email] = student.parent_email
                        
                        for parent in student.parents.all():
                            parent_email = parent.email or (parent.user.email if parent.user else None)
                            if parent_email:
                                email_to_parent[parent_email] = parent_email
                        
                        if not email_to_parent:
                            error_count += 1
                            continue
                        
                        # Send email with PDF attachment
                        for recipient_email in email_to_parent.values():
                            try:
                                from django.core.mail import EmailMessage as DjangoEmailMessage
                                from django.conf import settings
                                
                                email_msg = DjangoEmailMessage(
                                    subject=email_subject,
                                    body=email_content,
                                    from_email=settings.EMAIL_HOST_USER,
                                    to=[recipient_email]
                                )
                                
                                # Attach PDF
                                filename = f"Statement_{student.student_id}_{timezone.now().strftime('%Y%m%d')}.pdf"
                                email_msg.attach(filename, pdf_bytes, 'application/pdf')
                                
                                email_msg.send()
                                
                                # Log the email
                                EmailMessage.objects.create(
                                    school=school,
                                    student=student,
                                    recipient_email=recipient_email,
                                    subject=email_subject,
                                    content=email_content,
                                    status='sent',
                                    sent_by=request.user
                                )
                                
                                success_count += 1
                            except Exception as e:
                                logger.error(f'Error sending e-statement email to {recipient_email}: {str(e)}')
                                error_count += 1
                    except Exception as e:
                        logger.error(f'Error processing student {student_id}: {str(e)}')
                        error_count += 1
                
                if success_count > 0:
                    if success_count == 1:
                        messages.success(request, 'Successfully sent 1 e-statement.')
                    else:
                        messages.success(request, f'Successfully sent {success_count} e-statements.')
                if skipped_count > 0:
                    if skipped_count == 1:
                        messages.warning(request, f'Skipped 1 student (no transactions in selected date range): {skipped_students[0]}.')
                    else:
                        students_list = ', '.join(skipped_students[:5])
                        if len(skipped_students) > 5:
                            students_list += f' and {len(skipped_students) - 5} more'
                        messages.warning(request, f'Skipped {skipped_count} student(s) with no transactions in selected date range: {students_list}.')
                if error_count > 0:
                    if error_count == 1:
                        messages.warning(request, 'Failed to send 1 e-statement.')
                    else:
                        messages.warning(request, f'Failed to send {error_count} e-statements.')
            except Exception as e:
                messages.error(request, f'Error sending bulk e-statements: {str(e)}')
            return redirect('communications:bulk_estatement_email')
    
    # Prepare context
    context = {
        'students': students.order_by('first_name', 'last_name'),
        'grades': grades,
        'classes': classes,
        'routes': routes,
        'selected_grades': [int(g) for g in grade_ids if g.isdigit()],
        'selected_classes': [int(c) for c in class_ids if c.isdigit()],
        'selected_routes': [int(r) for r in route_ids if r.isdigit()],
        'show_inactive': show_inactive,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    
    # If AJAX filter request, return only the table HTML
    if is_filter_request:
        if is_ajax:
            try:
                table_html = render_to_string('communications/partials/bulk_estatement_table.html', context, request=request)
                return JsonResponse({'table_html': table_html})
            except Exception as e:
                logger.error(f'Error rendering bulk e-statement table: {str(e)}', exc_info=True)
                return JsonResponse({'error': f'Error loading students: {str(e)}'}, status=500)
        else:
            return redirect('communications:bulk_estatement_email')
    
    return render(request, 'communications/bulk_estatement_email.html', context)
