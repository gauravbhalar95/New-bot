import os
import base64
from pathlib import Path

def setup_ssl_files():
    """Setup SSL certificate files from environment variables or create self-signed ones."""
    certs_dir = Path(__file__).parent / 'certs'
    certs_dir.mkdir(exist_ok=True)
    
    cert_path = certs_dir / 'cert.pem'
    key_path = certs_dir / 'private.key'
    
    # If SSL files don't exist, create self-signed ones
    if not (cert_path.exists() and key_path.exists()):
        os.system(f'openssl req -newkey rsa:2048 -sha256 -nodes '
                 f'-keyout {key_path} -x509 -days 365 -out {cert_path} '
                 f'-subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"')
        
        # Set proper permissions
        os.chmod(key_path, 0o600)
        os.chmod(cert_path, 0o644)
    
    return cert_path, key_path

def encode_ssl_files():
    """Encode SSL files to base64 for environment variables."""
    cert_path, key_path = setup_ssl_files()
    
    with open(cert_path, 'rb') as f:
        cert_base64 = base64.b64encode(f.read()).decode()
    
    with open(key_path, 'rb') as f:
        key_base64 = base64.b64encode(f.read()).decode()
    
    return cert_base64, key_base64