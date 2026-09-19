# verify_installer.ps1 - the whole install journey, scripted, PASS/FAIL per step.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify_installer.ps1
#   ... -SetupPath <exe> -TestDir <dir>          # defaults: newest setup in dist\, %TEMP%\ofap-install-verify
#
# Run this on a CLEAN machine or profile before publishing (docs\RELEASE_CHECKLIST.md section 5):
# it installs silently into a scratch directory, checks the files, the Add/Remove entry and the
# Start Menu entry, boots the installed app headless and probes /healthz + /docs, then uninstalls
# and checks everything is gone and %APPDATA%\OrderFlowAnalysisPro is untouched.
#
# Nothing here needs admin: the installer is per-user by design.

param(
    [string]$SetupPath = '',
    [string]$TestDir = (Join-Path $env:TEMP 'ofap-install-verify'),
    [int]$Port = 8098,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$AppId = '{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1'
$ArpKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
$AppDataDir = Join-Path $env:APPDATA 'OrderFlowAnalysisPro'
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\ModFlow OrderFlow Analysis Suite.lnk'

if (-not $SetupPath) {
    $SetupPath = Get-ChildItem -Path (Join-Path $RepoRoot 'dist') -Filter 'ModFlowOrderFlowAnalysisSuite-Setup-*.exe' |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $SetupPath -or -not (Test-Path $SetupPath)) { throw "setup not found - build it first: installer\make_installer.ps1" }

$results = @()
function Step([string]$Name, [scriptblock]$Body) {
    try {
        $detail = & $Body
        $script:results += [pscustomobject]@{ Step = $Name; Result = 'PASS'; Detail = $detail }
        Write-Host ("PASS  " + $Name + "  " + $detail) -ForegroundColor Green
    } catch {
        $script:results += [pscustomobject]@{ Step = $Name; Result = 'FAIL'; Detail = $_.Exception.Message }
        Write-Host ("FAIL  " + $Name + "  " + $_.Exception.Message) -ForegroundColor Red
    }
}

Write-Host "setup:    $SetupPath"
Write-Host "test dir: $TestDir"
Write-Host ''

if (Test-Path $TestDir)      { Remove-Item $TestDir -Recurse -Force }
if (Test-Path $ArpKey)       { throw "an install already exists ($ArpKey) - uninstall it before verifying" }
$appDataBefore = Test-Path $AppDataDir

$installLog = Join-Path $env:TEMP 'ofap-install-verify.log'
$setupExeHash = (Get-FileHash $SetupPath -Algorithm SHA256).Hash

Step 'silent install' {
    $p = Start-Process -FilePath $SetupPath `
        -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$TestDir", "/LOG=$installLog") `
        -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "setup exit $($p.ExitCode) (log: $installLog)" }
    Start-Sleep -Seconds 2
    "exit 0, log $installLog"
}

Step 'payload landed' {
    $exe = Join-Path $TestDir 'ModFlowOrderFlowAnalysisSuite.exe'
    if (-not (Test-Path $exe)) { throw "exe missing in $TestDir" }
    $count = (Get-ChildItem $TestDir -Recurse -File).Count
    if ($count -lt 100) { throw "only $count files in the install dir" }
    "$count files, installer sha256 $($setupExeHash.Substring(0,16))..."
}

Step 'Add/Remove entry' {
    if (-not (Test-Path $ArpKey)) { throw "no ARP entry at $ArpKey" }
    (Get-ItemProperty $ArpKey).DisplayName
}

Step 'Start Menu entry' {
    if (-not (Test-Path $StartMenu)) { throw "no shortcut at $StartMenu" }
    'shortcut present'
}

Step 'installed app boots (headless)' {
    # The scratch profile lives OUTSIDE the install dir: the app writes its data to
    # %APPDATA%\OrderFlowAnalysisPro, and putting it inside the test dir made the uninstaller
    # leave that (foreign) directory behind - a false red on "install dir gone".
    $appData = Join-Path $env:TEMP 'ofap-install-verify-appdata'
    New-Item -ItemType Directory -Force -Path $appData | Out-Null
    $env:APPDATA = $appData
    $proc = Start-Process -FilePath (Join-Path $TestDir 'ModFlowOrderFlowAnalysisSuite.exe') `
        -ArgumentList @('--headless', '--port', "$Port") -PassThru -WindowStyle Hidden
    $healthy = $false
    foreach ($i in 1..40) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$Port/healthz"
            if ($r.StatusCode -eq 200) { $healthy = $true; break }
        } catch { }
    }
    if (-not $healthy) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue; throw "no /healthz within 40 s" }
    $desktop = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$Port/desktop").StatusCode
    $docs = 0
    try { $docs = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$Port/docs").StatusCode } catch {
        if ($_.Exception.Response) { $docs = [int]$_.Exception.Response.StatusCode } else { $docs = -1 }
    }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    if ($desktop -ne 200) { throw "/desktop answered $desktop" }
    if ($docs -ne 404) { throw "/docs answered $docs - expected 404 in the packaged build (F-11)" }
    "healthz 200, /desktop 200, /docs 404"
}

Step 'port released' {
    $listening = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listening) { throw "port $Port still listening" }
    'free'
}

Step 'silent uninstall' {
    $unins = Join-Path $TestDir 'unins000.exe'
    if (-not (Test-Path $unins)) { throw "no uninstaller at $unins" }
    $p = Start-Process -FilePath $unins -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
    Start-Sleep -Seconds 5
    if ($p.ExitCode -ne 0) { throw "uninstaller exit $($p.ExitCode)" }
    'exit 0'
}

Step 'install dir gone' {
    if (Test-Path $TestDir) { throw "still there: $TestDir" }
    'removed'
}

Step 'Add/Remove entry gone' {
    if (Test-Path $ArpKey) { throw "ARP entry still present: $ArpKey" }
    'removed'
}

Step 'Start Menu entry gone' {
    if (Test-Path $StartMenu) { throw "shortcut still present: $StartMenu" }
    'removed'
}

Step 'user data untouched' {
    if ($appDataBefore -and -not (Test-Path $AppDataDir)) { throw "$AppDataDir disappeared" }
    if ($appDataBefore) { "$AppDataDir intact" } else { 'not present before or after (fine)' }
}

# F-10: the scratch profile, the install log and any stray test dir do not stay in %TEMP%
foreach ($scratch in @($TestDir, $installLog)) {
    if ($scratch -and (Test-Path $scratch)) { Remove-Item $scratch -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host ''
$failed = @($results | Where-Object { $_.Result -eq 'FAIL' })   # @(): one object is not an array in PS 5.1
if ($failed) {
    Write-Host ("VERIFY FAILED - " + $failed.Count + " step(s) red") -ForegroundColor Red
    exit 1
}
Write-Host ("VERIFY PASSED - " + $results.Count + " steps green") -ForegroundColor Green
