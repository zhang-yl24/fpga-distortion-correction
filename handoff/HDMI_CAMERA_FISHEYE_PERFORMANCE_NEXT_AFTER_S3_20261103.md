# S3 实测之后：1080p 鱼眼下一轮提帧计划

日期：2026-11-03。本文是下一候选的设计与验收计划，不属于已冻结的 77 文件证明闭包；没有实现 RTL、运行 EDA、操作 P:/硬件或执行 Git。默认目标保持 **1920×1080 的完整鱼眼校正、RGB565 结果及 30Hz 显示**。下文分别标明实测、源码事实和估算。

## 1. 已经获得的改善与当前上限

| 指标 | 已验 C | 新 S3 实测 |
|---|---:|---:|
| 处理帧率 | 4.310345 FPS | 5.000000 FPS |
| 唯一完整结果显示 | 4.275862 FPS | 5.000000 FPS |
| HDMI 刷新 | 30Hz | 30Hz |
| 最近一帧处理时间，125MHz 时钟口径 | 222.479248ms | 168.663272ms |
| 统计窗口 | 30 样本 / 29 秒 | 30 样本 / 29 秒 |

S3 唯一结果帧率比 C 提高约 **16.94%**；最近一帧处理时间减少约 **24.19%**。这两个百分比的分母不同。S3 窗口内 processed、captured、unique 均增加 145，刷新 870 次、重复 725 次、blank 增量 0；30 个样本均无 failed/fault。host 独立计时得到约 5.000101 FPS，与 core 计数一致。它是此次 S3 SRAM 镜像的测量，不能仅凭与 C 相同的 UART build_id 识别版本。[S3 实测回执](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/72c68990e5-receipt.json)、[C 实测回执](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/77caff3880-receipt.json)

S3 实测绑定的 bit SHA256 为 `ae6be718eaa60fdcd1ba252c08133e7e24d22d247d2a649d21f0d1f7be4a4d16`，回执 SHA256 为 `ad9a9094ce85e606436b18d1a6ad0dc3077b05e65baa1a370507d3017b2b3805`。最近一帧为 21,082,909 core 周期，即平均 **10.1673 周期/输出像素**。坐标核已有 II=1 的验证，当前平均开销明显来自整条读写链路的等待；不应先复制多路坐标核。[mapper native 证据](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/5f7bb6a526-simulation.json)、[当前 core](../distortion/rtl/experimental/hdmi_camera_fisheye_core.v)

## 2. 先分清帧间交接与帧内处理

由窗口帧率推得平均结果间隔约 200ms；用最近一帧处理时间相减，得到约 **31.337ms 的间隔余量**。这是跨窗口平均值与最近一帧的差，不是已测量的 bank-wait 计数。当前 30 个处理时间样本约为 168.604～168.764ms，也支持这一量级。

源码中存在完整的节拍解释：

- `hdmi_camera_fisheye_bank.v:43` 的 `source_ready` 要求 `!processing && !pending`；`engine_done` 才把 processing 清零、pending 置一。
- 同文件第 76～81 行仅在 display request 握手时清 pending，并翻转 write_bank。显示请求由输出刷新边界触发。
- `hdmi_camera_fisheye_system_c.v:220` 要求 reader 完成、像素完成、reader_idle、FIFO 为空及标识/CRC 正确，才释放显示 lease。
- `hdmi1080_input_dma.v:46` 在 `source_valid` 尚未被消费时不发下一份 capture grant。两份源 bank 已允许一定程度的采集/处理重叠，但不是无限队列。

168.663ms 刚超过 `5 × 33.333ms = 166.667ms`。若下一轮启动受显示边界量化，落到第六个边界就是 200ms、5 FPS。**这是由 RTL 与实测共同支持的推断，仍须时间戳确认，不能把全部 31ms 都确认为显示等待。** [bank](../distortion/rtl/experimental/hdmi_camera_fisheye_bank.v)、[系统 lease](../distortion/rtl/experimental/hdmi_camera_fisheye_system_c.v)、[输入 DMA](../distortion/rtl/experimental/hdmi1080_input_dma.v)

两个结果 bank 中，一个可能被 front/display lease 占用，另一个存着 pending 完整结果。此时没有第三个可写 bank。因此，**不能单独删除 `!pending` 或提前翻转 write_bank**；那会覆盖未显示结果或正在扫描的数据。

建议先做两个可区分的小目标：

1. 记录 engine-start/done、pending-set/clear、source-offer/accept、display-grant/done 的 core 时间戳及等待周期，确定 31ms 的实际分布。把处理从 168.663ms 降到 **<166.667ms** 才只是跨过 6 FPS 的理论边界；工程目标先设 **≤160ms**，留出交接余量，再验唯一显示是否达到 6 FPS，不能保证仅过阈值就达到该帧率。完整 1080p 的 10 / 15 / 30 FPS 分别要求处理与 bank 交接的持续总间隔不超过 **100 / 66.667 / 33.333ms**。
2. 若证实 bank 等待显著，再评估第三个结果 bank。以当前 4MiB stride 计，增加 **4MiB 外部 DDR 保留空间**及 descriptor/所有权状态，不需要在片上存一整帧。必须把“显示中、待显示、可写”三类状态分开；pending 队列满时反压或按明确策略丢弃完整结果，不能覆盖 lease。即使完全消除帧间等待，按当前单帧耗时倒数也只有约 **5.929 FPS**，它解决不了 30 FPS 的帧内处理需求。

## 3. 帧内首要矛盾是访问局部性和串行 miss

当前 engine 的 `use_tiles=0`，INDEX_BITS=7；cache 为 128 条 × 128 像素 × RGB565，即 **32KiB 逻辑像素容量**。每次 miss 发 256B/8-beat 读请求，收到后再用 8 拍 scatter 写入。慢查询会先排空 fast 输出，锁定查询并依次保存四邻域。读仲裁器同一时刻只跟踪一个已选请求；display FIFO 水位不足 64 时优先显示读。[engine:20、39](../distortion/rtl/experimental/hdmi_camera_fisheye_engine.v)、[cache:94、160、174、354](../distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v)、[读仲裁器](../distortion/rtl/experimental/ddr_read_arbiter_fill8r2.v)、[显示优先入口](../distortion/rtl/experimental/hdmi_camera_fisheye_system_c.v)

S3 窗口 miss 增量 / 处理帧数为 `39,883,757 / 145 ≈ 275,060.39` 次 fill/帧，与固定镜头、raster 地址模型的 275,060 次非常接近。按计数计算，鱼眼源读取约 **70.42MB/帧、352.08MB/s（5 FPS）**；不是只读取一份 4.1472MB 的源帧。miss_fraction 约 3.69% 的分母是有效邻域访问，不宜把它解释成“只有 3.69% 的输出像素慢”。[S3 回执](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/72c68990e5-receipt.json)、[raster 模型](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/9710fe2461-cache-address-profile-a.json)

C 的 32 拍 scatter 改为 S3 的 8 拍，按固定地址模型估算可少 `275,060 × 24 = 6,601,440` 周期，即 **52.812ms**；两份实测最近一帧的差约 53.816ms。两者量级吻合，支持继续优化 miss 路径，但不能据不同帧样本把全部改善精确归因于 scatter。[旧计划与单元证据](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/f9614ec88f-HDMI_CAMERA_FISHEYE_PIPELINE_NEXT_20261103.md)

## 4. 优先实现路线：8×8 发射与能重叠的行缓冲 writer

下一主候选保持同一镜头参数、坐标算术、双线性采样和输出像素数，只改变查询顺序及结果缓冲方式：

1. corrected 模式按 8×8 tile 发射，tag 继续携带 global raster index；raw/identity 优先保留 raster 快路。模式仍按整帧锁存。
2. 使用两份八行 stripe，分别 COLLECT 与 DRAIN；每份为 `1920 × 8 × 2 = 30,720B`，总计 **60KiB**。
3. 排空改为同步 RAM 每拍 issue 一个像素、下一拍 PACK 的有效流水；保留完整 256 像素 burst 缓冲，AW/W 背压时停止 issue 并保存未返回像素。CRC 按实际 raster PACK 次序更新，不能按 tile 收集顺序计算。
4. READY stripe 不得被覆盖；最后输入像素、最后 RAM 返回、最后 PACK、最后 W beat、最终 CRC 与 frame done 必须分别记账。

**仅打开现有 tile 开关不够。** 当前 writer 只有单 stripe，且 READ/PACK 各占一拍，收满时停止接收。即使 DDR 零等待，约有 `N + 2N + N/16 = 6,350,400` 周期，即 **50.8032ms/帧** 的串行下界，还未计地址、排空及上游停顿。[writer:14～42、63～105](../distortion/rtl/experimental/ddr_adaptive_result_writer.v)

一像素流水排空可保守按每 256 像素 `256 issue + 1 RAM 填管 + 1 AW + 16 W = 274` 周期估算。1080p 共 8,100 个结果 burst，约 **17.7552ms/帧**；与另一 stripe 的 COLLECT 重叠。此数字只说明 writer 有机会满足 30 FPS，不包含 DDR 仲裁停顿，也不保证整个帧严格等于生产/排空两者的最大值。

### 地址模型只用作排序依据

下表从已有 C 地址 trace 中，仅将每次 fill 的 scatter 成本从 32 改为 8 拍；不是新 RTL 周期仿真，也不是板上 FPS。

| 查询顺序 / INDEX | 逻辑 cache | 256B fill/帧 | 乐观模型时间 @125MHz |
|---|---:|---:|---:|
| raster / 7，当前访问方式 | 32KiB | 275,060 | 87.425ms |
| raster / 8 | 64KiB | 184,736 | 64.097ms |
| raster / 9 | 128KiB | 123,305 | 48.189ms |
| 8×8 tile / 7 | 32KiB | 49,465 | 29.181ms |
| 8×8 tile / 8 | 64KiB | 37,483 | 26.105ms |
| 8×8 tile / 9 | 128KiB | 31,110 | 24.459ms |

tile/7 比 raster/7 少约 82% 的 fill，源块 payload 从约 **70.4MB/帧降到 12.7MB/帧，约减少到原来的 1/5.56**，因此优先级高于直接扩到更大的 raster cache。30 FPS 的周期预算是 4,166,666.67，tile/7 乐观模型只剩约 **519,013 周期 / 4.152ms**，平均每 fill 约 10.49 拍的额外余量，不能承诺达到 30 FPS。[tile trace 模型](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/151cc68f79-cache-address-tiled-profile-a.json)

再做一个明确标注的敏感性外推：S3 最近一帧实测比 raster/fill8 乐观模型多 10,154,844 周期。若把这部分全部除以 fill，得到约 36.92 拍/fill；若不合理但便于比较地把该残差线性带入 tile/7、8、9，时间约为 **43.79 / 37.18 / 33.65ms**。残差混合了流水排空、读等待、写反压及争用，不能当作实测 DDR 首拍延迟。这一计算说明：tile 模型的 29.18ms 很可能仍需 prefetch/重叠优化，而非给出新的 FPS 预测。

## 5. 在 tile 基础上做 prefetch，再决定是否扩 cache

先记录 AR 等待、AR→首 R、R beat 间隙、scatter、slow-query drain、writer 反压、display-urgent 占用的周期/直方图，避免把所有残差叫作 DDR 带宽不足。

最小 prefetch 方向是利用当前静态镜头地址可预测性及 lookahead 查询，准备下一块，需求访问优先。可以评估一份额外 256B fill buffer，使上一块 scatter 与下一次接收有机会重叠；或增加 16/32 条 mapped-coordinate FIFO，裸 payload 按 73bit/条约为 146/292B。实际还要计 tag、epoch、状态及 RAM 对齐。

这不是把 ARVALID 简单提前：当前 cache 在一个全局 miss 状态机中收 R，仲裁器也只有一份 owner/beat 状态。第一版宜保持 **单个总线 outstanding、RID=0 和响应顺序**，先证明 buffer 交接与端口独占；要真正支持多 outstanding，必须另开协议候选和响应队列。预取不得驱逐尚在使用/尚未发布的行；相同 DDR 地址的新帧也必须按 epoch 失效，不能复用上一帧像素。[cache 状态机与 frame drain](../distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v)、[单 owner 仲裁器](../distortion/rtl/experimental/ddr_read_arbiter_fill8r2.v)

若 tile/7 的实际额外等待仍不足以收敛，再比较 INDEX8/9、有限关联/冲突缓冲、预取深度。每次只改一个主变量，保留每帧 fill、stall 和 unique-presented 对比。

## 6. 资源和带宽预算：新增量先列清楚

当前实际 S3 已用 LUT 13,805/66,600（20.73%）、逻辑 FF 17,858/133,200（13.41%）、APM 54/240（22.50%）、DRM 19.5/155 个 36K 当量（12.58%）。片上 RAM 总容量池 **697.5KiB**，已用 **87.75KiB**，名义剩余 **609.75KiB**；18K 与 36K 是同一容量池，不能重复相加。CLMA/CLMS 已分配站点约 37.24%/35.24%，局部放置、端口和路由时序仍要检查。完整实测数量及来源见 [S3 资源报告](HDMI_CAMERA_FISHEYE_S3_RESOURCES_20261103.md)。

以下为下一候选的新增设计估算，不是已实现利用率。双八行相对单 stripe tile 设计约多 **30KiB**，在该容量池内有开展实验的空间；是否映射成功及其真实代价仍需新构建。

| 候选改变 | 逻辑容量/代价估算 | 主要检查点 |
|---|---|---|
| 双八行 stripe | 总 60KiB；按 16bit×1024 组织粗估 30 片 18K RAM，若深度取整约 32 片 | 实际 TDP 模式、宽深拆分、端口碰撞、RAM 读延迟 |
| 双 burst buffer | 总 1KiB，相对现有单 512B 缓冲多 512B | AW/W 停顿及最后 beat 保持 |
| INDEX7→8 | cache 总 32→64KiB，新增 32KiB 像素存储及 tag/valid | 真实 RAM 数、tag 比较和时序扇出 |
| INDEX7→9 | cache 总 32→128KiB，新增 96KiB 像素存储及 tag/valid | 先检查 RAM 余量，再讨论收益 |
| 一份额外 fill buffer | 256B；若用寄存器约 2,048 个数据位，另加元数据 | 不同 buffer 的接收/写入所有权 |
| 第三个结果 bank | 外部 DDR 多保留一个 4MiB stride；少量片上 descriptor 状态 | 所有地址范围、bank ID 宽度、完整 lease/epoch 协议 |

当前 `use_tiles=0`，综合可能消除现有源码中的 stripe 数组；不能直接认为 S3 已经占用 30KiB 可免费沿用。双 stripe 相对“单 stripe tile 设计”多 30KiB，但相对实际 S3 应按**最多新增全部 60KiB**预算，最终以网表/资源报告核对。若 RAM 余量不足，先设计更小块重排与逐行 CRC 合并方案；它需要额外 CRC 顺序证明，不能直接缩小 stripe 数组后继续声称 raster CRC 不变。

1080p RGB565 一帧 4,147,200B，30 FPS 的结果写、显示读各需 124.416MB/s。假设输入只接受 30 FPS：

| 30 FPS 目标下的有效 payload | raster/INDEX7 | tile/INDEX7 |
|---|---:|---:|
| 鱼眼源块读 | 2,112.461MB/s | 379.891MB/s |
| 输入帧写 | 124.416MB/s | 124.416MB/s |
| 结果写 | 124.416MB/s | 124.416MB/s |
| 显示读 | 124.416MB/s | 124.416MB/s |
| 合计 | **2,485.709MB/s** | **753.139MB/s** |

若实际输入接收 60 FPS，再增加 124.416MB/s。256bit×125MHz 是 4GB/s 的接口名义字节时钟，不是外部 DDR 保证可用吞吐，也不能把读写各算一份后相加。refresh、读写切换、命令开销、显示优先及不连续访问都要另外支付。

目标 30 FPS 只需平均 0.497664 像素/core 周期；II=1 的单路坐标核在无停顿时已有约 60.28 FPS 的像素吞吐。多 lane 会增加坐标 DSP、四邻域读端口、cache 复制和结果重排压力，先解决局部性与等待更合理。提高频率也不列为第一步；必须有新布局布线和完整时序结果，不能把当前有限裕量当成升频许可。

## 7. 分阶段验收与停止条件

| 阶段 | 交付与判断依据 |
|---|---|
| P0：可解释的 5 FPS | 新候选增加整帧时间戳、pending/bank wait、cache/writer stall 计数；30 秒窗口能把处理与交接等待对上。遥测若加字段须新协议版本，不能悄悄改变现有 96B 包。 |
| P1：小幅跨档 | 保持 raster/像素结果不变，先验证处理 ≤160ms 或第三结果 bank 的交接收益；真实唯一显示 ≥6 FPS 才称跨档。记录端到端延迟，避免只排更多帧造成更旧的画面。 |
| P2：主要帧内提速 | 独立 8×8+双 stripe writer：先 small 独立像素/CRC oracle，再完整 1080p；至少解释 fill 数量、stripe 等待和 RAM/DDR 停顿。模型达标不算硬件达标。 |
| P3：逼近 30 FPS | 按实测残差选择预取或 INDEX8/9；最终以 30 秒以上实机 processed 与 unique-presented 同时达标，刷新率单独报告。 |

每个候选都必须满足：

- 完整 2,073,600 像素的独立参考、四邻域/小数/tag 对齐、raster CRC；raw bit-exact，corrected 使用相同镜头参数和原定误差界。
- tile 跨边、右/下边界、黑边、重复/遗漏/乱序 tag、满 stripe、最后 RAM 返回与最后 W 同拍、AW/W/AR 背压、AR 同拍首 R、六类 cache 故障与 sticky quarantine。
- 持续 60Hz 输入下至少覆盖多次 bank 周转、corrected→raw→corrected、处理中 KEY 变化及 warm reset；不得读写同一被占用 bank，不提前发布，不覆盖 READY/pending/front。
- 显示 lease 继续验证 reader CRC、实际像素 CRC、完整计数、FIFO drain 和 epoch；不得以解除安全条件换取帧率。零 underflow、零 CRC mismatch、无新 fault，主动丢整帧与异常必须分开统计。
- 新原生宏/网表、资源、source/CDC/reset、引脚及十张 STA 汇总完整闭合，再绑定新 bit/program/wire 回执。30 FPS 若仍未达到，按实测报告原因，不换用模型倒数或 HDMI 刷新数。

## 8. 可选预览模式需要单独选择

上述主路线保持完整 1080p 校正。若用户另外选择低延迟预览，可研究 1280×720 校正后输出到 1080p，或更小的处理缓冲；这些会牺牲细节，并新增缩放/滤波及标定尺度处理。1280×720 像素数是 1080p 的 44.44%，但输出上采样、读写与显示开销仍可能保留，整体 FPS 不按像素比例直接换算。

960×540 的像素数是 1080p 的四分之一，但当前 tile 约束要求 HEIGHT 为 8 的倍数；540 行不能直接打开 tile。应选择有明确黑边约定的 960×544，或实现并证明边界 tile。预览回执必须明确处理分辨率，不能称为“完整 1080p 校正 30 FPS”。

## 9. 依据与可复核身份

除上文链接，关键当前 RTL SHA256：

| 文件 | SHA256 |
|---|---|
| `hdmi_camera_fisheye_engine.v` | `bd5a2e4b6b58f476066ce13b566df0c0be0751de54e911a8dcad993e5c9b9179` |
| `hdmi_camera_fisheye_bank.v` | `59020a41cc9d9e89a92a4973a4e227fdd1b243d15f80c71d3df1af6a39473616` |
| `ddr_adaptive_result_writer.v` | `fab6d79260ce4b81a54bfd5d6befde535e7aea1230ce2e5fdd1398655ffc20a6` |
| `ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v` | `ccddbc0293698184a3695744d7fca88350969ccc5f69cb1762b39eac84a0d294` |
| `hdmi1080_input_dma.v` | `ba4c24e483452bd4a3c52bc74ecece429eb793e17c73c1a037af3ebec4c48660` |
| `ddr_read_arbiter_fill8r2.v` | `de0c11db399033511048ef18a90345881f8f13d2458b81ff6daa131f79393ec7` |

raster 地址模型 SHA256：`5eaa3306c3ba766f93cfbc2f326a4daddc408f57210ff3311afbee9e8efebf73`；tile 模型 SHA256：`74734ccedb2f23b5b6f7f7d804fc649d3195ef2e434cae5fdff511cfe34ea66f`。模型都明确 `hardware_measured=false`，只覆盖当前固定镜头地址序列。
