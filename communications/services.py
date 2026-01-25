from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
import requests
import re
from .models import EmailMessage, SMSMessage, CommunicationTemplate, CommunicationLog
from core.models import Student
from receivables.models import Payment, PaymentReminder
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
            # Validate email settings before attempting to send
            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                error_msg = "Email settings are not configured. Please set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in your environment variables."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not self.from_email:
                error_msg = "From email address is not configured. Please set EMAIL_HOST_USER in your environment variables."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not recipient_email:
                error_msg = "Recipient email address is required."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Send email and check return value (number of messages sent)
            result = send_mail(
                subject=subject,
                message=content,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            
            # send_mail returns the number of messages successfully sent
            # If it's 0 or None, the email was not sent
            if not result or result == 0:
                error_msg = f"Email send_mail returned {result}, indicating no messages were sent."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Log the email
            # Get school from student if available, otherwise from template
            school = None
            if student:
                school = student.school
            elif template:
                school = template.school
            
            if not school:
                raise ValueError("School is required. Either student or template must be provided.")
            
            email_message = EmailMessage.objects.create(
                school=school,
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
                    school=school,
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
                # Get school from student if available, otherwise from template
                school = student.school if student else (template.school if template else None)
                if school:
                    EmailMessage.objects.create(
                        school=school,
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
    """Service class for SMS communications using Celcom Africa"""
    
    def __init__(self):
        self.api_url = settings.CELCOM_URL_SENDSMS
        self.api_key = settings.CELCOM_API_KEY
        self.partner_id = settings.CELCOM_PARTNER_ID
        self.shortcode = settings.CELCOM_SHORTCODE
        
        # Celcom Africa API return codes and descriptions
        self.api_codes = {
            200: "Successful Request Call",
            1001: "Invalid sender id",
            1002: "Network not allowed",
            1003: "Invalid mobile number",
            1004: "Low bulk credits",
            1005: "Failed. System error",
            1006: "Invalid credentials",
            1007: "Failed. System error",
            1008: "No Delivery Report",
            1009: "unsupported data type",
            1010: "unsupported request type",
            4090: "Internal Error. Try again after 5 minutes",
            4091: "No Partner ID is Set",
            4092: "No API KEY Provided",
            4093: "Details Not Found"
        }
    
    def validate_phone_number(self, phone_number):
        """
        Validate and format phone number for Celcom Africa (expected: 254xxxxxxxxxx)
        """
        # Remove any whitespace or special characters
        phone_number = re.sub(r'\D', '', phone_number)
        
        # Check if it starts with + or 0, and convert to 254 format
        if phone_number.startswith('254'):
            pass  # Already in correct format
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]  # Remove the +
        elif phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            return None  # Unsupported country code
        else:
            # Assume it's a Kenyan number without prefix
            phone_number = '254' + phone_number

        # Validate length and format (should be 12 digits: 254xxxxxxxxxx)
        if not re.match(r'^254\d{9}$', phone_number):
            return None
        
        return phone_number
    
    def send_sms(self, recipient_phone, content, student=None, 
                 template=None, payment_reminder=None, payment=None, sent_by=None):
        """Send SMS and log it"""
        try:
            # Validate and format phone number
            formatted_phone = self.validate_phone_number(recipient_phone)
            if not formatted_phone:
                error_msg = f"Invalid phone number format: {recipient_phone}"
                logger.error(error_msg)
                
                # Log failed SMS
                if student:
                    # Get school from student if available, otherwise from template
                    school = student.school if student else (template.school if template else None)
                    if school:
                        SMSMessage.objects.create(
                            school=school,
                            template=template,
                            student=student,
                            recipient_phone=recipient_phone,
                            content=content,
                            status='failed',
                            error_message=error_msg,
                            payment_reminder=payment_reminder,
                            payment=payment,
                            sent_by=sent_by
                        )
                return False
            
            # Construct the JSON payload for Celcom Africa
            payload = {
                "partnerID": str(self.partner_id),
                "apikey": self.api_key,
                "mobile": formatted_phone,
                "message": content,
                "shortcode": self.shortcode,
                "pass_type": "plain"
            }

            headers = {
                "Content-Type": "application/json"
            }

            # Send the POST request to Celcom Africa
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()

            # Parse the JSON response
            result = response.json()
            logger.info(f"Celcom Africa API response: {result}")

            # Check if the SMS was sent successfully
            if result.get("responses"):
                recipient = result["responses"][0]
                response_code = recipient.get("respose-code") or recipient.get("response-code")
                response_description = recipient.get("response-description", "Unknown")
                message_id = recipient.get("messageid")

                # Update SMS tracker
                if response_code == 200 or (response_code is None and response_description.lower() == "success"):
                    # Get school from student if available, otherwise from template
                    school = student.school if student else (template.school if template else None)
                    if not school and student:
                        raise ValueError("School is required. Student must have a school assigned.")
                    
                    # Log the SMS
                    sms_message = SMSMessage.objects.create(
                        school=school,
                        template=template,
                        student=student,
                        recipient_phone=formatted_phone,
                        content=content,
                        status='sent',
                        sent_at=timezone.now(),
                        twilio_sid=message_id,  # Using twilio_sid field to store Celcom message ID
                        payment_reminder=payment_reminder,
                        payment=payment,
                        sent_by=sent_by
                    )
                    
                    # Create communication log
                    if student and school:
                        CommunicationLog.objects.create(
                            school=school,
                            student=student,
                            communication_type='sms',
                            template=template,
                            sms_message=sms_message,
                            payment_reminder=payment_reminder,
                            payment=payment,
                            sent_by=sent_by
                        )
                    
                    logger.info(f"SMS sent successfully to {formatted_phone}, Message ID: {message_id}")
                    return True
                else:
                    error_message = self.api_codes.get(response_code, response_description)
                    logger.error(f"SMS failed with response code {response_code}: {error_message}")
                    
                    # Log failed SMS
                    if student:
                        # Get school from student if available, otherwise from template
                        school = student.school if student else (template.school if template else None)
                        if school:
                            SMSMessage.objects.create(
                                school=school,
                                template=template,
                                student=student,
                                recipient_phone=formatted_phone,
                                content=content,
                                status='failed',
                                error_message=error_message,
                                payment_reminder=payment_reminder,
                                payment=payment,
                                sent_by=sent_by
                            )
                    return False
            
            # No recipient data in response
            error_msg = "No recipient data in response"
            logger.error(error_msg)
            
            # Log failed SMS
            if student:
                # Get school from student if available, otherwise from template
                school = student.school if student else (template.school if template else None)
                if school:
                    SMSMessage.objects.create(
                        school=school,
                        template=template,
                        student=student,
                        recipient_phone=formatted_phone,
                        content=content,
                        status='failed',
                        error_message=error_msg,
                        payment_reminder=payment_reminder,
                        payment=payment,
                        sent_by=sent_by
                    )
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending SMS to {recipient_phone}: {str(e)}")
            
            # Log failed SMS
            if student:
                # Get school from student if available, otherwise from template
                school = student.school if student else (template.school if template else None)
                if school:
                    SMSMessage.objects.create(
                        school=school,
                        template=template,
                        student=student,
                        recipient_phone=recipient_phone,
                        content=content,
                        status='failed',
                        error_message=f"Network error: {str(e)}",
                        payment_reminder=payment_reminder,
                        payment=payment,
                        sent_by=sent_by
                    )
            return False
            
        except Exception as e:
            logger.error(f"Error sending SMS to {recipient_phone}: {str(e)}")
            
            # Log failed SMS
            if student:
                # Get school from student if available, otherwise from template
                school = student.school if student else (template.school if template else None)
                if school:
                    SMSMessage.objects.create(
                        school=school,
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