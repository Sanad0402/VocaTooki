"""Keeping the AltTester connection alive across a long run.

After a long run AltTester can drop the driver: the app's AltTester panel then
shows "Waiting for Driver to connect", and every later command raises
alttester ConnectionError at once. ``revive`` reconnects the SAME AltDriver
object (its websocket connection reconnects itself, the way the client already
does on close code 4002), so every holder of the driver -- the panel's MapPage,
the pytest session fixture -- keeps working without being handed a new one.
"""

import logging
import time

# Seconds to wait before each reconnect attempt.
RECONNECT_WAITS = (5, 10, 20, 30, 60)


def alive(driver):
    """True while the AltTester connection still answers. Never raises."""
    conn = getattr(driver, "_connection", None)
    if conn is not None and not getattr(conn, "_is_open", True):
        return False
    try:
        driver.get_current_scene()
        return True
    except Exception as e:                           # noqa: BLE001
        from alttester import exceptions as alt_exc
        return not isinstance(e, alt_exc.ConnectionError)


def close_reason(driver):
    """What the dropped connection left behind: the close code/reason the
    server sent (1006 = torn down without a close frame) and any socket error.
    Read it BEFORE revive(), which clears both."""
    conn = getattr(driver, "_connection", None)
    if conn is None:
        return "no connection object"
    parts = []
    close = getattr(conn, "_close_message", None)
    if close:
        parts.append(f"close code {close[0]}, reason {close[1]!r}")
    errors = list(getattr(conn, "_errors", []) or [])
    if errors:
        parts.append("socket errors: " + "; ".join(repr(e) for e in errors))
    return ", ".join(parts) or "closed with no close frame and no recorded error"


def _reconnect_once(driver):
    conn = driver._connection
    try:
        conn.close()
    except Exception:                                # noqa: BLE001 - already dead
        pass
    # A stale close message or error makes connect() fail straight away.
    conn._close_message = None
    conn._errors.clear()
    conn._driver_registered_called = False
    conn.connect()
    driver.get_current_scene()                       # proves commands go through


def revive(driver, waits=RECONNECT_WAITS, sleep=time.sleep, stopped=lambda: False, log=None):
    """Reconnect ``driver`` in place, with backoff. True once it answers again.

    ``sleep`` / ``stopped`` let the panel make the waits interruptible by Stop;
    ``log`` receives one line per attempt (defaults to logging.warning)."""
    log = log or logging.warning
    log(f"[RECONNECT] AltTester connection lost: {close_reason(driver)}")
    for attempt, wait in enumerate(waits, 1):
        if stopped():
            return False
        log(f"[RECONNECT] AltTester connection lost — attempt {attempt}/{len(waits)} in {wait}s...")
        sleep(wait)
        if stopped():
            return False
        try:
            _reconnect_once(driver)
        except Exception as e:                       # noqa: BLE001
            log(f"[RECONNECT] attempt {attempt} failed: {e}")
            continue
        log("[RECONNECT] Connected again.")
        return True
    return False
