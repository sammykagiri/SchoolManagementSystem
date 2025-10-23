from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CommunicationTemplate, EmailMessage, SMSMessage, CommunicationLog
from .services import CommunicationService
from core.models import Student
import json


@login_required
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
def template_detail(request, template_id):
    """Template detail view"""
    school = request.user.profile.school
    template = get_object_or_404(CommunicationTemplate, school=school, id=template_id)
    
    context = {
        'template': template,
    }
    return render(request, 'communications/template_detail.html', context)


@login_required
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
def email_detail(request, email_id):
    """Email detail view"""
    school = request.user.profile.school
    email = get_object_or_404(EmailMessage, school=school, id=email_id)
    
    context = {
        'email': email,
    }
    return render(request, 'communications/email_detail.html', context)


@login_required
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
def sms_detail(request, sms_id):
    """SMS detail view"""
    school = request.user.profile.school
    sms = get_object_or_404(SMSMessage, school=school, id=sms_id)
    
    context = {
        'sms': sms,
    }
    return render(request, 'communications/sms_detail.html', context)


@login_required
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
def communication_log_detail(request, log_id):
    """Communication log detail view"""
    school = request.user.profile.school
    log = get_object_or_404(CommunicationLog, school=school, id=log_id)
    
    context = {
        'log': log,
    }
    return render(request, 'communications/log_detail.html', context)


@login_required
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
                template = CommunicationTemplate.objects.get(school=school, id=template_id)
            
            communication_service = CommunicationService()
            success = communication_service.email_service.send_email(
                recipient_email=student.parent_email,
                subject=subject,
                content=content,
                student=student,
                template=template,
                sent_by=request.user
            )
            
            if success:
                messages.success(request, 'Email sent successfully.')
            else:
                messages.error(request, 'Failed to send email.')
                
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
                template = CommunicationTemplate.objects.get(school=school, id=template_id)
            
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
