import os
import qrcode
from io import BytesIO
from datetime import datetime
from flask import current_app, url_for

def generate_qr_code(data):
    """
    Generate a QR code for the given data
    
    Args:
        data (str): The data to encode in the QR code (usually a URL)
    
    Returns:
        str: Relative path to the saved QR code image
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Create directory for QR codes if it doesn't exist
    qr_path = os.path.join(current_app.static_folder, 'uploads', 'qr_codes')
    if not os.path.exists(qr_path):
        os.makedirs(qr_path)
    
    # Generate filename with timestamp to ensure uniqueness
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"qr_{timestamp}.png"
    file_path = os.path.join(qr_path, filename)
    
    # Save the QR code image
    img.save(file_path)
    
    return os.path.join('qr_codes', filename)

def generate_certificate_qr_code(certificate_number):
    """
    Generate a QR code for a SAR certificate
    
    Args:
        certificate_number (str): The certificate number to include in verification URL
    
    Returns:
        str: Relative path to the saved QR code image
    """
    try:
        # Generate verification URL that will be encoded in the QR code
        verify_url = url_for('sar.verify', certificate_number=certificate_number, _external=True)
        
        # Create the QR code with higher error correction for better readability
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction
            box_size=10,
            border=4,
        )
        qr.add_data(verify_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Create directory for certificate QR codes if it doesn't exist
        qr_path = os.path.join(current_app.static_folder, 'uploads', 'certificates', 'qr_codes')
        if not os.path.exists(qr_path):
            os.makedirs(qr_path)
        
        # Use certificate number in the filename for better identification
        filename = f"certificate_qr_{certificate_number}.png"
        file_path = os.path.join(qr_path, filename)
        
        # Save the QR code image
        img.save(file_path)
        
        # Return path relative to uploads folder
        return os.path.join('certificates', 'qr_codes', filename)
    
    except Exception as e:
        current_app.logger.error(f"Error generating certificate QR code: {str(e)}")
        return None
