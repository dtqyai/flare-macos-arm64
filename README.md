# Flare for Apple Silicon

自动获取官方 Flare 引擎和游戏资源，构建原生 arm64 macOS 应用。非官方构建项目，不修改或替代上游仓库。

[下载构建版本](https://github.com/dtqyai/flare-macos-arm64/releases) · [运行记录](https://github.com/dtqyai/flare-macos-arm64/actions/workflows/build.yml)

## 下载与运行

在 Releases 页面打开最近一次预发布，下载 `Flare-AppleSilicon.zip`，解压后打开 `Flare.app`，或将应用拖到“应用程序”。

- Apple Silicon（M 系列芯片），macOS 15.0 及以上。
- 包含 Empyrean Campaign、中文资源和运行库，不需要安装 Homebrew 或 Rosetta。
- 跟随官方 `master` 开发分支，属于开发快照，可能包含上游尚未修复的问题。
- 使用 ad-hoc 签名，未通过 Apple Developer ID 签名或公证。下载后 macOS 可能需要在“系统设置 → 隐私与安全性”中确认打开；不要关闭系统整体安全保护。
- 默认配置：`~/.config/flare/`；默认存档：`~/.local/share/flare/saves/`。

## 自动构建

每天 UTC 02:23（北京时间/新加坡时间 10:23）检查官方 [引擎](https://github.com/flareteam/flare-engine) 和 [游戏资源](https://github.com/flareteam/flare-game) 的最新提交。

两个上游提交与本项目提交共同组成构建标识。该标识已有完整公开发布包时跳过编译，否则在 GitHub 的 `macos-15` arm64 构建机上构建。先上传草稿 Release，重新下载校验后才公开；失败草稿可通过重跑恢复。

手动运行：**Actions → Build Apple Silicon → Run workflow**。同一构建标识已发布时仍会跳过；修改构建项目后会重新构建。

不需要 fork、同步上游代码或个人访问令牌。构建阶段只有只读权限；独立发布任务使用 `GITHUB_TOKEN` 写入本仓库 Releases。外部 PR 不会触发发布。

GitHub 定时任务可能延迟；公开仓库连续 60 天没有活动时，定时工作流可能自动停用，届时需在 Actions 页面重新启用。本项目不通过无意义提交规避此限制。

## 本地构建与验证

`dependencies.json` 固定 SDL2、SDL2_image、SDL2_mixer、SDL2_ttf、FreeType 源码版本和 SHA-256。依赖全部编译到项目内部，不使用 Homebrew 运行库。工具要求：原生 arm64 Mac、CMake、Python 3.12+、Git、Xcode 命令行工具。

图像与 Ogg 使用 SDL 附带的 stb 解码器。保留官方游戏使用的 PNG、Ogg、WAV、TrueType 支持；不启用额外 TIFF/WebP/AVIF、Opus、MIDI、MOD 解码器或 HarfBuzz。这不是所有第三方 mod 的完整依赖环境。

```sh
git clone https://github.com/dtqyai/flare-macos-arm64.git
cd flare-macos-arm64
mkdir -p work
git clone --depth 1 https://github.com/flareteam/flare-engine.git work/flare-engine
git clone --depth 1 --filter=blob:none --sparse https://github.com/flareteam/flare-game.git work/flare-game
git -C work/flare-game sparse-checkout set mods
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 scripts/package.py
```

打包脚本拒绝覆盖现有应用，重建时请使用新目录或自行清理本项目生成的 `dist/`。复现发布时，按 `BUILD-INFO.json` 检出对应构建项目、引擎和游戏提交。源码与配方已固定，编译器和 SDK 版本也有记录，但不承诺逐字节可复现。

验证内容：所有 Mach-O 均为 arm64；最低系统版本不超过 15.0；非系统库必须位于应用内部；签名校验；版本启动；捆绑库加载真实 PNG/Ogg/TTF 资源；ZIP 完整性和发布后下载校验。完整图形交互和通关不属于自动测试范围。

## 发布文件与许可证

- `Flare-AppleSilicon.zip`：自包含游戏应用。
- `Flare-corresponding-source.tar.gz`：对应引擎源码、依赖源码、构建脚本。
- `BUILD-INFO.json`：源码提交、依赖版本、编译器、SDK、构建选项。
- `SHA256SUMS.txt`：上述三个文件的校验值。

本项目脚本采用 GPL-3.0-or-later。Flare 引擎采用 GPL-3.0-or-later；游戏美术、数据与字体遵循上游各自许可证。应用保留上游 LICENSE、COPYING、CREDITS 和依赖许可文件，完整依赖许可也在对应源码包中。

[官方 Flare 网站](https://flarerpg.org/)
