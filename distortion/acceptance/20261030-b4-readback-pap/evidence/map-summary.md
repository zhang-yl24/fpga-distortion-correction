# Display-only reset attribute candidate: synthesis/map complete

One admitted native compile / ADS synthesis / dev_map invocation completed with
exit0. Outer wall361.150860s; native completion recorded at360.619264s, within
480s native budget. No timeout occurred. Cleanup took0.000308s, within reserved30s.
Root PDS PID15752 was created suspended, assigned to the private KILL_ON_JOB_CLOSE
Job, membership verified, and only then resumed. Job accounting recorded exactly
14 total processes, all14 identities/handles were retained, active0 at finish.
The Job was closed and all14 exit handles were signaled; visible EDA count0.
No taskkill, elevation, credentials or security change was used.

## Attribute result

The original36 logical b4 synchronizer bits reconcile through recorded optimizer
aliases to18 distinct synthesis DFFs. All18 carry PAP_ASYNC_REG="TRUE". There are
no unresolved mappings or invalid PAP_ASYNC_REG warnings. The previously unmarked
shared pixel release pair now resides in video_display_async_fifo; Q0 drives D1,
D0 is1, both clocks are nt_pix_clk and both resets are rst_n_inv. Seven non-reset
chains retain14 marked FFs; shared control and pixel release pairs add4.

Full per-bit source identity, alias sequence, native cell/module, property and
Q/D/CLK/reset evidence: synthesis-property-reconciliation.json. This proves
property retention in the emitted synthesis VM, not placement proximity,
post-route timing, CDC analog behavior or MTBF. No such physical claim is made.

## Source scope / structure

Only the existing display_fifo instance changes to the dedicated self-owned
video_display_async_fifo type. Its behavior, ports, parameters, state, RAM and
handshake remain the exact statically reviewed source. The original video_async_fifo
still serves capture/pixels; its file and input capture source hashes are unchanged.
The new source list has46 design entries /125 copied input files. The whole old
candidate, frozen c4 ZIP, original source set and reviewed static copies remain
protected:379 protected hashes and125 current input hashes match after execution.
No vendor/IP regeneration, FDC/clock/exception change or extra live FIFO occurred.

## Device-map resources versus prior PAP candidate

| Resource | Previous | New | Delta |
|---|---:|---:|---:|
| FF |21086|21086|0|
| LUT |16852.5|16852.5|0|
| DRM |17.5|17.5|0|
| APM |69|69|0|
| IO |144|144|0|

Fractional resource accounting is retained exactly as reported by PDS.
Original native warnings remain saved. Generic async_reg ignored warnings64
belong to remaining non-covered declarations; this task did not broaden into
fixing those. telemetry_rx/tx still have Timing-4086/4087 unbound timing and
ConstraintEditor-2019 unspecified IO warnings. They were not waived.

## Frozen outputs and boundary

Map ADF SHA256:
5b8bc05bf6d3aa0d4c2339a8796d3b4a17b11f18fd8162509ab4da99abb75bf4
Same-map PCF SHA256:
09bbefa7eb7670bccbafd79e429c0d046a00c756759dcfbc7a145c888df413b9

RESULT.json binds all native outputs and execution/protection evidence.
No PNR, STA, bitgen, hardware operation or Git write was run. HardwareReleaseAllowed
remains false. No second native run was launched. The unique heavy slot is free.

Next work requires separate admission: establish the supported effective physical
constraint/object path for the new held-bundle/mailbox and reset checks; then
consider one same-map-PCF PNR/STA diagnosis. Do not inherit old candidate timing,
expand exceptions, or infer native1080/hardware proof from c4's small system PASS.
