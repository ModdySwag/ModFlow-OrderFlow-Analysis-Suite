# Builds ModFlowBridge.dll with the .NET SDK — no admin, no Visual Studio required.
#
#   powershell -ExecutionPolicy Bypass -File build.ps1
#
# Sources:   src\*.cs            (compiled against the NinjaTrader 8 assemblies in Program Files)
# Output:    ModFlowBridge.dll   (this folder — the artifact the suite ships)
#
# Deploy after a build:
#   copy ModFlowBridge.dll  ->  Documents\NinjaTrader 8\bin\Custom\AddOns\
#   restart NinjaTrader (with Tools > Options > General > Miscellaneous >
#   "Allow custom assembly loading" enabled at least once)
param([string]$Dotnet = "")

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-Dotnet {
    if ($Dotnet) { return $Dotnet }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'dotnet-sdk\dotnet.exe'),
        'C:\Program Files\dotnet\dotnet.exe'
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'no dotnet CLI found — install the .NET SDK (https://learn.microsoft.com/dotnet/core/install/windows) or pass -Dotnet <path-to-dotnet.exe>'
}

$dotnet = Find-Dotnet
& $dotnet build (Join-Path $here 'src\ModFlowBridge.csproj') -c Release -v minimal
if ($LASTEXITCODE -ne 0) { throw 'build failed' }

$built = Join-Path $here 'src\bin\Release\ModFlowBridge.dll'
$artifact = Join-Path $here 'ModFlowBridge.dll'
Copy-Item $built $artifact -Force
$hash = (Get-FileHash $artifact -Algorithm SHA256).Hash.ToLower()
Write-Output ("built and copied: " + $artifact)
Write-Output ("sha256: " + $hash)
