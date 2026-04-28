#!/bin/bash
set -e

SERVICE_NAME="chat-reminder"
PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_CMD="$VENV_DIR/bin/python"
TARGET="${1:-dev}"

if [ "$TARGET" != "dev" ] && [ "$TARGET" != "ecs" ]; then
    echo "Usage: bash deploy.sh [dev|ecs]"
    exit 1
fi

echo "=== Preparing $SERVICE_NAME ($TARGET) ==="

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

echo "Checking Python virtual environment..."
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Notice: You are currently in a virtual environment ($VIRTUAL_ENV)."
    echo "deploy.sh will use the project-specific venv at $VENV_DIR instead."
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating new virtual environment at $VENV_DIR to isolate dependencies..."
    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is not installed. Please install it first."
        exit 1
    fi
    
    if ! python3 -m venv "$VENV_DIR"; then
        echo "Error: Failed to create virtual environment."
        echo "Note: On some systems (like Ubuntu/Debian), you may need to run 'sudo apt install python3-venv' first."
        exit 1
    fi
    echo "Virtual environment created successfully."
else
    echo "Using existing virtual environment at $VENV_DIR."
fi

source "$VENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Initializing database..."
python scripts/init_db.py

if [ "$TARGET" = "ecs" ]; then
    echo "Generating systemd service file..."
    cat > "${SERVICE_NAME}.service" << EOF
[Unit]
Description=Chat Screenshot Reminder Web Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PYTHON_CMD $PROJECT_DIR/scripts/run_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    echo "Service file created locally at ${SERVICE_NAME}.service"
    echo ""
    echo "=== ECS Deployment Instructions ==="
    echo "sudo cp ${SERVICE_NAME}.service /etc/systemd/system/"
    echo "sudo systemctl daemon-reload"
    echo "sudo systemctl enable ${SERVICE_NAME}"
    echo "sudo systemctl restart ${SERVICE_NAME}"
    echo "sudo systemctl status ${SERVICE_NAME}"
else
    echo ""
    echo "=== Development Machine Run Instructions ==="
    echo "source venv/bin/activate"
    echo "python scripts/run_server.py --reload"
    echo ""
    echo "If HOST=0.0.0.0, you can visit the app with localhost or this machine's private IP."
fi
