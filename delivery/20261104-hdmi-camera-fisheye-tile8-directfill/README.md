# Tile8 directfill INDEX8 v3

This delivery preserves the original A/B/C archive bytes and adds the selected INDEX8 directfill source and actual v3 physical, SRAM and saved UART evidence.

源码：[directfill缓存](../../distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v) · [INDEX8处理引擎](../../distortion/rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v)。归档：[阶段D包](../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a)。

| Actual UART window | Source FPS | Captured FPS | Processed FPS | Unique presented FPS | Scan refresh FPS | Last completed frame (ms at125MHz) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30-second acquisition | 60.001151 | 15.000288 | 15.000288 | 15.000288 | 30.000575 | 35.465376 |
| 600-second acquisition | 60.001200 | 15.000300 | 15.000300 | 15.000300 | 30.000600 | 35.435976 |

Actual bit: aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b (3,791,112 bytes). FinalADF: 2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430.

实测结论：新唯一结果帧约 15.00 FPS，30 新帧/秒目标未达。HDMI 约30次/秒扫描刷新包含重复显示，不能作为30新帧目标达成。

短测 30 个 last-completed-frame gauge 的均值为 35.463153 ms；旧版同类短测均值为 44.331588 ms，缩短 20.0048%。这些是同类采样 gauge，按125MHz换算，不是光学端到端延迟或完整逐帧分布。

后续提帧方案与证据分层见 [结果与下一步方案](docs/TILE8_DIRECTFILL_RESULTS_AND_NEXT_PLAN_20261104.md)。

All ten physical summary tables passed with zero failures/TNS. Final physical proof SHA256: 903741272bd2529ca9bc72dec2a333d44a0b74760442f8705906c6d92adb6ada.

Final resource counts bound to the programmed SRAM image: LUT 13875.0, FF 14397.0, DRM 43.5, APM 54.0.

The measured unique result rate and HDMI scan rate are listed separately. Process-cycle values are sampled last-completed-frame gauges, not an optical latency distribution. The source-to-captured difference reflects admission; it is not an invalid-image-drop count. The protocol exposes no image overflow or live underflow counter.

Use immutable d only for saved-wire analysis and e for complete v3 source/bit/program/release identity. The saved comparison uses verify_directfill_v3_vs_tile8_a.py and the actual two reviews; no model latency is substituted for board FPS.

CI checks original C and new D bytes plus the explicitly mapped finite110-source/cache-unit/collision contract. It does not rerun full native EDA, STA, bit generation or board tests. Large physical artifacts stay local with original path/SHA256/size indices; the actual bit is included.

Run: python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py --package distortion/results/hdmi-camera-fisheye-tile8-20261103-a
