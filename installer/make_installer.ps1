# make_installer.ps1 - build the ModFlow OrderFlow Analysis Suite installer from the frozen dist.
#
# Run under 32-BIT PowerShell (the ISWiAuto32 automation server is 32-bit only):
#   C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File make_installer.ps1
#
# What it produces:
#   installer\ModFlowOrderFlowAnalysisSuite.ism        (regenerated from the blank Basic MSI template each run)
#   installer\build\...\DiskImages\DISK1\setup.exe     (IsCmdBld output, compressed network image)
#   ..\dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe  (the release artifact, + its sha256)
#
# Design notes (all verified by probe against InstallShield 2026 on this machine):
#   * per-user install, no UAC: [LocalAppDataFolder]Programs\ModFlowOrderFlowAnalysisSuite, ALLUSERS=2 + MSIINSTALLPERUSER=1
#   * user data untouched: the app's config/DB live in %APPDATA%\OrderFlowAnalysisPro - the installer never writes or removes them
#   * the payload = the frozen dist folder: one dynamic folder link, minus the main exe (which ships as a static
#     file entry so the shortcut can target it)
#   * shortcut: Desktop only. Start Menu shortcut destinations are NOT creatable through this automation API
#     (the component's shortcut-folder set is fixed to [TaskBarFolder]/[SendToFolder]/[DesktopFolder]);
#     see installer\README.md for the one-click IDE route to add a Start Menu shortcut later.
#   * WebView2 prerequisite: NOT chained (the automation cannot source the bootstrapper payload; see README).
#   * UpgradeCode is FIXED below - never change it, or upgrades stop recognising previous installs.
#   * builds run in InstallShield evaluation mode on this machine, which is limited to the compressed
#     network image setup.exe - exactly the artifact this project wants anyway.

param(
    [string]$RepoRoot = 'C:\Users\Moddy\OrderFlow-Analysis-Pro',
    [string]$DistDir = '',
    [string]$InstallerDir = '',
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
if (-not $DistDir)      { $DistDir      = Join-Path $RepoRoot 'dist\ModFlowOrderFlowAnalysisSuite' }
if (-not $InstallerDir) { $InstallerDir = Join-Path $RepoRoot 'installer' }

$isRoot   = 'C:\Program Files (x86)\InstallShield\2026'
$tpl      = Join-Path $isRoot 'Support\0409\IsProjBlankTpl.ism'
$isCmdBld = Join-Path $isRoot 'System\IsCmdBld.exe'
$ism      = Join-Path $InstallerDir 'ModFlowOrderFlowAnalysisSuite.ism'
$outRoot  = Join-Path $InstallerDir 'build'
$setupSrc = Join-Path $outRoot 'Product Configuration 1\Release 1\DiskImages\DISK1\setup.exe'
$setupOut = Join-Path $RepoRoot 'dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe'

$appName = 'ModFlow OrderFlow Analysis Suite'
$exeName = 'ModFlowOrderFlowAnalysisSuite.exe'
$appExe  = Join-Path $DistDir $exeName

# product identity - FIXED forever (upgrades recognise this product by it)
$UpgradeCode = '{C2042089-3E19-410D-ABA6-C32BC9C13D80}'

foreach ($need in @($tpl, $isCmdBld)) { if (-not (Test-Path $need)) { throw "missing: $need" } }
if (-not (Test-Path $appExe)) { throw "dist exe missing: $appExe - rebuild the frozen dist first (scripts\build_exe.py)" }

New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null
Copy-Item $tpl $ism -Force

$proj = New-Object -ComObject ISWiAuto32.ISWiProject
$proj.OpenProject($ism)

# -- identity --
$proj.ProductName    = $appName
$proj.ProductVersion = '0.1.0'
$proj.CompanyName    = 'ModdySwag'
$proj.INSTALLDIR     = '[LocalAppDataFolder]Programs\ModFlowOrderFlowAnalysisSuite'
$g = $proj.GenerateGUID(); $proj.ProductCode = '{' + $g.Trim('{}') + '}'
$g = $proj.GenerateGUID(); $proj.PackageCode = '{' + $g.Trim('{}') + '}'
$proj.UpgradeCode    = $UpgradeCode

# -- per-user install context --
# ALLUSERS=2 + MSIINSTALLPERUSER=1 = per-user, no UAC; ApplicationUsers is the template's own
# "install for" switch (blank template ships AllUsers) and must agree or ARP lands machine-wide.
foreach ($pr in @($proj.ISWIProperties)) {
    if ($pr.Name -eq 'ALLUSERS') { $pr.Value = '2' }
    if ($pr.Name -eq 'ApplicationUsers') { $pr.Value = 'OnlyCurrentUser' }
}
$mp = $proj.AddProperty('MSIINSTALLPERUSER'); $mp.Value = '1'

# -- feature + component (AttachComponent takes the component OBJECT, not its name) --
# note: component destination is already [INSTALLDIR] by default; do NOT reassign the
# Destination property here - setting it makes the follow-up AddFile fail with a type
# mismatch (measured). --
$null = $proj.AddFeature('Application')
$comp = $proj.AddComponent('AppFiles')
$feat = $proj.ISWiFeatures.Item(1)
$null = $feat.GetType().InvokeMember('AttachComponent', [System.Reflection.BindingFlags]::InvokeMethod, $null, $feat, [object[]]@($comp))

# -- payload: static exe entry (shortcut target) + dynamic link for everything else --
# AddFile must be called natively - the reflection InvokeMember path fails intermittently
# with DISP_E_TYPEMISMATCH for this method (measured).
$file = $comp.AddFile($appExe)
$file.Name = $exeName
# DisplayName is the DESTINATION FILENAME in InstallShield's File table - it must be the actual
# file name, not the product name (the product name here once installed the exe extension-less
# as 'ModFlow OrderFlow Analysis Suite', which in turn orphaned the shortcut's target).
$file.DisplayName = $exeName

$link = $comp.AddDynamicFileLinking('AppFilesLink')
$link.SourceFolder = $DistDir
$link.DynamicSubfolders = $true
$link.ExcludeFiles = $exeName

# -- desktop shortcut --
$desktop = $null
foreach ($fo in @($comp.ISWiFolders)) { if ($fo.Name -eq '[DesktopFolder]') { $desktop = $fo } }
if ($null -eq $desktop) { throw 'DesktopFolder missing on component' }
$sc = $desktop.GetType().InvokeMember('AddShortcut', [System.Reflection.BindingFlags]::InvokeMethod, $null, $desktop, [object[]]@($exeName))
$sc.DisplayName = $appName
$sc.Description = 'Launch the ModFlow OrderFlow Analysis Suite'
# AddShortcut leaves Target pointing at the FEATURE (= an advertised shortcut), and a plain
# file name is silently skipped by CreateShortcuts too. The documented MSI form is a formatted
# file reference [#FileKey] - with the static file named after the exe its key IS the file name
# (measured against working vendor MSIs: [#wsl.exe], [#Putty_File], [#AllRemixes.exe]).
$sc.Target = '[#' + $exeName + ']'

# The automation leaves the Shortcut.Name cell pointing at string ID_STRING1 whose value is the
# file identifier - but IS's build validator rejects any non-8.3 value there ("does not contain a
# legitimate value for table Shortcut column Name"). Set it to a short|long pair, the convention
# InstallShield's own sample projects use ('TUTORIAL|Tutorial App'). This is the one string-table
# write the shortcut workflow needs; everything else about the shortcut is already correct.
$lang = $proj.ISWiLanguages.Item(1)
$fixed = $false
foreach ($e in @($lang.ISWiStringEntries)) {
    if ($e.Id -eq 'ID_STRING1') {
        $e.Value = 'MODFLO~1|' + $appName
        $fixed = $true
    }
}
if (-not $fixed) { throw 'ID_STRING1 not found in the string table - InstallShield version drift?' }

$proj.SaveProject()
$proj.CloseProject()
Write-Host "project written: $ism"

if ($SkipBuild) { exit 0 }

# -- build --
if (Test-Path $outRoot) { Remove-Item $outRoot -Recurse -Force }
$proc = Start-Process -FilePath $isCmdBld -ArgumentList @('-p', $ism, '-b', $outRoot) -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0) { throw "IsCmdBld failed: exit $($proc.ExitCode)" }
if (-not (Test-Path $setupSrc)) { throw "setup.exe not found: $setupSrc" }

Copy-Item $setupSrc $setupOut -Force
$hash = (Get-FileHash $setupOut -Algorithm SHA256).Hash
$size = (Get-Item $setupOut).Length
Write-Host ("setup.exe -> " + $setupOut)
Write-Host ("size: " + $size + " bytes (" + [math]::Round($size / 1MB, 2) + " MB)")
Write-Host ("sha256: " + $hash)
