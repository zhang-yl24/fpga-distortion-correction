# Bounded statistics UART receiver, 2026-11-01

`distortion/tools/camera720_stats_receive.py` is ready for a later statistics
bitstream. This task tested mock streams only. The existing frozen camera image
was not changed, and no real UART, JTAG or PDS access occurred.

The default is **COM7, 115200 baud, 8N1, 30 seconds**, matching the isolated
statistics RTL. The 921600 baud used for raw image transfer is a different
firmware mode. `--baud` can be explicitly overridden. Duration is bounded to
300 seconds maximum; received bytes are separately limited, default 1 MiB and
hard maximum 4 MiB. The serial read timeout never exceeds 250 ms or the remaining
receive duration. OS device open/close latency is not an independent hard deadline.

The receiver never sends UART data, clears the input buffer, triggers capture,
programs the board, or installs a heartbeat. It configures DTR/RTS low before
opening the serial port, with software/hardware flow control disabled. The owned
stream is closed on normal completion, timeout, byte limit, decoding/read failure
and keyboard interruption. Close failures remain explicit and prevent success.

Only the root hardware operator should invoke live reception after the new
candidate has an actual verified bitstream and successful program receipt. That
release remains separate: the receiver validates expected 64-bit labels and
CRC, **not** the full bitstream, physical connection or current board contents.

Example, after those actual prerequisites exist and expected labels are obtained
from the exact programmed source manifest (replace placeholders):

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_stats_receive.py --output distortion/work/camera720-core-stats-receive/live-<fresh-name> --expected-build-id <16-lowercase-hex> --expected-profile-id <16-lowercase-hex> --port COM7 --baud 115200 --seconds 30
```

The output parent must exist; the session directory must be fresh. Importing the
module opens nothing. `receive_stream` permits injected mock streams for tests,
which retain `SourceKind=injected_test_stream` and `HardwareAccessed=false`.

## Evidence and valid windows

Each session preserves:

- `received-wire.bin`: exact bounded received bytes, including corrupt packets
  and incomplete leading/trailing fragments.
- `reads.jsonl`: raw byte offsets, requested sizes, and monotonic read start/end
  times relative to the session start.
- `packets.jsonl`: every complete CRC-valid packet, exact wire offsets, expected
  build/profile ID match result and the read in which decoding completed.
- `windows.jsonl`: every adjacent complete-packet pair, why it was included or
  excluded, counter-derived rates and host read-time cross-checks.
- `session.json`: source/artifact SHA256, bounds, errors, close failures, missing
  data, identity mismatches and a weighted summary of selected valid windows.

Window counters are `SourceAccepted`, `Processed`, and `UniquePresented` with
the scopes documented in `CAMERA_720P_STATS_PROTOCOL_20261101.md`. Valid windows
require matching expected IDs at both ends, no intervening corrupt/unframed data,
and valid tick/sequence/counter deltas from the frozen decoder. A sequence gap by
itself uses the actual tick interval; it is not interpreted as lost video frames.
Observed reset/regression or old-ID packets break the adjacent window. The next
clean pair may still form a useful window, but any complete rejected packet or
identity mismatch prevents `ReceptionAndIdentityPassed` for the whole session.
An incomplete final packet is retained but never becomes a count sample.

Rates use board core ticks divided by the **nominal** core frequency. The summary
weights frame deltas over selected tick intervals, without bridging excluded
intervals or claiming a whole-host-session average. Host read-completion deltas
and their ratio to nominal board time are recorded separately. USB/OS buffering
can merge packets or delay delivery; these times are not exposure/snapshot times,
and they do not establish an independently calibrated core clock.

As in the frozen decoder, all rates assume a continuous reset epoch within each
window and fewer than 2^32 counter events per interval. An unobserved reset followed
by enough missing early packets can escape monotonicity checks; every session
retains `ResetEpochContinuityProven=false`. No sensor-total-input FPS or HDMI
refresh FPS is claimed.

Current statistics firmware leaves underflow and fault status unavailable.
`Underflows` and `KnownFaultObserved` remain null when unknown; no missing status
is converted to a zero count, a fault-free result or optical/hardware acceptance.
`ReceptionAndIdentityPassed` is only the bounded receive/label/protocol result.
No data or a single packet cannot produce FPS or pass this result.

The focused tests use only mocks: bad CRC, old build/profile IDs, gaps, reset,
no-data timeout, byte limit, partial tail, read/decode/open/close errors, keyboard
interrupt, frozen decoder mismatch and source drift. The live UART must not be
opened just to test this tool.
