# 720p 矫正完成后的帧率测量与优化计划

2026-11-02 实板更新：当前统计矫正版已上板，30秒与120秒UART采集分别29/119个有效窗口，接受/处理/唯一输出均15.0fps。传感器全部有效帧和PCLK仍未实测；下一步测量它们后再决定输入模式或调度优化。详情见[当前摄像头状态](CURRENT.md)和[统计版实板证据](../distortion/results/camera720-stats-live-20261102-a/README.md)。下面为先前阶段的分析记录，“无FPS/未上板”等状态不覆盖本条。

2026-11-02补充：实际镜头720p矫正基线已下载并封存，当前正在独立统计候选中解决输入同步时序，仍无720p实板FPS。只做静态吞吐计算：1280×720 RGB565一帧1843200字节；8位DVP在48MHz且完全没有消隐时上限也只有26.0417fps，30fps至少需要55.296MHz的有效字节时钟，真实还要考虑消隐。现有寄存器42MHz/约15fps只是条件模型；提高处理核心频率不能突破输入字节吞吐上限，也不能证明当前瓶颈一定在输入。先取得接受/处理/独特显示三组真实计数，再定位丢帧与等待。计算与来源哈希见`distortion/work/camera720-stats-delay/fps-transport-envelope-a.json`；本次没有改相机时钟、曝光或帧率配置。

## 2026-11-01 21:58新增：当前镜头720p完整系统仿真

当前镜头转移参数已通过独立完整系统仿真，见`distortion/work/camera720-corrected-system/actual-lens-rtl-a/`，两帧1843200个扫描像素逐一匹配，零欠载和CRC错误。`events.csv`的source commit→处理release分别为1759060和1761569个125MHz周期，即**14.072480ms、14.092552ms**；独立计算和输入哈希见`distortion/work/camera720-calibrated/actual-lens-modeled-performance-a.json`。这是使用合成48MHz相机时钟与行为DDR的模型耗时，不含commit前采集时间，不能写成实板约71fps或现有720p输入帧率。

实际calibrated布局使用66/240 APM、18159/133200 FF、14651/66600 LUT、16.5/155 DRM，主要资源尚有余量；不能仅由占用率判断提高帧率的瓶颈。新时序修复后的setup slow/fast +0.430/+2.982ns、hold +0.061/+0.020ns，最终复位/CDC/IO仍在核验。用户离开期间可继续离线开发和获授权下载，当前无UART遥测；实板FPS必须后续测量，先保留可回退的720p矫正版。

下文为较早的性能分析与计划；其中“当前板上transport”为历史状态，板上配置以[当前交接](CURRENT.md)为准。原优化顺序与计数口径仍适用。

2026-11-01。本文只读现有源码、已保存仿真及原生资源/时序报告；没有修改生产 RTL、原证据或板上配置，没有运行 PDS、硬件或新大型仿真。

任务顺序固定为：**当前镜头的真实 1280×720 几何/矫正验收 → 测量这套矫正配置的帧率和瓶颈 → 按测量优化**。当前板上 `camera720_transport_top` 单位映射已由用户确认方向正确、持续更新，LED5/6 闪烁、LED7 灭；它不是 720p 镜头矫正版，当前 720p 实板帧率未知。HDMI IN 支线继续暂停，远端 CI 按用户要求暂缓。当前优先级见 [CURRENT](CURRENT.md)、[首次上板记录](CAMERA_720P_FIRST_BOARD_20261101.md)。

## 1. 当前可以说什么

| 证据类别 | 已知结果 | 不能推出的结论 |
| --- | --- | --- |
| VGA 矫正实板人工计时 | LED6 十完整周期约 13–14 秒，即 320 个处理完成帧，粗估 22.9–24.6 fps | 不能继承为 720p 帧率；不是显示独特新帧率或精确时钟测量 |
| 720p 实板观察 | 单位映射画面正立、更新、无 LED 故障 | 没有 720p fps、矫正性能或长稳测量 |
| 720p 留存传感器寄存器模型 | 在 XVCLK=24 MHz 假设下 PCLK=42 MHz、约 14.999 fps；序列文件 `MeasuredFPS=null` | 不是当前板卡时钟/帧率实测，不能写成输入已确认 15 fps |
| 720p system RTL 仿真 | 完整 DVP→DDR→处理→实际扫描两帧、1843200 像素及 CRC 一致，零欠载/CRC 错；源提交到处理释放为 1430123、1432717 个 125 MHz 周期，约 11.441、11.462 ms | 使用单位映射、行为 DDR、48 MHz 合成 DVP；不是实板约 87 fps |
| 720p output RTL 仿真 | 非线性合成映射三帧，处理开始到完成为 1500382、1501878、1501803 周期，约 12.003–12.015 ms；2764800 坐标/扫描像素匹配 | 不是当前镜头 720p 矫正参数，不能据此承诺 83 fps 或当前板卡 60 fps |

system 数据来自 `distortion/results/camera720-offline-20261101-a/simulations/system/events.csv:2-5` 和 `summary.json:1`；125 MHz/48 MHz/74.25 MHz 合成时钟见 `distortion/tests/tb_camera720_system.sv:9-19`，合成行/帧节拍见 `:201-225`。output 数据来自同证据包 `simulations/output/frames.csv:2-4`，必须使用 `process_done_cycle-start_cycle`；其中 `release_cycle` 是后续显示银行释放，不能当作处理结束。两个仿真的参数分别见各自 `config.vh`，因此这两组周期不是同参数 A/B 性能比较。

当前输出为 1920×1080、2200×1125 总时序、74.25 MHz，即 **30 Hz 刷新**；有效相机/处理区域为 1280×720，居中不放大。源码见 `distortion/board/camera720_transport_top.v:19-20,156-173`；最终 STA 时钟见 `distortion/work/camera720-output/bit-a/report_timing/camera720_transport_top.rtr:45-49`。独特新画面率不可能高于输出刷新率，而实际值还取决输入、处理和银行调度。

720p 原图导出是另一套采图候选。RGB565 一帧 1843200 字节，921600 baud、8N1 的纯发送理论下界约 20 秒，另有封包和等帧时间。这个时间只表示 UART 导图吞吐，**不能换算为视频处理 fps**；后续性能仪表只发送小统计包，不连续导原图。

## 2. 确定存在的结构成本与待测主瓶颈

### 输入与银行调度可能先限制新帧率

- 传感器已有完整帧监测 `good_frames/bad_frames/pclk_edges_per_window`，当前 top 没有导出；见 `ov5640_current720_frontend.v:18-20,36-49`。先测这些量，不能仅从 LED5 推定传感器 fps。
- **现名为 `captured_frames` 的计数实际在 `source_valid && source_ready` 时增加**，即完整采集帧交给处理端的时刻；见 `camera_vga_input_dma.v:105-106`。完整 DMA/CRC 校验结束、置 `source_valid` 是另一事件 `:155-160`。若处理/显示堵住，LED5 也会变慢；它不是独立的所有有效输入帧计数。
- `lens1080_bank_core.v:45-46` 在 `processing`、`pending` 或银行占用时不接受下一帧。处理完成置 `pending`（`:73-78`），到显示申请才切换前台、清 `pending`（`:81-88`）。显示申请在每次扫描边界发起，见 `ddr_video_output_1080_board.v:142-145`。因此处理空闲不一定是传感器慢，也可能是在等显示消费；盲目提核心频率无法消除该等待。
- 输入采用双源银行，结果采用双银行，`BANK_STRIDE=1048576` 个 4 字节 UI 地址单位，即每银行 4 MiB；不是四个任意可互换队列。银行所有权/CRC/完整事务排空必须保留。

### 算术流水已经具备单坐标/周期入口，缓存慢路径会阻塞它

`bounded_brown_inverse_mapper.v:17-22,192-207` 为共享使能的 30 级流水，`bilinear_rgb.v:13,21-26` 为三段流水；这些是流水延迟，不能解释成每像素串行花 30 或 3 周期。在输出可接收时可连续接入；下游反压会暂停。engine 固定 raster、单坐标通道，`pipeline_gamma_frame_engine_1080_scatter4.v:23,40-52,82-92`。

实际选用 `ddr_neighbour_cache_scatter4_rowpipe.v`，engine `INDEX_BITS=7`（`:42`），即 128 条缓存行、每条 128 个 RGB565 像素，共 32 KiB 逻辑像素存储，另有 256 字节 fill 暂存。缓存组织见 cache `:95-115,213-214`。

- 全邻域命中的 fast 路径可每周期接受一个 query，见 cache `:157-159,246-248`。miss 必须先等 fast 结果排空，逐邻域进入 SELECT/CHECK/AR/FILL/SCATTER/LOAD/PICK；这时会阻塞后续查询。
- 每次 miss 发 ARLEN=7，即 8×256 bit=256 字节；见 `:171-179`。收到 8 个 beat 后仍需 **32 个 SCATTER 周期**，四个 16 bit 写口每周期放入四像素，见 `:201-229,311-314,326-332`。这是片上写口/调度成本，不等于 DDR 物理总线饱和。
- 每帧接受新 base 时清 tag 有效位（`:280-281`）；两次不同源帧不能直接复用旧像素缓存。真实矫正后的访问范围、局部性和映射黑区将改变 miss 数；当前单位映射的统计不能代表矫正参数。
- 已有 `hits` 是有效邻域采样 hit 次数（fast 一次可加 0–4，slow 命中加 1），`misses` 是邻域 miss/fill 启动次数，`queries` 是完成的输出 query；见 `:171,272-278,301-306`。**不能把 hits/queries 当 query 命中率，也不能默认 hits+misses=4×queries**，越界邻点不计入。

### 结果写回与 DDR 仲裁有可量化的空泡

`ddr_adaptive_result_writer.v:34,76-80,90-106` 仅在 COLLECT 接收像素；raster 模式收齐 256 像素，再写出 16 个 256 bit beat，然后恢复收集。即使 DDR 零等待，720p 的收集/写出阶段合计至少 `921600+57600=979200` 周期，即 7.8336 ms@125 MHz；这是结构下界，未含其他流水和等待。第二个 512 字节 burst buffer 可重叠收集/写回，但仅消除这部分空泡的理想增益上界为 57600 周期、0.4608 ms/帧，不能单凭此保证整体大幅提帧。当前 `use_tiles=0`，不能套用 tiled 的 stripe 开销。

读口有显示/采样两客户端，一次只有一个已接收 burst，ID=0、无 RREADY；见 `distortion/rtl/ddr_read_arbiter.v:2-5,17-30,39-52`。显示 FIFO 低于 64 个 256 bit word 时提高显示优先级，见 `camera_vga_video_system.v:132-140`。扩大 outstanding 或预取不是修改一个队列长度即可，必须保持整 burst 空间预留、不可反压返回、目的地与错误隔离。

输入 DMA 也有 CRC 和串行收集/写出成本（`camera_vga_input_dma.v:119-151`）；先看输入 FIFO 高水位及溢出再决定是否优化，不能直接关掉 CRC 或屏蔽 overflow 来得到“更快”。

## 3. 最小实板仪表：复用计数，新增等待分类

先完成一份 720p 镜头矫正候选，再做独立的仪表候选，保留原位流回退。统计口不能改变摄像头参数、映射、银行协议或 DDR 契约。当前 720p transport top 没有 UART 端口；新增只发小统计包的 UART 需要自己的引脚/构建/时序/CDC 检查，不能直接套用采图候选验收。

| 最小字段 | 精确采样口径 | 用于区分 |
| --- | --- | --- |
| build/profile ID、snapshot序号、参考时钟 ticks、窗口长 | 名义 27 MHz 参考域；排除 8 秒预热；跨域抓取时记录各自实际窗口边界 | 绑定本次矫正参数和测量时段，避免套用旧 VGA/单位映射数据 |
| sensor_good/bad、PCLK 窗口边沿、行/字节数 | 复用现有监测器完整帧判定和 held snapshot | 真实输入速率、坏帧与配置/曝光变化 |
| dma_complete、source_accepted、processed、presented_unique | 分别在完整 DDR/CRC done、source握手、engine done、完成完整像素扫描且ID更新时计数 | 分开输入、排队、计算完成、实际独特显示；不要用 HDMI VS 数替代 |
| drop/overflow/no_grant、repeat/blank、underflow/CRC mismatch | 复用输入/显示已有计数；额外导出 currently internal 的量 | 丢帧原因，输出重复和错误是否掩盖性能 |
| process cycles：count/sum/min/max；最近frame ID | 保留现有 `last_cycles`，增加 64 bit sum 与 min/max；commit→done 同 core 域 | 平均/最坏处理耗时，与总处理 fps 区分 |
| pending等待、无输入等待、源已到但不可启动、处理忙 | 以 core 每周期互斥分类；单独记录 pending→display grant 周期 | 银行/刷新等待与核心算力不足 |
| Δhits、Δmisses/fills、Δqueries、fast_queries、slow_queries、scatter_cycles | 现有累积计数取窗口差；新增 accept_fast/accept_slow 和 SCATTER 驻留计数 | 邻点命中率、query快路径比例、fill带宽与32周期开销 |
| 读写客户端 AR/AW/W 等待、返回空等、显示/采集 FIFO 高水位 | 按实际 valid&&!ready；read_active&&!rvalid；客户端分别计数 | DDR仲裁/返回延迟、入口溢出和显示危险余量 |

现成信号入口：`camera_vga_video_system.v:26-39,95-112,132-140,178-189,229-237`。其中 `presented_frames` 在读完、像素CRC/数量正确且 FIFO 排空后，只对更大的 frame ID 增加；相同 ID 单列 `scan_repeat_frames`（`:229-237`），这是应采用的独特显示口径。

计数器留在原时钟域。使用**完整向量 held snapshot + request/ack**转移和双缓冲统计包；不要给多位二进制计数直接各 bit 两级同步。沿用已经验证的 monitor 方法可减少重复设计，但新向量仍需要自身约束与 CDC 审查。累积32 bit计数做无符号模差，周期总和/时间基准用64 bit，避免125 MHz下约34秒的32 bit周期回绕；或每1秒锁存增量。串口主机只读，包带长度/版本/CRC/seq，丢包可发现；序列化不阻塞处理，禁止性能测量时导原图。

建议一次稳定测量至少30秒、取得至少300个完整矫正帧，再用同一光照/曝光设置做对比；这是后续计划，当前未执行。主机读包时间用于交叉核验，主要时基为板上锁存 ticks，并注明名义晶振误差。每帧耗时分布可用轻量分档直方图或有限逐帧记录，首版不必增加复杂 percentile 硬件。

计算口径：`input_fps=Δsensor_good/Δt`，`processed_fps=Δprocessed/Δt`，`unique_display_fps=Δpresented_unique/Δt`；处理时长为 `cycles/core_hz`。cache 邻点命中率 `Δhits/(Δhits+Δmisses)`，query 快路径比例 `Δfast_queries/(Δfast_queries+Δslow_queries)`，成功完整帧源读量 `256×fills` 字节。窗口末未排空时同时保留 accepted/completed fills，避免把正在返回的 burst 当已完成流量。任何压力计数可能重叠，**不能相加成总帧耗时**。

## 4. 720p 预算与实际资源余量

| 目标处理节拍 | 125 MHz 每帧预算 | 每输出像素预算 | capture写+result写+display读的等帧率有效流量 |
| --- | ---: | ---: | ---: |
| 15 fps | 8333333周期 | 9.04周期 | 82.944 MB/s |
| 24 fps | 5208333周期 | 5.65周期 | 132.710 MB/s |
| 30 fps | 4166667周期 | 4.52周期 | 165.888 MB/s |
| 60 fps | 2083333周期 | 2.26周期 | 331.776 MB/s |

这是精确几何/时钟预算，不是达成值。通用读写流量应按实际独立速率计算：`1.8432 MB×(capture写帧率+result写帧率+扫描读取帧率)+256×源fill次数/秒`。显示重复帧仍可能再次读取完整结果，不可一律把三路流量都乘处理 fps。若源像素恰好只读一次，30fps四路示意为221.184 MB/s；真实源读取由 fills 决定。DDR UI 的125 MHz×256 bit=4 GB/s只是名义单方向数据口乘积，不是物理可用吞吐或并发读写保证。

实际原生路由报告按 CLMA/CLMS 合计如下；表中余量为容量减使用量，不能作为新增并行通道一定可布通的证明。

| 资源 | 已验收 VGA 矫正构建 | 当前 720p 单位映射构建 | 720p 名义剩余 |
| --- | ---: | ---: | ---: |
| LUT（CLMA+CLMS） | 13706 / 66600 | 14176 / 66600，21.3% | 52424 |
| FF（CLMA+CLMS） | 17353 / 133200 | 18000 / 133200，13.5% | 115200 |
| APM | 66 / 240 | 60 / 240，25.0% | 180 |
| DRM（工具报告口径） | 16.5 / 155 | 16.5 / 155，10.6% | 138.5 |
| IO | 128 / 300 | 128 / 300，42.7% | 172，但须按实际bank/电压/封装选择 |
| GPLL | 3 / 6 | 3 / 6 | 3，不能推断任意新频率可用 |
| BKCL | 6 / 6 | 6 / 6 | 0，此专用项已满；不可笼统说所有资源充足 |

720p 来源：`distortion/work/camera720-output/build-b/place_route/run_route.log:174-209`；VGA 来源：`distortion/work/calibrated-camera-vga/build-a/place_route/run_route.log:133-168`。后续路由修正/精确 reset 例外没有重综合功能逻辑；VGA `reset-effect-a.json`确认17353 FF及功能/放置不变，720p `reset-effect-a.json`确认功能图/FF放置不变。以上是实际既有构建的资源，不是尚不存在的720p矫正+仪表构建预测。单位映射零系数可被综合优化，不可把60个APM承诺给新矫正配置，也不可把两构建差值全部归因于分辨率。

最终720p bit fresh STA 的125 MHz core同域 slow setup余量仅 **0.148 ns**（`.rtr:48,67`）；pixel域为1.985 ns（`:46,62`）。当前通过并不支持随意提频，报告估计频率也不是新频率验收。小计数器、双buffer或RAM打包有资源尝试空间，但须看新增布局、时钟扇出、DRM端口和最终双角时序。

## 5. 优化顺序和明确触发条件

1. **先固定正确的720p矫正与基线测量。** 原图/模式几何、独立实际姿态验证、完整定点映射和实屏直线改善先完成。再固定映射参数、图像/光照和仪表版本，记录输入/处理/独特显示速率及错误计数。不能用改曝光或缩小有效画面暗中换取性能。
2. **若 input低、process耗时短、无积压/丢帧，先验证摄像头节拍。** 先核 PCLK/完整帧计数和曝光/HTS/VTS实际设置，再在独立候选研究提高输入模式。当前约15fps寄存器模型是强提示，仍需实测；不要把问题先归咎于DSP不足。新PCLK可能超过48MHz现有约束预算，输入时序/模式准入/DDR/FIFO必须重新验证。
3. **若 pending/显示等待主导，先处理目标与扫描节拍。** 30Hz输出下不要为不可见的>30独特fps先改大流水。确需>30显示新帧时，独立研究720p60扫描、PLL/HDMI配置/读取节拍与新的银行调度；改变结果排队/丢旧帧策略必须显式说明延迟与丢帧代价。不得破坏当前前台bank租约。
4. **若计算中 SCATTER/fill 主导，优先优化缓存填充组织。** 首个小实验可保持32KiB容量/tag/块大小，把even/odd逻辑RAM从16bit改为32bit word，两个端口各写两像素，争取32→16 scatter周期；每帧理论最多节约`16×fills`周期，实际净收益必须量测。验证half选择、跨word四邻域、RAM推断、反压/错误隔离；不承诺PDS实际DRM数不变。若冲突替换/同块重载明显，再比较associativity、访问顺序或预取，先不要无依据扩大缓存。
5. **若writer反压明显，试第二个256像素buffer。** 增加512字节逻辑暂存，独立验证AW/W不可撤回、frame/tag/CRC及末burst排空；理想空泡收益仅0.4608ms/720p帧，按实际等待确定价值。读/写仲裁只在分别统计证明有需要时调节，保护显示欠载与输入溢出。
6. **最后才评估更宽流水或提频。** 单坐标/周期在720p60预算中仍有2.26周期/像素，不能照搬1080p60“几乎无空泡”的结论；是否需要双通道由真实矫正周期决定。双通道涉及mapper、四邻域读口、插值、CRC、writer和tag全链。提高核心频率需新的DDR/IP时钟方案与完整STA，不把修改一个频率常量作为提帧方案。

每次只比较一个机制：同一矫正参数/输入/时钟/反压条件，先小范围功能测试，核像素/CRC/帧ID/银行/故障排空，再必要的720p完整回归和新原生资源/时序，最后实板计数。若结果无收益，保留原回执和原因，不能仅用新的计数公式宣称改进。

## 6. 对1080p的边界

当前四银行每bank4MiB，1920×1080 RGB565=4147200字节，在几何容量上小于4194304字节，仅余47104字节；这只说明现布局可容纳该字节数，不证明输入模式/光学/吞吐。旧1080p合成参数八帧RTL曾取得最坏3816061周期（30.528488ms@125MHz），见 [既有1080p预算](BOARD1080_PERFORMANCE_BUDGET.md)，不是这颗镜头的实板1080p。

1080p60在125MHz下只有2083333周期，2073600个像素已占绝大部分；现writer理想下界2203200周期也超过预算。因此不能根据现有LUT/APM余量承诺1080p60。用户当前目标是先720p矫正，再提升该模式帧率；1080p另立输入、带宽、映射精度和完整物理验证任务。

## 核验索引

以下为本次实际读取原件的SHA256；不复制或改写原证据。源码行号以这些当前文件为准，后续修改须生成新的对比记录。

| 文件 | SHA256 |
| --- | --- |
| `distortion/board/camera720_transport_top.v` | `b71329fe4621f6a820fbc2b4e2513e51bfc06bed4bf87dd4adea42f78d8c0629` |
| `distortion/board/camera_vga_calibrated_top.v` | `eaa57f3f0500095aabbaba4f90b550552266877e622b8caa6e1ef2097b0086e8` |
| `distortion/rtl/experimental/camera_vga_video_system.v` | `5b45cabe9cf50f32aea2d6496cd56bec7c9e3cc755a3efa35afe8ba14b8f1d61` |
| `distortion/rtl/experimental/lens1080_bank_core.v` | `ed14a1266b39b048dcdd2687f3d4fdef13c502ce2858b7483c93d5397a22092c` |
| `distortion/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v` | `15e7927a6d8069e5f204c46c90956a5a5839239376da69719a659745307448bb` |
| `distortion/rtl/experimental/ddr_adaptive_result_writer.v` | `fab6d79260ce4b81a54bfd5d6befde535e7aea1230ce2e5fdd1398655ffc20a6` |
| `distortion/work/camera720-output/build-b/place_route/run_route.log` | `4a97203a11348836146275e59067b028c1a0d7f142bb9b642dca1b5bbffd4b2e` |
| `distortion/work/calibrated-camera-vga/build-a/place_route/run_route.log` | `8e009ecbf59f43254ede962f4838fc9d82fcef644182f27e9bbcde3b475e06a1` |
| `distortion/work/camera720-output/reset-effect-a.json` | `16bed69e7f3a16f59d48c5ed7356d8eb7c57c8b6be126da2ff91901809174df5` |
| `distortion/work/calibrated-camera-vga/reset-effect-a.json` | `5cfbed6da1f65de1740ad45598c0a9c2b71303a672077380b70f8559538a4697` |
| `distortion/work/camera720-output/bit-a/verification.json` | `6276dae061048d74950516617793732744052d4530a226f00e4d5328641d2430` |
| `distortion/results/camera720-offline-20261101-a/simulations/system/events.csv` | `ded2c5abd9f3ad81696a4cc2493b6f1465b278f7ab01922f727bc0d69b6203af` |
| `distortion/results/camera720-offline-20261101-a/simulations/system/summary.json` | `43a137e30e5fa7a9237753f5a169cd9e1571b426b085d508c46b2da1a4518b81` |
| `distortion/results/camera720-offline-20261101-a/simulations/output/frames.csv` | `91733c5c408dcb9768cb4636401bb81ec5a51b251179200d0b45b8b1507b7a96` |
| `distortion/results/camera720-offline-20261101-a/simulations/output/summary.json` | `86faf6edbdb59ed1b935b621b96daba319904e95c9e741b8f61fb30d13dcd367` |

本计划没有产生新的 fps、光学验收、资源利用率或上板结论。后续完成实际720p矫正与统计采样后，在新结果文件中填写测量值，不回填成既有结果。
