"""Strict PGHRAW01 raw-pin diagnostics; offline replay or receive-only UART.

This independent 128-byte protocol never accepts PGHDMI01 observer records.
Raw counters describe sampled parallel pins, not PHY lock or pixel correctness.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import struct
import time
import zlib

MAGIC, TRAILER, PACKET_SIZE = b'PGHRAW01', b'HR01', 128
BUILD_TAG, REFERENCE_HZ, SNAPSHOT_INTERVAL_REF = 0x48445202, 27000000, 27000
SUPPORTED_BUILD_TAGS = (0x48445201, BUILD_TAG)
FRESH_LIMIT, BAUD, MAX_BYTES = 270000, 115200, 4 * 1024 * 1024
MASK32, HALF32 = 0xffffffff, 0x80000000
FLAG_NAMES = ('cfg_snapshot_valid', 'cfg_fresh', 'cfg_lock', 'video_lock',
              'rx_done', 'all_done', 'cfg_failed', 'raw_snapshot_valid')
WORD_NAMES = ('source_sequence', 'pclk_cycles', 'vs_rises', 'vs_falls',
              'hs_rises', 'hs_falls', 'de_rises', 'de_falls', 'de_high_samples',
              'vs_period_pclk', 'hs_period_pclk', 'de_high_width_pclk',
              'vs_high_width_pclk', 'vs_low_width_pclk', 'level_validity', 'de_rises_per_vs_period')
VALID_NAMES = ('vs_period', 'hs_period', 'de_high_width', 'vs_high_width', 'vs_low_width', 'de_rises_per_vs_period')


def decode_packet(packet):
    if len(packet) != PACKET_SIZE:
        raise ValueError('length')
    if packet[:8] != MAGIC:
        raise ValueError('magic')
    if packet[124:] != TRAILER:
        raise ValueError('trailer')
    crc = zlib.crc32(packet[:120])
    if crc != struct.unpack_from('<I', packet, 120)[0]:
        raise ValueError('crc32')
    build_tag = struct.unpack_from('<I', packet, 100)[0]
    if build_tag not in SUPPORTED_BUILD_TAGS:
        raise ValueError('build_tag')
    if struct.unpack_from('<II', packet, 104) != (REFERENCE_HZ, SNAPSHOT_INTERVAL_REF):
        raise ValueError('timebase')
    flags = struct.unpack_from('<H', packet, 16)[0]
    words = struct.unpack_from('<16I', packet, 36)
    if (flags & ~0xff or packet[18] & 0xf0 or packet[19] & ~3 or packet[31] & ~3
            or words[14] & ~0x3f07 or packet[112:120] != bytes(8)):
        raise ValueError('reserved')
    state = {name: bool(flags & (1 << bit)) for bit, name in enumerate(FLAG_NAMES)}
    raw = dict(zip(WORD_NAMES, words))
    raw['levels'] = {name: bool(words[14] & (1 << bit)) for bit, name in enumerate(('vs', 'hs', 'de'))}
    raw['valid'] = {name: bool(words[14] & (1 << (8 + bit))) for bit, name in enumerate(VALID_NAMES)}
    value = {'sequence': struct.unpack_from('<I', packet, 8)[0],
             'reference_ticks': struct.unpack_from('<I', packet, 12)[0],
             'flags': flags, 'flags_decoded': state, 'cfg_error': packet[18],
             'raw_flags': packet[19], 'raw_snapshot_busy': bool(packet[19] & 1),
             'raw_snapshot_fresh': bool(packet[19] & 2),
             'cfg_snapshot_age': struct.unpack_from('<I', packet, 20)[0],
             'completed_transactions': struct.unpack_from('<I', packet, 24)[0],
             'last_address': struct.unpack_from('<H', packet, 28)[0],
             'last_value': packet[30], 'last_meta': packet[31],
             'last_transaction_is_read': bool(packet[31] & 1),
             'last_transaction_target': 'TX' if packet[31] & 2 else 'RX',
             'raw_snapshot_age': struct.unpack_from('<I', packet, 32)[0],
             'raw': raw, 'raw_words': list(words), 'build_tag': build_tag,
             'reference_hz': REFERENCE_HZ, 'snapshot_interval_ref': SNAPSHOT_INTERVAL_REF,
             'crc32': f'{crc:08x}', 'wire_hex': bytes(packet).hex()}
    issues = []
    if state['cfg_fresh'] != (state['cfg_snapshot_valid'] and value['cfg_snapshot_age'] < FRESH_LIMIT):
        issues.append('configuration_freshness_inconsistent')
    if value['raw_snapshot_fresh'] != (state['raw_snapshot_valid'] and value['raw_snapshot_age'] < FRESH_LIMIT):
        issues.append('raw_snapshot_freshness_inconsistent')
    if state['all_done'] and not state['rx_done']:
        issues.append('all_complete_without_rx_complete')
    if state['cfg_failed'] and (state['rx_done'] or state['all_done']):
        issues.append('configuration_failure_with_completion')
    value.update(semantic_issues=issues, phy_lock=None, colour_format=None,
                 pixels_verified=False, hdmi_display_verified=False, hardware_release_allowed=False)
    return value


class FrameParser:
    """Bounded framing recovery: retain at most127 bytes after every feed."""
    def __init__(self):
        self.buffer = bytearray()
        self.accepted = self.rejected = self.noise_bytes = 0
        self.error_counts = Counter()

    def feed(self, data):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError('feed expects bytes')
        view, offset, frames = memoryview(data).cast('B'), 0, []
        while offset < len(view):
            count = min(PACKET_SIZE - len(self.buffer), len(view) - offset)
            self.buffer.extend(view[offset:offset + count])
            offset += count
            while True:
                start = self.buffer.find(MAGIC)
                if start < 0:
                    remove = len(self.buffer) - min(len(MAGIC) - 1, len(self.buffer))
                    self.noise_bytes += remove
                    del self.buffer[:remove]
                    break
                if start:
                    self.noise_bytes += start
                    del self.buffer[:start]
                if len(self.buffer) < PACKET_SIZE:
                    break
                try:
                    frame = decode_packet(bytes(self.buffer))
                except ValueError as error:
                    self.rejected += 1
                    self.error_counts[str(error)] += 1
                    self.noise_bytes += 1
                    del self.buffer[0]
                else:
                    frames.append(frame)
                    self.accepted += 1
                    self.buffer.clear()
        return frames


def rate_between(previous, current):
    """Digital estimates only; repeated/stale snapshots never create rates.

    Packet reference time minus snapshot age is the reference-domain snapshot
    acknowledgment epoch, not the exact source sampling instant. Estimates use
    nominal27MHz and include unmeasured CDC acknowledgment latency variation.
    All modulo deltas assume one continuous reset epoch and less than half-wrap.
    """
    result = {'rates_available': False, 'reset_epoch_continuity_proven': False,
              'assumes_continuous_reset_epoch': True, 'nominal_reference_hz': REFERENCE_HZ,
              'basis': 'reference_ticks_minus_raw_snapshot_age_acknowledgment_epoch',
              'exact_source_snapshot_time_known': False, 'physical_frequency_calibration_performed': False}
    reason = None
    if current['build_tag'] != previous['build_tag']:
        reason = 'build_tag_changed'
    elif (current['sequence'] - previous['sequence']) & MASK32 != 1:
        reason = 'packet_sequence_gap_or_reset'
    elif previous['semantic_issues'] or current['semantic_issues']:
        reason = 'inconsistent_packet_semantics'
    elif not all(p['flags_decoded']['raw_snapshot_valid'] and p['raw_snapshot_fresh'] for p in (previous, current)):
        reason = 'snapshot_invalid_or_stale'
    else:
        source_delta = (current['raw']['source_sequence'] - previous['raw']['source_sequence']) & MASK32
        result['source_sequence_delta'] = source_delta
        if source_delta == 0:
            reason = 'snapshot_not_advanced'
        elif source_delta >= HALF32:
            reason = 'source_sequence_reset_or_ambiguous_wrap'
    if reason:
        result['reason'] = reason
        return result
    packet_delta = (current['reference_ticks'] - previous['reference_ticks']) & MASK32
    start = (previous['reference_ticks'] - previous['raw_snapshot_age']) & MASK32
    end = (current['reference_ticks'] - current['raw_snapshot_age']) & MASK32
    tick_delta = (end - start) & MASK32
    if not 0 < packet_delta < HALF32 or not 0 < tick_delta < HALF32:
        result['reason'] = 'reference_time_not_advancing_or_ambiguous_wrap'
        return result
    counters = WORD_NAMES[1:9]
    deltas = {name: (current['raw'][name] - previous['raw'][name]) & MASK32 for name in counters}
    if not 0 < deltas['pclk_cycles'] < HALF32:
        result['reason'] = 'pclk_not_advancing_or_ambiguous_wrap'
        return result
    if any(deltas[name] > deltas['pclk_cycles'] for name in counters[1:]):
        result['reason'] = 'counter_reset_or_incoherent_snapshot'
        return result
    edge_checks = []
    for signal in ('vs', 'hs', 'de'):
        rises, falls = (deltas[signal + suffix] for suffix in ('_rises', '_falls'))
        start_level = int(previous['raw']['levels'][signal])
        end_level = int(current['raw']['levels'][signal])
        expected = end_level - start_level
        passed = ((rises - falls) & MASK32) == (expected & MASK32)
        edge_checks.append({'signal': signal, 'rising_edges': rises, 'falling_edges': falls,
                            'start_level': start_level, 'end_level': end_level,
                            'rise_minus_fall': rises - falls, 'expected_difference': expected,
                            'passed': passed})
    failed_edges = [row for row in edge_checks if not row['passed']]
    result['edge_conservation'] = {'passed': not failed_edges, 'signals': edge_checks}
    if failed_edges:
        result.update(reason='edge_count_level_conservation_failed',
                      edge_conservation_failures=failed_edges)
        return result
    seconds = tick_delta / REFERENCE_HZ
    hz = deltas['pclk_cycles'] / seconds
    periods = {}
    for valid, word, trigger in (('vs_period', 'vs_period_pclk', 'vs_rises'),
            ('hs_period', 'hs_period_pclk', 'hs_rises'),
            ('de_high_width', 'de_high_width_pclk', 'de_falls'),
            ('vs_high_width', 'vs_high_width_pclk', 'vs_falls'),
            ('vs_low_width', 'vs_low_width_pclk', 'vs_rises')):
        count = current['raw'][word]
        valid_measurement = current['raw']['valid'][valid] and count > 0
        updated = valid_measurement and deltas[trigger] > 0
        periods[valid] = {'valid': valid_measurement, 'updated_in_window': updated,
                          'last_observed_only': valid_measurement and not updated,
                          'update_edge': trigger, 'pclk_cycles': count,
                          'seconds_estimate': count / hz if updated else None}
    lines_valid = current['raw']['valid']['de_rises_per_vs_period']
    lines_updated = lines_valid and deltas['vs_rises'] > 0
    result.update(rates_available=True, reason=None, reference_tick_delta=tick_delta,
                  packet_reference_tick_delta=packet_delta, nominal_seconds=seconds, counter_deltas=deltas,
                  pclk_hz_estimate=hz,
                  vs_rising_hz_estimate=deltas['vs_rises'] / seconds,
                  vs_falling_hz_estimate=deltas['vs_falls'] / seconds,
                  hs_rising_hz_estimate=deltas['hs_rises'] / seconds,
                  de_rising_hz_estimate=deltas['de_rises'] / seconds,
                  de_high_fraction=deltas['de_high_samples'] / deltas['pclk_cycles'],
                  periods=periods,
                  vs_period_hz_estimate=hz / current['raw']['vs_period_pclk']
                      if periods['vs_period']['updated_in_window'] else None,
                  vs_frame_boundaries_observed=deltas['vs_rises'] > 0 and deltas['vs_falls'] > 0,
                  raw_vs_no_edges=deltas['vs_rises'] == deltas['vs_falls'] == 0,
                  most_recent_vs_interval_de_rises=current['raw']['de_rises_per_vs_period']
                      if lines_updated else None,
                  last_observed_vs_interval_de_rises=current['raw']['de_rises_per_vs_period']
                      if lines_valid else None,
                  vs_interval_de_rises_updated_in_window=lines_updated,
                  edge_rate_resolution_hz=1 / seconds,
                  limits='Endpoint edge-count rates are quantized by approximately one edge per window. '
                         'Periods/widths count sampled PCLK cycles and update only on their defining edge; '
                         'sticky valid bits retain historical measurements. Frequencies use nominal27MHz '
                         'and snapshot acknowledgment epochs with unmeasured CDC latency variation. '
                         'The most recent complete VS interval can start before this window; no full-window geometry or pixel proof.')
    return result


def summarize(frames):
    windows = [rate_between(a, b) for a, b in zip(frames, frames[1:])]
    selected = [w for w in windows if w['rates_available']]
    totals = {name: sum(w['counter_deltas'][name] for w in selected) for name in WORD_NAMES[1:9]}
    ticks = sum(w['reference_tick_delta'] for w in selected)
    seconds = ticks / REFERENCE_HZ
    return {'packet_count': len(frames), 'counter_window_count': len(windows),
            'valid_counter_windows': len(selected), 'windows': windows,
            'unavailable_reasons': dict(Counter(w['reason'] for w in windows if not w['rates_available'])),
            'edge_conservation_failure_windows': sum(bool(w.get('edge_conservation_failures')) for w in windows),
            'edge_conservation_failed_signals': sorted({row['signal'] for w in windows
                for row in w.get('edge_conservation_failures', [])}),
            'selected_reference_ticks': ticks, 'selected_nominal_seconds': seconds,
            'selected_counter_deltas': totals,
            'pclk_hz_estimate': totals['pclk_cycles'] / seconds if seconds else None,
            'raw_vs_rising_hz_estimate': totals['vs_rises'] / seconds if seconds else None,
            'raw_vs_falling_hz_estimate': totals['vs_falls'] / seconds if seconds else None,
            'raw_vs_no_edges_in_selected_windows': bool(selected) and totals['vs_rises'] == totals['vs_falls'] == 0,
            'signal_edge_rate_is_verified_video_fps': False,
            'pixels_verified': False, 'hdmi_display_verified': False,
            'reset_epoch_continuity_proven': False,
            'limits': 'Selected fresh advancing raw snapshots; nominal reference time and variable CDC acknowledgment latency. Raw VS edge rates and PCLK do not prove resolution, progressive format, RGB packing, HDMI refresh or successful display.'}


def validate_serial_request(port, seconds):
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]*', port, re.I):
        raise ValueError('an explicit Windows COM port is required')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 30:
        raise ValueError('seconds must be finite and in (0,30]')


def serial_chunks(port_name, seconds, *, serial_factory=None, monotonic=time.monotonic, on_open=None):
    """Receive115200/8N1; no writes, flushing, reset or asserted control lines."""
    validate_serial_request(port_name, seconds)
    if serial_factory is None:
        import serial
        serial_factory = serial.Serial
    port = serial_factory(port=None, baudrate=BAUD, bytesize=8, parity='N', stopbits=1,
                          timeout=.1, write_timeout=0, xonxoff=False, rtscts=False, dsrdtr=False)
    try:
        port.dtr, port.rts, port.port = False, False, port_name.upper()
        port.open()
        if on_open is not None:
            on_open()
        deadline = monotonic() + seconds
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            port.timeout = min(.1, remaining)
            data = port.read(512)
            if not isinstance(data, bytes) or len(data) > 512:
                raise ValueError('serial read returned invalid bytes')
            if data:
                yield data
    finally:
        port.close()


def replay_chunks(path):
    with Path(path).open('rb') as stream:
        while chunk := stream.read(4096):
            yield chunk


def capture(output, *, replay=None, port=None, seconds=5, max_bytes=MAX_BYTES):
    """Save exact wire and a fresh receipt; replay never opens a device."""
    if (replay is None) == (port is None):
        raise ValueError('select exactly one of replay or port')
    if port is not None:
        validate_serial_request(port, seconds)
    if type(max_bytes) is not int or not PACKET_SIZE <= max_bytes <= MAX_BYTES:
        raise ValueError('byte limit must be integer128..4194304')
    if replay is not None and Path(replay).stat().st_size > max_bytes:
        raise ValueError('replay exceeds byte limit')
    output = Path(output).resolve()
    raw_path = output.with_suffix('.raw.bin')
    if output.suffix.lower() != '.json' or not output.parent.is_dir():
        raise ValueError('output must be a new.json in an existing directory')
    if output.exists() or (port is not None and raw_path.exists()):
        raise FileExistsError('output already exists')
    parser, digest = FrameParser(), hashlib.sha256()
    report = {'schema': 'hdmi-raw-status-receive-v1', 'passed': False, 'passed_scope': 'packet_integrity_only',
              'protocol': 'PGHRAW01', 'packet_bytes': PACKET_SIZE,
              'source_kind': 'offline_uart_replay' if replay is not None else 'receive_only_uart',
              'hardware_access_attempted': False, 'hardware_accessed': False, 'bytes_written': 0,
              'uart_transmit_bytes': 0, 'port': port, 'baudrate': BAUD, 'frames': [], 'received_bytes': 0,
              'maximum_bytes': max_bytes, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'hardware_release_allowed': False, 'pixels_verified': False, 'hdmi_display_verified': False}
    with output.open('x', encoding='utf-8', newline='\n') as receipt:
        raw = chunks = None
        try:
            if replay is not None:
                report['replay_path'] = str(Path(replay).resolve())
                chunks = replay_chunks(replay)
            else:
                raw = raw_path.open('xb')
                report['raw_path'] = str(raw_path)
                report['hardware_access_attempted'] = True
                chunks = serial_chunks(port, seconds,
                    on_open=lambda: report.update(hardware_accessed=True))
            with closing(chunks):
                for chunk in chunks:
                    if port is not None:
                        report['hardware_accessed'] = True
                    digest.update(chunk)
                    report['received_bytes'] += len(chunk)
                    if raw is not None:
                        raw.write(chunk)
                    report['frames'].extend(parser.feed(chunk))
                    if report['received_bytes'] > max_bytes:
                        raise ValueError('wire byte limit exceeded; complete last read retained')
            report['passed'] = bool(report['frames']) and parser.rejected == 0
        except (Exception, KeyboardInterrupt) as error:
            report['error'] = type(error).__name__ + ': ' + str(error)
        finally:
            if raw is not None:
                raw.close()
            report.update(wire_sha256=digest.hexdigest(), accepted_packets=parser.accepted,
                          rejected_packets=parser.rejected, error_counts=dict(parser.error_counts),
                          noise_bytes=parser.noise_bytes, trailing_bytes=len(parser.buffer),
                          summary=summarize(report['frames']),
                          ended_utc=datetime.now(timezone.utc).isoformat())
            json.dump(report, receipt, indent=2, ensure_ascii=False, allow_nan=False)
            receipt.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--replay', type=Path)
    source.add_argument('--port')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, default=MAX_BYTES)
    args = parser.parse_args(argv)
    try:
        report = capture(args.output, replay=args.replay, port=args.port,
                         seconds=args.seconds, max_bytes=args.max_bytes)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({k: report[k] for k in ('passed', 'accepted_packets', 'rejected_packets', 'summary')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
