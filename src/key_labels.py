"""Display symbols without changing stored backend key names."""
SYMBOLS = {"command": "⌘", "cmd": "⌘", "cmd_r": "⌘", "option": "⌥", "alt": "⌥", "alt_r": "⌥", "control": "⌃", "ctrl": "⌃", "shift": "⇧", "enter": "↵", "escape": "Esc", "up": "↑", "down": "↓", "left": "←", "right": "→"}


def action_label(mapping):
    action = mapping.get("action", "")
    if action == "window_switch":
        return "短按切换 · 长按选择"
    if action == "exec":
        command = mapping.get("command", "")
        return command if isinstance(command, str) else " ".join(command)
    if action == "macro":
        return f"{len(mapping.get('steps', []))} 步宏"
    keys = mapping.get("keys", [mapping.get("key", "")])
    return " + ".join(SYMBOLS.get(k.lower(), k.upper() if len(k) == 1 else k) for k in keys)
