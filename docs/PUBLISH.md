# 发布到 GitHub

建议仓库名：`OpenFunASR`，公开仓库，MIT 许可。默认 README 为英文，顶部可切换中文。
先发布源码；模型由安装脚本从固定来源下载。不要把原工作目录整体拖进 GitHub。

## 1. 核对发布内容

仓库应包含应用源码、构建安装脚本、中英文 README、AI 安装说明、许可和校验配置。
不要加入 `runtime-assets/`、`dist-*/`、`build-*/`、录音、日志、私人设置、备份或私钥。
`.gitignore` 不能移除已经提交过的敏感信息，所以应从这份脱敏副本建立全新的仓库。

如果这份副本已经包含脱敏的初始提交，保留它并跳过初始化和再次提交，直接检查文件、
提交身份及 remote。对于不含 Git 历史的源码压缩包，在解压后的项目目录执行：

```bash
python3 scripts/check_privacy.py
git init -b main
git add .
python3 scripts/check_privacy.py
git diff --cached --check
git diff --cached --stat
```

逐项阅读完整暂存差异，确认没有个人姓名、账号、真实邮箱、设备名称、私人 URL、
本机绝对路径、原始语音或转录文本。扫描器会检查已跟踪和未忽略的文本文件、当前系统
账户名、常见密钥格式、邮箱和个人目录；它不是对所有敏感信息的完整证明。
可通过 `--forbid` 增加其他私人姓名或标记，匹配时只显示位置和类别。

## 2. 提交身份也要脱敏

Git 的作者姓名和邮箱会进入提交历史。不要直接使用电脑现有的全局 Git 身份。
如果要在提交记录中使用完全独立的项目身份，可以仅在本仓库设置：

```bash
git config --local user.name 'OpenFunASR contributors'
git config --local user.email 'contributors@openfunasr.invalid'
git commit -m 'Initial public source release'
git log -1 --format=fuller
```

`.invalid` 地址用于项目匿名署名，不是联系邮箱，也不会关联到个人 GitHub 账户。
若希望关联 GitHub 账户，改用自己明确选择的 GitHub noreply 邮箱，并确认其中的账号信息
可以公开。不要使用未经确认的真实姓名或邮箱。

**公开仓库仍会显示其所属 GitHub 账号／组织。** 源码脱敏无法隐藏仓库所有者，
如果主账号本身含真实姓名，应使用愿意公开的独立账号或组织。

## 3. 创建公开仓库并推送

在确定目标 GitHub 账号／组织后，通过 GitHub 页面创建空的公开仓库 `OpenFunASR`，
不要让网页再生成 README 或 LICENSE。添加页面提供的 HTTPS remote，再推送 `main`。
也可以在已安装并登录的 GitHub CLI 中，如果这份副本已经包含脱敏的初始提交，保留它并跳过初始化和再次提交，直接检查文件、
提交身份及 remote。对于不含 Git 历史的源码压缩包，在解压后的项目目录执行：

```bash
gh repo create OpenFunASR --public --source=. --remote=origin --push \
  --description 'Local push-to-talk dictation for Apple Silicon macOS with Fun-ASR Nano'
```

该命令会立即公开上传，必须在目标账号和全部发布内容都已确认后执行。
不要把含访问令牌的 remote URL 保存进 Git 配置或分享给别人。

推送后检查 GitHub 文件页、中英文 README 链接、AI 安装文档和 Actions 结果。
从一个干净克隆验证安装前，不要宣传为已经跨机器验证的“一键安装”。

## 4. 后续二进制 Release

先积累源码安装反馈，再考虑提供 `.app` 下载。对外的完整包需单独处理第三方许可文本、
模型分发条件、二进制内嵌路径、Apple Developer ID 签名与公证，以及文件校验值。
本机自签证书与私钥不能随 Release 分发，也不要把本机自签包描述成已公证应用。
