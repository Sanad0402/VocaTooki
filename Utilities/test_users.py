USE_SINGLE_USER = True  # ✅ Toggle this to True for single-user tests

# 👤 Used only when USE_SINGLE_USER is True
SINGLE_USER = {
    "username": "vt01274560008",
    "password": "3453",
    "class_id": 7456,
    "lesson_nums": [1, 2]
}

# 👥 Used when USE_SINGLE_USER = False
ALL_USERS = [
    {
        "username": "vt01274560008",
        "password": "3453",
        "class_id": 7456,
        "lesson_nums": [1, 2, 3]
    },
    {
        "username": "vt01274560009",
        "password": "1234",
        "class_id": 8320,
        "lesson_nums": [0, 1]
    },
    {
        "username": "vt01274560010",
        "password": "5678",
        "class_id": 9010,
        "lesson_nums": [2]
    },
]