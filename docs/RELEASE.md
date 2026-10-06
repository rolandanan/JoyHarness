JoyHarness v1.2.0 · macOS Workflow Update

基于 VaderCheng/JoyHarness 二次开发，保留上游历史、原作者版权和 MIT License。

- 新中文工作台，真实后台输入状态、按键编辑和可自定义窗口切换按钮。
- 应用目标添加、编辑、删除、扫描；配置导入、导出与自动备份。
- 按平台、SDL GUID、设备名称持久化按钮与轴校准；公共 macOS 预设使用中性快捷键，默认不包含个人应用目标。
- 摇杆四/八方向、死区、首发等待、连发和轴反转；热插拔、keep-alive、电量不可用时降级。
- macOS / Windows 登录启动开关；源码和打包应用共用 backend bootstrap。
- 自动构建 Windows x64 ZIP、macOS Apple Silicon ZIP / DMG。

macOS：解压 ZIP 或打开 DMG，将 JoyHarness.app 放进“应用程序”。自行完成蓝牙配对，并在系统设置授权辅助功能与所需输入监控权限；首次使用请校准设备。ZR 在设备驱动暴露输入且正确校准后可用，SL/SR 依 SDL 和设备而异。

**macOS 产物只有 ad-hoc 签名，没有 Developer ID 签名，也没有 Apple 公证。** Gatekeeper 可能拦截；确认来源后在“隐私与安全性”选择“仍要打开”。Intel Mac 尚未构建或验证。

Windows CI 构建不代表 Windows 实体设备验证。双手柄、登录重启全过程及其他 Mac 的权限/Gatekeeper 行为仍需对应环境验证。长 macro/delay 会阻塞轮询，不适合长时间任务。
