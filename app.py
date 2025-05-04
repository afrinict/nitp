import os
import logging
from datetime import datetime

from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize Flask extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
socketio = SocketIO()

# Create the Flask application
app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure application settings
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///nigeria_urban_planner.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configure email for development
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "localhost")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 1025))
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@nigeriaturbanplanner.com")

# Configure file uploads
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

# Initialize extensions with the app
db.init_app(app)

# Initialize other extensions
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

mail.init_app(app)
csrf.init_app(app)
socketio.init_app(app)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# Create upload folders for different file types
upload_folders = [
    app.config["UPLOAD_FOLDER"],  # Base uploads folder
    os.path.join(app.config["UPLOAD_FOLDER"], "sar_documents"),
    os.path.join(app.config["UPLOAD_FOLDER"], "certificates"),
    os.path.join(app.config["UPLOAD_FOLDER"], "qr_codes"),
    os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "qr_codes"),
    os.path.join(app.config["UPLOAD_FOLDER"], "profile_documents"),
]

# Create all necessary folders
for folder in upload_folders:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Import models (must be done after db initialization)
with app.app_context():
    import models
    db.create_all()

# Function to initialize notification settings
def init_notification_settings():
    from models import NotificationSetting
    
    # Initialize notification settings if they don't exist
    default_settings = [
        {
            'name': 'email_notifications',
            'display_name': 'Email Notifications',
            'description': 'Send notifications via email to members and administrators.',
            'is_enabled': True,
            'config_values': {}
        },
        {
            'name': 'sms_notifications',
            'display_name': 'SMS Notifications',
            'description': 'Send notifications via SMS to members and administrators. Requires Twilio credentials.',
            'is_enabled': False,
            'config_values': {
                'account_sid': '',
                'auth_token': '',
                'phone_number': ''
            }
        },
        {
            'name': 'whatsapp_notifications',
            'display_name': 'WhatsApp Notifications',
            'description': 'Send notifications via WhatsApp to members and administrators. Requires Twilio credentials.',
            'is_enabled': False,
            'config_values': {
                'account_sid': '',
                'auth_token': '',
                'phone_number': ''
            }
        }
    ]
    
    # Add default settings if they don't exist
    for setting in default_settings:
        existing = NotificationSetting.query.filter_by(name=setting['name']).first()
        if not existing:
            new_setting = NotificationSetting(
                name=setting['name'],
                display_name=setting['display_name'],
                description=setting['description'],
                is_enabled=setting['is_enabled'],
                config_values=setting['config_values']
            )
            db.session.add(new_setting)
    
    # Commit changes
    db.session.commit()

# Initialize notification settings after all models are loaded
with app.app_context():
    # The import is needed to make sure all models are fully defined
    from models import User, NotificationSetting
    init_notification_settings()

# Set up login manager
from models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprints
from routes.auth import auth_bp
from routes.member import member_bp
from routes.subscription import subscription_bp
from routes.sar import sar_bp
from routes.admin import admin_bp
from routes.chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(member_bp)
app.register_blueprint(subscription_bp)
app.register_blueprint(sar_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(chat_bp)

# Context processor for templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Custom template filters
@app.template_filter('format_number')
def format_number(value):
    """Format a number with commas as thousand separators"""
    try:
        return "{:,}".format(float(value))
    except (ValueError, TypeError):
        return value

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Create temporary/mock templates for error pages
with app.app_context():
    if not os.path.exists(os.path.join(app.template_folder, '404.html')):
        with open(os.path.join(app.template_folder, '404.html'), 'w') as f:
            f.write("""{% extends 'layout.html' %}
{% block content %}
<div class="container mt-5">
    <div class="alert alert-danger">
        <h4>404 - Page Not Found</h4>
        <p>The requested page could not be found.</p>
        <a href="{{ url_for('index') }}" class="btn btn-primary">Return to Home</a>
    </div>
</div>
{% endblock %}""")
    
    if not os.path.exists(os.path.join(app.template_folder, '500.html')):
        with open(os.path.join(app.template_folder, '500.html'), 'w') as f:
            f.write("""{% extends 'layout.html' %}
{% block content %}
<div class="container mt-5">
    <div class="alert alert-danger">
        <h4>500 - Internal Server Error</h4>
        <p>An internal server error occurred. Please try again later.</p>
        <a href="{{ url_for('index') }}" class="btn btn-primary">Return to Home</a>
    </div>
</div>
{% endblock %}""")
