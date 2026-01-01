import re
from datetime import datetime
import os
try:
    from PIL import Image
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:
    pass

try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not installed.")

# Config for Tesseract if likely installed
default_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(default_tesseract):
    pytesseract.pytesseract.tesseract_cmd = default_tesseract

def extract_text_from_image(image_path):
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        return text
    except:
        return ""

def extract_text_from_pdf(pdf_path):
    text = ""
    # 1. Try Native PDF Text Extraction (Fast & Accurate for digital invoices like SEMRush)
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        print(f"pypdf error: {e}")

    # 2. Fallback to OCR if text is too short (likely scanned)
    if len(text) < 50:
        print("Text too short, attempting OCR...")
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            for img in images:
                text += pytesseract.image_to_string(img)
        except:
            pass
            
    return text

def parse_date(text):
    # Normalize text
    text_search = text # keep case for some formats
    
    # Common formats
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # 12/31/2025, 31-12-2025
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',    # 2025-12-31
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})', # Dec 31, 2025
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+(\d{4})'  # 31 Dec 2025
    ]
    
    for line in text.split('\n'):
        for pat in patterns:
            match = re.search(pat, line, re.IGNORECASE)
            if match:
                try:
                    raw = match.group(0)
                    # Attempt parse
                    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"]:
                        try:
                            dt = datetime.strptime(raw, fmt)
                            # Year correction (2 digits)
                            if dt.year < 100: dt = dt.replace(year=2000+dt.year)
                            return dt.strftime("%y%m%d")
                        except:
                            pass
                except:
                    continue
                    
    return datetime.now().strftime("%y%m%d")

def parse_store(text):
    text_lower = text.lower()
    
    # Keyword Mapping for common services/stores
    known = {
        "snappic": "Snappic",
        "paddle": "Snappic", # Often appears with Snappic
        "semrush": "SEMRush",
        "amazon": "Amazon",
        "uber": "Uber",
        "lyft": "Lyft",
        "starbucks": "Starbucks",
        "target": "Target",
        "walmart": "Walmart",
        "google": "Google",
        "microsoft": "Microsoft",
        "adobe": "Adobe",
        "apple": "Apple",
        "netflix": "Netflix",
        "costco": "Costco",
        "shell": "Shell",
        "chevron": "Chevron",
        "ihop": "IHOP",
        "mcdonalds": "McDonalds",
        "burger king": "BurgerKing",
        "domino": "Dominos"
    }
    
    for key, val in known.items():
        if key in text_lower:
            return val
            
    # Fallback: Header Line
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 2]
    # Filter out common bad headers like "via" or "receipt"
    lines = [l for l in lines if l.lower() not in ["via", "receipt", "invoice", "payment"]]
    
    if lines:
        candidate = lines[0]
        # Sanitize
        candidate = re.sub(r'[^a-zA-Z0-9 ]', '', candidate).strip()
        words = candidate.split()
        if len(words) > 0:
            return words[0][:15] # Return first word as Store
            
    return "UnknownStore"

def parse_payment(text):
    text_lower = text.lower()
    
    # helper to find last 4 digits
    def find_digits(txt):
        # Look for 4 digits that are NOT the year (2020-2030)
        # Matches digits preceded by space/mask/keyword
        # Excludes dates like 2025
        candidates = re.findall(r'(?:x|\*|\s)(\d{4})\b', txt)
        for c in candidates:
            if not c.startswith("202") and not c.startswith("201"): # Simple year filter
                return c
        return "XXXX"

    # 1. Strong Card Indicators
    card_keywords = [
        "credit card", "debit card", "visa", "mastercard", "amex", "american express", "discover",
        "ending in", "card ending", "**"
    ]
    if any(k in text_lower for k in card_keywords):
        digits = find_digits(text_lower)
        return f"Card-{digits}"

    # 2. Regex for masked cards (e.g., ****1234, XXXX1234)
    if re.search(r'(\*|x|X){2,}\s?\d{4}', text):
        digits = find_digits(text_lower)
        return f"Card-{digits}"
        
    if re.search(r'ending in\s?:?\s?\d{4}', text_lower):
        digits = find_digits(text_lower)
        return f"Card-{digits}"

    # 3. PayPal
    if "paypal" in text_lower: return "PayPal"
    
    # 4. Cash
    if re.search(r'\bcash\b', text_lower): return "Cash"

    # 5. Check
    if "check #" in text_lower or re.search(r'payment method:\s?check', text_lower):
        # Try to find check number
        match = re.search(r'check #\s?(\d+)', text_lower)
        if match: return f"Check-{match.group(1)}"
        return "Check"
    
    # Default
    return "Card-XXXX"

def parse_amount(text):
    # Regex for currency: $1,234.56 or 1234.56
    # We look for the LARGEST number that matches a currency pattern, assumed to be the total
    matches = re.findall(r'\$?\s?(\d{1,3}(?:,\d{3})*\.\d{2})', text)
    if not matches:
        return 0.0
    
    values = []
    for m in matches:
        try:
            # Clean string
            clean = m.replace(',', '')
            values.append(float(clean))
        except:
            continue
            
    if values:
        return max(values)
    return 0.0

def process_document(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    try:
        if ext == '.pdf':
            text = extract_text_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png']:
            text = extract_text_from_image(file_path)
    except Exception as e:
        print(f"Extraction error: {e}")

    # Metadata
    date_val = parse_date(text)
    store_val = parse_store(text)
    payment_val = parse_payment(text)
    amount_val = parse_amount(text)
    
    return {
        "date": date_val,
        "store": store_val,
        "payment": payment_val,
        "amount": amount_val,
        "raw_text_debug": text[:200]
    }
