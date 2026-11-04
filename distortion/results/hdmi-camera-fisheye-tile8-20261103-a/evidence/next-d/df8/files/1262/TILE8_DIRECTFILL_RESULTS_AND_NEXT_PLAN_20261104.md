# tile8 direct-fill 实测结果与下一阶段提帧方案

日期：2026-11-04。结论是：**本轮把处理时间样本均值降低约 20%，但尚未提高持续唯一新画面的帧率。下一轮需要同时解决帧内 DDR 等待和帧间准入/显示相位；先定位，再选择一项改动。** 本文是只读分析与未来计划，没有修改冻结 RTL、启动新仿真/EDA 或访问串口。30 秒和 600 秒保存数据均已通过最终 e 独立复核；600 秒采集与复核由 root 完成，本文读取并绑定其真实结果。

## 1. 本次确实测到了什么

选中版本为单 lane、125MHz、8×8 查询顺序、INDEX8、64KiB 逻辑像素缓存、DDR direct-fill 和双八行 stripe writer，保持完整 1920×1080、当前 OpenCV fisheye 参数和 30Hz HDMI 扫描。

已按 root 指定命令执行最终 e 复核，读取原始 wire/receipt，并重新核对 1,211 项输入身份：

- [30 秒独立 review](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/output/tile8_next15h_20261103/saved-fps-df8-v3-30s-review-a.json)，SHA256 `e9e1dfaed071c29c9f09754ddac5a5d4ee64a7c159201ed2a3da80d137d4bfd6`，Passed=true、candidate、非 baseline。
- 本次 SRAM bit SHA256：`aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b`；FinalADF SHA256：`2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430`。不能用共享的 UART profile/build ID 代替这些二进制身份。
- [旧 15FPS 固定自检](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/output/tile8_next15h_20261103/saved-fps-old15fps-selftest-d.json) SHA256 为 `0948d88d17a711cac7aadd6e499d154091e06b47e665e9a802638a99c1f8e236`，只作为旧板测基线。

| 指标 | 已发布 tile8 基线 | 本次 INDEX8 direct-fill |
| --- | ---: | ---: |
| 采集 wall / 实际首末 host 窗口 | 旧 30 秒预算 / 28.9994941001s | 30.019177s / 28.9994439000s |
| 独立 host 唯一新帧率 | 15.0002616769 FPS | 15.0002876435 FPS |
| core 计数口径处理 / 唯一新帧率 | 15 / 15 FPS | 15 / 15 FPS |
| HDMI 扫描 / 重复扫描 | 30 / 15 次每秒 | 30 / 15 次每秒 |
| 处理周期 gauge 样本均值 | 44.3315877333ms | 35.4631530667ms |
| 新版本 gauge 最小 / 最大 / 末样本 | — | 35.406232 / 35.512552 / 35.465376ms |

新窗口内 source、captured、processed、unique 分别增加 1,740、435、435、435；扫描增加 870，重复 435，blank **增量**为 0，30 个完整包无 fault，尾部无 partial packet。启动后累计 blank 的绝对值为 1，不能说从启动起从未 blank。处理 gauge 均值减少 **20.0048%**；新旧 host FPS 的微小差值处于 host 到达时钟差异量级，不构成“帧率提升”。

这里的 30 个 `last_process_cycles` 是每秒抓取的“最近一个完成帧”样本，不是窗口内全部 435 帧的耗时分布。PGHFPS02 没有独立的 invalid-drop、overflow 或 live-underflow 计数器；`source−captured=1305` 是准入差，不能改称 1,305 个异常丢帧。串口 CRC 丢包数也不是图像丢帧数。

实际资源报告 [df8-v3-final-resources-a.json](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/output/tile8_next15h_20261103/df8-v3-final-resources-a.json)，SHA256 `afe128582829ba943cb55de9e2aeed2a353fba517dd92468f4e1d071a710b1ad`，已绑定同一 bit/SRAM：LUT 13,875/66,600（20.83%），FF 14,397/133,200（10.81%），DRM 43.5/155 个 36K 当量（28.06%），APM 54/240（22.50%）。容量余量不代表 tag mux、局部布线和时钟路径有余量。

### 已完成的 600 秒长测

[600 秒独立 review](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/output/tile8_next15h_20261103/saved-fps-df8-v3-600s-review-a.json) SHA256 `2993e59abb811f183bd0f48bc9df02ac29220814dabbed45092c106fae63ac7b`，Passed=true，1,211 项输入身份复核，且与短测的完整 program/bit/ADF/source Identity 相同。实际采集 wall 为 **600.030666s**；600 个完整包、partial 0，实际首末 host 计数窗口 **598.9880206001s**，core 窗口 599s，不能把它们统称为完整 600s 计数窗口。

独立 host processed 与 unique 均为 **15.0002999910 FPS**，HDMI 扫描 **30.0005999819Hz**。窗口内 processed/unique 各增加 8,985，扫描增加 17,970、重复 8,985、blank 增量 0；串口 CRC rejected=0、discarded=0，600 个包均无 fault。处理 gauge 均值 **35.4514648ms**，最小 35.383328ms、最大 35.524192ms、末样本 35.435976ms。这支持当前负载下长窗数字链稳定运行，仍不是完整画面光学质量或不可观测 live-underflow 计数的证明。

长窗 cache 必须用 d/e 的逐相邻样本 modulo-32 累加：hits **66,637,095,732**、misses **336,785,410**、queries **18,631,356,506**；misses/processed 仍约为 37,483 fills/帧。冻结采集器整窗口 endpoint 的 hits 2,212,586,292 少了 `15×2^32`，只保留为原始兼容摘要，**不用于本报告长窗 cache 总量或性能分析**。上述准入、重复和帧率结论与短测一致，30FPS 目标仍未达到。

## 2. 为什么处理快了，仍然是 15 FPS

**实测事实：** 结果平均间隔仍为 66.6667ms；短窗 30 个和长窗 600 个处理 gauge 全部超过 33.3333ms。当前没有板上 engine/pending/lease 的逐事件时间戳，不能把 `66.6667−35.4632≈31.2035ms` 全部认作已测 bank-wait。

**源码事实：**

1. [bank L43](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_bank_tile8.v:43) 的 `source_ready` 同时要求 `!processing && !pending`，并检查结果写 bank 不与显示 front 冲突；[L69](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_bank_tile8.v:69) 完成后置 pending，[L76](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_bank_tile8.v:76) 在显示请求握手时才取走 pending 并翻转结果 bank。
2. [system L186](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_system_c.v:186) 按扫描请求边界发显示请求；[L220](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_system_c.v:220) 要求 reader、像素 CRC/计数、reader_idle、FIFO drain 和 lease 身份全部满足后才释放显示 bank。
3. [input DMA L46](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi1080_input_dma.v:46) 的 capture grant 要求 `!active && !source_valid`。完成源帧若尚未被处理器接收，就不能再发下一次采集 grant；[L101](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi1080_input_dma.v:101) 接收源帧才清 source_valid。两源 bank 并不等于完整的捕获描述符队列。
4. [capture L100](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi1080_capture_cdc.v:100) 的采集还受 SOF/首 DE 窗口和 pending grant 限制，不能在输入画面中途补收半帧。

**推断：** 35.46ms 错过一个 33.33ms 显示周期，加上 pending 与下一次整帧采集准入，会让新结果交接落到后续显示边界，形成 15FPS 的稳定档位。这个解释与 RTL 和实测一致，但还不是逐事件测量证明。不要把公式 `30/ceil(process_ms/33.333)` 当作本系统在所有输入/输出相位下的完整调度模型。

跨过 33.333ms 也只是必要预算之一。60Hz 输入、30Hz 输出、grant CDC 和两源/两结果 bank 的相位仍可能造成重复或 no-free。不能单独删除 `!pending`、提前释放正在扫描的 front，或靠覆盖排队源帧“提帧”。

## 3. 帧内优先看串行 miss 和 DDR 服务，而不是复制坐标核

本次 `cache_misses/processed≈37483.12`，与固定鱼眼 tile8/INDEX8 地址模型的 **37,483 fills/完整帧**一致；窗口边缘可能有跨帧在途事务，不能把这个非整数当作逐帧精确值。每 fill 为 256B，源块读 payload 约 **9.596MB/帧**。

当前 [engine L39](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v:39) 是单路 INDEX8；[cache L170](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v:170) 快命中可流水，但 miss 需要 fast 路排空；[L343](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v:343) 后的 SELECT/CHECK/AR/FILL/WAIT_COMMIT/LOAD/PICK 依次处理四邻域。写入是真实 8 拍 RAM commit，独立 scatter 已取消，不应再次规划“消除 8 拍 scatter”的重复收益。

[读仲裁器 L17](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_read_arbiter_fill8r2.v:17) 只有一份 owner/beat 状态；[L54](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_read_arbiter_fill8r2.v:54) 到 [L65](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_read_arbiter_fill8r2.v:65) 在末 R 后回 IDLE，再选择下一请求。当前只能有一个总线 outstanding。显示水位优先入口见 [system L124](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/hdmi_camera_fisheye_system_c.v:124)。

以下来自已完成的完整 1080p 系统仿真，**不是板上阶段计数**：

| 场景 / corrected 帧 | 处理时间，125MHz | coordinate blocked | cache AR wait | cache R wait | writer blocked |
| --- | ---: | ---: | ---: | ---: | ---: |
| 常规 INDEX8，第 1 帧 | 25.983784ms | 1,157,567 cyc | 57,081 | 67,223 | 0 |
| 连续 60 输入、40 拍首 R 模型，第 2 帧 | 39.591704ms | 2,858,557 cyc | 258,207 | 1,567,087 | 0 |

[常规回执](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/system-native-a/simulation.json)、[持续争用回执](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/system-sustained-native-a/simulation.json)。持续测试为 16 次完整输入光栅、4 个实际处理/唯一扫描 ID，读写争用及后续采集写重叠非零，12 个 no-free 是模型中的正常整帧准入结果，另无 overflow/CRC mismatch/underflow，最终 drain 完整。常规 corrected 帧没有未来采集写重叠，不能独用其 25.98ms 预测板上表现。

在 40 拍模型中，第 2 帧 R wait 约为 12.537ms，说明延迟敏感性很强；不能倒推出板上真实首 R 一定为 40 拍。coordinate blocked 与 AR/R/writer 等计数存在包含/重叠关系，不应全部相加。

**writer 不是当前已知的首要吞吐瓶颈。** corrected 常规及持续模型均 writer_blocked=0；尾排空约 16,805 周期，即 0.13444ms。现有双 stripe 已重叠收集/排空，但 [writer L52](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/rtl/experimental/ddr_adaptive_result_writer_dualstripe.v:52) 仍仅在 PACK 读 RAM，单 512B burst 在 AW/WRITE 时不继续打包。双 burst 可研究，但不能把完整模型约 2～5ms 的缺口预先归给 writer。

## 4. 下一轮的量化门槛与路线优先级

以下均为周期/地址模型，不是新板测承诺：

- 30FPS 的单次持续间隔预算为 **4,166,666.67 core 周期**。短窗末 gauge 4,433,172 周期，至少还需减少 **266,505.33 周期 / 2.132043ms / 6.01%**；长窗已观察最大 gauge 的缺口为 2.190859ms。未来工程目标应保留余量，例如持续处理 ≤30ms，而不是仅在某个样本擦过 33.333ms。
- 以末样本与 37,483 fills 估算，最低缺口相当于平均每 fill 少 **7.11 周期**；要达 30ms 则约需每 fill 少 18.23 周期。这个均摊只是筛选门槛，不证明某个优化可独立回收这些周期。
- 单 lane、每拍一个输出像素的理想下界为 **16.5888ms / 60.28FPS**。30FPS 只需平均 0.497664 像素/周期；当前不是先加第二坐标 lane 的证据。
- 30FPS、源写/结果写/扫描读均按 30FPS 准入时，INDEX8 的有效 payload 合计约 **661.12MB/s**，其中鱼眼源块读 287.87MB/s。这不是 DDR 保证吞吐；256bit×125MHz 的 4GB/s 只是 UI 名义字节时钟，必须支付命令、首 R、刷新和读写切换成本。若真收满 60FPS 源写，还需额外 124.416MB/s，且有限队列不能长期吸收“收 60、处理 30”的差。

| 路线 | 当前证据与潜在收益 | 建议 |
| --- | --- | --- |
| 单 outstanding 下的浅 lookahead / 需求优先预取 | miss 很少但每次使整路停顿；16/32 条完整坐标元数据可提前发现下一缺块。需证实 AR 提前与 RAM 写/读端口独占能减少等待 | **帧内第一研究项**，先做周期 A/B；单纯加 FIFO 深度不会隐藏当前全局 miss FSM |
| 连续 DDR 交接减少控制空泡 | 当前末 R→IDLE→ADDRESS 有空泡。即使每 fill 省 1～2 拍，约仅 0.30～0.60ms，尚不足覆盖当前至少 2.13ms 缺口 | 可与可证明的需求预取组合；不值得单凭这一项承诺 30FPS |
| INDEX9 + 正确注册 tag lookup | fills 37,483→31,110，少 17.00%；已完成 9tp 组合模型比 INDEX8 常规快 0.694ms，40 拍持续第 2 帧快 3.12048ms | 有潜力，但**该组合未通过物理**；需要定位并修复真实失败路径后重新闭环，不能直接复用本次通过的 INDEX8 bit |
| 改 cache index 映射 | 263 种完整 trace 已筛；INDEX8 最好仅少 206 fills，INDEX9 最好 28,242，未到既定 ≤24,000 门槛 | 当前不优先。纯模型结果不是可直接上板的 RTL；完整 block tag 与 DDR 地址必须保持 |
| 双 burst + `send_data` 寄存 | 可让 stripe PACK 与 DDR 发包重叠、改善宽输出路径；现有 corrected 模型没有 writer blocked | 仅在新增板上/仿真诊断证明 writer/写争用占比后提优先级 |
| 三源槽 + 完成描述符队列 | 可缓解捕获 grant、等待 source 与显示边界的相位损失 | **调度阶段首选参考**；先把持续处理压进预算。它不能消除 35.46ms 的持续算力超时 |
| 第三个结果 bank | 可分离显示中、待显示、可写状态，减少 pending 对下一帧的阻塞 | 与三源槽是不同问题，按时间戳决定；单做它仍受约 28.2FPS 的处理倒数上限约束，不能承诺 30 |

INDEX9 的失败不能轻描淡写：原 direct-fill slow setup −0.480ns/68 项失败；tagpipe 为 −0.033ns/5 项；seed4 为 −0.603ns/62 项。它们都不是本次已验镜像。[9tp 失败摘要](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/hdmi-camera-fisheye-tile8df9tp-20261103-a/raw-core-timing-a.json)。注册 tag 的 stale refresh、末 commit、younger query、RESULT stall/epoch 证明可复用为设计依据；通过的单元/全帧仿真不替代新的 STA。

## 5. 队友 stable30：能借什么，不能直接替换什么

本次直接从本地 Git 对象读取了冻结提交 `e89a2d42c21e6a216df00e4f0fdeb7c94439ba89`，对应 stable30 候选 `8c73465e`，不是只引用目录名字或当前分支。对象 SHA256 记录在随附 JSON。

| 冻结源码 / 证据 | 可借鉴内容 | 迁移边界 |
| --- | --- | --- |
| [cache L33](https://github.com/zhang-yl24/fpga-distortion-correction/blob/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89/delivery/20261103-hdmi1080-stable30/rtl/ddr_compact_neighbour_cache_scatter4.v#L33) | 入队前预计算四邻点线性地址和 bounds，完整元数据过寄存边界 | 该快照是两槽 FIFO，不能说成已验 D256；没有自动证明 DDR 延迟被隐藏。保留我们已经优于其 16 拍 scatter 的 direct-fill |
| [read return L14](https://github.com/zhang-yl24/fpga-distortion-correction/blob/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89/delivery/20261103-hdmi1080-stable30/rtl/ddr_read_return_register.v#L14) | data/valid/last/RID 整束寄存，原始 AR/R 侧 owner 检查 | 是时序隔离办法，本身增加一拍；不能称作提带宽。AR/首 R 同拍、尾 R/新 AR、无主返回和 sticky fault 必须保持 |
| [ping-pong writer L61](https://github.com/zhang-yl24/fpga-distortion-correction/blob/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89/delivery/20261103-hdmi1080-stable30/rtl/ddr_adaptive_result_writer.v#L61) | 两个 512B bank、寄存 `send_data`、局部 payload 写命令 | 它是 raster 快路；队友 tile 分支仍是旧单 stripe fallback。只能借 burst 排空层，不能整份替换我们的双 stripe |
| [三源调度 L9](https://github.com/zhang-yl24/fpga-distortion-correction/blob/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89/delivery/20261103-hdmi1080-stable30/evidence/scheduler/README.md#L9) | 逻辑源 0/1/2→DDR 物理槽 0/1/4；结果保持 2/3；两个完成源描述符，完整源 bank 生命周期 | 额外保留 4MiB DDR 区域，bank 元数据 2bit、mask 3bit，输入 CDC/DMA/link/bank 必须一起迁移，不是只改一个 bank 参数 |

队友调度的实 RTL bank+引擎时长 stub、五相位测试显示：在处理低于输入周期时，两源可出现 180/240 个新显示，三源为 240/240；但处理超过周期时，三源仍只有 120/240。这正好说明**相位损失和处理预算超限必须分开解决**。它还提供 32×16 实际小系统、八帧、第三源复用及独立 CRC 证据，但不覆盖我们完整鱼眼 1080p60 输入的实板吞吐。

队友引擎 22.650624ms/16,200 fills 对应其 Brown/Penn 参数，不是当前四项 OpenCV fisheye D；其冻结 board summary 明确 `hardware_verified=false`、`physical_timing_accepted=false`，不能引用名称 stable30 就称其已实板 30FPS。保留本工程镜头标定、148.5MHz 输入采样、初始化、RGB565/双线性和 current 125MHz/30Hz 时钟契约。完整 D256、双 lane、60Hz、三源/三结果槽组合属于后续独立架构项目，不并入本次冻结交付。

## 6. 可执行的分阶段计划及停止条件

| 阶段 | 只改一个主要变量的工作 | 必须交付 / 进入下一阶段的条件 |
| --- | --- | --- |
| A：收口当前版本 | 30/600 秒独立复核已完成，继续收口比较与资源/位流/SRAM/归档链；本次 RTL 不再调整 | 如实发布 15FPS 与处理 gauge 的改善；不把 HDMI 30Hz 或模型倒数称为 30 个新画面 |
| B：先获得可解释的时序 | 在新隔离 bench 中记录 capture grant/首末像素/source offer/accept、engine start/done、pending set/clear、display grant/done；AR wait/AR→首 R/beat gap/miss drain/writer stall 分开统计 | 使用当前相同 workload，明确造成 66.67ms 结果间隔的事件链；在 60Hz 输入/30Hz 输出下做相位扫描。若板上需加诊断，另立版本/BuildID/协议，不能改冻 PGHFPS02 包解释 |
| C：帧内 A/B | 优先单 outstanding 的浅 lookahead/需求预取；若证实主要是 tag/容量，则单独做修复时序后的 INDEX9/tagpipe。双 burst 只在 writer stall 有证据时推进 | 先小单元与完整 1080p oracle/CRC，再持续采集+扫描争用。模型周期须有明确改善，并以持续 ≤30ms 为工程目标；仅少几百个 fill 或省控制空泡不自动占用一轮上板 |
| D：调度 A/B | 当帧内持续处理已能进预算，仿队友先做三源描述符、保持两结果 bank，和原两源做同相位对照；第三结果 bank 单独评估 | 准入/等待/延迟及 whole-frame discard 明确；任一 frame ID、bank、epoch、CRC、reserve/lease 失配即停止。吞吐改善不能靠覆盖 READY、pending、front 或取消 drain 条件 |
| E：新候选闭环 | 仅推进一条完整组合；保持单 lane、125MHz、30Hz 和相同鱼眼像素 | 新 source manifest、RAM 映射/资源、全部 STA/CDC/reset/引脚、精确 bit/program 绑定；实板短测+长测 processed 和 unique 同时报告。只有实际完整新 ID 的持续速率达标，才宣称 30FPS |

所有新增缓存/预取必须覆盖：同拍 AR/首 R、R 间隙、RID/RLAST 错、无主返回、末 commit/tag 发布、旧 epoch/不同 tag stale hit、背压 metadata 保持、已发事务排空和协调 reset。所有新增 writer/调度必须覆盖：stripe/burst 所有权、最后 RAM 返回/最后 W、整帧 raster CRC、capture 与结果地址不重叠、显示 reader/像素/FIFO drain 联合释放。不要为了提帧删除本轮才完整闭合的物理与身份门禁。

建议下轮第一决策点放在阶段 B 的时间戳证据：若多数余量来自 miss 服务，先做 C；若处理已短于预算而仍长期 15/22.5FPS，先做 D。现有短测还不能决定三源槽一定必要，也不能证明仅把 35.46ms 压到 33.30ms 就足够。

## 7. 可复核附件与范围

[机器可读证据小结](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/output/tile8_next15h_20261103/tile8df8_v3_next_fps_evidence_20261104.json) 保存实际短窗与已通过 e 的长窗、周期模型、完整仿真 stage counters、失败候选 STA、已读取的队友 Git blob 身份及本地输入 SHA。它没有伪造新的 RTL/EDA/硬件验收；长窗仅引用 root 已完成的采集与 e 复核，本文未另行采集或启动比较，也不预写未来比较回执。

进一步上下文见 [stable30 技术交接](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/handoff/HDMI_CAMERA_FISHEYE_STABLE30_REFERENCE_20261103.md) 和 [S3 后续性能分析](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/handoff/HDMI_CAMERA_FISHEYE_PERFORMANCE_NEXT_AFTER_S3_20261103.md)。本文更新的是实际 INDEX8 direct-fill 板测后的判断，不继承旧计划中的未实现性能目标。
