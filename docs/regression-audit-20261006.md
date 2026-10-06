# JoyHarness 功能回归审计 · 2026-10-06

当前分支：mac-ui-overhaul。修改前保存 backup/pre-regression-20261006（21520d9），配置备份在 ~/JoyHarness/backups/regression-20261006。只做本地提交，未 fork/push。

## 输入无响应审计

对比上游 347b2b6 的 src/main.py：pygame display/joystick 初始化、find_joycon、detect_connection_mode、get_profile、KeyMapper、BatteryReader、KeepAliveManager、后台线程、模式回调、键盘输出和 release_all 均存在。新版线程转而调用 controller_runtime.run_controllers，原版调用 joycon_reader.run_polling_loop；新版支持独立双手柄与持久化设备校准，继续保留这个运行器，没有创建第二套 GUI 后台。

确定的缺口：dummy SDL 显示没有焦点，入口未开启 SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS；后台状态此前只显示设备/电量，轮询异常仅写日志，无法判断是否真正监听；轮询模式回调直接跨线程调用 Tk。修复后台输入开关、显式初始化设备、可见监听/异常/权限状态、逐键原始索引和动作路径，并把模式 UI 更新交回主线程。退出包含 GUI 异常时也释放按键并停止线程。

不能确认的部分：审计时 pygame 检测到 0 个手柄，历史 .app 日志显示此前检测到 Nintendo Switch Joy-Con (R)，但没有逐键输入记录或线程 traceback。不能把上述代码缺口冒充已实机复现的唯一根因。源代码进程辅助功能与输入监控均为已允许；本次 .app 启动也未报告权限警告。

## 使用

主界面右侧选择切换按钮，下拉选中即保存当前 profile 并提交给轮询线程应用。允许多个键绑定；各键仍可通过左侧双击编辑。SR 默认保持 window_switch，短按下一个、长按选择器。

添加应用填写显示名称和 macOS 应用进程名（Windows 为 EXE），保存后立即进入勾选列表；新目标默认勾选。扫描运行应用列出当前前台类型应用，双击或选中后点添加，确认信息并保存。每行可编辑/删除。扫描在本机返回 16 个运行应用。

左侧映射表、右侧应用列表分别滚动，关键操作固定可见；底部运行设置和权限入口，上方真实设备/电量/输入状态。主题支持浅色、深色和跟随系统。

设置与校准沿用独立的动作 profile 与硬件 device_profiles。选已连接设备、点逻辑键、按实体键、保存；期间拦截快捷键输出。配置页可导入/导出/备份。恢复默认只暂存当前模式快捷键，不清除设备校准。


双击同目录 JoyHarness.app。调试可双击“启动调试.command”，其调用同一个应用入口的 --debug。主界面显示最近 BTN→逻辑键→action，完整 DEBUG 日志写入 ~/Library/Application Support/JoyHarness/joyharness.log。请先关闭其他 JoyHarness 实例，避免重复发送。

## 验证

- python -m compileall src 通过。
- 默认 pytest：62 passed，1 skipped；启用 JOYHARNESS_UI_TEST=1 后，真实 Tk 界面测试也通过，共 63 passed（2 个旧主题名称弃用警告，依赖已限制在 3.0 以下）。新增模拟 pygame 设备的实际轮询→KeyMapper→模拟键盘输出测试覆盖八个快捷键、SR、四个摇杆方向；另覆盖线程异常可见状态、后台输入开关、应用目标持久化和切换按钮绑定后的运行时应用。既有短/长按选择器与双设备测试通过。
- python -m src --smoke-test 通过；直接 python src/main.py --list-controls 通过，已使用 app_platform 包，无 platform 同名冲突。
- 已运行真实 Tk 界面并查看截图，修正滚动区挤掉添加/扫描按钮的问题。PyInstaller .app 使用 pyinstaller_entry.py→src.main.main 同一启动链路。
- 实体手柄按键尚未验证，因为当前未检测到手柄。需要连接右 Joy-Con，在其他应用中逐个确认八个快捷键、SR 短/长按以及摇杆四方向，同时观察主界面输入路径。如果无 BTN 记录，是读取层问题；若有路径无键盘效果，再看权限/键盘输出层。

## 修改文件

src/main.py、src/controller_runtime.py、src/gui.py、src/settings_window.py、src/config_loader.py、src/window_switcher.py、tests/test_core.py、tests/test_runtime_regression.py，及本审计文档。运行状态不会写入持久化配置。
