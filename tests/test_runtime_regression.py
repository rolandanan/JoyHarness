"""Exercise the actual polling dispatcher without emitting OS keystrokes."""
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import controller_runtime as runtime, keyboard_output
from src.config_loader import load_config
from src.key_mapper import KeyMapper


@pytest.mark.parametrize("index,method,target", [
    (0, "tap", "enter"), (2, "tap", "escape"),
    (1, "send_combination", ["command", "c"]),
    (3, "send_combination", ["command", "v"]),
    (12, "send_combination", ["command", "s"]),
    (14, "send_combination", ["command", "f"]),
    (6, "send_combination", ["command", "a"]),
    (5, "send_combination", ["command", "z"]),
    (10, "switch", None),
])
def test_polling_to_action(monkeypatch, index, method, target):
    config = load_config(str(Path(__file__).parents[1] / "config/user-macos.json"))
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    events = []
    for name in ("tap", "press", "release", "send_combination"):
        monkeypatch.setattr(keyboard_output, name,
                            lambda *args, n=name, **kw: events.append((n, args)))
    mapper._window_cycler.next = Mock(return_value=None)
    stop = threading.Event()
    frame = [0]
    js = Mock()
    js.get_name.return_value = "Joy-Con (R)"
    js.get_guid.return_value = "test"
    js.get_instance_id.return_value = 1
    js.get_numbuttons.return_value = 15
    js.get_numaxes.return_value = 2
    js.get_axis.return_value = 0
    js.get_button.side_effect = lambda i: frame[0] == 1 and i == index
    def pump():
        frame[0] += 1
        if frame[0] == 3:
            stop.set()
    monkeypatch.setattr(runtime.pygame.event, "pump", pump)
    monkeypatch.setattr(runtime.pygame.event, "get", lambda *a: [])
    monkeypatch.setattr(runtime.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(runtime.pygame.joystick, "Joystick", lambda i: js)
    runtime.run_controllers(mapper, config, stop)
    assert f"BTN{index}" in config["runtime_status"]["last_input"]
    if method == "switch":
        mapper._window_cycler.next.assert_called_once()
    else:
        assert events == [(method, (target,))]
    js.init.assert_called()


def test_polling_crash_visible(monkeypatch):
    from src.main import _run_polling
    monkeypatch.setattr(runtime, "run_controllers", Mock(side_effect=RuntimeError("test failure")))
    config = {}
    _run_polling(None, Mock(), config, threading.Event())
    assert config["runtime_status"]["state"] == "轮询异常"
    assert "test failure" in config["runtime_status"]["error"]


def test_background_input_enabled():
    import os
    import src.main  # noqa: F401 -- imports initialize SDL background input
    assert os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] == "1"


def test_five_short_presses_between_samples(monkeypatch):
    config = load_config(str(Path(__file__).parents[1] / "config/user-macos.json"))
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    sent = []
    monkeypatch.setattr(keyboard_output, "tap", lambda key: sent.append(key))
    stop = threading.Event()
    js = Mock()
    js.get_name.return_value = "Joy-Con (R)"
    js.get_guid.return_value = "test"
    js.get_instance_id.return_value = 1
    js.get_numbuttons.return_value = 15
    js.get_numaxes.return_value = 2
    js.get_axis.return_value = 0
    js.get_button.return_value = 0  # already released by the next sample
    edges = [runtime.pygame.event.Event(kind, instance_id=1, button=0)
             for _ in range(5) for kind in (runtime.pygame.JOYBUTTONDOWN, runtime.pygame.JOYBUTTONUP)]
    monkeypatch.setattr(runtime.pygame.event, "pump", lambda: None)
    def get(*args):
        stop.set()
        return edges
    monkeypatch.setattr(runtime.pygame.event, "get", get)
    monkeypatch.setattr(runtime.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(runtime.pygame.joystick, "Joystick", lambda i: js)
    runtime.run_controllers(mapper, config, stop)
    assert sent == ["enter"] * 5


def test_output_injection_does_not_block_caller(monkeypatch):
    entered, allow_finish = threading.Event(), threading.Event()
    pressed = []
    def slow_press(key):
        entered.set()
        allow_finish.wait(2)
        pressed.append(key)
    monkeypatch.setattr(keyboard_output, "_do_press", slow_press)
    monkeypatch.setattr(keyboard_output, "_do_release", lambda key: None)
    keyboard_output.start_output_worker({})
    try:
        keyboard_output.tap("enter", duration=0)
        assert entered.wait(1)
        assert not pressed
        allow_finish.set()
        keyboard_output._output_queue.join()
        assert pressed == ["enter"]
    finally:
        allow_finish.set()
        keyboard_output.stop_output_worker()


def test_app_changes_persist_and_refresh(monkeypatch, tmp_path):
    from src.gui import MainWindow
    from src.window_switcher import KNOWN_APPS
    previous = dict(KNOWN_APPS)
    monkeypatch.setattr("src.gui.KNOWN_APPS", dict(previous))
    monkeypatch.setattr("src.window_switcher.KNOWN_APPS", dict(previous))
    config = load_config(str(Path(__file__).parents[1] / "config/user-macos.json"))
    config["_save_path"] = str(tmp_path / "user.json")
    window = MainWindow.__new__(MainWindow)
    window._config = config
    window._window_cycler = Mock()
    window.refresh_apps = Mock()
    window._persist_apps({"Test App": "TestProcess"}, ["TestProcess"])
    saved = load_config(config["_save_path"])
    assert saved["known_apps"] == {"Test App": "TestProcess"}
    assert saved["selected_apps"] == ["TestProcess"]
    assert window._window_cycler.app_names == ["TestProcess"]
    window.refresh_apps.assert_called_once()


def test_switch_binding_persists_and_reaches_mapper(tmp_path):
    from src.gui import MainWindow
    config = load_config(str(Path(__file__).parents[1] / "config/user-macos.json"))
    config["_save_path"] = str(tmp_path / "user.json")
    window = MainWindow.__new__(MainWindow)
    window._config = config
    window._key_mapper = KeyMapper(config)
    window._save_button_mapping("RStick", {"action": "window_switch"})
    window._key_mapper.command_queue.get_nowait()()
    window._key_mapper.switch_profile(config, "single_right")
    saved = load_config(config["_save_path"])
    assert saved["profiles"]["single_right"]["mappings"]["buttons"]["RStick"] == {"action": "window_switch"}
    assert window._key_mapper._button_mappings[7] == {"action": "window_switch"}
    assert config["mappings"]["buttons"]["R"] == {"action": "combination", "keys": ["command", "s"]}


@pytest.mark.parametrize("config_path", ["config/user.json", "config/user-macos.json", None])
@pytest.mark.parametrize("direction,axes", [("up", (0, -1)), ("down", (0, 1)), ("left", (-1, 0)), ("right", (1, 0))])
def test_polling_stick_directions(monkeypatch, direction, axes, config_path, caplog):
    import logging
    from src.config_loader import get_platform_config_path
    caplog.set_level(logging.DEBUG)
    config = load_config(str(Path(__file__).parents[1] / config_path) if config_path else get_platform_config_path())
    repeat_ms = config["mappings"]["stick_directions"][direction].get("repeat", 100)
    axes = (axes[0] * (-1 if config.get("right_stick_invert_x") else 1), axes[1] * (-1 if config.get("right_stick_invert_y") else 1))
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    calls = []
    for method in ("tap", "press", "release", "send_combination"):
        monkeypatch.setattr(keyboard_output, method, lambda *args, **kw: None)
    output = []
    monkeypatch.setattr(keyboard_output, "tap", output.append)
    original = mapper.stick_direction
    def dispatch(value):
        calls.append(value)
        original(value)
    mapper.stick_direction = dispatch
    stop = threading.Event()
    frame = [0]
    js = Mock()
    js.get_name.return_value = "Joy-Con (R)"
    js.get_guid.return_value = "test"
    js.get_instance_id.return_value = 1
    js.get_numbuttons.return_value = 15
    js.get_numaxes.return_value = 2
    js.get_button.return_value = 0
    js.get_axis.side_effect = lambda i: (axes[0] if i == 1 else axes[1]) if frame[0] == 2 else 0
    def pump():
        frame[0] += 1
        if frame[0] == 3:
            stop.set()
    monkeypatch.setattr(runtime.pygame.event, "pump", pump)
    monkeypatch.setattr(runtime.pygame.event, "get", lambda *a: [])
    monkeypatch.setattr(runtime.pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(runtime.pygame.joystick, "Joystick", lambda i: js)
    runtime.run_controllers(mapper, config, stop)
    assert calls == [direction]
    assert output == [direction]
    assert f"stick auto [{direction}] → {direction} (repeat={repeat_ms}ms)" in caplog.text
    assert not mapper._stick_repeat


def test_stick_edit_persists_and_reaches_backend(tmp_path):
    import copy
    from src.gui import MainWindow
    config = load_config(str(Path(__file__).parents[1] / "config/user.json"))
    config["_save_path"] = str(tmp_path / "user.json")
    buttons = copy.deepcopy(config["mappings"]["buttons"])
    window = MainWindow.__new__(MainWindow)
    window._config = config
    window._key_mapper = KeyMapper(config)
    value = {"action": "auto", "key": "up", "repeat": 150}
    window._save_mapping("stick_directions", "up", value)
    window._key_mapper.command_queue.get_nowait()()
    window._key_mapper.switch_profile(config, "single_right")
    assert window._key_mapper._direction_mappings["up"] == value
    assert load_config(config["_save_path"])["profiles"]["single_right"]["mappings"]["stick_directions"]["up"] == value
    assert config["mappings"]["buttons"] == buttons


def test_stick_repeat_stops_when_centered(monkeypatch):
    config = load_config(str(Path(__file__).parents[1] / "config/user.json"))
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    sent = []
    monkeypatch.setattr(keyboard_output, "tap", sent.append)
    monkeypatch.setattr(keyboard_output, "release", lambda key: None)
    mapper.stick_direction("up")
    mapper._stick_repeat[("stick", "up")]["last_time"] = 0
    mapper.poll()
    assert sent == ["up", "up"]
    mapper.stick_centered()
    mapper.poll()
    assert sent == ["up", "up"]


def test_light_stick_touch_waits_before_repeat(monkeypatch):
    config = load_config(str(Path(__file__).parents[1] / "config/user.json"))
    config["stick_repeat_delay"] = 400
    config["mappings"]["stick_directions"]["up"]["repeat"] = 180
    now = [10.0]
    monkeypatch.setattr("src.key_mapper.time.monotonic", lambda: now[0])
    sent = []
    monkeypatch.setattr(keyboard_output, "tap", sent.append)
    monkeypatch.setattr(keyboard_output, "release", lambda key: None)
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    mapper.stick_direction("up")
    for timestamp in (10.1, 10.2, 10.3, 10.399):
        now[0] = timestamp
        mapper.poll()
    assert sent == ["up"]
    now[0] = 10.401
    mapper.poll()
    assert sent == ["up", "up"]
    now[0] = 10.59
    mapper.poll()
    assert sent == ["up", "up", "up"]
    mapper.stick_centered()
    now[0] = 12
    mapper.poll()
    assert sent == ["up", "up", "up"]


@pytest.mark.parametrize("action", ["hold", "auto"])
def test_stick_hold_and_zero_repeat(monkeypatch, action):
    config = load_config(str(Path(__file__).parents[1] / "config/user.json"))
    config["mappings"]["stick_directions"]["up"] = {"action": action, "key": "up", "repeat": 0}
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    sent = []
    for method in ("press", "tap", "release"):
        monkeypatch.setattr(keyboard_output, method, lambda key, name=method: sent.append((name, key)))
    mapper.stick_direction("up")
    mapper.poll()
    assert not mapper._stick_repeat
    mapper.stick_centered()
    assert sent == [("press" if action == "hold" else "tap", "up"), ("release", "up")]


def test_joystick_only_update_does_not_pump_window_events(monkeypatch):
    config = load_config(str(Path(__file__).parents[1] / "config/user-macos.json"))
    config["_joystick_update_only"] = True
    config["device_profiles"] = {f"{__import__('sys').platform}:test:Joy-Con (R)": {"buttons": {"single_right": {"A": 0, "X": 1, "B": 2, "Y": 3, "R": 12, "ZR": 14}}}}
    mapper = KeyMapper(config)
    stop = threading.Event()
    update = Mock()
    monkeypatch.setattr(runtime, "joystick_only_updater", lambda: update)
    pump = Mock()
    monkeypatch.setattr(runtime.pygame.event, "pump", pump)
    def get(types, **kwargs):
        assert kwargs == {"pump": False}
        assert runtime.pygame.JOYAXISMOTION in types
        stop.set()
        return []
    monkeypatch.setattr(runtime.pygame.event, "get", get)
    monkeypatch.setattr(runtime.pygame.joystick, "get_count", lambda: 0)
    runtime.run_controllers(mapper, config, stop)
    update.assert_called_once()
    pump.assert_not_called()
