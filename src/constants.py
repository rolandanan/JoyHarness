"""Compatibility exports for hardware defaults and action presets."""
from .hardware_defaults import *  # noqa: F403
from .default_profiles import *  # noqa: F403

VALID_ACTIONS = ("tap", "hold", "auto", "combination", "sequence", "window_switch", "macro", "exec")

__version__ = "1.2.0"
