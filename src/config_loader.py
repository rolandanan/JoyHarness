"""Configuration loading, validation, saving, and default merging.

Loads JSON config files, validates key names and action types,
merges user config with built-in defaults, and saves config to disk.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

from .constants import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIGS,
    VALID_ACTIONS,
    BUTTON_NAMES,
    BUTTON_NAMES_BY_MODE,
    STICK_DIRECTIONS,
)

logger = logging.getLogger(__name__)


_BUNDLED_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_CONFIG_DIR = _BUNDLED_CONFIG_DIR
if getattr(sys, "frozen", False):
    _CONFIG_DIR = (Path.home() / "Library/Application Support/JoyHarness" if sys.platform == "darwin"
                   else Path(os.environ.get("APPDATA", str(Path.home()))) / "JoyHarness")
USER_CONFIG_PATH = str(_CONFIG_DIR / "user.json")


def get_platform_config_path() -> str | None:
    """Return the best config file path for the current platform.

    Priority:
    1. user.json (always preferred if it exists)
    2. user-macos.json (macOS) or user-windows.json (Windows)
    """
    import sys
    # Source and packaged launches should reopen the same saved workflow.
    shared_dir = (Path.home() / "Library/Application Support/JoyHarness" if sys.platform == "darwin"
                  else Path(os.environ.get("APPDATA", str(Path.home()))) / "JoyHarness")
    shared = shared_dir / "user.json"
    if shared.exists():
        return str(shared)
    user = _CONFIG_DIR / "user.json"
    if user.exists():
        return str(user)
    if sys.platform == "darwin":
        plat = _BUNDLED_CONFIG_DIR / "user-macos.json"
    else:
        plat = _BUNDLED_CONFIG_DIR / "user-windows.json"
    if plat.exists():
        return str(plat)
    return None


def load_config(path: str | None = None) -> dict:
    """Load configuration from a JSON file, or return built-in defaults.

    Args:
        path: Path to JSON config file. None uses built-in defaults.

    Returns:
        Complete configuration dict with all fields populated.

    Raises:
        FileNotFoundError: Config file path specified but doesn't exist.
        json.JSONDecodeError: Config file contains invalid JSON.
        ValueError: Config file contains invalid mappings.
    """
    if path is None:
        logger.info("Using built-in default configuration")
        return copy.deepcopy(DEFAULT_CONFIG)

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        user_config = json.load(f)
    if not isinstance(user_config, dict):
        raise ValueError("配置根节点必须为对象")
    _check_structure(user_config)

    logger.info("Loaded config from: %s", config_path)
    merged = merge_with_defaults(user_config)
    errors = validate_config(merged)

    if errors:
        error_msg = "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)
    # Public presets are read-only templates, including source launches.
    merged["_save_path"] = USER_CONFIG_PATH if config_path.parent == _BUNDLED_CONFIG_DIR and config_path.name != "user.json" else str(config_path)
    return merged


def _check_structure(config):
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles 必须为对象")
    containers = [config]
    for mode, profile in profiles.items():
        if mode not in DEFAULT_CONFIGS or not isinstance(profile, dict):
            raise ValueError(f"无效 profile: {mode}")
        containers.append(profile)
    for container in containers:
        mappings = container.get("mappings", {})
        if not isinstance(mappings, dict) or any(not isinstance(mappings.get(key, {}), dict) for key in ("buttons", "stick_directions")):
            raise ValueError("mappings/buttons/stick_directions 必须为对象")
    if "active_profile" in config and config["active_profile"] not in DEFAULT_CONFIGS:
        raise ValueError("无效 active_profile")
    if not isinstance(config.get("known_apps", {}), dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in config.get("known_apps", {}).items()):
        raise ValueError("known_apps 必须为名称与进程名对象")
    if not isinstance(config.get("selected_apps", []), list) or not all(isinstance(v, str) for v in config.get("selected_apps", [])):
        raise ValueError("selected_apps 必须为进程名列表")


def merge_with_defaults(user_config: dict) -> dict:
    """Merge user config into defaults. User values override defaults.

    Deep-merges the mappings section: user-defined buttons/directions
    override defaults, unspecified ones are kept from defaults.

    Supports both old format (top-level mappings) and new format (profiles).
    Old format is automatically migrated to profiles.single_right.
    """
    result = copy.deepcopy(DEFAULT_CONFIG)

    # Override top-level settings
    for key in ("version", "description", "deadzone", "poll_interval", "stick_mode", "stick_enabled", "keep_alive_enabled", "device_profiles", "long_press_threshold", "axis_x", "axis_y", "theme", "stick_repeat_delay", "right_stick_invert_x", "right_stick_invert_y"):
        if key in user_config:
            result[key] = user_config[key]

    # Override switch_scroll_interval
    if "switch_scroll_interval" in user_config:
        result["switch_scroll_interval"] = user_config["switch_scroll_interval"]

    # Preserve known_apps from user config (not in DEFAULT_CONFIG)
    if "known_apps" in user_config:
        result["known_apps"] = user_config["known_apps"]

    # Preserve selected_apps from user config (not in DEFAULT_CONFIG)
    if "selected_apps" in user_config:
        result["selected_apps"] = user_config["selected_apps"]

    # Handle profiles format (new) or old top-level mappings format
    if "profiles" in user_config:
        # New format: merge each profile with its mode-specific defaults
        result["profiles"] = {}
        for mode in ("single_right", "single_left", "dual"):
            default_cfg = DEFAULT_CONFIGS.get(mode, DEFAULT_CONFIG)
            default_mappings = default_cfg["mappings"]
            result["profiles"][mode] = {"mappings": copy.deepcopy(default_mappings)}

            user_profile = user_config["profiles"].get(mode, {})
            user_mappings = user_profile.get("mappings", {})
            if "buttons" in user_mappings:
                result["profiles"][mode]["mappings"]["buttons"].update(user_mappings["buttons"])
            if "stick_directions" in user_mappings:
                result["profiles"][mode]["mappings"]["stick_directions"].update(
                    user_mappings["stick_directions"]
                )

        # Keep top-level mappings in sync with active_profile (for backward compat with code that reads config["mappings"])
        active_profile = user_config.get("active_profile", "single_right")
        result["active_profile"] = active_profile
        result["mappings"] = copy.deepcopy(
            result["profiles"].get(active_profile, result["profiles"]["single_right"])["mappings"]
        )
    else:
        # Old format: migrate top-level mappings into profiles.single_right
        user_buttons = {}
        user_stick = {}
        if "mappings" in user_config:
            user_buttons = user_config["mappings"].get("buttons", {})
            user_stick = user_config["mappings"].get("stick_directions", {})

        # Build merged single_right profile
        single_right_mappings = {
            "buttons": {**DEFAULT_CONFIG["mappings"]["buttons"], **user_buttons},
            "stick_directions": {**DEFAULT_CONFIG["mappings"]["stick_directions"], **user_stick},
        }

        # Build full profiles dict with defaults for each mode
        result["profiles"] = {}
        for mode in ("single_right", "single_left", "dual"):
            default_cfg = DEFAULT_CONFIGS.get(mode, DEFAULT_CONFIG)
            result["profiles"][mode] = {
                "mappings": copy.deepcopy(default_cfg["mappings"])
            }
        # Override single_right with user's data
        result["profiles"]["single_right"]["mappings"] = single_right_mappings

        result["active_profile"] = "single_right"
        result["mappings"] = single_right_mappings

    return result


def get_profile(config: dict, mode: str) -> dict:
    """Get the mapping profile dict for the given connection mode.

    Returns a dict with a 'mappings' key. Falls back to single_right if
    the mode profile doesn't exist.
    """
    profiles = config.get("profiles", {})
    return profiles.get(mode, profiles.get("single_right", {}))


def validate_config(config: dict) -> list[str]:
    """Validate configuration and return list of error strings.

    Empty list means valid configuration.

    Checks:
    - Deadzone is within [0.0, 0.99]
    - Stick mode is "4dir" or "8dir"
    - Every action type is valid
    - Every key name is recognized by the keyboard library
    - Button names are known Joy-Con buttons
    - Stick direction names are valid
    - Validates all profiles if present
    """
    errors: list[str] = []
    try:
        _check_structure(config)
    except ValueError as error:
        return [str(error)]
    from .device_profiles import validate_devices
    errors.extend(validate_devices(config.get("device_profiles", {})))
    for field, default in (("long_press_threshold", .25), ("switch_scroll_interval", 400)):
        value = config.get(field, default)
        if type(value) not in (int, float) or not 0 < value <= 10000:
            errors.append(f"{field} 必须为正数")

    # Top-level validation
    delay = config.get("stick_repeat_delay", 400)
    if type(delay) not in (int, float) or not 0 <= delay <= 10000:
        errors.append("stick_repeat_delay 必须为 0–10000 毫秒")
    for field in ("right_stick_invert_x", "right_stick_invert_y"):
        if type(config.get(field, False)) is not bool:
            errors.append(f"{field} 必须为布尔值")
    deadzone = config.get("deadzone", 0.15)
    if not isinstance(deadzone, (int, float)) or not (0.0 <= deadzone < 1.0):
        errors.append(f"deadzone must be between 0.0 and 0.99, got {deadzone}")

    stick_mode = config.get("stick_mode", "4dir")
    if stick_mode not in ("4dir", "8dir"):
        errors.append(f"stick_mode must be '4dir' or '8dir', got '{stick_mode}'")

    poll_interval = config.get("poll_interval", 0.01)
    if not isinstance(poll_interval, (int, float)) or poll_interval <= 0:
        errors.append(f"poll_interval must be a positive number, got {poll_interval}")

    # Validate profiles (new format)
    profiles = config.get("profiles")
    if profiles:
        for mode, profile in profiles.items():
            btn_names = BUTTON_NAMES_BY_MODE.get(mode, BUTTON_NAMES)
            mappings = profile.get("mappings", {})
            for btn_name, mapping in mappings.get("buttons", {}).items():
                if btn_name not in btn_names.values():
                    errors.append(f"[{mode}] Unknown button name: '{btn_name}'")
                    continue
                errors.extend(_validate_mapping_entry(f"[{mode}] {btn_name}", mapping))
            for dir_name, mapping in mappings.get("stick_directions", {}).items():
                if dir_name not in STICK_DIRECTIONS:
                    errors.append(f"[{mode}] Unknown stick direction: '{dir_name}'")
                    continue
                errors.extend(_validate_mapping_entry(f"[{mode}] {dir_name}", mapping))
    else:
        # Old format: validate top-level mappings against all known button names
        all_button_names = set()
        for names in BUTTON_NAMES_BY_MODE.values():
            all_button_names.update(names.values())
        mappings = config.get("mappings", {})
        for btn_name, mapping in mappings.get("buttons", {}).items():
            if btn_name not in all_button_names:
                errors.append(f"Unknown button name: '{btn_name}'")
                continue
            errors.extend(_validate_mapping_entry(btn_name, mapping))
        for dir_name, mapping in mappings.get("stick_directions", {}).items():
            if dir_name not in STICK_DIRECTIONS:
                errors.append(f"Unknown stick direction: '{dir_name}'")
                continue
            errors.extend(_validate_mapping_entry(dir_name, mapping))

    return errors


def _validate_mapping_entry(name: str, mapping: dict) -> list[str]:
    """Validate a single mapping entry (button or stick direction)."""
    errors: list[str] = []

    if not isinstance(mapping, dict):
        errors.append(f"'{name}' mapping must be a dict, got {type(mapping).__name__}")
        return errors

    action = mapping.get("action")
    if action not in VALID_ACTIONS:
        errors.append(f"'{name}' has invalid action '{action}', must be one of {VALID_ACTIONS}")
        return errors

    repeat = mapping.get("repeat", 0)
    if type(repeat) not in (int, float) or repeat < 0:
        errors.append(f"'{name}' repeat 必须为非负数")
    if action in ("tap", "hold", "auto"):
        key = mapping.get("key")
        if not isinstance(key, str):
            errors.append(f"'{name}' action '{action}' requires a 'key' string")
        elif not _is_valid_key(key):
            errors.append(f"'{name}' has invalid key name: '{key}'")

    elif action in ("combination", "sequence"):
        keys = mapping.get("keys")
        if not isinstance(keys, list) or len(keys) == 0:
            errors.append(f"'{name}' {action} action requires a non-empty 'keys' list")
        else:
            for key in keys:
                if not isinstance(key, str):
                    errors.append(f"'{name}' {action} keys must be strings")
                elif not _is_valid_key(key):
                    errors.append(f"'{name}' has invalid key name in combination: '{key}'")

    elif action == "exec":
        command = mapping.get("command")
        if not (isinstance(command, str) and command.strip() or isinstance(command, list) and command and all(isinstance(c, str) and c for c in command)):
            errors.append(f"'{name}' exec 需要命令字符串或参数列表")
    elif action == "macro":
        steps = mapping.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"'{name}' macro 需要非空 steps")
        else:
            for step in steps:
                if not isinstance(step, dict):
                    errors.append(f"'{name}' 无效宏步骤")
                elif step.get("type") in ("tap", "hold", "release"):
                    errors.extend(_validate_mapping_entry(name, {"action": "tap", "key": step.get("key")}))
                elif step.get("type") == "combination":
                    errors.extend(_validate_mapping_entry(name, {"action": "combination", "keys": step.get("keys")}))
                elif step.get("type") == "delay":
                    if type(step.get("ms")) not in (int, float) or not 0 <= step["ms"] <= 60000:
                        errors.append(f"'{name}' 无效延时")
                elif step.get("type") == "type":
                    if not isinstance(step.get("text"), str):
                        errors.append(f"'{name}' 无效文本")
                else:
                    errors.append(f"'{name}' 未知宏步骤")
    return errors


def _is_valid_key(key_name: str) -> bool:
    """Check if a key name is recognized by the keyboard backend."""
    from .keyboard_output import is_valid_key
    return is_valid_key(key_name)


def save_config(config: dict, path: str | None = None) -> None:
    """Save configuration dict to a JSON file.

    Args:
        config: The complete configuration dict to save.
        path: Target file path. Defaults to USER_CONFIG_PATH.
    """
    target = Path(path or config.get("_save_path", USER_CONFIG_PATH))
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = validate_config(config)
    if errors:
        raise ValueError("\n".join(errors))
    if target.exists():
        backup_config(str(target))
    payload = copy.deepcopy(config)
    payload.pop("device_identity", None)
    payload.pop("runtime_devices", None)
    payload.pop("runtime_status", None)
    payload.pop("_joystick_update_only", None)
    payload.pop("_save_path", None)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)

    logger.info("Config saved to: %s", target)


def backup_config(path=None):
    source = Path(path or USER_CONFIG_PATH)
    directory = source.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    shutil.copy2(source, target)
    return target
