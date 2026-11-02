# Independent physical CLM mapper review

Reviewed 2026-11-01 by camera720_release_tools. No concrete structural blocker found in the frozen bytes listed below. The reviewer ran only CPU reads, tests and recomputation; no PDS, JTAG, UART or hardware operation, and no frozen implementation was modified.

The mapper only expands logical CIN on BLE B/C/D after proving the functional COUT driver, actual native driver/consumer connection, output/input direction, identical physical CLM site and adjacent A/B/C/D order. It traverses the actual selected Boolean inputs of the preceding carry LUTs. Source FF support filters unrelated upstream inputs. BLE A CIN and native I inputs remain boundary pins. Full logical source FF, destination FF, destination pin, logical Q, source CLK/output and placements remain in each relationship; query deduplication retains all original relationship indexes.

Completed verification:
- 38 tests passed: 15 focused CLM cases plus 23 original mapper/sameBLE regressions.
- Independently rebuilt placements, functional graph and selected route objects from the actual final netlist and native route dump. All 28 endpoint-inventory bound hashes matched before and after; candidate ADF SHA remained 777bed47bf6489457f42cda54a3cadc4e74f7a4ae2c8caacc51eb49f14e48904.
- Recomputed result exactly equals physical-clm-boundaries-b.json. All 976 logical relationships preserve every prior metadata field except the intentionally replaced NativeBoundaries field. Every relationship is present in query membership.
- Physical query identities change from 1616 to 1136: exactly 480 removed identities, all internal CIN, no added identities. Every removed CIN has an actual internal-carry proof and appears in the replacement boundary-to-logical-FF trail. All resulting boundary nets still causally depend on the original SourceFF.
- 480 logical boundary rows change and 496 remain unchanged; 15 internal carry connections and 124 native/functional LUT INIT bindings are retained.

Risk/limit: structural boundary expansion does not prove that a native report for one physical input accounts for every preserved logical capture FF. PhysicalTimingAggregationProved, NativeTimingAccepted and HardwareReleaseAllowed correctly remain false. Actual through-probe/native path semantics must resolve that separate question before a new timing collector or release adapter can credit coverage. This helper returns derivation data without its own complete file-hash closure; callers must bind actual graph, route, inventory, placement source and helper bytes, as declared by CallerMustBindActualGraphAndRoute=true. Existing incomplete or invalid native receipts are not upgraded by this review.

Frozen review hashes:
{
  "distortion/tools/camera720_cdc_clm.py": "1aca0f2df5d850fcb300a72c8c243be7985f97c7ada6e0b97af6ad646e25254d",
  "distortion/tests/test_camera720_cdc_clm.py": "db6bb5e09e55e5c73b8e13d5b889019a24813367b0052c3dcfbca4e94789110d",
  "distortion/work/camera720-output/physical-clm-boundaries-b.json": "84c66dffc42fa4b84fc32e92dc0a93f38e5d239972096a72634905873f1ddf23",
  "distortion/work/camera720-clm-independent-review-result.json": "f1f4421737ea029b7573b8382d148d6557c2b9c6b005dad5816b5c5ce157ab45"
}
