# installer/ — the ModFlow OrderFlow Analysis Suite Windows installer

This folder builds the shipped setup.exe from the frozen `dist\ModFlowOrderFlowAnalysisSuite\`
payload. It was authored as part of the §69 pass and every line below was verified end to end on
this machine (see "Verified journey" at the bottom).

## What it produces

- `ModFlowOrderFlowAnalysisSuite.ism` — the InstallShield project, regenerated from the blank
  Basic MSI template on every run (never hand-edit it; edit `make_installer.ps1` instead)
- `build\...\DiskImages\DISK1\setup.exe` — raw IsCmdBld output (compressed network image)
- `..\dist\ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` — the release artifact

Latest build: 41,770,193 bytes (39.84 MB), sha256
`8EE41AF5E8B52C04F44FB46515B42312ABB66FB5043A7966DBF1E2F7E5A40F2A`

## How to rebuild

InstallShield's automation server (ISWiAuto32) is 32-bit only, so the script must run under the
32-bit Windows PowerShell:

```
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File C:\Users\Moddy\OrderFlow-Analysis-Pro\installer\make_installer.ps1
```

Requires: InstallShield 2026 at `C:\Program Files (x86)\InstallShield\2026`, and a current
`dist` (run `scripts\build_exe.py` first if the app changed).

## Design decisions (all deliberate)

- **Per-user install, no UAC**: `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`, with
  `ALLUSERS=2` + `MSIINSTALLPERUSER=1` + `ApplicationUsers=OnlyCurrentUser` in the package.
  Note: when the setup is run from an already-elevated shell (as the test journey was), Windows
  Installer records the Add/Remove entry under HKLM; a normal double-click run records it per
  user. Either way the files land in the user's LocalAppData and uninstall cleans up.
- **User data is never touched**: the app's config/DB live in `%APPDATA%\OrderFlowAnalysisPro`.
  The installer neither writes nor removes anything there; upgrades and uninstalls leave it alone.
- **Payload = one dynamic folder link** to the frozen `dist` folder (minus the main exe, which
  ships as a static file entry so the shortcut can target it). Rebuilding the installer always
  packages whatever `dist` currently contains.
- **Desktop shortcut**: created during install, pointing at the installed exe
  (`ModFlow OrderFlow Analysis Suite.lnk`), removed on uninstall.
- **UpgradeCode `{C2042089-3E19-410D-ABA6-C32BC9C13D80}` is FIXED** — never change it, or future
  versions stop recognising this product for upgrades. ProductCode/PackageCode are re-minted on
  every build (correct MSI practice).

## Known notes / future work

- **Start Menu shortcut**: InstallShield's automation API cannot create additional shortcut-folder
  destinations (the component's set is fixed to [TaskBarFolder]/[SendToFolder]/[DesktopFolder],
  and folder roots are immutable — probed exhaustively). To add a Start Menu shortcut later:
  open the .ism in the InstallShield IDE → Application Shortcuts → add `[ProgramMenuFolder]` →
  save & rebuild with IsCmdBld. (Alternatively keep the desktop shortcut as the only entry point,
  which is what v0.1.0-beta ships.)
- **WebView2 prerequisite**: the app's UI needs the Microsoft Edge WebView2 Runtime (present by
  default on Windows 10/11 via Edge). The chain-package route was probed but the automation
  cannot source the bootstrapper payload, so it is NOT chained in this build. The ready-to-use
  prerequisite definition ships at `SetupPrerequisites\WebView2.prq`; to enable it: drop the
  Evergreen bootstrapper (`https://go.microsoft.com/fwlink/p/?LinkId=2124703`) into the folder
  the .prq points at, then add it via the IDE's Prerequisites view once.
- **InstallShield runs in evaluation mode on this machine** ("compressed Network Image setup.exe"
  is the only allowed build type). That happens to be exactly the artifact this project wants.
  Shipping publicly long-term may want a licensed build or the Inno Setup fallback (installed).
- `installer\build\` is regenerable build output — exclude it from the repo (add to .gitignore at
  commit time if you don't want it tracked).

## The traps this script encodes (measured the hard way)

1. `ISWiAuto32` is a 32-bit COM server — 64-bit PowerShell fails with REGDB_E_CLASSNOTREG.
2. `CreateProject`'s parameter binder is broken from PowerShell; instead copy
   `Support\0409\IsProjBlankTpl.ism` and `OpenProject` it.
3. `AttachComponent` only binds when passed the component OBJECT via IDispatch (strings fail).
4. `AddFile` must be called natively (`$comp.AddFile($path)`); the reflection InvokeMember route
   intermittently fails with DISP_E_TYPEMISMATCH.
5. A file's **DisplayName IS the destination filename** — setting it to the product name installs
   the exe extension-less as "ModFlow OrderFlow Analysis Suite". Set it to the file name.
6. `AddShortcut(<file-identifier>)` creates the row, but: its `Target` defaults to the FEATURE
   (advertised shortcut → silently skipped by /qn installs) and must be set to `[#<FileKey>]`;
   and the Shortcut.Name cell references string `ID_STRING1`, which the build validator rejects
   unless it holds an 8.3-style short name — set it to `MODFLO~1|ModFlow OrderFlow Analysis Suite`
   (the short|long convention InstallShield's own samples use).
7. `IsCmdBld -b` wants a backslash path; forward slashes fail with "Invalid release location".
8. Never reassign `$comp.Destination` (it is already [INSTALLDIR]); doing so breaks the follow-up
   AddFile call.

## Verified journey (2026-09-16)

Silent install (`setup.exe /s /v"/qn"`) → 494 files / 49.28 MB under
`%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`, exe under its own name, desktop shortcut
created with the correct target and description → installed app launched headless on 8098
(healthz 200, BTCUSDT candles 200, UNKNOWNXYZ `[]`) → silent uninstall → install dir, shortcut and
Add/Remove entry all gone. The machine's pre-existing development shortcut was preserved and
restored after testing.

Verified again on 2026-09-18 (the full fold-in payload): silent install -> **600 files**, the
installed exe's sha256 equal to the dist exe's -> app headless on 8097 (healthz 200,
`/api/candles/BTCUSDT` 200 / 173,439 B, `UNKNOWNXYZ` `[]`) -> ARP entry found in
`HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{FA4E31A6-840E-4581-A1E0-4C950A96E0FD}`
-> silent uninstall -> install dir, desktop shortcut and the ARP entry all gone, `%APPDATA%`
untouched. Frozen-exe smoke on the same payload: 18/18, including asset parity (73/73 shell refs
byte-identical), 11/11 help screenshots, the level-radar endpoint and the education corpus
answering from inside the build, and a clean client-error log.

Verified again on 2026-09-18 (the index-instrument UX pass: timeframe persistence, the Data-menu
index explainer, the one-click Alpaca source switch and the Alpaca asset lane): silent install ->
**600 files**, the installed exe's sha256 equal to the dist exe's (`CD895044…`) -> app headless
on 8097 (healthz 200, `/api/candles/BTCUSDT` 200 / 173,401 B, `UNKNOWNXYZ` `[]`) -> ARP entry in
`HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{0561F1EC-8E61-46CB-A123-076ED6964D3D}`
(product codes re-mint each build) -> silent uninstall -> install dir, desktop shortcut and the
ARP entry all gone, `%APPDATA%` untouched, development shortcut restored. Frozen-exe smoke on the
same payload: 18/18 including asset parity (73/73 shell refs byte-identical); new-code receipts:
`/api/control/alpaca/assets` answers from inside the build and the served `menubar.js` hashes
equal to the tree's.
