# Chat Screenshot Reminder

A Proof of Concept (PoC) web application that allows users to upload chat screenshots. The system uses a Vision LLM (Seed API) to extract the context and requested time for a reminder, automatically creating and tracking tasks.

## 🛠 Features

- **Upload & Extract**: Drag and drop chat screenshots. The app extracts text and reminder times automatically via Seed Vision LLM.
- **State Management**: Reminders go through states: `processing` -> `pending` -> `expired` or `completed`.
- **Snooze & Edit**: Manually adjust times, snooze by 1 hour, or mark tasks as completed.
- **Access Control**: Simple access code protection for PoC sharing.
- **Auto Status Checker**: Background scheduler automatically marks reminders as `expired` when time is up.

## 🚀 Local Development

### 1. Prerequisites
- Python 3.10+
- Seed API Key

### 2. Setup

```bash
git clone <your-repo-url>
cd client_chat_reminder

# Create environment file
cp .env.example .env
```

Edit `.env` to include your specific configurations:
```env
APP_PASSWORD=your-secret-code
PORT=8000
API_KEY=your-seed-api-key
```

### 3. Run Locally

```bash
bash deploy.sh

# Start the server for local testing
source venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Access the app at: `http://localhost:8000`

## ☁️ ECS Deployment

This project uses a standard single-server deployment flow with `systemd` and a virtual environment.

### Deployment Steps

1. Log into your ECS server.
2. Ensure you have python installed: `sudo apt install python3 python3-venv python3-pip git`
3. Clone the repo and enter the directory.
4. Copy and edit `.env`:
   ```bash
   cp .env.example .env
   vim .env
   ```
5. Run the deployment script to create the `venv`, install dependencies, init the DB, and generate the systemd service file:
   ```bash
   bash deploy.sh
   ```
6. Install and start the service:
   ```bash
   sudo cp chat-reminder.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable chat-reminder
   sudo systemctl restart chat-reminder
   sudo systemctl status chat-reminder
   ```

### Known Limitations
- The "Push Notification" to phones is not yet implemented (Web interface list view only).
- Vision LLM time parsing relies on relative reasoning capability of the model. Explicit times (e.g., "Tomorrow at 10 AM") work best.
