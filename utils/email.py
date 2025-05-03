from flask import render_template, current_app, url_for
from flask_mail import Message
from threading import Thread
from app import mail

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipients, html_body):
    msg = Message(
        subject=subject,
        recipients=recipients,
        html=html_body,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()

def send_verification_email(email, token):
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    
    html_body = f'''
    <h1>NITP Abuja Chapter Email Verification</h1>
    <p>Thank you for registering with the Nigeria Institute of Town Planners (NITP), Abuja Chapter.</p>
    <p>Please click on the following link to verify your email address:</p>
    <p><a href="{verification_url}">Verify Email Address</a></p>
    <p>This link will expire in 24 hours.</p>
    <p>If you did not register on our platform, please ignore this email.</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    send_email('Verify Your NITP Membership Email', [email], html_body)

def send_profile_update_notification(user):
    html_body = f'''
    <h1>NITP Profile Update Notification</h1>
    <p>Dear {user.first_name} {user.last_name},</p>
    <p>Your profile information has been updated successfully.</p>
    <p>Your educational information will be reviewed by our administrators for verification.</p>
    <p>You will be notified once the verification process is complete.</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    send_email('NITP Profile Update Notification', [user.email], html_body)

def send_verification_approval_email(email):
    login_url = url_for('auth.login', _external=True)
    
    html_body = f'''
    <h1>NITP Membership Verification Approved</h1>
    <p>Congratulations! Your NITP membership profile has been verified and approved.</p>
    <p>You now have full access to all member features, including the ability to apply for Site Analysis Reports (SAR).</p>
    <p>Please <a href="{login_url}">login to your account</a> to explore your member benefits.</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    send_email('NITP Membership Verification Approved', [email], html_body)

def send_subscription_confirmation(user, subscription):
    html_body = f'''
    <h1>NITP Annual Subscription Confirmation</h1>
    <p>Dear {user.first_name} {user.last_name},</p>
    <p>Thank you for renewing your NITP Abuja Chapter membership subscription for {subscription.year}.</p>
    <p>Your payment of ₦{subscription.amount:,.2f} has been received and processed successfully.</p>
    <p>Subscription details:</p>
    <ul>
        <li>Subscription year: {subscription.year}</li>
        <li>Payment reference: {subscription.payment_reference}</li>
        <li>Payment date: {subscription.payment_date.strftime('%d %B, %Y')}</li>
        <li>Valid until: {subscription.end_date.strftime('%d %B, %Y')}</li>
    </ul>
    <p>You now have full access to all member features, including the ability to apply for Site Analysis Reports (SAR).</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    send_email('NITP Annual Subscription Confirmation', [user.email], html_body)

def send_sar_approval_email(email, application):
    payment_url = url_for('sar.payment', application_id=application.id, _external=True)
    
    html_body = f'''
    <h1>NITP SAR Application Approved</h1>
    <p>Congratulations! Your Site Analysis Report (SAR) application has been approved.</p>
    <p>Application details:</p>
    <ul>
        <li>Reference number: {application.reference_number}</li>
        <li>Site address: {application.site_address}</li>
        <li>Application date: {application.created_at.strftime('%d %B, %Y')}</li>
    </ul>
    <p>Please <a href="{payment_url}">proceed to payment</a> to complete your application and generate your SAR certificate.</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    send_email('NITP SAR Application Approved', [email], html_body)

def send_sar_certificate(email, certificate_path, application):
    html_body = f'''
    <h1>NITP SAR Certificate</h1>
    <p>Congratulations! Your Site Analysis Report (SAR) certificate has been generated successfully.</p>
    <p>Certificate details:</p>
    <ul>
        <li>Certificate number: {application.certificate_number}</li>
        <li>Reference number: {application.reference_number}</li>
        <li>Site address: {application.site_address}</li>
    </ul>
    <p>Your certificate has been attached to this email. You can also download it from your account.</p>
    <p>Best regards,<br>NITP Abuja Chapter</p>
    '''
    
    msg = Message(
        subject='NITP SAR Certificate',
        recipients=[email],
        html=html_body,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    # Attach certificate
    with current_app.open_resource(f"static/uploads/{certificate_path}") as certificate:
        msg.attach(
            filename=f"NITP_SAR_Certificate_{application.certificate_number}.pdf",
            content_type="application/pdf",
            data=certificate.read()
        )
    
    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()

def send_certificate_email(email, name, certificate_number, reference_number, certificate_path):
    """
    Send certificate notification email with certificate attachment
    
    Args:
        email (str): User's email address
        name (str): User's first name
        certificate_number (str): Certificate number
        reference_number (str): SAR application reference number
        certificate_path (str): Path to the certificate file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        verify_url = url_for('sar.verify', certificate_number=certificate_number, _external=True)
        
        html_body = f'''
        <h1>NITP SAR Certificate Generated</h1>
        <p>Dear {name},</p>
        <p>Congratulations! Your Site Analysis Report (SAR) certificate has been generated successfully.</p>
        <p>Certificate details:</p>
        <ul>
            <li>Certificate number: {certificate_number}</li>
            <li>Reference number: {reference_number}</li>
        </ul>
        <p>Your certificate has been attached to this email. You can also view it online by visiting our website.</p>
        <p>To verify this certificate, please visit: <a href="{verify_url}">{verify_url}</a></p>
        <p>Best regards,<br>NITP Abuja Chapter</p>
        '''
        
        msg = Message(
            subject='Your NITP SAR Certificate',
            recipients=[email],
            html=html_body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Attach certificate
        with current_app.open_resource(f"static/uploads/{certificate_path}") as certificate:
            msg.attach(
                filename=f"NITP_SAR_Certificate_{certificate_number}.pdf",
                content_type="application/pdf",
                data=certificate.read()
            )
        
        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg)
        ).start()
        
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending certificate email: {str(e)}")
        return False
