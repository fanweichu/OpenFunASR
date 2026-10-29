# OpenFunASR

[简体中文](README.zh-CN.md) · English

Local, push-to-talk dictation for macOS. Hold **F5** or **F9**, speak, then release
to transcribe and paste into the active text field. OpenFunASR lives in the menu
bar and uses **Fun-ASR Nano GGUF Q5_K_M** for on-device speech recognition.

- Local inference after the initial dependency/model download; no cloud ASR key.
- Menu-bar controls, configurable hotkeys, clipboard copy and optional auto-paste.
- Silence filtering and Chinese number/punctuation cleanup.
- One recognition engine; whisper.cpp is used only for voice-activity detection.
- The current application interface is in Chinese.

## Platform support

| Platform | This desktop app |
| --- | --- |
| Apple Silicon Mac (arm64) | Target of the supplied build and install scripts |
| Intel Mac | No supplied runtime package or validated installation path |
| Linux / Windows | Not supported by this desktop app |

The bundle declares macOS 12.0 as its minimum version. This is a build setting,
not a guarantee that the current Homebrew/Python dependencies install on every
older macOS version. Use a macOS version supported by your Homebrew installation.

The [upstream FunASR runtime](https://github.com/modelscope/FunASR/tree/main/runtime/llama.cpp)
provides Linux, macOS and Windows command-line recognition. This app additionally
depends on Cocoa, AVFoundation, Carbon hotkeys and Quartz paste events. A Linux
desktop port would need replacements for those integrations.

## Install

Prerequisites: an Apple Silicon Mac, [Homebrew](https://brew.sh), Apple's Command
Line Tools (`xcode-select --install`), network access and several GB of free disk
space. Clone this repository and open a terminal in its directory.

First installation, after reviewing the local signing step:

```bash
./setup.sh --install --create-signing-identity
```

This installs missing Homebrew dependencies, prepares a Python virtual
environment, downloads about 1.03 GB of models plus the runtime, verifies asset
checksums, runs regression checks, builds and installs the app. The signing flag
explicitly permits creation of a persistent local code-signing identity in your
login Keychain and user-level code-signing trust. The identity contains no personal
name and is created locally; never upload its private key.

For later updates using the same signing identity:

```bash
./setup.sh --install
```

macOS will require user interaction for Microphone and Accessibility permission.
After granting permissions, restart OpenFunASR and test dictation in a disposable
text field. **Installation is not fully unattended.** The local certificate does
not provide Apple Developer ID signing or notarization.

For AI assistants, use [AI_INSTALL.md](docs/AI_INSTALL.md). Preparation without
installing or creating a signing identity is also available:

```bash
./setup.sh
```

## Use

1. Open `/Applications/OpenFunASR.app` and finish the permission setup.
2. Place the cursor in a text field, hold F5 or F9, speak, then release.
3. Use the menu-bar settings to change hotkeys or turn auto-paste off.

If your keyboard maps F-keys to hardware controls, you may need Fn/Globe or an
adjustment in macOS keyboard settings. Results are copied to the clipboard even
when auto-paste is disabled.

## Build and test

After `./setup.sh`, stable builds use the existing local signing identity:

```bash
./build_local_app.sh  # dist-local/OpenFunASR.app + dist-local/runtime
./build_full_app.sh   # dist-full/OpenFunASR.app, including runtime and models
.venv/bin/python test_openfunasr.py
```

A disposable development bundle can be built without creating a certificate:

```bash
OPENFUNASR_SIGN_IDENTITY=- OPENFUNASR_ALLOW_ADHOC=1 ./build_local_app.sh
```

Keep that bundle in the build directory. The production installer refuses ad-hoc
signing. A self-contained bundle includes third-party assets; review their
licenses before distributing a binary release.

To test real recognition, supply your own 16 kHz mono PCM WAV outside the repo:

```bash
export OPENFUNASR_CONFIG_DIR="$PWD/.cache/test-config"
export OPENFUNASR_LOCAL_RUNTIME_ROOT="$PWD/dist-local/runtime"
export OPENFUNASR_TEST_AUDIO="$HOME/speech-test.wav"
.venv/bin/python test_funasr_integration.py
```

This checks nonempty speech output and silence rejection. It does not test the
microphone, recognition accuracy, menu bar, global hotkeys or actual paste.

Version 2.0.3 fixes decimal percentages and nested Chinese number units, preserves
approximate quantities and ambiguous shorthand, and avoids rewriting sentence
boundaries based only on VAD segment count. Bracketed content and English short
answers are preserved. See the [fix record](docs/OUTPUT_QUALITY_FIXES.zh-CN.md)
and [audio quality test plan](docs/OUTPUT_QUALITY_TEST_PLAN.zh-CN.md) (in Chinese).
To replay the 24 synthetic text cases without recording audio or running ASR:

```bash
.venv/bin/python scripts/probe_output_quality.py --output benchmark-results/quality-run
```

The report separates text-processing failures from formatting differences and
ambiguous speech. These targeted cases do not measure recognition accuracy.

## Privacy, updates and publishing

Settings, diagnostic logs and the installed runtime are stored in
`~/Library/Application Support/OpenFunASR/`. Audio is temporarily written to
`/tmp` and normally deleted after processing; failures or interrupted execution
can leave a temporary recording. The most recent result stays in app memory and
on the system clipboard. Diagnostic logs can contain local paths, foreground-app
details and engine error output. Review and redact logs before sharing them.

This repository excludes model weights, executables, recordings, logs, build
outputs, personal settings, certificates and private keys. Run the privacy check
before publishing:

```bash
python3 scripts/check_privacy.py
```

Read [the signing and permission guide](PERMISSION_SOP.md) before changing an
existing installation, and [the publishing guide](docs/PUBLISH.md) before pushing
to GitHub. Downloaded dependencies are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

The application source and project documentation are available under the
[MIT License](LICENSE). Third-party runtimes, libraries and model weights retain
their own licenses; they are not relicensed by this repository.
