# DDR read return: isolated source combination

Status: source closure and static port/hash checks only. HDL compile, simulation,
native implementation, timing and board verification have NOT run. No existing
board build selects this unit. It is not the unpublished scout-local-a or KEY1
candidate, and does not replace the peer directfill fill8r2 read arbiter.

The base reference is current main 327ef108f48b467b8bbe5c4e67f9b503e4983b50.
Its generic distortion/rtl/ddr_read_arbiter.v is byte-identical to the published
O/P copy (blob dad2ea07876ad11cfeb15bca21a845d043eb639e). The return stage
comes from old published PR25 / 25015cf3, blob 504d127378dc7a2633fa916f54baf0408d3f9081.
That old whole-system candidate failed physical timing; its board entrypoints,
source-slot scheme and constraints are not restored here.

Three RTL files form this standalone unit. The new wrapper wires the public AR
handshake to both the original arbiter and the raw owner guard. The complete
256-bit data, valid, last and 4-bit ID return bundle passes through one core-clock
register stage before reaching the original arbiter. There is no RREADY, CDC,
address remapping, request gating, AR withdrawal or implicit reset.

Both blocks require the same transaction-domain clock/reset. Reset is sampled
synchronously by these blocks; payload bits are deliberately unreset and may
only be interpreted when valid. No flush/retry interface is invented. A parent
must stop NEW work on failed, preserve an already offered AR through acceptance,
drain/retire its existing transaction epoch, and only reset the entire DDR
transaction domain under its existing safe protocol. This wrapper alone does
not establish that a board parent's fault/drain/reset policy satisfies that contract.

failed is the OR of both sticky flags. The combined fault code gives the arbiter
priority, matching the published inline integration bench. Separate flags and
codes remain exposed for simultaneous faults. busy is the arbiter's ownership
state; it is not an alternative to failed. The guard fault is registered and
sticky, not a zero-cycle raw-fault veto. Any parent lease release that coincides
with a raw fault needs an explicit full-system check; this source unit does not
establish that a same-edge release is safely rejected.

The three original benches are kept byte-for-byte. tests/tb_unit_wrapper.sv is
an explicitly derived integration bench that substitutes this wrapper for the
original inline pair. Prior reports cover the original pair, not this new wrapper.
All benches remain UNRUN in this audit. Future offline acceptance should compile
the wrapper and run all four benches with the selected simulator, checking:
1/2/8/16 beats, both clients, urgent display/fairness, AR stalls, zero-latency raw
first beat, contiguous/gapped returns, RID/RLAST faults, unsolicited/overlapping
returns, timeout, held AR through fault and whole-domain mid-burst reset.
Add a simultaneous-fault export check. Then repeat the REAL parent's descriptor,
bank lease, FIFO capacity and full-frame CRC tests before any board integration.

Example future compile command, from this unit directory (NOT executed here):

    iverilog -g2012 -s tb_ddr_read_return_unit_wrapper -o wrapper.vvp -c rtl/sources.f tests/tb_unit_wrapper.sv
    vvp wrapper.vvp

Only after those pass should a full board candidate bind every exact IP/constraint,
check original clock/IO/CDC/reset and dual-corner STA, create a new diagnostic
BuildID and perform SRAM/rollback acceptance. No Flash action is part of this unit.
