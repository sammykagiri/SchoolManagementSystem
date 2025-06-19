from django.contrib import admin
from .models import CommunicationTemplate, EmailMessage, SMSMessage, CommunicationLog


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'message_type', 'is_active', 'created_by', 'created_at']
    list_filter = ['template_type', 'message_type', 'is_active', 'created_at']
    search_fields = ['name', 'subject', 'content']
    ordering = ['message_type', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ['recipient_email', 'subject', 'status', 'sent_at', 'student']
    list_filter = ['status', 'sent_at', 'created_at']
    search_fields = ['recipient_email', 'subject', 'student__student_id', 'student__first_name', 'student__last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Email Information', {
            'fields': ('template', 'student', 'recipient_email', 'subject', 'content', 'status')
        }),
        ('Related Records', {
            'fields': ('payment_reminder', 'payment', 'sent_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('sent_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ['recipient_phone', 'status', 'sent_at', 'student', 'twilio_sid']
    list_filter = ['status', 'sent_at', 'delivered_at', 'created_at']
    search_fields = ['recipient_phone', 'student__student_id', 'student__first_name', 'student__last_name', 'twilio_sid']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    fieldsets = (
        ('SMS Information', {
            'fields': ('template', 'student', 'recipient_phone', 'content', 'status')
        }),
        ('Twilio Information', {
            'fields': ('twilio_sid', 'sent_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
        ('Related Records', {
            'fields': ('payment_reminder', 'payment', 'sent_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ['student', 'communication_type', 'template', 'sent_by', 'created_at']
    list_filter = ['communication_type', 'created_at']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Communication Information', {
            'fields': ('student', 'communication_type', 'template', 'sent_by')
        }),
        ('Related Messages', {
            'fields': ('email_message', 'sms_message', 'payment_reminder', 'payment'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
