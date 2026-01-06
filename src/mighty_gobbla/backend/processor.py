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

def list_available_models():
    """List all models supporting generateContent."""
    try:
        available = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available.append(m.name)
        return available
    except Exception as e:
        logger.error(f"Could not list models: {e}")
        return []

def process_document(file_path):
    """
    Uses Google Gemini Flash to extract structured data from receipts.
    Replaces local OCR entirely.
    """
    logger.info(f"Sending {file_path} to Gemini Vision...")
    
    # Candidate models to try in order of preference
    # 'gemini-1.5-flash' is best balance. 'gemini-pro-vision' is legacy fallback.
    candidates = [
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro", 
        "gemini-pro-vision"
    ]

    # Read file bytes once
    try:
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = "image/jpeg"
        if ext == ".png": mime_type = "image/png"
        elif ext == ".pdf": mime_type = "application/pdf"
        
        with open(file_path, "rb") as f:
            file_data = f.read()
    except Exception as e:
         logger.error(f"Failed to read file: {e}")
         return {"store": "FileError", "amount": 0.0, "date": "240101"}

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

    last_error = None
    
    for model_name in candidates:
        try:
            logger.info(f"Attempting with model: {model_name}")
            model = genai.GenerativeModel(model_name)

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
            data["raw_text_debug"] = f"Gemini Success ({model_name})"
            logger.info(f"Success with {model_name}")
            
            # Validate keys exist
            if "date" not in data: data["date"] = datetime.now().strftime("%y%m%d")
            if "store" not in data: data["store"] = "Unknown"
            if "payment" not in data: data["payment"] = "Unknown"
            if "amount" not in data: data["amount"] = 0.0
            
            return data

        except Exception as e:
            logger.warning(f"Failed with {model_name}: {e}")
            last_error = e
            # Continue to next candidate
            
    # If we get here, all failed
    logger.error("All Gemini models failed.")
    
    # Log available models to help debug
    available = list_available_models()
    logger.info(f"Available models on server: {available}")
    
    return {
        "date": datetime.now().strftime("%y%m%d"),
        "store": "Error",
        "payment": "Unknown",
        "amount": 0.0,
        "raw_text_debug": f"All Gemini Models Failed. Available: {available}. Last Error: {str(last_error)}"
    }
