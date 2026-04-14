#!/bin/bash
set -e

# Configuration
SERVICE_NAME="chat-reminder"
PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_CMD="$VENV_DIR/bin/python"
UVICORN_CMD="$VENV_DIR/bin/uvicorn"

echo "=== Deploying $SERVICE_NAME ==="

# 1. Check environment
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# 2. Create and activate virtual environment
echo "Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 3. Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Initialize Database
echo "Initializing database..."
python scripts/init_db.py

# 5. Create systemd service file
echo "Generating systemd service file..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Note: In a real environment, you might need sudo to write to /etc/systemd/system
# We generate a local file first that the user can copy.
cat > "${SERVICE_NAME}.service" << EOF
[Unit]
Description=Chat Screenshot Reminder Web Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$UVICORN_CMD src.main:app --host 0.0.0.0 --port \${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created locally at ${SERVICE_NAME}.service"
echo ""
echo "=== Deployment Instructions ==="
echo "If deploying to ECS, run the following commands with root privileges:"
echo "sudo cp ${SERVICE_NAME}.service /etc/systemd/system/"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable ${SERVICE_NAME}"
echo "sudo systemctl restart ${SERVICE_NAME}"
echo "sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "For local testing, simply run:"
echo "source venv/bin/activate"
echo "uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
