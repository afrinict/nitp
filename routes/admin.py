from datetime import datetime, timedelta
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Length
from sqlalchemy import func, desc

from app import db
from models import (
    User, UserRole, MemberProfile, VerificationStatus, Subscription, 
    SubscriptionStatus, SARApplication, SARStatus, AuditLog, ChatRoom, NotificationSetting
)
from utils.email import send_verification_approval_email, send_sar_approval_email

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Forms
class UserRoleForm(FlaskForm):
    role = SelectField('Role', choices=[
        (UserRole.MEMBER.value, 'Member'),
        (UserRole.STAFF.value, 'Staff'),
        (UserRole.ADMIN.value, 'Admin'),
        (UserRole.SUPER_ADMIN.value, 'Super Admin')
    ], validators=[DataRequired()])
    submit = SubmitField('Update Role')

class ProfileVerificationForm(FlaskForm):
    status = SelectField('Verification Status', choices=[
        (VerificationStatus.VERIFIED.value, 'Verified'),
        (VerificationStatus.REJECTED.value, 'Rejected'),
        (VerificationStatus.PENDING.value, 'Pending')
    ], validators=[DataRequired()])
    comments = TextAreaField('Comments')
    submit = SubmitField('Update Status')

class SARReviewForm(FlaskForm):
    status = SelectField('Application Status', choices=[
        (SARStatus.UNDER_REVIEW.value, 'Under Review'),
        (SARStatus.APPROVED.value, 'Approved'),
        (SARStatus.REJECTED.value, 'Rejected')
    ], validators=[DataRequired()])
    comments = TextAreaField('Review Comments')
    submit = SubmitField('Update Status')

class NotificationSettingForm(FlaskForm):
    is_enabled = BooleanField('Enable Notification Channel')
    config_values = TextAreaField('Configuration (JSON format)', render_kw={"rows": 5})
    submit = SubmitField('Save Settings')

class TwilioSettingsForm(FlaskForm):
    account_sid = StringField('Twilio Account SID', validators=[DataRequired()])
    auth_token = PasswordField('Twilio Auth Token', validators=[DataRequired()])
    phone_number = StringField('Twilio Phone Number', validators=[DataRequired()])
    submit = SubmitField('Save Settings')

class ChatRoomForm(FlaskForm):
    name = StringField('Room Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    is_private = SelectField('Privacy', choices=[
        ('False', 'Public'),
        ('True', 'Private')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Room')

# Admin access decorator
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return login_required(decorated_function)

# Super admin access decorator
def super_admin_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.SUPER_ADMIN:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return login_required(decorated_function)

# Routes
@admin_bp.route('/')
@admin_required
def index():
    # Count statistics for dashboard
    total_members = User.query.filter_by(role=UserRole.MEMBER).count()
    pending_verifications = MemberProfile.query.filter_by(verification_status=VerificationStatus.PENDING).count()
    active_subscriptions = Subscription.query.filter_by(status=SubscriptionStatus.ACTIVE).count()
    pending_sar_applications = SARApplication.query.filter_by(status=SARStatus.SUBMITTED).count()
    
    # Get recent activities
    recent_registrations = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_sar_applications = SARApplication.query.order_by(SARApplication.created_at.desc()).limit(5).all()
    
    # Get subscription data for chart
    current_year = datetime.now().year
    subscription_data = []
    for month in range(1, 13):
        start_date = datetime(current_year, month, 1)
        if month == 12:
            end_date = datetime(current_year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(current_year, month + 1, 1) - timedelta(seconds=1)
        
        count = Subscription.query.filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.start_date >= start_date,
            Subscription.start_date <= end_date
        ).count()
        
        subscription_data.append({
            'month': start_date.strftime('%b'),
            'count': count
        })
    
    return render_template(
        'admin/dashboard.html',
        total_members=total_members,
        pending_verifications=pending_verifications,
        active_subscriptions=active_subscriptions,
        pending_sar_applications=pending_sar_applications,
        recent_registrations=recent_registrations,
        recent_sar_applications=recent_sar_applications,
        subscription_data=subscription_data
    )

@admin_bp.route('/members')
@admin_required
def members():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )
    
    members = query.order_by(User.created_at.desc()).paginate(page=page, per_page=10)
    
    return render_template('admin/members.html', members=members, search=search)

@admin_bp.route('/member/<int:user_id>')
@admin_required
def member_detail(user_id):
    user = User.query.get_or_404(user_id)
    profile = MemberProfile.query.filter_by(user_id=user_id).first()
    
    role_form = UserRoleForm()
    role_form.role.data = user.role.value if user.role else UserRole.MEMBER.value
    
    verification_form = None
    if profile:
        verification_form = ProfileVerificationForm()
        verification_form.status.data = profile.verification_status.value if profile.verification_status else VerificationStatus.PENDING.value
        verification_form.comments.data = profile.comments
    
    subscriptions = Subscription.query.filter_by(user_id=user_id).order_by(Subscription.year.desc()).all()
    sar_applications = SARApplication.query.filter_by(user_id=user_id).order_by(SARApplication.created_at.desc()).all()
    
    return render_template(
        'admin/member_detail.html',
        user=user,
        profile=profile,
        role_form=role_form,
        verification_form=verification_form,
        subscriptions=subscriptions,
        sar_applications=sar_applications
    )

@admin_bp.route('/member/<int:user_id>/update-role', methods=['POST'])
@admin_required
def update_role(user_id):
    user = User.query.get_or_404(user_id)
    
    # Only super admins can update roles
    if current_user.role != UserRole.SUPER_ADMIN:
        flash('You do not have permission to update user roles.', 'danger')
        return redirect(url_for('admin.member_detail', user_id=user_id))
    
    form = UserRoleForm()
    if form.validate_on_submit():
        # Don't allow changing super admin role unless you are a super admin
        if user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
            flash('You cannot change the role of a Super Admin.', 'danger')
        else:
            old_role = user.role.value if user.role else "None"
            user.role = UserRole(form.role.data)
            db.session.commit()
            
            # Log the action
            audit_log = AuditLog(
                user_id=current_user.id,
                action="Updated user role",
                resource_type="User",
                resource_id=user.id,
                details=f"Changed role from {old_role} to {user.role.value}",
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
            db.session.commit()
            
            flash(f'User role updated to {user.role.value}.', 'success')
    
    return redirect(url_for('admin.member_detail', user_id=user_id))

@admin_bp.route('/member/<int:user_id>/verify-profile', methods=['POST'])
@admin_required
def verify_profile(user_id):
    profile = MemberProfile.query.filter_by(user_id=user_id).first_or_404()
    user = User.query.get_or_404(user_id)
    
    form = ProfileVerificationForm()
    if form.validate_on_submit():
        old_status = profile.verification_status.value if profile.verification_status else "None"
        profile.verification_status = VerificationStatus(form.status.data)
        profile.comments = form.comments.data
        profile.verified_by = current_user.id
        profile.verification_date = datetime.utcnow()
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Updated profile verification status",
            resource_type="MemberProfile",
            resource_id=profile.id,
            details=f"Changed status from {old_status} to {profile.verification_status.value}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Send email notification to user
        if profile.verification_status == VerificationStatus.VERIFIED:
            send_verification_approval_email(user.email)
            flash('Profile verified and notification email sent.', 'success')
        else:
            flash(f'Profile verification status updated to {profile.verification_status.value}.', 'success')
    
    return redirect(url_for('admin.member_detail', user_id=user_id))

@admin_bp.route('/subscriptions')
@admin_required
def subscriptions():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    year = request.args.get('year', datetime.now().year, type=int)
    
    query = Subscription.query
    
    if status:
        query = query.filter_by(status=SubscriptionStatus(status))
    
    if year:
        query = query.filter_by(year=year)
    
    subscriptions = query.order_by(Subscription.updated_at.desc()).paginate(page=page, per_page=10)
    
    # Get unique years for filter
    years = db.session.query(Subscription.year).distinct().order_by(Subscription.year.desc()).all()
    years = [y[0] for y in years]
    
    return render_template(
        'admin/subscriptions.html',
        subscriptions=subscriptions,
        status=status,
        year=year,
        years=years,
        statuses=[s.value for s in SubscriptionStatus],
        User=User
    )

@admin_bp.route('/sar-applications')
@admin_required
def sar_applications():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = SARApplication.query
    
    if status:
        query = query.filter_by(status=SARStatus(status))
    
    applications = query.order_by(SARApplication.updated_at.desc()).paginate(page=page, per_page=10)
    
    return render_template(
        'admin/sar_applications.html',
        applications=applications,
        status=status,
        statuses=[s.value for s in SARStatus]
    )

@admin_bp.route('/sar-application/<int:application_id>')
@admin_required
def sar_application_detail(application_id):
    application = SARApplication.query.get_or_404(application_id)
    user = User.query.get(application.user_id)
    
    review_form = SARReviewForm()
    review_form.status.data = application.status.value if application.status else SARStatus.SUBMITTED.value
    review_form.comments.data = application.review_comments
    
    return render_template(
        'admin/sar_application_detail.html',
        application=application,
        user=user,
        review_form=review_form
    )

@admin_bp.route('/sar-application/<int:application_id>/review', methods=['POST'])
@admin_required
def review_sar_application(application_id):
    application = SARApplication.query.get_or_404(application_id)
    user = User.query.get(application.user_id)
    
    form = SARReviewForm()
    if form.validate_on_submit():
        old_status = application.status.value if application.status else "None"
        application.status = SARStatus(form.status.data)
        application.review_comments = form.comments.data
        application.reviewer_id = current_user.id
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Updated SAR application status",
            resource_type="SARApplication",
            resource_id=application.id,
            details=f"Changed status from {old_status} to {application.status.value}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Send email notification to user if approved
        if application.status == SARStatus.APPROVED:
            send_sar_approval_email(user.email, application)
            flash('SAR application approved and notification email sent.', 'success')
        else:
            flash(f'SAR application status updated to {application.status.value}.', 'success')
    
    return redirect(url_for('admin.sar_application_detail', application_id=application_id))

@admin_bp.route('/reports')
@admin_required
def reports():
    report_type = request.args.get('type', 'members')
    
    data = {}
    
    if report_type == 'members':
        # Members by verification status
        verification_stats = db.session.query(
            MemberProfile.verification_status,
            func.count(MemberProfile.id)
        ).group_by(MemberProfile.verification_status).all()
        
        data['verification_stats'] = {
            status.value: count for status, count in verification_stats
        }
        
        # Members by registration date (monthly)
        current_year = datetime.now().year
        monthly_registrations = []
        for month in range(1, 13):
            start_date = datetime(current_year, month, 1)
            if month == 12:
                end_date = datetime(current_year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(current_year, month + 1, 1) - timedelta(seconds=1)
            
            count = User.query.filter(
                User.created_at >= start_date,
                User.created_at <= end_date
            ).count()
            
            monthly_registrations.append({
                'month': start_date.strftime('%b'),
                'count': count
            })
        
        data['monthly_registrations'] = monthly_registrations
    
    elif report_type == 'subscriptions':
        # Subscriptions by status
        subscription_stats = db.session.query(
            Subscription.status,
            func.count(Subscription.id)
        ).group_by(Subscription.status).all()
        
        data['subscription_stats'] = {
            status.value: count for status, count in subscription_stats
        }
        
        # Subscriptions by year
        yearly_subscriptions = db.session.query(
            Subscription.year,
            func.count(Subscription.id)
        ).group_by(Subscription.year).order_by(Subscription.year).all()
        
        data['yearly_subscriptions'] = {
            year: count for year, count in yearly_subscriptions
        }
    
    elif report_type == 'sar':
        # SAR applications by status
        sar_stats = db.session.query(
            SARApplication.status,
            func.count(SARApplication.id)
        ).group_by(SARApplication.status).all()
        
        data['sar_stats'] = {
            status.value: count for status, count in sar_stats
        }
        
        # SAR applications by month (current year)
        current_year = datetime.now().year
        monthly_applications = []
        for month in range(1, 13):
            start_date = datetime(current_year, month, 1)
            if month == 12:
                end_date = datetime(current_year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(current_year, month + 1, 1) - timedelta(seconds=1)
            
            count = SARApplication.query.filter(
                SARApplication.created_at >= start_date,
                SARApplication.created_at <= end_date
            ).count()
            
            monthly_applications.append({
                'month': start_date.strftime('%b'),
                'count': count
            })
        
        data['monthly_applications'] = monthly_applications
    
    return render_template('admin/reports.html', report_type=report_type, data=data)

@admin_bp.route('/notification-settings')
@admin_required
def notification_settings():
    settings = NotificationSetting.query.all()
    
    return render_template(
        'admin/notification_settings.html',
        settings=settings
    )

@admin_bp.route('/notification-settings/<int:setting_id>', methods=['GET', 'POST'])
@admin_required
def edit_notification_setting(setting_id):
    setting = NotificationSetting.query.get_or_404(setting_id)
    
    # Create the appropriate form based on the notification type
    if setting.name in ['sms_notifications', 'whatsapp_notifications']:
        form = TwilioSettingsForm()
        if request.method == 'GET':
            if setting.config_values:
                form.account_sid.data = setting.config_values.get('account_sid', '')
                form.auth_token.data = setting.config_values.get('auth_token', '')
                form.phone_number.data = setting.config_values.get('phone_number', '')
    else:
        form = NotificationSettingForm()
        if request.method == 'GET':
            form.is_enabled.data = setting.is_enabled
            if setting.config_values:
                form.config_values.data = json.dumps(setting.config_values, indent=2)
    
    if form.validate_on_submit():
        old_enabled = setting.is_enabled
        
        if isinstance(form, TwilioSettingsForm):
            # Update Twilio settings
            config = {
                'account_sid': form.account_sid.data,
                'auth_token': form.auth_token.data,
                'phone_number': form.phone_number.data
            }
            setting.config_values = config
            setting.is_enabled = all(config.values())  # Enable only if all fields are filled
        else:
            # Update general settings
            setting.is_enabled = form.is_enabled.data
            if form.config_values.data:
                try:
                    setting.config_values = json.loads(form.config_values.data)
                except json.JSONDecodeError:
                    flash('Invalid JSON format for configuration values', 'danger')
                    return render_template(
                        'admin/edit_notification_setting.html',
                        setting=setting,
                        form=form
                    )
        
        db.session.commit()
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Updated notification setting",
            resource_type="NotificationSetting",
            resource_id=setting.id,
            details=f"Changed {setting.name} enabled from {old_enabled} to {setting.is_enabled}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash(f'Notification setting "{setting.display_name}" updated successfully.', 'success')
        return redirect(url_for('admin.notification_settings'))
    
    return render_template(
        'admin/edit_notification_setting.html',
        setting=setting,
        form=form
    )

@admin_bp.route('/audit-logs')
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '')
    resource_type = request.args.get('resource_type', '')
    
    query = AuditLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=20)
    
    # Get unique resource types for filter
    resource_types = db.session.query(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type).all()
    resource_types = [rt[0] for rt in resource_types if rt[0]]
    
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_types=resource_types
    )

@admin_bp.route('/chat-rooms')
@admin_required
def chat_rooms():
    rooms = ChatRoom.query.order_by(ChatRoom.created_at.desc()).all()
    form = ChatRoomForm()
    
    return render_template('admin/chat_rooms.html', rooms=rooms, form=form)

@admin_bp.route('/chat-rooms/create', methods=['POST'])
@admin_required
def create_chat_room():
    form = ChatRoomForm()
    
    if form.validate_on_submit():
        is_private = form.is_private.data == 'True'
        
        room = ChatRoom(
            name=form.name.data,
            description=form.description.data,
            is_private=is_private,
            created_by=current_user.id
        )
        
        db.session.add(room)
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="Created chat room",
            resource_type="ChatRoom",
            resource_id=room.id,
            details=f"Room name: {room.name}, Private: {room.is_private}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        flash(f'Chat room "{room.name}" created successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('admin.chat_rooms'))

@admin_bp.route('/chat-rooms/<int:room_id>/delete', methods=['POST'])
@admin_required
def delete_chat_room(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    
    # Only super admins or the creator can delete a room
    if current_user.role != UserRole.SUPER_ADMIN and room.created_by != current_user.id:
        flash('You do not have permission to delete this chat room.', 'danger')
        return redirect(url_for('admin.chat_rooms'))
    
    room_name = room.name
    
    # Log the action before deleting
    audit_log = AuditLog(
        user_id=current_user.id,
        action="Deleted chat room",
        resource_type="ChatRoom",
        resource_id=room.id,
        details=f"Room name: {room.name}",
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit_log)
    
    db.session.delete(room)
    db.session.commit()
    
    flash(f'Chat room "{room_name}" deleted successfully.', 'success')
    return redirect(url_for('admin.chat_rooms'))
