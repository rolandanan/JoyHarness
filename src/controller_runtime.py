"""Poll every connected device; translate separate L/R to logical dual buttons."""
import copy
import logging
import queue
import time
import pygame
from .constants import AXIS_RSTICK_X, AXIS_RSTICK_Y
from .device_profiles import button_indices, device_key
from .joystick_handler import apply_deadzone, get_direction
from .config_loader import get_profile

logger = logging.getLogger(__name__)


def joystick_only_updater():
    """Use the SDL linked by pygame without pumping Cocoa mouse/window events."""
    import ctypes
    library = ctypes.CDLL(pygame.base.__file__)
    update = library.SDL_JoystickUpdate
    update.argtypes = []
    update.restype = None
    return update


def device_mode(name):
    name = name.lower().replace(" ", "")
    if "(l+r)" in name or "(l/r)" in name or "pair" in name:
        return "dual"
    if "(l)" in name or name.endswith("-l") or name.endswith("joy-conl"):
        return "single_left"
    return "single_right"


def logical_button(name, side, mode):
    if mode != "dual" or side == "dual":
        return name
    if name in ("SL", "SR"):
        return name + ("_L" if side == "single_left" else "_R")
    return name


def run_controllers(mapper, config, stop_event, on_mode_change=None):
    status = config.setdefault("runtime_status", {})
    status.update(state="输入监听中", error="")
    logger.info("Controller polling started (background input enabled)")
    devices = {}
    last_scan = -10
    signature = None
    mode = config.get("active_profile", "single_right")
    update_joysticks = joystick_only_updater() if config.get("_joystick_update_only") else None
    try:
        while not stop_event.is_set():
            event_types = [pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED,
                           pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP,
                           pygame.JOYAXISMOTION, pygame.JOYHATMOTION, pygame.JOYBALLMOTION]
            if update_joysticks is not None:
                update_joysticks()
                events = pygame.event.get(event_types, pump=False)
            else:
                pygame.event.pump()
                events = pygame.event.get(event_types)
            now = time.monotonic()
            if any(event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED) for event in events) or now - last_scan > 1:
                last_scan = now
                found = {}
                for index in range(pygame.joystick.get_count()):
                    js = pygame.joystick.Joystick(index)
                    js.init()
                    if not any(word in js.get_name().lower() for word in ("joy-con", "joy con", "switch", "pro controller")):
                        continue
                    ident = js.get_instance_id()
                    found[ident] = devices.get(ident) or {"js": js, "buttons": set(), "direction": None,
                        "baseline": [js.get_axis(i) for i in range(js.get_numaxes())], "identity": device_key(js),
                        "side": device_mode(js.get_name()), "blocked": set()}
                devices = found
                status.update(state="输入监听中", error="")
                sides = {d["side"] for d in devices.values()}
                next_mode = "dual" if "dual" in sides or len(sides) > 1 else next(iter(sides), "single_right")
                next_signature = tuple(devices)
                if signature != next_signature:
                    mapper.release_all()
                    signature = next_signature
                    mode = next_mode
                    config["active_profile"] = mode
                    config["mappings"] = copy.deepcopy(get_profile(config, mode).get("mappings", config["mappings"]))
                    config["device_identity"] = next(iter(devices.values()))["identity"] if len(devices) == 1 else ""
                    mapper.switch_profile(config, mode)
                    config["runtime_devices"] = [{"identity": d["identity"], "name": d["js"].get_name(), "mode": d["side"]} for d in devices.values()]
                    if on_mode_change:
                        on_mode_change(mode)
            try:
                while True:
                    command = mapper.command_queue.get_nowait()
                    command()
                    mapper.switch_profile(config, mode)
                    for d in devices.values():
                        d["blocked"].update(d["buttons"])
            except queue.Empty:
                pass
            if config.get('_mapping_paused', False):
                for d in devices.values():
                    current = {i for i in range(d['js'].get_numbuttons()) if d['js'].get_button(i)}
                    d['buttons'] = current
                    d['blocked'] = set(current)
                    d['direction'] = None
                stop_event.wait(max(.001, config.get('poll_interval', .01)))
                continue
            for d in devices.values():
                js = d["js"]
                try:
                    current = {i for i in range(js.get_numbuttons()) if js.get_button(i)}
                    d["blocked"].intersection_update(current | d["buttons"])
                    indices = button_indices(config, d["side"], d["identity"])
                    reverse = {index: name for name, index in indices.items()}
                    dispatch = mapper._button_indices
                    def edge(index, down):
                        name = logical_button(reverse.get(index), d["side"], mode)
                        if down:
                            if index in d["blocked"]:
                                return
                            if mapper.capture_request is not None:
                                request = mapper.capture_request
                                if request[0] == d["identity"]:
                                    mapper.capture_request = None
                                    mapper.capture_events.put((request, index))
                                d["blocked"].add(index)
                                return
                            action = config.get("mappings", {}).get("buttons", {}).get(name)
                            path = f"BTN{index} → {name or '未映射'} → {action}"
                            status["last_input"] = path
                            logger.debug("%s: %s", js.get_name(), path)
                            if name in dispatch:
                                mapper.button_down(dispatch[name])
                        elif index in d["blocked"]:
                            d["blocked"].discard(index)
                        elif name in dispatch:
                            mapper.button_up(dispatch[name])

                    # Replay edges even when press + release happen between samples.
                    # State polling remains a fallback for drivers without button events.
                    for event in events:
                        if event.type not in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                            continue
                        if getattr(event, "instance_id", None) != js.get_instance_id():
                            continue
                        down = event.type == pygame.JOYBUTTONDOWN
                        if down and event.button not in d["buttons"]:
                            edge(event.button, True)
                            d["buttons"].add(event.button)
                        elif not down and event.button in d["buttons"]:
                            edge(event.button, False)
                            d["buttons"].discard(event.button)
                    for index in sorted(current - d["buttons"]):
                        edge(index, True)
                    for index in d["buttons"] - current:
                        edge(index, False)
                    d["buttons"] = current
                    if mapper.capture_request is not None:
                        mapper.stick_centered()
                        continue
                    axes = config.get("device_profiles", {}).get(d["identity"], {}).get("axes", {})
                    x = axes.get("x", config.get("axis_x", AXIS_RSTICK_X))
                    y = axes.get("y", config.get("axis_y", AXIS_RSTICK_Y))
                    if max(x, y) >= js.get_numaxes():
                        continue
                    right_stick = d["side"] != "single_left"
                    x_sign = -1 if right_stick and config.get("right_stick_invert_x", False) else 1
                    y_sign = -1 if right_stick and config.get("right_stick_invert_y", False) else 1
                    direction = get_direction(*apply_deadzone(
                        (js.get_axis(x) - d["baseline"][x]) * axes.get("x_sign", 1) * x_sign,
                        (js.get_axis(y) - d["baseline"][y]) * axes.get("y_sign", 1) * y_sign,
                        config.get("deadzone", .2)), config.get("stick_mode", "4dir"))
                    if direction != d["direction"]:
                        status["last_input"] = f"摇杆 → {direction or '归中'} → {config.get('mappings', {}).get('stick_directions', {}).get(direction)}"
                        logger.debug("%s", status["last_input"])
                        if direction is None:
                            mapper.stick_centered()
                        else:
                            mapper.stick_direction(direction)
                        d["direction"] = direction
                except pygame.error as error:
                    status.update(state="设备读取异常", error=str(error))
                    logger.warning("Device read failed: %s", error)
                    last_scan = -10
            mapper.poll()
            stop_event.wait(max(.001, config.get("poll_interval", .01)))
    finally:
        mapper.release_all()
        if stop_event.is_set():
            status["state"] = "已停止"
