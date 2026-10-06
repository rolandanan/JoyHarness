"""Native status item on Tk's main-thread Cocoa event loop."""
from AppKit import NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem, NSApplication
from Foundation import NSObject
import objc
import queue
from .autostart import is_enabled

class MenuActions(NSObject):
    @objc.IBAction
    def invoke_(self, sender):
        # Native menu tracking re-enters Cocoa while Tk has released the GIL.
        # Never call Tcl/Tk here, including after(): drain from a Tk timer.
        self.pending.put(self.callbacks[sender.tag()])

class MacMenuBar:
    def __init__(self, controller):
        self.controller = controller
        self.actions = MenuActions.alloc().init()
        self.actions.pending = queue.SimpleQueue()
        self.actions.callbacks = {}
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.item.button().setTitle_('JH')
        self.item.button().setToolTip_('JoyHarness')
        self.menu = NSMenu.alloc().initWithTitle_('JoyHarness')
        self.menu.setAutoenablesItems_(False)
        self.state = self.add('JoyHarness：运行中')
        self.devices = self.add('手柄：检测中')
        self.battery = self.add('电量：检测中')
        self.menu.addItem_(NSMenuItem.separatorItem())
        self.add('打开 JoyHarness', self.show)
        self.pause = self.add('暂停手柄映射', controller.toggle_pause)
        self.add('设置与校准', self.settings)
        self.login = self.add('登录时自动启动', self.toggle_login)
        self.dock = self.add('隐藏 Dock 图标', self.toggle_dock)
        self.menu.addItem_(NSMenuItem.separatorItem())
        self.add('退出 JoyHarness', controller.shutdown)
        self.item.setMenu_(self.menu)
        self.refresh()
        self.apply_dock_policy()
        controller.gui.root.after(50, self.drain_actions)

    def add(self, title, callback=None):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, 'invoke:' if callback else None, '')
        item.setEnabled_(callback is not None)
        if callback:
            tag = len(self.actions.callbacks)
            self.actions.callbacks[tag] = callback
            item.setTag_(tag)
            item.setTarget_(self.actions)
        self.menu.addItem_(item)
        return item

    def drain_actions(self):
        while not self.actions.pending.empty() and not self.controller.closing:
            callback = self.actions.pending.get()
            try:
                callback()
            except Exception:
                import sys
                self.controller.gui.root.report_callback_exception(*sys.exc_info())
        if not self.controller.closing:
            self.controller.gui.root.after(50, self.drain_actions)

    def apply_dock_policy(self):
        from AppKit import NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular
        policy = NSApplicationActivationPolicyAccessory if self.controller.config.get('hide_dock_icon', False) else NSApplicationActivationPolicyRegular
        NSApplication.sharedApplication().setActivationPolicy_(policy)

    def toggle_dock(self):
        from .config_loader import save_config
        c = self.controller
        c.config['hide_dock_icon'] = not c.config.get('hide_dock_icon', False)
        self.apply_dock_policy()
        save_config(c.config)

    def show(self):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.controller.gui.show()

    def settings(self):
        self.show()
        self.controller.gui._open_settings()

    def toggle_login(self):
        gui = self.controller.gui
        gui._login_var.set(not is_enabled())
        gui._on_login_toggle()

    def refresh(self):
        c = self.controller
        self.state.setTitle_('JoyHarness：' + ('已暂停' if c.paused else '运行中'))
        self.pause.setTitle_('恢复手柄映射' if c.paused else '暂停手柄映射')
        from .constants import MODE_LABELS
        self.devices.setTitle_('手柄：' + (MODE_LABELS.get(c.config.get('active_profile'), '检测中') if c.config.get('runtime_devices') else '未连接'))
        states = c.gui._battery_reader.get_state() if c.gui._battery_reader else {}
        self.battery.setTitle_('电量：' + (' / '.join(f'{side} {pct}%' for side, (_, pct) in states.items() if pct >= 0) or '不可用'))
        self.login.setState_(int(is_enabled()))
        self.dock.setState_(int(c.config.get("hide_dock_icon", False)))
        if not c.closing:
            c.gui.root.after(1000, self.refresh)

    def stop(self):
        NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
