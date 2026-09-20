import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Task, User

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("NOTIFY_FROM_EMAIL", "noreply@team-deadline-dashboard.local")


def _send_email(to_email: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        # ponytail: SMTP 미설정이면 발송 대신 로그만 남긴다. 배포 시 SMTP_* 환경변수를 채우면 그대로 발송된다.
        logger.info("[D-1 알림 생략: SMTP 미설정] to=%s subject=%s", to_email, subject)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


def notify_due_tomorrow(db: Session) -> int:
    """마감이 내일(D-1)이고 아직 미완료·미알림인 Task의 담당자에게 메일을 보낸다. 보낸 개수를 반환."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today_start + timedelta(days=1)
    window_end = window_start + timedelta(days=1)

    tasks = (
        db.query(Task)
        .filter(Task.done.is_(False), Task.notified_at.is_(None))
        .filter(Task.deadline >= window_start, Task.deadline < window_end)
        .all()
    )
    sent = 0
    for task in tasks:
        assignee = db.query(User).get(task.assignee_id)
        if not assignee:
            continue
        _send_email(
            assignee.email,
            f"[마감 D-1] {task.title}",
            f"{assignee.name}님, '{task.title}' 할 일의 마감이 내일({task.deadline.date()})입니다.",
        )
        task.notified_at = now
        sent += 1
    db.commit()
    return sent


def run_notify_job() -> None:
    db = SessionLocal()
    try:
        notify_due_tomorrow(db)
    finally:
        db.close()
