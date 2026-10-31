"""Assess captured PGHDMI01 input observations, offline only.

This checks a contiguous digital observation window. UART CRC and a capture
receipt cannot establish which FPGA/bitstream produced the bytes. The output
never certifies PHY lock, colour format, DDR, corrected pixels or a display.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math

import hdmi_status

REF_HZ = 27_000_000
PCLK_WINDOW_REF_CYCLES = 27_000
MIN_PCLK_EDGES, MAX_PCLK_EDGES = 73_500, 75_000
FRAME_PIXELS = 2200 * 1125
CFG_STALE_CYCLES = 270_000
MAX_RECORDS = 64
MAX_SPAN_SECONDS = 30
MIN_QUALIFIED_SECONDS = 1
# Fixed observer requests a held snapshot every 1 ms; req/ack/settle adds
# under 1 ms at the admitted clocks. Treat each endpoint as up to 2 ms old.
# Counts also quantize complete frame boundaries, introducing <1 frame of
# difference error. This is a stated diagnostic model, not a measured bound.
SNAPSHOT_AGE_BOUND_SECONDS = 0.002
UINT32_MASK = 0xFFFFFFFF
REQUIRED_FLAGS = (
    'cfg_snapshot_valid', 'cfg_fresh', 'cfg_pll_locked', 'video_pll_locked',
    'rx_init_done', 'all_init_done', 'observer_released', 'polarity_known',
    'input_qualified',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_frames(data):
    """Allow only an initial partial packet and a final partial packet.

    No resynchronization past a corrupt complete packet or interior garbage.
    Opening a UART mid-packet can discard at most 63 leading bytes. A final
    partial packet must contain the expected magic prefix where available.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('wire data must be bytes')
    if len(data) > (MAX_RECORDS + 2) * hdmi_status.PACKET_SIZE:
        raise ValueError('wire exceeds bounded observation size')
    if not data:
        raise ValueError('empty wire')
    start = data.find(hdmi_status.MAGIC)
    if not 0 <= start < hdmi_status.PACKET_SIZE:
        raise ValueError('no complete packet start within initial boundary')
    body = data[start:]
    count, trailing = divmod(len(body), hdmi_status.PACKET_SIZE)
    if not 1 <= count <= MAX_RECORDS:
        raise ValueError('complete packet count outside bounded window')
    frames = []
    for i in range(count):
        try:
            frames.append(hdmi_status.decode_packet(bytes(body[i * 64:(i + 1) * 64])))
        except ValueError as error:
            raise ValueError(f'packet {i}: {error}') from error
    if trailing:
        tail = bytes(body[count * 64:])
        prefix_length = min(len(tail), len(hdmi_status.MAGIC))
        if tail[:prefix_length] != hdmi_status.MAGIC[:prefix_length]:
            raise ValueError('trailing bytes are not a partial packet')
    return frames, {'leading_partial_bytes': start, 'trailing_partial_bytes': trailing}


def receipt_binding(data, frames, receipt):
    """Rebuild transport fields; a matching receipt is attribution, not proof."""
    if not isinstance(receipt, dict) or receipt.get('schema') != 'hdmi-status-receive-v1':
        raise ValueError('capture receipt schema differs')
    parser = hdmi_status.FrameParser()
    decoded = parser.feed(data)
    # Older captures did not include newly derived extension fields. Accept
    # their omission only where that packet version could not provide them;
    # every recorded value, wire byte and other field still has to match.
    captured_frames = receipt.get('frames')
    if type(captured_frames) is not list or len(captured_frames) != len(decoded):
        raise ValueError('capture receipt disagrees with wire: frames')
    for actual, current in zip(captured_frames, decoded):
        if type(actual) is not dict:
            raise ValueError('capture receipt disagrees with wire: frames')
        optional = ({'monitor_freshness', 'monitor_freshness_mask', 'vs_edge_count_ref'}
                    if current['build_tag'] == hdmi_status.BUILD_TAG else
                    {'vs_edge_count_ref'} if current['build_tag'] == hdmi_status.BUILD_TAG_V2 else set())
        comparable = {key: value for key, value in current.items()
                      if key not in optional or key in actual}
        if actual != comparable:
            raise ValueError('capture receipt disagrees with wire: frames')
    expected = {
        'passed': bool(decoded) and parser.rejected == 0,
        'wire_sha256': sha(data), 'received_bytes': len(data),
        'accepted_packets': parser.accepted, 'rejected_packets': parser.rejected,
        'error_counts': dict(parser.error_counts), 'noise_bytes': parser.noise_bytes,
        'trailing_bytes': len(parser.buffer),
        'baudrate': hdmi_status.BAUD, 'bytes_written': 0,
    }
    for name, value in expected.items():
        # bool and int equality alone would allow malformed receipt types.
        if type(receipt.get(name)) is not type(value) or receipt[name] != value:
            raise ValueError('capture receipt disagrees with wire: ' + name)
    if decoded != frames or not receipt['passed'] or receipt.get('error'):
        raise ValueError('capture receipt contains a failed/truncated reception')
    kind = receipt.get('source_kind')
    if kind not in ('receive_only_uart', 'offline_uart_replay'):
        raise ValueError('unsupported capture source kind')
    if receipt.get('hardware_accessed') is not (kind == 'receive_only_uart'):
        raise ValueError('capture source kind/access declaration disagrees')
    return {'matched': True, 'source_kind_claimed_by_receipt': kind,
            'physical_source_verified': False,
            'limits': 'Receipt and bytes are consistent; no signed board or bitstream identity is present in PGHDMI01.'}


def qualification_issues(frame):
    flags = frame['flags_decoded']
    issues = ['missing_' + name for name in REQUIRED_FLAGS if not flags[name]]
    if frame['cfg_snapshot_age'] >= CFG_STALE_CYCLES:
        issues.append('configuration_age_is_stale')
    if frame['width'] != 1920 or frame['height'] != 1080:
        issues.append('geometry_is_not_1920x1080')
    if not MIN_PCLK_EDGES <= frame['pclk_edges'] <= MAX_PCLK_EDGES:
        issues.append('pixel_clock_count_outside_admitted_window')
    if frame['good_frames'] < 2:
        issues.append('fewer_than_two_good_frames')
    return issues


def assess(data, capture_receipt=None):
    """Return a bounded-window assessment; failed evidence stays inspectable."""
    report = {
        'schema': 'hdmi-input-assessment-v1', 'passed': False,
        'passed_scope': 'digital_input_observation_window_only',
        'wire_sha256': sha(data), 'wire_bytes': len(data), 'records': 0,
        'transport_integrity_passed': False, 'errors': [], 'frames': [],
        'capture_receipt_binding': None, 'qualified_window': None,
        'hardware_accessed_by_assessor': False, 'physical_source_verified': False,
        'bitstream_identity_verified': False, 'phy_lock_verified': False,
        'pixel_payload_verified': False, 'display_verified': False,
        'ddr_or_distortion_pipeline_verified': False, 'hardware_release_allowed': False,
        'limits': 'Offline digital timing/geometry observations only. A shared build tag, CRC and a matching capture receipt do not authenticate hardware or identify the running diagnostic. The frame-rate estimate uses nominal 27 MHz reference ticks and delayed good-frame counters, not delivered/processed output frames.',
    }
    try:
        frames, boundary = strict_frames(data)
        report.update(transport_integrity_passed=True, records=len(frames),
                      frames=frames, boundary=boundary)
        if capture_receipt is not None:
            report['capture_receipt_binding'] = receipt_binding(data, frames, capture_receipt)
    except (ValueError, TypeError, KeyError) as error:
        report['errors'].append('transport_or_receipt: ' + str(error))
        return report

    elapsed_ticks = 0
    qualified_first = None
    good_total = 0
    first_good_total = None
    first_elapsed_ticks = None
    wraps = {'sequence': 0, 'reference_ticks': 0, 'good_frames': 0}
    observations = []
    for index, frame in enumerate(frames):
        flags = frame['flags_decoded']
        fatal = list(frame['semantic_issues'])
        if flags['cfg_failed'] or frame['cfg_error']:
            fatal.append('configuration_failed')
        if flags['input_failed'] or frame['input_fault']:
            fatal.append('input_failed')
        if frame['bad_frames']:
            fatal.append('bad_frames_observed')
        if index:
            previous = frames[index - 1]
            seq_delta = (frame['sequence'] - previous['sequence']) & UINT32_MASK
            delta = (frame['reference_ticks'] - previous['reference_ticks']) & UINT32_MASK
            good_delta = (frame['good_frames'] - previous['good_frames']) & UINT32_MASK
            if seq_delta != 1:
                fatal.append('sequence_gap_duplicate_or_reset')
            if not 0 < delta <= REF_HZ:
                fatal.append('reference_tick_interval_outside_0_to_1_second')
            else:
                elapsed_ticks += delta
                # Allow two endpoint frames of rounding/startup slack here;
                # the final qualified window uses a tighter explicit model.
                if good_delta > math.ceil(delta / REF_HZ * 31) + 2:
                    fatal.append('good_frame_counter_regressed_or_advanced_too_far')
            good_total += good_delta
            if frame['bad_frames'] != previous['bad_frames']:
                fatal.append('bad_frame_counter_changed')
            for name in wraps:
                if frame[name] < previous[name]:
                    wraps[name] += 1
                    if wraps[name] > 1:
                        fatal.append(name + '_wrapped_more_than_once')
        if elapsed_ticks > MAX_SPAN_SECONDS * REF_HZ:
            fatal.append('reference_span_exceeds_30_seconds')
        pending = qualification_issues(frame)
        if not pending and not fatal and qualified_first is None:
            qualified_first = index
            first_elapsed_ticks = elapsed_ticks
            first_good_total = good_total
        if qualified_first is not None and pending:
            fatal.extend('qualification_lost:' + issue for issue in pending)
        if qualified_first is not None:
            first_flags = frames[qualified_first]['flags_decoded']
            if any(flags[name] != first_flags[name] for name in ('vs_inactive', 'hs_inactive')):
                fatal.append('sync_polarity_changed_within_qualified_window')
        if fatal:
            report['errors'].extend(f'packet {index}: {issue}' for issue in dict.fromkeys(fatal))
        observations.append({'packet_index': index, 'waiting_for': pending})
    report['counter_wraps'] = wraps
    report['startup_observations'] = observations[:qualified_first] if qualified_first is not None else observations
    report['reference_span_seconds'] = elapsed_ticks / REF_HZ
    if qualified_first is None:
        report['errors'].append('no_qualified_input_window')
        return report

    qualified = frames[qualified_first:]
    span = (elapsed_ticks - first_elapsed_ticks) / REF_HZ
    advance = good_total - first_good_total
    allowed_rate = [MIN_PCLK_EDGES * (REF_HZ / PCLK_WINDOW_REF_CYCLES) / FRAME_PIXELS,
                    MAX_PCLK_EDGES * (REF_HZ / PCLK_WINDOW_REF_CYCLES) / FRAME_PIXELS]
    interval = None
    compatible = False
    if span > 2 * SNAPSHOT_AGE_BOUND_SECONDS and advance > 0:
        interval = [max(0, advance - 1) / (span + 2 * SNAPSHOT_AGE_BOUND_SECONDS),
                    (advance + 1) / (span - 2 * SNAPSHOT_AGE_BOUND_SECONDS)]
        compatible = interval[0] <= allowed_rate[1] and interval[1] >= allowed_rate[0]
    report['qualified_window'] = {
        'first_packet_index': qualified_first, 'records': len(qualified),
        'reference_seconds': span, 'good_frames_advanced': advance,
        'bad_frames_changed': any(f['bad_frames'] != qualified[0]['bad_frames'] for f in qualified),
        'pixel_clock_mhz_range': [min(f['pclk_edges'] for f in qualified) / 1000,
                                  max(f['pclk_edges'] for f in qualified) / 1000],
        'frame_rate_estimate_fps': advance / span if span > 0 else None,
        'frame_rate_interval_fps': interval,
        'frame_rate_interval_model': {'counter_endpoint_quantization_frames': 1,
                                      'snapshot_age_bound_per_endpoint_seconds': SNAPSHOT_AGE_BOUND_SECONDS},
        'pixel_clock_and_fixed_raster_expected_fps_range': allowed_rate,
        'frame_count_rate_compatible_with_admitted_pixel_clock': compatible,
        'is_processed_or_displayed_frame_rate': False,
    }
    if len(qualified) < 2 or span < MIN_QUALIFIED_SECONDS:
        report['errors'].append('qualified_window_shorter_than_1_second_or_two_records')
    if advance <= 0:
        report['errors'].append('good_frame_counter_did_not_advance')
    if not compatible:
        report['errors'].append('frame_count_rate_inconsistent_with_pixel_clock_and_raster')
    report['passed'] = not report['errors']
    return report


def assess_files(wire, receipt=None):
    wire = Path(wire).resolve()
    data = wire.read_bytes()
    raw_receipt = Path(receipt).read_bytes() if receipt is not None else None
    report = assess(data, json.loads(raw_receipt) if raw_receipt is not None else None)
    report['wire_path'] = str(wire)
    report['assessor_sha256'] = sha(Path(__file__).read_bytes())
    if raw_receipt is not None:
        report['capture_receipt_path'] = str(Path(receipt).resolve())
        report['capture_receipt_sha256'] = sha(raw_receipt)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wire', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error('output must be a new file in an existing directory')
    result = assess_files(args.wire, args.receipt)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'passed': result['passed'], 'records': result['records'],
                      'errors': result['errors'], 'output': str(args.output)}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
