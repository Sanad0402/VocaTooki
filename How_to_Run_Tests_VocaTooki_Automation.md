# ✅ How to Run Tests in the Automation Framework

This guide explains how to run tests for your Voca Tooki automation project, using markers, specific files, platforms, or a dynamic parallel runner.

---

## 🖥️ 1. Run All Tests

```bash
pytest
```
Runs all tests across all files and markers.

---

## 📄 2. Run a Specific Test File

```bash
pytest test_batch_gameplay.py
```

---

## 🧪 3. Run by Marker (Test Type)

You can run a specific group of tests using the marker system defined in `pytest.ini`.

| Marker     | Command                                | Description                                  |
|------------|----------------------------------------|----------------------------------------------|
| `express`  | `pytest -m express`                    | Run gameplay lesson tests                    |
| `sanity`   | `pytest -m sanity`                     | Run basic start scene and navigation tests   |
| `dialogues`| `pytest -m dialogues`                  | Run dialogue-based lessons                   |
| `exams`    | `pytest -m exams`                      | Run exam-type lessons                        |
| `test`     | `pytest -m test`                       | Run custom simple test cases                 |

Example: Run both express and dialogues:
```bash
pytest -m "express or dialogues"
```

---

## 🔍 4. Run Specific Test Function

From any file:
```bash
pytest -k "test_batch_lessons"
```

From a specific file:
```bash
pytest test_batch_gameplay.py -k "lesson"
```

---

## 🎯 5. Run Tests on a Specific Platform (Command Line)

```powershell
pytest -s -v Sanity/test_batch_gameplay.py `
  --platform=WindowsEditor `
  --app_id=56750000 `
  --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 `
  -m test
```

You can change the platform to:
- `WindowsEditor`
- `Android`
- `WebGL`
- `WindowsBuild`

---

## 🧵 6. Run Parallel Tests via Dynamic Runner (Multi-Device + Multi-Test)

Use the dynamic runner file:
```bash
run_parallel_dynamic.bat
```

✅ This batch file is configurable and supports multiple runs like this:
```
set CONFIGS[0]=WindowsEditor|13C50000|DEVICE_ID|test_NavigateStartScene.py|sanity
set CONFIGS[1]=Android|com.vocatooki.app|DEVICE_ID|test_batch_gameplay.py|express
set CONFIGS[2]=WebGL|WebGLAppId|DEVICE_ID|test_users.py|dialogues
```
Each test runs in a separate terminal window.

📝 Edit this file to change:
- Test file to run
- Platform/app ID
- Device ID
- Optional `-m` marker (or leave blank)

---

## 🧠 Pro Tip: Use a Single or Multiple Users

Edit `test_users.py` to switch:
```python
USE_SINGLE_USER = True  # Run tests with only 1 user

# or
USE_SINGLE_USER = False  # Run tests with all users
```

Each user can include a `target_language` field.
You can print it inside your test:
```python
print(f"[INFO] Running tests for user: {username}, Target Language: {user_case['target_language']}")
```
For example, inside `test_batch_lessons` or `test_project_1`:
```python
print(f"[SUCCESS] Login passed for: {username}, Target Language: {user_case['target_language']}")
```

---

## 📄 Final Report

After all tests run, the execution report will be saved to:
```
C:\Users\sanad\Downloads\reports\activity_report_<timestamp>.txt
```

This includes:
- Activity name with difficulty
- Platform used
- Pass/Fail status
- Error message (if any)

---

## ✅ Summary of Common Commands

| Task                             | Command |
|----------------------------------|---------|
| Run all tests                    | `pytest` |
| Run express tests only           | `pytest -m express` |
| Run sanity + dialogues           | `pytest -m "sanity or dialogues"` |
| Run specific file                | `pytest test_batch_gameplay.py` |
| Run by test function             | `pytest -k "test_login"` |
| Run on WindowsEditor platform    | `pytest Sanity/test_batch_gameplay.py --platform=WindowsEditor --app_id=56750000 --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 -m sanity` |
| Run on Android platform          | `pytest test_file.py --platform=Android --app_id=... --device_instance_id=...` |
| Run dynamic parallel tests       | `run_parallel_dynamic.bat` |

run in powershell :
"pytest -s -v Sanity/test_batch_gameplay.py `
  --platform=WindowsEditor `
  --app_id=56750000 `
  --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 `
  -m test"

run in cmd(to be in the automation proj) : 
"Sanity/test_batch_gameplay.py --platform=WindowsEditor --app_id=56750000 --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 -m test"