# 项目审计与改造清单（2026-10-06）

基于本机已有修改与上游 main；完整备份已建立，使用 mac-ui-overhaul 分支。

| 能力 | 审计结果 | 改造 |
|---|---|---|
| tap / hold / auto | 已存在，auto 默认 250ms；repeat 连发 | 保留引擎，暴露阈值/连发，校验配置 |
| combination / sequence | 已存在，sequence 保持首键 | 修复释放状态残留，保留 repeat |
| macro / exec | 已存在，但 GUI 不能完整编辑 | 提供高级 JSON 编辑与校验 |
| window_switch | 任意按钮可设，短按下一窗口，长按选择器 | 修正文案、空目标默认、重复触发和选择状态 |
| 单左/单右/双手柄 | 有 profiles；双手柄只读一个设备，名称判断过宽 | 按设备分别轮询与逻辑键转换 |
| 摇杆 | 4/8 向、死区、中心校准 | 保留，显示与编辑参数 |
| 热插拔 | 已有重连，但退出等待不能取消 | 改为持续枚举、可退出的等待 |
| 电量 | HID 读取，macOS open failed 重复警告 | 安静降级，明确不可用 |
| keep-alive | HID 零强度震动 | 保留，失败只调试日志 |
| GUI | ttkbootstrap、简陋主窗/设置 | 保留框架，原生标题栏、设备卡片、映射表、滚动与主题 |
| 开机启动 | 没有 | macOS LaunchAgent / Windows Startup 开关 |
| 启动 | start.command/vbs 直接 main.py；platform 遮蔽 | 重命名平台层；模块启动；独立 .app |
| 打包 | 只有入口文件，没有打包流程 | PyInstaller spec、可写用户配置目录 |
| 配置 | 用户 profiles 正确，顶层旧映射不同步 | 同步有效右手柄预设，备份/导入/导出/校验 |
| 校准 | 独立终端脚本，要求人工修改源码 | GUI 按按钮录入；平台+GUID+名称持久化 |

右手柄实测 A0 X1 B2 Y3 Home5 Plus6 SL9 SR10 R12 ZR14 保留；其余设备默认只是回退，需校准。
本机 config/user.json 保持个人配置，不上传；公开 macOS 预设采用用户授权的快捷键组合，不包含个人应用列表。
框架选择：继续 ttkbootstrap，避免新增 Qt 的安装体积与迁移成本。打包使用 PyInstaller，保留 Windows 入口。
权限检测原来通过发送真实按键检查，改为只读 AX/Quartz 检测。辅助功能影响键盘输出，输入监控状态单独显示。

验证边界：自动化测试替代输出函数验证派发；真实按键/权限/登录重启与 Windows 需要相应环境或人工操作。
