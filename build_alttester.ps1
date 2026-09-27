<#
.SYNOPSIS
    Builds AltTester instrumented players of Voca Tooki for Android and WebGL.

.DESCRIPTION
    Drives Unity in batch mode against AltTesterBuild.cs (Assets/Editor) in the game
    project. The Unity Editor must be closed first, it holds a lock on the project.

    iOS is not covered on purpose: Unity on Windows can only export an Xcode project,
    turning that into an .ipa needs a Mac.

.EXAMPLE
    .\build_alttester.ps1
    .\build_alttester.ps1 -Platforms webgl -Development
    .\build_alttester.ps1 -AltHost 192.168.1.20 -AltPort 13000 -AppName VocaTooki
#>
[CmdletBinding()]
param(
    [ValidateSet('android', 'webgl', 'both')]
    [string]$Platforms = 'both',

    [string]$Project = 'C:\Work\voca_tooki',
    [string]$Unity,
    [string]$Output = 'C:\Work\builds\alttester',

    [string]$AltHost = '127.0.0.1',
    [int]$AltPort = 13000,
    [string]$AppName = '__default__',

    [switch]$Development,
    [switch]$NoGraphics
)

$ErrorActionPreference = 'Stop'

function Resolve-UnityExe {
    param([string]$ProjectPath)

    $versionFile = Join-Path $ProjectPath 'ProjectSettings\ProjectVersion.txt'
    if (-not (Test-Path $versionFile)) {
        throw "Not a Unity project: $ProjectPath"
    }
    $version = ((Get-Content $versionFile -TotalCount 1) -split ':\s*')[1].Trim()

    $candidates = @(
        "C:\Work\Unity\Editor\$version\Editor\Unity.exe",
        "C:\Program Files\Unity\Hub\Editor\$version\Editor\Unity.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw "No Unity $version install found. Looked in: $($candidates -join ', ')"
}

function Assert-EditorClosed {
    param([string]$ProjectPath)

    $needle = $ProjectPath.TrimEnd('\')
    $open = Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Replace('/', '\') -like "*$needle*" }

    if ($open) {
        $pids = ($open | ForEach-Object { $_.ProcessId }) -join ', '
        throw "Unity has $ProjectPath open (PID $pids). Close the Editor, a batch mode build cannot take the project lock."
    }
}

function Invoke-UnityBuild {
    param(
        [string]$UnityExe,
        [string]$ProjectPath,
        [string]$BuildTarget,
        [string]$Method,
        [string]$LogFile
    )

    $unityArgs = @(
        '-batchmode'
        '-quit'
        '-accept-apiupdate'
        '-projectPath', $ProjectPath
        '-buildTarget', $BuildTarget
        '-executeMethod', $Method
        '-logFile', $LogFile
        '-altOutput', $Output
        '-altHost', $AltHost
        '-altPort', "$AltPort"
        '-altAppName', $AppName
    )
    if ($Development) { $unityArgs += '-altDevelopment' }
    if ($NoGraphics) { $unityArgs += '-nographics' }

    Write-Host "[$BuildTarget] building, log -> $LogFile" -ForegroundColor Cyan
    $started = Get-Date
    $process = Start-Process -FilePath $UnityExe -ArgumentList $unityArgs -Wait -PassThru -NoNewWindow
    $elapsed = (Get-Date) - $started

    if (Test-Path $LogFile) {
        Select-String -Path $LogFile -Pattern '\[AltTesterBuild\]' | ForEach-Object { Write-Host "    $($_.Line.Trim())" }
    }

    if ($process.ExitCode -eq 0) {
        Write-Host ("[$BuildTarget] OK in {0:hh\:mm\:ss}" -f $elapsed) -ForegroundColor Green
    }
    else {
        Write-Host ("[$BuildTarget] FAILED (exit {0}) after {1:hh\:mm\:ss}" -f $process.ExitCode, $elapsed) -ForegroundColor Red
        if (Test-Path $LogFile) {
            Write-Host '    --- last 30 log lines ---' -ForegroundColor DarkGray
            Get-Content $LogFile -Tail 30 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }
    }
    return $process.ExitCode
}

$unityExe = $Unity
if (-not $unityExe) { $unityExe = Resolve-UnityExe -ProjectPath $Project }
Assert-EditorClosed -ProjectPath $Project

$logDir = Join-Path $Output 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

$targets = @()
if ($Platforms -eq 'both' -or $Platforms -eq 'android') {
    $targets += @{ Name = 'Android'; Method = 'AltTesterBuild.Android' }
}
if ($Platforms -eq 'both' -or $Platforms -eq 'webgl') {
    $targets += @{ Name = 'WebGL'; Method = 'AltTesterBuild.WebGL' }
}

Write-Host "Unity   : $unityExe"
Write-Host "Project : $Project"
Write-Host "Output  : $Output"
Write-Host "AltTester: $AltHost`:$AltPort  app '$AppName'"
Write-Host ''

$failures = 0
foreach ($target in $targets) {
    $log = Join-Path $logDir "$($target.Name.ToLower())-$stamp.log"
    $code = Invoke-UnityBuild -UnityExe $unityExe -ProjectPath $Project -BuildTarget $target.Name -Method $target.Method -LogFile $log
    if ($code -ne 0) { $failures++ }
}

Write-Host ''
if ($failures -eq 0) {
    Write-Host 'All requested builds succeeded.' -ForegroundColor Green
    Get-ChildItem -Path $Output -Exclude 'logs' -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $($_.FullName)" }
    exit 0
}

Write-Host "$failures build(s) failed." -ForegroundColor Red
exit 1
