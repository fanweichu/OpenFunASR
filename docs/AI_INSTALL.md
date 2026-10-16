# AI installation guide / AI 安装说明

## 用户可以直接发送的指令

> 请安装这个仓库中的 OpenFunASR。先读取 `docs/AI_INSTALL.md`，确认当前系统和已有安装，
> 再按文档执行。首次创建本地签名证书前，说明钥匙串变更并取得授权；如果我已经明确批准
> 对应操作，不要重复询问。保留已有签名身份、设置和隐私权限。最后区分安装完成、
> 等待系统授权，以及真实语音输入验收的状态。

## Scope and prerequisites / 范围与前置条件

- This installer targets **Apple Silicon macOS**, not Intel, Linux or Windows.
  Stop clearly on an unsupported platform. Do not silently substitute an upstream CLI.
- Homebrew and Apple Command Line Tools must already be available. If absent,
  explain the missing prerequisite; use the official Homebrew instructions or
  `xcode-select --install` with user involvement. Do not pipe an unreviewed script into a shell.
- Python 3.10–3.12 is supported by this source snapshot. `audioop` is unavailable
  in Python 3.13+. Setup uses an existing compatible Python or installs Homebrew
  `python@3.12`. It also installs missing `whisper-cpp` and `openssl@3` formulae.
- Expect about 1.03 GB of model downloads, plus runtime/dependencies, and several
  GB of disk use during packaging. GitHub and Hugging Face must be reachable.
- macOS permission dialogs and Keychain prompts require user interaction.
  Do not claim that these can be silently bypassed.

## 1. Inspect / 检查

Run in the cloned repository:

```bash
uname -s
uname -m
xcode-select -p
brew --version
./setup.sh --help
```

Check whether `/Applications/OpenFunASR.app` exists. If it does, read its Bundle ID
and signature before changing it:

```bash
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' /Applications/OpenFunASR.app/Contents/Info.plist
codesign --verify --deep --strict /Applications/OpenFunASR.app
codesign -d --requirements - /Applications/OpenFunASR.app
```

Inspect the local signing identities with `security find-identity -v -p codesigning`.
Do not paste complete identity listings, usernames or local absolute paths into
public issues. Never export private keys as part of installation.

## 2. Install / 安装

For a first installation without an existing stable local identity, explain:
creating the identity generates a private key, imports it into the login Keychain,
and adds user-level trust restricted to code signing. The certificate subject is
generic. The identity must be retained for future updates. Obtain authorization
for that Keychain change unless the user has already explicitly approved it.

After approval:

```bash
./setup.sh --install --create-signing-identity
```

If the identity already exists, or for an ordinary update:

```bash
./setup.sh --install
```

The first command reuses an existing identity instead of regenerating it. Neither
command automatically changes a mismatched signing identity on an installed app.
The production installer rejects ad-hoc signing and stops before replacement if
Bundle IDs or designated requirements conflict.

For an intentional migration from a different identity, explain why authorization
will change and obtain approval first. Then use this one-time override:

```bash
OPENFUNASR_SIGNING_MIGRATION=1 ./setup.sh --install
```

Do not enable this override merely to get past an unexplained error. Do not run
`tccutil reset` or remove privacy database entries. Follow [PERMISSION_SOP.md](../PERMISSION_SOP.md).

To prepare dependencies and verified downloads without installing or changing Keychain:

```bash
./setup.sh
```

`runtime-manifest.json` pins the FunASR release, model revisions and SHA-256 values.
Never disable checksum verification to work around a failed download. Rerunning
setup reuses verified files. Use `OPENFUNASR_PYTHON` for a compatible Python path
or `OPENFUNASR_SPEECH_RUNTIME` for an explicitly selected whisper.cpp libexec directory.

## 3. Permissions and acceptance / 授权与验收

Ask the user to grant Microphone and Accessibility to OpenFunASR in macOS System
Settings, then restart it. These permissions enable recording and automatic paste.
Do not grant permissions to unrelated applications as a workaround.

Verify all of the following before reporting full usability:

1. `/Applications/OpenFunASR.app` exists and its signature verifies.
2. The menu-bar icon and menu are actually visible.
3. A **new** startup log from the installed app reports:
   `startup permissions accessibility=已授权 microphone=已授权(3)`.
4. Hold F5/F9, say a short test sentence, release, and confirm the expected text
   appears in a disposable input field. Check the hotkey, microphone, recognition
   and real paste as one flow.

Logs are at `~/Library/Application Support/OpenFunASR/app.log`. A terminal
`--self-check` does not prove the installed app's permissions. Do not inspect
unrelated transcript history or copy diagnostics publicly.

Optional resident-app paste test: focus a disposable input field, ensure the user
agrees to replacing the clipboard with `OPENFUNASR_PASTE_OK`, then trigger:

```bash
touch "$HOME/Library/Application Support/OpenFunASR/.paste-self-test"
```

The marker must actually appear in that field. A log saying an event was posted
is insufficient. Do not trigger this while the user is editing a real document.

## 4. Report / 交付状态

Report what ran, what passed, and any remaining manual action. If permission or
UI checks cannot be completed, state “installed; awaiting permissions/live test”
instead of claiming a complete installation. Do not rebuild or overwrite the app
again after its final permission and paste verification.
