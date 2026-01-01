```python
import re
from datetime import datetime
import os
try:
    from PIL import Image, ImageOps, ImageEnhance
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

def preprocess_image(image_path):
    """
    Enhance image for better OCR results:
    - Grayscale
    - Contrast Enhancement
    - Resize (if too small)
    """
    try:
        img = Image.open(image_path)
        
        # 1. Convert to Grayscale
        img = img.convert('L')
        
        # 2. Enhance Contrast (Limit Noise)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0) # Double the contrast
        
        # 3. Resize if width is small (e.g. < 1000px) typical for phone thumbnails but we want full res
        # If the image came from a phone it might be huge, or small. 
        # Tesseract likes characters to be ~30px high. 
        # A receipt photo usually benefits from scaling up if it's low res.
        w, h = img.size
        if w < 1000:
            new_w = w * 2
            new_h = h * 2
            img = img.resize((int(new_w), int(new_h)), Image.Resampling.LANCZOS)
            
        return img
    except Exception as e:
        print(f"Preprocessing error: {e}")
        return Image.open(image_path) # Fallback

def extract_text_from_image(image_path):
    try:
        # Use preprocessed image
        img = preprocess_image(image_path)
        
        # Determine PSM (Page Segmentation Mode)
        # 3 = Fully automatic page segmentation, but no OSD. (Default)
        # 4 = Assume a single column of text of variable sizes. (Good for receipts)
        # 6 = Assume a single uniform block of text.
        text = pytesseract.image_to_string(img, config='--psm 4')
        return text
    except:
        return ""

def extract_text_from_pdf(pdf_path):
    text = ""
    # 1. Try Native PDF Text Extraction
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        print(f"pypdf error: {e}")

    # 2. Fallback to OCR if text is too short
    if len(text) < 50:
        print("Text too short, attempting OCR...")
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            for img in images:
                # Preprocess PDF images too
                enhancer = ImageEnhance.Contrast(img.convert('L'))
                img = enhancer.enhance(1.5)
                text += pytesseract.image_to_string(img)
        except:
            pass
            
    return text

def parse_date(text):
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',   # 12/31/2025
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',     # 2025-12-31
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})',
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+(\d{4})'
    ]
    
    found_dates = []
    current_year = datetime.now().year
    
    for line in text.split('\n'):
        for pat in patterns:
            match = re.search(pat, line, re.IGNORECASE)
            if match:
                try:
                    raw = match.group(0)
                    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%m-%d-%Y"]:
                        try:
                            dt = datetime.strptime(raw, fmt)
                            # Year correction
                            if dt.year < 100: dt = dt.replace(year=2000+dt.year)
                            
                            # Sanity check: Date shouldn't be too far in future or past
                            # E.g. limit to 2000 - CurrentYear+1
                            if 2000 <= dt.year <= (current_year + 1):
                                found_dates.append(dt)
                        except:
                            pass
                except:
                    continue
    
    if found_dates:
        # Heuristic: The most recent date that isn't in the future is usually the transaction date.
        # Or, just pick the first valid one. Let's sort by date descending.
        # But receipts sometimes have 'Expiration Date' far in future? Usually not.
        found_dates.sort(reverse=True)
        best_date = found_dates[0]
        return best_date.strftime("%y%m%d")

    return datetime.now().strftime("%y%m%d")

def parse_store(text):
    text_lower = text.lower()
    known = {
        "snappic": "Snappic", "paddle": "Snappic", "semrush": "SEMRush",
        "amazon": "Amazon", "uber": "Uber", "lyft": "Lyft", "starbucks": "Starbucks",
        "target": "Target", "walmart": "Walmart", "google": "Google", "microsoft": "Microsoft",
        "adobe": "Adobe", "apple": "Apple", "netflix": "Netflix", "costco": "Costco",
        "shell": "Shell", "chevron": "Chevron", "ihop": "IHOP", "mcdonalds": "McDonalds",
        "burger king": "BurgerKing", "domino": "Dominos", "home depot": "HomeDepot",
        "lowes": "Lowes", "best buy": "BestBuy", "kroger": "Kroger", "publix": "Publix",
        "whole foods": "WholeFoods", "trader joes": "TraderJoes", "walgreens": "Walgreens",
        "cvs": "CVS", "7-eleven": "7-Eleven"
    }
    
    for key, val in known.items():
        if key in text_lower: return val
            
    # Fallback: First meaningful line
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]
    lines = [l for l in lines if l.lower() not in ["via", "receipt", "invoice", "payment", "welcome", "customer copy"]]
    
    if lines:
        candidate = lines[0]
        candidate = re.sub(r'[^a-zA-Z0-9 ]', '', candidate).strip()
        words = candidate.split()
        if len(words) > 0:
            return words[0][:15].capitalize() 
            
    return "UnknownStore"

def parse_payment(text):
    text_lower = text.lower()
    
    def extract_last4(txt):
        # Look for 4 digits that are possibly near "end", "x", "*", or "#"
        matches = re.findall(r'(?:#|x|\*|\s)(\d{4})\b', txt)
        # Filter commonly mistaken years
        valid_digits = []
        for m in matches:
            if not m.startswith("202") and not m.startswith("201"):
                valid_digits.append(m)
        if valid_digits:
            return valid_digits[-1] # Usually the last one found is the card (bottom of receipt)
        return "XXXX"

    # Keywords
    if "visa" in text_lower: return f"Card-{extract_last4(text_lower)}"
    if "mastercard" in text_lower or "mc" in text_lower: return f"Card-{extract_last4(text_lower)}"
    if "amex" in text_lower or "american" in text_lower: return f"Card-{extract_last4(text_lower)}"
    if "discover" in text_lower: return f"Card-{extract_last4(text_lower)}"
    
    # Generic "Card" keywords
    if any(x in text_lower for x in ["credit card", "debit card", "ending in", "card #"]):
        return f"Card-{extract_last4(text_lower)}"

    if "paypal" in text_lower: return "PayPal"
    if "cash" in text_lower and "change" not in text_lower: return "Cash"
    if "check" in text_lower: return "Check"
    
    # Last ditch: if we see 4 masked digits ANYWHERE
    if re.search(r'[\*xX]{4,}\s?-?\d{4}', text_lower):
        return f"Card-{extract_last4(text_lower)}"
        
    return "Card-XXXX"

def parse_amount(text):
    # Regex for currency: $1,234.56 or 1234.56
    matches = re.findall(r'\$?\s?(\d{1,3}(?:,\d{3})*\.\d{2})', text)
    if not matches:
        return 0.0
    
    values = []
    for m in matches:
        try:
            clean = m.replace(',', '')
            values.append(float(clean))
        except:
            continue
            
    if values:
        # Heuristic: The largest amount is usually the Total.
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

    return {
        "date": parse_date(text),
        "store": parse_store(text),
        "payment": parse_payment(text),
        "amount": parse_amount(text),
        "raw_text_debug": text[:200]
    }
```
