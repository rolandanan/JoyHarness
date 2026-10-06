"""Persistent physical mappings, independent of keyboard action profiles."""
import sys
from .constants import get_button_indices, MAPPABLE_BUTTONS_BY_MODE


def device_key(joystick):
    return f"{sys.platform}:{joystick.get_guid()}:{joystick.get_name()}"


def button_indices(config, mode, identity=None):
    defaults = dict(get_button_indices(mode))
    if sys.platform == "win32" and mode == "single_right":
        # Keep upstream Windows SDL fallback; all devices should save their own calibration.
        defaults.update({"A": 1, "X": 0, "B": 3, "Y": 2, "R": 16, "ZR": 18})
    saved = config.get("device_profiles", {}).get(identity or config.get("device_identity", ""), {})
    defaults.update(saved.get("buttons", {}).get(mode, {}))
    return defaults


def validate_devices(profiles):
    errors = []
    if not isinstance(profiles, dict):
        return ["device_profiles 必须为对象"]
    for identity, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get("buttons", {}), dict):
            errors.append(f"{identity}: 无效设备配置")
            continue
        axes = profile.get("axes", {})
        if not isinstance(axes, dict):
            errors.append(f"{identity}: 无效轴设置")
        else:
            for key in ("x", "y"):
                if key in axes and (type(axes[key]) is not int or axes[key] < 0):
                    errors.append(f"{identity}: 无效轴 {key}")
            for key in ("x_sign", "y_sign"):
                if key in axes and axes[key] not in (-1, 1):
                    errors.append(f"{identity}: 无效轴方向")
        for mode, buttons in profile.get("buttons", {}).items():
            if mode not in MAPPABLE_BUTTONS_BY_MODE or not isinstance(buttons, dict):
                errors.append(f"{identity}: 无效模式 {mode}")
                continue
            indices = []
            for name, index in buttons.items():
                if name not in MAPPABLE_BUTTONS_BY_MODE[mode] or type(index) is not int or index < 0:
                    errors.append(f"{identity}: 无效按钮 {name}={index}")
                indices.append(index)
            if len(set(map(str, indices))) != len(indices):
                errors.append(f"{identity}: 重复按钮索引")
    return errors
