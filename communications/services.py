from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from twilio.rest import Client
from .models import EmailMessage, SMSMessage, CommunicationTemplate, CommunicationLog
from core.models import Student
from payments.models import Payment, PaymentReminder
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service class for email communications"""
    
    def __init__(self):
        self.from_email = settings.EMAIL_HOST_USER
    
    def send_email(self, recipient_email, subject, content, student=None, 
                   template=None, payment_reminder=None, payment=None, sent_by=None):
        """Send email and log it"""
        try:
            # Send email
            send_mail(
                subject=subject,
                message=content,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            
            # Log the email
            email_message = EmailMessage.objects.create(
                template=template,
                student=student,
                recipient_email=recipient_email,
                subject=subject,
                content=content,
                status='sent',
                sent_at=timezone.now(),
                payment_reminder=payment_reminder,
                payment=payment,
                sent_by=sent_by
            )
            
            # Create communication log
            if student:
                CommunicationLog.objects.create(
                    student=student,
                    communication_type='email',
                    template=template,
                    email_message=email_message,
                    payment_reminder=payment_reminder,
                    payment=payment,
                    sent_by=sent_by
                )
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient_email}: {str(e)}")
            
            # Log failed email
            if student:
                EmailMessage.objects.create(
                    template=template,
                    student=student,
                    recipient_email=recipient_email,
                    subject=subject,
                    content=content,
                    status='failed',
                    error_message=str(e),
                    payment_reminder=payment_reminder,
                    payment=payment,
                    sent_by=sent_by
                )
            
            return False
    
    def send_payment_receipt(self, payment):
        """Send payment receipt email"""
        try:
            student = payment.student
            template = CommunicationTemplate.objects.filter(
                message_type='payment_receipt',
                template_type__in=['email', 'both'],
                is_active=True
            ).first()
            
            if not template:
                # Use default template
                subject = f"Payment Receipt - {payment.reference_number}"
                content = f"""
                Dear {student.parent_name},
                
                Thank you for your payment of KES {payment.amount} for {student.full_name}.
                
                Payment Details:
                - Reference: {payment.reference_number}
                - Date: {payment.payment_date.strftime('%Y-%m-%d %H:%M')}
                - Method: {payment.get_payment_method_display()}
                - Fee Category: {payment.student_fee.fee_category.name}
                - Term: {payment.student_fee.term.name}
                
                Best regards,
                School Administration
                """
            else:
                # Use template
                context = {
                    'student': student,
                    'payment': payment,
                    'receipt_number': payment.reference_number,
                    'amount': payment.amount,
                    'payment_date': payment.payment_date,
                    'payment_method': payment.get_payment_method_display(),
                    'fee_category': payment.student_fee.fee_category.name,
                    'term': payment.student_fee.term.name,
                }
                
                subject = template.subject.format(**context)
                content = template.content.format(**context)
            
            return self.send_email(
                recipient_email=student.parent_email,
                subject=subject,
                content=content,
                student=student,
                template=template,
                payment=payment
            )
            
        except Exception as e:
            logger.error(f"Error sending payment receipt email: {str(e)}")
            return False
    
    def send_due_date_reminder(self, student_fee):
        """Send due date reminder email"""
        try:
            student = student_fee.student
            template = CommunicationTemplate.objects.filter(
                message_type='due_date_reminder',
                template_type__in=['email', 'both'],
                is_active=True
            ).first()
            
            if not template:
                # Use default template
                subject = f"Fee Payment Reminder - {student.full_name}"
                content = f"""
                Dear {student.parent_name},
                
                This is a reminder that fees for {student.full_name} are due on {student_fee.due_date.strftime('%Y-%m-%d')}.
                
                Fee Details:
                - Amount Due: KES {student_fee.balance}
                - Fee Category: {student_fee.fee_category.name}
                - Term: {student_fee.term.name}
                - Due Date: {student_fee.due_date.strftime('%Y-%m-%d')}
                
                Please make payment before the due date to avoid any inconveniences.
                
                Best regards,
                School Administration
                """
            else:
                # Use template
                context = {
                    'student': student,
                    'student_fee': student_fee,
                    'balance': student_fee.balance,
                    'due_date': student_fee.due_date,
                    'fee_category': student_fee.fee_category.name,
                    'term': student_fee.term.name,
                }
                
                subject = template.subject.format(**context)
                content = template.content.format(**context)
            
            return self.send_email(
                recipient_email=student.parent_email,
                subject=subject,
                content=content,
                student=student,
                template=template
            )
            
        except Exception as e:
            logger.error(f"Error sending due date reminder email: {str(e)}")
            return False


class SMSService:
    """Service class for SMS communications"""
    
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
    
    def send_sms(self, recipient_phone, content, student=None, 
                 template=None, payment_reminder=None, payment=None, sent_by=None):
        """Send SMS and log it"""
        try:
            # Send SMS
            message = self.client.messages.create(
                body=content,
                from_=self.from_number,
                to=recipient_phone
            )
            
            # Log the SMS
            sms_message = SMSMessage.objects.create(
                template=template,
                student=student,
                recipient_phone=recipient_phone,
                content=content,
                status='sent',
                sent_at=timezone.now(),
                twilio_sid=message.sid,
                payment_reminder=payment_reminder,
                payment=payment,
                sent_by=sent_by
            )
            
            # Create communication log
            if student:
                CommunicationLog.objects.create(
                    student=student,
                    communication_type='sms',
                    template=template,
                    sms_message=sms_message,
                    payment_reminder=payment_reminder,
                    payment=payment,
                    sent_by=sent_by
                )
            
            logger.info(f"SMS sent successfully to {recipient_phone}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS to {recipient_phone}: {str(e)}")
            
            # Log failed SMS
            if student:
                SMSMessage.objects.create(
                    template=template,
                    student=student,
                    recipient_phone=recipient_phone,
                    content=content,
                    status='failed',
                    error_message=str(e),
                    payment_reminder=payment_reminder,
                    payment=payment,
                    sent_by=sent_by
                )
            
            return False
    
    def send_payment_receipt_sms(self, payment):
        """Send payment receipt SMS"""
        try:
            student = payment.student
            template = CommunicationTemplate.objects.filter(
                message_type='payment_receipt',
                template_type__in=['sms', 'both'],
                is_active=True
            ).first()
            
            if not template:
                # Use default template
                content = f"Payment received: KES {payment.amount} for {student.full_name}. Ref: {payment.reference_number}. Thank you!"
            else:
                # Use template
                context = {
                    'student': student,
                    'payment': payment,
                    'receipt_number': payment.reference_number,
                    'amount': payment.amount,
                    'payment_date': payment.payment_date,
                    'payment_method': payment.get_payment_method_display(),
                    'fee_category': payment.student_fee.fee_category.name,
                    'term': payment.student_fee.term.name,
                }
                
                content = template.content.format(**context)
            
            return self.send_sms(
                recipient_phone=student.parent_phone,
                content=content,
                student=student,
                template=template,
                payment=payment
            )
            
        except Exception as e:
            logger.error(f"Error sending payment receipt SMS: {str(e)}")
            return False
    
    def send_due_date_reminder_sms(self, student_fee):
        """Send due date reminder SMS"""
        try:
            student = student_fee.student
            template = CommunicationTemplate.objects.filter(
                message_type='due_date_reminder',
                template_type__in=['sms', 'both'],
                is_active=True
            ).first()
            
            if not template:
                # Use default template
                content = f"Fee reminder: {student.full_name} owes KES {student_fee.balance} due {student_fee.due_date.strftime('%Y-%m-%d')}. Please pay on time."
            else:
                # Use template
                context = {
                    'student': student,
                    'student_fee': student_fee,
                    'balance': student_fee.balance,
                    'due_date': student_fee.due_date,
                    'fee_category': student_fee.fee_category.name,
                    'term': student_fee.term.name,
                }
                
                content = template.content.format(**context)
            
            return self.send_sms(
                recipient_phone=student.parent_phone,
                content=content,
                student=student,
                template=template
            )
            
        except Exception as e:
            logger.error(f"Error sending due date reminder SMS: {str(e)}")
            return False


class CommunicationService:
    """Main communication service that coordinates email and SMS"""
    
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    def send_payment_receipt(self, payment, send_email=True, send_sms=True):
        """Send payment receipt via email and/or SMS"""
        results = {}
        
        if send_email and payment.student.parent_email:
            results['email'] = self.email_service.send_payment_receipt(payment)
        
        if send_sms:
            results['sms'] = self.sms_service.send_payment_receipt_sms(payment)
        
        return results
    
    def send_due_date_reminder(self, student_fee, send_email=True, send_sms=True):
        """Send due date reminder via email and/or SMS"""
        results = {}
        
        if send_email and student_fee.student.parent_email:
            results['email'] = self.email_service.send_due_date_reminder(student_fee)
        
        if send_sms:
            results['sms'] = self.sms_service.send_due_date_reminder_sms(student_fee)
        
        return results
    
    def send_overdue_notice(self, student_fee, send_email=True, send_sms=True):
        """Send overdue payment notice"""
        try:
            student = student_fee.student
            
            # Email
            if send_email and student.parent_email:
                template = CommunicationTemplate.objects.filter(
                    message_type='overdue_notice',
                    template_type__in=['email', 'both'],
                    is_active=True
                ).first()
                
                if template:
                    context = {
                        'student': student,
                        'student_fee': student_fee,
                        'balance': student_fee.balance,
                        'due_date': student_fee.due_date,
                        'days_overdue': (timezone.now().date() - student_fee.due_date).days,
                    }
                    
                    subject = template.subject.format(**context)
                    content = template.content.format(**context)
                else:
                    subject = f"Overdue Payment Notice - {student.full_name}"
                    content = f"""
                    Dear {student.parent_name},
                    
                    This is to notify you that fees for {student.full_name} are overdue.
                    
                    Fee Details:
                    - Amount Overdue: KES {student_fee.balance}
                    - Due Date: {student_fee.due_date.strftime('%Y-%m-%d')}
                    - Days Overdue: {(timezone.now().date() - student_fee.due_date).days}
                    
                    Please make immediate payment to avoid any consequences.
                    
                    Best regards,
                    School Administration
                    """
                
                self.email_service.send_email(
                    recipient_email=student.parent_email,
                    subject=subject,
                    content=content,
                    student=student,
                    template=template
                )
            
            # SMS
            if send_sms:
                template = CommunicationTemplate.objects.filter(
                    message_type='overdue_notice',
                    template_type__in=['sms', 'both'],
                    is_active=True
                ).first()
                
                if template:
                    context = {
                        'student': student,
                        'student_fee': student_fee,
                        'balance': student_fee.balance,
                        'due_date': student_fee.due_date,
                        'days_overdue': (timezone.now().date() - student_fee.due_date).days,
                    }
                    
                    content = template.content.format(**context)
                else:
                    content = f"URGENT: {student.full_name} fees overdue by KES {student_fee.balance}. Due: {student_fee.due_date.strftime('%Y-%m-%d')}. Please pay immediately."
                
                self.sms_service.send_sms(
                    recipient_phone=student.parent_phone,
                    content=content,
                    student=student,
                    template=template
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending overdue notice: {str(e)}")
            return False 