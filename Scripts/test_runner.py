import os
import sys
import json
import time
import zipfile
import tempfile
import argparse
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET
from typing import List

import pytest
from dotenv import load_dotenv

# --- Load custom env for email ---
env_path = Path(__file__).parent.parent / "automation_email.env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[INFO] Loaded email settings from: {env_path}")
else:
    print("[WARN] automation_email.env not found. Email sending may fail.")


def _mkparents(p: Path):
    if str(p):
        p.parent.mkdir(parents=True, exist_ok=True)


def _normalize_marks(marks: List[str]) -> List[str]:
    out = []
    for m in marks or []:
        s = (m or "").strip()
        if not s:
            continue
        if s.lower().startswith("regre"):
            s = "regression"
        out.append(s)
    return out


def _marks_expr(marks: List[str]) -> str:
    return " or ".join(marks) if marks else ""

def _zip_folder(folder: Path, outzip: Path):
    _mkparents(outzip)
    with zipfile.ZipFile(outzip, "w", zipfile.ZIP_DEFLATED) as zf:
        if folder.exists():
            for p in folder.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=p.relative_to(folder))
    return outzip


def _send_email(to_list, subject, body, attachments):
    import smtplib, socket
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from pathlib import Path

    host = os.getenv("AUTO_EMAIL_HOST")
    port = int(os.getenv("AUTO_EMAIL_PORT", "587"))
    user = os.getenv("AUTO_EMAIL_USER")
    pwd  = os.getenv("AUTO_EMAIL_PASS")
    from_addr = os.getenv("AUTO_EMAIL_FROM", user)
    timeout = 20  # seconds

    if not (host and user and pwd and from_addr) or not to_list:
        print("[WARN] Email not sent: missing SMTP config or recipients.")
        return

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            print(f"[WARN] Attachment not found: {path}")
            continue
        part = MIMEBase("application", "octet-stream")
        with open(path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    def try_starttls():
        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, pwd)
            server.send_message(msg)

    def try_ssl():
        with smtplib.SMTP_SSL(host, 465, timeout=timeout) as server:
            server.login(user, pwd)
            server.send_message(msg)

    try:
        try_starttls()
        print(f"[INFO] Email sent via STARTTLS to: {', '.join(to_list)}")
    except (smtplib.SMTPException, OSError, socket.timeout) as e1:
        print(f"[WARN] STARTTLS failed ({e1}); trying SSL:465...")
        try:
            try_ssl()
            print(f"[INFO] Email sent via SSL to: {', '.join(to_list)}")
        except (smtplib.SMTPException, OSError, socket.timeout) as e2:
            print(f"[WARN] Email not sent: {e2} (both STARTTLS and SSL failed).")



def _parse_junit(junit_path: Path):
    if not junit_path.exists():
        return 0, 0, 0, 0, 0, "[WARN] No JUnit XML produced."

    tree = ET.parse(junit_path)
    root = tree.getroot()

    testcases = list(root.iter("testcase"))
    total = len(testcases)

    failures = sum(1 for c in testcases if c.find("failure") is not None)
    errors   = sum(1 for c in testcases if c.find("error") is not None)
    skipped  = sum(1 for c in testcases if c.find("skipped") is not None)
    passed   = total - failures - errors - skipped

    details = []
    for case in testcases:
        name = f'{case.attrib.get("classname","")}.{case.attrib.get("name","")}'.strip(".")
        for tag in ("failure", "error", "skipped"):
            el = case.find(tag)
            if el is not None:
                msg = el.attrib.get("message", "").strip()
                text = (el.text or "").strip()
                details.append(f"{tag.upper()}: {name}\n{msg}\n{text}\n")

    return total, passed, failures, skipped, errors, "\n".join(details) if details else ""

def _try_write_activity_section(fh):
    try:
        from Utilities import utilsdemo
        utilsdemo.write_activity_report(fh)
    except Exception as e:
        fh.write(f"[WARN] Could not append activity report: {e}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="runner.json")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    tests_path = cfg.get("testsPath", "Sanity")
    report_out = cfg.get("reportOut", [])

    error_file = Path(cfg.get("errorFiles") or "")
    shots_dir = Path(cfg.get("screenShotsFolder") or "")
    report_path = Path(cfg.get("reportFileName") or f"./RunReport_{datetime.now():%Y%m%d_%H%M%S}.txt")

    user_mode = cfg.get("userMode", "single")
    user_index = str(cfg.get("userIndex", 0))
    levels_only = bool(cfg.get("levelsOnly", False))

    lesson = cfg.get("lesson", None)        # single lesson
    lessons = cfg.get("lessons", None)      # 🆕 multiple lessons support

    platform = cfg.get("platform", "WindowsEditor")
    app_id = cfg.get("appId", "")
    device_instance_id = cfg.get("deviceInstanceId", "")
    marks = _normalize_marks(cfg.get("testDomains", []))

    junit_xml = Path(tempfile.gettempdir()) / f"junit_{int(time.time())}.xml"
    pytest_args = [
        tests_path,
        "-q",
        "--maxfail=1",
        "-rA",
        f"--junitxml={junit_xml}",
        f"--user-mode={user_mode}",
        f"--user-index={user_index}",
        f"--platform={platform}",
        f"--app_id={app_id}",
        f"--device_instance_id={device_instance_id}",
    ]

    if marks:
        pytest_args += ["-m", _marks_expr(marks)]
    if levels_only:
        pytest_args.append("--levels-only")

    # 🆕 priority: multiple lessons > single lesson
    if lessons:
        pytest_args += ["--lessons", str(lessons)]
    elif lesson is not None:
        pytest_args += ["--lesson", str(lesson)]

    for extra in (cfg.get("extraPytestArgs") or []):
        pytest_args.append(str(extra))

    print("[RUN] pytest", " ".join(pytest_args))

    if str(shots_dir):
        shots_dir.mkdir(parents=True, exist_ok=True)

    retcode = pytest.main(pytest_args)

    total, passed, failed, skipped, errors, details = _parse_junit(junit_xml)

    _mkparents(report_path)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("🧪 TEST CASE EXECUTION REPORT\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Total   : {total}\nPassed  : {passed}\nFailed  : {failed}\nErrors  : {errors}\nSkipped : {skipped}\n")
        f.write("-" * 40 + "\n\n")
        if details:
            f.write(details + "\n")
        else:
            f.write("No failing tests.\n")

        f.write("\n\n📊 ACTIVITY EXECUTION REPORT\n")
        f.write("=" * 40 + "\n\n")
        _try_write_activity_section(f)

    if str(error_file):
        _mkparents(error_file)
        with open(error_file, "w", encoding="utf-8") as ef:
            ef.write(details or "")

    attachments = [report_path]
    if str(shots_dir) and any(shots_dir.glob("**/*")):
        zip_path = report_path.with_suffix(".screens.zip")
        _zip_folder(shots_dir, zip_path)
        attachments.append(zip_path)

    subject = f"[Automation] Test Report — {datetime.now():%Y-%m-%d %H:%M}"
    body = (
        f"Total: {total}\nPassed: {passed}\nFailed: {failed}\nErrors: {errors}\nSkipped: {skipped}\n"
        f"Report: {report_path}"
    )
    if report_out:
        _send_email(report_out, subject, body, attachments)

    print(f"[DONE] Report written to: {report_path}")
    if retcode != 0:
        sys.exit(retcode)


if __name__ == "__main__":
    main()