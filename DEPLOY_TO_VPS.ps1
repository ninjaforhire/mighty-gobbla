$ServerIP = "72.60.27.66"
$User = "root"

Write-Host "🦃 MIGHTY GOBBLA AUTO-DEPLOYMENT TURKEY 🦃" -ForegroundColor Yellow
Write-Host "Connecting to $ServerIP... (You will be asked for your VPS password)"

# The Remote Script (Bash)
$RemoteScript = @'
set -e

echo ">>> 1. Updating System..."
apt update && apt upgrade -y
apt install -y python3-pip python3-venv git tesseract-ocr libtesseract-dev poppler-utils acl

echo ">>> 2. Setting up Directory..."
mkdir -p /var/www
cd /var/www

if [ -d "mighty-gobbla" ]; then
    echo ">>> Repo exists, pulling updates..."
    cd mighty-gobbla
    git pull origin main
else
    echo ">>> Cloning Repo..."
    git clone https://github.com/ninjaforhire/mighty-gobbla.git
    cd mighty-gobbla
fi

echo ">>> 3. Python Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r src/mighty_gobbla/backend/requirements.txt

echo ">>> 4. Configuring Service..."
cat <<EOF > /etc/systemd/system/gobbla.service
[Unit]
Description=Mighty Gobbla
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/mighty-gobbla/src/mighty_gobbla/backend
ExecStart=/var/www/mighty-gobbla/venv/bin/uvicorn main:app --host 0.0.0.0 --port 80
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gobbla
systemctl restart gobbla

echo ">>> 5. CHECKING CONFIG..."
if [ ! -f ~/.mighty_gobbla_settings.json ]; then
    echo "WARNING: Settings file missing. Creating placeholder..."
    echo '{"notion_enabled": false}' > ~/.mighty_gobbla_settings.json
    echo ">>> YOU MUST EDIT ~/.mighty_gobbla_settings.json ON THE SERVER TO ADD NOTION KEYS!"
fi

echo ">>> TURKEY IS FLYING! Visit http://72.60.27.66"
'@

# Execute via SSH
# We use -t to force a pseudo-tty so sudo/prompts work nicely if needed, though we are root.
ssh -t $User@$ServerIP "$RemoteScript"

Write-Host "Done! Press Enter to exit."
Read-Host
