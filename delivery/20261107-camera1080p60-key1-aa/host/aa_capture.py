"""Collect passive AA telemetry on an explicitly selected UART port.

Requires an externally established clean reset/whole-packet boundary. Does not
reset/program the FPGA, change KEY1, enumerate ports or discard input bytes.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import secrets
import time

from aa_protocol import make_arm, make_stats
from aa_measure import AA_SHA256, WireParser, file_sha256


def save_manifest(directory, manifest):
    temporary = directory / 'capture.json.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(directory / 'capture.json')


def collect(transport, directory, manifest, *, seconds=10.0, interval=1.0,
            response_timeout=3.0, arm_timeout=15.0, clock=time.monotonic,
            nonce_source=lambda: secrets.randbelow((1 << 32) - 1) + 1):
    """Transport must already be open; function never retries a command write."""
    if (not all(math.isfinite(v) and v > 0 for v in
                (seconds, interval, response_timeout, arm_timeout)) or
            not 1 <= seconds <= 3600 or not 0.25 <= interval <= min(seconds, 5)):
        raise ValueError('Require 1 <= seconds <= 3600 and 0.25 <= interval <= min(seconds, 5)')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = dict(manifest, Schema='AA_CAPTURE_1', Status='collecting', Requests=[],
                    StartedUTC=datetime.now(timezone.utc).isoformat(),
                    RequestedSeconds=seconds, StatsIntervalSeconds=interval,
                    DurationAnchor='first statistics reply; analyze actual hardware tick duration',
                    SerialSettings='115200 8N1, no flow control',
                    UninterruptedResetEpochNotAutomaticallyVerified=True,
                    HardwarePassClaim=False)
    save_manifest(directory, manifest)
    parser = WireParser()
    used_nonces = set()
    ticket = 0
    outstanding = None
    armed = False
    measurement_start = None
    next_due = None
    final_reply = False
    complete_packets = 0
    received_bytes = 0
    started = clock()

    def send(kind, *, final=False):
        nonlocal ticket, outstanding
        ticket += 1
        # A long capture has many requests. Redraw an unused random identity
        # before transmission instead of aborting on a birthday collision.
        # This is not a retry of an already-issued UART command.
        for _ in range(16):
            nonce = nonce_source()
            if not isinstance(nonce, int) or not 0 < nonce < (1 << 32):
                raise ValueError('Nonce source did not provide a nonzero uint32')
            if nonce not in used_nonces:
                break
        else:
            raise ValueError('Nonce source exhausted 16 fresh-identity attempts; no command sent')
        used_nonces.add(nonce)
        packet = (make_arm if kind == 'SGA1' else make_stats)(ticket, nonce)
        request = {'Kind': kind, 'Ticket': ticket, 'Nonce': nonce, 'PacketHex': packet.hex(),
                   'HostMonotonicSeconds': clock(), 'Outcome': 'pending', 'Final': final}
        manifest['Requests'].append(request)
        # Save pending intent before transmission. A partial/uncertain write
        # remains visible, is never retried and cannot pass offline acceptance.
        save_manifest(directory, manifest)
        count = transport.write(packet)
        request['WrittenBytes'] = count
        if count != len(packet):
            request['Outcome'] = 'partial'
            raise ValueError(f'Partial command write ({count}/24); command not retried')
        request['Outcome'] = 'sent'
        save_manifest(directory, manifest)
        outstanding = (kind, ticket, nonce, clock() +
                       (arm_timeout if kind == 'SGA1' else response_timeout), final)

    try:
        with (directory / 'camera-uart.raw.bin').open('xb') as raw_file:
            send('SGA1')
            while True:
                data = transport.read(parser.bytes_needed() if final_reply else 4096)
                if data:
                    # Preserve even corrupt/truncated data BEFORE interpreting it.
                    raw_file.write(data)
                    raw_file.flush()
                    received_bytes += len(data)
                    for row in parser.feed(data):
                        complete_packets += 1
                        decoded = row['Decoded']
                        if row['Kind'] == 'SGK1':
                            if (armed or outstanding is None or outstanding[0] != 'SGA1' or
                                    (decoded['Ticket'], decoded['Nonce'], decoded['Status']) !=
                                    (outstanding[1], outstanding[2], '01')):
                                raise ValueError('Unexpected/stale/refused ARM acknowledgement')
                            armed = True
                            outstanding = None
                            next_due = clock()
                        elif row['Kind'] == 'PGSTAT02':
                            if (not armed or outstanding is None or outstanding[0] != 'SGT1' or
                                    (decoded['Ticket'], decoded['Nonce']) != outstanding[1:3]):
                                raise ValueError('Unmatched/duplicate statistics response')
                            final_reply = outstanding[4]
                            outstanding = None
                            if measurement_start is None:
                                measurement_start = clock()
                            next_due = clock() + interval
                        else:
                            arm_nonce = manifest['Requests'][0]['Nonce']
                            if not armed or decoded['SessionID'] != arm_nonce:
                                raise ValueError('Signature arrived outside the acknowledged session')
                now = clock()
                if outstanding is not None and now >= outstanding[3]:
                    raise TimeoutError(f'{outstanding[0]} response timeout; command not retried')
                if final_reply:
                    if not parser.buffer:
                        break
                    # Finish only the already-started tail packet; do not guess
                    # a new boundary or silently remove a partial UART packet.
                    if now - next_due + interval > response_timeout:
                        raise TimeoutError('Final partial packet did not finish')
                elif armed and outstanding is None and now >= next_due:
                    send('SGT1', final=measurement_start is not None and
                         now >= measurement_start + seconds)
                if now - started > arm_timeout + seconds + 3 * response_timeout + interval:
                    raise TimeoutError('Overall collection deadline reached')
            parser.finish()
        manifest['Status'] = 'complete'
    except BaseException as error:
        manifest['Status'] = 'failed'
        manifest['Error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        raw_path = directory / 'camera-uart.raw.bin'
        manifest['RawBytes'] = received_bytes
        manifest['CompletePackets'] = complete_packets
        manifest['UnfinishedTailBytes'] = len(parser.buffer)
        manifest['RawSHA256'] = file_sha256(raw_path) if raw_path.exists() else None
        manifest['HostElapsedSeconds'] = clock() - started
        save_manifest(directory, manifest)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', required=True, help='Operator-selected port, e.g. COM5 or /dev/ttyUSB0')
    ap.add_argument('--out-dir', required=True, type=Path, help='New directory; existing data are never overwritten')
    ap.add_argument('--epoch-label', required=True)
    ap.add_argument('--mode', required=True, choices=('raw', 'corr'), help='Set manually with KEY1 before collection')
    ap.add_argument('--loaded-bitstream-sha256', required=True)
    ap.add_argument('--confirm-clean-reset-boundary', action='store_true',
                    help='Confirm a fresh FPGA reset and no earlier telemetry ARM, with no other UART reader/writer')
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--stats-interval', type=float, default=1.0)
    args = ap.parse_args()
    if not args.confirm_clean_reset_boundary:
        ap.error('Establish and attest a fresh reset/quiet packet boundary first')
    if not args.port.strip() or not args.epoch_label.strip():
        ap.error('Explicit nonempty port and epoch label required')
    if args.loaded_bitstream_sha256.lower() != AA_SHA256:
        ap.error('This collector targets only the released AA bitstream SHA256')
    if (not math.isfinite(args.seconds) or not math.isfinite(args.stats_interval) or
            not 1 <= args.seconds <= 3600 or not 0.25 <= args.stats_interval <= min(args.seconds, 5)):
        ap.error('Require 1 <= seconds <= 3600 and 0.25 <= stats interval <= min(seconds, 5)')
    if args.out_dir.exists():
        ap.error('Output directory exists; choose a new directory')
    try:
        import serial
    except ImportError:
        ap.exit(2, 'Live collection requires pyserial: python -m pip install pyserial\n')
    # Configure DTR/RTS while closed to reduce unintended control transitions.
    # OS/adapter behavior is not guaranteed; neither signal is used as reset.
    port = serial.Serial(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                         timeout=0.05, write_timeout=2.0, xonxoff=False, rtscts=False, dsrdtr=False)
    port.dtr = False
    port.rts = False
    port.port = args.port
    manifest = {'PortOperatorSupplied': args.port, 'EpochLabel': args.epoch_label,
                'KnownCleanResetBoundaryAttested': True, 'ExpectedMode': args.mode,
                'LoadedBitstreamSHA256OperatorSupplied': args.loaded_bitstream_sha256.lower()}
    try:
        port.open()
        result = collect(port, args.out_dir, manifest, seconds=args.seconds,
                         interval=args.stats_interval)
    except (Exception, KeyboardInterrupt) as error:
        ap.exit(2, f'Collection stopped: {error}\nAny received bytes and request journal remain in {args.out_dir}.\n')
    finally:
        port.close()
    print(f'Saved {result["RawBytes"]} raw bytes in {args.out_dir}. No hardware pass is claimed.\n'
          'After independently confirming no FPGA reset occurred during capture, run:\n'
          f'python aa_measure.py "{args.out_dir}" --confirm-uninterrupted-epoch')


if __name__ == '__main__':
    main()
