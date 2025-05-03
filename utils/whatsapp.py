import os
import logging
from twilio.rest import Client
from flask import current_app

logger = logging.getLogger(__name__)

def send_whatsapp_notification(to_phone_number, message):
    """
    Send WhatsApp notification using Twilio
    
    Args:
        to_phone_number (str): Recipient's phone number in E.164 format (+123456789)
        message (str): WhatsApp message content
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Check if Twilio credentials are configured
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")
    
    if not all([account_sid, auth_token, from_number]):
        logger.warning("Twilio credentials not configured. WhatsApp message not sent.")
        return False
    
    # Format phone number to E.164 format if needed
    if not to_phone_number.startswith('+'):
        # Add Nigeria country code if not present
        to_phone_number = f"+234{to_phone_number.lstrip('0')}"
    
    # Format Twilio WhatsApp phone number
    twilio_whatsapp = f"whatsapp:{from_number}"
    recipient_whatsapp = f"whatsapp:{to_phone_number}"
    
    try:
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Send WhatsApp message
        whatsapp_message = client.messages.create(
            body=message,
            from_=twilio_whatsapp,
            to=recipient_whatsapp
        )
        
        logger.info(f"WhatsApp message sent successfully. SID: {whatsapp_message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return False