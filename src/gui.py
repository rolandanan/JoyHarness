"""Main GUI for NS Joy-Con Keyboard Mapper.

Uses ttkbootstrap for a modern dark theme appearance.
Provides controls for:
- Enabling/disabling stick mapping
- Selecting target applications for window switching (R key)

Cross-platform: Windows and macOS.
"""

from __future__ import annotations

import sys
import logging
import threading

import ttkbootstrap as ttk
from ttkbootstrap.constants import (
    BOTH, DANGER, INFO, LEFT, RIGHT, SECONDARY, SUCCESS, WARNING, X, W,
)

from .battery_reader import BatteryReader
from .config_loader import save_config
from .key_mapper import KeyMapper
from .resizable import ResizableMixin
from .window_switcher import WindowCycler, KNOWN_APPS

logger = logging.getLogger(__name__)

_UI_FONT = "Helvetica" if sys.platform == "darwin" else "Microsoft YaHei UI"


class MainWindow(ResizableMixin):
    """Main application window for the Joy-Con mapper."""

    def __init__(
        self,
        key_mapper: KeyMapper,
        window_cycler: WindowCycler,
        config: dict,
        stop_event: threading.Event,
        on_minimize=None,
        battery_reader: BatteryReader | None = None,
        connection_mode: str = "single_right",
        keep_alive_manager=None,
    ) -> None:
        self._key_mapper = key_mapper
        self._window_cycler = window_cycler
        self._config = config
        self._pending_mode = None
        self._stop_event = stop_event
        self._on_minimize = on_minimize
        self._battery_reader = battery_reader
        self._connection_mode = connection_mode
        self._keep_alive_manager = keep_alive_manager

        self._root = ttk.Window(
            title="JoyHarness · 工作台",
            themename="litera" if config.get("theme", "system") == "system" else config["theme"],
            size=(1080, 720),
            resizable=(True, True),
        )
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.report_callback_exception = self._callback_error
        self._root.minsize(820, 620)

        # On Windows, remove native title bar for a clean dark look.
        # On macOS, keep the native title bar for better system integration
        # (Dock icon, Mission Control, system-native minimize/close).
        self._frameless = False
        if self._frameless:
            self._root.overrideredirect(True)
        self._root.attributes("-topmost", False)

        # App selection variables: display_name → BooleanVar
        self._app_vars: dict = {}

        self._apply_theme()
        self._build_ui()
        self._configure_styles()
        if self._frameless:
            self._setup_resize()
        self._center_window()

    def _callback_error(self, kind, error, traceback):
        logger.error("UI callback failed", exc_info=(kind, error, traceback))
        from tkinter import messagebox
        self._input_label.configure(text=f"界面操作失败：{error}")
        messagebox.showerror("操作失败", str(error), parent=self._root)

    def _build_ui(self) -> None:
        """Build the UI layout."""
        from ttkbootstrap import ScrolledFrame
        main = ttk.Frame(self._root)
        main.pack(fill=BOTH, expand=True)
        header = ttk.Frame(main, padding=(24, 8))
        header.pack(fill=X)
        ttk.Label(header, text="JoyHarness", font=(_UI_FONT, 20, "bold")).pack(side=LEFT)
        ttk.Button(header, text="设置与校准", command=self._open_settings, bootstyle="secondary-outline").pack(side=RIGHT)
        ttk.Label(header, text="让手柄融入你的 Mac 工作流" if sys.platform == "darwin" else "让手柄融入你的工作流", font=(_UI_FONT, 12), style="Muted.TLabel").pack(side=LEFT, padx=18)
        overview = ttk.Frame(main)
        overview.pack(fill=X, padx=24, pady=4)
        status = ttk.Labelframe(overview, text="设备与配置", padding=10)
        status.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 16))
        control = ttk.Labelframe(main, text="运行设置与权限", padding=10)
        control.pack(side="bottom", fill=X, padx=24, pady=8)
        self._device_status = ttk.Label(status, text="正在检测设备…", font=(_UI_FONT, 13, "bold"), wraplength=460)
        self._device_status.pack(anchor=W)
        self._profile_status = ttk.Label(status, text="", wraplength=950)
        self._profile_status.pack(anchor=W, pady=4)
        battery = ttk.Frame(status)
        battery.pack(fill=X)
        self._battery_label_l = ttk.Label(battery, text="L：检测中…")
        self._battery_label_l.pack(side=LEFT)
        self._battery_label_r = ttk.Label(battery, text="R：检测中…")
        self._battery_label_r.pack(side=LEFT, padx=24)
        options = ttk.Frame(control)
        options.pack(fill=X)
        self._stick_var = ttk.BooleanVar(value=self._config.get("stick_enabled", True))
        self._keep_alive_var = ttk.BooleanVar(value=self._config.get("keep_alive_enabled", True))
        from .autostart import is_enabled
        self._login_var = ttk.BooleanVar(value=is_enabled())
        for label, variable, command in (("摇杆映射", self._stick_var, self._on_stick_toggle), ("保持手柄唤醒", self._keep_alive_var, self._on_keep_alive_toggle), ("登录时自动启动", self._login_var, self._on_login_toggle)):
            ttk.Checkbutton(options, text=label, variable=variable, command=command, bootstyle="success-round-toggle").pack(side=LEFT, padx=8, pady=4)
        self._theme_var = ttk.StringVar(value={"darkly": "深色", "litera": "浅色"}.get(self._config.get("theme"), "跟随系统"))
        theme = ttk.Combobox(options, textvariable=self._theme_var, values=("跟随系统", "浅色", "深色"), state="readonly", width=7)
        theme.pack(side=LEFT, padx=8, pady=4)
        theme.bind("<<ComboboxSelected>>", self._change_theme)
        permissions = ttk.Frame(control, padding=(0, 4))
        permissions.pack(fill=X)
        self._permission_label = ttk.Label(permissions, text="", wraplength=290, font=(_UI_FONT, 10))
        self._permission_label.pack(side=LEFT)
        permission_links = ttk.Frame(options)
        permission_links.pack(side=RIGHT, pady=(2, 0))
        if sys.platform == "darwin":
            from .app_platform.permission import open_permission_settings
            ttk.Button(permission_links, text="辅助功能", bootstyle="primary-outline", command=open_permission_settings).pack(side=RIGHT)
            ttk.Button(permission_links, text="输入监控", bootstyle="primary-outline", command=lambda: open_permission_settings("ListenEvent")).pack(side=RIGHT)
        body = ttk.Frame(main)
        body.pack(fill=BOTH, expand=True, padx=24, pady=8)
        targets = ttk.Labelframe(body, text="窗口切换目标应用", padding=12)
        targets.pack(side=RIGHT, fill=BOTH, padx=(12, 0))
        binding = ttk.Frame(targets)
        binding.pack(fill=X, pady=(0, 10))
        ttk.Label(binding, text="自定义切换按钮：").pack(side=LEFT)
        self._switch_button = ttk.StringVar(value="SR")
        self._switch_combo = ttk.Combobox(binding, textvariable=self._switch_button, values=tuple(self._config.get("mappings", {}).get("buttons", {})), state="readonly", width=9)
        self._switch_combo.pack(side=LEFT, padx=8)
        self._switch_combo.bind("<<ComboboxSelected>>", lambda event: self._bind_window_switch())

        self._switch_status = ttk.Label(binding, text="当前：SR", style="Muted.TLabel")
        self._switch_status.pack(side=LEFT, padx=4)
        ttk.Label(targets, text="勾选切换目标 · 短按切换 · 长按选择", style="Muted.TLabel").pack(anchor=W, pady=(0, 8))
        app_scroll = ScrolledFrame(targets, auto_hide=True, height=260)
        app_scroll.pack(fill=BOTH, expand=True)
        self._app_frame = ttk.Frame(app_scroll)
        self._app_frame.pack(fill=X)
        self._build_app_checkboxes()
        app_tools = ttk.Frame(targets)
        app_tools.pack(side="bottom", fill=X, pady=8, before=app_scroll.container)
        ttk.Button(app_tools, text="添加应用", command=self._app_editor, bootstyle="secondary-outline").pack(side=LEFT)
        ttk.Button(app_tools, text="扫描运行应用", command=self._scan_apps, bootstyle="secondary-outline").pack(side=LEFT, padx=6)
        mapping = ttk.Labelframe(body, text="当前按键工作流", padding=12)
        mapping.pack(side=LEFT, fill=BOTH, expand=True)
        toolbar = ttk.Frame(mapping)
        toolbar.pack(fill=X, pady=(0, 10))
        ttk.Label(toolbar, text="双击任意一行即可修改动作和快捷键", style="Muted.TLabel").pack(side=LEFT)
        ttk.Button(toolbar, text="编辑选中键位", command=self._edit_selected, bootstyle="primary-outline").pack(side=RIGHT)
        self._mapping_table = ttk.Treeview(mapping, columns=("button", "action", "target"), show="headings", height=11, style="Workflow.Treeview", selectmode="browse")
        for name, title, width in (("button", "按钮 / 摇杆", 90), ("action", "动作类型", 100), ("target", "快捷键 / 命令", 230)):
            self._mapping_table.heading(name, text=title)
            self._mapping_table.column(name, width=width, minwidth=80, anchor="center")
        self._mapping_table.pack(fill=BOTH, expand=True)
        self._mapping_table.bind("<Double-1>", self._edit_selected)
        scrollbar = ttk.Scrollbar(mapping, orient="vertical", command=self._mapping_table.yview)
        scrollbar.pack(side=RIGHT, fill="y", before=self._mapping_table)
        self._mapping_table.configure(yscrollcommand=scrollbar.set)
        self._runtime_label = ttk.Label(status, text="输入监听：未启动", wraplength=850)
        self._runtime_label.pack(anchor=W, pady=4)
        self._input_label = ttk.Label(main, text="等待手柄输入…", wraplength=1000, style="Muted.TLabel")
        self._input_label.pack(side="bottom", fill=X, padx=24, pady=4, before=body)
        self._root.after(300, self._refresh_status)
        if self._battery_reader:
            self._root.after(2000, self._update_battery_display)

    def _refresh_status(self):
        if self._stop_event.is_set():
            return
        from .constants import MODE_LABELS
        if self._pending_mode is not None:
            self._root.title(f"JoyHarness [{MODE_LABELS.get(self._pending_mode, self._pending_mode)}]")
            self._pending_mode = None
        from .key_labels import action_label
        from .mapping_editor import ACTION_TITLES
        from .app_platform.permission import has_required_permissions, input_monitoring_status
        if self._config.get("theme", "system") == "system":
            self._apply_theme()
        runtime = self._config.get("runtime_status", {})
        state = runtime.get("state", "未启动")
        if state == "输入监听中" and not has_required_permissions():
            state = "权限缺失 · 请允许辅助功能后重启" if sys.platform == "darwin" else "权限不足 · 部分应用需要管理员权限"
        elif state == "输入监听中" and sys.platform == "darwin" and input_monitoring_status() is False:
            state = "输入监控待授权 · 可在下方打开系统设置"
        self._runtime_label.configure(text=f"输入监听：{state}  {runtime.get('error', '')}")
        self._input_label.configure(text=runtime.get("last_input") or "等待手柄输入…")
        devices = self._config.get("runtime_devices", [])
        self._device_status.configure(text=" · ".join(d["name"] for d in devices) or "未连接 · 请在蓝牙设置连接 Joy-Con")
        mode = self._config.get("active_profile", "single_right")
        self._connection_mode = mode
        calibrated = all(d["identity"] in self._config.get("device_profiles", {}) for d in devices) if devices else False
        self._profile_status.configure(text=f"当前 profile：{MODE_LABELS.get(mode, mode)}  ·  {self._config.get('stick_mode', '4dir')}  ·  死区 {self._config.get('deadzone', .2):.2f}  ·  {'已保存设备校准' if calibrated else '使用预设，可在设置中首次校准'}")
        if sys.platform == "darwin":
            monitoring = input_monitoring_status()
            self._permission_label.configure(text=f"辅助功能：{'已允许' if has_required_permissions() else '待授权'}  ·  输入监控：{'已允许' if monitoring else '待授权' if monitoring is False else '无法检测'}")
        else:
            self._permission_label.configure(text="权限：" + ("管理员" if has_required_permissions() else "普通用户，部分应用可能需要管理员权限"))
        fingerprint = repr(self._config.get("mappings"))
        if fingerprint != getattr(self, "_mapping_fingerprint", None):
            self._mapping_fingerprint = fingerprint
            selection = self._mapping_table.selection()
            self._mapping_table.delete(*self._mapping_table.get_children())
            for button, value in self._config.get("mappings", {}).get("buttons", {}).items():
                self._mapping_table.insert("", "end", iid=button, values=(button, ACTION_TITLES.get(value.get("action"), value.get("action")), action_label(value)))
            buttons = tuple(self._config.get("mappings", {}).get("buttons", {}))
            for direction, label in (("up", "摇杆 ↑ 上"), ("down", "摇杆 ↓ 下"), ("left", "摇杆 ← 左"), ("right", "摇杆 → 右")):
                value = self._config.get("mappings", {}).get("stick_directions", {}).get(direction, {})
                self._mapping_table.insert("", "end", iid=f"stick:{direction}", values=(label, "连发 auto" if value.get("action") == "auto" else ACTION_TITLES.get(value.get("action"), "未映射"), action_label(value)))
            rows = self._mapping_table.get_children()
            if rows:
                self._mapping_table.selection_set(selection[0] if selection and selection[0] in rows else rows[0])
            self._switch_combo.configure(values=buttons)
            switches = [name for name, value in self._config.get("mappings", {}).get("buttons", {}).items() if value.get("action") == "window_switch"]
            self._switch_status.configure(text="当前：" + (" / ".join(switches) or "尚未绑定"))
            if self._switch_button.get() not in buttons:
                self._switch_button.set(next(iter(switches or buttons), ""))
        self._root.after(1000, self._refresh_status)

    def _on_login_toggle(self):
        from .autostart import set_enabled, is_enabled
        from tkinter import messagebox
        try:
            set_enabled(self._login_var.get())
        except OSError as error:
            self._login_var.set(is_enabled())
            messagebox.showerror("登录启动失败", str(error), parent=self._root)

    def _change_theme(self, event=None):
        value = {"深色": "darkly", "浅色": "litera", "跟随系统": "system"}[self._theme_var.get()]
        self._config["theme"] = value
        self._apply_theme()
        save_config(self._config)

    def _apply_theme(self):
        value = self._config.get("theme", "system")
        if value == "system":
            dark = False
            if sys.platform == "darwin":
                from Foundation import NSUserDefaults
                dark = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark"
            value = "darkly" if dark else "litera"
        self._root.style.theme_use(value)
        self._configure_styles()

    def _configure_styles(self):
        from tkinter import font
        font.nametofont("TkDefaultFont").configure(family=_UI_FONT, size=12)
        font.nametofont("TkTextFont").configure(family=_UI_FONT, size=12)
        dark = self._root.style.theme.name == "darkly"
        foreground = "#e5e7eb" if dark else "#26323e"
        muted = "#cbd5e1" if dark else "#52606d"
        style = self._root.style
        style.configure("TLabel", foreground=foreground, font=(_UI_FONT, 12))
        style.configure("Muted.TLabel", foreground=muted, font=(_UI_FONT, 12))
        style.configure("secondary.TLabel", foreground=muted)
        style.configure("Workflow.Treeview", rowheight=26, font=(_UI_FONT, 11))
        style.configure("Workflow.Treeview.Heading", font=(_UI_FONT, 12, "bold"), padding=(6, 6))

    def _save_button_mapping(self, button, value):
        self._save_mapping("buttons", button, value)

    def _save_mapping(self, group, name, value):
        import copy
        from .config_loader import validate_config
        mode = self._config.get("active_profile", "single_right")
        candidate = copy.deepcopy(self._config)
        if group == "stick_directions" and value.get("action") not in ("auto", "tap", "hold", "combination"):
            raise ValueError("摇杆方向支持 auto 连发、tap 点击、hold 保持和 combination 组合键")
        candidate["profiles"][mode]["mappings"].setdefault(group, {})[name] = value
        candidate["mappings"] = copy.deepcopy(candidate["profiles"][mode]["mappings"])
        errors = validate_config(candidate)
        if errors:
            raise ValueError("\n".join(errors))
        save_config(candidate)
        def apply():
            self._config["profiles"][mode] = candidate["profiles"][mode]
            active = self._config.get("active_profile", "single_right")
            self._config["mappings"] = copy.deepcopy(self._config["profiles"][active]["mappings"])
        self._key_mapper.command_queue.put(apply)

    def _edit_selected(self, event=None):
        selection = self._mapping_table.selection()
        if event is not None:
            row = self._mapping_table.identify_row(event.y)
            if row:
                selection = (row,)
        if not selection:
            from tkinter import messagebox
            messagebox.showinfo("编辑键位", "先选择一个按钮，或双击表格中的按钮行。", parent=self._root)
            return
        button = selection[0]
        from .mapping_editor import MappingEditor
        if button.startswith("stick:"):
            direction = button.split(":", 1)[1]
            MappingEditor(self._root, f"摇杆 {direction}", self._config["mappings"]["stick_directions"][direction], lambda value: self._save_mapping("stick_directions", direction, value))
            return
        MappingEditor(self._root, button, self._config["mappings"]["buttons"][button], lambda value: self._save_button_mapping(button, value))

    def _bind_window_switch(self):
        from tkinter import messagebox
        button = self._switch_button.get()
        if button:
            try:
                self._save_button_mapping(button, {"action": "window_switch"})
                self._switch_status.configure(text=f"{button} 已设为窗口切换")
            except (ValueError, OSError) as error:
                messagebox.showerror("绑定失败", str(error), parent=self._root)

    def _center_window(self) -> None:
        """Center the window on screen."""
        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        x = (self._root.winfo_screenwidth() - w) // 2
        y = (self._root.winfo_screenheight() - h) // 2
        self._root.geometry(f"+{x}+{y}")

    def _start_drag(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event) -> None:
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    def _on_stick_toggle(self) -> None:
        """Handle stick mapping toggle."""
        enabled = self._stick_var.get()
        self._config["stick_enabled"] = enabled
        def apply():
            self._key_mapper._stick_enabled = enabled
            if not enabled:
                self._key_mapper.release_all()
        self._key_mapper.command_queue.put(apply)
        save_config(self._config)
        logger.info("Stick mapping %s", "enabled" if enabled else "disabled")

    def _on_keep_alive_toggle(self) -> None:
        """Handle keep-alive toggle."""
        enabled = self._keep_alive_var.get()
        self._config["keep_alive_enabled"] = enabled
        if self._keep_alive_manager:
            self._keep_alive_manager.set_enabled(enabled)
        save_config(self._config)
        logger.info("Keep-alive %s", "enabled" if enabled else "disabled")

    def _build_app_checkboxes(self) -> None:
        """Build/refresh app checkboxes from KNOWN_APPS."""
        # Clear existing
        for widget in self._app_frame.winfo_children():
            widget.destroy()
        self._app_vars.clear()

        # Get selected apps from config to know which are checked
        selected_apps = set(self._config.get("selected_apps", []))

        for i, (display_name, process_name) in enumerate(KNOWN_APPS.items()):
            var = ttk.BooleanVar(value=(process_name in selected_apps))
            self._app_vars[display_name] = var
            cb = ttk.Checkbutton(
                self._app_frame,
                text=f"  {display_name}",
                variable=var,
                command=self._on_app_toggle,
                bootstyle=INFO,
            )
            cb.grid(row=i, column=0, sticky="w", padx=(0, 8), pady=3)
            ttk.Button(self._app_frame, text="编辑", bootstyle="secondary-link", command=lambda n=display_name: self._app_editor(n)).grid(row=i, column=1)
            ttk.Button(self._app_frame, text="删除", bootstyle="danger-link", command=lambda n=display_name: self._delete_app(n)).grid(row=i, column=2)

    def refresh_apps(self) -> None:
        """Refresh app checkboxes (call after settings change)."""
        self._build_app_checkboxes()

    def _persist_apps(self, apps, selected):
        from .window_switcher import set_known_apps
        candidate = dict(self._config, known_apps=apps, selected_apps=selected)
        save_config(candidate)
        self._config.update(known_apps=apps, selected_apps=selected)
        set_known_apps(apps)
        self._window_cycler.app_names = selected
        self.refresh_apps()

    def _delete_app(self, name):
        apps = dict(KNOWN_APPS)
        process = apps.pop(name)
        selected = [p for p in self._config.get("selected_apps", []) if p != process]
        self._persist_apps(apps, selected)

    def _app_editor(self, name=None, process="", display_name=""):
        logger.info("UI: open app editor %s", name or "new")
        from tkinter import messagebox
        win = ttk.Toplevel(master=self._root)
        win.title("编辑应用" if name else "添加应用")
        win.geometry("430x210")
        display = ttk.StringVar(value=name or display_name)
        target = ttk.StringVar(value=KNOWN_APPS.get(name, process))
        for label, variable in (("显示名称", display), ("应用进程名" if sys.platform == "darwin" else "进程 / EXE", target)):
            ttk.Label(win, text=label).pack(anchor=W, padx=16, pady=4)
            ttk.Entry(win, textvariable=variable).pack(fill=X, padx=16)
        def save():
            title, proc = display.get().strip(), target.get().strip()
            if not title or not proc or (title != name and title in KNOWN_APPS):
                messagebox.showerror("应用信息", "请填写名称和进程名，显示名称不能重复。", parent=win)
                return
            apps = dict(KNOWN_APPS)
            old = apps.pop(name, None)
            apps[title] = proc
            selected = [proc if p == old else p for p in self._config.get("selected_apps", [])]
            if name is None and proc not in selected:
                selected.append(proc)
            try:
                self._persist_apps(apps, selected)
                win.destroy()
            except (OSError, ValueError) as error:
                messagebox.showerror("保存失败", str(error), parent=win)
        ttk.Button(win, text="保存", command=save, bootstyle="secondary-outline").pack(pady=12)
        from .dialogs import present_dialog
        present_dialog(win, self._root)

    def _scan_apps(self):
        logger.info("UI: scan running apps")
        from .window_switcher import running_apps
        from tkinter import messagebox
        try:
            apps = running_apps()
        except Exception as error:
            messagebox.showerror("扫描失败", str(error), parent=self._root)
            return
        win = ttk.Toplevel(master=self._root)
        win.title("选择运行应用 · 双击添加")
        win.geometry("460x420")
        table = ttk.Treeview(win, columns=("name", "process"), show="headings")
        table.heading("name", text="显示名称")
        table.heading("process", text="进程名")
        table.pack(fill=BOTH, expand=True, padx=12, pady=12)
        for name, process in sorted(apps.items()):
            table.insert("", "end", values=(name, process))
        def choose(event=None):
            if table.selection():
                name, process = table.item(table.selection()[0], "values")
                self._app_editor(process=process, display_name=name)
                win.destroy()
        table.bind("<Double-1>", choose)
        ttk.Button(win, text="添加选中应用", command=choose).pack(pady=8)
        from .dialogs import present_dialog
        present_dialog(win, self._root)

    def update_connection_mode(self, mode: str) -> None:
        """Update the displayed connection mode (e.g. after reconnection).

        Thread-safe: schedules the update on the tkinter main thread.
        """
        # Only the GUI thread calls Tk; polling publishes a pending update.
        self._pending_mode = mode

    def _on_app_toggle(self) -> None:
        """Handle app selection change."""
        selected = []
        for display_name, var in self._app_vars.items():
            if var.get():
                selected.append(KNOWN_APPS[display_name])
        self._window_cycler.app_names = selected
        # Persist selected app process names to config
        self._config["selected_apps"] = selected
        save_config(self._config)
        logger.info("Window switch targets: %s", selected)

    def _update_battery_display(self) -> None:
        """Read battery state and update the labels. Reschedules itself."""
        try:
            if self._battery_reader:
                states = self._battery_reader.get_state()
                for side, label in (("L", self._battery_label_l), ("R", self._battery_label_r)):
                    status, pct = states.get(side, ("unknown", -1))
                    text, style = self._format_battery(side, status, pct)
                    if pct < 0:
                        label.configure(text=text, style="Muted.TLabel")
                    else:
                        label.configure(text=text, bootstyle=style)
            # Reschedule
            if not self._stop_event.is_set():
                self._root.after(3000, self._update_battery_display)
        except Exception:
            # Widget may be destroyed during shutdown — ignore
            pass

    @staticmethod
    def _format_battery(side: str, status: str, pct: int) -> tuple[str, str]:
        """Return (display_text, bootstyle) for one Joy-Con side."""
        prefix = f"{side}:"
        if status == "unavailable" or status == "unknown":
            return (f"{prefix} 电量不可用", SECONDARY)
        if status == "disconnected" or pct < 0:
            return (f"{prefix} 未连接", SECONDARY)
        elif status == "charging":
            return (f"{prefix} 🔌 {pct}%", SUCCESS)
        elif pct <= 25:
            return (f"{prefix} 🪫 {pct}%", DANGER)
        elif pct <= 50:
            return (f"{prefix} {pct}%", WARNING)
        else:
            return (f"{prefix} {pct}%", SUCCESS)

    def _on_minimize_click(self) -> None:
        """Minimize to system tray."""
        self._root.withdraw()
        if self._on_minimize:
            self._on_minimize()

    def _open_settings(self) -> None:
        """Open the settings window."""
        logger.info("UI: open settings")
        from .settings_window import SettingsWindow
        SettingsWindow(
            self._root, self._key_mapper, self._config, self._window_cycler,
            main_window=self, mode=self._connection_mode,
        )

    def _on_close(self) -> None:
        """Handle window close — exit the program."""
        logger.info("Main window closed, stopping...")
        save_config(self._config)
        self._stop_event.set()
        self._root.destroy()

    @property
    def root(self) -> ttk.Window:
        """Get the tkinter root window."""
        return self._root

    def show(self) -> None:
        """Show the window (restore from minimized)."""
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def run(self) -> None:
        """Start the tkinter main loop (blocks)."""
        logger.info("GUI started")
        self._root.mainloop()
        logger.info("GUI stopped")
