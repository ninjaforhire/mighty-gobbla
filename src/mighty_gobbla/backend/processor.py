import re
import os
import numpy as np
from datetime import datetime

try:
    from PIL import Image
    import pytesseract
    from pdf2image import convert_from_path
    import cv2
except ImportError:
    pass

try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not installed.")

# Config for Tesseract
default_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(default_tesseract):
    pytesseract.pytesseract.tesseract_cmd = default_tesseract

def smart_crop_receipt(image_path):
    """
    Uses OpenCV to find the receipt contour and crop it, removing the background.
    """
    try:
        # Read image
        image = cv2.imread(image_path)
        if image is None: return Image.open(image_path)
        
        # Resize for faster processing if huge
        ratio = image.shape[0] / 500.0
        orig = image.copy()
        image = cv2.resize(image, (int(image.shape[1]/ratio), 500))

        # Convert to grayscale & Blur
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge Detection
        edged = cv2.Canny(gray, 75, 200)

        # Find Contours
        cnts = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts[0] if len(cnts) == 2 else cnts[1], key=cv2.contourArea, reverse=True)[:5] # Get largest

        screenCnt = None
        for c in cnts:
            # Approximate the contour
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)

            # If our approximated contour has 4 points, we assume we found the receipt
            if len(approx) == 4:
                screenCnt = approx
                break
        
        if screenCnt is None:
            # Fallback: Just simple thresholding if no clear rect found
            return Image.open(image_path)

        # Transform Logic (Deskew) would go here, but simple bounding rect is safer/faster
        x, y, w, h = cv2.boundingRect(screenCnt)
        
        # Scale back up to original size
        x = int(x * ratio)
        y = int(y * ratio)
        w = int(w * ratio)
        h = int(h * ratio)
        
        # Crop
        cropped = orig[y:y+h, x:x+w]
        
        # Convert to PIL for Tesseract
        return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        
    except Exception as e:
        print(f"Smart Crop Failed: {e}")
        return Image.open(image_path)

def preprocess_image(image_path):
    """
    Pipeline: 
    1. Smart Crop (Remove Granite Background)
    2. Binarize (Black text on White bg)
    """
    try:
        # 1. Smart Crop
        pil_img = smart_crop_receipt(image_path)
        
        # 2. Convert to CV2 format for thresholding
        open_cv_image = np.array(pil_img) 
        # Convert RGB to BGR 
        open_cv_image = open_cv_image[:, :, ::-1].copy() 
        
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # 3. Simple Thresholding (or Adaptive)
        # Using simple binary thresholding is often better for receipts than adaptive if lighting is even-ish
        # scanning effect.
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Check noise? If too noisy, maybe fallback to original gray
        # But OTSU is usually good.
        
        return Image.fromarray(thresh)
    except Exception as e:
        print(f"Preprocessing error: {e}")
        return Image.open(image_path)

def extract_text_from_image(image_path):
    try:
        img = preprocess_image(image_path)
        # --psm 4: Assume a single column of text of variable sizes
        text = pytesseract.image_to_string(img, config='--psm 4')
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
    
    if len(text) < 50:
        try:
            images = convert_from_path(pdf_path)
            for img in images:
                text += pytesseract.image_to_string(img)
        except: pass
    return text

def parse_date(text):
    # Kroger bottom format: 11/09/25 07:01pm
    # Regex designed to catch line endings where dates often hide
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
    ]
    
    candidates = []
    
    for line in text.split('\n'):
        for pat in patterns:
            match = re.search(pat, line, re.IGNORECASE)
            if match:
                raw = match.group(0)
                # Try formats
                for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%m-%d-%y"]:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        if dt.year < 100: dt = dt.replace(year=2000+dt.year)
                        if 2000 <= dt.year <= (datetime.now().year + 1):
                            candidates.append(dt)
                    except: pass
                    
    # Prefer dates that are NOT "today" if we found others (since today might be default)
    # Actually just take most recent valid
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0].strftime("%y%m%d")
        
    return datetime.now().strftime("%y%m%d")

def parse_store(text):
    text_lower = text.lower()
    # Kroger Specific
    if "kroger" in text_lower: return "Kroger"
    
    known = {
        "snappic": "Snappic", "paddle": "Snappic", "semrush": "SEMRush",
        "amazon": "Amazon", "uber": "Uber", "lyft": "Lyft", "starbucks": "Starbucks",
        "target": "Target", "walmart": "Walmart", "google": "Google", "shell": "Shell"
    }
    for k, v in known.items():
        if k in text_lower: return v
        
    # Header fallback
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]
    lines = [l for l in lines if l.lower() not in ["via", "receipt", "invoice", "copy"]]
    if lines:
        return lines[0].split()[0][:15].capitalize()
    return "UnknownStore"

def parse_payment(text):
    text_lower = text.lower()
    
    # Kroger: "Total Savings" "Total Coupons" often appear
    # Look for "BALANCE" or "CASH" explicitly
    
    # Explicit Cash
    if re.search(r'\bcash\b', text_lower):
        # Ensure it's not "Cash Back" if possible, but usually Receipt says "Cash" implies pay method
        return "Cash"
        
    # Cards
    # Find last 4
    digits = re.findall(r'(?:#|x|\*|\s)(\d{4})\b', text_lower)
    valid = [d for d in digits if not d.startswith("202")] # Filter years
    
    if "visa" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    if "mastercard" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    if "amex" in text_lower: return f"Card-{valid[-1] if valid else 'XXXX'}"
    
    if valid: return f"Card-{valid[-1]}"
    
    return "Cash" # Default to Cash if no card indicators found? Or Card-XXXX? 
                  # Safer to detect "Cash" above. If nothing found, default Card-XXXX is safer for expenses.
    return "Card-XXXX"

def parse_amount(text):
    matches = re.findall(r'\$?\s?(\d{1,3}(?:,\d{3})*\.\d{2})', text)
    if matches:
        vals = [float(m.replace(',','')) for m in matches]
        return max(vals)
    return 0.0

def process_document(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.pdf': text = extract_text_from_pdf(file_path)
        else: text = extract_text_from_image(file_path)
    except Exception as e:
        print(f"Error: {e}")
        
    return {
        "date": parse_date(text),
        "store": parse_store(text),
        "payment": parse_payment(text),
        "amount": parse_amount(text),
        "raw_text_debug": text[:200]
    }
