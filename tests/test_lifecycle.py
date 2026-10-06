"""Lifecycle boundaries and native-menu actions without hardware output."""
import threading
import sys
import pytest
from unittest.mock import Mock
from src.app_controller import AppController


def test_start_and_quit_are_idempotent():
    gui, mapper, thread = Mock(), Mock(), Mock()
    stop = threading.Event()
    controller = AppController(gui, mapper, {}, stop)
    controller.start(thread)
    controller.start(thread)
    thread.start.assert_called_once()
    controller.shutdown()
    controller.shutdown()
    assert stop.is_set()
    gui.root.destroy.assert_called_once()


def test_close_only_hides_on_macos(monkeypatch):
    from src.gui import MainWindow
    monkeypatch.setattr('src.gui.sys.platform', 'darwin')
    gui = MainWindow.__new__(MainWindow)
    gui._root = Mock()
    gui._stop_event = threading.Event()
    gui.controller = Mock()
    gui._on_close()
    assert not gui._stop_event.is_set()
    gui._root.withdraw.assert_called_once()
    gui._root.destroy.assert_not_called()
    gui.controller.shutdown.assert_not_called()
    gui.show()
    gui._root.deiconify.assert_called_once()


def test_pause_is_serialized_on_polling_thread():
    import queue
    mapper = Mock()
    mapper.command_queue = queue.Queue()
    config = {}
    controller = AppController(Mock(), mapper, config, threading.Event())
    controller.toggle_pause()
    assert controller.paused and not config
    mapper.command_queue.get_nowait()()
    assert config['_mapping_paused']
    controller.toggle_pause()
    mapper.command_queue.get_nowait()()
    assert not config['_mapping_paused']


def test_login_launches_in_background(monkeypatch):
    from src import autostart
    monkeypatch.setattr(autostart.sys, 'platform', 'darwin')
    assert autostart.launch_arguments()[-1] == '--background'


def test_existing_login_migration_preserves_target_and_backup(tmp_path, monkeypatch):
    import plistlib
    from src import autostart
    path = tmp_path / 'login.plist'
    payload = {'ProgramArguments': ['/existing/JoyHarness'], 'RunAtLoad': True}
    original = plistlib.dumps(payload)
    path.write_bytes(original)
    monkeypatch.setattr(autostart.sys, 'platform', 'darwin')
    monkeypatch.setattr(autostart, 'launcher_path', lambda: path)
    autostart.upgrade_background_launcher()
    autostart.upgrade_background_launcher()
    assert plistlib.loads(path.read_bytes())['ProgramArguments'] == ['/existing/JoyHarness', '--background']
    assert path.with_suffix('.plist.before-background').read_bytes() == original


@pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS menu")
def test_native_action_only_enqueues_without_touching_tk():
    import queue
    from types import SimpleNamespace
    from src.macos_menu import MenuActions
    callback = Mock()
    actions = MenuActions.alloc().init()
    actions.pending = queue.SimpleQueue()
    actions.callbacks = {3: callback}
    from AppKit import NSMenuItem
    sender = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Test", None, "")
    sender.setTag_(3)
    actions.invoke_(sender)
    callback.assert_not_called()
    assert actions.pending.get_nowait() is callback


@pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS menu")
def test_menu_drains_actions_from_tk_timer():
    import queue
    from types import SimpleNamespace
    from src.macos_menu import MacMenuBar
    callback = Mock()
    controller = SimpleNamespace(closing=False, gui=Mock())
    menu = SimpleNamespace(controller=controller, actions=SimpleNamespace(pending=queue.SimpleQueue()), drain_actions=Mock())
    menu.actions.pending.put(callback)
    MacMenuBar.drain_actions(menu)
    callback.assert_called_once()
    controller.gui.root.after.assert_called_once_with(50, menu.drain_actions)


@pytest.mark.skipif(sys.platform != "darwin", reason="Native macOS menu")
def test_hide_dock_uses_accessory_and_restores_regular(monkeypatch):
    from types import SimpleNamespace
    import AppKit
    from src.macos_menu import MacMenuBar
    app = Mock()
    monkeypatch.setattr('src.macos_menu.NSApplication', SimpleNamespace(sharedApplication=lambda: app))
    menu = SimpleNamespace(controller=SimpleNamespace(config={'hide_dock_icon': True}))
    MacMenuBar.apply_dock_policy(menu)
    app.setActivationPolicy_.assert_called_with(AppKit.NSApplicationActivationPolicyAccessory)
    menu.controller.config['hide_dock_icon'] = False
    MacMenuBar.apply_dock_policy(menu)
    app.setActivationPolicy_.assert_called_with(AppKit.NSApplicationActivationPolicyRegular)
