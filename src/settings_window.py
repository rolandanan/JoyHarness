"""Chinese mapping editor and guided device calibration."""
import copy
import json
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap import ScrolledFrame
from .constants import VALID_ACTIONS, MAPPABLE_BUTTONS_BY_MODE, MODE_LABELS
from .config_loader import load_config, save_config, validate_config, backup_config, get_platform_config_path
from .device_profiles import button_indices, validate_devices
from .key_labels import action_label
from .window_switcher import KNOWN_APPS, set_known_apps


class SettingsWindow:
    def __init__(self, parent, key_mapper, config, window_cycler, main_window=None, mode="single_right"):
        self._key_mapper, self._config = key_mapper, config
        self._window_cycler, self._main_window, self._mode = window_cycler, main_window, mode
        self._draft = copy.deepcopy(config)
        self._win = ttk.Toplevel(parent)
        self._win.title("JoyHarness · 设置")
        self._win.geometry("900x740")
        self._win.minsize(760, 560)
        self._win.protocol("WM_DELETE_WINDOW", self._close)
        self._rows = {}
        self._app_rows = []
        self._build_ui()
        self._win.after(100, self._capture_poll)

    def _build_ui(self):
        top = ttk.Frame(self._win, padding=20)
        top.pack(fill="x")
        ttk.Label(top, text="设置你的工作流", font=("Helvetica", 22, "bold")).pack(anchor="w")
        ttk.Label(top, text=f"当前配置：{MODE_LABELS[self._mode]}  ·  ⌘ Command    ⌥ Option    ⌃ Control    ⇧ Shift").pack(anchor="w", pady=(8, 0))
        nb = ttk.Notebook(self._win)
        nb.pack(fill="both", expand=True, padx=20)
        tabs = [ttk.Frame(nb) for _ in range(3)]
        mapping, apps, calibration = [ScrolledFrame(tab, auto_hide=True) for tab in tabs]
        for widget in (mapping, apps, calibration):
            widget.pack(fill="both", expand=True)
        general = ttk.Frame(nb, padding=20)
        for widget, label in ((tabs[0], "按键映射"), (tabs[1], "切换目标"), (tabs[2], "设备校准"), (general, "配置与参数")):
            nb.add(widget, text=label)
        self._build_mapping(mapping)
        self._build_apps(apps)
        self._build_calibration(calibration)
        self._build_general(general)
        footer = ttk.Frame(self._win, padding=20)
        footer.pack(fill="x")
        ttk.Button(footer, text="恢复此模式默认", bootstyle="warning-outline", command=self._reset_defaults).pack(side="left")
        ttk.Button(footer, text="保存并应用", command=self._apply).pack(side="right")
        ttk.Button(footer, text="取消", bootstyle="secondary-outline", command=self._close).pack(side="right", padx=10)

    def _build_mapping(self, parent):
        ttk.Label(parent, text="物理按钮 → 动作 → 快捷键 / 命令", font=("Helvetica", 12, "bold")).pack(anchor="w", padx=16, pady=16)
        ttk.Label(parent, text="组合键用 + 分隔；exec 输入命令；macro 点“高级”编辑。连发间隔为毫秒，0 表示不连发。", wraplength=740).pack(anchor="w", padx=16, pady=(0, 10))
        mappings = self._draft["profiles"][self._mode]["mappings"]["buttons"]
        for name in MAPPABLE_BUTTONS_BY_MODE[self._mode]:
            mapping = mappings.get(name, {"action": "tap", "key": "enter"})
            row = ttk.Frame(parent, padding=(12, 10))
            row.pack(fill="x", padx=12, pady=3)
            ttk.Label(row, text=name, width=8, font=("Helvetica", 12, "bold")).pack(side="left")
            action = ttk.StringVar(value=mapping["action"])
            ttk.Combobox(row, textvariable=action, values=VALID_ACTIONS, state="readonly", width=14).pack(side="left", padx=6)
            target = mapping.get("key", "+".join(mapping.get("keys", [])))
            if mapping["action"] == "exec":
                command = mapping.get("command", "")
                target = command if isinstance(command, str) else json.dumps(command, ensure_ascii=False)
            key = ttk.StringVar(value=target)
            ttk.Entry(row, textvariable=key, width=24).pack(side="left", padx=6, fill="x", expand=True)
            repeat = ttk.StringVar(value=str(mapping.get("repeat", 0)))
            ttk.Entry(row, textvariable=repeat, width=6).pack(side="left", padx=6)
            ttk.Button(row, text="高级", bootstyle="secondary-outline", command=lambda n=name: self._advanced(n)).pack(side="left")
            self._rows[name] = {"action": action, "key": key, "repeat": repeat, "mapping": copy.deepcopy(mapping)}
            ttk.Label(parent, text=action_label(mapping), bootstyle="secondary").pack(anchor="w", padx=36, pady=(0, 4))

    def _advanced(self, name):
        win = ttk.Toplevel(self._win)
        win.title(f"{name} · 完整动作 JSON")
        win.geometry("640x450")
        editor = tk.Text(win, font=("Menlo", 12))
        editor.pack(fill="both", expand=True, padx=16, pady=16)
        editor.insert("1.0", json.dumps(self._rows[name]["mapping"], ensure_ascii=False, indent=2))
        def apply():
            try:
                value = json.loads(editor.get("1.0", "end"))
                from .config_loader import _validate_mapping_entry
                errors = _validate_mapping_entry(name, value)
                if errors:
                    raise ValueError("\n".join(errors))
                row = self._rows[name]
                row["mapping"] = value
                row["action"].set(value["action"])
                row["repeat"].set(str(value.get("repeat", 0)))
                target = value.get("key", "+".join(value.get("keys", [])))
                if value["action"] == "exec":
                    target = value["command"] if isinstance(value["command"], str) else json.dumps(value["command"], ensure_ascii=False)
                row["key"].set(target)
                win.destroy()
            except (ValueError, TypeError) as error:
                messagebox.showerror("动作错误", str(error), parent=win)
        ttk.Button(win, text="应用动作", command=apply).pack(pady=(0, 16))

    def _build_apps(self, parent):
        self._apps_frame = parent
        ttk.Label(parent, text="窗口切换目标应用", font=("Helvetica", 14, "bold")).pack(anchor="w", padx=16, pady=16)
        ttk.Label(parent, text="应用名称                  " + ("应用进程名" if sys.platform == "darwin" else "进程 / EXE")).pack(anchor="w", padx=16)
        for name, process in self._draft.get("known_apps", KNOWN_APPS).items():
            self._add_app(name, process)
        ttk.Button(parent, text="添加应用", bootstyle="secondary-outline", command=self._add_app).pack(anchor="w", padx=16, pady=16)

    def _add_app(self, name="", process=""):
        frame = ttk.Frame(self._apps_frame, padding=10)
        frame.pack(fill="x", padx=10)
        name_var, process_var = ttk.StringVar(value=name), ttk.StringVar(value=process)
        ttk.Entry(frame, textvariable=name_var, width=24).pack(side="left", padx=6)
        ttk.Entry(frame, textvariable=process_var, width=32).pack(side="left", padx=6)
        ttk.Button(frame, text="移除", bootstyle="danger-outline", command=frame.destroy).pack(side="left", padx=6)
        self._app_rows.append((frame, name_var, process_var))

    def _build_calibration(self, parent):
        ttk.Label(parent, text="选择设备，再点按钮名称并按下实体键", font=("Helvetica", 14, "bold")).pack(anchor="w", padx=16, pady=16)
        ttk.Label(parent, text="录入期间暂停快捷键输出；相同索引会与原按钮交换。保存后按平台、GUID 和设备名称持久化。", wraplength=740).pack(anchor="w", padx=16)
        self._devices = self._config.get("runtime_devices", [])
        self._device_var = ttk.StringVar(value=self._devices[0]["identity"] if self._devices else "")
        ttk.Combobox(parent, textvariable=self._device_var, values=[d["identity"] for d in self._devices], state="readonly", width=70).pack(fill="x", padx=16, pady=16)
        self._capture_label = ttk.Label(parent, text="尚未录入；现有已验证映射保持有效。")
        self._capture_label.pack(anchor="w", padx=16, pady=8)
        controls = ttk.Frame(parent, padding=16)
        controls.pack(fill="x")
        names = sorted(set(n for d in self._devices for n in MAPPABLE_BUTTONS_BY_MODE[d["mode"]]))
        for i, name in enumerate(names):
            ttk.Button(controls, text=name, bootstyle="secondary-outline", command=lambda n=name: self._capture(n)).grid(row=i // 5, column=i % 5, padx=5, pady=5, sticky="ew")
        for i in range(5):
            controls.columnconfigure(i, weight=1)
        ttk.Button(parent, text="取消录入", bootstyle="secondary-outline", command=self._cancel_capture).pack(anchor="w", padx=16, pady=16)
        self._axis_x, self._axis_y = ttk.StringVar(value="1"), ttk.StringVar(value="0")
        axes = ttk.Frame(parent, padding=16)
        axes.pack(fill="x")
        ttk.Label(axes, text="摇杆轴 X / Y（已知设备无需更改）").pack(side="left")
        ttk.Entry(axes, textvariable=self._axis_x, width=5).pack(side="left", padx=8)
        ttk.Entry(axes, textvariable=self._axis_y, width=5).pack(side="left", padx=8)
        ttk.Button(axes, text="保存轴设置", command=self._save_axes).pack(side="left")

    def _save_axes(self):
        identity = self._device_var.get()
        try:
            x, y = int(self._axis_x.get()), int(self._axis_y.get())
            if not identity or min(x, y) < 0 or x == y:
                raise ValueError("请选择设备并填写不同的非负轴索引")
            self._draft.setdefault("device_profiles", {}).setdefault(identity, {})["axes"] = {"x": x, "y": y}
            self._capture_label.configure(text="轴设置已暂存，保存后生效。")
        except ValueError as error:
            messagebox.showerror("轴设置", str(error), parent=self._win)

    def _capture(self, name):
        identity = self._device_var.get()
        device = next((d for d in self._devices if d["identity"] == identity), None)
        if not device or name not in MAPPABLE_BUTTONS_BY_MODE[device["mode"]]:
            messagebox.showinfo("校准", "请选择支持该按钮的已连接设备。", parent=self._win)
            return
        self._key_mapper.command_queue.put(self._key_mapper.release_all)
        self._key_mapper.capture_request = (identity, device["mode"], name)
        self._capture_label.configure(text=f"请按下 {name}，可随时取消。")

    def _cancel_capture(self):
        self._key_mapper.capture_request = None
        self._capture_label.configure(text="录入已取消。")

    def _capture_poll(self):
        if not self._win.winfo_exists():
            return
        try:
            while True:
                (identity, mode, name), index = self._key_mapper.capture_events.get_nowait()
                indices = button_indices(self._draft, mode, identity)
                old_index = indices[name]
                for other in indices:
                    if other != name and indices[other] == index:
                        indices[other] = old_index
                indices[name] = index
                self._draft.setdefault("device_profiles", {}).setdefault(identity, {}).setdefault("buttons", {})[mode] = indices
                self._capture_label.configure(text=f"已识别 {name} → BTN {index}；保存后生效。")
        except queue.Empty:
            pass
        self._win.after(100, self._capture_poll)

    def _build_general(self, parent):
        self._params = {}
        for field, label, default in (("long_press_threshold", "长按阈值（秒）", .25), ("switch_scroll_interval", "长按窗口选择速度（毫秒）", 400), ("deadzone", "摇杆死区（0–0.99）", .2)):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=8)
            ttk.Label(row, text=label, width=34).pack(side="left")
            var = ttk.StringVar(value=str(self._draft.get(field, default)))
            ttk.Entry(row, textvariable=var, width=12).pack(side="left")
            self._params[field] = var
        self._stick_mode = ttk.StringVar(value=self._draft.get("stick_mode", "4dir"))
        ttk.Combobox(parent, textvariable=self._stick_mode, values=("4dir", "8dir"), state="readonly", width=12).pack(anchor="w", pady=8)
        for label, command in (("导入配置", self._import), ("导出当前配置", self._export), ("备份已保存配置", self._backup)):
            ttk.Button(parent, text=label, bootstyle="secondary-outline", command=command).pack(anchor="w", pady=8)

    def _collect(self):
        candidate = copy.deepcopy(self._draft)
        buttons = {}
        for name, row in self._rows.items():
            action, key = row["action"].get(), row["key"].get().strip()
            value = copy.deepcopy(row["mapping"]) if action == row["mapping"].get("action") else {"action": action}
            value["action"] = action
            if action in ("tap", "hold", "auto"):
                value["key"] = key
            elif action in ("combination", "sequence"):
                value["keys"] = [k.strip() for k in key.replace(",", "+").split("+") if k.strip()]
            elif action == "exec":
                value["command"] = json.loads(key) if key.startswith("[") else key
            if action in ("auto", "sequence"):
                value["repeat"] = int(row["repeat"].get())
            buttons[name] = value
        candidate["profiles"][self._mode]["mappings"]["buttons"] = buttons
        candidate["mappings"] = copy.deepcopy(candidate["profiles"][self._mode]["mappings"])
        apps = {}
        for frame, name, process in self._app_rows:
            if frame.winfo_exists():
                if not name.get().strip() or not process.get().strip():
                    raise ValueError("应用名称和进程名均不能为空")
                apps[name.get().strip()] = process.get().strip()
        candidate["known_apps"] = apps
        candidate["selected_apps"] = [p for p in candidate.get("selected_apps", []) if p in apps.values()]
        for field, var in self._params.items():
            candidate[field] = float(var.get())
        candidate["stick_mode"] = self._stick_mode.get()
        errors = validate_config(candidate) + validate_devices(candidate.get("device_profiles", {}))
        if errors:
            raise ValueError("\n".join(errors))
        return candidate

    def _apply(self):
        try:
            candidate = self._collect()
            save_config(candidate)
        except (ValueError, TypeError, OSError) as error:
            messagebox.showerror("配置错误", str(error), parent=self._win)
            return
        def apply():
            runtime = {k: self._config[k] for k in ("runtime_devices", "device_identity") if k in self._config}
            self._config.clear()
            self._config.update(candidate)
            self._config.update(runtime)
            set_known_apps(candidate["known_apps"])
            self._window_cycler.app_names = candidate["selected_apps"]
        self._key_mapper.command_queue.put(apply)
        if self._main_window:
            self._main_window.root.after(200, self._main_window.refresh_apps)
        self._close()

    def _reset_defaults(self):
        if not messagebox.askyesno("恢复默认", "仅暂存当前模式默认映射，保存前不会生效。", parent=self._win):
            return
        from .config_loader import merge_with_defaults
        from .constants import DEFAULT_CONFIGS
        defaults = DEFAULT_CONFIGS[self._mode]["mappings"]
        if sys.platform == "darwin":
            path = __import__("pathlib").Path(__file__).resolve().parent.parent / "config/user-macos.json"
            defaults = merge_with_defaults(json.loads(path.read_text()))["profiles"][self._mode]["mappings"]
        self._draft["profiles"][self._mode]["mappings"] = copy.deepcopy(defaults)
        self._rebuild()

    def _rebuild(self):
        self._rows.clear()
        self._app_rows.clear()
        for child in self._win.winfo_children():
            child.destroy()
        self._build_ui()

    def _import(self):
        path = filedialog.askopenfilename(parent=self._win, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self._draft = load_config(path)
            self._draft["_save_path"] = self._config.get("_save_path", __import__("src.config_loader", fromlist=["USER_CONFIG_PATH"]).USER_CONFIG_PATH)
            self._draft["active_profile"] = self._mode
            self._rebuild()
        except (ValueError, OSError, TypeError, AttributeError) as error:
            messagebox.showerror("导入失败", str(error), parent=self._win)

    def _export(self):
        try:
            candidate = self._collect()
            path = filedialog.asksaveasfilename(parent=self._win, defaultextension=".json", filetypes=[("JSON", "*.json")])
            if path:
                save_config(candidate, path)
        except (ValueError, OSError) as error:
            messagebox.showerror("导出失败", str(error), parent=self._win)

    def _backup(self):
        try:
            path = backup_config(get_platform_config_path())
            messagebox.showinfo("备份完成", str(path), parent=self._win)
        except OSError as error:
            messagebox.showerror("备份失败", str(error), parent=self._win)

    def _close(self):
        self._key_mapper.capture_request = None
        self._win.destroy()
