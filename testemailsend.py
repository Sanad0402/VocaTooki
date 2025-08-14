# testemailsend.py
import os, smtplib, socket
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    raise SystemExit("pip install python-dotenv")

# Load the same env file your runner uses
env_path = Path(__file__).parent / "automation_email.env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("[WARN] automation_email.env not found next to this script; falling back to OS env")

HOST = os.getenv("AUTO_EMAIL_HOST", "smtp.gmail.com")
PORT = int(os.getenv("AUTO_EMAIL_PORT", "587"))
USER = os.getenv("AUTO_EMAIL_USER")
PWD  = os.getenv("AUTO_EMAIL_PASS")
FROM = os.getenv("AUTO_EMAIL_FROM", USER)
TO   = os.getenv("AUTO_EMAIL_TO", USER or "")  # send to yourself by default

missing = [k for k,v in [("AUTO_EMAIL_USER",USER),("AUTO_EMAIL_PASS",PWD)] if not v]
if missing:
    raise SystemExit(f"Missing env var(s): {', '.join(missing)}. Check automation_email.env.")

MSG = "Subject: SMTP test\n\nHello from AutomationRunner!"

def try_starttls():
    with smtplib.SMTP(HOST, PORT, timeout=20) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(USER, PWD)
        s.sendmail(FROM, [TO or USER], MSG)
    print("✅ Sent via STARTTLS 587")

def try_ssl():
    with smtplib.SMTP_SSL(HOST, 465, timeout=20) as s:
        s.login(USER, PWD)
        s.sendmail(FROM, [TO or USER], MSG)
    print("✅ Sent via SSL 465")

try:
    try_starttls()
except (smtplib.SMTPException, OSError, socket.timeout) as e:
    print(f"[WARN] STARTTLS failed: {e} — trying SSL:465 …")
    try:
        try_ssl()
    except Exception as e2:
        raise SystemExit(f"❌ Email failed on both 587 and 465: {e2}")
