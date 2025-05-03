import os
import logging
from flask import current_app
from .email import send_certificate_email
from .sms import send_sms_notification
from .whatsapp import send_whatsapp_notification

logger = logging.getLogger(__name__)

def notify_certificate_generation(user, application, certificate_path):
    """
    Send notifications about certificate generation through multiple channels
    
    Args:
        user: User object with contact information
        application: SARApplication object with certificate details
        certificate_path: Path to the generated certificate file
    
    Returns:
        dict: Status of each notification channel {email: bool, sms: bool, whatsapp: bool}
    """
    if not user or not application or not certificate_path:
        logger.error("Missing required parameters for notifications")
        return {"error": "Missing required parameters"}
    
    notification_status = {
        "email": False,
        "sms": False,
        "whatsapp": False
    }
    
    # Full path to certificate file
    certificate_full_path = os.path.join(
        current_app.static_folder, 
        'uploads', 
        certificate_path
    )
    
    if not os.path.exists(certificate_full_path):
        logger.error(f"Certificate file not found at {certificate_full_path}")
        return {"error": f"Certificate file not found at {certificate_path}"}
    
    # 1. Send email notification with certificate attachment
    try:
        if user.email:
            email_sent = send_certificate_email(
                email=user.email,
                name=f"{user.first_name} {user.last_name}",
                certificate_number=application.certificate_number,
                reference_number=application.reference_number,
                certificate_path=certificate_full_path
            )
            notification_status["email"] = email_sent
            logger.info(f"Email notification {'sent' if email_sent else 'failed'} to {user.email}")
        else:
            logger.warning(f"No email address available for user {user.id}")
    except Exception as e:
        logger.error(f"Email notification error: {str(e)}")
    
    # 2. Send SMS notification if Twilio credentials are configured
    try:
        if user.phone_number and all([
            os.environ.get("TWILIO_ACCOUNT_SID"),
            os.environ.get("TWILIO_AUTH_TOKEN"),
            os.environ.get("TWILIO_PHONE_NUMBER")
        ]):
            message = (
                f"Hello {user.first_name}, your NITP Site Analysis Report certificate "
                f"(#{application.certificate_number}) has been generated and sent to your email. "
                f"Thank you for using our services."
            )
            sms_sent = send_sms_notification(
                to_phone_number=user.phone_number,
                message=message
            )
            notification_status["sms"] = sms_sent
            logger.info(f"SMS notification {'sent' if sms_sent else 'failed'} to {user.phone_number}")
        else:
            if not user.phone_number:
                logger.warning(f"No phone number available for user {user.id}")
            else:
                logger.warning("SMS notification skipped: Twilio credentials not configured")
    except Exception as e:
        logger.error(f"SMS notification error: {str(e)}")
    
    # 3. Send WhatsApp notification if Twilio credentials are configured
    try:
        if user.phone_number and all([
            os.environ.get("TWILIO_ACCOUNT_SID"),
            os.environ.get("TWILIO_AUTH_TOKEN"),
            os.environ.get("TWILIO_PHONE_NUMBER")
        ]):
            message = (
                f"Hello {user.first_name}, your NITP Site Analysis Report certificate "
                f"(#{application.certificate_number}) has been generated and sent to your email. "
                f"You can also download it from your account dashboard. "
                f"Thank you for using our services."
            )
            whatsapp_sent = send_whatsapp_notification(
                to_phone_number=user.phone_number,
                message=message
            )
            notification_status["whatsapp"] = whatsapp_sent
            logger.info(f"WhatsApp notification {'sent' if whatsapp_sent else 'failed'} to {user.phone_number}")
        else:
            if not user.phone_number:
                logger.warning(f"No phone number available for user {user.id}")
            else:
                logger.warning("WhatsApp notification skipped: Twilio credentials not configured")
    except Exception as e:
        logger.error(f"WhatsApp notification error: {str(e)}")
    
    return notification_status