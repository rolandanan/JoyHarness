"""Process lifecycle independent of the settings window."""
class AppController:
    def __init__(self, gui, mapper, config, stop_event):
        self.gui, self.mapper, self.config, self.stop_event = gui, mapper, config, stop_event
        self.paused = self.closing = self._started = False

    def start(self, thread):
        if not self._started:
            self._started = True
            thread.start()

    def toggle_pause(self):
        self.paused = not self.paused
        paused = self.paused
        self.mapper.command_queue.put(lambda: self.config.__setitem__('_mapping_paused', paused))

    def shutdown(self):
        if not self.closing:
            self.closing = True
            self.stop_event.set()
            self.gui.root.destroy()
