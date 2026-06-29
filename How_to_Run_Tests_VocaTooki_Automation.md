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
"pytest Sanity/test_batch_gameplay.py -s --platform=WindowsEditor --app_id=D590000 --device_instance_id=73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48 -m sanity"
"pytest Sanity/test_multiuser_solve_lesson.py --platform WindowsEditor --user-mode single"

Pick a different user:
"pytest Sanity/test_multiuser_solve_lesson.py --platform WindowsEditor --user-mode single --user-index 1"

All users :
"pytest Sanity/test_multiuser_solve_lesson.py --platform WindowsEditor --user-mode all"

run for spefic lesson :
"pytest -q Sanity/test_single_lesson_express.py --lesson=4 --class-id=8821"

run by runner :
python scripts/test_runner.py --config runner.json

{ "testDomains": ["sanity1"],
  "reportOut": ["sanad@kideo.tech"],
  "errorFiles": "C:/Users/sanad/Downloads/reports/errors.txt",
  "screenShotsFolder": "C:/Users/sanad/Downloads/screenshots",
  "reportFileName": "C:/Users/sanad/Downloads/reports/RunReport.txt",
  "testsPath": "Sanity",
  "extraPytestArgs": [],
  "levelsOnly": false,
  "lessons": [-1,0,1,2,3,4,5],
  "userMode": "single", 
  "userIndex": 0,
  "platform": "WindowsEditor",
  "appId": "5DD30000",
  "deviceInstanceId": "73e60e7d6bbb26eb2e71b16c2c479c0f1dadbb48"
}

  "userMode": "single", or  'all'
  "lessons": [-1,0,1,2,3,4,5], or   "lesson": 2

---

## 🖥️ Server config — Runner Panel (`run_panel.py`)

The control panel is a Flask app served at **http://localhost:5000**
(`run_panel.py`, last line: `app.run(host="127.0.0.1", port=5000, ...)`).
Users are entered in the panel's **Users** block; the AltTester
host/port the runs connect to (default `127.0.0.1:13000`) is set per run
under **Connection (advanced)**.

### Start

Double-click `run_panel.bat`, or from the project root:
```bat
.venv\Scripts\python.exe run_panel.py
```
`run_panel.bat` is smart: if port 5000 is already listening it just opens
the browser; otherwise it starts the server, waits, then opens it.

### Restart (stop the running instance, then start again)

**cmd:**
```bat
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":5000 " ^| findstr LISTENING') do taskkill /PID %a /F
run_panel.bat
```
(inside a `.bat` file, double the percent signs: `%%a`)

**PowerShell:**
```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen |
  Select-Object -ExpandProperty OwningProcess |
  ForEach-Object { Stop-Process -Id $_ -Force }
.\.venv\Scripts\python.exe run_panel.py
```

### Stop only
```bat
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":5000 " ^| findstr LISTENING') do taskkill /PID %a /F
```

### Change the panel port
Edit the `port=5000` in the last line of `run_panel.py`, then update the
`:5000` checks in `run_panel.bat` to match.

> Note: this is Flask's built-in **development** server, bound to
> `127.0.0.1` (this machine only). It does not auto-start on boot — run it
> with one of the commands above.


