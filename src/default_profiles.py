"""Default keyboard actions, independent of physical device indices."""
from .hardware_defaults import DEFAULT_DEADZONE, POLL_INTERVAL

# === Default Key Mapping (used when no config file is loaded) ===
DEFAULT_MAPPINGS: dict = {
    "buttons": {
        "A":      {"action": "tap", "key": "enter"},
        "B":      {"action": "sequence", "keys": ["shift", "tab"]},
        "X":      {"action": "auto", "key": "f2"},
        "Y":      {"action": "sequence", "keys": ["alt", "tab"], "repeat": 500},
        "R":      {"action": "window_switch"},
        "ZR":     {
            "action": "macro",
            "if_window": "code.exe",
            "steps": [
                {"type": "combination", "keys": ["ctrl", "shift", "p"]},
                {"type": "delay", "ms": 100},
                {"type": "type", "text": "Claude Code: Focus input"},
                {"type": "delay", "ms": 100},
                {"type": "tap", "key": "enter"},
            ],
        },
        "Plus":   {"action": "combination", "keys": ["ctrl", "s"]},
        "Home":   {"action": "tap", "key": "windows"},
        "RStick": {"action": "tap", "key": "tab"},
        "SL":     {"action": "hold", "key": "alt"},
        "SR":     {"action": "window_switch"},
    },
    "stick_directions": {
        "up":    {"action": "auto", "key": "up", "repeat": 100},
        "down":  {"action": "auto", "key": "down", "repeat": 100},
        "left":  {"action": "auto", "key": "left", "repeat": 100},
        "right": {"action": "auto", "key": "right", "repeat": 100},
    },
}

DEFAULT_MAPPINGS_LEFT: dict = {
    "buttons": {
        "A":       {"action": "tap", "key": "enter"},
        "B":       {"action": "tap", "key": "escape"},
        "X":       {"action": "tap", "key": "backspace"},
        "Y":       {"action": "sequence", "keys": ["alt", "tab"], "repeat": 500},
        "L":       {"action": "window_switch"},
        "ZL":      {"action": "hold", "key": "ctrl"},
        "Minus":   {"action": "combination", "keys": ["ctrl", "s"]},
        "Capture": {"action": "tap", "key": "print_screen"},
        "LStick":  {"action": "tap", "key": "tab"},
        "SL":      {"action": "hold", "key": "shift"},
        "SR":      {"action": "window_switch"},
    },
    "stick_directions": {
        "up":    {"action": "tap", "key": "up"},
        "down":  {"action": "tap", "key": "down"},
        "left":  {"action": "tap", "key": "left"},
        "right": {"action": "tap", "key": "right"},
    },
}

DEFAULT_MAPPINGS_DUAL: dict = {
    "buttons": {
        "A":       {"action": "tap", "key": "enter"},
        "B":       {"action": "sequence", "keys": ["shift", "tab"]},
        "X":       {"action": "auto", "key": "f2"},
        "Y":       {"action": "sequence", "keys": ["alt", "tab"], "repeat": 500},
        "R":       {"action": "window_switch"},
        "ZR":     {
            "action": "macro",
            "if_window": "code.exe",
            "steps": [
                {"type": "combination", "keys": ["ctrl", "shift", "p"]},
                {"type": "delay", "ms": 100},
                {"type": "type", "text": "Claude Code: Focus input"},
                {"type": "delay", "ms": 100},
                {"type": "tap", "key": "enter"},
            ],
        },
        "L":       {"action": "hold", "key": "ctrl"},
        "ZL":      {"action": "hold", "key": "shift"},
        "Plus":    {"action": "combination", "keys": ["ctrl", "s"]},
        "Minus":   {"action": "tap", "key": "escape"},
        "Home":    {"action": "tap", "key": "windows"},
        "Capture": {"action": "tap", "key": "print_screen"},
        "RStick":  {"action": "tap", "key": "tab"},
        "LStick":  {"action": "tap", "key": "enter"},
        "SL_L":    {"action": "hold", "key": "alt"},
        "SR_L":    {"action": "window_switch"},
        "SL_R":    {"action": "hold", "key": "alt"},
        "SR_R":    {"action": "window_switch"},
    },
    "stick_directions": {
        "up":    {"action": "tap", "key": "up"},
        "down":  {"action": "tap", "key": "down"},
        "left":  {"action": "tap", "key": "left"},
        "right": {"action": "tap", "key": "right"},
    },
}

DEFAULT_CONFIG: dict = {
    "version": "1.0",
    "description": "Default Joy-Con R to keyboard mapping",
    "deadzone": DEFAULT_DEADZONE,
    "poll_interval": POLL_INTERVAL,
    "stick_mode": "4dir",
    "stick_enabled": True,
    "keep_alive_enabled": True,
    "mappings": DEFAULT_MAPPINGS,
}

DEFAULT_CONFIG_LEFT: dict = {
    "version": "1.0",
    "description": "Default Joy-Con L to keyboard mapping",
    "deadzone": DEFAULT_DEADZONE,
    "poll_interval": POLL_INTERVAL,
    "stick_mode": "4dir",
    "stick_enabled": True,
    "keep_alive_enabled": True,
    "mappings": DEFAULT_MAPPINGS_LEFT,
}

DEFAULT_CONFIG_DUAL: dict = {
    "version": "1.0",
    "description": "Default Joy-Con L+R to keyboard mapping",
    "deadzone": DEFAULT_DEADZONE,
    "poll_interval": POLL_INTERVAL,
    "stick_mode": "4dir",
    "stick_enabled": True,
    "keep_alive_enabled": True,
    "mappings": DEFAULT_MAPPINGS_DUAL,
}

DEFAULT_CONFIGS: dict[str, dict] = {
    "single_right": DEFAULT_CONFIG,
    "single_left": DEFAULT_CONFIG_LEFT,
    "dual": DEFAULT_CONFIG_DUAL,
}
