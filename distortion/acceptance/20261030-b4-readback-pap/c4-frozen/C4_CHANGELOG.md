# c4: durable timeout evidence and strict event-bounded UART drain

## c3 result remains incomplete

Parent/cloud reports video3 frames /3072 pixels PASS, underflow/CRC/drop/overflow/
no-free all0, periodic AR/AW/W stalls19/19/73, forced hold0 and no natural collision
coverage. Host wall budget300s expired before UART/footer/oracle completion.
c3 result is FAIL_OR_INCOMPLETE, not whole-test PASS. Buffered trace3042 lines is
not reliable UART progress evidence. c3 package and all earlier artifacts remain.

The old task unconditionally delayed40ms after video completion. It did not wait
for a dropped signature. At27MHz and rounded234cycles/bit, one wire byte consumes
86.6667us. ACK24 + signatures2*128 =280bytes require24.2667ms of serialization;
408bytes require35.36ms, plus interbyte/packet handshake cycles. No choice is
assumed in advance. Based on approximately2.21ms first ACK, drain is expected
around26.5ms or37.6ms, subject to actual observed byte/queue completion.

## Runner evidence fix

Compiler/vvp stdout and stderr stream directly into one stage log. Running PID,
budget, state, wall time and actual exit code are saved independently. On timeout,
only the runner-owned direct process is killed and waited; partial log remains.
Every second a wall-timeline sample records available flushed simulator time and
wire byte count. Launch failures/nonzero exits/timeouts cannot produce PASS.

Four local short Python-child tests verified successful combined stdout/stderr,
nonzero rejection, timeout preservation/owned-child exit, and timestamped progress
capture during timeout. These are runner tests, not HDL simulation.

## Strict drain admission and termination

The original video/drain/CRC/ownership assertions must already have passed.
After at least16 stable pixel AND control cycles, lock dropped count d in{0,1}.
Any later change fails. Target byte count is24+128*(3-d), not a guessed280.

An independent pin decoder now assembles host packets, checks magic/length,
packet CRC, one ACK with expected ticket/nonce, unique frame IDs1..3, and counts
only complete wire packets. It does not inspect internal TX data to count them.
The existing final Python oracle still checks expected synthetic pixels, all
metadata/CRC/samples and requires raw frame1 AND corrected frame2.

Termination requires all of the following, stable for16 cycles in BOTH domains:

- decoded bytes equal target, exactly one ACK and3-d signatures, no partial packet;
- UART not busy, tx_valid0, packet arbiter IDLE;
- ACK/signature serializers inactive, reply/gate ACK/command/load valids0;
- parser idle, observer gate has no pending arm, capture has no partial frame;
- signature mailbox request=ack, both synchronizer stages caught up;
- request/ACK CDC request=ack, both sync vectors caught up, destination valids0.

Then require one full UART-byte interval (2340 control cycles) of TX high, no
new bytes/requests, every queue still idle and unchanged drop count. Late starts
fail. Only then write footer and invoke the unchanged full expected-vector oracle.
Per-pixel, per-byte, completed-packet and1ms drain-progress events are flushed.
No RTL, image/config vectors, clocks, baud or60ms simulated watchdog is changed.

## Execution and wall budget boundary

This candidate is NOT_COMPILED/NOT_RUN locally. CPU/hash preparation is allowed:

    python -B run_system.py

Future single admitted cloud run:

    python -B run_system.py --rtl --out work-real-system --simulate-timeout SECONDS

Compile remains90s. Default simulation wall limit remains300s; an explicit larger
wall allowance may be supplied once admitted, without changing simulation timing.
We do not have c3's missing time-resolved stdout, so an exact measured throughput
or sufficient new wall budget cannot honestly be reconstructed from the truncated
trace. New wall-timeline progress supplies that evidence. Do not automatically
rerun or raise a budget on failure. No local EDA/hardware/Git is authorized here.
