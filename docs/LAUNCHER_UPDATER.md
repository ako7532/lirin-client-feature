# Private launcher updates

The launcher checks `ako7532/lirin-client-feature` using each person's own GitHub
authorization. No private key, client secret, personal token or shared credential
is distributed. The repository and assets remain private. Initial deployment
requires one manual download. GitHub configuration and publication require the
owner's separate action; local implementation does not perform them.

## Owner setup (external work still pending)

1. GitHub **Settings > Developer settings > GitHub Apps > New GitHub App**.
   Use a descriptive unique name and `https://github.com/ako7532` as homepage. Disable
   webhooks (there is no server). Enable **Device flow**. Do not enable a setup
   redirect or request a callback-based login. Leave callback URL empty; device
   flow ignores that field.
2. Grant only repository **Contents: Read-only** (Metadata read is implicit).
   No organization/account write permissions are required. Select **Any account**
   for installation availability so the app is shareable with the collaborator;
   a public app registration still accesses only selected private repositories.
   The repository owner installs the app on **only this repository**. The
   collaborator authorizes the app but does not install it on the owner's account.
3. Leave expiring user tokens enabled initially. The launcher respects `expires_in`
   and requires **Connect GitHub** again on expiration/revocation. It does not
   store/use refresh tokens or ship the client secret required by the refresh
   flow. Do not promise permanent login. The owner can explicitly opt out of
   user-token expiration in the app's optional features if desired, trading fewer
   logins for longer-lived credentials; revocation and Disconnect still work.
4. Copy the **Client ID**, not App ID or secret, into repository Actions variable
   `UPDATER_GITHUB_CLIENT_ID`. This is public configuration embedded in
   `updater.json` by the packager. Missing configuration fails the release gate.
5. After reviewing/merging the implementation and explicitly authorizing a test
   release, publish a packaged build. Both users must independently connect and
   verify release metadata **and the private ZIP download** on their PCs.
   Mock tests are not evidence of account access or GitHub App configuration.

Official references checked during implementation:

- [GitHub App user access tokens and device flow](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [Registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [Release assets API](https://docs.github.com/en/rest/releases/assets)

## First installation and Windows identity

The deployment remains **framework-dependent**: install the .NET 8 Desktop
Runtime **x64**. The helper also uses WinForms for failure reporting. Python and
the injection prerequisites are unchanged. In particular the current runner
and RepositoryPaths still use the original author's absolute Python 3.11 path;
that existing limitation must be resolved separately for a different Windows
profile before injection can work there. Updater tests do not invoke injection.

Extract the complete package into a dedicated folder, for example
`C:\Program Files\LirinFeature`. Use an elevated Explorer/PowerShell copy and
make **Administrators** the owner of the package directory and files. Keep
standard inherited Program Files permissions: ordinary users may read/execute,
but must not write/delete/change permissions. Existing custom parent ACLs can
cause a safe refusal. Never install into the Program Files root itself.

The launcher refuses automatic replacement in a Git checkout, without a valid
distribution marker/build identity, outside Program Files, through reparse
points, or with nonadministrative write access. Portable/old/source builds can
check releases but need manual migration. Existing settings, logs and `.runtime`
can be copied into the new installation; they are never package-managed.

Run the launcher as usual with its existing administrator requirement. Select
**Updates > Connect GitHub**, enter the displayed code in the opened GitHub page,
and authorize your own account. Subsequent launches check asynchronously. Use
**Check for updates** for a manual check; checks are throttled to one per minute
and for one hour after a rate-limit error. Offline/auth failures leave injection
available. A failed check is never presented as up-to-date. An available update
shows installed/available identities, release notes, **Update now** and **Later**.

Credentials live in Windows Credential Manager under
`LirinFeatureLauncher/GitHub/ako7532/lirin-client-feature/v1`. They belong to the
Windows identity running the elevated launcher. Elevating with a different
administrator account uses that account's store, not the desktop user's store.
There is no roaming promise. **Disconnect GitHub** deletes the local credential;
revoke the app in GitHub Settings to invalidate authorization remotely as well.

## Release identity and trust

`build.json` is the installed build identity; `package.json` lists every managed
file and its size/hash. The external `update-manifest.json` repeats that identity
and list and adds ZIP size/SHA-256. A release must have both uploaded assets,
supported schema/package format 1, stable channel, and a tag matching
`stable-<sequence>-<40-character-commit>`; drafts and prereleases are excluded.
Checks examine up to 1,000 releases and fail explicitly rather than claim a
complete result beyond that bound.

Sequence = existing Release workflow run number * 1000 + run attempt. Attempts
must be below 1000. A rerun of an older run cannot outrank a newer run. Keep this
workflow's run-number lineage; if recreating it, reserve a larger sequence range
before publishing. Neither commit lexicographic order nor timestamps determine
upgrades. The workflow serializes publication, creates a draft with both assets,
then publishes it; clients choose the highest valid sequence above the installed
one regardless of GitHub's latest-release pointer. No downgrades are installed.

Assets use authenticated fixed GitHub API URLs. Redirects only permit HTTPS on
the API and explicitly allowed GitHub release-storage hosts; **no redirect gets
Authorization**. ZIPs are limited to 256 MiB, extracted data to 512 MiB, and a
fixed flat allowlist rejects traversal, aliases, links, duplicates and unexpected
files. All required runtime files ship together. The checksum detects corruption
and mismatched assets; it is **not an independent signature** against compromise
of the repository/account that controls both ZIP and manifest.

## Installation and recovery

Close every Lirin process before updating. The helper rechecks this after waiting
for the launcher to exit, and never terminates or injects a game. Loaded feature
code cannot be refreshed by overwriting disk files. The runner stages scripts
and DLLs into `.runtime`, and the feature reads model/config/snapshot files at
runtime, so installation conservatively requires all Lirin processes closed.

A file lock serializes injection/update operations across launcher instances.
Download/validation can be cancelled; replacement begins only after validation.
The full archive and helper are staged in an administrator-only `.update-<id>`
directory under the installation. The helper receives paths/process identity
only, revalidates the archive, freshly extracts it, backs up every changed/removed
managed file, flushes an atomic recovery journal, then replaces the package.
Unmanaged files are preserved; collisions with new managed names fail closed.

The new launcher confirms startup using a random per-restart acknowledgement in
the protected staging directory after validating its installed files. The helper
waits 30 seconds; failures cause rollback. Files are not atomically replaced as
a group. `.update-journal.json` and complete backups remain after success or
rollback for inspection; automatic cleanup is intentionally omitted.

On an interrupted install, the launcher blocks injection and starts the retained
helper to roll back before normal startup. If interruption damaged the executable
or a runtime dependency so it cannot start at all, use the original retained
helper in an **administrator PowerShell**, after closing all feature launchers
and Lirin processes:

```powershell
# Substitute the exact installation and .update-ID from .update-journal.json.
$installRoot = 'C:\Program Files\LirinFeature'
$updateStage = 'C:\Program Files\LirinFeature\.update-REPLACE_WITH_ACTUAL_ID'
Start-Process -FilePath "$updateStage\helper\LirinUpdater.Helper.exe" -WindowStyle Hidden -ArgumentList @('recover', ('"' + $installRoot + '"'), ('"' + $updateStage + '"'), '0', '0')
```

The journal's `Stage` is the `payload` directory inside that `.update-ID`; the
command uses its parent. If rollback encounters locks/denied permissions, keep
the journal and `payload\backup` intact, fix the reported lock/permissions, and
retry. As a final manual recovery, restore all original managed files from that
backup and remove only newly introduced managed files named in the journal.
Never mark a mixed package successful or delete recovery evidence prematurely.

## Local validation and live acceptance

```powershell
dotnet build .\LirinFeatureLauncher -c Release
dotnet build .\LirinUpdater.Helper -c Release
dotnet run --project .\LirinFeatureLauncher.Tests -c Release
dotnet run --project .\LirinUpdater.Tests -c Release
python .\test_client_feature_local.py
```

`scripts/package_release.py` takes `--root`, `--launcher`, `--helper`, a **new**
`--output` directory, `--sequence`, `--commit`, and public `--client-id`.
Validate the actual output with
`dotnet run --project .\LirinUpdater.Tests -c Release -- --validate-package <output>`.

Live acceptance still required before relying on unattended detection:

- Both accounts: authorize, inspect release metadata, download private asset;
  verify expiry/reconnect, Disconnect and revoked access.
- Packaged A -> B on each PC: correct identity, helper restart acknowledgement,
  preserved config/logs/runtime state; offline launch remains usable.
- Intended elevation identity and Credential Manager retrieval on each PC.
- Installer permission refusal, actual restart failure, process-exit timeout,
  power/process interruption and retry via the retained helper in a disposable
  installation. Local transaction tests simulate interruptions but do not prove
  physical power-loss durability or end-to-end helper/UI behavior.
