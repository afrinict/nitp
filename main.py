import logging
from app import app, socketio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Initialize the application
    with app.app_context():
        # Create database tables if they don't exist
        from app import db
        db.create_all()
        
        # Initialize notification settings
        from app import init_notification_settings
        init_notification_settings()
    
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
