# 720p reset-effect checkpoint review (2026-11-01)

Scope: CPU-only review and tests of `tools/audit_camera720_reset_effect.py`.
No PDS process, native mutation, bitstream or hardware was started. This is
review of the audit implementation, not a passed audit of a reset candidate.

Binding APIs are consistent with the actual tools: baseline route-derived
`bind_receipt(path)` returns `(receipt, watched)`; reset-derived
`bind_source_receipt(path, watched)` and `bind_receipt(path, watched)` return
the receipt dictionary. The effect auditor requires both exports and the
application to share the build, exact source/result ADF chain and application
receipt identity. Generic comparison helpers reuse no historical endpoint
counts or target acceptance flags.

One bug fixed in the unfrozen new effect auditor: late assignments of the
current SHA to already watched proof/netlist/route files could replace a
previous identity and hide a change during comparison. Added `watch` with
conflicting-identity rejection, conflict-checked merging of baseline inputs,
and snapshots of loaded local parser tools before and after parsing.

Added `tests/test_camera720_reset_effect.py`: 16 CPU cases pass. These use
explicit mocked native bind/parsers and real effect comparison functions;
they do not stand in for actual native reports. Coverage includes the two
different binding APIs, exact build/ADF/receipt/mode chain, all ten timing
tables, remaining data-check count and slack preservation, unchanged negative
slack rejection, setup false-path rejection, missing reset variants, any route
mutation, artifact hash mismatch, and mutation of a netlist after its graph
comparison. Success explicitly keeps timing, CDC, external AC and hardware
release authority false.

Combined regression: the 16 new cases plus 19 existing generic reset-effect
cases passed (35 total). The legacy tool/tests were not edited. Fresh native
reset application/export and actual reset-effect audit remain outstanding.
