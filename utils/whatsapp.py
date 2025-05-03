import os
from twilio.rest import Client
from flask import current_app

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_NUMBER = f"whatsapp:{TWILIO_PHONE_NUMBER}" if TWILIO_PHONE_NUMBER else None

def send_whatsapp_message(to_phone_number, message):
    """
    Send a WhatsApp message using Twilio
    
    Args:
        to_phone_number (str): Recipient's phone number (should include country code)
        message (str): Message content
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Clean phone number and ensure it's in WhatsApp format
        # Remove any non-digit characters except the plus sign
        clean_number = ''.join(c for c in to_phone_number if c.isdigit() or c == '+')
        
        # Ensure number starts with +
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        
        # Add WhatsApp prefix
        whatsapp_number = f"whatsapp:{clean_number}"
        
        # Check if Twilio credentials are available
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER]):
            current_app.logger.warning("Twilio credentials not configured. WhatsApp message not sent.")
            return False
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Sending the WhatsApp message
        message = client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=whatsapp_number
        )
        
        current_app.logger.info(f"WhatsApp message sent with SID: {message.sid}")
        return True
    
    except Exception as e:
        current_app.logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False

def send_sar_certificate_whatsapp(phone_number, certificate_path, application):
    """
    Send SAR certificate notification and PDF via WhatsApp
    
    Args:
        phone_number (str): Recipient's phone number
        certificate_path (str): Path to the certificate file
        application (SARApplication): SAR application object
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Compose message
    message = f"""
*NITP SAR Certificate Generated*

Congratulations! Your Site Analysis Report (SAR) certificate has been generated successfully.

*Certificate details:*
- Certificate number: {application.certificate_number}
- Reference number: {application.reference_number}
- Site address: {application.site_address}

Your certificate has also been sent to your registered email address. Thank you for using our services.

Best regards,
NITP Abuja Chapter
"""
    
    # Send message
    return send_whatsapp_message(phone_number, message)
