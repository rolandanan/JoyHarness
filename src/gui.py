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
    BOTH, DANGER, INFO, LEFT, LIGHT, RIGHT, SECONDARY, SUCCESS, WARNING, X, W,
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
        self._stop_event = stop_event
        self._on_minimize = on_minimize
        self._battery_reader = battery_reader
        self._connection_mode = connection_mode
        self._keep_alive_manager = keep_alive_manager

        self._root = ttk.Window(
            title="JoyHarness · 工作台",
            themename=config.get("theme", "litera"),
            size=(1000, 900),
            resizable=(True, True),
        )
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
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

        self._configure_styles()
        self._build_ui()
        self._configure_styles()
        if self._frameless:
            self._setup_resize()
        self._center_window()

    def _build_ui(self) -> None:
        """Build the UI layout."""
        from ttkbootstrap import ScrolledFrame
        main = ScrolledFrame(self._root, auto_hide=True)
        main.pack(fill=BOTH, expand=True)
        header = ttk.Frame(main, padding=(24, 16))
        header.pack(fill=X)
        ttk.Label(header, text="JoyHarness", font=(_UI_FONT, 24, "bold")).pack(side=LEFT)
        ttk.Button(header, text="设置与校准", command=self._open_settings, bootstyle="primary").pack(side=RIGHT)
        ttk.Label(header, text="让手柄融入你的 Mac 工作流" if sys.platform == "darwin" else "让手柄融入你的工作流", font=(_UI_FONT, 12), style="Muted.TLabel").pack(side=LEFT, padx=18)
        overview = ttk.Frame(main)
        overview.pack(fill=X, padx=28, pady=12)
        status = ttk.Labelframe(overview, text="设备与配置", padding=16)
        status.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 16))
        control = ttk.Labelframe(overview, text="运行设置", padding=12)
        control.pack(side=RIGHT, fill=BOTH)
        self._device_status = ttk.Label(status, text="正在检测设备…", font=(_UI_FONT, 13, "bold"), wraplength=460)
        self._device_status.pack(anchor=W)
        self._profile_status = ttk.Label(status, text="", wraplength=440)
        self._profile_status.pack(anchor=W, pady=8)
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
            ttk.Checkbutton(options, text=label, variable=variable, command=command, bootstyle="success-round-toggle").pack(anchor=W, pady=4)
        self._theme_var = ttk.StringVar(value="深色" if self._config.get("theme") == "darkly" else "浅色")
        theme = ttk.Combobox(options, textvariable=self._theme_var, values=("浅色", "深色"), state="readonly", width=7)
        theme.pack(anchor=W, pady=4)
        theme.bind("<<ComboboxSelected>>", self._change_theme)
        permissions = ttk.Frame(control, padding=(0, 4))
        permissions.pack(fill=X)
        self._permission_label = ttk.Label(permissions, text="", wraplength=290, font=(_UI_FONT, 10))
        self._permission_label.pack(anchor=W)
        permission_links = ttk.Frame(permissions)
        permission_links.pack(fill=X, pady=(6, 0))
        if sys.platform == "darwin":
            from .app_platform.permission import open_permission_settings
            ttk.Button(permission_links, text="辅助功能", bootstyle="primary-outline", command=open_permission_settings).pack(side=RIGHT)
            ttk.Button(permission_links, text="输入监控", bootstyle="primary-outline", command=lambda: open_permission_settings("ListenEvent")).pack(side=RIGHT)
        targets = ttk.Labelframe(main, text="窗口切换目标应用", padding=14)
        targets.pack(fill=X, padx=28, pady=8)
        binding = ttk.Frame(targets)
        binding.pack(fill=X, pady=(0, 10))
        ttk.Label(binding, text="自定义切换按钮：").pack(side=LEFT)
        self._switch_button = ttk.StringVar(value="SR")
        self._switch_combo = ttk.Combobox(binding, textvariable=self._switch_button, values=tuple(self._config.get("mappings", {}).get("buttons", {})), state="readonly", width=9)
        self._switch_combo.pack(side=LEFT, padx=8)
        ttk.Button(binding, text="设为窗口切换", command=self._bind_window_switch, bootstyle="primary-outline").pack(side=LEFT)
        self._switch_status = ttk.Label(binding, text="当前：SR", style="Muted.TLabel")
        self._switch_status.pack(side=LEFT, padx=14)
        ttk.Label(targets, text="下方勾选目标应用 · 短按切换 · 长按选择 · 可给多个按钮绑定", style="Muted.TLabel").pack(anchor=W, pady=(0, 8))
        self._app_frame = ttk.Frame(targets)
        self._app_frame.pack(fill=X)
        self._build_app_checkboxes()
        mapping = ttk.Labelframe(main, text="当前按键工作流", padding=14)
        mapping.pack(fill=BOTH, expand=True, padx=28, pady=(8, 24))
        toolbar = ttk.Frame(mapping)
        toolbar.pack(fill=X, pady=(0, 10))
        ttk.Label(toolbar, text="双击任意一行即可修改动作和快捷键", style="Muted.TLabel").pack(side=LEFT)
        ttk.Button(toolbar, text="编辑选中键位", command=self._edit_selected, bootstyle="primary-outline").pack(side=RIGHT)
        self._mapping_table = ttk.Treeview(mapping, columns=("button", "action", "target"), show="headings", height=11, style="Workflow.Treeview", selectmode="browse")
        for name, title, width in (("button", "物理按钮", 120), ("action", "动作类型", 150), ("target", "快捷键 / 命令", 480)):
            self._mapping_table.heading(name, text=title)
            self._mapping_table.column(name, width=width, minwidth=80, anchor="center")
        self._mapping_table.pack(fill=BOTH, expand=True)
        self._mapping_table.bind("<Double-1>", self._edit_selected)
        self._root.after(300, self._refresh_status)
        if self._battery_reader:
            self._root.after(2000, self._update_battery_display)

    def _refresh_status(self):
        if self._stop_event.is_set():
            return
        from .constants import MODE_LABELS
        from .key_labels import action_label
        from .app_platform.permission import has_required_permissions, input_monitoring_status
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
                from .mapping_editor import ACTION_TITLES
                self._mapping_table.insert("", "end", iid=button, values=(button, ACTION_TITLES.get(value.get("action"), value.get("action")), action_label(value)))
            buttons = tuple(self._config.get("mappings", {}).get("buttons", {}))
            if buttons:
                self._mapping_table.selection_set(selection[0] if selection and selection[0] in buttons else buttons[0])
            self._switch_combo.configure(values=buttons)
            switches = [name for name, value in self._config.get("mappings", {}).get("buttons", {}).items() if value.get("action") == "window_switch"]
            self._switch_status.configure(text="当前：" + (" / ".join(switches) or "尚未绑定"))
            if self._switch_button.get() not in buttons:
                self._switch_button.set(next(iter(buttons), ""))
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
        value = "darkly" if self._theme_var.get() == "深色" else "litera"
        self._root.style.theme_use(value)
        self._config["theme"] = value
        self._configure_styles()
        save_config(self._config)

    def _configure_styles(self):
        from tkinter import font
        font.nametofont("TkDefaultFont").configure(family=_UI_FONT, size=12)
        font.nametofont("TkTextFont").configure(family=_UI_FONT, size=12)
        dark = self._config.get("theme") == "darkly"
        foreground = "#e5e7eb" if dark else "#26323e"
        muted = "#cbd5e1" if dark else "#52606d"
        style = self._root.style
        style.configure("TLabel", foreground=foreground, font=(_UI_FONT, 12))
        style.configure("Muted.TLabel", foreground=muted, font=(_UI_FONT, 12))
        style.configure("secondary.TLabel", foreground=muted)
        style.configure("Workflow.Treeview", rowheight=26, font=(_UI_FONT, 11))
        style.configure("Workflow.Treeview.Heading", font=(_UI_FONT, 12, "bold"), padding=(6, 6))

    def _save_button_mapping(self, button, value):
        import copy
        from .config_loader import validate_config
        mode = self._config.get("active_profile", "single_right")
        candidate = copy.deepcopy(self._config)
        candidate["profiles"][mode]["mappings"]["buttons"][button] = value
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
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 16), pady=3)

    def refresh_apps(self) -> None:
        """Refresh app checkboxes (call after settings change)."""
        self._build_app_checkboxes()

    def update_connection_mode(self, mode: str) -> None:
        """Update the displayed connection mode (e.g. after reconnection).

        Thread-safe: schedules the update on the tkinter main thread.
        """
        from .constants import MODE_LABELS
        self._connection_mode = mode
        mode_label = MODE_LABELS.get(mode, mode)

        def _do_update():
            self._root.title(f"JoyHarness [{mode_label}]")
            if self._frameless:
                for widget in self._root.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Label) and "JoyHarness" in str(child.cget("text")):
                                child.configure(text=f"  JoyHarness [{mode_label}]")
                                return

        self._root.after(0, _do_update)

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
