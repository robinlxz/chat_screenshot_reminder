import logging
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.database import SessionLocal
from src.models import Reminder

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def check_overdue_reminders():
    """
    Periodic task to check for pending reminders that have passed their reminder_time
    and update their status to 'expired'.
    """
    try:
        db: Session = SessionLocal()
        now = datetime.utcnow()
        
        # Find pending reminders that are overdue
        overdue_reminders = db.query(Reminder).filter(
            Reminder.status == "pending",
            Reminder.reminder_time <= now
        ).all()
        
        for reminder in overdue_reminders:
            reminder.status = "expired"
            logger.info(f"Reminder {reminder.id} is now expired.")
            
        if overdue_reminders:
            db.commit()
            
    except Exception as e:
        logger.error(f"Error checking overdue reminders: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler.add_job(check_overdue_reminders, 'interval', seconds=10)
    scheduler.start()
    logger.info("Scheduler started.")

def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler shutdown.")
