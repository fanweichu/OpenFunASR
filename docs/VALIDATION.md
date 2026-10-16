# Source-publication validation

Checked on 2026-10-16, on an Apple Silicon Mac running macOS 15.7.3.

Passed:

- Installed `requirements.txt` into a fresh Python 3.12.13 virtual environment.
- Checked shell/Python syntax, plist/JSON parsing, local documentation links and
  the linked third-party license pages. The PyObjC license link was corrected.
- Downloaded and SHA-256 verified the pinned public FunASR runtime archive.
- Verified all four model hashes against the pinned Hugging Face metadata;
  existing matching model files were reused locally instead of downloaded again.
- Built an isolated, ad-hoc local development bundle and verified its signature.
- Started the packaged executable with `--self-check`; both native tools and all
  four models resolved. No recording or paste was triggered by that check.
- Passed command construction, Chinese post-processing and silence-gate
  regression checks.
- Passed real whisper.cpp VAD plus Fun-ASR inference using an existing local
  speech fixture, producing 30 characters; generated silence produced no text.
  The fixture and its transcript are not included in the repository.
- Confirmed that production installation rejects ad-hoc signing before changing
  an app, and setup rejects Linux before dependency or system changes.
- Confirmed that the privacy scanner rejects a private path present only in the
  Git staging area, even after the working copy has been cleaned.
- Scanned the publication files and staging area for configured sensitive-data
  patterns, local account names, absolute user paths, email addresses and tokens.

The inference test could not create a Metal command queue inside the restricted
test sandbox. The same test passed with normal host GPU access. It was not
substituted with a different engine or a CPU-only test.

Limits:

- The installed application, its runtime/settings and the login Keychain were
  not replaced or modified. Production installation, certificate creation,
  existing-permission continuity and rollback were not exercised end to end.
- No live microphone, global hotkey, menu-bar UI or real text-field paste test
  was performed for the publication copy.
- The self-contained `full` build, a new machine, Intel Mac, Linux desktop and
  every declared macOS version were not tested.
- Speech integration checks nonempty output, not measured recognition accuracy.
- Privacy scanning is evidence for the configured checks, not proof that every
  possible sensitive value has been detected. Review the staged source and Git
  identity before uploading.
- GitHub Actions and a clean-machine one-command installation are unverified
  until they are actually run. No notarized binary release is provided.
