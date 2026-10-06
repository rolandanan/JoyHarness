"""Optional real Tk component smoke tests (JOYHARNESS_UI_TEST=1)."""
import os
from pathlib import Path
import threading
from unittest.mock import Mock
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('JOYHARNESS_UI_TEST') != '1', reason='Explicit GUI smoke only')


def test_workbench_editor_and_settings(tmp_path):
    from src.config_loader import load_config
    from src.key_mapper import KeyMapper
    from src.gui import MainWindow
    from src.mapping_editor import MappingEditor
    from src.settings_window import SettingsWindow
    config = load_config(str(Path(__file__).resolve().parents[1] / 'config/user-macos.json'))
    config['_save_path'] = str(tmp_path / 'user.json')
    mapper = KeyMapper(config)
    stop = threading.Event()
    gui = MainWindow(mapper, mapper._window_cycler, config, stop)
    try:
        gui.root.update()
        gui._refresh_status()
        assert len(gui._mapping_table.get_children()) == 11
        assert str(gui._mapping_table.column('target', 'anchor')) == 'center'
        assert int(gui.root.style.lookup('Workflow.Treeview', 'rowheight')) == 28
        gui._switch_button.set('RStick')
        gui._bind_window_switch()
        mapper.command_queue.get_nowait()()
        assert config['profiles']['single_right']['mappings']['buttons']['RStick']['action'] == 'window_switch'
        mapper.switch_profile(config, 'single_right')
        mapper._window_cycler.next = Mock()
        mapper.button_down(7)
        mapper.button_up(7)
        mapper._window_cycler.next.assert_called_once()
        saved = []
        editor = MappingEditor(gui.root, 'X', config['mappings']['buttons']['X'], saved.append)
        editor.editor.delete('1.0', 'end')
        editor.editor.insert('1.0', 'command+v')
        editor._save()
        assert saved == [{'action':'combination','keys':['command','v']}]
        settings = SettingsWindow(gui.root, mapper, config, mapper._window_cycler)
        settings._win.update()
        assert len(settings._rows) == 11
        settings._collect()
        settings._close()
        gui._config['theme'] = 'darkly'
        gui.root.style.theme_use('darkly')
        gui._configure_styles()
        gui.root.update()
        assert gui.root.style.lookup('Muted.TLabel', 'foreground') == '#cbd5e1'
    finally:
        stop.set()
        gui.root.destroy()
