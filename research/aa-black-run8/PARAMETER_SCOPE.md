# Parameter reachability in the exact AA native path

Source inspection only, not system dynamic or physical proof. See PDS_INTEGRATION.md for the source anchors and exact overlay mapping. The seven new RTL modules are flattened under rtl/ without changing their bytes. Original AA source paths remain relative to native/.

Line numbers below refer to the exact source hashes above and original AA source tree. For brevity, `geometry/` denotes `source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/`.

### HEAD_PREDECODE: real hardware change, shared across OFF/ON

Original board top214 selects0 for Rational Brown. Core98 forwards CACHE_HEAD_PREDECODE to sampler. `source/rtl/experimental/ddr_remap_sample_scatter4.v:21` forwards it as HEAD_PREDECODE to the active D256 cache for profile6. Cache `d256_runtime_prefetch_cache.sv:57` changes TOKEN_W; lines226-231 pack predecoded metadata into FIFO instead of coordinates/tags alone; lines262-280 consume that descriptor instead of recomputing head geometry. FIFO instance is at245. This can change RAM usage, logic and timing. It is intended to preserve functional sampling but is not an unreachable or cosmetic parameter. Shared HEAD1 is mandatory to compare the candidate against a source-matched control. Fresh synthesis/timing remain necessary.

### HDMI_FISHEYE_PROFILE: unreachable alternate geometry under fixed Rational Brown

Original top215 passes2 because CAMERA_RUNTIME_GAMMA defaults1, regardless of HDMI_FISHEYE_PROFILE default1. At AA core63, Rational Brown wins the rotation-centre ternary. Lines64-65 apply profile1 cosine/sine override only when !RATIONAL_BROWN_PROFILE. Lines71-84 choose Rational Brown first, then HDMI fisheye, then bounded Brown. Owner91 selects FORCE_TILE8 and TILE8_OVERLAP_WRITER from `RATIONAL_BROWN_PROFILE ? 1 : HDMI_FISHEYE_PROFILE`; hence profile2→0 does not change those flags when Rational=1. System and owner otherwise only forward this parameter. Therefore profile2→0 canonicalizes an inactive alternate profile for this fixed Rational build. It is not safe to generalize this conclusion to Rational=0. ON adapter40-44 explicitly requires0.

### MAX_RADIUS_Q22: unreachable bounded-Brown radius

Original top216 passes the private board-header radius symbol. Core84 passes MAX_RADIUS_Q22 only to bounded Brown in the final else branch, which is not elaborated when Rational=1. The rational mapper uses its separate retained fixed profile and ROM. System/owner/engine only forward this parameter. Therefore explicit0 does not change active Rational geometry, while satisfying ON adapter40. No private radius/profile values need to be republished.

### RASTER_DOUBLE_BUFFER: not capture/display ownership or result-bank count

Original top215 passes1. Old system97 and old owner91 only forward it. Original engine81 forwards it to `ddr_adaptive_result_writer_capture_local`. That module in `source/rtl/experimental/ddr_adaptive_result_writer.v:12` FIRST chooses macro-rowburst when TILE8_OVERLAP_WRITER && GROUP_WIDTH!=16 && MACRO_TILE_HEIGHT!=8. With Rational=1 owner91 supplies TILE8_OVERLAP_WRITER1, group64 and macro32, so this condition is true. `else if(RASTER_DOUBLE_BUFFER)` at33 is unreachable. The selected macro writer at13 receives CRC_FOLD_BITS and has no RASTER_DOUBLE_BUFFER argument. Engine30 use_tiles is true for RAW as well as CORR because TILE8_OVERLAP_WRITER is nonzero; KEY1 RAW cannot dynamically fall through to the raster writer.

Consequently1→0 does not change the selected legacy macro writer, its CRC, input capture banks, display FIFO, or frame result-bank ownership in this exact native Rational macro configuration. It does NOT turn double-buffered capture/display off. Result-bank count remains RESULT_BANKS2; bank addresses still use BANK_STRIDE. New system8/100/124 only declares/forwards RASTER_DOUBLE_BUFFER; new adapter40 checks it and131 forwards it only in its internal legacy branch. ON KEY1 directly instantiates run8 macro writer at85 with CRC_FOLD_BITS; no raster selector exists there.

Important distinction: ON DOES intentionally replace owner/engine logic. Adapter95-116 adds extended completion identity/current-edge gating. Those are real owner-control differences, unrelated to changing RASTER_DOUBLE_BUFFER. New system111/135 preserves the existing display_done && !failed gate in both branches; that gate is not a newly introduced difference. A direct old/new system diff shows only module/parameter declaration and owner generate-selection additions, with capture/display/arbiters unchanged. This reachability argument does not certify all new owner/CRC behavior or vendor implementation; it proves only the scope of the raster parameter.

