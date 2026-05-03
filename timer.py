class Timer:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"

    FOCUS = "focus"
    BREAK = "break"

    def __init__(self, root, focus_sec, break_sec, on_tick, on_mode_change):
        self.root = root
        self.focus_sec = focus_sec
        self.break_sec = break_sec
        self.on_tick = on_tick
        self.on_mode_change = on_mode_change

        self.state = self.IDLE
        self.mode = self.FOCUS
        self.remaining = focus_sec
        self._job = None

    def start(self):
        if self.state == self.RUNNING:
            return
        self.state = self.RUNNING
        self._tick()

    def pause(self):
        if self.state != self.RUNNING:
            return
        self.state = self.PAUSED
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None

    def resume(self):
        if self.state != self.PAUSED:
            return
        self.state = self.RUNNING
        self._tick()

    def reset(self):
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        self.state = self.IDLE
        self.mode = self.FOCUS
        self.remaining = self.focus_sec
        self.on_tick(self.remaining)
        self.on_mode_change(self.mode)

    def set_durations(self, focus_sec, break_sec):
        self.focus_sec = focus_sec
        self.break_sec = break_sec
        if self.state == self.IDLE:
            self.remaining = focus_sec if self.mode == self.FOCUS else break_sec
            self.on_tick(self.remaining)

    def _tick(self):
        if self.state != self.RUNNING:
            return
        self.on_tick(self.remaining)
        if self.remaining <= 0:
            self._switch_mode()
            return
        self.remaining -= 1
        self._job = self.root.after(1000, self._tick)

    def _switch_mode(self):
        if self.mode == self.FOCUS:
            self.mode = self.BREAK
            self.remaining = self.break_sec
        else:
            self.mode = self.FOCUS
            self.remaining = self.focus_sec
        self.on_mode_change(self.mode)
        self._job = self.root.after(1000, self._tick)
