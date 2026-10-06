"""Per-user login launchers; changes only when the user toggles the switch."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "io.joyharness.login"


def launcher_path():
    if sys.platform == "darwin":
        return Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft/Windows/Start Menu/Programs/Startup/JoyHarness.vbs"


def launch_arguments():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "src"]


def is_enabled():
    return launcher_path().exists()


def set_enabled(enabled):
    target = launcher_path()
    if not enabled:
        if sys.platform == "darwin" and target.exists():
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent.parent
    args = launch_arguments()
    if sys.platform == "darwin":
        payload = {"Label": LABEL, "ProgramArguments": args, "RunAtLoad": True,
                   "WorkingDirectory": str(root)}
        target.write_bytes(plistlib.dumps(payload))
        # RunAtLoad takes effect at the next login, avoiding a duplicate now.
    elif sys.platform == "win32":
        command = subprocess.list2cmdline(args).replace('"', '""')
        target.write_text(f'Set s = CreateObject("WScript.Shell")\ns.CurrentDirectory = "{root}"\ns.Run "{command}", 0, False\n', encoding="utf-8")
    else:
        raise OSError("当前平台不支持登录启动")
