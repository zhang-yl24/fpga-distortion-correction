# 1080P 帧率预算与下一步优化

2026-10-28，只读源码分析及已保存的回归结果。本文没有修改冻结 RTL、bench、runner 或约束，也没有启动仿真/EDA；正在运行的 native 回归以其最终回执为准。

## 结论

当前已完成的旧版本八帧 RTL 回归为 **1080P 稳态30fps**，最坏每帧处理 3,816,061 个125MHz周期，即30.528488ms。将该周期数直接换算，处理器容量约32.76帧/秒；这不是已经测得的32.76fps实时视频输出，更不是实板结果。

**60fps需要流水组织改进，不能把当前125MHz直接改到更高频率来承诺。** 125MHz下60fps每帧只有2,083,333周期，而1920×1080本身已有2,073,600像素，单像素/周期仅余9,733周期（约0.47%）容纳所有miss、写回、仲裁和排空。当前结果写入器即使没有cache miss和DDR等待，也已超过此预算。

## 可核对的预算

| 项目 | 周期或带宽 | 证据性质 |
| --- | ---: | --- |
| 1920×1080像素数 | 2,073,600/帧 | 精确几何计算 |
| 125MHz、30fps预算 | 4,166,666.7周期/帧 | 理论预算 |
| 125MHz、60fps预算 | 2,083,333.3周期/帧 | 理论预算 |
| 旧八帧最坏处理 | 3,816,061周期，30.528488ms | 已完成RTL回归，不含实际PHY |
| 当前writer理想下界 | 至少2,203,200周期，17.6256ms | 由当前状态机导出；不含等待/流水排空 |
| 仅writer下界折算上限 | 不高于56.74fps@125MHz | 理论上限，不是已实现性能 |
| 不改周期数而达到60fps所需核心频率 | 228.96366MHz | 反事实换算，无时序可行性证明 |
| 60fps三项基本DDR流量 | 746.496MB/s | capture写+result写+display读，RGB565有效负载 |
| 上项再加每源像素只读一次的示意 | 995.328MB/s | 理想一次源读的预算例，不是实测/保证 |

真正DDR源读取量应使用每帧fill数F：每次ARLEN7返回8×256bit=256字节，故源读有效字节为 **256F**。重读、块冲突、边界映射和显示重复帧均可能改变流量。不能从125MHz×256bit=4GB/s这个用户口名义峰值，推断物理DDR可用带宽或读写同时峰值。

## 源码中的确定瓶颈

1. **结果写回有结构性空泡。** `ddr_adaptive_result_writer.v`只在COLLECT接收像素；非tiled模式收齐256个像素才进入ADDRESS/WRITE，16个256bit beat完成后才重新COLLECT。即使首beat能在AW握手同周期给出，256像素至少占256+16周期；8100个burst共2,203,200周期。当前engine的`use_tiles=0`，不是另一种tile吞吐口径。双缓冲可重叠收集与写回，消除此空泡，但单独修它只能节省最多约129,600周期/帧（1.0368ms），不足以把30提升到60。

2. **cache miss串行阻塞快路径。** `ddr_neighbour_cache_scatter4_rowpipe.v`的fast hit可每周期一个query，但slow miss会等待fast结果排空，再逐邻域SELECT/CHECK/AR/FILL/SCATTER/LOAD/PICK。每fill只有8个返回beat，却要32周期将128个RGB565像素按4像素/周期写入缓存；SCATTER期间占用even/odd RAM的全部写端口，不能正常读取下一query。它是调度/片上写口组织成本，不等同DDR总线已饱和。

3. **rowpipe主要切时序路径，未扩吞吐宽度。** 新增`pre_row`一级切开y×WIDTH与x/offset加法，保留1query/周期快路径与原slow状态机。当前运行的partial events已完整release前两帧：commit→release分别3,802,919和3,815,511周期，与旧八帧摘要相同ID完全一致。此观察不是新八帧完成，也不能由此推断最终Fmax或全部帧不变。

4. **视频接口目前硬性为30fps。** 输出默认2200×1125、74.25MHz，每周期一个RGB888像素；输入observer的1ms PCLK窗口只接受73500–75000边沿。1080p60标准相同总时序需148.5MHz，新模式必须同步修改/验证PLL、输入准入、FDC、外部AC和FIFO吞吐，不能仅让核心跑得快然后声称60fps输出。

## 优化优先次序

| 顺序 | 独立实验 | 应量化的收益与风险 |
| --- | --- | --- |
| P0 | 完成当前八帧与最终STA，先交付实板30fps闭环 | 保住一周内交付，不把未通过recovery和外部IO带入现场 |
| P1 | 读取本轮最终frames.csv/summary，不改正在跑的bench | 每帧F、32F scatter周期、hardware_process_cycles、各类pressure、真实scan间隔；pressure计数可能重叠，不能直接相加 |
| P2 | writer增加第二个256像素buffer | 额外逻辑数据512字节，收集与16beat写回并行；先验证AW/W不可撤回、tag/CRC、最后burst排空、fault/common reset；最佳仅约1ms/帧 |
| P3 | 对真实热点优先cache分bank宽scatter或预取 | 8像素/周期scatter需16周期，16像素/周期需8周期；相对32周期最多分别节省16F或24F，但实际净收益取决与其他阶段重叠。需多bank满足写端口并保持四邻域读取、冲突/边界和RAM推断正确 |
| P4 | 若确需60fps，设计2pixel/query lanes，或先取得更高Fmax证明后采用适度提频 | 2lane涉及mapper/双线性/cache读口/gamma统计/writer和标签的整链变化；125MHz单lane几乎无空泡预算，不是一处参数修复 |

预取方案必须保持实际DDR口ID=0、无RREADY、整burst不可反压的契约。当前读仲裁一次只允许一个burst占用总线；增加多个outstanding或在fill期间发下一AR，需要独立的整burst预留、目的行元数据队列及错误隔离，不能简单扩大FIFO。缓存容量目前32KiB，不先凭猜测加大；若统计显示冲突/重读主导，再比较分bank、associativity或访问顺序。切到tile顺序还会启用writer的stripe重排成本，必须对完整链而非仅cache命中率评估。

## 最小后续实验

当前native结束后从frames.csv建立同帧ID的表：`hardware_process_cycles`、`fills`、`scatter_cycles`、`commit_to_release_cycles`、source/result字节量与scan间隔。基线和候选使用同一CPU golden、同一Brown配置与反压时序，分别列warmup/steady/tail。若miss成本主导，先对独立cache构造同一映射下的只读事件回放/单位实验，再按CRC和边界/反压/切帧规则决定是否合入；若writer空泡明显，先做双buffer小整链。每次只改一个机制，再完整native、资源推断及最终STA。当前没有足够数据认定DDR物理带宽已成为主墙。

## 定位

- 已完成旧八帧：`distortion/output/project/board1080-offline-summary-20261028.json`。
- 当前partial events：`distortion/build/board1080-rowpipe-reproduction/local-native-20261028-a/events.csv`，目前仅引用前两帧已存在的source_commit/source_release；文件仍在增长，不绑定成最终回归结果。
- engine：`distortion/rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v`，use_tiles第23行、INDEX_BITS7第42行、raster发射第82行。
- writer：`distortion/rtl/experimental/ddr_adaptive_result_writer.v`，COLLECT-only ready第34行、收256/转ADDRESS第80行、WRITE第90行以后。
- cache：`distortion/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v`，fast accept第157行、SCATTER第311行、最后8beat进入SCATTER第331行。
- 输入模式：`distortion/rtl/experimental/hdmi1080_input_status.v`第8–9行。
- 输出模式：`distortion/rtl/experimental/ddr_video_output_1080_board.v`第11–13行。
