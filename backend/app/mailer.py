from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.db import SessionLocal
from app.models import EmailLog, Order, User


def send_order_email(order_id: int, event_type: str, subject: str, message: str):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return
        student = db.query(User).filter(User.id == order.user_id).first()
        admin_email = settings.ADMIN_NOTIFICATION_EMAIL
        if not admin_email:
            admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
            admin_email = admin.email if admin else None

        recipients = []
        if student:
            recipients.append(student.email)
        if admin_email and admin_email not in recipients:
            recipients.append(admin_email)
        if not recipients:
            return

        logs = [
            EmailLog(
                recipient=recipient,
                subject=subject,
                body=message,
                event_type=event_type,
                status="simulated" if not settings.SMTP_HOST else "pending",
            )
            for recipient in recipients
        ]
        db.add_all(logs)
        db.commit()

        if not settings.SMTP_HOST:
            return

        for log in logs:
            try:
                email = EmailMessage()
                email["Subject"] = subject
                email["From"] = settings.SMTP_FROM_EMAIL
                email["To"] = log.recipient
                email.set_content(message)
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                    if settings.SMTP_USE_TLS:
                        smtp.starttls()
                    if settings.SMTP_USERNAME:
                        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
                    smtp.send_message(email)
                log.status = "sent"
                log.error_message = None
            except (OSError, smtplib.SMTPException) as error:
                log.status = "failed"
                log.error_message = str(error)[:1000]
        db.commit()
    finally:
        db.close()
