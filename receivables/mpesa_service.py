import requests
import base64
import json
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import Payment, MpesaPayment
from core.models import StudentFee
import logging

logger = logging.getLogger(__name__)


class MpesaService:
    """Service class for M-Pesa integration"""
    
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.business_shortcode = settings.MPESA_BUSINESS_SHORT_CODE
        self.passkey = settings.MPESA_PASSKEY
        self.environment = settings.MPESA_ENVIRONMENT
        
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
    
    def get_access_token(self):
        """Get M-Pesa access token"""
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
            
            headers = {
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get('access_token')
            
        except Exception as e:
            logger.error(f"Error getting M-Pesa access token: {str(e)}")
            return None
    
    def generate_password(self):
        """Generate M-Pesa API password"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_string = f"{self.business_shortcode}{self.passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode()
            return password, timestamp
        except Exception as e:
            logger.error(f"Error generating M-Pesa password: {str(e)}")
            return None, None
    
    def initiate_stk_push(self, phone_number, amount, reference, student_fee_id):
        """Initiate STK push for payment"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            password, timestamp = self.generate_password()
            if not password:
                return {'success': False, 'message': 'Failed to generate password'}
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Format phone number
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+'):
                phone_number = phone_number[1:]
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{settings.BASE_URL}/receivables/mpesa/callback/",
                "AccountReference": reference,
                "TransactionDesc": f"School Fees - {reference}"
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('ResponseCode') == '0':
                # Create payment record
                student_fee = StudentFee.objects.get(id=student_fee_id)
                payment = Payment.objects.create(
                    student=student_fee.student,
                    student_fee=student_fee,
                    amount=amount,
                    payment_method='mpesa',
                    status='processing',
                    reference_number=reference
                )
                
                # Create M-Pesa payment record
                MpesaPayment.objects.create(
                    payment=payment,
                    phone_number=phone_number,
                    checkout_request_id=data.get('CheckoutRequestID'),
                    merchant_request_id=data.get('MerchantRequestID')
                )
                
                return {
                    'success': True,
                    'message': 'STK push initiated successfully',
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'payment_id': payment.payment_id
                }
            else:
                return {
                    'success': False,
                    'message': data.get('ResponseDescription', 'STK push failed')
                }
                
        except Exception as e:
            logger.error(f"Error initiating STK push: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def process_callback(self, callback_data):
        """Process M-Pesa callback"""
        try:
            result_code = callback_data.get('ResultCode')
            checkout_request_id = callback_data.get('CheckoutRequestID')
            merchant_request_id = callback_data.get('MerchantRequestID')
            
            # Find the M-Pesa payment record
            try:
                mpesa_payment = MpesaPayment.objects.get(
                    checkout_request_id=checkout_request_id
                )
            except MpesaPayment.DoesNotExist:
                logger.error(f"M-Pesa payment not found for checkout_request_id: {checkout_request_id}")
                return False
            
            payment = mpesa_payment.payment
            
            if result_code == '0':
                # Payment successful
                payment.status = 'completed'
                payment.transaction_id = callback_data.get('TransactionID', '')
                
                # Update M-Pesa payment details
                mpesa_payment.result_code = result_code
                mpesa_payment.result_desc = callback_data.get('ResultDesc', '')
                mpesa_payment.mpesa_receipt_number = callback_data.get('MpesaReceiptNumber', '')
                mpesa_payment.transaction_date = timezone.now()
                
                # Update student fee amount paid
                student_fee = payment.student_fee
                student_fee.amount_paid += payment.amount
                if student_fee.amount_paid >= student_fee.amount_charged:
                    student_fee.is_paid = True
                student_fee.save()
                
                payment.save()
                mpesa_payment.save()
                
                logger.info(f"Payment completed successfully: {payment.payment_id}")
                return True
                
            else:
                # Payment failed
                payment.status = 'failed'
                mpesa_payment.result_code = result_code
                mpesa_payment.result_desc = callback_data.get('ResultDesc', '')
                
                payment.save()
                mpesa_payment.save()
                
                logger.warning(f"Payment failed: {payment.payment_id} - {callback_data.get('ResultDesc')}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing M-Pesa callback: {str(e)}")
            return False
    
    def check_transaction_status(self, checkout_request_id):
        """Check transaction status"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'message': 'Failed to get access token'}
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            password, timestamp = self.generate_password()
            if not password:
                return {'success': False, 'message': 'Failed to generate password'}
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'} 