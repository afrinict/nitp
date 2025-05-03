import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SubmitField, HiddenField, StringField
from wtforms.validators import DataRequired

from app import db
from models import Subscription, SubscriptionStatus, AuditLog, PaymentStatus
from utils.payment import generate_payment_reference, initialize_payment, verify_payment
from utils.email import send_subscription_confirmation

subscription_bp = Blueprint('subscription', __name__, url_prefix='/subscription')

# Forms
class SubscriptionPaymentForm(FlaskForm):
    amount = HiddenField('Amount', validators=[DataRequired()])
    year = HiddenField('Year', validators=[DataRequired()])
    reference = HiddenField('Reference')
    submit = SubmitField('Proceed to Payment')

# Constants
SUBSCRIPTION_FEE = 20000  # in Naira (or your local currency)

# Routes
@subscription_bp.route('/')
@login_required
def index():
    current_year = datetime.now().year
    active_subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        year=current_year,
        status=SubscriptionStatus.ACTIVE
    ).first()
    
    subscription_history = Subscription.query.filter_by(
        user_id=current_user.id
    ).order_by(Subscription.year.desc()).all()
    
    return render_template(
        'subscription/index.html',
        active_subscription=active_subscription,
        subscription_history=subscription_history,
        current_year=current_year,
        subscription_fee=SUBSCRIPTION_FEE
    )

@subscription_bp.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    form = SubscriptionPaymentForm()
    
    if form.validate_on_submit():
        year = int(form.year.data)
        amount = float(form.amount.data)
        
        # Check if a subscription already exists for this year
        existing_subscription = Subscription.query.filter_by(
            user_id=current_user.id,
            year=year
        ).first()
        
        if existing_subscription and existing_subscription.status == SubscriptionStatus.ACTIVE:
            flash('You already have an active subscription for this year.', 'warning')
            return redirect(url_for('subscription.index'))
        
        # Generate payment reference
        reference = generate_payment_reference()
        
        # Create or update subscription record
        if existing_subscription:
            existing_subscription.amount = amount
            existing_subscription.payment_reference = reference
            existing_subscription.status = SubscriptionStatus.PENDING
            subscription = existing_subscription
        else:
            subscription = Subscription(
                user_id=current_user.id,
                year=year,
                amount=amount,
                payment_reference=reference,
                status=SubscriptionStatus.PENDING
            )
            db.session.add(subscription)
        
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Initiated subscription payment",
            resource_type="Subscription",
            resource_id=subscription.id,
            details=f"Year: {year}, Amount: {amount}",
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
            callback_url=url_for('subscription.verify', _external=True)
        )
        
        if payment_url:
            return redirect(payment_url)
        else:
            flash('Payment initialization failed. Please try again.', 'danger')
            return redirect(url_for('subscription.index'))
    
    # For GET requests or form validation failures
    year = request.args.get('year', datetime.now().year)
    amount = SUBSCRIPTION_FEE  # Fixed subscription fee
    
    form.year.data = year
    form.amount.data = amount
    
    return render_template(
        'subscription/payment.html',
        form=form,
        year=year,
        amount=amount
    )

@subscription_bp.route('/verify')
@login_required
def verify():
    reference = request.args.get('reference')
    if not reference:
        flash('Payment reference is missing.', 'danger')
        return redirect(url_for('subscription.index'))
    
    # Verify payment with payment gateway
    payment_data = verify_payment(reference)
    
    if not payment_data:
        flash('Payment verification failed. Please contact support.', 'danger')
        return redirect(url_for('subscription.index'))
    
    # Get the subscription record
    subscription = Subscription.query.filter_by(
        payment_reference=reference
    ).first()
    
    if not subscription:
        flash('Subscription record not found.', 'danger')
        return redirect(url_for('subscription.index'))
    
    # Update subscription status based on payment status
    if payment_data.get('status') == PaymentStatus.COMPLETED:
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.payment_date = datetime.utcnow()
        subscription.start_date = datetime.utcnow()
        subscription.end_date = datetime.utcnow() + timedelta(days=365)  # Valid for one year
        
        db.session.commit()
        
        # Send confirmation email
        send_subscription_confirmation(current_user, subscription)
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Subscription payment completed",
            resource_type="Subscription",
            resource_id=subscription.id,
            details=f"Year: {subscription.year}, Amount: {subscription.amount}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Subscription payment successful! Your subscription is now active.', 'success')
    else:
        flash('Payment was not successful. Please try again or contact support.', 'danger')
    
    return redirect(url_for('subscription.index'))

@subscription_bp.route('/history')
@login_required
def history():
    subscription_history = Subscription.query.filter_by(
        user_id=current_user.id
    ).order_by(Subscription.year.desc()).all()
    
    return render_template(
        'subscription/history.html',
        subscription_history=subscription_history
    )

@subscription_bp.route('/receipt/<int:subscription_id>')
@login_required
def receipt(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Ensure the subscription belongs to the current user
    if subscription.user_id != current_user.id:
        flash('You do not have permission to view this receipt.', 'danger')
        return redirect(url_for('subscription.index'))
    
    return render_template(
        'subscription/receipt.html',
        subscription=subscription
    )
