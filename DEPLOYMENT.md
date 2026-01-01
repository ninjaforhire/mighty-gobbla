# Deploying Mighty Gobbla to Hostinger VPS (Ubuntu/Debian)

Your Hostinger "KVM 2" VPS is perfect for this. Follow these steps to get the Turkey flying in the cloud.

## 1. Access Your Server
Open your terminal (PowerShell or Command Prompt) and SSH into your server:
```bash
ssh root@72.60.27.66
# Enter your VPS password when prompted
```

## 2. Install System Dependencies
Update your system and install Python, Git, Tesseract (OCR), and Poppler (PDFs).
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git tesseract-ocr libtesseract-dev poppler-utils
```

## 3. Clone the Repository
Pull your code from GitHub.
```bash
cd /var/www
git clone https://github.com/ninjaforhire/mighty-gobbla.git
cd mighty-gobbla
```

## 4. Setup Python Environment
Create a virtual environment to keep things clean.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r src/mighty_gobbla/backend/requirements.txt
```

## 5. Configure Secrets
The app needs to know your Notion settings.
Create the settings file manually (since it's not in git for security):
```bash
nano ~/.mighty_gobbla_settings.json
```
Paste this content (Right click to paste):
```json
{
    "notion_enabled": true,
    "notion_token": "YOUR_NOTION_TOKEN_HERE",
    "notion_db_id": "YOUR_DATABASE_ID_HERE"
}
```
*Press `Ctrl+X`, then `Y`, then `Enter` to save.*

## 6. Test It
Run the server briefly to make sure it doesn't crash.
```bash
cd src/mighty_gobbla/backend
../../../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```
*   Visit `http://72.60.27.66:8000` in your browser.
*   If you see the Turkey, it works!
*   Press `Ctrl+C` in terminal to stop it.

## 7. Keep It Running (Systemd)
To keep the Turkey running even when you close the terminal, we use Systemd.

Create a service file:
```bash
sudo nano /etc/systemd/system/gobbla.service
```

Paste this:
```ini
[Unit]
Description=Mighty Gobbla Service
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/mighty-gobbla/src/mighty_gobbla/backend
ExecStart=/var/www/mighty-gobbla/venv/bin/uvicorn main:app --host 0.0.0.0 --port 80 start
Restart=always

[Install]
WantedBy=multi-user.target
```
*Save (Ctrl+X, Y, Enter).*

**Start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl start gobbla
sudo systemctl enable gobbla
```

## 8. Mobile "App" Usage
1.  Open Chrome/Safari on your iPhone/Android.
2.  Go to `http://72.60.27.66:80`
3.  Tap "Share" -> "Add to Home Screen".
4.  **Boom.** You now have a Mighty Gobbla app icon on your phone.
