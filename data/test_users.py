TEST_USERS = [
    {"username": "vt254006", "password": "9241", "class_id": "2540"},
    {"username": "vt233615", "password": "4948", "class_id": "2336"}
]

DEFAULT_CLASS_ID = "CLASS_DEFAULT"

# Backward-compat for older tests
try:
    USE_SINGLE_USER  # type: ignore
except NameError:
    USE_SINGLE_USER = False

try:
    SINGLE_USER  # type: ignore
except NameError:
    SINGLE_USER = TEST_USERS[0] if TEST_USERS else {}

try:
    ALL_USERS  # type: ignore
except NameError:
    ALL_USERS = TEST_USERS
# Backward-compat for older tests
try:
    USE_SINGLE_USER  # type: ignore
except NameError:
    USE_SINGLE_USER = False

try:
    SINGLE_USER  # type: ignore
except NameError:
    SINGLE_USER = TEST_USERS[0] if TEST_USERS else {}

try:
    ALL_USERS  # type: ignore
except NameError:
    ALL_USERS = TEST_USERS
