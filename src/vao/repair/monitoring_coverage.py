"""Presence-only main-program coverage using CPython's per-location disable flag."""
import _thread
import os
import sys


class MonitoringCoverage:
    def __init__(self, files):
        self.monitor = sys.monitoring
        self.tool = self.monitor.COVERAGE_ID
        self.files = {os.path.abspath(name): name for name in files}
        self.lines, self.events, self.limited = set(), 0, False
        self.owner, self.other_thread = _thread.get_ident(), False
        self.callback = self.on_line

    def on_line(self, code, line):
        filename = self.files.get(code.co_filename)
        if filename is not None:
            if _thread.get_ident() != self.owner:
                self.other_thread = True
            else:
                self.events = min(self.events + 1, 100001)
                if self.events > 100000 or (len(self.lines) >= 4096 and (filename, line) not in self.lines):
                    self.limited = True
                else:
                    self.lines.add((filename, line))
        # LINE describes presence. Repeated visits to this bytecode location add
        # no information to the union of covered lines, including within loops.
        return self.monitor.DISABLE

    def start(self):
        self.monitor.use_tool_id(self.tool, 'repair-public-lines')
        self.monitor.register_callback(self.tool, self.monitor.events.LINE, self.callback)
        self.monitor.set_events(self.tool, self.monitor.events.LINE)

    def intact(self):
        if (self.monitor.get_tool(self.tool) != 'repair-public-lines'
                or self.monitor.get_events(self.tool) != self.monitor.events.LINE
                or self.other_thread):
            return False
        return self.monitor.register_callback(self.tool, self.monitor.events.LINE, None) is self.callback

    def stop(self):
        if self.monitor.get_tool(self.tool) == 'repair-public-lines':
            self.monitor.set_events(self.tool, 0)
            self.monitor.register_callback(self.tool, self.monitor.events.LINE, None)
            self.monitor.free_tool_id(self.tool)

    def export(self, intact):
        return {'version': 'stdin-monitoring-line-coverage-v1',
                'lines': [list(row) for row in sorted(self.lines)], 'line_events': self.events,
                'limit_reached': self.limited, 'intact': intact, 'event_limit': 100000, 'line_limit': 4096}
