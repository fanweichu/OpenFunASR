# OpenFunASR

简体中文 · [English](README.md)

一个在 macOS 菜单栏运行的本地语音输入工具。按住 **F5** 或 **F9** 说话，
松开后自动转写，并粘贴到当前光标位置。识别使用 **Fun-ASR Nano GGUF Q5_K_M**，
在本机完成推理。

- 首次下载依赖与模型后，本地识别无需云端 ASR 或 API Key。
- 菜单栏操作，可修改快捷键，可关闭自动粘贴，结果同时复制到剪贴板。
- 过滤静音，整理部分中文数字、停顿逗号和错误断句。
- 只使用一个转录引擎；whisper.cpp 在这里仅负责语音活动检测。
- 当前应用界面为中文。

## 支持哪些系统

| 系统 | 本项目桌面应用 |
| --- | --- |
| Apple Silicon Mac（arm64） | 提供构建与安装脚本 |
| Intel Mac | 暂无配套运行库包和已验证的安装流程 |
| Linux / Windows | 不支持本桌面应用 |

应用包声明最低 macOS 12.0，但这只是构建配置，不代表当前 Homebrew、Python 等依赖
能在所有旧系统安装。请使用你的 Homebrew 仍支持的 macOS 版本。

[上游 FunASR 运行库](https://github.com/modelscope/FunASR/tree/main/runtime/llama.cpp)
有 Linux、macOS、Windows 命令行版本。当前桌面程序还依赖 Cocoa 菜单栏、
AVFoundation 录音、Carbon 快捷键和 Quartz 粘贴事件；移植到 Linux 需要另做这些系统集成。

## 安装

前置条件：Apple Silicon Mac、[Homebrew](https://brew.sh)、Apple 命令行工具
（`xcode-select --install`）、网络连接和数 GB 可用磁盘空间。克隆本仓库，
在仓库目录打开终端。

首次安装，了解本地签名操作后运行：

```bash
./setup.sh --install --create-signing-identity
```

脚本会补齐 Homebrew 依赖、创建 Python 虚拟环境、下载约 1.03 GB 模型及运行库、
校验文件、运行回归检查，然后构建并安装应用。
`--create-signing-identity` 明确允许在登录钥匙串创建固定的本地代码签名身份，
并添加当前用户范围的代码签名信任。证书不含个人姓名，私钥在本机生成，不能上传。

之后更新，复用同一签名身份：

```bash
./setup.sh --install
```

首次麦克风和辅助功能授权仍需你在 macOS 中操作。授权后重启应用，在临时文本框
测试语音输入。**安装并非完全无人值守。** 本地自签证书也不等于 Apple Developer ID
签名或苹果公证。

让 AI 代装时，将 [AI_INSTALL.md](docs/AI_INSTALL.md) 交给它即可。
只准备依赖和模型、不安装应用、不创建签名身份：

```bash
./setup.sh
```

## 使用

1. 打开 `/Applications/OpenFunASR.app`，完成权限引导。
2. 将光标放进文本框，按住 F5 或 F9 说话，松开后等待转录。
3. 在菜单栏设置中调整快捷键或关闭自动粘贴。

如果 F 键默认控制音量等硬件功能，可能需要同时按 Fn／地球键，或调整 macOS 键盘设置。
关闭自动粘贴后，结果仍会进入剪贴板。

## 构建和测试

执行 `./setup.sh` 后，用已有的固定签名身份构建：

```bash
./build_local_app.sh  # dist-local/OpenFunASR.app 与独立的 dist-local/runtime
./build_full_app.sh   # dist-full/OpenFunASR.app，内含运行库与模型
.venv/bin/python test_openfunasr.py
```

不创建证书的临时开发构建：

```bash
OPENFUNASR_SIGN_IDENTITY=- OPENFUNASR_ALLOW_ADHOC=1 ./build_local_app.sh
```

临时开发包留在构建目录使用，正式安装脚本拒绝 ad-hoc 签名。
完整包包含第三方资产，对外分发前需核对各自许可。

真实引擎测试使用你自己提供的 16 kHz 单声道 PCM WAV，录音放在仓库外：

```bash
export OPENFUNASR_CONFIG_DIR="$PWD/.cache/test-config"
export OPENFUNASR_LOCAL_RUNTIME_ROOT="$PWD/dist-local/runtime"
export OPENFUNASR_TEST_AUDIO="$HOME/speech-test.wav"
.venv/bin/python test_funasr_integration.py
```

测试覆盖真实语音产生非空文本、静音不输出文本；不等于录音、识别准确率、菜单栏、
快捷键和实际粘贴已经通过验收。

## 隐私、更新与发布

设置、诊断日志和安装后的运行库存放在 `~/Library/Application Support/OpenFunASR/`。
录音临时写入 `/tmp`，正常处理后删除；异常或中断可能留下临时录音。
最近一次识别结果保留在程序内存和系统剪贴板中。诊断日志可能含本机路径、
前台应用信息和引擎错误输出，分享前请先检查和脱敏。

本仓库不收录模型权重、可执行程序、录音、日志、构建产物、个人设置、证书或私钥。
发布前运行：

```bash
python3 scripts/check_privacy.py
```

更新现有应用前阅读 [签名与权限说明](PERMISSION_SOP.md)；
上传 GitHub 前阅读 [发布说明](docs/PUBLISH.md)。
第三方下载来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可

本项目的应用源码和文档使用 [MIT License](LICENSE)。第三方运行库、依赖和模型权重
仍使用各自许可，本项目的 MIT 许可不覆盖这些第三方资产。
