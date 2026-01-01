Write-Host "🦃 MIGHTY GOBBLA IS WAKING UP..." -ForegroundColor Magenta

# Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed! Please install Python 3.8+."
    exit 1
}

# Install Dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r src/mighty_gobbla/backend/requirements.txt

# Check for Tesseract (Optional warning)
if (-not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
    Write-Warning "Tesseract OCR not found at default location. OCR might fail for images. Please install Tesseract-OCR if needed."
}

# Run App
Write-Host "STARTING THE GOBBLA ENGINE!" -ForegroundColor Cyan
Write-Host "Go to http://localhost:8000 in your browser." -ForegroundColor Green
$env:PYTHONPATH="src"
python src/mighty_gobbla/backend/main.py
