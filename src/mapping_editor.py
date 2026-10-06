"""Direct, discoverable action editor shared by the workbench."""
import copy
import json
import sys
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from .config_loader import _validate_mapping_entry

ACTION_TITLES = {"tap": "点击 tap", "hold": "保持 hold", "auto": "短按 / 长按 auto",
                 "combination": "组合快捷键", "sequence": "序列 sequence",
                 "window_switch": "窗口切换", "macro": "宏 macro", "exec": "执行命令"}


def parse_shortcut(text):
    aliases = {"⌘": "command", "⌥": "option", "⌃": "control", "⇧": "shift", "esc": "escape", "↵": "enter"}
    return [aliases.get(k.strip().lower(), k.strip().lower()) for k in text.replace(",", "+").split("+") if k.strip()]


def build_mapping(action, text, repeat=0, old=None):
    value = {"action": action}
    keys = parse_shortcut(text)
    if action in ("tap", "hold", "auto"):
        if len(keys) != 1:
            raise ValueError("此动作需要一个键；多个键请选择“组合快捷键”。")
        value["key"] = keys[0]
    elif action in ("combination", "sequence"):
        value["keys"] = keys
    elif action == "exec":
        value["command"] = json.loads(text) if text.strip().startswith("[") else text.strip()
    elif action == "macro":
        value = json.loads(text)
        value["action"] = "macro"
    if action in ("auto", "sequence"):
        value["repeat"] = int(repeat)
    if old and action == old.get("action") and "if_window" in old:
        value["if_window"] = old["if_window"]
    errors = _validate_mapping_entry("动作", value)
    if errors:
        raise ValueError("\n".join(errors))
    return value


class MappingEditor:
    def __init__(self, parent, button, mapping, on_save):
        self.mapping = copy.deepcopy(mapping)
        self.on_save = on_save
        self.win = ttk.Toplevel(master=parent)
        self.win.title(f"自定义 {button}")
        self.win.geometry("620x490")
        self.win.minsize(580, 440)
        self.win.transient(parent)
        self.win.grab_set()
        frame = ttk.Frame(self.win, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{button} · 自定义动作", font=("Helvetica", 20, "bold")).pack(anchor="w", pady=(0, 16))
        ttk.Label(frame, text="动作类型").pack(anchor="w", pady=6)
        self.action = ttk.StringVar(value=ACTION_TITLES[mapping.get("action", "tap")])
        action = ttk.Combobox(frame, textvariable=self.action, values=list(ACTION_TITLES.values()), state="readonly")
        action.pack(fill="x", pady=6)
        action.bind("<<ComboboxSelected>>", self._changed)
        ttk.Label(frame, text="目标快捷键 / 命令").pack(anchor="w", pady=(12, 6))
        self.editor = tk.Text(frame, height=3, font=("Helvetica", 13), wrap="word", relief="solid", borderwidth=1)
        self.editor.pack(fill="x")
        target = mapping.get("key", "+".join(mapping.get("keys", [])))
        if mapping.get("action") == "exec":
            target = mapping["command"] if isinstance(mapping["command"], str) else json.dumps(mapping["command"], ensure_ascii=False)
        elif mapping.get("action") == "macro":
            target = json.dumps(mapping, ensure_ascii=False)
        self.editor.insert("1.0", target)
        self.hint = ttk.Label(frame, text="", wraplength=560)
        self.hint.pack(anchor="w", pady=8)
        self.record = ttk.Button(frame, text="录入键盘快捷键", command=self._record, bootstyle="primary-outline")
        self.record.pack(anchor="w", pady=6)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="连发间隔（毫秒，0 为关闭）").pack(side="left")
        self.repeat = ttk.StringVar(value=str(mapping.get("repeat", 0)))
        self.repeat_entry = ttk.Entry(row, textvariable=self.repeat, width=8)
        self.repeat_entry.pack(side="left", padx=12)
        footer = ttk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(12, 0))
        ttk.Button(footer, text="保存并生效", command=self._save).pack(side="right")
        ttk.Button(footer, text="取消", command=self.win.destroy, bootstyle="secondary-outline").pack(side="right", padx=10)
        self._changed()
        self.win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.win.winfo_height()) // 2
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _action(self):
        return next(k for k, v in ACTION_TITLES.items() if v == self.action.get())

    def _changed(self, event=None):
        action = self._action()
        self.editor.configure(state="disabled" if action == "window_switch" else "normal")
        self.record.configure(state="normal" if action in ("tap", "hold", "auto", "combination", "sequence") else "disabled")
        self.repeat_entry.configure(state="normal" if action in ("auto", "sequence") else "disabled")
        hints = {"window_switch": "保存即可。短按切换窗口，长按打开选择器；目标应用在主界面勾选。",
                 "macro": "输入完整宏 JSON，可在设置页的“高级”编辑器查看与编辑步骤。",
                 "exec": "输入 Shell 命令或 JSON 参数数组，例如 [\"open\", \"-a\", \"Safari\"]。"}
        self.hint.configure(text=hints.get(action, "可以直接输入 command+c，或点击录入后按键盘快捷键。⌘ / ⌥ / ⌃ / ⇧ 也可输入。"))

    def _record(self):
        self.hint.configure(text="现在按下键盘快捷键；仅在此对话框录入。")
        self.win.focus_force()
        self.win.bind("<KeyPress>", self._record_event)

    def _record_event(self, event):
        key = event.keysym.lower()
        if key in ("shift_l", "shift_r", "control_l", "control_r", "alt_l", "alt_r", "meta_l", "meta_r", "super_l", "super_r"):
            return "break"
        keys = []
        if event.state & 0x4:
            keys.append("control")
        if sys.platform == "darwin":
            if event.state & 0x8:
                keys.append("command")
            if event.state & 0x10:
                keys.append("option")
        elif event.state & 0x8:
            keys.append("alt")
        if event.state & 0x1:
            keys.append("shift")
        keys.append({"return": "enter", "prior": "page_up", "next": "page_down"}.get(key, key))
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", "+".join(keys))
        if len(keys) > 1:
            self.action.set(ACTION_TITLES["combination"])
        self.win.unbind("<KeyPress>")
        self.hint.configure(text="快捷键已录入。点击保存后生效。")
        return "break"

    def _save(self):
        try:
            value = build_mapping(self._action(), self.editor.get("1.0", "end").strip(), self.repeat.get(), self.mapping)
            self.on_save(value)
        except (ValueError, TypeError, OSError) as error:
            messagebox.showerror("无法保存", str(error), parent=self.win)
            return
        self.win.destroy()
