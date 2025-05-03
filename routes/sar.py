import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, FloatField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Length, Optional

from app import db
from models import SARApplication, SARStatus, User, PaymentStatus, AuditLog
from utils.payment import generate_payment_reference, initialize_payment, verify_payment
from utils.certificate import generate_sar_certificate
from utils.qrcode import generate_qr_code
from utils.email import send_sar_certificate
from utils.whatsapp import send_sar_certificate_whatsapp

sar_bp = Blueprint('sar', __name__, url_prefix='/sar')

# Constants
SAR_APPLICATION_FEE = 50000  # in Naira (or your local currency)

# Forms
class SARApplicationForm(FlaskForm):
    site_address = TextAreaField('Site Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[
        DataRequired(),
        NumberRange(min=-180, max=180, message='Longitude must be between -180 and 180.')
    ])
    latitude = FloatField('Latitude', validators=[
        DataRequired(),
        NumberRange(min=-90, max=90, message='Latitude must be between -90 and 90.')
    ])
    title_document = FileField('Title Document', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDF files only!')
    ])
    cofo_document = FileField('Certificate of Occupancy (CofO)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDF files only!')
    ])
    ownership_proof = FileField('Proof of Ownership', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDF files only!')
    ])
    submit = SubmitField('Submit Application')

class SARPaymentForm(FlaskForm):
    application_id = HiddenField('Application ID', validators=[DataRequired()])
    amount = HiddenField('Amount', validators=[DataRequired()])
    reference = HiddenField('Reference')
    submit = SubmitField('Proceed to Payment')

# Helper function for file uploads
def save_file(file, subfolder):
    if not file:
        return None
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    new_filename = f"{timestamp}_{filename}"
    
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    
    file_path = os.path.join(upload_path, new_filename)
    file.save(file_path)
    
    return os.path.join(subfolder, new_filename)

# Helper function to generate reference number
def generate_reference_number():
    return f"SAR-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

# Routes
@sar_bp.route('/')
@login_required
def index():
    # Check if user has active subscription
    if not current_user.has_active_subscription():
        flash('You need an active subscription to apply for SAR. Please renew your subscription.', 'warning')
        return redirect(url_for('subscription.index'))
    
    # Get user's SAR applications
    applications = SARApplication.query.filter_by(user_id=current_user.id).order_by(SARApplication.created_at.desc()).all()
    
    return render_template('sar/index.html', applications=applications)

@sar_bp.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    # Check if user has active subscription
    if not current_user.has_active_subscription():
        flash('You need an active subscription to apply for SAR. Please renew your subscription.', 'warning')
        return redirect(url_for('subscription.index'))
    
    form = SARApplicationForm()
    
    if form.validate_on_submit():
        # Generate reference number
        reference_number = generate_reference_number()
        
        # Handle file uploads
        title_document_path = save_file(form.title_document.data, 'sar_documents')
        cofo_document_path = save_file(form.cofo_document.data, 'sar_documents')
        ownership_proof_path = save_file(form.ownership_proof.data, 'sar_documents')
        
        # Create SAR application
        sar_application = SARApplication(
            user_id=current_user.id,
            reference_number=reference_number,
            site_address=form.site_address.data,
            city=form.city.data,
            state=form.state.data,
            longitude=form.longitude.data,
            latitude=form.latitude.data,
            title_document_path=title_document_path,
            cofo_document_path=cofo_document_path,
            ownership_proof_path=ownership_proof_path,
            status=SARStatus.SUBMITTED,
            payment_amount=SAR_APPLICATION_FEE
        )
        
        db.session.add(sar_application)
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Created SAR application",
            resource_type="SARApplication",
            resource_id=sar_application.id,
            details=f"Reference: {reference_number}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        flash('SAR application submitted successfully!', 'success')
        return redirect(url_for('sar.view', application_id=sar_application.id))
    
    return render_template('sar/apply.html', form=form)

@sar_bp.route('/view/<int:application_id>')
@login_required
def view(application_id):
    application = SARApplication.query.get_or_404(application_id)
    
    # Ensure the application belongs to the current user
    if application.user_id != current_user.id and not current_user.role == 'admin':
        flash('You do not have permission to view this application.', 'danger')
        return redirect(url_for('sar.index'))
    
    return render_template('sar/view.html', application=application)

@sar_bp.route('/payment/<int:application_id>', methods=['GET', 'POST'])
@login_required
def payment(application_id):
    application = SARApplication.query.get_or_404(application_id)
    
    # Ensure the application belongs to the current user
    if application.user_id != current_user.id:
        flash('You do not have permission to access this payment page.', 'danger')
        return redirect(url_for('sar.index'))
    
    # Ensure the application is in the correct status
    if application.status != SARStatus.APPROVED:
        flash('This application is not ready for payment yet.', 'warning')
        return redirect(url_for('sar.view', application_id=application.id))
    
    form = SARPaymentForm()
    
    if form.validate_on_submit():
        application_id = int(form.application_id.data)
        amount = float(form.amount.data)
        
        # Verify application again
        application = SARApplication.query.get_or_404(application_id)
        if application.user_id != current_user.id:
            flash('You do not have permission to make this payment.', 'danger')
            return redirect(url_for('sar.index'))
        
        # Generate payment reference
        reference = generate_payment_reference()
        
        # Update application with payment reference
        application.payment_reference = reference
        application.status = SARStatus.PAYMENT_PENDING
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Initiated SAR payment",
            resource_type="SARApplication",
            resource_id=application.id,
            details=f"Reference: {application.reference_number}, Amount: {amount}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Initialize payment with gateway
        payment_url = initialize_payment(
            amount=amount,
            email=current_user.email,
            reference=reference,
            callback_url=url_for('sar.verify_payment', _external=True)
        )
        
        if payment_url:
            return redirect(payment_url)
        else:
            flash('Payment initialization failed. Please try again.', 'danger')
            return redirect(url_for('sar.view', application_id=application.id))
    
    # For GET requests or form validation failures
    form.application_id.data = application.id
    form.amount.data = application.payment_amount
    
    return render_template(
        'sar/payment.html',
        form=form,
        application=application
    )

@sar_bp.route('/verify-payment')
@login_required
def verify_payment():
    reference = request.args.get('reference')
    if not reference:
        flash('Payment reference is missing.', 'danger')
        return redirect(url_for('sar.index'))
    
    # Verify payment with payment gateway
    payment_data = verify_payment(reference)
    
    if not payment_data:
        flash('Payment verification failed. Please contact support.', 'danger')
        return redirect(url_for('sar.index'))
    
    # Get the application record
    application = SARApplication.query.filter_by(
        payment_reference=reference
    ).first()
    
    if not application:
        flash('Application record not found.', 'danger')
        return redirect(url_for('sar.index'))
    
    # Update application status based on payment status
    if payment_data.get('status') == PaymentStatus.COMPLETED:
        application.payment_status = PaymentStatus.COMPLETED
        application.status = SARStatus.PAYMENT_COMPLETED
        
        # Generate certificate with all notifications
        certificate_path, qr_code_path, notification_status = generate_sar_certificate(application, current_user)
        
        if certificate_path and qr_code_path:
            # Update application status
            application.status = SARStatus.CERTIFICATE_GENERATED
            
            # Check if notifications were sent successfully
            if notification_status.get('email') or notification_status.get('sms') or notification_status.get('whatsapp'):
                application.status = SARStatus.CERTIFICATE_DELIVERED
                current_app.logger.info(f"Certificate delivery status: {notification_status}")
            else:
                current_app.logger.warning(f"No notifications were sent successfully: {notification_status}")
        else:
            # Log the error
            current_app.logger.error(f"Certificate generation failed: {notification_status.get('error', 'Unknown error')}")
            flash('Certificate generation encountered an issue. Please contact administrator.', 'warning')
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="SAR payment completed and certificate generated",
            resource_type="SARApplication",
            resource_id=application.id,
            details=f"Reference: {application.reference_number}, Certificate: {application.certificate_number}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Payment successful! Your SAR certificate has been generated and sent to your email and WhatsApp.', 'success')
    else:
        flash('Payment was not successful. Please try again or contact support.', 'danger')
    
    return redirect(url_for('sar.view', application_id=application.id))

@sar_bp.route('/certificate/<int:application_id>')
@login_required
def certificate(application_id):
    application = SARApplication.query.get_or_404(application_id)
    
    # Ensure the application belongs to the current user or is an admin
    if application.user_id != current_user.id and not current_user.role == 'admin':
        flash('You do not have permission to view this certificate.', 'danger')
        return redirect(url_for('sar.index'))
    
    # Ensure the certificate has been generated
    if application.status not in [SARStatus.CERTIFICATE_GENERATED, SARStatus.CERTIFICATE_DELIVERED]:
        flash('Certificate has not been generated yet.', 'warning')
        return redirect(url_for('sar.view', application_id=application.id))
    
    # Serve the certificate file
    if application.certificate_path:
        try:
            certificate_path = os.path.join(current_app.static_folder, 'uploads', application.certificate_path)
            if os.path.exists(certificate_path):
                return send_file(certificate_path, as_attachment=True)
            else:
                current_app.logger.error(f"Certificate file not found at {certificate_path}")
                flash('Certificate file not found on server. Please contact administrator.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Error serving certificate file: {str(e)}")
            flash('Error accessing certificate file. Please try again later.', 'danger')
    else:
        flash('Certificate information is missing. Please contact administrator.', 'danger')
    
    return redirect(url_for('sar.view', application_id=application.id))

@sar_bp.route('/verify')
def verify():
    certificate_number = request.args.get('certificate_number')
    if not certificate_number:
        return render_template('sar/verify.html')
    
    application = SARApplication.query.filter_by(certificate_number=certificate_number).first()
    
    if not application:
        return render_template('sar/verify.html', error="Certificate not found or invalid.")
    
    # Get user info
    user = User.query.get(application.user_id)
    
    return render_template('sar/verify.html', application=application, user=user)
