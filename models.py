from datetime import datetime
import enum
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import Enum
from app import db

class UserRole(enum.Enum):
    MEMBER = "member"
    ADMIN = "admin"
    STAFF = "staff"
    SUPER_ADMIN = "super_admin"

class VerificationStatus(enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class SARStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_COMPLETED = "payment_completed"
    CERTIFICATE_GENERATED = "certificate_generated"
    CERTIFICATE_DELIVERED = "certificate_delivered"
    REJECTED = "rejected"

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(64), nullable=False)
    state = db.Column(db.String(64), nullable=False)
    role = db.Column(Enum(UserRole), default=UserRole.MEMBER)
    is_active = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('MemberProfile', backref='user', uselist=False)
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic')
    sar_applications = db.relationship('SARApplication', backref='user', lazy='dynamic')
    sent_messages = db.relationship('Message', 
                                   foreign_keys='Message.sender_id',
                                   backref='sender', 
                                   lazy='dynamic')
    received_messages = db.relationship('Message', 
                                       foreign_keys='Message.recipient_id',
                                       backref='recipient', 
                                       lazy='dynamic')
    chat_rooms = db.relationship('ChatRoom', 
                                secondary='chat_room_members',
                                backref=db.backref('members', lazy='dynamic'))
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_active_subscription(self):
        active_sub = Subscription.query.filter_by(
            user_id=self.id, 
            status=SubscriptionStatus.ACTIVE
        ).first()
        return active_sub is not None
    
    def __repr__(self):
        return f'<User {self.username}>'

class MemberProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    secondary_school = db.Column(db.String(128))
    secondary_school_start_year = db.Column(db.Integer)
    secondary_school_end_year = db.Column(db.Integer)
    secondary_school_cert_path = db.Column(db.String(255))
    higher_institution = db.Column(db.String(128))
    higher_institution_start_year = db.Column(db.Integer)
    higher_institution_end_year = db.Column(db.Integer)
    higher_institution_cert_path = db.Column(db.String(255))
    degree_type = db.Column(db.String(64))  # HND or BSc
    verification_status = db.Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verification_date = db.Column(db.DateTime, nullable=True)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MemberProfile {self.user_id}>'

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    status = db.Column(Enum(SubscriptionStatus), default=SubscriptionStatus.PENDING)
    payment_reference = db.Column(db.String(100))
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Subscription {self.user_id} - {self.year}>'

class SARApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title_document_path = db.Column(db.String(255))
    cofo_document_path = db.Column(db.String(255))
    ownership_proof_path = db.Column(db.String(255))
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    site_address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(64))
    state = db.Column(db.String(64))
    status = db.Column(Enum(SARStatus), default=SARStatus.DRAFT)
    reference_number = db.Column(db.String(64), unique=True)
    payment_amount = db.Column(db.Float, nullable=True)
    payment_reference = db.Column(db.String(100))
    payment_status = db.Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_comments = db.Column(db.Text)
    certificate_path = db.Column(db.String(255))
    certificate_number = db.Column(db.String(64), unique=True, nullable=True)
    qr_code_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship for reviewer
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    
    def __repr__(self):
        return f'<SARApplication {self.reference_number}>'

class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_private = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship for creator
    creator = db.relationship('User', foreign_keys=[created_by])
    
    # Relationship for messages
    messages = db.relationship('ChatMessage', backref='chat_room', lazy='dynamic')
    
    def __repr__(self):
        return f'<ChatRoom {self.name}>'

class ChatRoomMember(db.Model):
    __tablename__ = 'chat_room_members'
    id = db.Column(db.Integer, primary_key=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship for sender
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<ChatMessage {self.id}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id}>'

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AuditLog {self.id}>'

class EmailVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), nullable=False, unique=True)
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User')

class NotificationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_enabled = db.Column(db.Boolean, default=False)
    config_values = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<NotificationSetting {self.name}: {"Enabled" if self.is_enabled else "Disabled"}>'
