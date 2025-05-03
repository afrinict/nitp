import os
import io
import uuid
from datetime import datetime
from fpdf import FPDF
from flask import current_app, url_for
from PIL import Image

from .qrcode import generate_certificate_qr_code
from .notification import notify_certificate_generation

def generate_certificate_number():
    """
    Generate a unique certificate number
    
    Returns:
        str: Certificate number in format 'NITP-SAR-YYYYMMDD-XXXX'
    """
    # Generate timestamp and random components
    timestamp = datetime.now().strftime("%Y%m%d")
    random_component = uuid.uuid4().hex[:4].upper()
    
    # Format certificate number
    certificate_number = f"NITP-SAR-{timestamp}-{random_component}"
    
    return certificate_number

def generate_sar_certificate(application, user=None):
    """
    Generate a PDF certificate for a SAR application and send notifications
    
    Args:
        application: SARApplication object
        user: User object (optional, will be fetched from application if not provided)
    
    Returns:
        tuple: (certificate_path, qr_code_path, notification_status)
    """
    try:
        # Get user details if not provided
        if not user:
            user = application.user
        
        # Generate certificate number if not already assigned
        if not application.certificate_number:
            application.certificate_number = generate_certificate_number()
            
        # Generate QR code first
        qr_code_path = generate_certificate_qr_code(application.certificate_number)
        if not qr_code_path:
            current_app.logger.error(f"Failed to generate QR code for certificate {application.certificate_number}")
            return None, None, {"error": "Failed to generate QR code"}
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        
        # Check if custom fonts are available, otherwise use standard fonts
        try:
            pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
            pdf.add_font('DejaVu', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)
            title_font = 'DejaVu'
        except Exception as e:
            current_app.logger.warning(f"Custom fonts not available, using standard fonts: {str(e)}")
            title_font = 'Arial'
        
        # Title
        pdf.set_font(title_font, 'B', 24)
        pdf.cell(0, 20, 'NIGERIA INSTITUTE OF TOWN PLANNERS', 0, 1, 'C')
        pdf.set_font(title_font, 'B', 20)
        pdf.cell(0, 10, 'ABUJA CHAPTER', 0, 1, 'C')
        
        # Certificate title
        pdf.ln(10)
        pdf.set_font(title_font, 'B', 18)
        pdf.cell(0, 10, 'SITE ANALYSIS REPORT CERTIFICATE', 0, 1, 'C')
        
        # Certificate border
        pdf.rect(10, 10, 190, 277)
        pdf.rect(15, 15, 180, 267)
        
        # Certificate details
        pdf.ln(10)
        pdf.set_font(title_font, '', 12)
        pdf.cell(0, 10, f'Certificate Number: {application.certificate_number}', 0, 1)
        pdf.cell(0, 10, f'Reference Number: {application.reference_number}', 0, 1)
        pdf.cell(0, 10, f'Date Issued: {datetime.now().strftime("%d %B, %Y")}', 0, 1)
        
        # Member details
        pdf.ln(5)
        pdf.set_font(title_font, 'B', 14)
        pdf.cell(0, 10, 'Member Details:', 0, 1)
        pdf.set_font(title_font, '', 12)
        pdf.cell(0, 10, f'Name: {user.first_name} {user.last_name}', 0, 1)
        pdf.cell(0, 10, f'Email: {user.email}', 0, 1)
        pdf.cell(0, 10, f'Phone: {user.phone_number}', 0, 1)
        
        # Site details
        pdf.ln(5)
        pdf.set_font(title_font, 'B', 14)
        pdf.cell(0, 10, 'Site Details:', 0, 1)
        pdf.set_font(title_font, '', 12)
        pdf.cell(0, 10, f'Address: {application.site_address}', 0, 1)
        pdf.cell(0, 10, f'City: {application.city}', 0, 1)
        pdf.cell(0, 10, f'State: {application.state}', 0, 1)
        pdf.cell(0, 10, f'Coordinates: {application.latitude}, {application.longitude}', 0, 1)
        
        # QR code
        pdf.ln(5)
        pdf.set_font(title_font, 'B', 12)
        pdf.cell(0, 10, 'Scan QR Code to Verify Certificate:', 0, 1, 'C')
        
        # Add QR code to the PDF
        qr_full_path = os.path.join(current_app.static_folder, 'uploads', qr_code_path)
        if os.path.exists(qr_full_path):
            pdf.image(qr_full_path, x=85, y=210, w=40, h=40)
        else:
            current_app.logger.error(f"QR code file not found at {qr_full_path}")
        
        # Add verification URL
        verify_url = url_for('sar.verify', certificate_number=application.certificate_number, _external=True)
        pdf.ln(45)
        pdf.set_font(title_font, '', 10)
        pdf.cell(0, 10, f'Verify online at: {verify_url}', 0, 1, 'C')
        
        # Footer
        pdf.ln(10)
        pdf.set_font(title_font, 'B', 14)
        pdf.cell(0, 10, 'Nigeria Institute of Town Planners, Abuja Chapter', 0, 1, 'C')
        pdf.set_font(title_font, '', 10)
        pdf.cell(0, 10, 'This certificate is electronically generated and does not require physical signature.', 0, 1, 'C')
        
        # Create directory for certificates if it doesn't exist
        cert_path = os.path.join(current_app.static_folder, 'uploads', 'certificates')
        if not os.path.exists(cert_path):
            os.makedirs(cert_path)
        
        # Generate filename with certificate number
        filename = f"SAR_Certificate_{application.certificate_number}.pdf"
        file_path = os.path.join(cert_path, filename)
        
        # Save the PDF
        pdf.output(file_path)
        
        # Update application with certificate paths
        certificate_path = os.path.join('certificates', filename)
        application.certificate_path = certificate_path
        application.qr_code_path = qr_code_path
        
        # Send notifications through various channels
        notification_status = notify_certificate_generation(user, application, certificate_path)
        
        return certificate_path, qr_code_path, notification_status
        
    except Exception as e:
        current_app.logger.error(f"Error generating certificate: {str(e)}")
        return None, None, {"error": str(e)}
