"""Reading exam results from the backend (token login, get-user-exam).

Moved out of Utilities/utilsdemo.py unchanged (2026-09-22); every name is still
reachable as utilsdemo.<name>.
"""

from datetime import datetime
import logging
import os
import requests

from vocatooki import backend_api


def _load_project_env():
    """Populate env vars from a local, gitignored .env (or rally/email env) if
    they aren't already set. Mirrors run_panel's minimal loader so direct pytest
    runs pick up credentials too. Never overrides values already in the env."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in (".env", "rally.env", "automation_email.env"):
        try:
            with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            continue


_load_project_env()


VT_LOGIN_URL = os.getenv("VT_LOGIN_URL", "https://login.vocatooki.com/access/auth")


VT_GAME = os.getenv("VT_GAME", "vt")


# Credentials are read from the environment (see .env.template). Never hard-code
# secrets here — this file is tracked in git.
VT_USERNAME = os.getenv("VT_USERNAME")


VT_PASSWORD = os.getenv("VT_PASSWORD")


_TOKEN_CACHE = {
    "access_token": None
}


def format_exam_timestamp(ms_value):
    if not ms_value:
        return None
    try:
        return datetime.fromtimestamp(ms_value / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ms_value


def extract_user_id_from_userid_examid(userid_examid: str) -> str:
    if "_" not in userid_examid:
        raise ValueError(f"Invalid userid_examid format: {userid_examid}")
    return userid_examid.split("_", 1)[0]


def login_and_get_vt_token(username=None, password=None, force_refresh=False):
    """
    Logs in to Voca Tooki auth service and returns a bearer token.
    Caches token in memory for reuse during the same test run.
    """
    if _TOKEN_CACHE["access_token"] and not force_refresh:
        return _TOKEN_CACHE["access_token"]

    username = username or VT_USERNAME
    password = password or VT_PASSWORD

    if not username or not password:
        raise ValueError("Missing VT credentials. Set VT_USERNAME and VT_PASSWORD.")

    payload = {
        "username": username,
        "password": password,
        "game": VT_GAME
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    logging.info("[login_and_get_vt_token] Requesting auth token")

    response = requests.post(VT_LOGIN_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    # support a few common token keys
    token = (
            data.get("jwtToken")
            or data.get("token")
            or data.get("access_token")
            or data.get("jwt")
            or data.get("id_token")
    )

    if not token:
        raise ValueError(f"Token not found in login response. Response keys: {list(data.keys())}")

    _TOKEN_CACHE["access_token"] = token
    return token


def get_auth_headers(token=None, username=None, password=None, force_refresh=False):
    """
    Returns Authorization headers.
    If token is not supplied, fetches it automatically via login.
    """
    bearer = token or login_and_get_vt_token(
        username=username,
        password=password,
        force_refresh=force_refresh
    )

    if not bearer.startswith("Bearer "):
        bearer = f"Bearer {bearer}"

    return {
        "Authorization": bearer,
        "Accept": "application/json"
    }


def get_user_exam_by_userid_examid(userid_examid, class_id=2336, token=None, username=None, password=None):
    """
    Calls:
    GET {VT_DATA_API}/get-user-exams/{user_id}/{class_id}

    Returns only the matching record for userid_examid.
    """
    user_id = extract_user_id_from_userid_examid(userid_examid)
    url = f"{backend_api.VT_DATA_API}/get-user-exams/{user_id}/{class_id}"

    headers = get_auth_headers(token=token, username=username, password=password)

    logging.info(
        f"[get_user_exam_by_userid_examid] Fetching exam for userid_examid={userid_examid}, class_id={class_id}"
    )

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if isinstance(data.get("data"), list):
                records = data["data"]
            elif isinstance(data.get("exams"), list):
                records = data["exams"]
            else:
                records = [data]
        else:
            logging.warning("[get_user_exam_by_userid_examid] Unexpected response type")
            return None

        for record in records:
            if record.get("userid_examid") == userid_examid:
                return {
                    "userid_examid": record.get("userid_examid"),
                    "delivered_date": record.get("delivered_date"),
                    "delivered_date_readable": format_exam_timestamp(record.get("delivered_date")),
                    "class_id": record.get("class_id"),
                    "lesson_id": record.get("lesson_id"),
                    "name": record.get("name"),
                    "grade": record.get("grade")
                }

        logging.warning(f"[get_user_exam_by_userid_examid] No record found for {userid_examid}")
        return None

    except requests.exceptions.HTTPError as e:
        logging.error(f"[get_user_exam_by_userid_examid] HTTP error: {e}")
        try:
            logging.error(f"[get_user_exam_by_userid_examid] Response text: {response.text}")
        except Exception:
            pass

        # optional retry once with fresh token on 401
        if getattr(response, "status_code", None) == 401 and token is None:
            logging.info("[get_user_exam_by_userid_examid] Token may be expired, retrying with fresh token")
            try:
                fresh_headers = get_auth_headers(
                    username=username,
                    password=password,
                    force_refresh=True
                )
                retry_response = requests.get(url, headers=fresh_headers, timeout=30)
                retry_response.raise_for_status()
                retry_data = retry_response.json()

                if isinstance(retry_data, list):
                    retry_records = retry_data
                elif isinstance(retry_data, dict):
                    if isinstance(retry_data.get("data"), list):
                        retry_records = retry_data["data"]
                    elif isinstance(retry_data.get("exams"), list):
                        retry_records = retry_data["exams"]
                    else:
                        retry_records = [retry_data]
                else:
                    return None

                for record in retry_records:
                    if record.get("userid_examid") == userid_examid:
                        return {
                            "userid_examid": record.get("userid_examid"),
                            "delivered_date": record.get("delivered_date"),
                            "delivered_date_readable": format_exam_timestamp(record.get("delivered_date")),
                            "class_id": record.get("class_id"),
                            "lesson_id": record.get("lesson_id"),
                            "name": record.get("name")
                        }
            except Exception as retry_err:
                logging.error(f"[get_user_exam_by_userid_examid] Retry failed: {retry_err}")

    except requests.exceptions.RequestException as e:
        logging.error(f"[get_user_exam_by_userid_examid] Request error: {e}")
    except ValueError as e:
        logging.error(f"[get_user_exam_by_userid_examid] JSON parse/token error: {e}")

    return None
