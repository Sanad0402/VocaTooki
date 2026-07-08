#========================================================================
# AltTester MCP Setup Script (PowerShell)
# Automates setup and verification
#========================================================================

$ErrorActionPreference = "Continue"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n========================================================================" -ForegroundColor Cyan
Write-Host "         AltTester MCP Setup & Verification" -ForegroundColor Cyan
Write-Host "========================================================================`n" -ForegroundColor Cyan

# ========================================================================
# Helper functions
# ========================================================================

function Test-Command {
    param([string]$CommandName)
    $null = Get-Command $CommandName -ErrorAction SilentlyContinue
    return $?
}

function Show-Pass {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Show-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Show-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Show-Step {
    param([string]$Message)
    Write-Host "`n$Message" -ForegroundColor Cyan -BackgroundColor Black
    Write-Host "=========================================================================" -ForegroundColor Cyan
}

# ========================================================================
# STEP 1: Check Python
# ========================================================================

Show-Step "[STEP 1] Checking Python environment..."

$pythonPath = Join-Path $ScriptPath ".venv\Scripts\python.exe"
if (Test-Path $pythonPath) {
    $pythonVer = & $pythonPath --version 2>&1
    Show-Pass "Python found: $pythonVer"
} else {
    Show-Fail "Python not found at $pythonPath"
    exit 1
}

# ========================================================================
# STEP 2: Check pytest
# ========================================================================

Show-Step "[STEP 2] Checking pytest..."

try {
    $pytestVer = & $pythonPath -m pytest --version 2>&1 | Select-Object -First 1
    Show-Pass "pytest found: $pytestVer"
} catch {
    Show-Fail "pytest not found"
    exit 1
}

# ========================================================================
# STEP 3: Check AltTester CLI
# ========================================================================

Show-Step "[STEP 3] Checking AltTester CLI..."

if (Test-Command alttester) {
    $alttesterVer = alttester --version 2>&1
    Show-Pass "AltTester CLI found: $alttesterVer"
} else {
    Show-Warn "AltTester CLI not found in PATH"
    Write-Host "`nTo install AltTester CLI:"
    Write-Host "  1. Launch AltTester Desktop"
    Write-Host "  2. Click 'Download' button"
    Write-Host "  3. Or: Settings > Configure AI Extension > Setup"
    Write-Host "  4. Restart PowerShell after installing"
    Write-Host "`nAfter installing, run this script again.`n"
    Read-Host "Press Enter to exit"
    exit 1
}

# ========================================================================
# STEP 4: Check registered games
# ========================================================================

Show-Step "[STEP 4] Checking for registered games..."

try {
    $games = alttester apps --timeout 5 2>&1
    if ($games) {
        Show-Pass "Game(s) found"
        Write-Host $games
    } else {
        Show-Warn "No game detected"
        Write-Host "`nMake sure to:"
        Write-Host "  1. Start your game with AltTester SDK enabled"
        Write-Host "  2. Game must listen on port 13000 (default)"
        Write-Host "  3. Check with: alttester apps"
    }
} catch {
    Show-Warn "Could not check for games"
}

# ========================================================================
# STEP 5: Run Python verification script
# ========================================================================

Show-Step "[STEP 5] Running setup verification..."

Write-Host "`n"
& $pythonPath verify_alttester_setup.py

# ========================================================================
# STEP 6: Show next steps
# ========================================================================

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host "NEXT STEPS - Follow these commands in order:" -ForegroundColor Green
Write-Host "========================================================================`n" -ForegroundColor Green

Write-Host "COMMAND 1 - Start MCP Server (keep this terminal open):" -ForegroundColor Yellow
Write-Host "  PowerShell> alttester mcp`n" -ForegroundColor White

Write-Host "COMMAND 2 - Start your game (NEW terminal):" -ForegroundColor Yellow
Write-Host "  (Launch your game with AltTester SDK enabled)`n" -ForegroundColor White

Write-Host "COMMAND 3 - Run tests (NEW terminal):" -ForegroundColor Yellow
Write-Host "  PowerShell> cd '$ScriptPath'" -ForegroundColor White
Write-Host "  PowerShell> .venv\Scripts\python -m pytest Tests/test_alttester_mcp_example.py -v -s`n" -ForegroundColor White

Write-Host "========================================================================" -ForegroundColor Green
Write-Host "For more details, see: ALTTESTER_MCP_SETUP.md" -ForegroundColor Green
Write-Host "========================================================================`n" -ForegroundColor Green

Read-Host "Press Enter to exit"
