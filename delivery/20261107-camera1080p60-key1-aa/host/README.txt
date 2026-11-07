Read-only offline host helpers for the frozen AA configuration.
No script here imports serial or opens a device. Python3 standard library only.
pyserial would be needed by a separately reviewed live collector, not by these
parsers. No ready-to-run generic AA COM collector is claimed here.

aa_protocol.py imports both sibling files:
 normal_function_uart.py (exact existing SGA1/SGK1/PGSIG001 helper)
 stats_protocol_legacy.py (exact existing SGT1 builder; legacy decoder retained)
aa_protocol.py itself decodes current PGSTAT02 high24 FAULT_DETAIL fields, so
fault packets retain original CRC and are not rejected as legacy reserved bits.

From this host directory:
 python aa_protocol.py --arm-hex --ticket 1 --nonce 0x12345678
 python aa_protocol.py --stats-hex --ticket 2 --nonce 0x23456789
 python aa_protocol.py --wire camera-uart.raw.bin --known-packet-boundary

The first2 commands PRINT hex only; they send nothing. Use fresh nonzero nonce
values and increasing SGA tickets within a reset epoch. Send the resulting24
binary bytes using a separately verified live transport, not ASCII hex text.
Sending only the4 ASCII characters SGA1 or SGT1 is NOT a valid request: both
commands require all24 bytes, including schema, ticket, nonce, reserved0 and CRC.
SGK1 is a24-byte reply to SGA1, not an input command. SGT1 returns84-byte PGSTAT02.
SGA only arms passive scan telemetry; it neither changes KEY1 mode nor starts video.

Raw input must begin at an externally known whole-packet boundary. The parser
does not search arbitrary payload for magic or hide truncation/CRC failures.
A fresh FPGA reset plus no prior telemetry ARM can establish an initial quiet
session; the operator must record the reset epoch and actual serial transport.
Do not use the --known-packet-boundary flag as a substitute for that evidence.

Expected AA ParameterID is adfb7264, mode0 RAW or mode1 CORR, Gamma bit1 always0.
Default requested mode is CORR. Mode changes are frame-handshake latched; wait
for a NEW presented FrameID showing the new mode, not merely LED6 or ScanEpoch.
PGSIG refresh sequence/ScanEpoch and repeated identical FrameIDs are not fresh
frames. PGSTAT presented_frames counts new IDs; scan_repeat_frames is separate.

The static ParameterID is not a firmware hash or fresh session nonce. Check the
released SRAM sbit SHA separately. CRC/schema/identity checks do not compare a
camera frame to an optical golden or establish physical 1080p60 performance.
No full-frame export is enabled in this build; SGF1/SGR1 are not usable commands.

RAW disables geometric correction before the SAME DDR sampler; capture still
writes DDR and display still reads DDR. RAW is not direct HDMI pass-through.
The camera enters through the board HDMI RX, not a naked DVP/MIPI sensor port.

For a fresh-frame rate, record2 PGSTAT02 responses with matched distinct request
identities in one explicitly uninterrupted reset epoch. core_tick is64bits;
snapshot sequence and frame counters are32bits. Require positive hardware tick
delta, advancing snapshot sequence, and a short interval below2^32 core cycles
(34.359738368s at nominal125MHz) to exclude multiple32bit counter wraps. Use
delta_counter=(second-first) modulo2^32 only with that epoch/range evidence;
reject FrameID rollover/backward identity rather than calling it new progress.
New-presented rate candidate = delta(presented_frames)*nominal_core_hz/delta_tick;
captured/processed rates use their own counters. Report nominal-clock scope and
source, completed and displayed stages separately. PGSIG distinctFrameID is a
freshness crosscheck, not a substitute for hardware-time/epoch proof. This
offline parser deliberately does not calculate or certify rates automatically.
Never use scan VS/Sequence/ScanEpoch/repeats, or1/last_process_duration, as fresh
camera FPS. last_process_cycles is a32bit single-completion internal observation.

No active serial client is included. Any later live collector must require an
explicit operator-supplied port and must not select a default port or auto-open devices.
