import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, IntegerField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, Email

from app import db
from models import User, MemberProfile, VerificationStatus
from utils.email import send_profile_update_notification

member_bp = Blueprint('member', __name__, url_prefix='/member')

# Forms
class ProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=64)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=20)])
    address = TextAreaField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    submit = SubmitField('Update Profile')

class EducationForm(FlaskForm):
    secondary_school = StringField('Secondary School Name', validators=[DataRequired()])
    secondary_school_start_year = IntegerField('Start Year', validators=[
        DataRequired(),
        NumberRange(min=1950, max=datetime.now().year)
    ])
    secondary_school_end_year = IntegerField('End Year', validators=[
        DataRequired(),
        NumberRange(min=1950, max=datetime.now().year)
    ])
    secondary_school_cert = FileField('Secondary School Certificate', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDF files only!')
    ])
    
    higher_institution = StringField('Higher Institution Name', validators=[DataRequired()])
    higher_institution_start_year = IntegerField('Start Year', validators=[
        DataRequired(),
        NumberRange(min=1950, max=datetime.now().year)
    ])
    higher_institution_end_year = IntegerField('End Year', validators=[
        DataRequired(),
        NumberRange(min=1950, max=datetime.now().year)
    ])
    degree_type = SelectField('Degree Type', choices=[('HND', 'HND'), ('BSc', 'BSc')])
    higher_institution_cert = FileField('Higher Institution Certificate', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDF files only!')
    ])
    
    submit = SubmitField('Save Educational Information')

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

# Routes
@member_bp.route('/profile')
@login_required
def profile():
    profile = MemberProfile.query.filter_by(user_id=current_user.id).first()
    return render_template('member/profile.html', profile=profile)

@member_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone_number = form.phone_number.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.state = form.state.data
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('member.profile'))
    
    # Pre-fill form data
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.phone_number.data = current_user.phone_number
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.state.data = current_user.state
    
    return render_template('member/edit_profile.html', form=form)

@member_bp.route('/education', methods=['GET', 'POST'])
@login_required
def education():
    form = EducationForm()
    profile = MemberProfile.query.filter_by(user_id=current_user.id).first()
    
    if form.validate_on_submit():
        secondary_school_cert_path = profile.secondary_school_cert_path if profile else None
        higher_institution_cert_path = profile.higher_institution_cert_path if profile else None
        
        # Handle file uploads
        if form.secondary_school_cert.data:
            secondary_school_cert_path = save_file(form.secondary_school_cert.data, 'certificates')
        
        if form.higher_institution_cert.data:
            higher_institution_cert_path = save_file(form.higher_institution_cert.data, 'certificates')
        
        if profile:
            # Update existing profile
            profile.secondary_school = form.secondary_school.data
            profile.secondary_school_start_year = form.secondary_school_start_year.data
            profile.secondary_school_end_year = form.secondary_school_end_year.data
            if secondary_school_cert_path:
                profile.secondary_school_cert_path = secondary_school_cert_path
            
            profile.higher_institution = form.higher_institution.data
            profile.higher_institution_start_year = form.higher_institution_start_year.data
            profile.higher_institution_end_year = form.higher_institution_end_year.data
            profile.degree_type = form.degree_type.data
            if higher_institution_cert_path:
                profile.higher_institution_cert_path = higher_institution_cert_path
            
            # If documents are updated, reset verification status
            if form.secondary_school_cert.data or form.higher_institution_cert.data:
                profile.verification_status = VerificationStatus.PENDING
                profile.verified_by = None
                profile.verification_date = None
        else:
            # Create new profile
            profile = MemberProfile(
                user_id=current_user.id,
                secondary_school=form.secondary_school.data,
                secondary_school_start_year=form.secondary_school_start_year.data,
                secondary_school_end_year=form.secondary_school_end_year.data,
                secondary_school_cert_path=secondary_school_cert_path,
                higher_institution=form.higher_institution.data,
                higher_institution_start_year=form.higher_institution_start_year.data,
                higher_institution_end_year=form.higher_institution_end_year.data,
                degree_type=form.degree_type.data,
                higher_institution_cert_path=higher_institution_cert_path,
                verification_status=VerificationStatus.PENDING
            )
            db.session.add(profile)
        
        db.session.commit()
        
        # Notify admin about new profile update
        send_profile_update_notification(current_user)
        
        flash('Educational information has been saved successfully!', 'success')
        return redirect(url_for('member.profile'))
    
    # Pre-fill form data
    if request.method == 'GET' and profile:
        form.secondary_school.data = profile.secondary_school
        form.secondary_school_start_year.data = profile.secondary_school_start_year
        form.secondary_school_end_year.data = profile.secondary_school_end_year
        
        form.higher_institution.data = profile.higher_institution
        form.higher_institution_start_year.data = profile.higher_institution_start_year
        form.higher_institution_end_year.data = profile.higher_institution_end_year
        form.degree_type.data = profile.degree_type
    
    return render_template('member/education.html', form=form, profile=profile)

@member_bp.route('/documents')
@login_required
def documents():
    profile = MemberProfile.query.filter_by(user_id=current_user.id).first()
    return render_template('member/documents.html', profile=profile)
