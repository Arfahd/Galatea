#!/bin/bash
# ===========================================
# Galatea Cloud - Oracle Cloud Server Setup
# ===========================================
# Run this script on a fresh Oracle Cloud Free Tier VM
# Tested on: Oracle Linux 8, Ubuntu 22.04
#
# Usage:
#   chmod +x setup_server.sh
#   sudo ./setup_server.sh
# ===========================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "Please run as root (sudo ./setup_server.sh)"
    exit 1
fi

echo_info "Starting Galatea Cloud setup..."

# ===========================================
# 1. System Updates
# ===========================================
echo_info "Updating system packages..."
if command -v dnf &> /dev/null; then
    # Oracle Linux / RHEL
    dnf update -y
    dnf install -y python3.11 python3.11-pip git sqlite
elif command -v apt &> /dev/null; then
    # Ubuntu / Debian
    apt update && apt upgrade -y
    apt install -y python3.11 python3.11-venv python3-pip git sqlite3
else
    echo_error "Unsupported package manager. Please install Python 3.11 manually."
    exit 1
fi

# ===========================================
# 2. Create Galatea User
# ===========================================
echo_info "Creating galatea user..."
if ! id "galatea" &>/dev/null; then
    useradd -r -m -s /bin/bash galatea
    echo_info "User 'galatea' created"
else
    echo_warn "User 'galatea' already exists"
fi

# ===========================================
# 3. Create Directory Structure
# ===========================================
echo_info "Setting up directory structure..."
mkdir -p /opt/galatea
mkdir -p /opt/galatea/data
mkdir -p /opt/galatea/backups

# ===========================================
# 4. Clone/Copy Application
# ===========================================
echo_info "Setting up application files..."
# If running from the repo directory, copy files
if [ -f "../main.py" ]; then
    cp -r ../* /opt/galatea/
    rm -rf /opt/galatea/scripts  # Remove scripts from app dir
    mkdir -p /opt/galatea/scripts
    cp ../scripts/*.sh /opt/galatea/scripts/
else
    echo_warn "main.py not found. Please copy application files to /opt/galatea manually."
fi

# ===========================================
# 5. Setup Python Virtual Environment
# ===========================================
echo_info "Setting up Python virtual environment..."
cd /opt/galatea

# Create venv with Python 3.11
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo_info "Dependencies installed"
else
    echo_error "requirements.txt not found!"
    exit 1
fi

deactivate

# ===========================================
# 6. Setup Environment File
# ===========================================
echo_info "Setting up environment file..."
if [ ! -f "/opt/galatea/.env" ]; then
    if [ -f "/opt/galatea/.env.example" ]; then
        cp /opt/galatea/.env.example /opt/galatea/.env
        echo_warn "Created .env from .env.example"
        echo_warn "IMPORTANT: Edit /opt/galatea/.env with your API keys!"
    else
        echo_error ".env.example not found!"
    fi
else
    echo_warn ".env already exists, skipping"
fi

# ===========================================
# 7. Set Permissions
# ===========================================
echo_info "Setting permissions..."
chown -R galatea:galatea /opt/galatea
chmod 600 /opt/galatea/.env
chmod 755 /opt/galatea/scripts/*.sh

# ===========================================
# 8. Setup Systemd Service
# ===========================================
echo_info "Setting up systemd service..."
cp /opt/galatea/galatea.service /etc/systemd/system/galatea.service
systemctl daemon-reload
systemctl enable galatea

# ===========================================
# 9. Setup Backup Cron Job
# ===========================================
echo_info "Setting up daily backup cron job..."
CRON_CMD="0 3 * * * /opt/galatea/scripts/backup.sh >> /opt/galatea/backups/backup.log 2>&1"
(crontab -u galatea -l 2>/dev/null | grep -v "backup.sh"; echo "$CRON_CMD") | crontab -u galatea -

# ===========================================
# 10. Firewall Setup (Oracle Cloud)
# ===========================================
echo_info "Note: Oracle Cloud firewall rules..."
echo_warn "Make sure to allow outbound HTTPS (443) in Oracle Cloud Security Lists"
echo_warn "The bot only needs outbound connections to:"
echo_warn "  - api.telegram.org (443)"
echo_warn "  - api.anthropic.com (443)"

# ===========================================
# Summary
# ===========================================
echo ""
echo_info "========================================="
echo_info "Setup Complete!"
echo_info "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit the environment file:"
echo "     sudo nano /opt/galatea/.env"
echo ""
echo "  2. Add your API keys:"
echo "     - TELEGRAM_BOT_TOKEN"
echo "     - ANTHROPIC_API_KEY"
echo "     - ADMIN_USERS (your Telegram user ID)"
echo ""
echo "  3. Start the bot:"
echo "     sudo systemctl start galatea"
echo ""
echo "  4. Check status:"
echo "     sudo systemctl status galatea"
echo ""
echo "  5. View logs:"
echo "     sudo journalctl -u galatea -f"
echo ""
echo "Database location: /opt/galatea/data/galatea.db"
echo "Backups location:  /opt/galatea/backups/"
echo ""
