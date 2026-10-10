"""Ordered, CRC-validated raw/bypass/enhanced frames from frozen capture RTL."""
from dataclasses import dataclass
import zlib
from frame_protocol import Frame


@dataclass
class GammaTriplet:
    group_id: int
    mode: int
    raw: Frame
    before: Frame
    after: Frame


class GammaTripletAssembler:
    def __init__(self):
        self.pending = []
        self.incomplete_groups = 0
        self.orphan_packets = 0
        self.completed_groups = 0
        self.last_group = None

    def feed(self, frame):
        # Revalidate callers that bypass the stream parser; no observation-only
        # packet or mismatched CRC can become a completed image comparison.
        if not 0 < frame.width <= 1920 or not 0 < frame.height <= 1080 or len(frame.payload) != frame.width * frame.height * 2:
            raise ValueError('Invalid RGB565 frame layout')
        if zlib.crc32(frame.payload) != frame.source_crc:
            raise ValueError('Frame payload CRC mismatch')
        if not 0 <= frame.frame_id <= 0xFFFFFFFF:
            raise ValueError('Invalid frame identifier')
        group, mode, kind = frame.frame_id >> 4, (frame.frame_id >> 2) & 3, frame.frame_id & 3
        if group == 0 or kind == 3 or mode == 3 or (kind != 2 and mode != 0):
            raise ValueError('Invalid frozen capture packet identity')
        if kind == 0:
            if self.last_group == group or (self.pending and self.pending[0].frame_id >> 4 == group):
                raise ValueError('Duplicate source group')
            if self.pending:
                self.incomplete_groups += 1
            self.pending = [frame]
            return None
        if not self.pending:
            self.orphan_packets += 1
            return None
        first = self.pending[0]
        if first.frame_id >> 4 != group or (first.width, first.height) != (frame.width, frame.height):
            raise ValueError('Before/after source group or shape mismatch')
        if kind != len(self.pending):
            raise ValueError('Duplicate or out-of-order tone packet')
        self.pending.append(frame)
        if kind == 2:
            raw, before, after = self.pending
            self.pending = []
            self.last_group = group
            self.completed_groups += 1
            return GammaTriplet(group, mode, raw, before, after)
        return None

    def finish(self):
        if self.pending:
            self.incomplete_groups += 1
            self.pending = []
