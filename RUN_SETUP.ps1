param([switch]$SkipChecks = $false)

$ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AltTester MCP - Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if (-not $SkipChecks) {
    Write-Host "[1] Checking environment...`n" -ForegroundColor Yellow

    $python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
    if (Test-Path $python) {
        $ver = & $python --version 2>&1
        Write-Host "  [OK] Python: $ver"
    } else {
        Write-Host "  [FAIL] Python not found" -ForegroundColor Red
        exit 1
    }

    $pytest = & $python -m pytest --version 2>&1 | Select-Object -First 1
    Write-Host "  [OK] pytest: $pytest"
}

Write-Host "`n[2] Checking AltTester CLI...`n" -ForegroundColor Yellow

$altFound = $false
try {
    $altver = alttester --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] AltTester: $altver"
        $altFound = $true
    }
} catch {}

if (-not $altFound) {
    Write-Host "  [WARN] AltTester CLI not found" -ForegroundColor Yellow
    Write-Host "`n  Install AltTester:
    1. Launch AltTester Desktop
    2. Click 'Download' button
    3. Or: Settings > Configure AI Extension > Setup
    4. Restart this terminal after installing
    5. Re-run this script`n" -ForegroundColor Cyan
    exit 1
}

Write-Host "`n[3] Next steps:`n" -ForegroundColor Yellow

Write-Host "  Terminal 1 (Keep Open):" -ForegroundColor Green
Write-Host "    alttester mcp`n"

Write-Host "  Terminal 2 (Different):" -ForegroundColor Green
Write-Host "    cd '$ProjectPath'"
Write-Host "    .venv\Scripts\python -m pytest Tests\test_alttester_mcp_example.py -v -s`n"

Write-Host "  Terminal 3 (Your Game):" -ForegroundColor Green
Write-Host "    Launch your game with AltTester SDK`n"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Read-Host "Press Enter when ready"
