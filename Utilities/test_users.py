USE_SINGLE_USER = True  # ✅ Toggle this to True for single-user tests

# 👤 Used only when USE_SINGLE_USER is True
SINGLE_USER = {
    "username": "vt01274560008",
    "password": "3453",
    "class_id": 7456,
    "lesson_nums": [0, 1],
    "target_language": "Hebrew"  # Example: Hebrew
}

# 👥 Used when USE_SINGLE_USER = False
ALL_USERS = [
    {
        "username": "vt01274560008",
        "password": "3453",
        "class_id": 7456,
        "lesson_nums": [1, 2, 3],
        "target_language": "En"
    },
    {
        "username": "vt56988190001",
        "password": "3882",
        "class_id": 8819,
        "lesson_nums": [0, 1],
        "target_language": "DE"
    },
    {
        "username": "vt56789610001",
        "password": "2944",
        "class_id": 8961,
        "lesson_nums": [2],
        "target_language": "PT"
    },
]