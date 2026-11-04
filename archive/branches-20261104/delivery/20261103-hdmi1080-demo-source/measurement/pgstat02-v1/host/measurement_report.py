"""Strict host-only run validation/report around the unchanged PGSTAT02 parser.

No serial import or device access. Hardware counters use core ticks; host times
are capture provenance only. Last-completion samples are not per-frame traces.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import statistics

from stats_protocol import MixedParser, request, window
from pure_window import analyze as base_analyze
from normal_function_uart import make_arm, decode as decode_b4

U32 = 1 << 32
EXPECTED_HZ = 125000000
CANONICAL_COMMAND_SHAS = (
    '67e6b0bea0d81d9eb33229c292d5e54b3f2ad062e0e5d8f877169de610e17a02',
    'a3d5e9b6ad1f0fbcb1ac022b97056b8cae7d2627df176c9dbe58f3ad440effcb',
    'ba88adac0f3285a4959cbb1edf95a4e688a850ede36fce7a59527a305fc0ba9c',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_plan(plan):
    commands = plan['Commands']
    if len(commands) != 3 or [x['Magic'] for x in commands] != ['SGA1', 'SGT1', 'SGT1']:
        raise ValueError('This client supports the source-checked canonical one-SGA/two-SGT plan only')
    if tuple(x['SHA256'] for x in commands) != CANONICAL_COMMAND_SHAS:
        raise ValueError('Only the exact existing broadcast-RX-prechecked request bytes are supported')
    seen = set()
    for command in commands:
        pair = command['Ticket'], command['Nonce']
        if pair in seen:
            raise ValueError('duplicate request identity')
        seen.add(pair)
        data = bytes.fromhex(command['Hex'])
        expected = (make_arm if command['Magic'] == 'SGA1' else request)(*pair)
        if data != expected or sha(data) != command['SHA256']:
            raise ValueError('Request bytes, CRC or SHA differ from plan')
    return commands


def validate_attestation(manifest, attestation):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', manifest.get('firmware_sha256', '')):
        raise ValueError('requires actual built firmware SHA256 before capture')
    if manifest.get('fixed_mode') != 1 or manifest.get('gamma_enable') != 0:
        raise ValueError('requires an actual fixed pure correction gamma-off build')
    if manifest.get('nominal_core_hz') != EXPECTED_HZ:
        raise ValueError('This source-bound run requires nominal125MHz manifest')
    if (manifest.get('width'), manifest.get('height')) != (1920, 1080):
        raise ValueError('requires native1920x1080 build')
    if attestation.get('loaded_firmware_sha256') != manifest['firmware_sha256']:
        raise ValueError('actual load receipt SHA does not match build manifest')
    for name in ('load_receipt_evidence', 'epoch_label', 'boundary_evidence', 'input_description'):
        if not isinstance(attestation.get(name), str) or not attestation[name].strip():
            raise ValueError('missing run evidence: ' + name)
    if attestation.get('uninterrupted_reset_epoch') is not True:
        raise ValueError('explicit uninterrupted FPGA reset epoch evidence required')
    offset = attestation.get('known_packet_boundary_offset')
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError('known packet boundary offset must be an external attested byte offset')
    return offset


def validate_ack(packet, arm):
    acks, frames, invalid = decode_b4(packet, nonce=arm['Nonce'], ticket=arm['Ticket'])
    if invalid or frames or len(acks) != 1:
        raise ValueError('expected exactly one complete SGK1')
    ack = acks[0]
    if not ack['SchemaValid'] or not ack['MatchesCommand'] or ack['Status'] != '01':
        raise ValueError('ACK schema/request identity/ARMED status mismatch')
    return ack


def validate_signature(packet, manifest, arm):
    acks, frames, invalid = decode_b4(packet, nonce=arm['Nonce'])
    if invalid or acks or len(frames) != 1:
        raise ValueError('expected one complete PGSIG001 packet')
    frame = frames[0]
    if not frame['Complete1080'] or not frame['MatchesSession'] or frame['Mode'] != 1 or frame['ParameterID'] != manifest['param_id']:
        raise ValueError('PGSIG schema/session/native geometry/mode/parameter mismatch')
    return frame


def validate_snapshot(value, manifest, command):
    if value['magic'] != 'PGSTAT02' or value['version'] != 2 or value['domain'] != 'core_clk':
        raise ValueError('requires exact PGSTAT02 v2 core schema')
    if (value['ticket'], value['nonce']) != (command['Ticket'], command['Nonce']):
        raise ValueError('stale or unrelated PGSTAT request identity')
    if value['nominal_core_hz'] != manifest['nominal_core_hz']:
        raise ValueError('packet frequency does not match source-bound build manifest')
    if not value['last_process_valid'] or value['completed_mode'] != 1 or value['completed_param_id'] != manifest['param_id']:
        raise ValueError('invalid/mixed completion or parameter identity')
    if value['state_flags'] & 0xc0:
        raise ValueError('pipeline failed or static snapshot unexpectedly active')
    return value


def distribution(values, hz):
    if not values:
        return dict(count=0, cycles=None, seconds_nominal=None)
    ordered = sorted(values)
    def summary(scale):
        # Nearest-rank percentiles; with small N they are descriptive only.
        return dict(min=ordered[0] / scale, median=statistics.median(ordered) / scale,
                    mean=statistics.mean(ordered) / scale,
                    p90=ordered[math.ceil(.90 * len(ordered)) - 1] / scale,
                    p95=ordered[math.ceil(.95 * len(ordered)) - 1] / scale,
                    max=ordered[-1] / scale)
    return dict(count=len(values), percentile_method='nearest_rank', cycles=summary(1), seconds_nominal=summary(hz))


def validate_capture_bindings(manifest, plan, attestation, capture_meta, input_file_bytes):
    """Bind capture provenance to the actual input file bytes, not redumped JSON.

    The collector already records these hashes. LIVE requires their presence;
    synthetic fixtures without file claims remain usable. Supplied byte objects
    must parse to the same dictionaries being analyzed, then their exact hashes
    must match the capture log. The protocol itself has no firmware/boot digest.
    """
    live = capture_meta.get('capture_kind') == 'LIVE_SERIAL_CAPTURE'
    equal_fields = {
        'loaded_firmware_sha256': attestation['loaded_firmware_sha256'],
        'epoch_label': attestation['epoch_label'],
        'uninterrupted_reset_epoch_attested': True,
        'external_boundary_offset': attestation['known_packet_boundary_offset'],
        'boundary_evidence': attestation['boundary_evidence'],
        'input_description': attestation['input_description'],
    }
    for name, expected in equal_fields.items():
        if live and name not in capture_meta:
            raise ValueError('live capture metadata missing input binding: ' + name)
        if name in capture_meta and (type(capture_meta[name]) is not type(expected) or capture_meta[name] != expected):
            raise ValueError('capture metadata contradicts report input: ' + name)
    if 'uninterrupted_reset_epoch_attested' in capture_meta and capture_meta['uninterrupted_reset_epoch_attested'] is not True:
        raise ValueError('capture metadata does not attest uninterrupted reset epoch')
    specifications = {'manifest': (manifest, 'manifest_sha256'), 'plan': (plan, 'plan_sha256'),
                      'run_attestation': (attestation, 'run_attestation_sha256')}
    claimed_hashes = any(field in capture_meta for _, field in specifications.values())
    if not (live or claimed_hashes or input_file_bytes is not None):
        return dict(verified=False, scope='synthetic fixture without input-file provenance claims')
    if not isinstance(input_file_bytes, dict):
        raise ValueError('actual manifest/plan/attestation file bytes required for capture-hash verification')
    computed = {}
    for name, (parsed, field) in specifications.items():
        raw = input_file_bytes.get(name)
        if not isinstance(raw, bytes):
            raise ValueError('actual input file bytes missing: ' + name)
        if json.loads(raw.decode('utf-8-sig')) != parsed:
            raise ValueError('input file bytes differ from parsed report input: ' + name)
        actual = sha(raw)
        if capture_meta.get(field) != actual:
            raise ValueError('capture metadata input-file SHA mismatch: ' + field)
        computed[field] = actual
    return dict(verified=True, hashes=computed, scope='SHA256 of supplied exact file bytes; not canonicalized/redumped JSON')


def analyze_run(raw, manifest, plan, attestation, capture_meta, *, input_file_bytes=None):
    start = validate_attestation(manifest, attestation)
    commands = validate_plan(plan)
    input_binding = validate_capture_bindings(manifest, plan, attestation, capture_meta, input_file_bytes)
    if capture_meta.get('raw_sha256') != sha(raw):
        raise ValueError('raw capture SHA mismatch')
    end = capture_meta.get('validated_analysis_end_offset')
    if isinstance(end, bool) or not isinstance(end, int) or not start <= end <= len(raw):
        raise ValueError('invalid externally recorded validated analysis end offset')
    selected = raw[start:end]
    parser = MixedParser()
    packets = parser.feed(selected)
    parser.finish()
    offset, selected_index, arm_start = start, None, None
    for index, (kind, value) in enumerate(packets):
        if kind == 'SGK1':
            decoded, _, invalid = decode_b4(value, nonce=commands[0]['Nonce'], ticket=commands[0]['Ticket'])
            if invalid or len(decoded) != 1 or not decoded[0]['SchemaValid']:
                raise ValueError('invalid pre-arm ACK schema')
            if decoded[0]['MatchesCommand']:
                validate_ack(value, commands[0])
                selected_index, arm_start = index, offset
                break
        offset += value['packet_bytes'] if isinstance(value, dict) else len(value)
    if selected_index is None:
        raise ValueError('missing matched ARMED ACK after attested packet boundary')
    if capture_meta.get('selected_ack_start_offset', arm_start) != arm_start:
        raise ValueError('recorded ACK boundary was not derived by the strict packet walk')
    pre_arm_packets = selected_index
    packets = packets[selected_index:]
    selected = raw[arm_start:end]
    if not packets or packets[-1][0] != 'PGSTAT02':
        raise ValueError('analysis end must be the complete final requested PGSTAT02 boundary')
    snapshots, signatures, acks, snapshot_ranges = [], [], [], []
    packet_offset = arm_start
    for kind, value in packets:
        this_packet_start = packet_offset
        packet_offset += value['packet_bytes'] if isinstance(value, dict) else len(value)
        if kind == 'SGK1':
            if acks or signatures or snapshots:
                raise ValueError('unexpected additional or late ARM ACK')
            acks.append(validate_ack(value, commands[0]))
        elif kind == 'PGSIG001':
            if not acks:
                raise ValueError('signature preceded matched ARMED ACK')
            signatures.append(validate_signature(value, manifest, commands[0]))
        elif kind == 'PGSTAT02':
            if not acks or not signatures or len(snapshots) >= len(commands) - 1:
                raise ValueError('unrequested stats or missing complete armed signature')
            snapshots.append(validate_snapshot(value, manifest, commands[len(snapshots) + 1]))
            snapshot_ranges.append((this_packet_start, packet_offset))
        else:
            raise ValueError('unexpected packet in lightweight measurement: ' + kind)
    if len(acks) != 1 or len(snapshots) != 2:
        raise ValueError('canonical run needs one ARMED ACK and both exact requested stats responses')
    tx = capture_meta.get('TX_requests')
    if capture_meta.get('capture_kind') == 'LIVE_SERIAL_CAPTURE':
        if capture_meta.get('outcome') != 'CAPTURE_COMPLETE_TWO_SNAPSHOTS' or tx is None:
            raise ValueError('live capture lacks complete outcome and exact transmit journal')
    if tx is not None:
        if len(tx) != len(commands):
            raise ValueError('transmit journal does not contain exactly the canonical3commands')
        response_starts = [arm_start] + [r[0] for r in snapshot_ranges]
        for index, (entry, command) in enumerate(zip(tx, commands)):
            if (entry.get('index'), entry.get('magic'), entry.get('ticket'), entry.get('nonce'), entry.get('sha256')) != (
                index+1, command['Magic'], command['Ticket'], command['Nonce'], command['SHA256']):
                raise ValueError('transmit journal identity mismatch')
            if bytes.fromhex(entry.get('hex', '')) != bytes.fromhex(command['Hex']) or entry.get('outcome_uncertain') is not False or entry.get('disposition') != 'HOST_WRITE_DRAINED':
                raise ValueError('transmit journal bytes or write outcome unconfirmed')
            fence = entry.get('rx_fence_offset')
            if isinstance(fence, bool) or not isinstance(fence, int) or not 0 <= fence <= response_starts[index]:
                raise ValueError('response began before its recorded request RX fence')
    # Reuse the unchanged analyzer and conservative32-bit counter-window guard.
    base = base_analyze(selected, manifest, uninterrupted_reset_epoch=True)
    intervals, samples, unique = [], [], {}
    pixels_per_frame = manifest['width'] * manifest['height']
    for index, current in enumerate(snapshots):
        candidate = current['last_process_cycles_including_final_edge']
        processing = int(bool(current['state_flags'] & 2))
        outstanding = (current['captured_frames'] - current['processed_frames']) % U32
        # Exact DMA source_pop and bank source acceptance are the same event.
        # A normal granted-capture rejection/no-grant never increments this A.
        if outstanding != processing:
            raise ValueError('accepted-minus-completed/processing snapshot invariant failed; window is not a coherent healthy common-reset profile')
        key = (current['processed_frames'], current['completed_frame_id'], current['completed_param_id'], current['completed_mode'])
        evidence = None
        if current['core_tick'] < U32:
            if not 0 < candidate <= current['core_tick']:
                raise ValueError('last process cycle candidate exceeds since-reset core-tick bound')
            evidence = 'core_tick_since_shared_reset_less_than_2**32'
        if index:
            previous = snapshots[index - 1]
            interval = window(previous, current, uninterrupted_reset_epoch=True)
            if (current['sequence'] - previous['sequence']) % U32 != 1:
                raise ValueError('duplicate/out-of-order/missing or other-client snapshot sequence')
            done_delta = interval['delta']['processed_frames']
            previous_processing = int(bool(previous['state_flags'] & 2))
            if interval['delta']['captured_frames'] - done_delta != processing - previous_processing:
                raise ValueError('accepted/completed interval deltas do not conserve the single active processing frame')
            # The first completion may have begun before this snapshot window.
            # Every later completion requires at least N coordinate admissions.
            if done_delta > interval['core_cycles'] // pixels_per_frame + 1:
                raise ValueError('completion count exceeds native single-engine coordinate-throughput bound')
            tuple_fields = ('completed_frame_id', 'completed_param_id', 'completed_mode', 'last_process_cycles')
            if done_delta == 0 and any(current[k] != previous[k] for k in tuple_fields):
                raise ValueError('completion tuple changed without a completed frame')
            frame_span = (current['completed_frame_id'] - previous['completed_frame_id']) % U32
            if current['completed_frame_id'] < previous['completed_frame_id']:
                raise ValueError('source-frame-ID reset/order/wrap crossing unsupported by this display profile')
            if done_delta > 0 and not done_delta <= frame_span <= interval['core_cycles']:
                raise ValueError('completion counter and distinct source frame IDs disagree')
            for name, value in interval['delta'].items():
                if value > interval['core_cycles']:
                    raise ValueError('counter reset/multiple-wrap or impossible per-cycle delta: ' + name)
            if done_delta >= 2:
                # Source-bound invariant: one serial engine, count and completed
                # tuple update in the same success branch. The last of>=2 new
                # completions starts after the first and finishes in this window.
                if candidate > interval['core_cycles']:
                    raise ValueError('last process cycle candidate exceeds serial-engine in-window bound')
                evidence = 'at_least_two_serial_engine_completions_inside_sub_2**32_tick_window'
            intervals.append(interval)
        if evidence is None and key in unique and unique[key]['no_legacy_cycle_wrap_proven']:
            evidence = 'same_atomic_completion_identity_as_earlier_no_wrap_proved_sample'
        # A small raw residue alone can be a legitimately wrapped long frame.
        # Apply the physical-coordinate lower bound only after no-wrap proof.
        if evidence and candidate < pixels_per_frame:
            raise ValueError('unwrapped processing duration below native2073600-coordinate edge lower bound')
        if key in unique and unique[key]['cycles_candidate_raw_plus1'] != candidate:
            raise ValueError('same completion identity has conflicting process cycles')
        sample = dict(sequence=current['sequence'], core_tick=current['core_tick'],
                      processed_frames=current['processed_frames'], frame_id=current['completed_frame_id'],
                      accepted_minus_completed=outstanding, processing_flag=processing,
                      param_id=current['completed_param_id'], mode=current['completed_mode'],
                      raw_legacy_last_index=current['last_process_cycles'], cycles_candidate_raw_plus1=candidate,
                      no_legacy_cycle_wrap_proven=evidence is not None, no_wrap_evidence=evidence,
                      completed_after_first_snapshot=(index > 0 and (current['processed_frames']-snapshots[0]['processed_frames']) % U32 > 0),
                      sourceaccept_to_success_cycles=candidate if evidence else None,
                      sourceaccept_to_success_seconds_nominal=candidate / EXPECTED_HZ if evidence else None)
        samples.append(sample)
        if key not in unique or evidence:
            unique[key] = sample
    total = base['window']
    delta = total['delta']
    good_counted = delta['presented_frames'] + delta['scan_repeat_frames']
    durations = [s['sourceaccept_to_success_cycles'] for s in unique.values() if s['no_legacy_cycle_wrap_proven']]
    within_window_samples = sum(s['no_legacy_cycle_wrap_proven'] and s['completed_after_first_snapshot'] for s in unique.values())
    synthetic = capture_meta.get('capture_kind') == 'SYNTHETIC_OFFLINE_FIXTURE'
    return dict(status='PASS_OFFLINE_SYNTHETIC_FIXTURE' if synthetic else 'PASS_VALIDATED_INTERNAL_COUNTER_RUN',
        data_origin=capture_meta.get('capture_kind', 'UNSPECIFIED_RAW_FILE_ORIGIN_NOT_ATTESTED_BY_PROTOCOL'),
        firmware_sha256=manifest['firmware_sha256'],
        build_status=manifest.get('status'), param_id=manifest['param_id'], nominal_core_hz=EXPECTED_HZ,
        frequency_basis='Source/PLL/build nominal clock; not independently measured physical frequency',
        reset_epoch=dict(label=attestation['epoch_label'], evidence='external_run_attestation_plus_counter_consistency; no hardware boot ID',
                         uninterrupted=True, ack_arm_epoch=acks[0]['Epoch'], ack_arm_epoch_is_not_reset_epoch=True),
        input_description=attestation['input_description'],
        integrity=dict(raw_sha256=sha(raw), raw_bytes=len(raw), external_attested_packet_boundary=start,
                       analysis_start_offset=arm_start, analysis_end_offset=end,
                       excluded_prefix_bytes=arm_start, retained_tail_bytes=len(raw)-end,
                       strict_parsed_complete_packets_before_selected_ARMED=pre_arm_packets,
                       packet_boundaries='external_attested_start; strict incremental parsing thereafter, no magic resynchronization',
                       validated_packet_count=len(packets), packet_order=[k for k, _ in packets],
                       all_packet_CRCS_valid=True, CRC_scope='complete packets from attested boundary through final stats; excluded raw prefix/tail not validated',
                       request_ticket_nonce_matches=True, PGSTAT_version=2,
                       transmit_journal_validated=(tx is not None),
                       capture_input_file_binding=input_binding,
                       PGSIG_session_nonce=commands[0]['Nonce'], complete_PGSIG_packets=len(signatures)),
        core_window=total,
        counter_semantics=dict(captured_frames='Complete source DMA descriptors accepted by bank source_pop; not all sensor/HDMI arrivals',
            processed_frames='Successful processing completions; sampled IDs and atomic completion tuple must agree',
            presented_frames='New greater frame IDs finishing successful reader/pixel/FIFO display lease; not physical photons',
            scan_repeat_frames='Successful nonblank display lease completing the same last presented ID',
            dropped_frames='Rejected completion of a previously granted capture; no-grant input windows and separate no_free are omitted'),
        rates=dict(accepted_source_descriptors_per_second_nominal=delta['captured_frames']/total['seconds_nominal'],
                   processed_new_correction_fps_nominal=total['processed_fps_nominal'],
                   new_presented_fps_nominal=total['new_presented_fps_nominal'],
                   scan_repeat_events_per_second_nominal=delta['scan_repeat_frames']/total['seconds_nominal'],
                   successful_nonblank_scan_repeat_fraction=(delta['scan_repeat_frames']/good_counted if good_counted else None),
                   DMA_rejected_completion_events_per_second_nominal=delta['dropped_frames']/total['seconds_nominal']),
        sampled_internal_sourceaccept_to_success=dict(samples=samples,
            distinct_completed_samples=len(unique), unambiguous_samples=len(durations),
            unproven_cycle_wrap_samples=sum(not s['no_legacy_cycle_wrap_proven'] for s in unique.values()),
            distribution=distribution(durations, EXPECTED_HZ),
            unambiguous_new_completion_samples_inside_window=within_window_samples,
            sample_coverage_fraction_vs_window_completions=(within_window_samples/delta['processed_frames'] if delta['processed_frames'] else None),
            scope='Only requested last-completion samples, not a complete per-frame latency distribution; canonical plan supplies at most2 samples'),
        intervals=intervals,
        limitations=base['limitations'] + [
            'Counter deltas are modulo32 under an externally attested uninterrupted epoch; core ticks are full64-bit and their difference gets no+1.',
            'Only legacy per-frame last-index gets+1. Absolute duration is excluded if absence of its32-bit wrap is unproven.',
            'Low32 core-tick carry is supported; a decreasing full64 tick or repeated/out-of-order stats sequence is rejected.',
            'Event counters support one modulo32 crossing under the bounded window; source frame-ID descent/wrap is rejected because this display profile uses an unsigned new-ID comparison.',
            'The first endpoint latency may belong to a completion before the throughput window; only new in-window samples enter the coverage numerator.',
            'Native duration lower bound is applied only to no-wrap-proved samples; low legacy residues without that proof stay unproven.',
            'Repeat fraction excludes blank/failed scans; PGSTAT02 does not export all scan/no-grant/overflow fields.',
            'captured_frames plus dropped_frames is not total camera frames; neither no-grant losses nor sensor exposure events are exported.',
            'PGSIG packet CRC validates transport. FPGA PixelCRC is not an independent image-correctness or calibration oracle.',
            'External input boundary/reset/bit-load attestations cannot be proven from a nonce, scan epoch or UART wall time.'],
        external_E2E='UNMEASURED', scan_refresh_fps='NOT_INFERRED', corrected60fps='NOT_CLAIMED')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('wire', 'manifest', 'plan', 'run-attestation', 'capture-meta', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    a = ap.parse_args()
    input_bytes = dict(manifest=a.manifest.read_bytes(), plan=a.plan.read_bytes(),
                       run_attestation=a.run_attestation.read_bytes())
    parse = lambda raw: json.loads(raw.decode('utf-8-sig'))
    capture_meta = parse(a.capture_meta.read_bytes())
    # Offline simple fixtures have no file-provenance claims. Live/claimed-hash
    # captures must cross-check the exact bytes loaded once above.
    bound = (capture_meta.get('capture_kind') == 'LIVE_SERIAL_CAPTURE' or
             any(k in capture_meta for k in ('manifest_sha256', 'plan_sha256', 'run_attestation_sha256')))
    result = analyze_run(a.wire.read_bytes(), parse(input_bytes['manifest']), parse(input_bytes['plan']),
                         parse(input_bytes['run_attestation']), capture_meta,
                         input_file_bytes=input_bytes if bound else None)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], rates=result['rates'],
                          latency_distribution=result['sampled_internal_sourceaccept_to_success']['distribution'],
                          external_E2E=result['external_E2E']), indent=2))


if __name__ == '__main__':
    main()
