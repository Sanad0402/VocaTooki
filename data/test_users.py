# Test users are auto-loaded from Rally test cases
# No manual configuration needed - credentials come from Rally suite.json

TEST_USERS = []  # Populated dynamically from Rally

DEFAULT_CLASS_ID = "CLASS_DEFAULT"

# Backward-compat for older tests
USE_SINGLE_USER = False
SINGLE_USER = TEST_USERS[0] if TEST_USERS else {}
ALL_USERS = TEST_USERS
