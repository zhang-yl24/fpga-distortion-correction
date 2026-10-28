# 1080P 帧率预算与下一步优化

2026-10-28，只读源码分析及已保存的回归结果。本文没有修改冻结 RTL、bench、runner 或约束，也没有启动仿真/EDA。新的 rowpipe native 八帧回归已结束，最终回执的 Passed/FunctionalPassed/Digital30fpsBudgetMet 均为 true；此文只读取其完成结果。

## 结论

当前新 rowpipe 八帧与旧版本八帧 RTL 回归均为 **1080P 稳态30fps**，新八帧逐帧 commit→release 周期数与旧摘要完全相同，最坏3,816,061个125MHz周期，即30.528488ms。将该周期数直接换算，处理器容量约32.76帧/秒；这不是已经测得的32.76fps实时视频输出，更不是实板结果。rowpipe的功能整合通过，但本轮没有体现吞吐提升。

**60fps需要流水组织改进，不能把当前125MHz直接改到更高频率来承诺。** 125MHz下60fps每帧只有2,083,333周期，而1920×1080本身已有2,073,600像素，单像素/周期仅余9,733周期（约0.47%）容纳所有miss、写回、仲裁和排空。当前结果写入器即使没有cache miss和DDR等待，也已超过此预算。

## 可核对的预算

| 项目 | 周期或带宽 | 证据性质 |
| --- | ---: | --- |
| 1920×1080像素数 | 2,073,600/帧 | 精确几何计算 |
| 125MHz、30fps预算 | 4,166,666.7周期/帧 | 理论预算 |
| 125MHz、60fps预算 | 2,083,333.3周期/帧 | 理论预算 |
| 新旧八帧最坏commit→release | 3,816,061周期，30.528488ms | 已完成RTL回归，不含实际PHY |
| 当前writer理想下界 | 至少2,203,200周期，17.6256ms | 由当前状态机导出；不含等待/流水排空 |
| 仅writer下界折算上限 | 不高于56.74fps@125MHz | 理论上限，不是已实现性能 |
| 不改周期数而达到60fps所需核心频率 | 228.96366MHz | 反事实换算，无时序可行性证明 |
| 60fps三项基本DDR流量 | 746.496MB/s | capture写+result写+display读，RGB565有效负载 |
| 上项再加每源像素只读一次的示意 | 995.328MB/s | 理想一次源读的预算例，不是实测/保证 |
| 新八帧实际每帧源cache fill | 25,944次，6,641,664字节 | 数字DDR用户口回归计数 |
| 新八帧每帧scatter状态驻留 | 830,208周期，6.641664ms | 精确等于32×25,944 |
| 本模型实际四类基本流量折算 | 572.498MB/s@30；1144.996MB/s@60 | 前者按已测fill数换算；后者假定60模式fill数不变，非已运行60 |

真正DDR源读取量应使用每帧fill数F：每次ARLEN7返回8×256bit=256字节，故源读有效字节为 **256F**。新八帧F均为25,944，源读量相当于完整RGB565源帧字节数的1.60148倍；这不是独立像素覆盖率，也不以此估计唯一源块数。加capture写、result写、display读，每帧共19,083,264有效字节。重读、块冲突、边界映射和显示重复帧均可能改变流量。不能从125MHz×256bit=4GB/s这个用户口名义峰值，推断物理DDR可用带宽或读写同时峰值。

## 新八帧最终结果与延迟口径

新的32×16同源small gate先通过后才运行本次native。最终八个输入均完成DMA提交、处理、发布和唯一像素扫描，共16,588,800像素，无丢帧、溢出、无空闲bank错误、输出下溢或CRC错，最终排空；CoverageFailures=[]，源/夹具前后SHA一致。native未执行small专属的故障阶段，因此其fault_isolation等字段为false并非native失败，故障恢复范围由先前同源small结果单独证明。没有实板PHY、相机或光学验收结论。

| 帧ID | fills | scatter周期 | hardware_process_cycles | commit→release周期 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 25,944 | 830,208 | 3,802,918 | 3,802,919 |
| 2 | 25,944 | 830,208 | 3,815,510 | 3,815,511 |
| 3 | 25,944 | 830,208 | 3,815,366 | 3,815,367 |
| 4 | 25,944 | 830,208 | 3,815,231 | 3,815,232 |
| 5 | 25,944 | 830,208 | 3,816,060 | 3,816,061 |
| 6 | 25,944 | 830,208 | 3,814,533 | 3,814,534 |
| 7 | 25,944 | 830,208 | 3,815,646 | 3,815,647 |
| 8 | 25,944 | 830,208 | 3,812,542 | 3,812,543 |

两种周期口径相差1周期是计数器/事件观测边界，逐列保留，不混作性能提升。实际扫描末像素间隔为33,333,333,333或33,333,333,334ps，steady唯一新扫描为30fps，没有累积滑移。每帧从首输入像素到末输出像素为 **98.662816548ms**，从末输入像素到末输出像素约 **66.666601059–66.666601060ms**；约30.53ms只是完整源帧提交后的处理区间，不能称端到端延迟。以上均来自数字bench的事件时间，不是摄像头到屏幕的硬件测量。

全八帧累计pressure为AW等待100,345周期、W等待400,446、AR等待114,710、cache输出等待1,188,502、core输出等待1,273,875、tone等待1,328,283；读/写客户端同请求分别2,258/994周期。它们的采样区间和重叠不同，不能相加成“总瓶颈耗时”。输出FIFO峰值512、全部128缓存行均被触达，也不单独证明缓存容量不足。

## 源码中的确定瓶颈

1. **结果写回有结构性空泡。** `ddr_adaptive_result_writer.v`只在COLLECT接收像素；非tiled模式收齐256个像素才进入ADDRESS/WRITE，16个256bit beat完成后才重新COLLECT。即使首beat能在AW握手同周期给出，256像素至少占256+16周期；8100个burst共2,203,200周期。当前engine的`use_tiles=0`，不是另一种tile吞吐口径。双缓冲可重叠收集与写回，消除此空泡，但单独修它只能节省最多约129,600周期/帧（1.0368ms），不足以把30提升到60。

2. **cache miss串行阻塞快路径。** `ddr_neighbour_cache_scatter4_rowpipe.v`的fast hit可每周期一个query，但slow miss会等待fast结果排空，再逐邻域SELECT/CHECK/AR/FILL/SCATTER/LOAD/PICK。每fill只有8个返回beat，却要32周期将128个RGB565像素按4像素/周期写入缓存；SCATTER期间占用even/odd RAM的全部写端口，不能正常读取下一query。它是调度/片上写口组织成本，不等同DDR总线已饱和。

3. **rowpipe主要切时序路径，未扩吞吐宽度。** 新增`pre_row`一级切开y×WIDTH与x/offset加法，保留1query/周期快路径与原slow状态机。新八帧的完整结果现已确认：commit→release逐帧与旧八帧摘要完全一致。此功能回归不能证明最终Fmax提高。

4. **视频接口目前硬性为30fps。** 输出默认2200×1125、74.25MHz，每周期一个RGB888像素；输入observer的1ms PCLK窗口只接受73500–75000边沿。1080p60标准相同总时序需148.5MHz，新模式必须同步修改/验证PLL、输入准入、FDC、外部AC和FIFO吞吐，不能仅让核心跑得快然后声称60fps输出。

## 优化优先次序

| 顺序 | 独立实验 | 应量化的收益与风险 |
| --- | --- | --- |
| P0 | 完成当前八帧与最终STA，先交付实板30fps闭环 | 保住一周内交付，不把未通过recovery和外部IO带入现场 |
| P1 | 已读取本轮最终frames.csv/summary，先据真实热点选择独立改动 | 每帧F=25,944，32F=830,208scatter周期，占最坏处理周期约21.76%；不能直接把重叠pressure计数相加 |
| P2 | writer增加第二个256像素buffer | 额外逻辑数据512字节，收集与16beat写回并行；先验证AW/W不可撤回、tag/CRC、最后burst排空、fault/common reset；最佳仅约1ms/帧 |
| P3 | 首先独立试验现有parity TDP RAM打包为32bit/word，其次才分bank或预取 | 32bit每写端口两RGB565像素，可保留even/odd两个逻辑RAM、每RAM两个端口，以8像素/周期将scatter32→16周期。相对32周期最多省16F=415,104周期（3.320832ms），实际净收益取决重叠；须验证32bit TDP推断、地址bit1选择和同步读metadata对齐 |
| P4 | 若确需60fps，设计2pixel/query lanes，或先取得更高Fmax证明后采用适度提频 | 2lane涉及mapper/双线性/cache读口/gamma统计/writer和标签的整链变化；125MHz单lane几乎无空泡预算，不是一处参数修复 |

32bit打包的容量可保持32KiB：原每parity的8192×16bit改为4096×32bit（INDEX_BITS=7）。每个读出的word含相邻的两个同parity像素，以原像素地址bit1选择half；fast路径必须随tag/fx/fy/bounds保留half选择，slow路径也须在SELECT锁存并经LOAD/PICK对齐。每周期四个写端口各写32bit，共8像素；这不是必须增加bank数的优化。PDS是否映射成预期TDP DRM、实际DRM数量/余量以及读写冲突行为必须另验。若再追16像素/周期，可评估64bit打包或更多bank，不能仅根据总bit容量宣称物理资源不变。

即便按最理想无重叠抵消计算，32→16scatter把最坏3,816,061周期降到约3,400,957周期，仅折算36.75fps处理容量；再叠加writer最佳129,600周期节省，约3,271,357周期，折算38.21fps。它们都是估算上限，未实现或验证，仍离60fps所需约45.41%的总周期缩减很远。

预取方案必须保持实际DDR口ID=0、无RREADY、整burst不可反压的契约。当前读仲裁一次只允许一个burst占用总线；增加多个outstanding或在fill期间发下一AR，需要独立的整burst预留、目的行元数据队列及错误隔离，不能简单扩大FIFO。缓存容量目前32KiB，不先凭猜测加大；若统计显示冲突/重读主导，再比较分bank、associativity或访问顺序。切到tile顺序还会启用writer的stripe重排成本，必须对完整链而非仅cache命中率评估。

## 最小后续实验

本轮表已列明。后续首个cache实验可只改存储字宽和half选择，保持块大小、tag规则、容量及slow协议，先用稀疏四邻域的跨32bit字边界、frame drain、反压、reset/fault测试验证，再同源small。对比每fill16周期是否成立以及完成总周期，不能靠把旧32F断言改成16F直接算通过。基线和候选使用同一CPU golden、同一Brown配置与反压时序，分别列warmup/steady/tail。每次只改一个机制，再决定是否做完整native、资源推断及最终STA。当前没有足够数据认定DDR物理带宽已成为主墙。

## 定位

- 已完成旧八帧：`distortion/output/project/board1080-offline-summary-20261028.json`。
- 新八帧最终回执：`distortion/build/board1080-rowpipe-reproduction/local-native-20261028-a/board1080-system-simulation.json`，SHA256 `c38d2a18a0b240c272363722e8962a0b27e7cb345d1b07a388b6f06a8aadd752`。
- 新八帧最终逐帧表：同目录`frames.csv`，SHA256 `a5724002cbb14e0998f6e4e19ab55d5e38b2740ec5398a94c223b246f16610f9`。
- 新八帧最终日志：同目录`simulation.log`，SHA256 `0fd7fcb46b0e73ce268d73258d9381dab927cfcb85ddcc125e8e265dce6b824c`。
- engine：`distortion/rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v`，use_tiles第23行、INDEX_BITS7第42行、raster发射第82行。
- writer：`distortion/rtl/experimental/ddr_adaptive_result_writer.v`，COLLECT-only ready第34行、收256/转ADDRESS第80行、WRITE第90行以后。
- cache：`distortion/rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v`，fast accept第157行、SCATTER第311行、最后8beat进入SCATTER第331行。
- 输入模式：`distortion/rtl/experimental/hdmi1080_input_status.v`第8–9行。
- 输出模式：`distortion/rtl/experimental/ddr_video_output_1080_board.v`第11–13行。
