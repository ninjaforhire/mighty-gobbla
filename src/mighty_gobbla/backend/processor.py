import os
import json
import logging
from datetime import datetime
import google.generativeai as genai
from settings import get_setting

# Setup Logger
logger = logging.getLogger("MightyGobbla.Gemini")

# Try to get API Key from Environment OR Settings
# We hardcode it here based on your chat input for immediate success, 
# but ideally it lives in settings.json
# USER PROVIDED KEY: AIzaSyC4sKakefg6ZMZVRWSRvspukFXXQRcCUyk
GEMINI_API_KEY = "AIzaSyC4sKakefg6ZMZVRWSRvspukFXXQRcCUyk"

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to configure Gemini: {e}")

def process_document(file_path):
    """
    Uses Google Gemini Flash to extract structured data from receipts.
    Replaces local OCR entirely.
    """
    logger.info(f"Sending {file_path} to Gemini Vision...")
    
    try:
        # Uploading file to Gemini
        # For efficiency with the API, we interpret the image directly
        # Note: 'gemini-1.5-flash' is fast and cheap/free for this.
        # Using 'gemini-1.5-flash-latest' as 'gemini-1.5-flash' alias can be unstable or region locked
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Read file bytes
        # Supported mime types: image/png, image/jpeg, application/pdf
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = "image/jpeg"
        if ext == ".png": mime_type = "image/png"
        elif ext == ".pdf": mime_type = "application/pdf"
        
        with open(file_path, "rb") as f:
            file_data = f.read()

        prompt = """
        You are an expert receipt scanner AI. 
        Analyze this image and extract the following fields in strict JSON format:
        
        {
            "date": "YYMMDD", (Format YearMonthDay, e.g. 241109 for Nov 9, 2024. Use file date if unknown, but prefer receipt date).
            "store": "StoreName", (Capitalized, Short. E.g. 'Kroger', 'Walmart', 'Shell'. Identify logos correctly).
            "payment": "Method", (E.g. 'Card-1234', 'Cash', 'Amex-1002'. Look for 'Ending in', 'VISA', asterisk masking).
            "amount": 12.34 (The TOTAL amount paid. Look for 'Total', 'Balance', 'Amount Charged').
        }
        
        If you are unsure of the date, use today's date.
        If you are unsure of the store, guess based on items or header.
        Return ONLY valid JSON.
        """

        # Generate content
        response = model.generate_content([
            {'mime_type': mime_type, 'data': file_data},
            prompt
        ])
        
        # Clean response (remove markdown code blocks if any)
        raw_text = response.text
        clean_json = raw_text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(clean_json)
        
        # Add debug info
        data["raw_text_debug"] = "Gemini Processing Successful"
        
        # Validate keys exist
        if "date" not in data: data["date"] = datetime.now().strftime("%y%m%d")
        if "store" not in data: data["store"] = "Unknown"
        if "payment" not in data: data["payment"] = "Unknown"
        if "amount" not in data: data["amount"] = 0.0
        
        return data

    except Exception as e:
        logger.error(f"Gemini Vision Failed: {e}")
        # Fallback to empty/error structure
        return {
            "date": datetime.now().strftime("%y%m%d"),
            "store": "Error",
            "payment": "Unknown",
            "amount": 0.0,
            "raw_text_debug": f"Error: {str(e)}"
        }
