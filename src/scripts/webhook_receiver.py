import os
import subprocess
import json
import hmac
import hashlib
import sys
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configure logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Error log for critical issues
ERROR_LOG_PATH = ".tmp/sync_errors.log"
os.makedirs(".tmp", exist_ok=True)
error_handler = logging.FileHandler(ERROR_LOG_PATH)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(error_handler)

# Config
PYTHON_PATH = r"C:\Users\andre\AppData\Local\Programs\Python\Python311\python.exe"
SYNC_SCRIPT = "src/scripts/sync_quo_to_notion.py"
WEBHOOK_SECRET = os.getenv("OPENPHONE_WEBHOOK_SECRET")
SIGNATURE_HEADER = "openphone-signature-hash"

def verify_signature(data, full_signature_header):
    """
    OpenPhone signature format: hmac;1;timestamp;signature
    We must sign: f"{timestamp}:{raw_body_data}"
    """
    if not WEBHOOK_SECRET:
        logger.info("No WEBHOOK_SECRET configured, skipping verification.")
        return True
    
    try:
        import base64
        parts = full_signature_header.split(';')
        if len(parts) != 4:
           logger.error(f"Invalid signature format: {full_signature_header}")
           return False
        
        timestamp = parts[2]
        received_signature = parts[3]
        
        # Determine if secret needs decoding
        try:
            key = base64.b64decode(WEBHOOK_SECRET)
            if len(key) < 16: # Probably not a real key if it's too short
                key = WEBHOOK_SECRET.encode()
        except Exception:
            key = WEBHOOK_SECRET.encode()
        
        # Payload to sign is timestamp + ":" + raw_body
        message = f"{timestamp}:".encode() + data
        
        mac = hmac.new(key, message, hashlib.sha256)
        expected_signature = base64.b64encode(mac.digest()).decode()
        
        is_valid = hmac.compare_digest(expected_signature, received_signature)
        if not is_valid:
            # Try without colon as fallback
            msg2 = f"{timestamp}".encode() + data
            mac2 = hmac.new(key, msg2, hashlib.sha256)
            expected2 = base64.b64encode(mac2.digest()).decode()
            if hmac.compare_digest(expected2, received_signature):
                logger.info("Signature matched without colon!")
                return True
            
            logger.warning(f"Signature mismatch! Received: {received_signature}, Expected (w/ colon): {expected_signature}, Expected (no colon): {expected2}")
        return is_valid
    except Exception as e:
        logger.error(f"Error during signature verification: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Receives webhook from Quo, verifies signature, and pipes it to the sync script.
    """
    # Verify Signature
    signature_header = request.headers.get(SIGNATURE_HEADER)
    if not signature_header:
        logger.error(f"Missing {SIGNATURE_HEADER} header")
        return jsonify({"status": "error", "message": f"Missing {SIGNATURE_HEADER}"}), 401
    
    if not verify_signature(request.data, signature_header):
        logger.error("Invalid signature")
        return jsonify({"status": "error", "message": "Invalid signature"}), 401

    payload = request.json
    if not payload:
        return jsonify({"status": "error", "message": "No JSON payload received"}), 400

    logger.info(f"Received webhook event. Routing to {SYNC_SCRIPT}...")
    
    try:
        # Run the sync script and pass the payload via stdin
        process = subprocess.Popen(
            [PYTHON_PATH, SYNC_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=json.dumps(payload))
        
        if process.returncode != 0:
            logger.error(f"Sync script failed with code {process.returncode}")
            logger.error(f"Error: {stderr}")
            return jsonify({"status": "error", "message": "Sync script failed", "details": stderr}), 500
        
        # Parse the result from the sync script
        result = json.loads(stdout)
        logger.info(f"Sync script result: {result}")
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error executing sync script: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Run on port 5000 by default
    app.run(port=5000, debug=True)
