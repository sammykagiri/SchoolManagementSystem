from django.db import models
from django.contrib.auth.models import User
from core.models import School, Student
from payments.models import Payment, PaymentReminder
from django.core.validators import MinValueValidator


class CommunicationTemplate(models.Model):
    """Model for communication templates"""
    TEMPLATE_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('both', 'Both'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('payment_receipt', 'Payment Receipt'),
        ('due_date_reminder', 'Due Date Reminder'),
        ('overdue_notice', 'Overdue Notice'),
        ('partial_payment', 'Partial Payment'),
        ('welcome', 'Welcome Message'),
        ('general', 'General Communication'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='communication_templates')
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=10, choices=TEMPLATE_TYPE_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)
    subject = models.CharField(max_length=200, blank=True)  # For emails
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.get_template_type_display()}"

    class Meta:
        ordering = ['message_type', 'name']
        unique_together = ['school', 'name', 'message_type', 'template_type']


class EmailMessage(models.Model):
    """Model for email message logs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='email_messages')
    template = models.ForeignKey(CommunicationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='email_messages')
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    payment_reminder = models.ForeignKey(PaymentReminder, on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.recipient_email} - {self.status}"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['school', 'recipient_email', 'subject', 'created_at']


class SMSMessage(models.Model):
    """Model for SMS message logs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sms_messages')
    template = models.ForeignKey(CommunicationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='sms_messages')
    recipient_phone = models.CharField(max_length=15)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    twilio_sid = models.CharField(max_length=100, blank=True)
    payment_reminder = models.ForeignKey(PaymentReminder, on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.status}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "SMS Message"
        verbose_name_plural = "SMS Messages"
        unique_together = ['school', 'recipient_phone', 'content', 'created_at']


class CommunicationLog(models.Model):
    """Model for general communication logs"""
    COMMUNICATION_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('both', 'Both'),
    ]
    
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='communication_logs')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='communication_logs')
    communication_type = models.CharField(max_length=10, choices=COMMUNICATION_TYPE_CHOICES)
    template = models.ForeignKey(CommunicationTemplate, on_delete=models.SET_NULL, null=True)
    email_message = models.ForeignKey(EmailMessage, on_delete=models.SET_NULL, null=True, blank=True)
    sms_message = models.ForeignKey(SMSMessage, on_delete=models.SET_NULL, null=True, blank=True)
    payment_reminder = models.ForeignKey(PaymentReminder, on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.communication_type} - {self.student} - {self.created_at.date()}"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['school', 'student', 'communication_type', 'created_at']
