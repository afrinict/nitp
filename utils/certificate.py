import os
import io
from datetime import datetime
from fpdf import FPDF
from flask import current_app
from PIL import Image

def generate_sar_certificate(application, qr_code_path):
    """
    Generate a PDF certificate for a SAR application
    
    Args:
        application: SARApplication object
        qr_code_path: Path to the QR code image
    
    Returns:
        str: Path to the generated certificate
    """
    # Get user details
    user = application.user
    
    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Set up fonts
    pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)
    
    # Title
    pdf.set_font('DejaVu', 'B', 24)
    pdf.cell(0, 20, 'NIGERIA INSTITUTE OF TOWN PLANNERS', 0, 1, 'C')
    pdf.set_font('DejaVu', 'B', 20)
    pdf.cell(0, 10, 'ABUJA CHAPTER', 0, 1, 'C')
    
    # Certificate title
    pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 18)
    pdf.cell(0, 10, 'SITE ANALYSIS REPORT CERTIFICATE', 0, 1, 'C')
    
    # Certificate border
    pdf.rect(10, 10, 190, 277)
    pdf.rect(15, 15, 180, 267)
    
    # Certificate details
    pdf.ln(10)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, f'Certificate Number: {application.certificate_number}', 0, 1)
    pdf.cell(0, 10, f'Reference Number: {application.reference_number}', 0, 1)
    pdf.cell(0, 10, f'Date Issued: {datetime.now().strftime("%d %B, %Y")}', 0, 1)
    
    # Member details
    pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 14)
    pdf.cell(0, 10, 'Member Details:', 0, 1)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, f'Name: {user.first_name} {user.last_name}', 0, 1)
    pdf.cell(0, 10, f'Email: {user.email}', 0, 1)
    pdf.cell(0, 10, f'Phone: {user.phone_number}', 0, 1)
    
    # Site details
    pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 14)
    pdf.cell(0, 10, 'Site Details:', 0, 1)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, f'Address: {application.site_address}', 0, 1)
    pdf.cell(0, 10, f'City: {application.city}', 0, 1)
    pdf.cell(0, 10, f'State: {application.state}', 0, 1)
    pdf.cell(0, 10, f'Coordinates: {application.latitude}, {application.longitude}', 0, 1)
    
    # QR code
    pdf.ln(5)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(0, 10, 'Scan QR Code to Verify Certificate:', 0, 1, 'C')
    
    qr_path = os.path.join(current_app.config['UPLOAD_FOLDER'], qr_code_path)
    pdf.image(qr_path, x=85, y=210, w=40, h=40)
    
    # Footer
    pdf.ln(50)
    pdf.set_font('DejaVu', 'B', 14)
    pdf.cell(0, 10, 'Nigeria Institute of Town Planners, Abuja Chapter', 0, 1, 'C')
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 10, 'This certificate is electronically generated and does not require physical signature.', 0, 1, 'C')
    
    # Create directory for certificates if it doesn't exist
    cert_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'certificates')
    if not os.path.exists(cert_path):
        os.makedirs(cert_path)
    
    # Generate filename with certificate number
    filename = f"SAR_Certificate_{application.certificate_number}.pdf"
    file_path = os.path.join(cert_path, filename)
    
    # Save the PDF
    pdf.output(file_path)
    
    return os.path.join('certificates', filename)
