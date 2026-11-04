# B4 readback and final synchronizer attributes: isolated delivery proposal

Repository: zhang-yl24/fpga-distortion-correction (existing private repository).
Suggested new branch: delivery/20261030-b4-readback-pap. No branch was created,
no commit/push/merge was performed. Keep main and the TX49/CFG100/CE delivery intact.

## Evidence boundaries

| Version | Evidence | Boundary |
|---|---|---|
| c2 | Failed: artificial display AR hold caused real underflow | Failure retained locally |
| c3 | 3 video frames passed; UART completion incomplete at 300s | Not a full pass |
| c4-frozen | Cloud compile/vvp/oracle PASS; 667.003s, 3072 pixels, 280 UART bytes, ACK1 + signatures frames1/2 | Old generic async_reg source hashes; 32x32 synthetic A/B/A, DDR UI behavioral model |
| final-attribute-candidate | 11 overlay files; exact inverse-byte checks; real PDS2025.2 build211867 compile/synth/map exit0 in 361.151s | New hashes did NOT rerun the 667s HDL test; no PNR/STA |
| Properties | 36 logical bits ->18 synthesis FF, all18 PAP marked | Synthesis VM only, not physical CDC/MTBF |
| Resources | FF21086, LUT16852.5, DRM17.5, APM69, IO144; unchanged versus previous attribute candidate | Full board closure is local-only and excluded here |

c4 video drop/underflow=0; telemetry signature_dropped=1 is separate and expected
by the accepted wire oracle. Natural contention=0; forced collision NOT_RUN.
Signatures/samples are not a full image upload or proof of physical HDMI output.
The cloud evidence was sealed separately (see evidence/c4-functional-status.json),
but local materialization failed twice; this package does not invent its bytes.
Historical c4 README/manifest and historical-handoff were preserved byte-for-byte;
their preparation-time NOT_RUN/resource TODO statements are superseded only by
the explicitly version-bound receipts above.

## Consume without changing stable inputs

The original 65-file allowance is preserved under c4-frozen (62) and
historical-handoff (3). The final source delta is an 11-file overlay, not a new
functional baseline. From final-attribute-candidate run:

    python -B materialize_sources.py <new-empty-destination>

This only hash-checks and materializes 37 own RTL/header files plus the 34-entry
sources.f. It executes no HDL tool and refuses an existing destination. It does
not supply a vendor-dependent board top or imply a stand-alone board build.
The old functional test entry is c4-frozen/run_system.py (use --help); its
check_telemetry.py oracle and synthetic vectors remain unchanged. Do not label
a run of that frozen test as a run of the final overlay. Any future new-hash
regression needs a separately bound test manifest and an explicitly authorized run.

## Remaining work and exclusions

No physical timing/IO/V1.4/MTBF or hardware release accepted. UART telemetry_rx/tx
remain unbound, generic ignored async_reg warnings64 remain outside this reviewed
set, and exact physical CDC constraints/reset coverage need supported-tool proof.
Do not inherit old CE22/CE25 timing, apply broad exceptions, or treat attributes
as closure of DDR recovery. Input FIFO is unchanged; only display FIFO specializes
its module name/read-reset attribute. All hardware gates remain false.

Next: review effective physical constraint/object binding; then separately admit
matched PNR/STA and affected native1080 readback coverage. Future board diagnostics
use PC HDMI input plus authorized UART readback; monitor is not a prerequisite.
No device access or pin probing occurred in this delivery preparation.

Excluded: vendor/derived sources or diffs, DDR/PLL IP, complete board top, FDC/PCF,
netlists, ADF/DB/bitstreams, full native logs, media/Penn data, license/credentials,
private absolute paths and transfer receipts. Only small self-owned connection
and attribute summaries are included. Source ownership follows the reviewed
c4 allowance, not a newly inferred permission to redistribute third-party IP.

REMOTE_PATH_MAP.json maps the old allowance and the official db4fed changed-file
list. That API response is not a recursive tree and does not prove the new branch
or target directory absent. The future Git workflow must recheck current refs,
privacy and destination collisions before committing; never overwrite a collision.
