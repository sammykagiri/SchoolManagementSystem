"""
M-Pesa Express (STK Push) API Integration Service
"""
import requests
import base64
import json
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class MpesaService:
    """Service for M-Pesa Express (STK Push) payments"""
    
    def __init__(self):
        # M-Pesa API credentials (should be in settings)
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.passkey = getattr(settings, 'MPESA_PASSKEY', '')
        self.shortcode = getattr(settings, 'MPESA_SHORTCODE', '')
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        self.environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox')  # 'sandbox' or 'production'
        
        # API endpoints
        if self.environment == 'production':
            self.base_url = 'https://api.safaricom.co.ke'
        else:
            self.base_url = 'https://sandbox.safaricom.co.ke'
        
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self):
        """Get OAuth access token from M-Pesa API"""
        # Check if we have a valid token
        if self.access_token and self.token_expires_at and timezone.now() < self.token_expires_at:
            return self.access_token
        
        try:
            url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
            
            # Encode credentials
            credentials = f'{self.consumer_key}:{self.consumer_secret}'
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data.get('access_token')
            
            # Token expires in 3599 seconds (set expiry 5 minutes before actual expiry)
            expires_in = data.get('expires_in', 3599) - 300
            self.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
            
            logger.info('M-Pesa access token obtained successfully')
            return self.access_token
            
        except Exception as e:
            logger.error(f'Error getting M-Pesa access token: {str(e)}')
            raise
    
    def generate_password(self, timestamp):
        """Generate password for STK push"""
        data_to_encode = f'{self.shortcode}{self.passkey}{timestamp}'
        encoded = base64.b64encode(data_to_encode.encode()).decode()
        return encoded
    
    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """
        Initiate M-Pesa STK Push payment
        
        Args:
            phone_number: Phone number in format 254712345678
            amount: Amount to charge
            account_reference: Reference for the transaction (e.g., student fee ID)
            transaction_desc: Description of the transaction
        
        Returns:
            dict: Response from M-Pesa API
        """
        try:
            access_token = self.get_access_token()
            
            # Format phone number (ensure it starts with 254)
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif not phone_number.startswith('254'):
                phone_number = '254' + phone_number
            
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            password = self.generate_password(timestamp)
            
            # STK Push URL
            url = f'{self.base_url}/mpesa/stkpush/v1/processrequest'
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'PartyA': phone_number,
                'PartyB': self.shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': self.callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ResponseCode') == '0':
                logger.info(f'M-Pesa STK Push initiated successfully. CheckoutRequestID: {result.get("CheckoutRequestID")}')
                return {
                    'success': True,
                    'merchant_request_id': result.get('MerchantRequestID'),
                    'checkout_request_id': result.get('CheckoutRequestID'),
                    'response_code': result.get('ResponseCode'),
                    'response_description': result.get('ResponseDescription'),
                    'customer_message': result.get('CustomerMessage')
                }
            else:
                logger.error(f'M-Pesa STK Push failed: {result.get("ResponseDescription")}')
                return {
                    'success': False,
                    'error': result.get('ResponseDescription', 'Unknown error'),
                    'response_code': result.get('ResponseCode')
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f'Network error initiating M-Pesa STK Push: {str(e)}')
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            logger.error(f'Error initiating M-Pesa STK Push: {str(e)}')
            return {
                'success': False,
                'error': f'Error: {str(e)}'
            }
    
    def query_stk_status(self, checkout_request_id):
        """
        Query the status of an STK Push transaction
        
        Args:
            checkout_request_id: The CheckoutRequestID from initiate_stk_push
        
        Returns:
            dict: Transaction status
        """
        try:
            access_token = self.get_access_token()
            
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            password = self.generate_password(timestamp)
            
            url = f'{self.base_url}/mpesa/stkpushquery/v1/query'
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'CheckoutRequestID': checkout_request_id
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                'success': True,
                'response_code': result.get('ResponseCode'),
                'response_description': result.get('ResponseDescription'),
                'merchant_request_id': result.get('MerchantRequestID'),
                'checkout_request_id': result.get('CheckoutRequestID'),
                'result_code': result.get('ResultCode'),
                'result_description': result.get('ResultDesc')
            }
            
        except Exception as e:
            logger.error(f'Error querying M-Pesa STK status: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

