"""Isolated synthetic UART/PDS tests; no real hardware access."""
from pathlib import Path
import copy
import json
import sys
import zlib
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import guarded_native_session as host
import guarded_protocol as gp
from frame_protocol import encode, Frame
REAL_VARIANT_FACTORY = host._variant_factory
REAL_HELPERS = host._helpers


class Clock:
    def __init__(self): self.value = 0.
    def __call__(self): return self.value


class SyntheticUART:
    """Packet-boundary device fixture, with optional deliberate protocol faults."""
    def __init__(self, clock, *, stale_query=False, bad_ack=False, renew_query=False,
                 renew_duplicate=False, corrupt_status=False, silent=False, build_tag=gp.BUILD_TAG):
        self.clock = clock
        self.options = locals().copy()
        self.silent = silent
        self.out = []
        self.sent = []
        self.pending_status = False
        self.active = None
        self.snapshot = 0
        self.last_emit = -1.
        self.session = self.seq = self.op = self.result = 0
        self.accepted = self.duplicates = 0
        self.admitted = self.completed = self.remaining = 0
        self.armed = False
        self.expiry = 0.
        self.reason = gp.StopReason.NONE
        self.last_packet = None
        self.frame_id = 0
        self.current_frame = None
        self.closed = False
        self.build_tag = build_tag
    def flags(self):
        values = {n: False for n in gp.FLAG_NAMES}
        for n in ('camera_ready', 'ddr_ready', 'warmup_ready', 'safety_ok', 'temp_valid'):
            values[n] = True
        values.update(armed=self.armed, inflight=self.current_frame is not None,
                      bank_locked=self.current_frame is not None,
                      draining=not self.armed and self.current_frame is not None,
                      core_idle=self.current_frame is None)
        if self.options['stale_query'] and self.op == gp.Opcode.QUERY:
            values['temp_stale'] = True
        return sum(int(values[n]) << i for i, n in enumerate(gp.FLAG_NAMES))
    def status(self):
        self.snapshot += 1
        fields = dict(uptime_ms=int(self.clock()*1000), session_id=self.session,
            last_received_seq=self.seq, last_accepted_seq=self.seq,
            last_opcode=self.op, last_result=self.result, flag_bits=self.flags(),
            accepted_commands=self.accepted, duplicate_commands=self.duplicates,
            admitted_frames=self.admitted, completed_frames=self.completed,
            remaining_frames=self.remaining, remaining_cycles=max(0, int((self.expiry-self.clock())*125000000)) if self.armed else 0,
            temperature_raw=0x9d60, temperature_code=0x9d6,
            temperature_age_27mhz=54000000 if self.options['stale_query'] and self.op == gp.Opcode.QUERY else 1000,
            temperature_samples=int(self.clock()*2)+10, temperature_conversions=int(self.clock()*2)*20+100,
            sensor_id=0x5640, stop_reason=int(self.reason), snapshot_seq=self.snapshot,
            safety_snapshot_age_core=100)
        if self.options['bad_ack'] and self.op == gp.Opcode.GRANT:
            fields['last_accepted_seq'] ^= 1
        packet = gp.encode_status(fields, build_tag=self.build_tag)
        if self.options['corrupt_status']:
            packet = packet[:90]+bytes([packet[90]^1])+packet[91:]
        return packet
    def queue_status(self):
        if self.current_frame is not None:
            self.pending_status = True
        else:
            self.out.append(('status', self.status()))
            self.last_emit = self.clock()
    def admit(self):
        if self.armed and self.remaining and self.current_frame is None:
            self.frame_id += 1
            self.admitted += 1
            self.remaining -= 1
            if not self.remaining:
                self.armed = False
                self.reason = gp.StopReason.FRAME_BUDGET
            # Embedded magic is ordinary pixel content, not a status event.
            payload = bytearray(614400)
            payload[100:108] = b'PGSTAT02'
            self.current_frame = encode(640, 480, self.frame_id, payload)
            self.out.append(('frame', self.current_frame))
    def write(self, packet):
        self.sent.append(packet)
        cmd = gp.decode_command(packet)
        if packet == self.last_packet:
            self.duplicates += 1
            self.result = gp.Result.DUPLICATE
            if self.options['renew_duplicate']:
                self.remaining += 1
                self.armed = True
                self.expiry = self.clock()+12
            self.queue_status()
            return len(packet)
        self.last_packet = packet
        self.seq, self.op = cmd['seq'], cmd['opcode']
        self.result = gp.Result.ACCEPTED
        self.accepted += 1
        if self.op == gp.Opcode.OPEN:
            self.session = cmd['session']
        elif self.op == gp.Opcode.GRANT:
            self.remaining = cmd['requested_frames']
            self.expiry = self.clock()+cmd['lease_ms']/1000
            self.armed = True
            self.reason = gp.StopReason.NONE
            # Actual lease feedback ACK precedes the first raw packet.
            self.out.append(('status', self.status()))
            self.last_emit = self.clock()
            self.admit()
            return len(packet)
        elif self.op == gp.Opcode.STOP:
            if self.armed:
                self.reason = gp.StopReason.OPERATOR_STOP
            self.armed = False
        elif self.op == gp.Opcode.QUERY and self.options['renew_query'] and self.armed:
            self.expiry = self.clock()+2
        self.queue_status()
        return len(packet)
    def flush(self): pass
    def close(self): self.closed = True
    def read(self, count):
        self.clock.value += .1
        if self.silent:
            return b''
        if self.armed and self.clock() >= self.expiry:
            self.armed = False
            self.reason = gp.StopReason.LEASE_EXPIRED
        if not self.out and self.current_frame is None and self.clock()-self.last_emit >= .5:
            self.queue_status()
        if not self.out:
            return b''
        kind, packet = self.out[0]
        data = packet[:count]
        if len(data) < len(packet):
            self.out[0] = (kind, packet[count:])
        else:
            self.out.pop(0)
            if kind == 'frame':
                self.completed += 1
                self.current_frame = None
                self.queue_status()
                self.pending_status = False
                self.admit()
        return data


class NegativeUART(SyntheticUART):
    """Zero-frame oracle with deliberate wrong-rejection options, never hardware."""
    def __init__(self, clock, *, fault=None):
        super().__init__(clock)
        self.model = gp.GuardedCommandModel()
        self.fault = fault
        self.fault_applied = False

    def status(self):
        fields = gp.decode_status(super().status())
        model = self.model
        fields.update(session_id=model.session_id, last_received_seq=model.last_received_seq,
            last_accepted_seq=model.last_accepted_seq, last_opcode=model.last_opcode,
            last_result=int(model.last_result), accepted_commands=model.accepted_count,
            rejected_commands=model.rejected_count, duplicate_commands=model.duplicate_count,
            rx_errors=model.rx_error_count, requested_frames=model.requested_frames,
            lease_ms=model.lease_ms)
        if self.fault_applied and self.fault == 'armed':
            fields['flag_bits'] |= 1 << gp.FLAG_NAMES.index('armed')
            fields['remaining_frames'] = 1
        if self.fault_applied and self.fault == 'admitted':
            fields['admitted_frames'] = 1
        return gp.encode_status(fields)

    def write(self, packet):
        self.sent.append(packet)
        before = self.model.rx_error_count
        event = self.model.handle_packet(packet)
        if not self.fault_applied and event['result'] == gp.Result.BAD_CRC:
            self.fault_applied = self.fault is not None
            if self.fault == 'ignore-bad-crc':
                self.model.rx_error_count = before
                self.model.last_result = gp.Result.ACCEPTED
            elif self.fault == 'bad-crc-executed':
                self.model.accepted_count += 1
            elif self.fault == 'unexpected-duplicate':
                self.model.duplicate_count += 1
            elif self.fault == 'wrong-error':
                self.model.last_result = gp.Result.BAD_VERSION
        if event.get('grant'):
            pytest.fail('the fixed negative script must never emit a legal GRANT')
        self.queue_status()
        return len(packet)


def session_plan(scenario='capture', frames=1, lease_ms=12000):
    return {'port': 'COM5', 'scenario': scenario, 'frames': frames, 'seconds': 45.,
            'frequency': '1MHz', 'lease_ms': lease_ms, 'host_session': 1234567}


@pytest.fixture
def binding():
    return dict(schema=1, camera_id='synthetic-arrival', lens_id='synthetic-lens',
                profile_id='synthetic-uncalibrated', capture_mode_id='synthetic-vga',
                eye='CAM2', image_size=[640, 480], pixel_format='RGB565_LE')


def test_fixed_negative_commands_verify_rejections_and_followup_queries(tmp_path, binding):
    clock = Clock()
    link = NegativeUART(clock)
    result = host.run_uart(link, session_plan('negative-commands', 0), binding, tmp_path, clock=clock)
    assert result['passed'] and result['saved_frames'] == 0
    assert result['legal_GRANT_commands_sent'] == 0 and len(link.sent) == 14
    assert len(result['negative_command_checks']) == 12
    final = result['last_status']
    assert (final['accepted_commands'], final['rejected_commands'], final['rx_errors'],
            final['duplicate_commands'], final['last_received_seq'], final['last_accepted_seq']) == (8, 4, 2, 0, 10, 10)
    assert not result['grant_execution_acknowledged'] and not result['frame_headers']
    assert all(final[k] == 0 for k in ('admitted_frames', 'completed_frames', 'remaining_frames', 'remaining_cycles'))
    assert all(r.get('response_verified') for r in result['tx_commands'][2:])
    # Rejected/RX-error probes are verified rejections, never accepted executions.
    checks = result['tx_commands'][2:]
    assert all(not r['execution_acknowledged'] for r in checks[::2])
    assert all(r['execution_acknowledged'] for r in checks[1::2])
    assert link.sent[2][2] == 2 and gp.crc16_ccitt_false(link.sent[2][2:14]) != int.from_bytes(link.sent[2][14:16], 'little')
    assert link.sent[4][2] == 1 and gp.crc16_ccitt_false(link.sent[4][2:14]) == int.from_bytes(link.sent[4][14:16], 'little')
    grants = [gp.decode_command(p) for p in link.sent[6:] if p[3] == gp.Opcode.GRANT]
    assert [p['requested_frames'] for p in grants] == [0, 4]
    assert not (tmp_path/'session-summary.json').exists()  # run_uart returns data; orchestrator seals it.
    wire = (tmp_path/'received-wire.bin').read_bytes()
    assert len(wire) % 128 == 0 and b'PGFRAME1' not in wire


@pytest.mark.parametrize('fault', ['ignore-bad-crc', 'bad-crc-executed', 'unexpected-duplicate',
                                  'wrong-error', 'armed', 'admitted'])
def test_negative_command_wrong_ack_counters_or_admission_never_pass(tmp_path, binding, fault):
    clock = Clock()
    link = NegativeUART(clock, fault=fault)
    with pytest.raises((RuntimeError, TimeoutError)):
        host.run_uart(link, session_plan('negative-commands', 0), binding, tmp_path, clock=clock)
    assert not any(p[3] == gp.Opcode.GRANT for p in link.sent)


@pytest.mark.parametrize('target', [t for t in host.VARIANTS if t != host.TARGET])
def test_negative_commands_are_not_a_payload_entry_for_other_variants(tmp_path, binding, target):
    plan = {**session_plan('negative-commands', 0), 'target': target}
    with pytest.raises(ValueError, match='only for natural CAM2'):
        host.run_uart(NegativeUART(Clock()), plan, binding, tmp_path)
    with pytest.raises(ValueError, match='only for natural CAM2'):
        host.prepare_plan('missing.json', 'missing', tmp_path, port='COM5',
                          target=target, scenario='negative-commands', frames=0)
    with pytest.raises(ValueError, match='only for natural CAM2'):
        host.execute_plan(plan)


@pytest.mark.parametrize('frames', [1, 2, 3])
def test_negative_commands_require_explicit_zero_frame_budget(frames):
    plan = session_plan('negative-commands', frames)
    plan.pop('host_session')
    with pytest.raises(ValueError): host._limits(**plan)


@pytest.mark.parametrize('scenario,frames,lease', [
    ('boot-idle', 0, 12000), ('idle', 0, 12000), ('capture', 1, 12000),
    ('capture', 2, 24000), ('duplicate-grant', 1, 12000),
    ('lease-expiry', 2, 2000), ('host-silence', 2, 2000), ('stop-drain', 2, 24000),
])
def test_synthetic_packet_boundary_scenarios(tmp_path, binding, scenario, frames, lease):
    clock = Clock()
    link = SyntheticUART(clock)
    result = host.run_uart(link, session_plan(scenario, frames, lease), binding, tmp_path, clock=clock)
    assert result['passed'] and result['source_kind'] == 'offline_uart_replay'
    assert result['saved_frames'] == (frames if scenario in ('capture', 'duplicate-grant') else 0 if frames == 0 else 1)
    assert result['parser_rejected'] == 0
    assert result['wire_sha256'] == host.hw.sha(tmp_path/'received-wire.bin')
    if scenario == 'boot-idle': assert not link.sent
    if scenario == 'idle': assert all(gp.decode_command(p)['opcode'] != gp.Opcode.GRANT for p in link.sent)
    if scenario == 'duplicate-grant':
        grants = [p for p in link.sent if gp.decode_command(p)['opcode'] == gp.Opcode.GRANT]
        assert len(grants) == 2 and grants[0] == grants[1]
    if scenario == 'lease-expiry':
        queries = [p for p in link.sent if gp.decode_command(p)['opcode'] == gp.Opcode.QUERY]
        assert 5 <= len(queries) <= 17
        assert result['last_status']['remaining_cycles'] == 0
    if scenario == 'host-silence':
        assert len(link.sent) == 3 and result['host_silence_means'].startswith('COM remained')
    for frame in result['frames']:
        assert frame['source_kind'] == 'offline_uart_replay'
        assert frame['hardware_accessed'] is False
        assert frame['geometry_applied'] is None


@pytest.mark.parametrize('option', ['stale_query', 'bad_ack', 'renew_query', 'renew_duplicate', 'corrupt_status', 'silent'])
def test_bad_ack_safety_replay_and_renewal_fail_closed(tmp_path, binding, option):
    clock = Clock()
    link = SyntheticUART(clock, **{option: True})
    scenario = 'lease-expiry' if option == 'renew_query' else 'duplicate-grant' if option == 'renew_duplicate' else 'capture'
    plan = session_plan(scenario, 2 if scenario == 'lease-expiry' else 1, 2000 if scenario == 'lease-expiry' else 12000)
    with pytest.raises((RuntimeError, TimeoutError)):
        host.run_uart(link, plan, binding, tmp_path, clock=clock)
    if option in ('stale_query', 'corrupt_status', 'silent'):
        assert not any(gp.decode_command(p)['opcode'] == gp.Opcode.GRANT for p in link.sent)


def test_coalesced_query_ack_cannot_hide_untransmitted_duplicates(tmp_path, binding):
    clock = Clock()
    link = SyntheticUART(clock)
    original_status = link.status
    def impossible_duplicate():
        packet = original_status()
        if link.op == gp.Opcode.QUERY and link.seq >= 4:
            fields = gp.decode_status(packet)
            fields['duplicate_commands'] = 1
            packet = gp.encode_status(fields)
        return packet
    link.status = impossible_duplicate
    with pytest.raises(RuntimeError, match='coalesced QUERY'):
        host.run_uart(link, session_plan('lease-expiry', 2, 2000), binding, tmp_path, clock=clock)


@pytest.mark.parametrize('scenario', ['boot-idle', 'idle'])
def test_zero_frames_without_camera_ddr_ready_is_not_acceptance(tmp_path, binding, scenario):
    clock = Clock()
    link = SyntheticUART(clock)
    original_flags = link.flags
    def not_ready():
        return original_flags() & ~(1 << gp.FLAG_NAMES.index('camera_ready')) & ~(1 << gp.FLAG_NAMES.index('ddr_ready'))
    link.flags = not_ready
    with pytest.raises(TimeoutError):
        host.run_uart(link, session_plan(scenario, 0), binding, tmp_path, clock=clock)
    assert not any(gp.decode_command(p)['opcode'] == gp.Opcode.GRANT for p in link.sent)


@pytest.mark.parametrize('values', [
    dict(port='COM0'), dict(frames=True), dict(seconds=float('nan')), dict(seconds=61),
    dict(lease_ms=24001), dict(frequency='100KHz'), dict(scenario='forever'),
    dict(scenario='idle', frames=1), dict(scenario='lease-expiry', frames=1, lease_ms=2000),
    dict(scenario='stop-drain', frames=2, lease_ms=1000),
])
def test_plan_limits_reject_unsafe_or_unbounded_inputs(values):
    args = dict(port='COM5', scenario='capture', frames=1, seconds=45, lease_ms=12000, frequency='1MHz')
    args.update(values)
    with pytest.raises(ValueError): host._limits(**args)


@pytest.fixture
def planned(tmp_path, monkeypatch, binding):
    """Tiny explicitly synthetic build fixture, not an actual PDS artifact."""
    root = tmp_path/'p'
    board = root/'board'
    board.mkdir(parents=True)
    scratch = root/'s'
    scratch.mkdir(parents=True)
    base = scratch/'b'
    (base/'place_route').mkdir(parents=True)
    (base/'generate_bitstream').mkdir()
    reference = host.capture.load_json(ROOT/'board/raw_camera_capture_cam2_ref-pins.json')
    def save(path, value):
        path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    save(board/'raw_camera_capture_cam2_ref-pins.json', reference)
    pins = {**reference, 'uart_rxd': 'B24'}
    pinpath = board/(host.TARGET+'-pins.json')
    save(pinpath, pins)
    top = board/(host.TARGET+'.v')
    top.write_text('// synthetic unit-test placeholder, not synthesized\n')
    sources = {str(p.relative_to(root)).replace('\\', '/'): host.hw.sha(p) for p in (top, pinpath)}
    save(board/(host.TARGET+'-sources.json'), {'target': host.TARGET,
        'source_files': list(sources), 'SourceSHA256': sources,
        'RawCaptureContract': host.RAW_CONTRACT, 'GuardedControlContract': gp.GUARDED_CONTROL_CONTRACT})
    (root/'output/project').mkdir(parents=True)
    save(root/'output/project/guarded-protocol-v2.json', gp.protocol_spec())
    bit = base/'generate_bitstream'/(host.TARGET+'.sbit')
    bit.write_bytes(b'synthetic mock bitstream; never configure')
    timing = base/'place_route'/(host.TARGET+'_timing_summary_after_hold_fix.txt')
    timing.write_text('Design Summary : All Constraints Met.\n')
    prr = base/'place_route'/(host.TARGET+'_prr.prt')
    prr.write_text(''.join(f'{pad}|mock|bank|type|{port}|input|YES\n' for port, pad in pins.items()))
    manifest = dict(Target=host.TARGET, Device='PG2L100H', Package='FBG676', SCBV='High Voltage',
        UnusedIO='UNUSED', Bitstream=str(bit), SHA256=host.hw.sha(bit),
        TimingReport=str(timing), TimingSHA256=host.hw.sha(timing),
        PinReport=str(prr), PinReportSHA256=host.hw.sha(prr), SourceSHA256=sources,
        RawCaptureContract=host.RAW_CONTRACT, GuardedControlContract=gp.GUARDED_CONTROL_CONTRACT)
    save(base/'validated-build.json', manifest)
    review_record = root/'synthetic-review.json'
    save(review_record, {'kind': 'synthetic unit test, no physical review'})
    reviewed = copy.deepcopy(binding)
    reviewed['connection_review'] = {key: key != 'programmed_bound_bitstream' for key in host.capture.CONNECTION_FIELDS}
    reviewed['connection_review_basis'] = {'review_record': {'path': str(review_record), 'sha256': host.hw.sha(review_record)}}
    review_path = root/'synthetic-operator-binding.json'
    save(review_path, reviewed)
    pds = root/'synthetic-pds'
    pds.mkdir()
    idlebit = root/'synthetic-heartbeat.sbit'
    idlebit.write_bytes(b'synthetic idle unit test')
    monkeypatch.setattr(host, 'ROOT', root)
    monkeypatch.setattr(host.capture, 'ROOT', root)
    monkeypatch.setattr(host.hw, 'APPROVED', scratch)
    monkeypatch.setattr(host.idle, 'APPROVED', scratch)
    monkeypatch.setattr(host.hw, 'resolve_pds_bin', lambda value=None: pds)
    monkeypatch.setattr(host, '_helpers', lambda target=host.TARGET: {'synthetic_unit_test': 'no_hardware'})
    monkeypatch.setattr(host.idle, 'validate_heartbeat', lambda: {'target': 'heartbeat', 'bitstream_path': str(idlebit)})
    monkeypatch.setattr(host.hw.subprocess, 'Popen', lambda *a, **k: pytest.fail('no actual subprocess in tests'))
    plan = host.prepare_plan(review_path, base, scratch, port='COM5')
    return plan, root, base, save


def test_default_plan_has_no_hardware_and_binds_fresh_guarded_role(planned):
    plan, _, _, _ = planned
    assert plan['executed'] is False and plan['hardware_accessed'] is False
    assert plan['host_session'] != 0
    assert plan['idle_plan']['program_budget']['client_timeout_seconds'] == 90.
    assert host.idle.validate_program_budget(plan['idle_plan']) == plan['idle_plan']['program_budget']
    binding = host.capture.load_json(plan['program_plan']['validation']['binding_path'])
    assert binding['connection_review']['programmed_bound_bitstream'] is False
    assert binding['guarded_control_contract'] == gp.GUARDED_CONTROL_CONTRACT
    assert binding['build_binding']['bitstream']['path'].endswith(host.TARGET+'.sbit')
    assert 'synthetic unit test' in host.capture.load_json(binding['connection_review_basis']['review_record']['path'])['kind']


@pytest.mark.parametrize('part', ['bit', 'source', 'timing', 'pin-report', 'contract', 'target'])
def test_bound_guarded_build_rejects_changes(planned, part):
    plan, root, base, save = planned
    manifest = host.capture.load_json(base/'validated-build.json')
    if part == 'bit': Path(manifest['Bitstream']).write_bytes(b'changed')
    elif part == 'source': (root/'board'/(host.TARGET+'.v')).write_text('changed')
    elif part == 'timing': Path(manifest['TimingReport']).write_text('timing failed')
    elif part == 'pin-report': Path(manifest['PinReport']).write_text('AA22|bad|bank|type|cam_data[5]|input|YES\n')
    elif part == 'contract': manifest['GuardedControlContract'] = {'protocol': 'old'}; save(base/'validated-build.json', manifest)
    elif part == 'target': manifest['Target'] = 'camera_isp_probe'; save(base/'validated-build.json', manifest)
    with pytest.raises(ValueError): host.validate_guarded_build(base)


@pytest.mark.parametrize('record', ['derived_review_binding', 'review_record'])
def test_operator_review_evidence_is_rechecked_before_programming(planned, record):
    plan, _, base, _ = planned
    validation = plan['program_plan']['validation']
    binding = validation['binding']
    item = binding[record] if record == 'derived_review_binding' else binding['connection_review_basis'][record]
    Path(item['path']).write_text('modified review evidence')
    with pytest.raises(ValueError, match='SHA256 differs'):
        host.validate_program_binding(validation['binding_path'], base)


def fake_program_success(plan):
    work = Path(plan['workdir'])
    binding = copy.deepcopy(plan['validation']['binding'])
    binding['connection_review']['programmed_bound_bitstream'] = True
    host.hw._new_json(work/'session-binding.json', binding)
    return {'passed': True, 'done_confirmed': True, 'programming_attempted': True,
            'hardware_accessed': True, 'session_binding_path': str(work/'session-binding.json')}


@pytest.mark.parametrize('fault', [None, 'wrong-error'])
def test_negative_plan_default_is_inert_and_mock_execution_always_restores(planned, monkeypatch, fault):
    _, root, base, _ = planned
    plan = host.prepare_plan(root/'synthetic-operator-binding.json', base, host.hw.APPROVED,
                             port='COM5', scenario='negative-commands', frames=0)
    assert not plan['hardware_accessed'] and not plan['executed']
    assert not (Path(plan['workdir'])/'result.json').exists()
    clock = Clock()
    link = NegativeUART(clock, fault=fault)
    order = []
    original_run = host.run_uart
    def close():
        order.append('closed')
        link.closed = True
    def restore(*args, **kwargs):
        assert link.closed
        order.append('heartbeat')
        return {'passed': True, 'done_confirmed': True, 'hardware_accessed': True,
                'synthetic_test_fixture': True}
    monkeypatch.setattr(link, 'close', close)
    monkeypatch.setattr(host, 'execute_program', fake_program_success)
    monkeypatch.setattr(host, '_serial', lambda port: link)
    monkeypatch.setattr(host, 'run_uart', lambda *a, **kw: original_run(*a, **kw, clock=clock))
    monkeypatch.setattr(host.idle, 'execute_plan', restore)
    result = host.execute_plan(plan)
    assert result['passed'] == (fault is None)
    assert result['idle_restoration_attempted'] and result['idle_done_confirmed']
    assert order == ['closed', 'heartbeat']
    assert Path(plan['workdir'], 'received-wire.bin').is_file()
    assert (result['session_summary'] is not None) == (fault is None)


@pytest.mark.parametrize('failure', ['none', 'uart', 'interrupt', 'serial-close', 'idle-fail', 'unknown-program', 'malformed-program', 'nondict-program'])
def test_orchestrator_closes_com_and_attempts_idle_on_all_active_outcomes(planned, monkeypatch, failure):
    plan, _, _, _ = planned
    order = []
    class Link:
        def close(self):
            order.append('close')
            if failure == 'serial-close': raise RuntimeError('mock COM close failed')
    def program(p):
        order.append('program')
        if failure == 'unknown-program': raise KeyboardInterrupt()
        if failure == 'malformed-program': return {'passed': False, 'done_confirmed': False}
        if failure == 'nondict-program': return 17
        return fake_program_success(p)
    def acquire(*args, **kwargs):
        order.append('uart')
        if failure == 'uart': raise RuntimeError('mock invalid CRC')
        if failure == 'interrupt': raise KeyboardInterrupt()
        return {'passed': True, 'saved_frames': 1}
    def restore(*args, **kwargs):
        order.append('idle')
        return {'passed': failure != 'idle-fail', 'done_confirmed': failure != 'idle-fail', 'hardware_accessed': True}
    monkeypatch.setattr(host, 'execute_program', program)
    monkeypatch.setattr(host, '_serial', lambda port: Link())
    monkeypatch.setattr(host, 'run_uart', acquire)
    monkeypatch.setattr(host.idle, 'execute_plan', restore)
    result = host.execute_plan(plan)
    assert result['idle_restoration_attempted'] and order[-1] == 'idle'
    assert result['passed'] == (failure == 'none')
    if failure in ('unknown-program', 'malformed-program', 'nondict-program'):
        assert result['programming_state_unknown'] and 'uart' not in order
    else:
        assert order.index('close') < order.index('idle')


def test_modified_sealed_plan_rejected_before_any_hardware(planned, monkeypatch):
    plan, _, _, _ = planned
    plan['frames'] = 3
    monkeypatch.setattr(host, 'execute_program', lambda p: pytest.fail('must not program'))
    with pytest.raises(ValueError, match='changed'): host.execute_plan(plan)


@pytest.mark.parametrize('change', ['missing', 'altered', 'different-timeout'])
def test_recovery_budget_rejected_before_active_program_even_if_reserialized(planned, monkeypatch, change):
    plan, _, _, save = planned
    exit_plan = plan['idle_plan']
    if change == 'missing':
        exit_plan.pop('program_budget')
    elif change == 'altered':
        exit_plan['program_budget']['wire_seconds'] += 1
    else:
        exit_plan['program_budget'] = host.idle.program_budget(exit_plan['validation'], exit_plan['frequency'], 100.)
    save(Path(plan['workdir'])/'plan.json', plan)
    save(Path(exit_plan['workdir'])/'plan.json', exit_plan)
    monkeypatch.setattr(host, 'execute_program', lambda p: pytest.fail('must reject recovery budget before active program'))
    with pytest.raises(ValueError, match='budget'):
        host.execute_plan(plan)


def test_direct_guarded_program_rejects_100khz_before_any_process(planned):
    plan, _, _, _ = planned
    program = copy.deepcopy(plan['program_plan'])
    program['frequency'] = '100KHz'
    with pytest.raises(ValueError): host.execute_program(program)


def test_even_reserialized_nested_frequency_mismatch_is_rejected(planned):
    plan, _, _, save = planned
    plan['program_plan']['frequency'] = '100KHz'
    save(Path(plan['workdir'])/'plan.json', plan)
    with pytest.raises(ValueError, match='nested'): host.execute_plan(plan)


def test_wrong_device_never_attempts_program_and_only_owned_handles_are_stopped(planned, monkeypatch):
    plan, _, _, _ = planned
    calls, stopped = [], []
    class Child:
        pid = 24680
    def start(command, work, owned, stage):
        owned.append(Child())
        calls.append(stage)
        return owned[-1]
    def client(p, stage, owned, seconds):
        calls.append(stage)
        return 'PG2L50H\nThe ID value is: 0x00602899\n'
    monkeypatch.setattr(host.hw, 'listening_pids', lambda port: set())
    monkeypatch.setattr(host.hw, '_start_owned', start)
    monkeypatch.setattr(host.hw, '_await_owned_server', lambda p: None)
    monkeypatch.setattr(host.hw, '_owned_server_check', lambda p: None)
    monkeypatch.setattr(host.hw, '_client', client)
    monkeypatch.setattr(host.hw, '_stop_owned', lambda owned: (stopped.extend(owned) or ([], [])))
    result = host.execute_program(plan['program_plan'])
    assert not result['passed'] and not result['programming_attempted']
    assert calls == ['server', 'scan'] and len(stopped) == 1 and stopped[0].pid == 24680


def test_foreign_server_is_never_used_or_killed(planned, monkeypatch):
    plan, _, _, _ = planned
    seen = []
    monkeypatch.setattr(host.hw, 'listening_pids', lambda port: {99999})
    monkeypatch.setattr(host.hw, '_start_owned', lambda *args: pytest.fail('must not create a competing server'))
    monkeypatch.setattr(host.hw, '_stop_owned', lambda owned: (seen.extend(owned) or ([], [])))
    result = host.execute_program(plan['program_plan'])
    assert not result['passed'] and not result['hardware_accessed'] and seen == []


@pytest.fixture(params=tuple(host.VARIANTS))
def variant_plan(planned, monkeypatch, request):
    _, root, _, save = planned
    target = request.param
    variant = host.variant_for(target)
    scratch = host.hw.APPROVED
    # Keep the mock route path short enough for Windows' legacy260-character limit.
    build = scratch/'v'
    (build/'place_route').mkdir(parents=True)
    (build/'generate_bitstream').mkdir()
    board = root/'board'
    cam1_reference = host.capture.load_json(ROOT/'board/camera_sync-pins.json')
    save(board/'camera_sync-pins.json', cam1_reference)
    pins = host.capture.load_json(board/'raw_camera_capture_cam2_ref-pins.json')
    if variant.eye == 'CAM1':
        pins.update({n: p for n, p in cam1_reference.items() if n.startswith('cam_')})
    pins['uart_rxd'] = 'B24'
    if variant.mode == 'cam1-guarded-isolated': pins['cam2_hold_rst_n'] = 'Y20'
    pinpath = board/(target+'-pins.json')
    save(pinpath, pins)
    top = board/(target+'.v')
    top.write_text('// synthetic variant fixture, not FPGA evidence\n' +
                   ('camera #(.I2C_QUARTER_CYCLES(270)) synthetic();\n' if variant.mode == 'cam1-guarded-sccb25' else '') +
                   ("inout cam2_hold_rst_n; assign cam2_hold_rst_n=1'b0;\n" if variant.mode == 'cam1-guarded-isolated' else ''))
    sources = {str(p.relative_to(root)).replace('\\', '/'): host.hw.sha(p) for p in (top, pinpath)}
    contract = {**gp.GUARDED_CONTROL_CONTRACT, 'build_tag': variant.build_tag}
    prepared = {'target': target, 'source_files': list(sources), 'SourceSHA256': sources,
                'RawCaptureContract': host.RAW_CONTRACT, 'GuardedControlContract': contract}
    sensor_contract = host._expected_sensor_contract(variant)
    if sensor_contract is not None: prepared['SensorOutputContract'] = sensor_contract
    trial_contract = host._expected_sccb_trial_contract(variant)
    if trial_contract is not None: prepared['SCCBTrialContract'] = trial_contract
    reset_contract = host._expected_other_sensor_reset_contract(variant)
    if reset_contract is not None: prepared['OtherSensorResetTrialContract'] = reset_contract
    if variant.eye == 'CAM1':
        prepared.update(camera_id=variant.camera_id_tag, connector_slot_tag=1,
                        ReferenceSHA256={'board/camera_sync-pins.json': host.hw.sha(board/'camera_sync-pins.json')})
    save(board/(target+'-sources.json'), prepared)
    bit = build/'generate_bitstream'/(target+'.sbit')
    bit.write_bytes(b'synthetic variant bytes, never program')
    timing = build/'place_route'/(target+'_timing_summary_after_hold_fix.txt')
    timing.write_text('Design Summary : All Constraints Met.\n')
    prr = build/'place_route'/(target+'_prr.prt')
    prr.write_text(''.join(f"{pad}|mock|bank|type|{port}|{'inout' if port == 'cam2_hold_rst_n' else 'input'}|YES\n" for port, pad in pins.items()))
    manifest = dict(Target=target, Device='PG2L100H', Package='FBG676', SCBV='High Voltage',
        UnusedIO='UNUSED', Bitstream=str(bit), SHA256=host.hw.sha(bit),
        TimingReport=str(timing), TimingSHA256=host.hw.sha(timing), PinReport=str(prr),
        PinReportSHA256=host.hw.sha(prr), SourceSHA256=sources,
        RawCaptureContract=host.RAW_CONTRACT, GuardedControlContract=contract)
    if sensor_contract is not None: manifest['SensorOutputContract'] = sensor_contract
    if trial_contract is not None: manifest['SCCBTrialContract'] = trial_contract
    if reset_contract is not None: manifest['OtherSensorResetTrialContract'] = reset_contract
    if variant.eye == 'CAM1':
        manifest.update(CameraID=variant.camera_id_tag, ConnectorSlot=1, ReferenceSHA256=prepared['ReferenceSHA256'])
    save(build/'validated-build.json', manifest)
    original_review = host.capture.load_json(root/'synthetic-operator-binding.json')
    original_review.update(eye=variant.eye, camera_id='synthetic-'+variant.eye,
                           lens_id='synthetic-lens-'+variant.eye, profile_id='synthetic-uncalibrated-'+variant.eye)
    review = root/('synthetic-review-'+variant.mode+'.json')
    save(review, original_review)
    def factory(selected):
        if not selected.factory: return None, None
        return host.capture.load_json(board/(selected.target+'-sources.json')), host._expected_sensor_contract(selected)
    monkeypatch.setattr(host, '_variant_factory', factory)
    plan = host.prepare_plan(review, build, scratch, port='COM5', target=target)
    return plan, variant, root, build, save


def test_each_variant_has_explicit_sealed_identity_and_matching_binding(variant_plan):
    plan, variant, _, build, _ = variant_plan
    validation = plan['program_plan']['validation']
    binding = validation['binding']
    assert plan['target'] == plan['program_plan']['target'] == variant.target
    assert plan['variant'] == host.asdict(variant) == binding['guarded_variant']
    assert binding['eye'] == variant.eye and binding['capture_mode_id'] == variant.capture_mode_id
    assert binding['guarded_control_contract']['build_tag'] == variant.build_tag
    assert host.validate_program_binding(validation['binding_path'], build, target=variant.target) == validation
    if variant.mode == 'sensor-internal-bars':
        assert binding['calibration_scene_eligible'] is False
        assert 'uncalibrated' in binding['profile_id'] and 'bars' in binding['profile_id']
    else:
        assert 'sensor_output_contract' not in binding and 'input_origin' not in binding
    if variant.mode == 'cam1-guarded-sccb25':
        assert binding['sccb_trial_contract'] == host._expected_sccb_trial_contract(variant)
        assert validation['build']['sccb_trial_contract'] == binding['sccb_trial_contract']
    else:
        assert 'sccb_trial_contract' not in binding
    if variant.mode == 'cam1-guarded-isolated':
        assert binding['other_sensor_reset_trial_contract'] == host._expected_other_sensor_reset_contract(variant)
        assert validation['build']['other_sensor_reset_trial_contract'] == binding['other_sensor_reset_trial_contract']
    else:
        assert 'other_sensor_reset_trial_contract' not in binding


def test_cross_variant_artifact_is_rejected_even_if_other_tag_is_declared(variant_plan):
    _, variant, _, build, _ = variant_plan
    other = next(t for t in host.VARIANTS if t != variant.target)
    with pytest.raises(ValueError, match='exact guarded'):
        host.validate_guarded_build(build, target=other)


@pytest.mark.parametrize('part', ['eye', 'mode', 'tag'])
def test_binding_eye_mode_and_tag_mismatches_rejected(variant_plan, part):
    plan, variant, _, build, save = variant_plan
    p = Path(plan['program_plan']['validation']['binding_path'])
    binding = host.capture.load_json(p)
    if part == 'eye': binding['eye'] = 'CAM1' if variant.eye == 'CAM2' else 'CAM2'
    elif part == 'mode': binding['capture_mode_id'] = 'other-variant'
    else: binding['guarded_control_contract']['build_tag'] ^= 1
    save(p, binding)
    with pytest.raises(ValueError): host.validate_program_binding(p, build, target=variant.target)


def test_changed_eye_pin_cannot_pass_by_rehashing_source_manifest(variant_plan):
    _, variant, root, build, save = variant_plan
    pinpath = root/'board'/(variant.target+'-pins.json')
    pins = host.capture.load_json(pinpath)
    pins['cam_data[5]'] = 'AA23' if variant.eye == 'CAM1' else 'Y21'
    save(pinpath, pins)
    prepared_path = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(prepared_path)
    prepared['SourceSHA256'][str(pinpath.relative_to(root)).replace('\\', '/')] = host.hw.sha(pinpath)
    save(prepared_path, prepared)
    manifest = host.capture.load_json(build/'validated-build.json')
    manifest['SourceSHA256'] = prepared['SourceSHA256']
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='electrical-eye'):
        host.validate_guarded_build(build, target=variant.target)


def test_variant_parser_requires_its_explicit_runtime_tag(variant_plan):
    plan, variant, _, _, _ = variant_plan
    binding = plan['program_plan']['validation']['binding']
    wrong = next(v for v in host.VARIANTS.values() if v.build_tag != variant.build_tag)
    clock = Clock()
    link = SyntheticUART(clock, build_tag=wrong.build_tag)
    with pytest.raises((ValueError, RuntimeError)):
        host.run_uart(link, plan, binding, Path(plan['workdir']), clock=clock)
    assert not link.sent


def test_variant_replay_metadata_never_upgrades_to_physical_or_optical(variant_plan):
    plan, variant, _, _, _ = variant_plan
    binding = plan['program_plan']['validation']['binding']
    clock = Clock()
    result = host.run_uart(SyntheticUART(clock, build_tag=variant.build_tag), plan, binding,
                           Path(plan['workdir']), clock=clock)
    assert result['passed'] and result['source_kind'] == 'offline_uart_replay'
    frame = result['frames'][0]
    assert frame['identity_binding']['eye'] == variant.eye and frame['source_kind'] == 'offline_uart_replay'
    assert frame['hardware_accessed'] is False and frame['geometry_applied'] is None
    assert host.hw.sha(frame['metadata_path']) == frame['metadata_sha256']
    assert host.capture.load_json(frame['metadata_path'])['guarded_variant'] == host.asdict(variant)
    if variant.mode == 'cam1-guarded-sccb25':
        assert frame['sccb_trial_contract'] == result['sccb_trial_contract'] == host._expected_sccb_trial_contract(variant)
    else:
        assert 'sccb_trial_contract' not in frame and 'sccb_trial_contract' not in result
    if variant.mode == 'cam1-guarded-isolated':
        assert frame['other_sensor_reset_trial_contract'] == result['other_sensor_reset_trial_contract'] == host._expected_other_sensor_reset_contract(variant)
    else:
        assert 'other_sensor_reset_trial_contract' not in frame and 'other_sensor_reset_trial_contract' not in result
    if variant.mode == 'sensor-internal-bars':
        for record in (frame, result):
            assert record['input_origin'] == 'ov5640_internal_pre_isp_test_pattern'
            assert record['sensor_output_contract'] == host._expected_sensor_contract(variant)
            assert record['calibration_scene_eligible'] is False
        assert host._reported_source_kind('physical_native_camera', variant) == 'physical_sensor_internal_test_pattern'
    else:
        assert 'sensor_output_contract' not in frame and 'input_origin' not in frame
    assert host.TARGET == 'raw_camera_capture_cam2_guarded' and gp.BUILD_TAG == 0x52473201


def test_natural_and_pattern_sensor_contracts_cannot_be_interchanged(variant_plan):
    _, variant, _, build, save = variant_plan
    manifest = host.capture.load_json(build/'validated-build.json')
    if variant.mode == 'sensor-internal-bars':
        manifest['SensorOutputContract']['calibration_scene_eligible'] = 0  # wrong JSON type, even though0==False
    else:
        manifest['SensorOutputContract'] = host._expected_sensor_contract(host.VARIANTS['raw_camera_capture_cam2_guarded_bars'])
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError): host.validate_guarded_build(build, target=variant.target)


def test_synthetic_live_kind_mapping_only_enriches_fresh_metadata(variant_plan, monkeypatch):
    plan, variant, _, _, _ = variant_plan
    # Exercise live-kind serialization with an explicit synthetic build fixture.
    # No serial/program path is invoked and this is never a physical result.
    binding = plan['program_plan']['validation']['binding']
    build_record = host.capture.validate_live_binding(binding,
        base_dir=Path(plan['program_plan']['validation']['binding_path']).parent, require_programmed=False)
    build_record['synthetic_test_fixture'] = True
    work = Path(plan['workdir'])
    historical = work/'unrelated-sealed-history.json'
    historical.write_bytes(b'{"sealed":true,"synthetic_test_fixture":true}\n')
    history_sha = host.hw.sha(historical)
    original_save = host.capture.save_frame
    before = {}
    def record_new(*args, **kwargs):
        descriptor = original_save(*args, **kwargs)
        for key in ('raw_path', 'image_path', 'metadata_path'):
            before[key] = host.hw.sha(descriptor[key])
        return descriptor
    monkeypatch.setattr(host.capture, 'save_frame', record_new)
    payload = bytes(614400)
    frame = Frame(640, 480, 1, zlib.crc32(payload), payload)
    descriptor = host._save_guarded_frame(frame, binding, work, 'synthetic-kind-mapping',
        variant=variant, source_kind='physical_native_camera', build_record=build_record)
    assert descriptor['build_binding']['synthetic_test_fixture'] is True
    assert descriptor['metadata_sha256'] != before['metadata_path']
    assert host.hw.sha(descriptor['raw_path']) == before['raw_path']
    assert host.hw.sha(descriptor['image_path']) == before['image_path']
    if variant.mode == 'sensor-internal-bars':
        assert descriptor['source_kind'] == 'physical_sensor_internal_test_pattern'
        assert descriptor['calibration_scene_eligible'] is False
        assert descriptor['input_origin'] == 'ov5640_internal_pre_isp_test_pattern'
        assert descriptor['sensor_output_contract'] == host._expected_sensor_contract(variant)
    else:
        assert descriptor['source_kind'] == 'physical_native_camera'
        assert 'sensor_output_contract' not in descriptor
    sealed = host.hw.sha(descriptor['metadata_path'])
    with pytest.raises(ValueError, match='never overwrite'):
        host._save_guarded_frame(frame, binding, work, 'synthetic-kind-mapping',
            variant=variant, source_kind='physical_native_camera', build_record=build_record)
    assert host.hw.sha(descriptor['metadata_path']) == sealed
    assert host.hw.sha(historical) == history_sha


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_sccb25'], indirect=True)
@pytest.mark.parametrize('value', ['68', 'True', '269', '270+0'])
def test_sccb25_parameter_change_cannot_pass_by_rehashing(variant_plan, value):
    _, variant, root, build, save = variant_plan
    top = root/'board'/(variant.target+'.v')
    top.write_text(top.read_text().replace('I2C_QUARTER_CYCLES(270)', 'I2C_QUARTER_CYCLES('+value+')'))
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p)
    prepared['SourceSHA256'][str(top.relative_to(root)).replace('\\', '/')] = host.hw.sha(top)
    save(p, prepared)
    manifest = host.capture.load_json(build/'validated-build.json')
    manifest['SourceSHA256'] = prepared['SourceSHA256']
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='I2C_QUARTER_CYCLES'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_sccb25'], indirect=True)
def test_sccb25_cannot_skip_its_readonly_exact_clone_factory(variant_plan, monkeypatch):
    _, variant, _, build, _ = variant_plan
    monkeypatch.setattr(host, '_variant_factory', lambda selected: (None, None))
    with pytest.raises(ValueError, match='clone factory'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_sccb25'], indirect=True)
def test_sccb25_uses_the_specific_factory_and_preserves_factory_rejection(variant_plan, monkeypatch):
    _, variant, _, build, _ = variant_plan
    import prepare_guarded_cam1_sccb25 as factory
    calls = []
    def reject():
        calls.append('SCCB25 exact clone')
        raise ValueError('synthetic changed PLL/mask/readback rejected by factory')
    monkeypatch.setattr(factory, 'verify_clone', reject, raising=False)
    monkeypatch.setattr(host, '_variant_factory', REAL_VARIANT_FACTORY)
    with pytest.raises(ValueError, match='changed PLL/mask/readback'):
        host.validate_guarded_build(build, target=variant.target)
    assert calls == ['SCCB25 exact clone']


def test_sccb_trial_contract_cannot_be_interchanged_with_ordinary_variants(variant_plan):
    _, variant, root, build, save = variant_plan
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p)
    manifest = host.capture.load_json(build/'validated-build.json')
    if variant.mode == 'cam1-guarded-sccb25':
        trial = {**manifest['SCCBTrialContract'], 'unexpected': True}
    else:
        trial = host._expected_sccb_trial_contract(host.VARIANTS['raw_camera_capture_cam1_guarded_sccb25'])
    prepared['SCCBTrialContract'] = manifest['SCCBTrialContract'] = trial
    save(p, prepared)
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='SCCB25'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_sccb25'], indirect=True)
def test_sccb25_binding_contract_is_required_even_with_matching_eye_tag(variant_plan):
    plan, variant, _, build, save = variant_plan
    p = Path(plan['program_plan']['validation']['binding_path'])
    binding = host.capture.load_json(p)
    binding.pop('sccb_trial_contract')
    save(p, binding)
    with pytest.raises(ValueError, match='SCCB25'):
        host.validate_program_binding(p, build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_sccb25'], indirect=True)
@pytest.mark.parametrize('value', ['270', 270.0, True])
def test_sccb25_trial_parameter_json_types_are_not_coerced(variant_plan, value):
    _, variant, root, build, save = variant_plan
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p)
    manifest = host.capture.load_json(build/'validated-build.json')
    trial = {**manifest['SCCBTrialContract'], 'quarter_cycles': value}
    manifest['SCCBTrialContract'] = prepared['SCCBTrialContract'] = trial
    save(p, prepared)
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='SCCB25'):
        host.validate_guarded_build(build, target=variant.target)


def test_only_sccb25_helper_seal_adds_the_transitive_cam1_factory(monkeypatch):
    monkeypatch.setattr(host.hw, 'sha', lambda p: str(p))
    target = 'raw_camera_capture_cam1_guarded_sccb25'
    helpers = REAL_HELPERS(target)
    assert 'tools/prepare_guarded_cam1_sccb25.py' in helpers
    assert 'tools/prepare_guarded_cam1.py' in helpers
    assert 'tools/prepare_guarded_cam1.py' not in REAL_HELPERS(host.TARGET)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
@pytest.mark.parametrize('value', ["1'b1", "1'bz"])
def test_isolated_reset_drive_cannot_change_after_rehash(variant_plan, value):
    _, variant, root, build, save = variant_plan
    top = root/'board'/(variant.target+'.v')
    top.write_text(top.read_text().replace("cam2_hold_rst_n=1'b0", 'cam2_hold_rst_n='+value))
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p)
    prepared['SourceSHA256'][str(top.relative_to(root)).replace('\\', '/')] = host.hw.sha(top)
    save(p, prepared)
    manifest = host.capture.load_json(build/'validated-build.json')
    manifest['SourceSHA256'] = prepared['SourceSHA256']
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='sink-only'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
@pytest.mark.parametrize('pad', ['T20', 'AA22'])
def test_isolated_reset_exact_y20_pad_or_collision_cannot_be_rehashed(variant_plan, pad):
    _, variant, root, build, save = variant_plan
    path = root/'board'/(variant.target+'-pins.json')
    pins = host.capture.load_json(path);pins['cam2_hold_rst_n'] = pad;save(path, pins)
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p)
    prepared['SourceSHA256'][str(path.relative_to(root)).replace('\\', '/')] = host.hw.sha(path)
    save(p, prepared)
    manifest = host.capture.load_json(build/'validated-build.json');manifest['SourceSHA256'] = prepared['SourceSHA256']
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='electrical-eye'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
@pytest.mark.parametrize('direction', ['input', 'output'])
def test_isolated_y20_must_route_as_inout_even_with_correct_pad_hash(variant_plan, direction):
    _, variant, _, build, save = variant_plan
    prr = build/'place_route'/(variant.target+'_prr.prt')
    prr.write_text(prr.read_text().replace('cam2_hold_rst_n|inout|YES', 'cam2_hold_rst_n|'+direction+'|YES'))
    manifest = host.capture.load_json(build/'validated-build.json');manifest['PinReportSHA256'] = host.hw.sha(prr)
    save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='active routed inout'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
def test_isolated_pad_requires_the_existing_cam2_reset_reference(variant_plan):
    _, variant, root, build, save = variant_plan
    p = root/'board/raw_camera_capture_cam2_guarded-pins.json'
    pins = host.capture.load_json(p);pins['cam_rst_n'] = 'T20';save(p, pins)
    with pytest.raises(ValueError, match='CAM2 Y20 references'):
        host.validate_guarded_build(build, target=variant.target)


def test_reset_trial_contract_cannot_be_interchanged_or_coerced(variant_plan):
    _, variant, root, build, save = variant_plan
    p = root/'board'/(variant.target+'-sources.json')
    prepared = host.capture.load_json(p);manifest = host.capture.load_json(build/'validated-build.json')
    contract = host._expected_other_sensor_reset_contract(host.VARIANTS['raw_camera_capture_cam1_guarded_isolated'])
    if variant.mode == 'cam1-guarded-isolated': contract['drives_high'] = 0  # Wrong JSON type although False==0.
    prepared['OtherSensorResetTrialContract'] = manifest['OtherSensorResetTrialContract'] = contract
    save(p, prepared);save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='reset'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', [t for t in host.VARIANTS if not t.endswith('_isolated')], indirect=True)
def test_previous_four_targets_cannot_accept_an_extra_130th_pin(variant_plan):
    _, variant, root, build, save = variant_plan
    path = root/'board'/(variant.target+'-pins.json');pins = host.capture.load_json(path)
    pins['cam2_hold_rst_n'] = 'Y20';save(path, pins)
    p = root/'board'/(variant.target+'-sources.json');prepared = host.capture.load_json(p)
    prepared['SourceSHA256'][str(path.relative_to(root)).replace('\\', '/')] = host.hw.sha(path);save(p, prepared)
    manifest = host.capture.load_json(build/'validated-build.json');manifest['SourceSHA256'] = prepared['SourceSHA256'];save(build/'validated-build.json', manifest)
    with pytest.raises(ValueError, match='electrical-eye'):
        host.validate_guarded_build(build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
def test_isolated_binding_cannot_omit_its_explicit_reset_diagnostic_contract(variant_plan):
    plan, variant, _, build, save = variant_plan
    p = Path(plan['program_plan']['validation']['binding_path']);binding = host.capture.load_json(p)
    binding.pop('other_sensor_reset_trial_contract');save(p, binding)
    with pytest.raises(ValueError, match='isolated reset'):
        host.validate_program_binding(p, build, target=variant.target)


@pytest.mark.parametrize('variant_plan', ['raw_camera_capture_cam1_guarded_isolated'], indirect=True)
def test_isolated_requires_its_specific_readonly_factory(variant_plan, monkeypatch):
    _, variant, _, build, _ = variant_plan
    import prepare_guarded_cam1_isolated as factory
    calls = []
    def reject():
        calls.append('isolated exact clone')
        raise ValueError('synthetic modified active-camera init rejected')
    monkeypatch.setattr(factory, 'verify_clone', reject, raising=False)
    monkeypatch.setattr(host, '_variant_factory', REAL_VARIANT_FACTORY)
    with pytest.raises(ValueError, match='modified active-camera'):
        host.validate_guarded_build(build, target=variant.target)
    assert calls == ['isolated exact clone']
