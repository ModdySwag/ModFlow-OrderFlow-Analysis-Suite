# SignPath Foundation — application pack

For **ModFlow OrderFlow Analysis Suite**. Prepared 2026-09-21 (ACST). Everything in section A was
re-verified against the live repository and the public GitHub copy today — nothing here is remembered
or assumed.

## A. What is already true (readiness evidence)

- **Project**: ModFlow OrderFlow Analysis Suite — a frozen Windows desktop application (Python +
  WebView2 UI) shipped with an Inno Setup installer that embeds the WebView2 bootstrapper.
- **Source repository**: https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite — **public**,
  licence **MIT**, default branch `master`. The public copy is the reviewed source, and local and
  public were brought back in step on 2026-09-21 (`50f871a`, then the policy commit).
- **CI**: GitHub Actions workflow `CI` (`.github/workflows/ci.yml`) with three jobs — `test`
  (pytest on Windows, Python 3.11 + 3.12), `build` (freezes the exe, builds the installer, uploads
  `dist-sign`: the app exe + the Setup, one artifact), `sign` (SignPath). Both runs on the public
  repository on 2026-09-21 are green: `35571830367` (`50f871a`) and `35572466682` (`85130d7`).
- **Artifact configuration**: committed and public at
  `.signpath/artifact-configurations/default.xml`. It signs the app exe and the Setup in one signing
  request, and (added 2026-09-21) enforces the Foundation's metadata conditions: the `version`
  parameter is required and fills `product-version`/`file-version`, with `product-name` and
  `company-name` restricted on both files.
- **The sign job is already wired** and stays skipped until the repository carries the SignPath
  values. It uses:
  - project slug `ModFlow-OrderFlow-Analysis-Suite`
  - signing policy slug `release-signing`
  - artifact configuration slug `default`
  - api token from secret `SIGNPATH_API_TOKEN`; organization id from variable
    `SIGNPATH_ORGANIZATION_ID`
  and then requires every downloaded signed file to read `Valid` from `Get-AuthenticodeSignature`.
- **Action inputs checked this pass**: every input our job passes matches the schema of
  `signpath/github-action-submit-signing-request` v3 (`api-token`, `organization-id`,
  `project-slug`, `signing-policy-slug`, `artifact-configuration-slug`, `github-artifact-id`,
  `wait-for-completion`, `output-artifact-directory`).
- **Distribution**: releases are published from the CI-built artifacts
  (github.com/ModdySwag/ModFlow-beta-builds, tag `v0.1.0-beta`).
- **Why signing is needed**: on a fresh machine the installer shows "Unknown publisher" and trips
  SmartScreen — the beta is live and this is the first thing a tester meets. There is **no commercial
  offering**: no paid edition, no paid support, no dual licence. It is built and maintained by one
  individual (Adelaide, Australia).

## B. The application answers (paste-ready)

The form's wording varies; these answers cover what it asks for.

- **Project name**: ModFlow OrderFlow Analysis Suite
- **Project / repository URL**: https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite
- **Licence**: MIT
- **Project description**: ModFlow OrderFlow Analysis Suite is a free, open-source Windows desktop
  application for order-flow trading analysis — footprint charts, depth-of-market, volume profile,
  trade replay and paper trading, with all processing local to the machine. It is written in Python
  with a WebView2 interface and shipped as a frozen build plus an Inno Setup installer that embeds
  the WebView2 bootstrapper. It is distributed freely to testers and other traders through GitHub
  releases.
- **Build system**: GitHub Actions (`windows-latest`). The frozen executable and the installer are
  built on the runner from the tagged source; the workflow already contains the SignPath signing job
  (currently skipped for lack of the organization id and API token) so no workflow changes are needed
  once the project is onboarded.
- **Download page**: https://github.com/ModdySwag/ModFlow-beta-builds/releases
- **Contact**: admin@moddys.net
- **GitHub account**: ModdySwag
- **Commercial offering / backing**: none — no paid edition, no paid support, no sponsor influence.
  Single maintainer.
- **Why a Foundation certificate**: the installer and the app exe are unsigned today, so Windows shows
  an unknown publisher and SmartScreen warnings; a Foundation signature gives users a verifiable link
  between the public repository and the binary they run.
- **Anything else they should know**: the artifacts to be signed are one signing request containing
  the application executable and the installer (the committed artifact configuration describes both).
  Timestamps: default (signing request is timestamped).

## C. After approval — the setup, and the parts I run

1. SignPath onboards the organization; you get access at https://app.signpath.io/.
2. In the organization, these must exist with exactly these slugs (the CI job depends on them):
   - project `ModFlow-OrderFlow-Analysis-Suite` (repository URL set to the GitHub repo)
   - signing policy `release-signing` (purpose: release)
   - artifact configuration `default` — paste the repository's committed XML (the repo copy is the
     reviewable version)
   - a CI user with submit permission on the policy, and an **API token** created for it
   If SignPath creates these during onboarding, only the API token step remains.
3. Two values go into the repository — both set from this machine with `gh` (I can run them, the
   token never has to appear in any chat):
   - `gh variable set SIGNPATH_ORGANIZATION_ID --body "<org id>" -R ModdySwag/ModFlow-OrderFlow-Analysis-Suite`
   - `gh secret set SIGNPATH_API_TOKEN -R ModdySwag/ModFlow-OrderFlow-Analysis-Suite < <file>`
4. Effect: the `sign` job stops being skipped. It runs after `build` on the next `master` push, tag,
   or manual dispatch, submits one signing request for both binaries, downloads the signed artifact
   and fails the job unless every file verifies as `Valid`.
5. First signed release: re-take the hashes and the SBOM from the **signed** artifacts, then the
   release notes. (Signing changes the bytes — the order is recorded in `docs/RELEASE_CHECKLIST.md`
   §6, and `BUILD_INFO.json`'s recorded `exe_sha256` will then describe the pre-sign exe.)

## D. The Foundation's conditions, checked one by one

Source: <https://signpath.org/terms.html> (read 2026-09-21). Each condition, and where it stands:

| Condition | State |
| --- | --- |
| Free of charge for users; no commercial offering | Met — no paid edition, no paid support, no dual licence. |
| Open source under an OSI-approved licence | Met — MIT, public repository. |
| No proprietary components | Met — every component's source is in the repository, including the NinjaTrader bridge (C# sources and its build script are in-tree). |
| Released | Met — `v0.1.0-beta` published from CI-built artifacts. |
| Documented | Met — README plus `docs/`. |
| Provide uninstallation | Met — the installer registers a plain per-user uninstaller (Inno Setup, `installer/modflow.iss`). |
| Announce system changes | Met — per-user install, no service, no scheduled task; `docs/RELEASE_CHECKLIST.md` states it. |
| **Code signing policy on the home page / download page** | Met — the README gained a `## Code signing policy` section with the required attribution sentence, the team roles and the privacy sentence; the download page (`ModFlow-beta-builds` README) carries the same policy. |
| Team roles assigned (authors / reviewers / approvers) | Met — one maintainer holds every role; stated in the README policy section. |
| MFA on the SignPath and repository accounts | **Owner to confirm** — required of every team member; nothing in the repository can attest to it. |
| Metadata attributes set and enforced by file metadata restrictions | Met — `product-name`, `product-version`, `file-version`, `company-name` enforced in `.signpath/artifact-configurations/default.xml`; CI fills the required `version` parameter from `pyproject.toml`. |
| Same product version in each build | Met — one source (`pyproject.toml`) feeds the exe's version resource and the installer's `VersionInfo` directives. |

Two notes from this pass:

- **Inno Setup pads version-info strings** to fixed field widths (`"0.1.0"` followed by spaces —
  measured on a scratch build, 2026-09-21; the certified Setup of `0eedc0d` has the same padding and
  a blank `FileVersion`, which the new directives fix for the next build). The restriction values in
  the config are the unpadded ones; if the organization's metadata check is exact-match, the config's
  comment records the adjustment (drop the Setup's `product-version`, keep `product-name` +
  `company-name`).
- **What this changed in the repository**: the README policy section, explicit `VersionInfo`
  directives in `installer/modflow.iss`, the `default.xml` restrictions plus the required `version`
  parameter, and the sign job now reading the version from `pyproject.toml`. The frozen build and the
  certified artifacts of this release are untouched — the change lands in the next build, which is
  exactly the build that gets signed.

## E. Local signing stays available

`scripts/sign_release.ps1` signs with a certificate you own — either a thumbprint in the user or
machine store (`/sm` is detected automatically) or a `.pfx` with `OFAP_SIGN_PFX_PASSWORD`. A
self-signed certificate for private beta builds exists at `C:\Users\Moddy\keystores\modflow-selfsigned.cer`
(created 2026-09-21; see the §150 supplement in `docs/SESSION_HANDOFF.md`).
