import logging
from app import app, socketio

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
