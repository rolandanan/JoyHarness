# Build: python -m PyInstaller --noconfirm JoyHarness.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
config_files = [(f'config/{name}.json', 'config') for name in ('default', 'user-macos', 'user-windows')]
# Homebrew SDL2-compat loads SDL3 via dlopen; binary dependency scanning misses it.
sdl3 = Path('/opt/homebrew/opt/sdl3/lib/libSDL3.0.dylib')
extra_binaries = [(str(sdl3), '.'), (str(sdl3.with_name('libSDL3.dylib')), '.')] if sys.platform == 'darwin' and sdl3.exists() else []
a = Analysis(['pyinstaller_entry.py'], pathex=['.'], binaries=extra_binaries,
             datas=config_files + [('assets', 'assets'), ('LICENSE', '.')],
             hiddenimports=collect_submodules('pynput') if sys.platform == 'darwin' else [],
             hookspath=[], runtime_hooks=[], excludes=['pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='JoyHarness',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='JoyHarness')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='JoyHarness.app', bundle_identifier='io.joyharness.desktop',
                 info_plist={'NSHighResolutionCapable': True,
                             'NSInputMonitoringUsageDescription': 'JoyHarness 使用手柄驱动键盘快捷键。',
                             'NSAppleEventsUsageDescription': 'JoyHarness 切换所选应用窗口。'})
