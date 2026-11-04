# DDR read return: isolated source combination

Status: HDL UNIT COMPILE/SIMULATION PASS. Independent cloud Icarus Verilog 12.0
compiled and simulated all five tests with exit 0 and no compile warnings.
The tested source commit is 2ab69332114ddf76ebd426076d043457b78ec56e;
its 10/10 bound files were checked by bytes, Git blob SHA and SHA256.
The three RTL files are unchanged. The original four benches were published in
that commit. The fifth bench is a supplemental test supplied with the parent
cloud receipt against those same RTL bytes; it was NOT included in 2ab69332.
It is stored here with CLOUD_UNIT_VALIDATION.json. The task host did not
rerun HDL/EDA or access active FPGA builds.

This is NOT a selected board build. Actual parent/full-system integration,
native implementation, STA/CDC/reset/IO and board verification have NOT run.
It is not scout-local-a or the KEY1 candidate, and does not replace peer
directfill's different fill8r2 read arbiter.

The source reference is main 327ef108f48b467b8bbe5c4e67f9b503e4983b50.
Its generic distortion/rtl/ddr_read_arbiter.v is byte-identical to published
O/P (blob dad2ea07876ad11cfeb15bca21a845d043eb639e). The return stage
comes from old published PR25 / 25015cf3, blob 504d127378dc7a2633fa916f54baf0408d3f9081.
That old whole-system candidate failed physical timing; its board entrypoints,
source-slot scheme and constraints are not restored here.

The new wrapper wires the public AR handshake to both original arbiter and raw
owner guard. The complete data256/valid/last/id4 bundle passes through one
core-clock register stage before the original arbiter. No RREADY, CDC, address
remapping, request gating, AR withdrawal or implicit reset is introduced.

Both blocks need the same transaction-domain clock/reset. Reset is sampled
synchronously; payload bits are deliberately unreset and valid-qualified.
There is no flush/retry interface. On failed, the parent must stop NEW work,
preserve an already offered AR through acceptance, drain/retire the existing
transaction epoch and only reset the entire DDR transaction domain using its
safe protocol. Unit tests do not establish a board parent's fault/drain/reset
or lease-release policy.

failed is the OR of both sticky flags. The combined fault code gives arbiter
priority, matching the original published inline bench. Independent flags/codes
remain exposed when both faults occur. busy is arbiter ownership state, not
an alternative to failed. Guard fault is registered/sticky, not a zero-cycle
raw-fault veto. Same-edge raw fault plus parent lease release still requires
an explicit full-system check; the new simultaneous-fault unit test has no
bank/display lease and does not cover that check.

## Cloud tests passed

| Testbench | Top |
|---|---|
| tests/original/tb_legacy_registered.sv | tb_ddr_read_arbiter |
| tests/original/tb_readstage_guard.sv | tb_readstage_guard |
| tests/original/tb_readstage_integration.sv | tb_ddr_readstage_integration |
| tests/tb_unit_wrapper.sv | tb_ddr_read_return_unit_wrapper |
| tests/tb_simultaneous_faults.sv | tb_simultaneous_faults |

The three original benches are byte-preserved. The wrapper bench derives from
the original inline-pair test and substitutes the wrapper. Results cover both
clients, 1/2/8/16 beats, urgency/fairness, held AR, address/response stalls,
same-AR raw first beat, contiguous/gapped returns, bad RID/RLAST, missing
response, unsolicited/overlapping returns and common reset. Normal and gapped
zero-latency cases each checked 162 beats and 24 same-AR first returns;
the continuous case recorded 138 consecutive raw beats. Guard-only checks=11.

The fifth test uses real transactions, not force/hierarchical injection, to
make the registered bad RID (arbiter=03) and next raw unsolicited response
(guard=40) assert on the same edge. It checks arbiter code priority, independent
sticky codes, zero completed-burst counts and common reset clearing.

Reproduce from this unit directory with a selected simulator, for example:

    iverilog -g2012 -s tb_simultaneous_faults -o simultaneous.vvp -c rtl/sources.f tests/tb_simultaneous_faults.sv
    vvp simultaneous.vvp

Next bind the unit to an exact published parent, then run that parent's FIFO
capacity, descriptor/bank ownership, complete-frame pixel/tag/CRC scoreboard,
fault/drain, same-edge release and coordinated reset regressions. Only then
prepare a full board candidate with exact IP/constraints, original clocks,
IO/CDC/RDC and dual-corner STA, a distinct BuildID/bitstream and SRAM/rollback
acceptance. No Flash action or new board entrypoint is part of this unit.
