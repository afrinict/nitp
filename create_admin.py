import os
from app import app, db
from models import User, UserRole
from werkzeug.security import generate_password_hash

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def create_admin_user():
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()

        # Check if admin user already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists!")
            return

        # Create admin user
        admin = User(
            email='admin@nigeriaturbanplanner.com',
            username='admin',
            password_hash=generate_password_hash('admin123'),
            first_name='Admin',
            last_name='User',
            phone_number='08012345678',
            address='Admin Address',
            city='Lagos',
            state='Lagos',
            role=UserRole.ADMIN,
            is_active=True
        )

        # Add to database
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")

if __name__ == '__main__':
    create_admin_user()
