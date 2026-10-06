# JoyHarness

把 Nintendo Switch Joy-Con 变成桌面快捷键控制器。支持 macOS 与 Windows、单左 / 单右 / 双手柄、设备校准、窗口切换和可编辑工作流。

本仓库基于 [VaderCheng/JoyHarness](https://github.com/VaderCheng/JoyHarness) 二次开发，保留原作者版权声明与 [MIT License](LICENSE)。本次审计与改造清单见 [docs/AUDIT.md](docs/AUDIT.md)。

## 主要功能

- 中文工作台：设备、连接模式、当前 profile、电量、摇杆、keep-alive、登录启动、权限、窗口目标与映射一屏查看。
- 主界面双击任意按键行或点“编辑选中键位”，可录入键盘快捷键。窗口切换区可以直接选择任意物理按钮并绑定。
- 按键表格编辑，Mac 修饰键显示为 ⌘ Command、⌥ Option、⌃ Control、⇧ Shift；存储仍使用标准键名。
- 首次设备校准：选择设备 → 点物理按钮名称 → 按实体键 → 保存。平台、SDL GUID 与设备名称作为设备身份，无需改源码。
- 每个连接模式独立动作 profile；两个独立 Joy-Con 分别轮询，侧键转换为 SL_L / SR_L / SL_R / SR_R。
- 4 / 8 向摇杆、死区、按键连发、热插拔、配置导入 / 导出 / 自动备份、亮色 / 暗色主题。
- 电量读取不可用时安静降级；keep-alive 使用周期性零强度震动，HID 不可访问时不影响按键映射。

## macOS 安装与启动

推荐把打包产物 `JoyHarness.app` 放到固定位置，再双击运行。不需要终端或另外安装 Python。若移动了应用位置，重新切换一次登录启动开关。

源码运行推荐 Python 3.12；本机也验证 Python 3.14.5 + pygame 2.6.1。3.14 的 pygame 可能需要编译，取决于系统 SDL 开发库，不能保证每台机器直接安装成功。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src
```

完成依赖安装后可双击 `start.command`，优先使用仓库 `.venv`。模块入口为 `python -m src`；直接 `python src/main.py` 也已修复标准库 `platform` 命名冲突。

### 打包

双击 `scripts/build-macos.command`，或：

```sh
.venv/bin/python -m pip install pyinstaller
.venv/bin/python -m PyInstaller --noconfirm JoyHarness.spec
```

产物：`dist/JoyHarness.app`。打包只包含公开预设，排除本机 `config/user.json` 和所有配置备份。此构建为本地 ad-hoc 签名，未使用开发者证书、未公证；其他 Mac 的 Gatekeeper 分发体验尚未验证。

### 权限

工作台显示当前进程的辅助功能和输入监控状态，并提供系统设置入口。检测采用只读 AX / Quartz API，不发送测试按键。

- **辅助功能**：键盘快捷键输出与指定窗口激活需要。
- **输入监控**：系统 / SDL / 驱动相关输入读取可能需要；具体以运行环境为准。
- **自动化**：窗口管理回退到 AppleScript 时，系统可能请求控制 System Events 的权限。
- **屏幕录制**：部分窗口标题受系统隐私限制，不授权时可能只能显示应用名称。

在系统设置 → 隐私与安全性中授权实际运行的应用或 Python / 终端进程。源码和 `.app` 是不同授权身份；重新打包可能需要重新授权。应用不会自动修改系统权限。

## Windows 安装与启动

推荐 Python 3.12：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m src
```

安装依赖后双击 `start.vbs`；优先使用 `.venv\Scripts\pythonw.exe`。可用相同 `JoyHarness.spec` 打包窗口程序：

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --noconfirm JoyHarness.spec
```

产物 `dist\JoyHarness\JoyHarness.exe`。控制管理员应用时可能需要以管理员身份运行。Windows 构建与 CI 保留；本次本机只有 macOS，未声称 Windows 实机验证通过。

## 配对与首次校准

1. 在系统蓝牙设置中配对 Joy-Con，长按滑轨的小配对按钮至灯闪烁。
2. 打开应用，未连接时工作台仍保持打开并等待热插拔。
3. 设置与校准 → 设备校准 → 选择已连接设备。
4. 点击 A、B、R、ZR 等按钮名称，按下对应实体按钮。录入阶段暂停快捷键输出。
5. 检查识别结果，点击“保存并应用”。重复索引会交换原按钮绑定，避免两个物理名抢同一个索引。
6. 新设备身份、SDL / 驱动改变或按钮不一致时重新校准。也可在校准页设置摇杆 X / Y 轴索引；轴方向可在设备 JSON 中设置 ±1。

**ZR 在正确校准、驱动暴露该按钮的设备上可用。SL / SR 也可自定义；可用性取决于驱动输入，不能笼统称为“不稳定”或“不可用”。** 左手柄与组合设备预设索引仍为回退值，建议首次使用完成校准。

### 本机已验证右手柄索引与 macOS 预设

| 按钮 | SDL 索引 | 动作 |
|---|---:|---|
| A | 0 | Enter |
| X | 1 | ⌘ C 复制 |
| B | 2 | Esc |
| Y | 3 | ⌘ V 粘贴 |
| Home | 5 | ⌘ Z 撤销 |
| Plus | 6 | ⌘ A 全选 |
| SL | 9 | 保留 Command hold，可自定义 |
| SR | 10 | window_switch |
| R | 12 | ⌃ Q（闪电说，需该应用设置对应快捷键） |
| ZR | 14 | ⌥ A（iShot，需该应用设置对应快捷键） |
| 摇杆 | X=1 / Y=0 | 上下左右，100ms 连发 |

这些值保留了用户实测结果，但并非所有设备通用。实体键映射在设备配置，快捷键动作在 profile，二者分别保存。

## 动作说明

| 类型 | 行为 |
|---|---|
| `tap` | 按下时立即点击 |
| `hold` | 按下保持，松开释放 |
| `auto` | 短按松开时 tap；达到长按阈值后 hold；若 repeat > 0，长按后按间隔连发 |
| `combination` | 同时按组合键，逆序释放，例如 command+c |
| `sequence` | 按住第一个修饰键，点击余下按键；支持 repeat，松开时全部释放 |
| `window_switch` | 短按切下一个目标窗口；长按打开选择器，按间隔移动选择，松开确认 |
| `macro` | 顺序执行 combination / tap / hold / release / delay / type 步骤；可用 if_window 限定前台进程 |
| `exec` | 执行 Shell 命令字符串，或参数数组（数组不经 Shell） |

短按 / 长按原项目已经实现，本版本改进配置、状态释放与体验。默认长按阈值 0.25 秒、窗口选择速度 400 毫秒，可在设置中调整。摇杆 auto 是立即 tap 后连发，与物理按钮 auto 的延迟判断不同。

高级按钮可以编辑完整动作 JSON。宏里的 hold 应有配对 release；宏和 delay 目前在轮询线程顺序执行，长宏会暂时阻塞输入，不建议安排长时间延时。导入他人配置前检查 exec / macro 内容；导入操作本身不会执行命令，映射生效后按按钮才执行。

窗口切换目标在主界面勾选，所有绑定 `window_switch` 的按钮共用目标列表，不再与 R 绑定。未选择目标时不切换窗口。macOS 填“应用进程名”，Windows 填“进程 / EXE”。全屏与其他 Space 的窗口可能不可见。

## 登录时自动启动

主界面“登录时自动启动”开关，默认关闭，读取实际安装状态：

- macOS：用户级 `~/Library/LaunchAgents/io.joyharness.login.plist`，下一次登录启动；关闭会卸载该登录任务并移除文件。不会创建系统级 daemon。
- Windows：用户 Startup 文件夹中的 `JoyHarness.vbs`，关闭即删除本应用创建的启动项。Task Scheduler 可由用户自行选择用于管理员运行，本版默认无需管理员任务。

固定应用 / 仓库位置与 Python 环境后再开启；移动位置后重新开启。登录重启全过程需要人工验证，本次仅验证创建 / 删除机制。

## 配置、备份与项目结构

源码优先 `config/user.json`，其次平台预设，最后内置默认。打包版本个人配置：

- macOS：`~/Library/Application Support/JoyHarness/user.json`
- Windows：`%APPDATA%\JoyHarness\user.json`

用户配置包含 `profiles`（single_right / single_left / dual）、`device_profiles`（设备身份 → buttons / axes）、`known_apps`、`selected_apps`、摇杆参数与主题。自定义 `--config path.json` 在保存时继续写该文件。每次覆盖前在相邻 `backups/` 自动备份，写入采用临时文件替换。备份不自动删除，可在确认后自行清理。

```text
src/main.py               入口、线程和退出
src/controller_runtime.py 多设备轮询、热插拔与校准事件
src/device_profiles.py    设备映射与校验
src/hardware_defaults.py  回退按钮与轴索引
src/default_profiles.py   默认动作 profile
src/config_loader.py      配置合并、校验、原子保存和备份
src/key_mapper.py          既有动作引擎
src/gui.py                 中文工作台
src/settings_window.py     映射、目标、校准和导入导出
src/app_platform/          平台与只读权限检测
src/autostart.py           登录启动开关
```

常用命令：`python -m src --discover` 查看原始索引；`--list-controls` 查看有效配置；`--verbose` 记录调试日志；`--smoke-test` 短暂打开 GUI 并退出，不保存配置 / 不发送按键。打包版错误日志保存在个人配置目录 `joyharness.log`。

## 验证与限制

```sh
python -m pip install pytest ruff
python -m compileall -q src calibrate.py
ruff check src tests/test_core.py --select E9,F63,F7,F82
python -m pytest -q
python -m src --smoke-test
```

旧 `tests/test_headless.py` / battery / reconnect 等是需要真实手柄的手动诊断工具；`tests/test_core.py` 与后续自动化用例不发送真实键盘事件。

macOS HID 被 SDL 或驱动占用时，电量会显示“电量不可用”；keep-alive 也可能无法发送。不会强行抢占设备或停止其他程序。双手柄与 Windows 逻辑经过自动化验证，仍需对应实体硬件 / 系统实测。测试快捷键派发不等于闪电说、iShot 的实际响应或真实物理按键测试。

## 致谢与许可证

原作者 VaderCheng 与上游 [JoyHarness](https://github.com/VaderCheng/JoyHarness)，以及 pygame、ttkbootstrap、pynput、PyObjC、hidapi、PyInstaller 等项目。本项目遵循 MIT，保留 LICENSE 中原作者的版权与许可全文。
