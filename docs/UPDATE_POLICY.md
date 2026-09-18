# Update policy — what the updater promises

*ModFlow OrderFlow Analysis Suite · the rule, written down so it stays true.*

The updater exists so a better build can reach you. It is not a delivery mechanism for anyone
else's schedule, and it is never a reason for the app to stand still.

## The promise

1. **Nothing blocks.** The check runs on load and on a timer, in the background. A found update
   waits until you are not typing before it says so. The app is fully usable the whole time.
2. **Nothing restarts itself.** There is no auto-restart and no forced window. When you choose to
   update, *you* run the installer.
3. **Nothing is forced.** A found update is a notice. The default is “tell me — download when I
   ask”; fetching the installer automatically is opt-in, per machine.
4. **What changed is part of the update.** The release's own notes are shown beside the notice
   (“What's in X”), and release notes carry a short list of user-visible interface changes — so a
   moved button is documented, not discovered.
5. **Downloads are verified** against the release's own SHA-256 when GitHub publishes one; a
   mismatch is reported and the file is not offered.
6. **Failures are quiet and retried.** Offline, rate-limited, a broken channel: the check logs it,
   retries later, and never nags. No error is ever a modal.
7. **No account, no telemetry.** The check reads a public release channel. It sends nothing about
   you, your machine or your data anywhere.

## Why this is written down

The paid field's cautionary tale is a force-update window that stranded licensed installs — an
update path that turned a working app into a stopped one. The rule above is the opposite of that
design, and it is written down so that no future change quietly softens it: every clause here has
a test or a setting behind it, and the release-note habit is how a one-developer app avoids “where
did the button go?”

The same promises exist in-app: **Help ▸ Updates never block** (`work.updates`), linked from the
update card itself.

