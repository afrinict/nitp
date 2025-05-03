from flask import current_app
from .email import send_certificate_email
from .sms import send_sar_certificate_sms
from .whatsapp import send_sar_certificate_whatsapp

def notify_certificate_generation(user, application, certificate_path):
    """
    Send notifications about certificate generation through multiple channels
    
    Args:
        user (User): User object containing contact information
        application (SARApplication): SAR application object
        certificate_path (str): Path to the generated certificate file
    
    Returns:
        dict: Status of each notification channel (email, sms, whatsapp)
    """
    result = {
        'email': False,
        'sms': False,
        'whatsapp': False
    }
    
    # Send email notification
    try:
        result['email'] = send_certificate_email(
            user.email, 
            user.first_name, 
            application.certificate_number,
            application.reference_number,
            certificate_path
        )
    except Exception as e:
        current_app.logger.error(f"Error sending certificate email: {str(e)}")
    
    # Send SMS notification
    try:
        result['sms'] = send_sar_certificate_sms(
            user.phone_number,
            f"{user.first_name} {user.last_name}",
            application.certificate_number,
            application.reference_number
        )
    except Exception as e:
        current_app.logger.error(f"Error sending certificate SMS: {str(e)}")
    
    # Send WhatsApp notification
    try:
        result['whatsapp'] = send_sar_certificate_whatsapp(
            user.phone_number,
            certificate_path,
            application
        )
    except Exception as e:
        current_app.logger.error(f"Error sending certificate WhatsApp: {str(e)}")
    
    # Log the notification status
    current_app.logger.info(
        f"Certificate notifications for {application.certificate_number}: "
        f"Email: {'Sent' if result['email'] else 'Failed'}, "
        f"SMS: {'Sent' if result['sms'] else 'Failed'}, "
        f"WhatsApp: {'Sent' if result['whatsapp'] else 'Failed'}"
    )
    
    return result

def send_subscription_notifications(user, subscription):
    """
    Send notifications about subscription payment/renewal
    
    Args:
        user (User): User object containing contact information
        subscription (Subscription): Subscription object
    
    Returns:
        dict: Status of each notification channel (email, sms)
    """
    result = {
        'email': False,
        'sms': False
    }
    
    # TODO: Implement subscription email notification
    # result['email'] = send_subscription_email(...)
    
    # TODO: Implement subscription SMS notification
    # result['sms'] = send_subscription_sms(...)
    
    # Log the notification status
    current_app.logger.info(
        f"Subscription notifications for User ID {user.id}, Year {subscription.year}: "
        f"Email: {'Sent' if result['email'] else 'Failed'}, "
        f"SMS: {'Sent' if result['sms'] else 'Failed'}"
    )
    
    return result

def send_sar_status_notifications(user, application):
    """
    Send notifications about SAR application status changes
    
    Args:
        user (User): User object containing contact information
        application (SARApplication): SAR application object
    
    Returns:
        dict: Status of each notification channel (email, sms)
    """
    result = {
        'email': False,
        'sms': False
    }
    
    # TODO: Implement SAR status email notification
    # result['email'] = send_sar_status_email(...)
    
    # TODO: Implement SAR status SMS notification
    # from .sms import send_sar_status_update
    # result['sms'] = send_sar_status_update(
    #     user.phone_number,
    #     f"{user.first_name} {user.last_name}",
    #     application.reference_number,
    #     application.status.value
    # )
    
    # Log the notification status
    current_app.logger.info(
        f"SAR status notifications for {application.reference_number}: "
        f"Email: {'Sent' if result['email'] else 'Failed'}, "
        f"SMS: {'Sent' if result['sms'] else 'Failed'}"
    )
    
    return result