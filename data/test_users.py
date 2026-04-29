TEST_USERS = [
    {"username": "vt392702", "password": "4832", "class_id": "3927"},
    {"username": "vt254008", "password": "7012", "class_id": "2540"}

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
