import re
import os
import numpy as np
from datetime import datetime
import logging

# Setup Logger
logger = logging.getLogger("MightyGobbla.Processor")

try:
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    import pytesseract
    from pdf2image import convert_from_path
    import cv2
except ImportError as e:
    logger.error(f"CRITICAL IMPORT ERROR: {e}")
    # We re-raise so the app crashes and tells us causes, instead of failing silently later
    raise e

try:
    from pypdf import PdfReader
except ImportError:
    pass

# Config for Tesseract
default_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(default_tesseract):
    pytesseract.pytesseract.tesseract_cmd = default_tesseract

def smart_crop_receipt(image_path):
    """
    Simpler, more aggressive crop and enhance.
    Granite is high frequency noise. Paper is low frequency flat area.
    """
    try:
        # Read image
        image = cv2.imread(image_path)
        if image is None: return Image.open(image_path)
        
        # 1. Resize helps removing fine granite noise
        h, w = image.shape[:2]
        if h > 1000:
             scale = 1000.0 / h
             image = cv2.resize(image, (int(w*scale), 1000))
        
        # 2. Convert to Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 3. Aggressive Gaussian Blur to kill granite specs
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # 4. Threshold (Otsu) to separate paper from background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 5. Find Largest Contour (The Paper)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
        
        # If we found a contour that is big enough
        if cnts and cv2.contourArea(cnts[0]) > 5000:
            c = cnts[0]
            x, y, w, h = cv2.boundingRect(c)
            
            # Crop to the paper
            receipt_roi = image[y:y+h, x:x+w]
            
            # 6. Post-Process for OCR: Enhance Contrast & Sharpen
            # Convert back to PIL for easy enhancement
            receipt_pil = Image.fromarray(cv2.cvtColor(receipt_roi, cv2.COLOR_BGR2RGB))
            
            # Contrast
            enhancer = ImageEnhance.Contrast(receipt_pil)
            final = enhancer.enhance(2.0) # Very high contrast (black text, white paper)
            
            # Sharpen
            final = final.filter(ImageFilter.SHARPEN)
            return final
            
        # Fallback if no good contour found
        return Image.open(image_path) 
        
    except Exception as e:
        logger.error(f"Smart Crop Failed: {e}")
        return Image.open(image_path)

def extract_text_from_image(image_path):
    try:
        # 1. Get the "Clean" receipt image
        img = smart_crop_receipt(image_path)
        
        # 2. OCR with PSM 6 (Assume single uniform block of text) helps top-to-bottom reading
        # PSM 4 was column based. PSM 6 is better for a single receipt column.
        text = pytesseract.image_to_string(img, config='--psm 6')
        return text
    except:
        return ""

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t + "\n"
    except: pass
    
    # Fallback to OCR if pdf text is empty/short
    if len(text) < 50:
         try:
            images = convert_from_path(pdf_path)
            for img in images:
                 text += pytesseract.image_to_string(img)
         except: pass
    return text

def parse_date(text):
    # Try finding the specific Kroger bottom date line first
    # Format: 11/09/25 07:01pm
    match = re.search(r'(\d{2}/\d{2}/\d{2})\s+\d{2}:\d{2}', text)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%m/%d/%y")
            # Year auto-correct
            if dt.year < 100: dt = dt.replace(year=2000+dt.year)
            return dt.strftime("%y%m%d")
        except: pass

    # Generic search
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
    ]
    candidates = []
    
    current_year = datetime.now().year
    
    for line in text.split('\n'):
        for pat in patterns:
            match = re.search(pat, line, re.IGNORECASE)
            if match:
                raw = match.group(0)
                # Try multiple formats
                for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%m-%d-%y"]:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        if dt.year < 100: dt = dt.replace(year=2000+dt.year)
                        
                        # Sanity Check: Year must be near now (2000 to Next Year)
                        if 2000 <= dt.year <= (current_year + 1):
                            candidates.append(dt)
                    except: pass
    
    if candidates:
        # Sort descending (usually 'latest' date is the one, unless it's an expiration date?)
        # For receipts, transaction date is usually prominent.
        candidates.sort(reverse=True)
        return candidates[0].strftime("%y%m%d")
        
    return datetime.now().strftime("%y%m%d")

def parse_store(text):
    text_lower = text.lower()
    if "kroger" in text_lower: return "Kroger"
    
    known = {
        "snappic": "Snappic", "amazon": "Amazon", "uber": "Uber", "lyft": "Lyft", 
        "starbucks": "Starbucks", "target": "Target", "walmart": "Walmart", 
        "google": "Google", "shell": "Shell", "home depot": "HomeDepot",
        "lowes": "Lowes", "best buy": "BestBuy", "whole foods": "WholeFoods",
        "trader joes": "TraderJoes"
    }
    for k, v in known.items():
        if k in text_lower: return v
        
    # FORCE TOP LINE STRATEGY
    # Stores are ALWAYS at the top. We ignore anything below the first 5 lines.
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]
    # Filter junk words
    clean_lines = [l for l in lines if l.lower() not in ["receipt", "invoice", "copy", "sale", "transaction", "welcome", "customer copy"]]
    
    # If we have lines, scan the first one
    if clean_lines:
        first_line = clean_lines[0]
        # Remove special chars but keep spaces
        first_line = re.sub(r'[^a-zA-Z0-9 ]', '', first_line).strip()
        words = first_line.split()
        if words:
            # Return first word capitalized (e.g. "Kroger" from "Kroger Fresh")
            # If word is very short (like "The"), maybe take second? 
            w = words[0]
            if len(w) <= 2 and len(words) > 1:
                w = words[1]
            return w.capitalize()
            
    return "UnknownStore"

def parse_payment(text):
    text_lower = text.lower()
    
    # Check for "Cash" first
    if re.search(r'\bcash\b', text_lower): return "Cash"
    
    # Check for cards
    # Look for 4 digits preceded by typical keywords
    digits = re.findall(r'(?:#|x|\*|\s)(\d{4})\b', text_lower)
    # Filter out years (20xx)
    valid = [d for d in digits if not (d.startswith("20") and int(d) > 2000)]
    
    if "visa" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    if "mastercard" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    if "amex" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    
    # Generic "Card" keywords
    if any(k in text_lower for k in ["credit", "debit", "auth", "approval"]):
        if valid: return f"Card-{valid[-1]}"
        return "Card-XXXX"
    
    # If we found explicit "Card-like" masking without keywords
    if re.search(r'[\*x]{4,}\d{4}', text_lower) and valid:
         return f"Card-{valid[-1]}"
    
    # Default fallback
    return "Card-XXXX"

def parse_amount(text):
    # Looking for currency-like patterns: 12.34 or $12.34
    matches = re.findall(r'\$?\s?(\d{1,3}(?:,\d{3})*\.\d{2})', text)
    if matches:
        vals = [float(m.replace(',','')) for m in matches]
        return max(vals) # Return largest value found (Total)
    return 0.0

def process_document(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.pdf': text = extract_text_from_pdf(file_path)
        else: text = extract_text_from_image(file_path)
    except Exception as e:
        logger.error(f"Error processing doc: {e}")
        
    return {
        "date": parse_date(text),
        "store": parse_store(text),
        "payment": parse_payment(text),
        "amount": parse_amount(text),
        "raw_text_debug": text[:200]
    }
