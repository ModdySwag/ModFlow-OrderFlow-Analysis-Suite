; ModFlow OrderFlow Analysis Suite - Inno Setup script.
;
; Build it with make_installer.ps1 (which passes /DAppVersion and, when available, the WebView2
; bootstrapper). This script replaces the InstallShield project the release used to ship, closing
; three audit findings in one move:
;   F-05 - the MSI was built in InstallShield evaluation mode; Inno is free, so the pipeline
;          carries no licensing caveat.
;   F-06 - the WebView2 prerequisite was a .prq that was never chained; here the setup detects the
;          runtime and runs Microsoft's bootstrapper (or points at the download) when it is absent.
;   E-05 - the binary .ism embedded the maintainer's absolute path; this installer is plain text.
;
; Conventions kept from the MSI pipeline:
;   * per-user install, no UAC ({localappdata}\Programs\...);
;   * the app's data (%APPDATA%\OrderFlowAnalysisPro: config, logs, database) is never written or
;     removed by the installer or the uninstaller, so upgrades cannot clobber it;
;   * AppId is the old MSI UpgradeCode, so an existing install is recognised and replaced rather
;     than duplicated. Never change it.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "ModFlow OrderFlow Analysis Suite"
#define AppExeName "ModFlowOrderFlowAnalysisSuite.exe"
#define AppPublisher "ModdySwag"
#define AppURL "https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite"
#define AppId "{{C2042089-3E19-410D-ABA6-C32BC9C13D80}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={localappdata}\Programs\ModFlowOrderFlowAnalysisSuite
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=ModFlowOrderFlowAnalysisSuite-Setup-{#AppVersion}
SetupIconFile=..\orderflow_system\desktop\ui\app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
SetupLogging=yes
; The binaries are unsigned until a code-signing certificate is bought - see
; scripts\sign_release.ps1 and docs\RELEASE_CHECKLIST.md ?6.
SignedUninstaller=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ModFlowOrderFlowAnalysisSuite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef WebView2Bootstrapper
; Microsoft's Evergreen bootstrapper, carried in the setup and extracted only when the runtime is
; missing (see CurStepChanged below).
Source: "{#WebView2Bootstrapper}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: WebView2Missing
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nothing: the app's data lives in %APPDATA%\OrderFlowAnalysisPro and is deliberately left alone.

[Code]
const
  WebView2Key = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2Installed(): Boolean;
begin
  { The Evergreen runtime registers under this key: per-machine in the 64-bit view and under
    WOW6432Node on machines that got it with a 32-bit app, or per-user. Any of the three means
    "present". }
  Result :=
    RegKeyExists(HKLM64, WebView2Key) or
    RegKeyExists(HKLM32, WebView2Key) or
    RegKeyExists(HKCU, WebView2Key);
end;

function WebView2Missing(): Boolean;
begin
  Result := not WebView2Installed();
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Bootstrapper: String;
begin
  if (CurStep = ssPostInstall) and WebView2Missing() then
  begin
    Bootstrapper := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
    if FileExists(Bootstrapper) then
    begin
      { /silent /install: the Evergreen bootstrapper installs for the current user when it can. }
      if (not Exec(Bootstrapper, '/silent /install', '', SW_SHOW, ewWaitUntilTerminated, ResultCode))
         or (ResultCode <> 0) then
        MsgBox('The Microsoft Edge WebView2 Runtime could not be installed automatically (code ' +
               IntToStr(ResultCode) + ').' + #13#10 + #13#10 +
               'Install it from https://go.microsoft.com/fwlink/p/?LinkId=2124703 and start ' +
               '{#AppName} again.', mbInformation, MB_OK);
    end
    else
      MsgBox('Microsoft Edge WebView2 Runtime is required and was not detected.' + #13#10 + #13#10 +
             'Download and install it from https://go.microsoft.com/fwlink/p/?LinkId=2124703, ' +
             'then start {#AppName} again.', mbInformation, MB_OK);
  end;
end;
