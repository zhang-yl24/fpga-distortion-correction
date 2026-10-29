# Acceptance delivery handoff — 2026-10-29

**Git delivery only. All simulation/PDS/hardware/optimization stays paused.** This new branch starts from remote main ddf3540, preserving the collaborator's PR history. The original working checkout remains local HEAD9334 with all dirty files; this snapshot does not merge,approve,or replace that checkout.

Verified original evidence: frame2401920×1080/0°/Gamma0,2073600 pixels,actual DMA→behaviorDDR arbitration→SCATTER4/bilinear→writer/reader→realasyncFIFO→DE/RGB scan CRC2aee1c42,sourceCRCc14e962f. Single-frame commit→release3233552cycles=25.868416ms at125MHz. Source is uncorrected; FFmpeg default swscale RGB24→RGB565 truncation,missing source color metadata. This is internal research,not validated HDMI colors or optical accuracy. Single frame has no later capture contention and does not prove continuous30fps or external HDMI latency.

Board control9.7576996s/79cycles and static32load/110role closure passed; real compile/synth/map succeeded. MapLUT16393,routeLUT16229,FF17643,APM69,DRM17.5. 32KiB pixel cache mapped to8 true-dual-port DRM;two independent-clock FIFOs each4 simple-dual-port DRM;dynamic raw/corrected control cone retained. Resource scope is fixed exact Brown,0°,Gammaoff,dynamic raw/corrected,not full arbitrary-angle/Gamma resources.

PCF-only fix added one explicit current-map PCF registration with same mapped DB/options.145 commands,two gates/CPD consumed,Place-0006 disappears,PNR native0. Final16,016,016-byte ADF SHA2566e3a254a5e62dc32811c46e0610209bb98d5ef5d37444722c833793756c45143 is retained locally,not uploaded. Original wrapper HOST_OR_AUDIT_FAILED/CLI1 from optional CPD slot parser remains; exact nativeexit0 and post-assessment are separate. Original failure chronology is in FAILURES.md.

PNR native0 is not timing acceptance: built-in summary still245 recovery failures per corner and3 cross-SRB200ps hold-margin warnings. Final saved-DB independent STA was not started due deadline. Empty MPW/unknownCDC/IO/clock coverage is not pass. External BASEV1.4 HDMI AC/skew,DDR dynamic reset/training guarantees and formal calibration remain unresolved.

**Shortest next engineering step after explicit resume:** read the already saved final ADF with exact frozen source/FDC and run one independent all-corner STA,including setup/hold/recovery/removal/MPW,allclockpairs,CDC/unsafe/coverage/exceptions/skew. No recompile or PNR is needed to obtain this report. Do not modify vendor/reset exceptions or claim old+.191 timing for this candidate. This Git task does not execute that next step.

Exact hashes and per-file origin/relocation changes are in manifest.json and evidence-summary.json. Restricted IP,constraints,parameters and research media are external with explicit restoration inputs (EXCLUSIONS.md). Packaging portability changes are not newly tested or physically signed. Allformal/hardware gates remain false.
