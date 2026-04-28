# Chat Screenshot Reminder

A Proof of Concept (PoC) web application that allows users to upload chat screenshots. The system uses a Vision LLM (Seed API) to extract the context and requested time for a reminder, automatically creating and tracking tasks.

## 🛠 Features

- **Upload & Extract**: Drag and drop chat screenshots. The app extracts text and reminder times automatically via Seed Vision LLM.
- **State Management**: Reminders go through states: `processing` -> `pending` -> `expired` or `completed`.
- **Snooze & Edit**: Manually adjust times, snooze by 1 hour, or mark tasks as completed.
- **Access Control**: Simple access code protection for PoC sharing.
- **Auto Status Checker**: Background scheduler automatically marks reminders as `expired` when time is up.

## 🚀 Development Machine Deployment

### 1. Prerequisites
- Python 3.10+
- A reachable Vision LLM API endpoint

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
HOST=0.0.0.0
PORT=8000
API_KEY=your-seed-api-key
MODEL_NAME=your-model-name
BASE_URL=your-base-url
```

`HOST` controls how the service is exposed:

- `HOST=127.0.0.1`: only this machine can access the app
- `HOST=0.0.0.0`: this machine and other clients on the same private network can access the app through the machine's private IP

If the machine can successfully connect to the model endpoint, the upload and parsing flow works even when the machine does not have a public IP. A connection test that reaches the endpoint and only returns an authentication error means the network path is already working and only the API credential still needs to be configured.

### 3. Prepare the Environment

```bash
bash deploy.sh dev
```

### 4. Start the Service on the Development Machine

```bash
source venv/bin/activate
python scripts/run_server.py --reload
```

Access examples:

- `http://127.0.0.1:8000`
- `http://localhost:8000`
- `http://<private-ip>:8000`

If your development machine is the one in the example below and `HOST=0.0.0.0`, the app can be accessed from the same private network through:

```text
http://10.37.121.113:8000
```

This mode is suitable for an internal development machine with outbound access to the LLM API and no public IP.

## ☁️ ECS Deployment

This project uses a single-server deployment flow with `systemd` and a virtual environment. The ECS path is kept separate from the development-machine path.

### Deployment Steps

1. Log into your ECS server.
2. Ensure you have python installed: `sudo apt install python3 python3-venv python3-pip git`
3. Clone the repo and enter the directory.
4. Copy and edit `.env`:
   ```bash
   cp .env.example .env
   vim .env
   ```
5. Set `HOST=0.0.0.0` in `.env`, and set the server's LLM API endpoint, model, and key.
6. Run the deployment script to create the `venv`, install dependencies, init the DB, and generate the systemd service file:
   ```bash
   bash deploy.sh ecs
   ```
7. Install and start the service:
   ```bash
   sudo cp chat-reminder.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable chat-reminder
   sudo systemctl restart chat-reminder
   sudo systemctl status chat-reminder
   ```
8. Allow inbound access through your ECS security group or reverse proxy.

The repository also keeps a reusable example file at `chat-reminder.service.template`, while `bash deploy.sh ecs` generates the real machine-specific `chat-reminder.service`.

## Deployment Notes

- The current project is intended for a single machine and a single app instance
- SQLite, local uploads, FastAPI `BackgroundTasks`, and the in-process scheduler are not designed for multi-instance deployment
- For public exposure on ECS, it is better to place the app behind a reverse proxy and keep API docs disabled in production
- For internal development-machine deployment, a public IP is not required as long as the machine can reach the model endpoint and your client can reach the machine's private IP

### Known Limitations
- The "Push Notification" to phones is not yet implemented (Web interface list view only).
- Vision LLM time parsing relies on relative reasoning capability of the model. Explicit times (e.g., "Tomorrow at 10 AM") work best.
