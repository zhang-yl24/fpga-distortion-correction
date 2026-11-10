# Source-bound PDS integration gate

## Isolate and identify inputs

Seed a new OFF case and ON case from the same complete AA/A platform. Keep existing A, Brown-B, production sources, constraints and outputs unchanged. This overlay does not provide missing vendor files. All paths below are relative to a complete `native` input root, not relative to this repository checkout.

Required AA SHA256 identities are the retained LF source bytes below, except the board top which uses the platform verifier's canonical root-token identity. Record raw local hashes separately. If a local tree has CRLF, compare an in-memory CRLF-to-LF view only where appropriate; do not confuse EOL conversion with native-root canonicalization, and do not rewrite the original:

- source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/rotated_remap_core_gamma_geometry_bypass_scatter4.v: f67f50326b88cd018334d0e6df612c11284ce1ad05108723349e3b41a20c3e25.
- source/rtl/rational_brown_mapper.v: 6dfc66dec28d36712b475edc372ff780567387555edff6add2191c1aa7ef62c2.
- source/profile/board/rational_brown_profile.vh: 9bd0b13500d16390d7c9a1b25ca568ffafd0a64add376b48e5d900d2a8d9b475.
- source/rtl/rational_brown_radial_rom.v: c0698d8718987968b9d10d3ca90d83c0443cff3224ae3c9f0898b9902ee4622f.
- source/rtl/experimental/d256_runtime_prefetch_cache.sv: ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088.
- source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/lens1080_bank_core_geometry_bypass.v: f41c60456d709f3b0c30363f985046a3613d31ab458a64a04c8757d03912dce8.
- source/build/offline-20261024/bypass-system1080-20261029-a/hdmi1080_video_system_geometry_ab.v: 89e855122b0b2ffa8293ef24032073bfca1c8b73900ae8abb7035658d4ba370e.
- source/build/offline-20261024/cfg100-independent-20261030-a/candidate/board1080_cfg100_top.v: canonical root-token SHA256 1edb706db722ba4ac1c61152471e149bb96c4799dbdaae444701bf08d8d9fa27.
- source/board/bringup_pll.v: 4c25680cccf3f1e0083439db379613207d3f622392a00cc41d82e30d1020f3e1, 10,834 bytes. The actual validated platform has 148.5 MHz pixel and 125 MHz core clocks. A stale 74.25 MHz source comment is not clock evidence. Do not substitute the different public-tree PLL.

The historical Brown-B core cc88d83b1a7f331b8a6953b9efe286c70db0e45f95c154afbd097bf73825c3e0 and mapper ae44f749cea523b4f74a319c842f982a9e967c337d41796dc9fa590d16c3add3 include a real CORRECTED_ONLY optimization. They are not this overlay's proof inputs. Do not silently revert B or inherit these AA results for B.

Device/tool gate: PG2L100H-6FBG676; PDS 2025.2 Fabric Compiler build 211867; exact complete generated DDR/PHY, cfg_pll, bringup_pll, GTP_INBUFGDS library and constraints. Keep all original vendor imports, include directories, clock relations, route constraints, KEY1 pin constraint and b4 telemetry sources. Missing/unmatched inputs are a stop, not a reason to add stubs or suppress unresolved modules.

## Add sources, not replacements

Retain all original platform design imports including the old system, bank, engine and writer. Add exactly the seven entries in rtl_sources.f using `add_design {<overlay-root>/<entry>}`. They have unique module names. `rtl/video_crc32.vh` is an include, not a separately compiled module. Do not add testbenches, another FIFO implementation or any other cache experiment.

The original flow uses `compile -verilog_standard SystemVerilog -top_module board1080_top -include_path {...}`. Preserve its existing include paths and append this overlay's rtl directory using the installed PDS command's documented multiple-path syntax. Also retain the native profile/header paths already used by the platform. Do not invent an `add_include` command. Audit include resolution so the run8 writer consumes the pinned video_crc32.vh; a same-name file is not sufficient evidence.

## Deliberate top changes in isolated copies only

At the original board top's `system` instance, select module `hdmi1080_video_system_run8_research`. Keep all ports unchanged. Add `.BLACK_RUN8_RESEARCH(0)` in the OFF case and `.BLACK_RUN8_RESEARCH(1)` in the ON case. For BOTH cases make these explicit values, rather than inheriting old ternaries:

WIDTH=1920; HEIGHT=1080; RATIONAL_BROWN_PROFILE=1; CACHE_PROFILE=6;
TILE8_GROUP_WIDTH=64; MACRO_TILE_HEIGHT=32; CACHE_INDEX_BITS=7;
PREFETCH_QUERY_DEPTH=4096; PREFETCH_LOOKAHEAD=512; CACHE_ROW_STRIDE=2;
CACHE_HEAD_PREDECODE=1; READ_REQUEST_LOOKAHEAD=0; CRC_FOLD_BITS=2;
RESULT_BANKS=2; HDMI_FISHEYE_PROFILE=0; RASTER_DOUBLE_BUFFER=0;
MAX_RADIUS_Q22=0; ENABLE_RUNTIME_ROTATION=0.

Preserve the actual board's BANK_STRIDE=33554432 (4-byte units), CORE_PRIORITY=1, STATS_ENABLE=1, STATS_CORE_HZ=125000000, STARTUP_SCAN_ALIGN=1, STARTUP_SCAN_GUARD_CYCLES=0, STARTUP_PRIME_NEXT_SOURCE=1, HT=2200, VT=1125, HS=44, VS=5, X0=192, Y0=41. Preserve its 148.5 MHz PLL, source/result address permutation, KEY1 debounce/accepted mode, default CORR and Gamma-OFF control, telemetry and common reset/release logic. Assert that live board cfg_rot_cos=2^30, cfg_rot_sin=0 and gamma_enable=0. Do not enable new rotation features or broaden the guard just to make a rejected configuration compile.

BLACK_RUN8_RESEARCH=0 selects the original bank/engine; =1 selects the new adapter/KEY1 engine. A fresh physical OFF/ON comparison therefore measures the complete implementation change, not just a compression bit in an otherwise identical new engine. The separate fixed-processing model pair in README has a different comparison scope. Both local cases need fresh implementation and acceptance; neither inherits old A/B margins. PARAMETER_SCOPE.md gives the source-line reachability argument for inactive alternate parameters and distinguishes the real HEAD change.

## ROM initialization is a release gate

Copy rom/run8_intervals_30bit.mem to EACH actual PDS synthesis process working directory under the exact default name run8_intervals_30bit.mem. Hash after copying: e03f1869bf3247ed5ae84e94fa431885a20cca86b85e6d12d8a38053ecb8c8a7, 2,394 bytes, 266 lines. It is a 266x30-bit synchronous-read ROM (7,980 logical data bits), not a frame vector. Selector has a ROM_FILE parameter, but this exact KEY1 pipeline does not forward it. Changing the source default or adding a forwarding parameter creates a new source identity and needs separate checks.

Record the actual synthesis cwd and init resource binding in local evidence. A project attachment or absence of a warning alone does not establish initialization. Inspect synthesized initialized contents and logical behavior for all 266 words, and record mapping as ROM/RAM/registers plus actual physical cost. If PDS cannot support the source construct or resolve the asset, stop and report the exact diagnostic. No generic zero/constant replacement is permitted. `ram_style="block"` is a hint, not proof of target inference.

## Required checks before proceeding

Hash every platform/overlay input before and after each isolated case. Review the top diff as module selection plus explicit settings only. g_original/g_run8 changes hierarchy, so inspect hierarchy-based constraints/probes without blanket false paths. Run strict elaboration then vendor compile/synthesis/Map/P&R/STA in fresh outputs. Check real clocks, setup/hold, unconstrained paths, IO/CDC/reset, inferred memories and device fit. Do not generate/load a bitstream or claim hardware success from Map alone. Actual capture, reader CRC, FIFO drain, lease ownership, KEY1 and DDR-fault/reset behavior still require same-source system/board validation.
