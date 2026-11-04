# Tile8 cache research — 2026-11-04

**板上发布版本仍约 15 个新帧 FPS。此包为隔离研究，没有新位流、SRAM 下载或新板测结论。**

c 的慢查询状态优化通过了功能仿真，但普通 core setup 为 −0.714 ns、21 fail。d 仅删除未使用的 SELECT 逻辑；其 raw core/RAM 结果也只属于研究，不能代替完整 physical/source/bit/program 门禁。2 路 256 KiB 原型从原 tagpipe 单独派生，分别保存单元、边界、系统仿真与 raw 证据。

**最后 CHOOSE + FRAME_CLEAR 组合仍未过时序：slow setup -1.481 ns、TNS -46.258 ns、224 个失败 capture pins，全部仍属 FAST metadata → accept 反馈。** 已消失的 writer ready、slow choose/fault 和 frame admission/full-clear 负路径不代表整体签核；此包记录截至12:19的实现结果，未生成新位流或下载；后续 FAST 修复在独立 namespace 推进，不纳本包接受。下一步独立 metadata response queue 方案仅为设计建议。


实际完整 1080p 仿真如下，均沿用 125 MHz core。Normal corrected 是通常延迟模型的 corrected 帧；40lat 为持续输入、首返回延迟 40 拍模型的四帧。两者都不是板测，unique IDs 是完整扫描过的不同结果 ID，new-ID interval 为相邻新 ID 首次 scan_done 的间隔，不能把正常 scan 30Hz 当成新帧30FPS。

| 版本 | Normal corrected / raw ms | 40lat 各帧 ms | fills（normal / 40lat） | scan unique IDs（normal / 40lat） | new-ID interval ms（normal / 40lat） |
|---|---|---|---|---|---|
| INDEX8 baseline | [25.983784] / [22.069496] | [37.981864, 39.591704, 39.606824, 39.605128] | [37483] / [37483, 37483, 37483, 37483] | [1, 2] / [1, 2, 3, 4] | [33.333333333] / [66.666666667, 66.666666666, 66.666666667] |
| slow-query c | [23.707744] / [21.172664] | [35.654248, 37.452176, 37.44308, 37.452184] | [37483] / [37483, 37483, 37483, 37483] | [1, 2] / [1, 2, 3, 4] | [33.333333333] / [66.666666667, 66.666666666, 66.666666667] |
| direct10 tagpipe | [23.551504] / [22.587248] | FAILED（不列完整数字） | [24833] / [] | [1, 2] / [] | [33.333333333] / [] |
| 2way256 tagpipe | [22.422472] / [22.587248] | FAILED（不列完整数字） | [20630] / [] | [1, 2] / [] | [33.333333333] / [] |
| FIFO safe-stop | NOT_RUN（不列完整数字） | [28.942216, 29.83076, 29.828864, 29.828864] | [] / [20630, 20630, 20630, 20630] | [] / [1, 2, 3, 4] | [] / [33.333333333, 33.333333334, 33.333333333] |

direct10 tagpipe Latency40 完整运行失败：`ValueError: original full-system assertions/finish failed`。原始 partial 表仅供故障定位，不当作完整性能通过。


2way256 tagpipe Latency40 完整运行失败：`ValueError: original PASS/finish/assertions failed`。原始 partial 表仅供故障定位，不当作完整性能通过。


raw control 在各版本可能因 writer/DDR 相位而增减，不能将 corrected 改善泛化为所有模式加速。上表保留实际 raw 控制帧，未用模型修正它。

FIFO safe-stop 最终实际完整运行 **Passed=true**，模拟器运行用时 3563.404 秒；四个新 ID 共扫描 8,294,400 个独立结果像素，完整 scan CRC32 为 ['ef786fd8', '8c89a4d7', '8c89a4d7', 'ef786fd8']，final_drain=True。这是有限四帧的完整仿真，通过不授予最后 CHOOSE + FRAME_CLEAR 的 native 性能或 STA 接受。

原 direct10 与原两路 stress 在 16-input 尾段将 scan_enable 于活动 display lease 中途撤销，触发原有 bad scan completion/fault07 断言，整次终态均为 FAILED。小诊断 old-stop 的 Passed=true 表示成功复现预期故障，CompleteSystemPassed=false，不是完整系统通过。safe-stop 在小诊断中完整通过；其新 benchmark 只改变边界停止刺激并保留原断言，新的 FIFO safe-stop 完整 stress 是单独运行、单独一行，不能洗掉两个原失败。

实际 raw 普通 core 与 RAM 映射（不是完整 physical signoff）：

| 版本 | slow setup ns / fail | 十普通 core 表 | cache DRM36K / 逻辑 bytes |
|---|---|---|---|
| slow-query c | -0.714 / 21 | False | 16 / 65536 |
| dead SELECT d | 0.045 / 0 | True | 16 / 65536 |
| 2way256 tagpipe | -1.155 / 687 | False | 64.0 / 262144 |
| 2way256 engine FIFO | -2.067 / 3018 | False | 64.0 / 262144 |
| 2way256 CHOOSE + FRAME_CLEAR | -1.481 / 224 | False | 64.0 / 262144 |

2 路原型 raw route 总资源：LUT 21528、FF 16224、DRM 101、APM 54。其中像素 cache 为 64 个 DRM36K、262144 bytes；总 DRM 还含 tag/IP，不能与像素 cache 数混用。这是未上板、普通 core 时序失败候选的 draft 资源身份，不是最终发布资源。

各独立 raw 资源标签（均未上板，完成 raw 也不是 physical signoff）：

| 版本 | LUT | FF | 总 DRM | APM |
|---|---:|---:|---:|---:|
| 2way b raw | 21528 | 16224 | 101 | 54 |
| 2way + engine FIFO raw | 21583 | 16267 | 101 | 54 |
| CHOOSE + FRAME_CLEAR route draft | 20841 | 16273 | 101 | 54 |
| CHOOSE + FRAME_CLEAR actual completed raw | 20841 | 16273 | 101 | 54 |

新增的 engine FIFO 探针把单项 elastic stage 改为两个完整 RGB/mask/tag 槽，以 registered count 决定 ready，切断 writer ready 组合反馈。其 unit 用真实 engine 和 core/writer 接口 stubs；小系统和 raw 结果各按实际 role 保存。原两路版本 normal 完整测试通过，stress 终态失败；两者都不能授予 FIFO 新版本通过。原 687 个时序端点中 writer 反馈族为 257，其余 430 个端点仍需真实新 STA，不能承诺一个 FIFO 修好全部。

容量模型从同一完整冷帧轨迹复现 INDEX8/9 direct 的 37,483/31,110 fills。256 KiB 2 路 LRU 为 20,630 fills；latency0/8/40 合成服务模型省时约 4.214/5.297/9.615 ms。这些是地址/周期模型，不是 RTL 或板上 FPS；相联 tag/LRU/way 选择开销、共享 DDR 仲裁和显示调度尚不能由模型代替。

例如 2 路 256 KiB 的 latency40 纯服务周期模型 28.232632 ms，与上表实际系统硬件处理计数是两个层级，不能互相冒充。

便携检查命令：`python verify_research_portable_a.py --bundle .`。它只校验包内 SHA/大小、重放原 assoc-b 三 geometry 的 1173 个已保存有序四邻域像素/CRC 和 5 个边界案例，并运行 9 个有限 LRU 用例。CHOOSE 等新增 variant 的单元/6-boundary/peer 按实际字节保存，CI 不声称重放全部 variant HDL。没有重跑完整 1080p 仿真、EDA 或硬件，也没有继承旧 cache 或旧 STA 接受。大型 rtr/ADF/网表/轨迹仅在 `large-native-artifact-index.json` 中索引。

下一步以真实系统性能和新的 RAM/时序实现证据决定实现方向；目标持续 ≤30 ms，不从仿真 latency40 外推上板。已发布的 A/B/C/D、32 项 live source 和旧 workflow 字节保持。

[本轮两路 cache RTL](sources/assoc-ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v) · [本轮容量模型](capacity_associativity_screen_a.py)

[后续 FAST metadata 方案](docs/NEXT_FAST_METADATA_PLAN_A.md) 仅为未来设计，未实现、未仿真、未跑 EDA；不能用于本轮性能或时序接受。

保存角色终态附录：

| Role | 保存的 Passed | CompleteSystemPassed（若为诊断） | BuildCompleted | ExitCode |
|---|---|---|---|---|
| raw-c-raw-research-result-a | False | None | None | None |
| raw-c-raw-core-timing-a | False | None | None | None |
| raw-c-raw-cache-ram-mapping-a | True | None | None | None |
| raw-c-plan | None | None | None | None |
| raw-c-execution-result | None | None | True | 0 |
| raw-d-raw-research-result-a | True | None | None | None |
| raw-d-raw-core-timing-a | True | None | None | None |
| raw-d-raw-cache-ram-mapping-a | True | None | None | None |
| raw-d-plan | None | None | None | None |
| raw-d-execution-result | None | None | True | 0 |
| raw-assoc-raw-research-result-a | False | None | None | None |
| raw-assoc-raw-core-timing-a | False | None | None | None |
| raw-assoc-raw-cache-ram-mapping-a | True | None | None | None |
| raw-assoc-plan | None | None | None | None |
| raw-assoc-execution-result | None | None | True | 0 |
| phase40 | True | None | None | None |
| profile40 | True | None | None | None |
| slow-c-unit | True | None | None | None |
| slow-c-boundary | True | None | None | None |
| slow-d-unit | True | None | None | None |
| slow-d-boundary | True | None | None | None |
| slow-c-normal-small | True | None | None | None |
| slow-d-normal-small | True | None | None | None |
| direct10-normal-small | True | None | None | None |
| assoc-normal-small | True | None | None | None |
| slow-c-normal-native | True | None | None | None |
| direct10-normal-native | True | None | None | None |
| assoc-normal-native | True | None | None | None |
| slow-c-sustained-small | True | None | None | None |
| slow-d-sustained-small | True | None | None | None |
| direct10-sustained-small | True | None | None | None |
| assoc-sustained-small | True | None | None | None |
| slow-c-sustained-native | True | None | None | None |
| direct10-sustained-native | False | None | None | None |
| assoc-sustained-native | False | None | None | None |
| direct10-unit | True | None | None | None |
| assoc-unit | True | None | None | None |
| assoc-boundary | True | None | None | None |
| baseline-normal | True | None | None | None |
| baseline-sustained | True | None | None | None |
| assoc-failure-small-summary | None | None | None | None |
| fifo-unit | True | None | None | None |
| fifo-normal-small | True | None | None | None |
| fifo-sustained-small | True | None | None | None |
| raw-fifo-raw-research-result-a | False | None | None | None |
| raw-fifo-raw-core-timing-a | False | None | None | None |
| raw-fifo-raw-cache-ram-mapping-a | True | None | None | None |
| raw-fifo-plan | None | None | None | None |
| raw-fifo-execution-result | None | None | True | 0 |
| stop-old-expected-fault | True | False | None | None |
| stop-safe-small-diagnostic | True | True | None | None |
| fifo-safe-normal-small | True | None | None | None |
| fifo-safe-sustained-small | True | None | None | None |
| fifo-safe-sustained-native | True | None | None | None |
| choose-unit | True | None | None | None |
| choose-boundary-six | True | None | None | None |
| choose-normal-small | True | None | None | None |
| choose-sustained-small | True | None | None | None |
| combo-unit | True | None | None | None |
| combo-boundary-seven | True | None | None | None |
| combo-normal-small | True | None | None | None |
| combo-sustained-small | True | None | None | None |
| raw-combo-raw-research-result-a | False | None | None | None |
| raw-combo-raw-core-timing-a | False | None | None | None |
| raw-combo-raw-cache-ram-mapping-a | True | None | None | None |
| raw-combo-plan | None | None | None | None |
| raw-combo-execution-result | None | None | True | 0 |
