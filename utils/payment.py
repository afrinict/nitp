import os
import uuid
import requests
from datetime import datetime
from flask import current_app, url_for
from models import PaymentStatus

# Payment gateway configuration
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')
PAYSTACK_BASE_URL = 'https://api.paystack.co'

def generate_payment_reference():
    """
    Generate a unique payment reference
    
    Returns:
        str: Unique payment reference
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    return f"NITP-{timestamp}-{unique_id}"

def initialize_payment(amount, email, reference, callback_url):
    """
    Initialize a payment with Paystack
    
    Args:
        amount (float): Amount to charge (in Naira)
        email (str): Customer's email address
        reference (str): Unique payment reference
        callback_url (str): URL to redirect to after payment
    
    Returns:
        str: URL to redirect user to for payment or None if initialization failed
    """
    try:
        # Convert amount to kobo (Paystack uses kobo, not Naira)
        amount_in_kobo = int(amount * 100)
        
        headers = {
            'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'amount': amount_in_kobo,
            'email': email,
            'reference': reference,
            'callback_url': callback_url,
            'currency': 'NGN',
            'metadata': {
                'custom_fields': [
                    {
                        'display_name': 'NITP Payment',
                        'variable_name': 'nitp_payment',
                        'value': reference
                    }
                ]
            }
        }
        
        response = requests.post(
            f'{PAYSTACK_BASE_URL}/transaction/initialize',
            json=data,
            headers=headers
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data['status']:
                return response_data['data']['authorization_url']
        
        current_app.logger.error(f"Paystack payment initialization failed: {response.text}")
        return None
    
    except Exception as e:
        current_app.logger.error(f"Error initializing payment: {str(e)}")
        return None

def verify_payment(reference):
    """
    Verify a payment with Paystack
    
    Args:
        reference (str): Payment reference to verify
    
    Returns:
        dict: Payment data or None if verification failed
    """
    try:
        headers = {
            'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'{PAYSTACK_BASE_URL}/transaction/verify/{reference}',
            headers=headers
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data['status'] and response_data['data']['status'] == 'success':
                # Extract payment details
                payment_data = {
                    'amount': response_data['data']['amount'] / 100,  # Convert from kobo to Naira
                    'reference': response_data['data']['reference'],
                    'status': PaymentStatus.COMPLETED,
                    'paid_at': response_data['data']['paid_at'],
                    'channel': response_data['data']['channel'],
                    'transaction_date': response_data['data']['transaction_date']
                }
                return payment_data
        
        current_app.logger.error(f"Paystack payment verification failed: {response.text}")
        return None
    
    except Exception as e:
        current_app.logger.error(f"Error verifying payment: {str(e)}")
        return None

# Mock function for testing without Paystack integration
def mock_initialize_payment(amount, email, reference, callback_url):
    """
    Mock function to initialize payment for testing
    
    Returns:
        str: Callback URL with reference appended
    """
    return f"{callback_url}?reference={reference}"

def mock_verify_payment(reference):
    """
    Mock function to verify payment for testing
    
    Returns:
        dict: Mock payment data
    """
    return {
        'amount': 20000.00,
        'reference': reference,
        'status': PaymentStatus.COMPLETED,
        'paid_at': datetime.now().isoformat(),
        'channel': 'test',
        'transaction_date': datetime.now().isoformat()
    }
