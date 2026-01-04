"""
QR code generator for easy mobile access
"""
import qrcode
import io
import base64
from pathlib import Path

class QRCodeGenerator:
    """Generates QR codes for URLs"""
    
    def __init__(self):
        self.qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
    
    def generate_qr(self, url: str) -> str:
        """
        Generate QR code for URL
        Returns base64 encoded PNG image
        """
        self.qr.clear()
        self.qr.add_data(url)
        self.qr.make(fit=True)
        
        img = self.qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        return img_base64
    
    def save_qr_to_file(self, url: str, output_path: Path):
        """Save QR code to file"""
        self.qr.clear()
        self.qr.add_data(url)
        self.qr.make(fit=True)
        
        img = self.qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)