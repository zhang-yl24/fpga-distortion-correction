# Private runtime receipts

These are schemas, not completed evidence. Create receipts only after authorized acquisition/generation and checking the actual installation. Keep them outside published source, for example under a private directory in a disposable local copy. No sensitive values or license contents are needed.

## External input JSON

Required fields:

- schema: 1
- authorized_use: true, only after entitlement is established by the operator
- placeholder_or_blackbox_inputs: false
- ddr_generator: "2022.2-SP6.4 build146967"
- ddr_model: "HMIC_S1.10"
- device: "Logos2 PG2L100H -6 FBG676"
- provenance: a nonempty factual explanation of the authorized original restoration or new matching generation, including actual generation/model evidence. Do not claim original byte equality from configuration equality.
- files: exactly 77 objects, each with path (the relative required path from EXTERNAL_INPUTS.json) and sha256 (computed from the locally supplied bytes).

The tool validates exact paths/hashes, rejects trivial empty files, and invokes the unmodified read-only DDR/PLL parameter tools. These checks cannot prove licensing or inspect every encrypted implementation. Actual vendor closure, primitives/connectivity, synthesis unresolved-cell reports and all report coverage remain required. The receipt is a human assertion plus local byte binding, not a cryptographic certificate of vendor provenance. Never fabricate it to let placeholders pass.

## Tool JSON

Required fields:

- schema: 1
- product: "PDS"
- version: "2025.2"
- fabric_compiler_build: "211867"
- normal_authorized_license_setup: true, only after the operator's normal authorization is established
- executable_sha256: SHA256 of the actual executable selected by --pds
- version_evidence: nonempty actual official version/banner evidence connecting the launcher and Fabric Compiler to this version/build.

No hypothetical --version syntax is prescribed. Obtain exact version evidence from the official installed UI/banner/help or a documented invocation. The wrapper verifies the supplied executable bytes against the receipt but cannot authenticate the assertion or test a missing license. It does not set, read or copy license secrets.

## Predecessor review JSON

Required fields:

- build_input_identity: exact digest from BUILD_IDENTITY.json
- stage: the preceding source stage, "map", "place" or "route"
- checkpoint_sha256: SHA256 of its actual recorded new ADF
- accepted_for_next_stage: true, only after reviewing actual outputs
- unresolved_cells_or_blackboxes: false
- reviewed_reports: one or more objects with path relative to this root and sha256. Each must be a real file inside that preceding stage output directory.

Map output may feed place, place may feed route, and final route may feed STA and bitgen. Reports must cover the relevant implementation checks; a zero return code alone is insufficient. The stage adapter does not decide whether timing, CDC or HDMI physical I/O is acceptable. STA and bitgen consume the same unchanged final hold-optimized route ADF. The build receipt records what actually ran and remains GENERATED_UNREVIEWED even on success.

Any failed/interrupted stage leaves its lock and receipt. Do not delete them to masquerade as a fresh run. Preserve that diagnostic record and start a separately rooted copy for the next attempt.

## Additional STA review gate for offline bitgen

The bitgen command must also supply `--sta-review private/sta-review.json`.
This review binds stage "sta", build_input_identity, checkpoint_sha256,
vendor_receipt_sha256 and tool_receipt_sha256 to the same final route ADF
and runtime inputs used by the recorded STA invocation. It requires:

- accepted_for_offline_bitgen: true
- unresolved_cells_or_blackboxes: false
- setup_and_hold_reviewed: true
- unconstrained_and_zero_coverage_reviewed: true
- clock_and_exception_coverage_reviewed: true
- physical_io_and_cdc_limitations_acknowledged: true
- reviewed_reports: nonempty relative paths and SHA256s of actual STA reports
  inside build-repro/sta.

These are explicit operator review facts, not an automated report parser.
Do not mark a field true until reviewed. The wrapper compares actual report
hashes and execution identity, but cannot certify the operator's conclusions.
Offline image generation still does not authorize board programming or imply
HDMI AC, CDC, optical calibration or hardware acceptance.

Every reviewed report must also appear in the completed stage receipt's
`output_files` manifest with the same path and SHA256. A later copy of an old
report into the stage directory is not accepted. The adapter records all
regular generated files after the vendor process returns, including console
logs, and rejects symlink outputs. Runtime receipts and output manifests are
local audit records, not signed vendor attestations; preserve them unchanged.

All receipts must be nonempty JSON objects. Empty objects, arrays, null and
other nonobject values fail closed. Plaintext synthesis includes in Verilog,
SystemVerilog and encrypted-file .vp headers are limited to literal paths
inside the recorded closure. Macro/nonliteral include forms require a
separately reviewed dependency contract and are rejected by this adapter.

The STA review additionally requires these numerical fields:

- worst_setup_slack_ns and worst_hold_slack_ns: actual worst slack in ns from
  the reviewed reports, JSON integer or floating-point numbers, finite and
  greater than or equal to zero. Missing, string, Boolean, NaN, Infinity and
  negative values are rejected.
- reviewed_clock_count: positive JSON integer, not Boolean or floating point.
- unconstrained_path_count: JSON integer zero, not Boolean or floating point.
  Nonzero or unknown/unreviewed unconstrained-path counts are rejected.

These numbers are explicit operator assertions linked to the recorded report
hashes. The adapter does not derive them from PDS output. A negative-path-only
listing with no paths does not prove worst slack, clock coverage or absence of
unconstrained paths. If the retained official recipe does not produce enough
reports to establish these facts, stop before bitgen and obtain a separately
reviewed official reporting procedure; do not invent numbers or tool flags.
The unresolved HDMI external-I/O and CDC limitations are still separate
acceptance obligations and are not made safe by entering zero here.
