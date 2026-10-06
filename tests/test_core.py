"""Automated regression tests; never emit real keyboard events."""
import copy
from pathlib import Path
from unittest.mock import Mock
import pytest
from src.config_loader import load_config, merge_with_defaults, validate_config, save_config
from src.device_profiles import button_indices, validate_devices
from src.key_mapper import KeyMapper
from src import keyboard_output
from src.controller_runtime import device_mode, logical_button
from src.key_labels import action_label
from src.joystick_handler import apply_deadzone

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    config = load_config(str(ROOT / 'config/user-macos.json'))
    from src.hardware_defaults import BUTTON_INDICES
    config['device_identity'] = 'verified-test-device'
    config['device_profiles'] = {'verified-test-device': {'buttons': {'single_right': dict(BUTTON_INDICES)}}}
    return config


@pytest.fixture
def output(monkeypatch):
    events = []
    for method in ('tap', 'press', 'release', 'send_combination', 'type_text'):
        monkeypatch.setattr(keyboard_output, method, lambda *a, m=method, **kw: events.append((m, a)))
    return events


@pytest.mark.parametrize('name,index', [('A',0),('X',1),('B',2),('Y',3),('Home',5),('Plus',6),('SL',9),('SR',10),('R',12),('ZR',14)])
def test_verified_indices(config, name, index):
    assert button_indices(config, 'single_right')[name] == index


@pytest.mark.parametrize('name,method,target', [('R','send_combination',['control','q']),('ZR','send_combination',['option','a']),('A','tap','enter'),('B','tap','escape'),('X','send_combination',['command','c']),('Y','send_combination',['command','v']),('Plus','send_combination',['command','a']),('Home','send_combination',['command','z'])])
def test_verified_shortcuts(config, output, name, method, target):
    mapper = KeyMapper(config)
    index = mapper._button_indices[name]
    mapper.button_down(index)
    mapper.button_up(index)
    assert output == [(method, (target,))]


def test_window_switch_sr(config, output):
    mapper = KeyMapper(config)
    mapper._window_cycler.next = Mock()
    mapper.button_down(10)
    mapper.button_up(12)  # unrelated release cannot trigger switching
    mapper._window_cycler.next.assert_not_called()
    mapper.button_up(10)
    mapper._window_cycler.next.assert_called_once()
    assert not output


def test_window_switch_long(config, output, monkeypatch):
    import src.key_mapper as engine
    mapper = KeyMapper(config)
    window = Mock(title='Window')
    overlay = Mock(selected=window)
    mapper._switcher_overlay = overlay
    mapper._on_overlay_select = Mock()
    monkeypatch.setattr(engine, 'find_windows', lambda apps: [window])
    mapper._find_current_window_index = lambda w: 0
    mapper.button_down(10)
    mapper._ws_press_time -= 1
    mapper.poll()
    overlay.show.assert_called_once()
    mapper.button_up(10)
    mapper._on_overlay_select.assert_called_once_with(window)


def test_auto_hold_repeat(config, output):
    config['mappings']['buttons']['A'] = {'action':'auto','key':'enter'}
    mapper = KeyMapper(config)
    mapper.button_down(0)
    mapper.button_up(0)
    assert output == [('tap', ('enter',))]
    output.clear()
    mapper.button_down(0)
    key, when = mapper._auto_pending[0]
    mapper._auto_pending[0] = (key, when - 1)
    mapper.poll()
    mapper.button_up(0)
    assert output == [('press', ('enter',)), ('release', ('enter',))]
    config['mappings']['buttons']['A']['repeat'] = 100
    mapper = KeyMapper(config)
    output.clear()
    mapper.button_down(0)
    mapper._auto_pending[0] = ('enter', 0)
    mapper.poll()
    mapper._button_repeat[0]['last_time'] = 0
    mapper.poll()
    mapper.button_up(0)
    assert output == [('tap', ('enter',)), ('tap', ('enter',))]
    assert not mapper._button_repeat


def test_sequence_release_no_sentinel(config, output):
    config['mappings']['buttons']['A'] = {'action':'sequence','keys':['command','tab'],'repeat':100}
    mapper = KeyMapper(config)
    mapper.button_down(0)
    mapper.button_up(0)
    mapper.release_all()
    assert not mapper._active_holds
    assert all('__sequence__' not in args for _, args in output)


def test_device_override_isolated(config):
    config['device_profiles'] = {'device1': {'buttons': {'single_right': {'R': 8}}}}
    assert button_indices(config, 'single_right', 'device1')['R'] == 8
    import sys
    assert button_indices(config, 'single_right', 'device2')['R'] == (16 if sys.platform == 'win32' else 12)
    assert validate_devices({'a': {'buttons': {'single_right': {'A':0,'B':0}}}})


def test_profile_migration_roundtrip(config, tmp_path):
    merged = merge_with_defaults({'mappings': {'buttons': {'A': {'action':'tap','key':'space'}}}, 'long_press_threshold':.6, 'axis_x':0})
    assert merged['profiles']['single_right']['mappings']['buttons']['A']['key'] == 'space'
    assert merged['long_press_threshold'] == .6
    path = tmp_path / 'user.json'
    save_config(config, str(path))
    save_config(config, str(path))
    assert list((tmp_path / 'backups').glob('*.json'))
    assert load_config(str(path))['profiles'] == config['profiles']


@pytest.mark.parametrize('mapping', [{'action':'auto'}, {'action':'auto','key':'enter','repeat':-1}, {'action':'exec','command':[]}, {'action':'macro','steps':[{'type':'delay','ms':-1}]}])
def test_invalid_mapping(config, mapping):
    config['profiles']['single_right']['mappings']['buttons']['A'] = mapping
    assert validate_config(config)


def test_alias(config):
    assert all(keyboard_output.is_valid_key(k) for k in ['command','cmd','option','alt','control','ctrl','shift'])
    assert action_label({'action':'combination','keys':['command','option','a']}) == '⌘ + ⌥ + A'
    assert keyboard_output._windows_key('alt_r') == 'right alt'
    assert keyboard_output._windows_key('ctrl_l') == 'left ctrl'


def test_device_side_and_dual():
    assert device_mode('Joy-Con (R)') == 'single_right'
    assert device_mode('Joy-Con (L)') == 'single_left'
    assert device_mode('Joy-Con (L+R)') == 'dual'
    assert logical_button('SR', 'single_right', 'dual') == 'SR_R'
    assert logical_button('SL', 'single_left', 'dual') == 'SL_L'
    assert logical_button('ZR','single_right','dual') == 'ZR'
    assert apply_deadzone(0,0,0) == (0,0)


def test_empty_window_targets():
    from src.window_switcher import WindowCycler
    assert WindowCycler([]).app_names == []


def test_login_is_reversible(tmp_path, monkeypatch):
    from src import autostart
    monkeypatch.setattr(autostart, 'launcher_path', lambda: tmp_path / 'login.plist')
    monkeypatch.setattr(autostart.subprocess, 'run', Mock())
    autostart.set_enabled(True)
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    assert not autostart.is_enabled()


@pytest.mark.parametrize('action,text,expected', [('combination','⌘+c',{'action':'combination','keys':['command','c']}), ('window_switch','',{'action':'window_switch'}), ('tap','Esc',{'action':'tap','key':'escape'}), ('exec','["open", "-a", "Safari"]',{'action':'exec','command':['open','-a','Safari']})])
def test_direct_mapping_editor(action, text, expected):
    from src.mapping_editor import build_mapping
    assert build_mapping(action, text) == expected


def test_direct_editor_rejects_multiple_keys_for_tap():
    from src.mapping_editor import build_mapping
    with pytest.raises(ValueError):
        build_mapping('tap','command+c')


@pytest.mark.parametrize('nibble,status,percent', [(0,'discharging',0),(2,'discharging',25),(6,'discharging',75),(8,'discharging',100),(3,'charging',25),(9,'charging',100),(15,'unknown',-1)])
def test_battery_protocol(nibble,status,percent):
    from src.battery_reader import battery_label
    assert battery_label(nibble) == (status,percent)


def test_runtime_dual_and_calibrated_input(config, output, monkeypatch):
    import threading
    import sys
    from src import controller_runtime as runtime
    stop = threading.Event()
    tick = [-1]
    class Device:
        def __init__(self, side):
            self.side = side
        def get_name(self):
            return f'Joy-Con ({self.side})'
        def get_guid(self):
            return self.side
        def get_instance_id(self):
            return 1 if self.side == 'R' else 2
        def get_numbuttons(self):
            return 20
        def get_numaxes(self):
            return 2
        def get_axis(self, axis):
            return 0
        def get_button(self, index):
            return self.side == 'R' and ((tick[0] == 1 and index == 8) or (tick[0] == 3 and index == 10))
    devices = [Device('R'), Device('L')]
    def pump():
        tick[0] += 1
        if tick[0] >= 5:
            stop.set()
    monkeypatch.setattr(runtime.pygame.event, 'pump', pump)
    monkeypatch.setattr(runtime.pygame.event, 'get', lambda *a: [])
    monkeypatch.setattr(runtime.pygame.joystick, 'get_count', lambda: 2)
    monkeypatch.setattr(runtime.pygame.joystick, 'Joystick', lambda index: devices[index])
    config['device_profiles'] = {f'{sys.platform}:R:Joy-Con (R)': {'buttons': {'single_right': {'R':8}}}}
    config['profiles']['dual']['mappings']['buttons']['R'] = {'action':'combination','keys':['control','q']}
    config['profiles']['dual']['mappings']['buttons']['SR_R'] = {'action':'window_switch'}
    mapper = KeyMapper(config)
    mapper._window_cycler.next = Mock()
    runtime.run_controllers(mapper, config, stop)
    assert config['active_profile'] == 'dual'
    assert len(config['runtime_devices']) == 2
    assert ('send_combination', (['control','q'],)) in output
    mapper._window_cycler.next.assert_called_once()
