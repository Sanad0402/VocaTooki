"""Which VocaTooki backend the framework talks to, and the calls that depend on it.

Every API call of a run — the class map, the user state, exams and tasks — goes
to the backend chosen for that run (the panel asks before every run and passes
it as VT_BACKEND; see set_backend). "auto" keeps the ask-each-host chain for the
class map.

Moved out of utilsdemo.py unchanged (2026-09-22); utilsdemo still offers every
name. VT_DATA_API / VT_TASKS_API / _VT_BACKEND are REASSIGNED at run time, so
read them as `backend.<name>`, never copy them with `from ... import`.
"""

import logging
import os

import requests


# The backend the data endpoints talk to. No single host has every class. On
# 2026-09-01 get-class-map answered 404 ("Error 1A001F01A32") on vtbe for every
# class while green returned the map, so everything moved to green. On
# 2026-09-12 class 35 turned out to live on vtbetest, which green 404s
# ("Error 1A039D6F790") -- while green still holds 2336/651/2335/2337, which
# vtbetest 404s. The hosts are two class sets, not two versions of one.
#
# A miss is silent the whole way up -- get_class_map -> {} -> get_level -> -1 ->
# enter_to_level -> False -> nothing recorded -> a lesson reporting "FAILED,
# 0s". So get_class_map ASKS EACH host in turn and takes the first that really
# holds the class, instead of trusting whichever host was right last month.
# See _vt_data_bases().
_VT_DATA_API_DEFAULT = "https://green.vocatooki.com/data"
# `os` is imported far below, so read the override the same way VT_TASKS_API
# does rather than moving an import and disturbing the module's load order.
VT_DATA_API = os.getenv("VT_DATA_API") or _VT_DATA_API_DEFAULT

# The hosts a class map is looked for on, in order. They hold DIFFERENT class
# sets -- none is "the" backend (get-class-map probed 2026-09-22):
#
#   green     2336 (55 lessons), 651 (45)   <- the classes the suite runs
#   vtbetest  35 (55), 1 (45)
#   vtbe2027  651 (45), 35 (55), 1 (45)
#   vtbe      answers, but held none of 2336/651/35/1 -- not in the auto chain
#
# green leads so the classes the tests use cost no wasted round-trip; the
# others follow for the classes only they have. All are asked before anything
# is called missing.
_VT_DATA_API_HOSTS_DEFAULT = (
    "https://green.vocatooki.com/data",
    "https://vtbetest.vocatooki.com/data",
    "https://vtbe2027.vocatooki.com/data",
)

# The backends a run can be POINTED at, by the names the team uses. The runner
# panel asks for one before every run (user, 2026-09-22) and hands it over as
# VT_BACKEND; "auto" keeps the ask-each-host chain above.
VT_BACKEND_AUTO = "auto"
VT_BACKENDS = {
    "green": "https://green.vocatooki.com/data",
    "vtbe": "https://vtbe.vocatooki.com/data",
    "vtbetest": "https://vtbetest.vocatooki.com/data",
    "vtbe2027": "https://vtbe2027.vocatooki.com/data",
}
_VT_BACKEND = VT_BACKEND_AUTO
# What the environment said before any backend was chosen, so "auto" can put
# it back instead of wiping an override someone set in their own shell.
_VT_ENV_AT_IMPORT = {k: os.environ.get(k)
                     for k in ("VT_DATA_API", "VT_DATA_API_HOSTS", "VT_TASKS_API")}


def current_backend():
    """The backend this process was pointed at: a VT_BACKENDS key, or 'auto'."""
    return _VT_BACKEND


def backend_pinned():
    """True when a run named its backend — nothing may then quietly switch it."""
    return _VT_BACKEND != VT_BACKEND_AUTO


def set_backend(name):
    """Point EVERY data call at one backend, or back to the auto chain.

    Covers get-class-map (pinned, no fallback), get-user-state, get-user-exams
    and the task endpoints. Takes effect at once — module globals are rewritten,
    not just the environment, because VT_DATA_API / VT_TASKS_API are read at
    import time. Also clears the per-class host memo, or a class resolved under
    the previous backend would keep its old host. Returns the name applied.
    """
    global _VT_BACKEND, VT_DATA_API, VT_TASKS_API
    _os = os
    key = (name or VT_BACKEND_AUTO).strip().lower()
    if key != VT_BACKEND_AUTO and key not in VT_BACKENDS:
        raise ValueError(f"unknown backend '{name}' — choose one of "
                         f"{[VT_BACKEND_AUTO] + list(VT_BACKENDS)}")

    if key == VT_BACKEND_AUTO:
        for env_key, value in _VT_ENV_AT_IMPORT.items():
            if value is None:
                _os.environ.pop(env_key, None)
            else:
                _os.environ[env_key] = value
        VT_DATA_API = _VT_ENV_AT_IMPORT["VT_DATA_API"] or _VT_DATA_API_DEFAULT
        VT_TASKS_API = _VT_ENV_AT_IMPORT["VT_TASKS_API"] or _VT_TASKS_API_DEFAULT
    else:
        base = VT_BACKENDS[key]
        _os.environ["VT_DATA_API"] = base          # _vt_data_bases(): pin, no fallback
        _os.environ.pop("VT_DATA_API_HOSTS", None)
        _os.environ["VT_TASKS_API"] = base
        VT_DATA_API = VT_TASKS_API = base
    _os.environ["VT_BACKEND"] = key
    _CLASS_MAP_HOST.clear()
    _VT_BACKEND = key
    logging.info(f"[Backend] {key}" + ("" if key == VT_BACKEND_AUTO
                                       else f" -> {VT_BACKENDS[key]}"))
    return key


def _vt_data_bases():
    """The data hosts to ask for a class map, in order, without duplicates.

    VT_DATA_API_HOSTS (comma-separated) replaces the list outright. A bare
    VT_DATA_API instead PINS the lookup to that single host: someone who names
    an environment wants THAT environment's data, and a quiet fallback to a
    different one is exactly the half-here-half-there mismatch this file has
    already been bitten by.
    """
    _os = os
    listed = _os.getenv("VT_DATA_API_HOSTS")
    pinned = _os.getenv("VT_DATA_API")
    if listed:
        bases = [b.strip() for b in listed.split(",") if b.strip()]
    elif pinned:
        bases = [pinned]
    else:
        bases = list(_VT_DATA_API_HOSTS_DEFAULT)

    ordered, seen = [], set()
    for base in bases:
        base = base.rstrip("/")
        if base and base not in seen:
            seen.add(base)
            ordered.append(base)
    return ordered


# The environment the app under test talks to. `green` is where the task data
# lives for the accounts these tests use; override with VT_TASKS_API when
# pointing at another environment.
_VT_TASKS_API_DEFAULT = "https://green.vocatooki.com/data"
VT_TASKS_API = (os.getenv("VT_TASKS_API")
                or _VT_TASKS_API_DEFAULT)


# Which host last served a given class, so a run that resolves ten lessons pays
# the losing host's 404 once instead of ten times.
_CLASS_MAP_HOST = {}


def get_class_map(class_id, map_id):
    """
    Fetches the class map configuration from the backend.

    Asks each host in _vt_data_bases() in turn and returns the first that
    actually holds the map, so a class that has moved environments is still
    found. On total failure it logs what EVERY host said, because an unread
    class map makes get_level return -1 and only surfaces much later, as a
    lesson that "FAILED, 0s".

    Args:
        class_id (int): ID of the class.
        map_id (int): ID of the map (typically 1).

    Returns:
        dict: Map data as JSON, or an empty dict on failure.
    """
    bases = _vt_data_bases()
    # Ask whichever host answered for this class last time first.
    known = _CLASS_MAP_HOST.get(str(class_id))
    if known in bases:
        bases = [known] + [b for b in bases if b != known]

    logging.info(f"[get_class_map] Fetching map for class_id={class_id}, map_id={map_id}")
    tried = []

    for base in bases:
        url = f"{base}/get-class-map/{class_id}/{map_id}"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            code = getattr(getattr(e, "response", None), "status_code", "?")
            tried.append(f"{base} -> HTTP {code}")
            continue
        except requests.exceptions.RequestException as e:
            tried.append(f"{base} -> {type(e).__name__}")
            continue
        except ValueError:
            tried.append(f"{base} -> unparseable JSON")
            continue

        # What makes an answer usable is levels: get_level indexes straight
        # into map["levels"], so a 200 carrying an empty map is no more use
        # than a 404. Either way the host is saying "not mine" -- keep asking.
        #
        # Do NOT check data["class_id"] against class_id to decide: it is not
        # the class that was asked for. Asking vtbetest for class 1 answers
        # class_id 5, and green for 999 answers 85 -- it names the curriculum
        # behind the class, so matching on it would throw away good maps.
        levels = data.get("map", {}).get("levels") if isinstance(data.get("map"), dict) else None
        if not levels:
            tried.append(f"{base} -> 200 but no usable map.levels")
            continue

        _CLASS_MAP_HOST[str(class_id)] = base
        logging.info(f"[get_class_map] class_id={class_id} served by {base} "
                     f"({len(levels)} lessons)")
        return data

    logging.error(
        f"[get_class_map] no host holds class_id={class_id} map_id={map_id}: "
        + "; ".join(tried)
    )
    return {}



def get_user_state(user_id, avatar_version, awards_version, lessons_version, add_is_complete):
    payload = {
        "user_id": user_id,
        "avatar_version": avatar_version,
        "awards_version": awards_version,
        "lessons_version": lessons_version,
        "add_is_complete": add_is_complete
    }
    try:
        response = requests.post(f"{VT_DATA_API}/get-user-state", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[ERROR] Fetching user state failed: {e}")
        return None


# A run launched by the panel names its backend in VT_BACKEND (the pytest
# subprocess inherits it). Applied at the very end, once VT_TASKS_API and
# _CLASS_MAP_HOST exist. An unknown name is reported and falls back to auto.
if os.getenv("VT_BACKEND"):
    try:
        set_backend(os.getenv("VT_BACKEND"))
    except ValueError as _e:
        logging.error(f"[Backend] {_e}; using auto")
        set_backend(VT_BACKEND_AUTO)
