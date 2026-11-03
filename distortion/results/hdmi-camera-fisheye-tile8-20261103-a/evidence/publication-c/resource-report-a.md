# tile8 当前路由构建资源核对（2026-11-03）

当前 tile8 **Route Optimize 完成后的构建**使用 13,181 LUT、13,987 FF、35.5 个 36K RAM 当量。与已上板的最终 S3 相比，LUT 减少 624，FF 减少 3,871，RAM 增加 16 个 36K 当量。

本报告只绑定 `build-a` ADF：`7bf8bded0b6db30c5c942800a28939bb2aeea90e2fda6bea7e5f5bd9f1e88e6a`。它不是最终物理验证通过声明，也没有运行 EDA、访问硬件或测量 FPS。S3 对照来自此前最终已选版本；本次只重核其记录来源 SHA。

| 资源 | S3 最终用量 | tile8 当前构建 / 容量 | tile8 占用率 | 差值 | tile8 余量 |
|---|---:|---:|---:|---:|---:|
| LUT | 13805 | 13181 / 66600 | 19.79% | -624 | 53419 |
| FF | 17858 | 13987 / 133200 | 10.50% | -3871 | 119213 |
| CLMA | 4348 | 3442 / 11675 | 29.48% | -906 | 8233 |
| CLMS | 1753 | 1375 / 4975 | 27.64% | -378 | 3600 |
| DRM（36K 当量） | 19.5 | 35.5 / 155 | 22.90% | +16 | 119.5 |
| APM | 54 | 54 / 240 | 22.50% | +0 | 186 |
| GPLL | 4 | 4 / 6 | 66.67% | +0 | 2 |
| USCM | 6 | 6 / 32 | 18.75% | +0 | 26 |
| BKCL | 5 | 5 / 6 | 83.33% | +0 | 1 |
| CCS | 1 | 1 / 1 | 100.00% | +0 | 0 |

LUT = CLMA 9,449 + CLMS 3,732；FF = CLMA 10,358 + CLMS 3,629。百分比由原始 used/capacity 重算；PDS 表内显示百分比有向上取整。LUT-CONST 和 Distributed RAM 单列保存在 JSON，未重复加到 LUT 总数。

## 双 stripe RAM 的实际映射

原生导出网表共有 **34 个 V_DRM36K_E1、3 个 V_DRM18K_E1**，合计 35.5 个 36K 当量，1,308,672 bit（159.75 KiB）。155 个 36K 当量为同一 RAM 资源池，总容量 697.5 KiB，当前余量 119.5 个当量（537.75 KiB）；36K/18K 两种数量不能视为两套独立池相加。

`writer/stripe0`、`writer/stripe1` 各实际映射为 **8 个 DRM36K**。两份逻辑缓冲为 2 × 1920 × 8 × 16 bit = 60 KiB；每份按深度取到 16K，每个原语承担 16K × 2 bit，映射有效数据宽深容量合计 64 KiB，16 个物理块的标称总 bit 容量为 72 KiB。两种容量的差别包含深度取整与原语额外位容量。新增的 16 个实际原语恰好等于全设计 +16 DRM 的差值。

模式需按来源分别表述：综合映射表报告 **SIMPLE_DUAL_PORT / NORMAL_WRITE / 16 K × 2**；实际原生原语参数是 **RAM_MODE=TRUE_DUAL_PORT、DATA_WIDTH_A/B=2**，A 写、B 读，DOA 未用、WEB 接 ground 命名的常量网。两者是功能映射与底层原语不同层次的描述，不能把综合表字符串冒充原生参数。16 个实例名、行号、参数与端口及 18 行综合映射原文均在 JSON 中。

## 提帧的资源余量判断

当前 LUT/FF/RAM/APM 总量支持继续研究增加计算 lane。仅作粗略算术参考，将当前整个设计的这四类用量都乘二，会得到 LUT 26,362（39.58%）、FF 27,974（21.00%）、DRM 71（45.81%）、APM 108（45.00%）。这不是双 lane 的实现或综合测量，不能证明可布通、能满足时序、DDR 带宽足够或 FPS 翻倍。时钟和 IO 需要共享设计：CCS 已 1/1，BKCL 已 5/6，不能照搬复制。

LUT/FF 的下降是整个候选的实测资源差，包含 engine/writer/bank 逻辑与布局布线差异；没有逐模块差分证据，不能全部归因于某一个模块。当前 RAM 余量较 S3 少 16 个 36K 当量，逻辑余量增大，后续选择仍应由实际等待周期、DDR 流量与上板 FPS 指导。

## 主要证据

- Route Optimize 资源原文：[run_route_optimize.log](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\build-a\place_route\run_route_optimize.log:68)，SHA `a65481a18c3e0eb1b43edaecaa96a3fb3f04d81e8783ee04ab04ff9bd18aeeee`。
- 当前构建原生网表：[hdmi_camera_fisheye_top_sim.v](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\export-a\generate_netlist\hdmi_camera_fisheye_top_sim.v)，SHA `74b386c47d132a3d1fda06496461b53f806ac80fb1891ee4e8e2db5f61997454`。
- RAM 映射原文：[apm_drm_lutram_utilization.log](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\build-a\synthesize\apm_drm_lutram_utilization.log:975)，SHA `1c3720f7a0c21273f6248c6c54cfdd2bc1dd4517877e48ee30e05a9d35aec1b6`。
- 构建完成回执：[execution-result.json](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\build-a\execution-result.json)，SHA `a12118c7cab4fe478d8a7af02f091f28c98330fb4186869c0dc73a8add12bca0`。
- 原生导出回执：[result.json](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\export-a\result.json)，SHA `6d4df3e0d97102e944dc9c8a38b788c7c1008ec6ca6e05c8670578d7fc2303e6`。
- S3 对照报告：[HDMI_CAMERA_FISHEYE_S3_RESOURCES_20261103.json](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\handoff\HDMI_CAMERA_FISHEYE_S3_RESOURCES_20261103.json)，SHA `177b9fa0492b216024d658fe2c4c7a99a3dccf247ff1fca81705d031aef7afa4`。
- 完整结构化证据：[resource-report-a.json](D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-tile8-20261103-a\resource-report-a.json)，SHA `9ea8a0e81aef10fb8ea8b0547c916874387392906ff3029b2fad12d608dad3d2`。
