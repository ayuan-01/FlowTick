class Timer:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"

    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"

    def __init__(self, root, on_tick, on_segment_change, on_session_end):
        self.root = root
        self.on_tick = on_tick
        self.on_segment_change = on_segment_change
        self.on_session_end = on_session_end

        self.state = self.IDLE
        self.segments = []
        self.current_idx = 0
        self.segment_remaining = 0
        self.focus_accumulated = 0
        self.focus_total = 0
        self._job = None

    def build_session(self, focus_total_min, focus_block, break_min, long_break_min, long_interval):
        """根据总专注时长和节奏参数，预计算所有 segments"""
        self.segments = []
        self.focus_total = focus_total_min
        remaining = focus_total_min
        pomodoro_count = 0
        while remaining > 0:
            block = min(focus_block, remaining)
            self.segments.append((self.FOCUS, block))
            remaining -= block
            pomodoro_count += 1
            if remaining <= 0:
                break
            if pomodoro_count % long_interval == 0:
                self.segments.append((self.LONG_BREAK, long_break_min))
            else:
                self.segments.append((self.SHORT_BREAK, break_min))

    @property
    def total_segments(self):
        return len(self.segments)

    @property
    def focus_segments(self):
        return sum(1 for t, _ in self.segments if t == self.FOCUS)

    @property
    def current_focus_index(self):
        """已完成的专注段数（1-based）"""
        return sum(1 for i, (t, _) in enumerate(self.segments)
                   if t == self.FOCUS and i < self.current_idx)

    @property
    def session_remaining_sec(self):
        """整个会话剩余秒数"""
        if not self.segments:
            return 0
        total = sum(m * 60 for _, m in self.segments[self.current_idx:])
        return total - (self.segments[self.current_idx][1] * 60 - self.segment_remaining)

    def start(self):
        """开始会话"""
        if not self.segments:
            return
        self.state = self.RUNNING
        self.current_idx = 0
        self.focus_accumulated = 0
        self._begin_segment()

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

    def skip_segment(self):
        """跳过当前 segment"""
        if self.state != self.RUNNING:
            return
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        # 跳过的专注段不计入 focus_accumulated
        self._advance()

    def reset(self):
        if self._job:
            self.root.after_cancel(self._job)
            self._job = None
        self.state = self.IDLE
        self.current_idx = 0
        self.segment_remaining = 0
        self.focus_accumulated = 0

    def _begin_segment(self):
        """开始当前 index 对应的 segment"""
        seg_type, seg_min = self.segments[self.current_idx]
        self.segment_remaining = seg_min * 60
        self.on_segment_change(
            seg_type, seg_min,
            self.current_idx, len(self.segments),
            self.focus_accumulated, self.focus_total
        )
        self._tick()

    def _tick(self):
        if self.state != self.RUNNING:
            return
        self.on_tick(self.segment_remaining)
        if self.segment_remaining <= 0:
            seg_type, seg_min = self.segments[self.current_idx]
            if seg_type == self.FOCUS:
                self.focus_accumulated += seg_min
            self._advance()
            return
        self.segment_remaining -= 1
        self._job = self.root.after(1000, self._tick)

    def _advance(self):
        """推进到下一个 segment 或结束会话"""
        self.current_idx += 1
        if self.current_idx >= len(self.segments):
            self.state = self.IDLE
            self.on_session_end(self.focus_accumulated)
            return
        self._begin_segment()
