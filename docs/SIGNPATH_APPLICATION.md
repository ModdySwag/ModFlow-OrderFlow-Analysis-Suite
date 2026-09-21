# SignPath Foundation — application pack

For **ModFlow OrderFlow Analysis Suite**. Prepared 2026-09-21 (ACST). Everything in section A was
re-verified against the live repository and the public GitHub copy today — nothing here is remembered
or assumed.

## A. What is already true (readiness evidence)

- **Project**: ModFlow OrderFlow Analysis Suite — a frozen Windows desktop application (Python +
  WebView2 UI) shipped with an Inno Setup installer that embeds the WebView2 bootstrapper.
- **Source repository**: https://github.com/ModdySwag/ModFlow-OrderFlow-Analysis-Suite — **public**,
  licence **MIT**, default branch `master`. (Local `master` is one commit ahead of the public copy;
  the public copy is what SignPath reviews.)
- **CI**: GitHub Actions workflow `CI` (`.github/workflows/ci.yml`) with three jobs — `test`
  (pytest on Windows, Python 3.11 + 3.12), `build` (freezes the exe, builds the installer, uploads
  `dist-sign`: the app exe + the Setup, one artifact), `sign` (SignPath). The last runs on the public
  repository are green (2026-09-19).
- **Artifact configuration**: committed and public at
  `.signpath/artifact-configurations/default.xml` (public blob sha `53824a40122b…`). It signs the app
  exe and the Setup in one signing request.
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

## D. Local signing stays available

`scripts/sign_release.ps1` signs with a certificate you own — either a thumbprint in the user or
machine store (`/sm` is detected automatically) or a `.pfx` with `OFAP_SIGN_PFX_PASSWORD`. A
self-signed certificate for private beta builds exists at `C:\Users\Moddy\keystores\modflow-selfsigned.cer`
(created 2026-09-21; see the §150 supplement in `docs/SESSION_HANDOFF.md`).
