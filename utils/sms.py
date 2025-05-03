import os
from twilio.rest import Client
from flask import current_app

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def send_sms(to_phone_number, message):
    """
    Send an SMS message using Twilio
    
    Args:
        to_phone_number (str): Recipient's phone number (should include country code)
        message (str): Message content
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Clean phone number
        # Remove any non-digit characters except the plus sign
        clean_number = ''.join(c for c in to_phone_number if c.isdigit() or c == '+')
        
        # Ensure number starts with +
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        
        # Check if Twilio credentials are available
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            current_app.logger.warning("Twilio credentials not configured. SMS not sent.")
            return False
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Sending the SMS
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=clean_number
        )
        
        current_app.logger.info(f"SMS sent with SID: {message.sid}")
        return True
    
    except Exception as e:
        current_app.logger.error(f"Error sending SMS: {str(e)}")
        return False

def send_subscription_reminder(phone_number, user_name, expiry_date, subscription_year):
    """
    Send subscription reminder via SMS
    
    Args:
        phone_number (str): Member's phone number
        user_name (str): Member's name
        expiry_date (datetime): Subscription expiry date
        subscription_year (int): Subscription year
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Format date as DD-MM-YYYY
    formatted_date = expiry_date.strftime('%d-%m-%Y')
    
    # Compose message
    message = f"Dear {user_name}, your NITP membership subscription for {subscription_year} will expire on {formatted_date}. Please renew your subscription to continue accessing all member benefits."
    
    # Send SMS
    return send_sms(phone_number, message)

def send_sar_status_update(phone_number, user_name, reference_number, status):
    """
    Send SAR application status update via SMS
    
    Args:
        phone_number (str): Member's phone number
        user_name (str): Member's name
        reference_number (str): SAR application reference number
        status (str): New status of the application
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Format status for display
    formatted_status = status.replace('_', ' ').title()
    
    # Compose message
    message = f"Dear {user_name}, your SAR application with reference number {reference_number} has been updated to '{formatted_status}'. Login to your account for more details."
    
    # Send SMS
    return send_sms(phone_number, message)

def send_sar_certificate_sms(phone_number, user_name, certificate_number, reference_number):
    """
    Send SAR certificate notification via SMS
    
    Args:
        phone_number (str): Member's phone number
        user_name (str): Member's name
        certificate_number (str): Certificate number
        reference_number (str): SAR application reference number
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Compose message
    message = f"Dear {user_name}, your SAR certificate (Number: {certificate_number}) for application {reference_number} has been generated. Please login to download your certificate or check your email."
    
    # Send SMS
    return send_sms(phone_number, message)