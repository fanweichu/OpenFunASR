# Working on OpenFunASR

- For installation requests, read `docs/AI_INSTALL.md` first. Inspection or code
  review does not authorize installation, Keychain changes or permission changes.
- The automated desktop installer targets Apple Silicon macOS. The upstream
  recognition engine's Linux support does not make this a Linux desktop app.
- Preserve Bundle ID, signing identity and designated requirement on updates.
  Do not overwrite a stable installation with an ad-hoc build or reset TCC.
- Keep model weights, native runtime files, personal settings, recordings, logs,
  certificates, private keys and generated build outputs out of Git.
- Use Python 3.10–3.12. Run `test_openfunasr.py` for regression checks and
  `scripts/check_privacy.py` before a commit or public upload.
- Do not claim microphone, hotkey or paste acceptance from a build or terminal
  self-check. Report any manual permission or live-UI checks still required.
- Keep English and Chinese READMEs consistent when changing installation or usage.
