"""Email the activity report when a run finishes.

Reads the same AUTO_EMAIL_* env vars as testemailsend.py (loaded from
automation_email.env by run_panel.py). Tries STARTTLS:587 then SSL:465.
"""

import os
import smtplib
import socket
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def email_configured():
    return all(os.getenv(k) for k in ("AUTO_EMAIL_HOST", "AUTO_EMAIL_USER", "AUTO_EMAIL_PASS"))


def default_recipient():
    return os.getenv("AUTO_EMAIL_TO") or os.getenv("AUTO_EMAIL_USER") or ""


def send_report_email(to_list, subject, body, attachments):
    """Send an email with attachments. Returns (ok: bool, detail: str)."""
    host = os.getenv("AUTO_EMAIL_HOST")
    port = int(os.getenv("AUTO_EMAIL_PORT", "587"))
    user = os.getenv("AUTO_EMAIL_USER")
    pwd = os.getenv("AUTO_EMAIL_PASS")
    from_addr = os.getenv("AUTO_EMAIL_FROM", user)
    to_list = [t.strip() for t in (to_list or []) if t and t.strip()]

    if not (host and user and pwd and from_addr):
        return False, "missing SMTP config (set AUTO_EMAIL_HOST/USER/PASS in automation_email.env)"
    if not to_list:
        return False, "no recipients"

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            continue
        part = MIMEBase("application", "octet-stream")
        with open(p, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
        msg.attach(part)

    def _starttls():
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo(); s.starttls(); s.ehlo(); s.login(user, pwd); s.send_message(msg)

    def _ssl():
        with smtplib.SMTP_SSL(host, 465, timeout=20) as s:
            s.login(user, pwd); s.send_message(msg)

    try:
        _starttls()
        return True, f"sent via STARTTLS:{port} to {', '.join(to_list)}"
    except (smtplib.SMTPException, OSError, socket.timeout) as e1:
        try:
            _ssl()
            return True, f"sent via SSL:465 to {', '.join(to_list)}"
        except (smtplib.SMTPException, OSError, socket.timeout) as e2:
            return False, f"STARTTLS failed ({e1}); SSL failed ({e2})"
