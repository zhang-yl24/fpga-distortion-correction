"""Literal observation markers and external host timing; no native authority."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

PREFIX = 'HDMI_CAMERA_FISHEYE_TILE8DF8V3_OBSERVE'
POLL_SECONDS = .25
COMMANDS_PER_BLOCK = 8


def mark(label):
    if re.fullmatch(r'[A-Z0-9_|-]+', label) is None:
        raise ValueError('literal observation label required')
    return 'puts {' + PREFIX + '|' + label + '}\nflush stdout\n'


def query_body(body):
    return ''.join(mark('QUERY|' + str(i) + '|BEGIN') + line + '\n' + mark('QUERY|' + str(i) + '|RETURN')
                   for i, line in enumerate(body.splitlines()))


def command_body(commands):
    parts = []
    for start in range(0, len(commands), COMMANDS_PER_BLOCK):
        stop = min(start + COMMANDS_PER_BLOCK, len(commands))
        label = 'COMMANDS|' + str(start) + '|' + str(stop - 1)
        parts.append(mark(label + '|BEGIN') + '\n'.join(commands[start:stop]) + '\n' + mark(label + '|RETURN'))
    return ''.join(parts)


def strip_markers(text):
    lines = text.splitlines(keepends=True)
    result, i = [], 0
    while i < len(lines):
        if lines[i].startswith('puts {' + PREFIX + '|'):
            if re.fullmatch(r'puts \{' + PREFIX + r'\|[A-Z0-9_|-]+\}\n', lines[i]) is None or i + 1 >= len(lines) or lines[i + 1] != 'flush stdout\n':
                raise ValueError('nonliteral observation marker cannot be stripped')
            i += 2
        else:
            result.append(lines[i]); i += 1
    return ''.join(result)


class HostObserver:
    def __init__(self, work, native_start):
        self.path = Path(work) / 'stdout.log'
        self.output = (Path(work) / 'host-application-observations.jsonl').open('x', encoding='utf-8', newline='\n')
        self.native_start = native_start
        self.offset = 0
        self.pending = b''
        self.last_poll = None
        self.max_gap = 0.
        self.records = []
        self.native_match_count = 0

    def poll(self):
        now = time.monotonic()
        if self.last_poll is not None:
            self.max_gap = max(self.max_gap, now - self.last_poll)
        self.last_poll = now
        if not self.path.exists():
            return
        with self.path.open('rb') as source:
            source.seek(self.offset); data = source.read()
        self.offset += len(data); self.pending += data
        while b'\n' in self.pending:
            raw, self.pending = self.pending.split(b'\n', 1)
            line = raw.rstrip(b'\r').decode('ascii', errors='replace')
            if line.startswith('I: Timing-5001:'):
                self.native_match_count += 1
            if line.startswith(PREFIX + '|'):
                record = {'NativeMarkerText': line, 'ObservedUTC': datetime.now(timezone.utc).isoformat(),
                          'ObservedHostMonotonicNS': time.monotonic_ns(),
                          'ObservedSecondsSinceNativeLaunch': time.monotonic() - self.native_start,
                          'NativeTiming5001LinesSeen': self.native_match_count,
                          'ExternalHostObservationNotNativeInternalTime': True}
                self.records.append(record)
                self.output.write(json.dumps(record) + '\n'); self.output.flush()

    def close(self):
        try:
            self.poll()
        finally:
            self.output.close()
        return {'ConfiguredPollIntervalSeconds': POLL_SECONDS, 'MaximumActualPollGapSeconds': self.max_gap,
                'ObservedNativeTiming5001Lines': self.native_match_count, 'Markers': self.records,
                'TimestampsAreExternalHostObservations': True,
                'ConfiguredPollingDoesNotBoundNativeStdioBufferingOrOSSchedulingDelay': True,
                'ObservationCreatesNoSelectorOrPhysicalAcceptance': True}
