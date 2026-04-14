import os
import shutil
import logging
from datetime import datetime
from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
        if path.startswith("/api/") or path == "/" or path.startswith("/reminder/"):
            # Check for header or cookie
            code = request.headers.get("X-Access-Code") or request.cookies.get("access_code")
            if path == "/" and code != APP_PASSWORD:
                # Render login page if visiting home without access code
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
                    reminder.status = "pending"
                except ValueError:
                    logger.warning(f"Invalid time format returned from LLM: {time_str}")
                    reminder.status = "pending" # Needs manual time set
            else:
                reminder.status = "pending" # Needs manual time set
                
            db.commit()
    except Exception as e:
        logger.error(f"Error in background processing: {e}")
        # Could set status to error, but for MVP keep it simple

# --- API Endpoints ---

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    password = data.get("password")
    if password == APP_PASSWORD:
        response = JSONResponse(content={"success": True})
        response.set_cookie(key="access_code", value=password, httponly=True, max_age=3600*24*30)
        return response
    return JSONResponse(status_code=401, content={"success": False, "message": "Invalid password"})

@app.post("/api/upload")
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save file
    timestamp = datetime.now().strftime("%Y%md%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Create DB entry
    reminder = Reminder(image_path=str(file_path.relative_to(BASE_DIR)))
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    
    # Add background task to process with LLM
    background_tasks.add_task(process_image_background, reminder.id, str(file_path), db)
    
    return {"success": True, "reminder_id": reminder.id, "message": "Image uploaded, processing started"}

@app.get("/api/reminders")
async def get_reminders(db: Session = Depends(get_db)):
    reminders = db.query(Reminder).order_by(Reminder.created_at.desc()).all()
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
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/reminder/{id}", response_class=HTMLResponse)
async def reminder_detail(request: Request, id: str):
    return templates.TemplateResponse(request=request, name="detail.html", context={"id": id})
