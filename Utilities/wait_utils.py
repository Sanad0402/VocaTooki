import time

def wait_until(fn, timeout=10.0, interval=0.25, on_timeout=None):
    """
    Polls fn() until it returns a truthy value or timeout expires.
    Returns the truthy value from fn(). Raises TimeoutError otherwise.
    """
    end = time.time() + timeout
    last_exc = None
    while time.time() < end:
        try:
            val = fn()
            if val:
                return val
        except Exception as e:
            last_exc = e
        time.sleep(interval)
    if on_timeout:
        on_timeout()
    raise TimeoutError(last_exc or "Condition not met within timeout")


def wait_for_object(driver, by, value, timeout=10.0, interval=0.25):
    """
    Generic waiter around AltTester driver methods.
    Tries driver.wait_for_object if available, otherwise polls driver.find_object.
    """
    native_wait = getattr(driver, "wait_for_object", None)
    if callable(native_wait):
        return native_wait(by, value, timeout)

    find_object = getattr(driver, "find_object", None)
    if not callable(find_object):
        raise AttributeError("Driver does not support find_object or wait_for_object")

    end = time.time() + timeout
    while time.time() < end:
        try:
            obj = find_object(by, value)
            if obj:
                return obj
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Object not found: {by}={value} within {timeout}s")
