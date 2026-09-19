# installer/ — the ModFlow OrderFlow Analysis Suite Windows setup

Builds the shipped `setup.exe` from the frozen `dist\ModFlowOrderFlowAnalysisSuite\` payload.

## What it produces

- `..\dist\ModFlowOrderFlowAnalysisSuite-Setup-<version>.exe` — the release artifact
- `..\dist\ModFlowOrderFlowAnalysisSuite-Setup-<version>.exe.sha256` — its hash, for the release page
- `prereq\MicrosoftEdgeWebview2Setup.exe` — fetched at build time (not committed), embedded so the
  setup can install the WebView2 runtime when it is missing

## Why Inno Setup (and why the InstallShield project is gone)

The v0.1.0-beta setup was a Basic MSI produced by driving InstallShield 2026's automation server
from `make_installer.ps1`. The v0.1b audit left three findings that pipeline could not close:

| Finding | What it was | How the Inno pipeline closes it |
|---|---|---|
| F-05 | The MSI was built in **InstallShield evaluation mode** — a licensing caveat on a shipped installer | Inno Setup is free software; the toolchain carries no caveat |
| F-06 | The WebView2 `.prq` shipped but was **never chained** into the setup | The setup detects the runtime and runs Microsoft's Evergreen bootstrapper when it is absent |
| E-05 | The binary `.ism` embedded the maintainer's absolute path | The installer is plain text (`modflow.iss`); the `.ism` and the unused `.prq` were deleted |

`AppId` carries over the old MSI `UpgradeCode` (`{C2042089-3E19-410D-ABA6-C32BC9C13D80}`), so a
machine that has the MSI build installed is recognised as the same product and replaced in place.
Never change that GUID.

## How to rebuild

```
powershell -NoProfile -ExecutionPolicy Bypass -File installer\make_installer.ps1
```

Requires: Inno Setup 6 (per-user install at `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, or the
machine-wide locations — the script checks all three) and a current `dist`
(`scripts\build_exe.py`). The version comes from `pyproject.toml`, so the installer cannot drift
from the app.

The script fetches Microsoft's WebView2 bootstrapper when `prereq\` is empty (fwlink 2124703,
~1.8 MB) and prints its hash; `-SkipWebView2Fetch` builds without it, in which case the setup tells
the user where to download the runtime instead.

## Design decisions (kept from the MSI pipeline)

- **Per-user install, no UAC**: `PrivilegesRequired=lowest`, install dir
  `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`.
- **User data is never touched**: the app's config/logs/database live in
  `%APPDATA%\OrderFlowAnalysisPro`. The installer neither writes nor removes anything there, and
  the uninstaller deliberately leaves it behind — upgrades cannot clobber settings.
- **Start Menu + optional desktop shortcut**: the old automation could only create the desktop
  entry; Inno always creates the Start Menu entry and offers the desktop icon as a task.
- **`CloseApplications=yes`**: an upgrade asks the running app to close instead of failing on
  locked files.
- **Payload = whatever `dist` currently holds** — rebuild `dist` first when the app changes.

## Verification journey (run this before publishing)

```powershell
# 1. install silently into a scratch directory, with a log
.\dist\ModFlowOrderFlowAnalysisSuite-Setup-<version>.exe /VERYSILENT /SUPPRESSMSGBOXES `
    /DIR="$env:TEMP\ofap-install-test" /LOG="$env:TEMP\ofap-install.log"

# 2. files + registry
Get-ChildItem "$env:TEMP\ofap-install-test"            # the frozen payload, incl. the exe
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1"

# 3. the installed app boots
$env:APPDATA = "$env:TEMP\ofap-install-appdata"
& "$env:TEMP\ofap-install-test\ModFlowOrderFlowAnalysisSuite.exe" --headless --port 8099   # in another shell: curl /healthz

# 4. uninstall silently
& "$env:TEMP\ofap-install-test\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES
# install dir gone, ARP entry gone, %APPDATA%\OrderFlowAnalysisPro untouched
```

The measured results of this journey on the Inno pipeline are recorded at the bottom of this file.

## Signing

The binaries are **unsigned**. The route is decided (see `docs\RELEASE_CHECKLIST.md` §6):

- **SignPath Foundation** (free for qualifying open-source projects) is wired up and inert: the
  artifact configuration is committed at `.signpath/artifact-configurations/default.xml`, and the
  `sign` job in CI stays skipped until the repository carries `SIGNPATH_ORGANIZATION_ID` (variable)
  and `SIGNPATH_API_TOKEN` (secret). Apply at signpath.org; after approval every CI build signs
  automatically.
- **Local signing** with a certificate you own: `scripts\sign_release.ps1 -Thumbprint <sha1>`
  (or `-PfxPath` with `OFAP_SIGN_PFX_PASSWORD`) signs, timestamps and verifies the exe and the
  setup; it fetches signtool from the Windows SDK build tools when absent, and with no certificate
  it exits 3 and prints what is missing.
- Azure Artifact Signing is **not** available to individual developers outside the USA/Canada, so
  it was ruled out for this project.

## History — the MSI pipeline and its verified journeys

The InstallShield automation and the install journeys verified on it (2026-09-16 and 2026-09-18:
silent install → 600 files, installed-exe hash equal to the dist exe, headless boot on 8097
answering `/healthz` 200 and `/api/candles/BTCUSDT` 200, ARP entry under
`HKLM\...\Uninstall\{…}`, silent uninstall leaving no files, no shortcut and no ARP entry, with
`%APPDATA%` untouched) are recorded in git history at `45172b1` and earlier. That pipeline's known
traps — the 32-bit-only `ISWiAuto32` server, `AttachComponent` binding, the
`DisplayName`-is-the-filename rule, the advertised-shortcut `Target`, the string-table 8.3 name —
are preserved in the `installer-authoring` skill rather than here, since the project no longer uses
InstallShield.

## Verified journey (Inno pipeline) - measured 2026-09-19

- **Build**: `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, 37,622,650 bytes (37.62 MB), sha256
  `7623C718E041E82951FD3AA3325310D80B2C82975754D53BBD5EBF57A1ADAD48`; the WebView2 bootstrapper embedded in it is 1.76 MB, sha256
  `83004A28553BCF2F932BF03564FBAB407B8E1F59CD265F8DC99CC53D028E459C`.
  The payload it wraps: 891 files (226 developer files pruned) → 42,946,702 bytes (42.9 MB)
  zipped (`scripts/make_release.py`, sha256 `36af140ac1…`);
  CycloneDX SBOM, sha256 `33de958bf2…`.
  dist exe: 15.3 MB, sha256 `7be98b115a…`. The shipped build passes the hover-info audit
  (`scripts/hover_audit.py`) and the Profiles workflow probe (`receipts/profiles_probe_frozen.json`).
- **Silent install** (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<scratch>`): exit 0, **893 files**
  (the 891-file payload + `unins000.exe`/`.dat`), installed exe sha256 equal to the dist exe's
  (`b3347bb5...`), ARP entry under
  `HKCU\...\Uninstall\{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1`, Start Menu entry created,
  desktop icon correctly skipped (task unchecked), setup log clean (`HKEY_CURRENT_USER`, 64-bit).
- **Installed app**: headless on 8099 -> `/healthz` 200, `/desktop` 200, `/api/control/bootstrap` 200,
  `/docs` 404, `/redoc` 404, `/openapi.json` 404.
- **Silent uninstall**: install dir gone, ARP entry gone, Start Menu entry gone,
  `%APPDATA%\OrderFlowAnalysisPro` untouched, port released.
- **WebView2 branch**: the runtime is present on this machine (v153), so the setup's check skipped the
  bootstrapper exactly as designed (nothing extracted in the log). The missing-runtime branch is
  untested here - try it on a clean image per `docs\RELEASE_CHECKLIST.md` section 5.
