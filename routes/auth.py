import uuid
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from sqlalchemy.exc import IntegrityError

from app import db
from models import User, EmailVerification, UserRole
from utils.email import send_verification_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Forms
class LoginForm(FlaskForm):
    identifier = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=64)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=20)])
    address = StringField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email address already registered. Please use a different email.')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different username.')

class PasswordResetRequestForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

# Routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Try to find user by email first
        user = User.query.filter_by(email=form.identifier.data).first()
        if not user:
            # If not found by email, try by username
            user = User.query.filter_by(username=form.identifier.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Create new user
            user = User(
                email=form.email.data,
                username=form.username.data,
                password_hash=generate_password_hash(form.password.data),
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                phone_number=form.phone_number.data,
                address=form.address.data,
                city=form.city.data,
                state=form.state.data,
                role=UserRole.MEMBER,
                is_active=True
            )

            # Add to database
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    email = request.args.get('email')
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Don't reveal that the user doesn't exist
        flash('If your email exists in our system, a verification link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    
    if user.email_verified:
        flash('Your email is already verified. You can login.', 'info')
        return redirect(url_for('auth.login'))
    
    # Create new verification token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    verification = EmailVerification(
        user=user,
        token=token,
        expires_at=expires_at
    )
    
    db.session.add(verification)
    db.session.commit()
    
    # Send verification email
    send_verification_email(user.email, token)
    
    flash('A new verification link has been sent to your email.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate reset token
            token = secrets.token_urlsafe(32)
            session['reset_token'] = {
                'user_id': user.id,
                'token': token,
                'expires': (datetime.utcnow() + timedelta(hours=1)).timestamp()
            }
            
            # TODO: Send password reset email with token
            # For now, just redirect to reset page with token
            flash('Password reset instructions have been sent to your email.', 'info')
            return redirect(url_for('auth.reset_password', token=token))
        
        flash('If your email exists in our system, reset instructions have been sent.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Verify token from session
    reset_info = session.get('reset_token')
    if not reset_info or reset_info['token'] != token or datetime.fromtimestamp(reset_info['expires']) < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.get(reset_info['user_id'])
        if user:
            user.set_password(form.password.data)
            db.session.commit()
            
            # Clear reset token from session
            session.pop('reset_token', None)
            
            flash('Your password has been reset successfully! You can now login.', 'success')
            return redirect(url_for('auth.login'))
        
        flash('An error occurred. Please try again.', 'danger')
    
    return render_template('auth/reset_password.html', form=form)
