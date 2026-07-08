#========================================================================
# AltTester MCP - Complete Setup Wizard
# This script guides you through the entire setup process
#========================================================================

param(
    [switch]$SkipAltTester = $false
)

$script:ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:ProjectPath = $ScriptPath

# ========================================================================
# Helper Functions
# ========================================================================

function Write-Title {
    param([string]$Text)
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan -BackgroundColor Black
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Number, [string]$Text)
    Write-Host "`n[$Number] $Text" -ForegroundColor Yellow -BackgroundColor Black
}

function Write-Success {
    param([string]$Text)
    Write-Host "    [OK] $Text" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host "    [WARN] $Text" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Text)
    Write-Host "    [FAIL] $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "    → $Text" -ForegroundColor Cyan
}

function Pause-Script {
    param([string]$Message = "Press Enter to continue...")
    Write-Host ""
    Read-Host $Message | Out-Null
}

function Test-Command {
    param([string]$CommandName)
    $null = Get-Command $CommandName -ErrorAction SilentlyContinue
    return $?
}

# ========================================================================
# MAIN WIZARD
# ========================================================================

Write-Title "AltTester MCP Complete Setup Wizard"

Write-Host "
This wizard will guide you through setting up AltTester MCP for your
automation framework. Follow each step carefully.

Prerequisites:
  • Python 3.10+ (you have 3.12.5 ✓)
  • pytest (you have 9.0.3 ✓)
  • AltTester Desktop 2.3.2+ (needs to be installed)
  • Your game with AltTester SDK

Estimated time: 15-20 minutes

" -ForegroundColor Cyan

Pause-Script "Press Enter to start..."

# ========================================================================
# STEP 1: Verify Python & pytest
# ========================================================================

Write-Step "1" "Verifying Python & pytest"

$pythonPath = Join-Path $ProjectPath ".venv\Scripts\python.exe"
$pythonVer = & $pythonPath --version 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Success "Python $pythonVer"
} else {
    Write-Fail "Python not found"
    exit 1
}

$pytestVer = & $pythonPath -m pytest --version 2>&1 | Select-Object -First 1
if ($LASTEXITCODE -eq 0) {
    Write-Success "$pytestVer"
} else {
    Write-Fail "pytest not found"
    exit 1
}

Write-Success "Environment ready"

# ========================================================================
# STEP 2: Check AltTester CLI
# ========================================================================

Write-Step "2" "Checking AltTester CLI"

if (Test-Command alttester) {
    $alttesterVer = alttester --version 2>&1
    Write-Success "AltTester CLI: $alttesterVer"
} else {
    Write-Warn "AltTester CLI not found in PATH"
    Write-Info "You need to install it before continuing"
    Write-Host "
Installation options:

  OPTION A: Auto-Install (Recommended)
    1. Launch AltTester Desktop
    2. Click 'Download' button on start screen
    3. Wait for installation to complete
    4. Close AltTester Desktop
    5. Close and reopen this PowerShell window
    6. Re-run this script

  OPTION B: Manual Install
    1. Launch AltTester Desktop
    2. Go to Settings (gear icon)
    3. Click 'Configure AltTester® AI Extension'
    4. Click 'Open Configuration Setup'
    5. Follow the installation wizard
    6. Restart PowerShell and re-run this script
" -ForegroundColor Yellow

    if ($SkipAltTester) {
        Write-Warning "Skipping AltTester check (--SkipAltTester flag)"
    } else {
        Pause-Script "After installing, press Enter..."
        exit 0
    }
}

# ========================================================================
# STEP 3: Verify Framework Files
# ========================================================================

Write-Step "3" "Verifying framework files"

$files = @(
    ".mcp.json",
    ".claude\settings.json",
    "Utilities\alttester_mcp.py",
    "Tests\test_alttester_mcp_example.py",
    "verify_alttester_setup.py"
)

$allPresent = $true
foreach ($file in $files) {
    $fullPath = Join-Path $ProjectPath $file
    if (Test-Path $fullPath) {
        Write-Success $file
    } else {
        Write-Fail "$file - NOT FOUND"
        $allPresent = $false
    }
}

if (-not $allPresent) {
    Write-Fail "Some files are missing!"
    exit 1
}

Write-Success "All framework files present"

# ========================================================================
# STEP 4: Check Game & MCP Server Status
# ========================================================================

Write-Step "4" "Checking for registered games and MCP server"

Write-Warning "These checks require your game and MCP server to be running"

try {
    $games = alttester apps --timeout 5 2>&1
    if ($games) {
        Write-Success "Game found: $games"
    } else {
        Write-Warning "No game detected (expected if not running)"
    }
} catch {
    Write-Warning "Could not check for games (this is OK if AltTester not running)"
}

# ========================================================================
# STEP 5: Run Environment Verification
# ========================================================================

Write-Step "5" "Running detailed environment check"

Write-Host ""
& $pythonPath verify_alttester_setup.py
Write-Host ""

# ========================================================================
# STEP 6: Show Instructions
# ========================================================================

Write-Title "Setup Instructions"

Write-Host "
Now you need to start the MCP server and run the tests.
Open THREE PowerShell windows and run these commands:

WINDOW 1 - Start MCP Server (KEEP THIS OPEN):
  ────────────────────────────────────────────────────
  alttester mcp

  This starts the MCP server that Claude Code uses.
  Keep this window open during testing.
  You'll see: '[INFO] MCP server started'

WINDOW 2 - Run Tests:
  ────────────────────────────────────────────────────
  cd '$ProjectPath'
  .venv\Scripts\python -m pytest Tests\test_alttester_mcp_example.py -v -s

  This runs the example tests.
  You'll see test results (PASSED/SKIPPED/FAILED).

WINDOW 3 - Your Game:
  ────────────────────────────────────────────────────
  Start your game with AltTester SDK enabled
  Default port: 13000 (no configuration usually needed)

SUCCESS INDICATORS:
  ✓ MCP server shows 'Waiting for connections'
  ✓ Tests show PASSED or SKIPPED (not FAILED)
  ✓ Verify script shows 6/6 checks passing

" -ForegroundColor Cyan

# ========================================================================
# STEP 7: Interactive Menu
# ========================================================================

Write-Title "What Would You Like To Do?"

$options = @(
    "Start MCP Server (alttester mcp)",
    "Run Tests (pytest)",
    "Run Verification (verify_alttester_setup.py)",
    "View Quick Start Guide (QUICK_START.txt)",
    "View Setup Guide (ALTTESTER_MCP_SETUP.md)",
    "View Checklist (EXECUTION_CHECKLIST.md)",
    "Exit Wizard"
)

$choice = 0
while ($true) {
    Write-Host ""
    for ($i = 0; $i -lt $options.Length; $i++) {
        Write-Host "  $($i + 1). $($options[$i])" -ForegroundColor Yellow
    }
    Write-Host ""
    $selection = Read-Host "Choose option (1-$($options.Length))"

    if ($selection -match '^\d+$' -and [int]$selection -ge 1 -and [int]$selection -le $options.Length) {
        $choice = $selection - 1
        break
    }
    Write-Host "Invalid choice. Please try again." -ForegroundColor Red
}

switch ($choice) {
    0 {
        Write-Title "Starting MCP Server"
        Write-Host "
Run this command:
  alttester mcp

Keep this window open during testing.
Press Ctrl+C to stop the server.
" -ForegroundColor Cyan
        Pause-Script
        Write-Host "
Starting MCP server...
" -ForegroundColor Cyan
        alttester mcp
    }
    1 {
        Write-Title "Running Tests"
        Write-Host "
Running pytest tests...
This may take a few seconds.
" -ForegroundColor Cyan
        Pause-Script
        cd $ProjectPath
        .venv\Scripts\python -m pytest Tests\test_alttester_mcp_example.py -v -s
    }
    2 {
        Write-Title "Running Verification"
        Write-Host ""
        Pause-Script
        cd $ProjectPath
        .venv\Scripts\python verify_alttester_setup.py
    }
    3 {
        Write-Title "Quick Start Guide"
        $quickStart = Join-Path $ProjectPath "QUICK_START.txt"
        if (Test-Path $quickStart) {
            Get-Content $quickStart | Out-Host
        } else {
            Write-Error "QUICK_START.txt not found"
        }
    }
    4 {
        Write-Title "Setup Guide"
        $setupGuide = Join-Path $ProjectPath "ALTTESTER_MCP_SETUP.md"
        if (Test-Path $setupGuide) {
            Get-Content $setupGuide -TotalCount 100 | Out-Host
            Write-Host "`n... (see full file for complete guide)" -ForegroundColor Gray
        } else {
            Write-Error "ALTTESTER_MCP_SETUP.md not found"
        }
    }
    5 {
        Write-Title "Execution Checklist"
        $checklist = Join-Path $ProjectPath "EXECUTION_CHECKLIST.md"
        if (Test-Path $checklist) {
            Get-Content $checklist -TotalCount 100 | Out-Host
            Write-Host "`n... (see full file for complete checklist)" -ForegroundColor Gray
        } else {
            Write-Error "EXECUTION_CHECKLIST.md not found"
        }
    }
    6 {
        Write-Title "Setup Complete"
        Write-Host "
Next steps:
  1. Install AltTester CLI (if not done)
  2. Start your game with AltTester SDK
  3. Start MCP server: alttester mcp
  4. Run tests: pytest Tests/test_alttester_mcp_example.py -v -s

For more help, see:
  • QUICK_START.txt - Command reference
  • EXECUTION_CHECKLIST.md - Step-by-step guide
  • ALTTESTER_MCP_SETUP.md - Technical details

Good luck! 🚀
" -ForegroundColor Green
    }
}

Write-Host ""
Pause-Script "Press Enter to exit..."
