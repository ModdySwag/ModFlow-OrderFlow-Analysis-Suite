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

## Verified journey (Inno pipeline, the §125 rebuild) - measured 2026-09-19

- **Build**: the §119–§125 tree (HEAD `797eea0`, worktree dirty; `dist/BUILD_INFO.json` records commit + state, built 2026-09-19T16:03:35+0930). Setup `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, **37,659,252 bytes** (35.91 MB), sha256
  `5B8BF8B46DEAB5F7F004E58530353D340F353EBEC076EEFD7C625A8E2ACE699A`; the WebView2 bootstrapper embedded in it is 1.76 MB, sha256
  `83004A28553BCF2F932BF03564FBAB407B8E1F59CD265F8DC99CC53D028E459C`.
  The payload it wraps: 896 files (232 developer files pruned); zip 42,998,781 bytes, sha256
  `917a48b2556633f5a23662e365a43efd75662c38896e498f573706baec5beb9a`; CycloneDX SBOM, sha256
  `eb51942bd71e95d92aaae290e19fa3293cc5b373ee2cb129dd768cf0485c9bac`. dist exe: 15.3 MB, sha256
  `b2eb32d8f6fb15064fa6cd92f071332024a701e573c63d17295c01abcc31b8e2`.
- **Frozen smoke** (dist exe, port 8098, scratch APPDATA): **18/18** — healthz + BTCUSDT candles, unknown-symbol `[]` on footprint/tape, hostile-Host 403, `/api/control/sources` (7 venues), radar endpoint + education corpus present, **asset parity 78 shell refs + 11 help PNGs + corpus/search/pane byte-identical to the tree**, help payload `frozen=true`, WS 101/403, 0 client errors.
- **Silent install** (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<scratch>`): exit 0; **898 files** (the 896-file payload + `unins000.exe`/`.dat`), installed exe sha256 equal to the dist exe's; Start Menu entry created; desktop icon correctly skipped (task unchecked); ARP entry under
  `HKCU\...\Uninstall\{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1`.
- **Installed app**: headless on 8097 → `/healthz` 200, `/api/candles/BTCUSDT` 200 (173 KB), `/api/footprint/UNKNOWNXYZ` → `[]`, `/desktop` 200.
- **Silent uninstall**: exit 0; install dir, ARP entry and Start Menu entry all gone;
  `%APPDATA%\OrderFlowAnalysisPro` untouched; the dev desktop shortcut was backed up before the journey and left exactly as found.


## Verified journey (Inno pipeline, the §127 rebuild) - measured 2026-09-19

- **Build**: the §119–§127 tree (HEAD `797eea0`, worktree dirty; `dist/BUILD_INFO.json` records commit + state, built 2026-09-19T17:06:16+0930). Setup `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, **37,661,860 bytes** (35.92 MB), sha256
  `0D0BF7C57329ADC02B642CF07B187A398CC8666AA4481CA0662E563981D692E2`; the WebView2 bootstrapper embedded in it is 1.76 MB, sha256
  `83004A28553BCF2F932BF03564FBAB407B8E1F59CD265F8DC99CC53D028E459C` (unchanged).
  The payload it wraps: 896 files (232 developer files pruned); zip 43,001,835 bytes, sha256
  `113be091cd0befb22e187b21b292337e399fa2a80ee6ad45ce060a80d06b4f2f`; CycloneDX SBOM, sha256
  `8e2fa4b02096d45c00511b7e436eec078a16396a14843bfc4ce6e1ab890f3130`. dist exe: 15.3 MB, sha256
  `8ae3b25018dfd89643b23a3b289de28fb18fbd7e45e8e21871ef1e4c26c8896e`.
- **Frozen smoke** (dist exe, port 8098, scratch APPDATA): **18/18** — healthz + BTCUSDT candles, unknown-symbol `[]`, hostile-Host 403, `/api/control/sources` (7 venues), radar endpoint + education corpus present, **asset parity 78 shell refs + 11 help PNGs + corpus/search/pane byte-identical to the tree**, help payload `frozen=true`, WS 101/403, 0 client errors.
- **Silent install** (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<scratch>`): exit 0; **898 files** (the 896-file payload + `unins000.exe`/`.dat`), installed exe sha256 equal to the dist exe's; Start Menu entry created; desktop icon correctly skipped (task unchecked); ARP entry under
  `HKCU\...\Uninstall\{C2042089-3E19-410D-ABA6-C32BC9C13D80}_is1`.
- **Installed app**: headless on 8097 → `/healthz` 200, `/api/candles/BTCUSDT` 200 (173 KB), `/api/footprint/UNKNOWNXYZ` → `[]`, `/desktop` 200.
- **Silent uninstall**: exit 0; install dir, ARP entry and Start Menu entry all gone;
  `%APPDATA%\OrderFlowAnalysisPro` untouched; the dev desktop shortcut was backed up before the journey and left exactly as found.

## Verified journey (Inno pipeline, the §129b rebuild) - measured 2026-09-19

- **Build**: the §119–§129b tree (HEAD `797eea0`, worktree dirty; `dist/BUILD_INFO.json` records commit + state, built 2026-09-19T20:20:02+0930). Setup `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, **37,693,744 bytes** (35.95 MB), sha256
  `E39E3ADC03E5CEB8AAC54B6368D7CD8B142EE4BA813B518479225360D785B961`; the WebView2 bootstrapper embedded in it is 1.76 MB, sha256
  `83004A28553BCF2F932BF03564FBAB407B8E1F59CD265F8DC99CC53D028E459C` (unchanged).
  The payload it wraps: 896 files (232 developer files pruned); zip 43,032,010 bytes, sha256
  `b51b1c9fb2e8c2aaefc5975573616dd8a0bc7e877a10682eb1e8d3f8a76c75d8`; CycloneDX SBOM, sha256
  `cc88e4ccaafa3d1c52e3e5807a281e0f02fa1cc57cf55bc04b363ed9f6245edf`. dist exe: 15.3 MB, sha256
  `1863553f91eb4bc4cec3d65d7ab0e820f5c0cb42ab53d34753ba2b8a921bd7fb`.
- **Frozen smoke** (dist exe, port 8098, scratch APPDATA): **18/18** — healthz + BTCUSDT candles, unknown-symbol `[]`, hostile-Host 403, `/api/control/sources` (7 venues), radar endpoint + education corpus present, **asset parity 78 shell refs + 11 help PNGs + corpus/search/pane byte-identical to the tree**, help payload `frozen=true`, WS 101/403, 0 client errors.
- **Frozen features** (same exe, port 8097): **20/20** — payload parity for `menubar.js` / `windows-ui.js` / `windowing.js` / `help-data.js`; the §129 versions row + auto-cull switch and the §129b scroll guard present in the payload AND in the file the page actually requests; `/api/control/layouts` answers `keep=5 max=10 autocull=True` and the switch writes through it (`{autocull:false}` → response `autocull: False`, store False — the stale-answer defect THIS probe found is fixed and pinned); `/api/control/windows` answers the §128 `stranded` + `open_geometry`; served `help-data.js` carries the ring explanation; 0 client errors; port released.
- **Frozen UI over CDP** (the artifact's own WebView2, app 8104 / CDP 9224): the owner's gesture re-run against the frozen build — the View menu stayed open through a real wheel (`scrollTop 260`) and the below-the-fold **Rail** row clicked → rail toggled; the Layout menu stayed open through a wheel, the row read `✓Auto-cull old versions`, clicking it flipped the route's flag (True→False, then restored).
- **Silent install / uninstall** (`scripts/verify_installer.ps1`): **11/11 PASS** — install exit 0, 898 files, ARP entry + Start Menu entry created, the installed app booted headless (`/healthz` 200, `/desktop` 200, `/docs` 404), port released, uninstall exit 0, install dir + ARP + Start Menu gone, `%APPDATA%\OrderFlowAnalysisPro` untouched, the dev desktop shortcut left as found.

## Verified journey (Inno pipeline, the §135 fix pass) - measured 2026-09-19

- **Build**: the §119–§134 tree + the §135 fix pass (HEAD `797eea0`, worktree dirty; `dist/BUILD_INFO.json` records commit + state, built 2026-09-19T22:42:07+0930). Setup `ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe`, **37,699,102 bytes** (35.95 MB), sha256
  `D921D58EF76394879377D978C6A2DA6F4B39AE00A259EEEED05F5B693B3C0A9F`; the WebView2 bootstrapper embedded in it is 1.76 MB, sha256
  `83004A28553BCF2F932BF03564FBAB407B8E1F59CD265F8DC99CC53D028E459C` (unchanged).
  The payload it wraps: 899 files (233 developer files pruned); zip 43,040,670 bytes, sha256
  `6a1926a7411818387d5f60bc0aa4dbdb406507988288102bcaec19b27d2c4907`; CycloneDX SBOM, sha256
  `26dad36f93ee74ac56b8da8e46760c70dfbff5f9fd4b9f113a7904896f377bba`. dist exe: 15.3 MB, sha256
  `bb503bcd9d9421710699ab39833afe651e1f254a0018933e2b481ae9dc88d15d`.
- **Frozen smoke** (dist exe, port 8098, scratch APPDATA): **18/18** — healthz + BTCUSDT candles, unknown-symbol `[]`, hostile-Host 403, `/api/control/sources` (7 venues), radar endpoint + education corpus present, **asset parity 79 shell refs + 11 help PNGs + corpus/search/pane byte-identical to the tree**, help payload `frozen=true`, WS 101/403, 0 client errors.
- **Frozen features** (same exe, port 8097): **20/20** — payload parity for `menubar.js` / `windows-ui.js` / `windowing.js` / `help-data.js`; the §129 versions row + auto-cull switch and the §129b scroll guard present in the payload AND in the file the page actually requests; `/api/control/layouts` answers `keep=5 max=10` and the switch writes through it; `/api/control/windows` answers the §128 `stranded` + `open_geometry`; 0 client errors; port released.
- **Frozen payload markers** (this pass's own additions, served from the artifact): `/desktop/index.html` carries the instrument selector's tooltip, `/desktop/ui.js` carries `CHART_RETRY_MAX` + `refreshLiveChip(payload)`, `/desktop/help-data.js` carries the pick-starts-engine sentence.
- **Frozen guard probe** (the release audit's battery, re-run on this artifact): **23/23** — docs 404 ×3, served==packaged for 8 shell files, CSP meta, hostile Host / cross-origin / cross-site 403, loopback 200, WS 101/403, export-traversal name stays inside `exports\`, `app.frozen=true`.
- **Silent install / uninstall** (`scripts/verify_installer.ps1`): **11/11 PASS** — install exit 0, 899 files, ARP entry + Start Menu entry created, the installed app booted headless (`/healthz` 200, `/desktop` 200, `/docs` 404), port released, uninstall exit 0, install dir + ARP + Start Menu gone, `%APPDATA%\OrderFlowAnalysisPro` untouched, the dev desktop shortcut left as found.
