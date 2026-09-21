# Binary provenance

Two prebuilt binaries are committed so a fresh checkout can use the optional NinjaTrader-8 and
Bookmap bridges without a JDK or a build step. They are **not** part of the Python package's
runtime path, and nothing in the app loads them automatically.

| File | SHA-256 | Built from | Rebuild |
|---|---|---|---|
| `orderflow_system/data/bookmap_addon/ofap-bridge.jar` | `c3f015b86ebd93ba2ebe9f119e542b470cacca9fbabf49d4aa114ecd03bb3aad` | `orderflow_system/data/bookmap_addon/src` (Gradle project beside it) | `cd orderflow_system/data/bookmap_addon && gradle jar` |
| `orderflow_system/data/ninjatrader_bridge/ModFlowBridge.dll` | `a2bdb248e9beae7607eabb3e51cf064cbcc6c2b76c79e3fba5660f3e69ff2c9f` | `orderflow_system/data/ninjatrader_bridge/src` (C#; compiled in the NT8 NinjaScript Editor — see that directory's README) | see `orderflow_system/data/ninjatrader_bridge/README.md` |

Verify a copy against these hashes before trusting it:

```bash
sha256sum orderflow_system/data/bookmap_addon/ofap-bridge.jar
sha256sum orderflow_system/data/ninjatrader_bridge/ModFlowBridge.dll
```

Notes from the v0.1b audit (2026-09-18):

- The hashes above are the committed bytes as audited. Regenerate this table whenever either file
  changes — a binary with no recorded provenance is a supply-chain gap (audit E-04).
- Re-verified 2026-09-21 (release pass): the table row for `ModFlowBridge.dll` now records the
  committed bytes (`a2bdb248…`). The bridge rebuild in `42ec6a2` (2026-09-19) replaced the DLL but
  left the previous hash in the row — a recorded hash that no longer matches its file is the same
  class of gap as a missing one. Both rows now match the files, the working tree and the payload
  the zip ships.
- The release binaries (installer and portable zip) are **unsigned** (audit F-11): Windows
  SmartScreen warns on first run until the owner signs them.
- `build/` holds PyInstaller intermediates (spec, TOC dumps, cross-reference HTML, warn log) and
  must never be attached to a release; the shipped payload is `dist/` only (audit E-12).
