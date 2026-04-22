import os
import shutil
import logging
import urllib.parse
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import UPLOAD_DIR, APP_PASSWORD, ENABLE_DOCS, BASE_DIR
from src.database import get_db, init_db
from src.models import Reminder
from src.llm import extract_reminder_info
from src.scheduler import start_scheduler, shutdown_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chat Screenshot Reminder",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "src" / "templates"))

# Mount static files (uploaded images)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.on_event("startup")
def startup_event():
    init_db()
    start_scheduler()

@app.on_event("shutdown")
def shutdown_event():
    shutdown_scheduler()

# --- Middlewares ---
@app.middleware("http")
async def verify_access_code(request: Request, call_next):
    # Only protect specific paths if APP_PASSWORD is set
    if APP_PASSWORD:
        path = request.url.path
        if path.startswith("/api/") or path == "/" or path.startswith("/reminder/") or path == "/stats":
            # Check for header or cookie
            code = request.headers.get("X-Access-Code") or request.cookies.get("access_code")
            if (path == "/" or path == "/stats") and code != APP_PASSWORD:
                # Render login page if visiting protected pages without access code
                return templates.TemplateResponse(request=request, name="login.html")
            elif path.startswith("/api/") and code != APP_PASSWORD:
                if path == "/api/login":
                    pass # Let login pass
                else:
                    return JSONResponse(status_code=401, content={"detail": "Invalid access code"})
    response = await call_next(request)
    return response

# --- Background Tasks ---
async def process_image_background(reminder_id: str, image_path: str, db: Session):
    try:
        # Call LLM
        info = await extract_reminder_info(image_path)
        
        # Update DB
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.extracted_text = info.get("extracted_text")
            
            time_str = info.get("reminder_time")
            if time_str:
                try:
                    # Basic ISO parsing
                    reminder.reminder_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Invalid time format returned from LLM: {time_str}")
                    reminder.reminder_time = datetime.utcnow() + timedelta(hours=1)
            else:
                reminder.reminder_time = datetime.utcnow() + timedelta(hours=1)
                
            reminder.status = "pending"
            db.commit()
    except Exception as e:
        logger.error(f"Error in background processing: {e}")
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.extracted_text = f"⚠️ System Error: {str(e)}"
            reminder.reminder_time = datetime.utcnow()
            reminder.status = "pending"
            db.commit()

# --- API Endpoints ---

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    password = data.get("password")
    username = data.get("username", "anonymous").strip().lower()
    
    if password == APP_PASSWORD:
        response = JSONResponse(content={"success": True})
        response.set_cookie(key="access_code", value=password, httponly=True, max_age=3600*24*30)
        
        # URL encode the username to support Chinese characters in cookies
        encoded_username = urllib.parse.quote(username)
        response.set_cookie(key="username", value=encoded_username, httponly=True, max_age=3600*24*30)
        return response
    return JSONResponse(status_code=401, content={"success": False, "message": "Invalid password"})

@app.post("/api/logout")
async def logout():
    response = JSONResponse(content={"success": True})
    response.delete_cookie(key="access_code")
    response.delete_cookie(key="username")
    return response

@app.post("/api/upload")
async def upload_image(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    
    # Save file
    timestamp = datetime.now().strftime("%Y%md%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    logger.info(f"[Upload] Received image: {filename}, size: {os.path.getsize(file_path)} bytes")
        
    # Create DB entry
    reminder = Reminder(
        image_path=str(file_path.relative_to(BASE_DIR)),
        user_id=username
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    
    # Add background task to process with LLM
    background_tasks.add_task(process_image_background, reminder.id, str(file_path), db)
    
    return {"success": True, "reminder_id": reminder.id, "message": "Image uploaded, processing started"}

@app.get("/api/stats")
async def get_stats(request: Request, db: Session = Depends(get_db)):
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    if username != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
        
    stats = db.query(Reminder.user_id, func.count(Reminder.id).label("task_count")).group_by(Reminder.user_id).all()
    
    # Optional: Get unique users (not just those with tasks, though in our DB they are the same)
    # Since we only save user_id in Reminder table, we query that.
    
    result = [
        {"nickname": s[0], "task_count": s[1]} for s in stats
    ]
    return {"stats": result}

@app.get("/api/reminders")
async def get_reminders(request: Request, db: Session = Depends(get_db)):
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    
    query = db.query(Reminder)
    if username != "admin":
        query = query.filter(Reminder.user_id == username)
        
    reminders = query.order_by(Reminder.created_at.desc()).all()
    return {"reminders": [r.to_dict() for r in reminders], "total": len(reminders)}

@app.get("/api/reminder/{id}")
async def get_reminder(id: str, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder.to_dict()

@app.put("/api/reminder/{id}")
async def update_reminder(id: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    reminder = db.query(Reminder).filter(Reminder.id == id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
        
    if "status" in data:
        reminder.status = data["status"]
    if "reminder_time" in data:
        time_str = data["reminder_time"]
        if time_str:
            reminder.reminder_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        else:
            reminder.reminder_time = None
    if "extracted_text" in data:
        reminder.extracted_text = data["extracted_text"]
        
    db.commit()
    db.refresh(reminder)
    return {"success": True, "reminder": reminder.to_dict()}

@app.delete("/api/reminder/{id}")
async def delete_reminder(id: str, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"success": True}

# --- HTML Views ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    return templates.TemplateResponse(request=request, name="index.html", context={"username": username})

@app.get("/stats", response_class=HTMLResponse)
async def stats_dashboard(request: Request):
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    if username != "admin":
        return HTMLResponse(content="<h1>403 Forbidden</h1><p>You must be 'admin' to view this page.</p>", status_code=403)
    return templates.TemplateResponse(request=request, name="stats.html", context={"username": username})

@app.get("/reminder/{id}", response_class=HTMLResponse)
async def reminder_detail(request: Request, id: str):
    username = urllib.parse.unquote(request.cookies.get("username", "anonymous"))
    return templates.TemplateResponse(request=request, name="detail.html", context={"id": id, "username": username})
