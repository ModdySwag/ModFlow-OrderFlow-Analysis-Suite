# sign_release.ps1 - sign the release binaries and verify the signatures.
#
#   # with a certificate in the store (its thumbprint):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sign_release.ps1 `
#       -Thumbprint <SHA1 thumbprint> -Path dist\ModFlowOrderFlowAnalysisSuite\ModFlowOrderFlowAnalysisSuite.exe `
#       -Path dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe
#
#   # or with a .pfx (password via the environment, never on the command line):
#   $env:OFAP_SIGN_PFX_PASSWORD = '...'
#   ... -PfxPath C:\keys\moddy-codesign.pfx
#
# Why this exists (audit F-11): the released binaries are unsigned, so Windows SmartScreen warns on
# every download and nothing proves who built them. A certificate cannot be created by a script -
# it is bought (OV ~AU$300/yr, EV ~AU$600/yr) and identity-verified - so this script is the
# mechanical half: find the tools, sign with a timestamp, verify, and report what is still missing.
#
# Nothing here needs admin: signtool is fetched into %LOCALAPPDATA%\ModFlow\sdk-tools when absent.

param(
    [Parameter(Mandatory = $true)][string[]]$Path,
    [string]$Thumbprint = $env:OFAP_SIGN_THUMBPRINT,
    [string]$PfxPath = $env:OFAP_SIGN_PFX,
    [string]$PfxPassword = $env:OFAP_SIGN_PFX_PASSWORD,
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [switch]$SkipFetch
)

$ErrorActionPreference = 'Stop'

function Find-SignTool {
    $candidates = @()
    $sdkRoot = 'C:\Program Files (x86)\Windows Kits\10\bin'
    if (Test-Path $sdkRoot) {
        $candidates += Get-ChildItem -Path $sdkRoot -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\' } |
            Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    }
    $candidates += (Join-Path $env:LOCALAPPDATA 'ModFlow\sdk-tools\signtool.exe')
    $onPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    return $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

function Install-SignTool {
    # The Windows SDK ships signtool.exe inside the NuGet build-tools package; fetching that is far
    # lighter than installing the whole SDK.
    $dest = Join-Path $env:LOCALAPPDATA 'ModFlow\sdk-tools'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $nupkg = Join-Path $env:TEMP 'Microsoft.Windows.SDK.BuildTools.zip'
    if (-not (Test-Path $nupkg)) {
        $index = Invoke-RestMethod 'https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/index.json'
        $ver = $index.versions[-1]
        Write-Host "fetching Microsoft.Windows.SDK.BuildTools $ver (for signtool.exe)..."
        Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/$ver/microsoft.windows.sdk.buildtools.$ver.nupkg" -OutFile $nupkg -UseBasicParsing
    }
    $tmp = Join-Path $env:TEMP 'sdk-buildtools-extract'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $nupkg -DestinationPath $tmp -Force
    $found = Get-ChildItem -Path $tmp -Filter signtool.exe -Recurse |
        Where-Object { $_.FullName -match '\\x64\\' } | Select-Object -First 1
    if (-not $found) { throw 'signtool.exe was not found inside the build-tools package' }
    Copy-Item $found.FullName $dest -Force
    Copy-Item (Join-Path $found.DirectoryName 'Microsoft.Windows.SDK.BuildTools.dll') $dest -Force -ErrorAction SilentlyContinue
    # F-10: the extraction scratch (hundreds of MB) does not stay behind in %TEMP%
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
    return (Join-Path $dest 'signtool.exe')
}

foreach ($p in $Path) {
    if (-not (Test-Path $p)) { throw "nothing to sign at: $p" }
}

if (-not $Thumbprint -and -not $PfxPath) {
    Write-Host ''
    Write-Host 'No certificate configured - nothing was signed.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'To sign, one of these must exist:'
    Write-Host '  * a code-signing certificate in the user store:  Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert'
    Write-Host '    then pass -Thumbprint <thumbprint> (or set OFAP_SIGN_THUMBPRINT)'
    Write-Host '  * a .pfx file:                                    -PfxPath <file> with $env:OFAP_SIGN_PFX_PASSWORD'
    Write-Host ''
    Write-Host 'Until then the setup and the exe stay unsigned: Windows SmartScreen will warn on every'
    Write-Host 'download and nothing attests who built them (audit F-11). The rest of the release is ready -'
    Write-Host 'docs\RELEASE_CHECKLIST.md section 6 lists what the certificate changes.'
    exit 3
}

$signtool = Find-SignTool
if (-not $signtool -and -not $SkipFetch) { $signtool = Install-SignTool }
if (-not $signtool) { throw "signtool.exe not found and -SkipFetch was given. Install the Windows SDK or drop signtool.exe into $env:LOCALAPPDATA\ModFlow\sdk-tools" }
Write-Host "signtool: $signtool"

$signArgs = @('sign', '/fd', 'sha256', '/tr', $TimestampUrl, '/td', 'sha256')
if ($Thumbprint) { $signArgs += @('/sha1', $Thumbprint, '/sm') ; Write-Host "certificate: store thumbprint $Thumbprint" }
else {
    $signArgs += @('/f', $PfxPath)
    if ($PfxPassword) { $signArgs += @('/p', $PfxPassword) }
    Write-Host "certificate: $PfxPath"
}

$failed = @()
foreach ($p in $Path) {
    Write-Host "signing $p ..."
    & $signtool @signArgs $p
    if ($LASTEXITCODE -ne 0) { $failed += $p; continue }
    & $signtool verify /pa /v $p | Out-Null
    if ($LASTEXITCODE -ne 0) { $failed += $p; continue }
    Write-Host "  signed + verified: $p"
}

if ($failed.Count) { throw ("signature failed for: " + ($failed -join ', ')) }
Write-Host ''
Write-Host 'All binaries signed and verified. Record the certificate subject in the release notes.'
