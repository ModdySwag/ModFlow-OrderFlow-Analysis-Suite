# make_installer.ps1 - build the ModFlow OrderFlow Analysis Suite installer from the frozen dist.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File installer\make_installer.ps1
#
# Engine: Inno Setup 6 (ISCC.exe). This replaced the InstallShield pipeline that closed three
# audit findings at once - F-05 (the MSI was built in InstallShield evaluation mode), F-06 (the
# WebView2 .prq was never chained into the setup) and E-05 (the binary .ism carried the
# maintainer's absolute path). The whole installer is now reviewable text: installer\modflow.iss.
#
# What it produces:
#   dist\ModFlowOrderFlowAnalysisSuite-Setup-<version>.exe       (the release artifact)
#   dist\ModFlowOrderFlowAnalysisSuite-Setup-<version>.exe.sha256 (its hash, for the release page)
#
# Conventions kept from the old pipeline: per-user install, no UAC; the app's data
# (%APPDATA%\OrderFlowAnalysisPro) is never written or removed; the AppId GUID is the old MSI
# UpgradeCode, so an existing install is replaced in place.

param(
    # Defaults to this script's own checkout, so a fresh clone builds without editing paths.
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$DistDir = '',
    [string]$InstallerDir = '',
    [switch]$SkipWebView2Fetch
)

$ErrorActionPreference = 'Stop'
if (-not $DistDir)      { $DistDir      = Join-Path $RepoRoot 'dist\ModFlowOrderFlowAnalysisSuite' }
if (-not $InstallerDir) { $InstallerDir = $PSScriptRoot }

# -- the Inno Setup compiler (per-user install first, then the machine-wide ones) ---------------
$iscc = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 compiler (ISCC.exe) not found. Install it from https://jrsoftware.org/isdl.php (per-user install is fine)."
}
Write-Host "compiler: $iscc"

$appExe = Join-Path $DistDir 'ModFlowOrderFlowAnalysisSuite.exe'
if (-not (Test-Path $appExe)) {
    throw "dist exe missing: $appExe - build the frozen dist first (scripts\build_exe.py)"
}

# -- version from ONE source: pyproject.toml ----------------------------------------------------
$version = '0.1.0'
$pyproject = Join-Path $RepoRoot 'pyproject.toml'
if (Test-Path $pyproject) {
    $m = Select-String -Path $pyproject -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($m) { $version = $m.Matches[0].Groups[1].Value }
}
Write-Host "version: $version (pyproject.toml)"

# -- WebView2 bootstrapper: fetch when missing so the setup chains the prerequisite (F-06) ------
# Microsoft's Evergreen bootstrapper (~1.8 MB) downloads and installs the runtime at setup time
# when it is absent. It is fetched, not committed: the URL is Microsoft's own fwlink, and the
# hash of whatever was fetched is printed below. A build without it still works - the setup then
# tells the user where to get the runtime.
$prereq = Join-Path $InstallerDir 'prereq\MicrosoftEdgeWebview2Setup.exe'
$haveBootstrapper = Test-Path $prereq
if (-not $haveBootstrapper -and -not $SkipWebView2Fetch) {
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $prereq) | Out-Null
        Write-Host 'fetching the WebView2 bootstrapper (Microsoft fwlink 2124703)...'
        Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $prereq `
            -UseBasicParsing -TimeoutSec 180
        $haveBootstrapper = Test-Path $prereq
    } catch {
        Write-Warning "WebView2 bootstrapper fetch failed: $($_.Exception.Message)"
        Write-Warning 'building without it - the setup will direct the user to Microsoft if the runtime is missing'
    }
}
if ($haveBootstrapper) {
    $boot = Get-Item $prereq
    $bootHash = (Get-FileHash $prereq -Algorithm SHA256).Hash
    Write-Host ("WebView2 bootstrapper: " + [math]::Round($boot.Length / 1MB, 2) + " MB, sha256 " + $bootHash)
}

# -- build --------------------------------------------------------------------------------------
$iss = Join-Path $InstallerDir 'modflow.iss'
$args = @('/Qp', "/DAppVersion=$version")
if ($haveBootstrapper) { $args += "/DWebView2Bootstrapper=$prereq" }
$args += $iss

& $iscc @args
if ($LASTEXITCODE -ne 0) { throw "ISCC failed: exit $LASTEXITCODE" }

$setupOut = Join-Path $RepoRoot "dist\ModFlowOrderFlowAnalysisSuite-Setup-$version.exe"
if (-not (Test-Path $setupOut)) { throw "setup.exe not found after a successful compile: $setupOut" }

$hash = (Get-FileHash $setupOut -Algorithm SHA256).Hash
$size = (Get-Item $setupOut).Length
Set-Content -Path "$setupOut.sha256" -Value ($hash + '  ' + (Split-Path $setupOut -Leaf)) -Encoding ascii

Write-Host ("setup.exe -> " + $setupOut)
Write-Host ("size: " + $size + " bytes (" + [math]::Round($size / 1MB, 2) + " MB)")
Write-Host ("sha256: " + $hash)
Write-Host "verify on a clean machine with the checklist in docs\RELEASE_CHECKLIST.md (section 3)."
