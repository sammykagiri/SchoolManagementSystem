"""
Verification service for parent phone/email updates
"""
import random
import string
from django.utils import timezone
from datetime import timedelta
from .models import ParentVerification
import logging

logger = logging.getLogger(__name__)


class VerificationService:
    """Service for generating and verifying OTP codes"""
    
    @staticmethod
    def generate_code(length=6):
        """Generate a random verification code"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def create_verification(parent, verification_type, new_value):
        """
        Create a verification code for phone or email update
        
        Args:
            parent: Parent instance
            verification_type: 'phone' or 'email'
            new_value: New phone number or email address
        
        Returns:
            ParentVerification instance
        """
        # Invalidate any existing unverified codes for this parent and type
        ParentVerification.objects.filter(
            parent=parent,
            verification_type=verification_type,
            is_verified=False
        ).update(is_verified=True)  # Mark as used
        
        # Generate new code
        code = VerificationService.generate_code()
        
        # Create verification record (expires in 15 minutes)
        verification = ParentVerification.objects.create(
            parent=parent,
            verification_type=verification_type,
            verification_code=code,
            new_value=new_value,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        return verification
    
    @staticmethod
    def send_verification_code(verification):
        """
        Send verification code via SMS or Email
        
        Args:
            verification: ParentVerification instance
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if verification.verification_type == 'phone':
                # TODO: Integrate SMS service (e.g., Africa's Talking, Twilio)
                # For now, just log it
                logger.info(f'SMS verification code for {verification.parent.full_name}: {verification.verification_code}')
                # In production, you would send SMS here
                # Example: sms_service.send(verification.new_value, f'Your verification code is: {verification.verification_code}')
                return True
                
            elif verification.verification_type == 'email':
                # Send email verification
                from django.core.mail import send_mail
                from django.conf import settings
                
                subject = 'Email Verification - Eduvanta'
                message = f'''
Hello {verification.parent.full_name},

You have requested to update your email address to: {verification.new_value}

Your verification code is: {verification.verification_code}

This code will expire in 15 minutes.

If you did not request this change, please ignore this email.

Best regards,
Eduvanta
                '''
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [verification.new_value],
                    fail_silently=False,
                )
                
                logger.info(f'Email verification sent to {verification.new_value}')
                return True
                
        except Exception as e:
            logger.error(f'Error sending verification code: {str(e)}')
            return False
    
    @staticmethod
    def verify_code(parent, verification_type, code):
        """
        Verify a code and update parent's phone/email if valid
        
        Args:
            parent: Parent instance
            verification_type: 'phone' or 'email'
            code: Verification code
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            verification = ParentVerification.objects.get(
                parent=parent,
                verification_type=verification_type,
                verification_code=code,
                is_verified=False
            )
            
            # Check if expired
            if verification.is_expired():
                return False, 'Verification code has expired. Please request a new one.'
            
            # Verify the code
            verification.is_verified = True
            verification.verified_at = timezone.now()
            verification.save()
            
            # Update parent's phone or email
            if verification_type == 'phone':
                parent.phone = verification.new_value
                parent.save()
                return True, 'Phone number updated successfully.'
            elif verification_type == 'email':
                parent.email = verification.new_value
                parent.user.email = verification.new_value
                parent.user.save()
                parent.save()
                return True, 'Email address updated successfully.'
                
        except ParentVerification.DoesNotExist:
            return False, 'Invalid verification code.'
        except Exception as e:
            logger.error(f'Error verifying code: {str(e)}')
            return False, 'An error occurred during verification.'



