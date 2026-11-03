# HDMI鱼眼：fill8证据复核与8×8双条带下一步

2026-11-03。本文只记录独立只读复核与下一候选设计，没有改当前板上固件、冻结provider或生产RTL，没有执行PDS/COM/JTAG。

## 当前事实与证据范围

- C板上矫正已被用户确认画面正常，但有卡顿。`distortion/work/hdmi-camera-fisheye-20261103-a/live-baseline-reparsed-resume.json`重新解码了实际wire：矫正处理约4.3104帧/秒、唯一显示约4.2760帧/秒、末次处理222.475ms；原图处理和唯一显示约30.0005帧/秒、末次处理31.371ms；HDMI刷新约30Hz，输入数字VS约60Hz。两者都是各30样本/约29秒窗口，host/core交叉频率约125.002MHz。它们是已下载C的实测，不能移用为fill8硬件成绩。
- fill8源`ddr_neighbour_cache_scatter16_rowpipe.v` SHA256 `ebf3566e39589e7c383d5cf753675c440823b19b4eabfdd9bd33b68c37561091`；基线fill32源SHA256 `15e7927a6d8069e5f204c46c90956a5a5839239376da69719a659745307448bb`。接口/FIFO/坐标预计算/替换与故障策略相同；变化是64bit四lane偶/奇TDP组织、同步lane选择及32→8写入拍数。
- 独立`fill8-20261103-a/unit-a/simulation.json`实际通过；此处完整目录是`distortion/work/hdmi-camera-fisheye-fill8-20261103-a/`。同一独立坐标/边界/RGB565公式分别测试fill8、fill32。WIDTH639各53次完整fill/6784个RAM像素检查；WIDTH1920各43次fill/5504个RAM像素检查；每配置322个四邻域/小数/25bit标签输出全部匹配。并非拿旧RTL输出作为新RTL像素oracle。
- `system-small-a/simulation.json`实际通过，32×16两帧1024个真实扫描像素，4次fill/帧、32次scatter/帧，矫正/原图793/780个模型core周期；AW/W/AR背压12/24/7次，3次KEY变化，完整drain。该small结果没有实际read/write contention，不能拿它推断native争用。
- 本文初次复核时`system-native-a`仍在运行，尚无`simulation.json`；native结论应由根代理读取其最终report和独立comparison后追加。PDS/原生宏/STA由另一任务推进，本文不替它放行。

## 单元与系统测试的有效性

暖缓存测试连续接收64个不同X/小数/标签查询，检查64个输出的跨度为63周期，首个out_valid距外部输入握手4周期；两种cache分别实际满足这些断言。它验证真实II=1与保持接口延迟，且确认测试窗口没有新DDR fill。WIDTH639上行与下行相反的线性像素奇偶，使upper/lower端口和lane选择不能仅靠偶数行宽巧合通过。逐fill读取全部128个RAM像素，覆盖后续查询没有碰到的写lane。边界查询横跨8/16/128像素字/beat/block边界及图像右/下边界，使用signed坐标和黑边参考。

lane寄存器与其RAM读字分别在完全相同的read_enable/read_lower条件下采样。上个v0在某个边沿转移到输出时读取的是旧RAM读字/旧lane；同边沿下一查询的RAM/selector更新在NBA后发生。输出被阻塞时fast_pixel/fraction/tag保持；允许填入一个v0后read_enable停止。单元确实覆盖输入阻塞、FIFO满与结果阻塞，但没有逐一断言所有四个lane selector的内部hold；其外部像素/元数据oracle和完整RAM检查提供主要功能证据。

最后scatter前复位测试在group7（旧group31）将要写入前断言reset，检查valid_lines清空、没有旧结果泄漏，并在同地址重新完整填充。六类sticky故障实际覆盖RID错误、早RLAST、缺末RLAST、无请求R、AR超时及FILL无R超时；AR超时后还检查地址请求不被撤回。新帧请求在队列/输出尚未drain时必须等待；相同bank新epoch与换bank均重算独立源数据。

需要补齐的真实缺口：

1. 初版unit-a和系统模型均以left/rleft>0才驱动R，因此**没有测试AR握手同拍首R**，尽管cache的receiving表达式明确支持它。应独立增加该正常路径，再分别跑fill8/fill32；不要改正在运行的system-native源闭包。
2. 系统small只有cold启动和WREADY强制为1时的本域两拍reset探针；没有warm处理中复位、故障后重新采图、持续60Hz输入下的整帧丢弃压力。cache局部reset/fault通过不等于系统这些行为通过。
3. 单元不是物理TDP模型；64bit端口可能拆成多块DRM，lane mux和使能会增加实际路径。PDS须核实读延迟、TDP模式/碰撞语义、同一宏端口的所有lane、真实资源及125MHz时序，不能复用fill32物理证明。
4. 两帧系统仿真是功能/CRC/所有权证据，不是持续帧率测试。需要后续真实板上分别测处理、唯一显示、刷新率和fault，再宣称硬件提帧。

## 为什么不能直接打开现有tile开关

`hdmi_camera_fisheye_engine.v`已经有8×8发射分支，但`use_tiles=0`。它按tile-x→tile内row→tile内column发射，tag始终保留global raster index；鱼眼坐标核与双线性计算可以逐字节保留。8×8模式只需在**新engine候选**按整帧锁存的corrected模式选择tile，raw继续raster；KEY请求变化仍只在下一事务生效。

现有`ddr_adaptive_result_writer.v`的tile分支只有一份8行stripe：COLLECT满后停止接收，再逐像素READ→PACK各一拍，最后每256像素执行16个256bit写拍。1920×1080的N=2,073,600，即使全部AW/W零等待，仍至少需要：

`COLLECT N + READ/PACK 2N + WRITE N/16 = 6,350,400 cycles = 50.8032ms @125MHz`。

这还没算cache/mapper停顿、ADDRESS空拍、末尾DRAIN与银行调度。仅打开tile开关即便减少读miss，也无法用这个writer达到30个新帧/秒。

## 最小下一候选：8×8发射 + 双stripe + 每拍一个像素的排空

先保留INDEX7/fill8的32KiB逻辑cache、23级坐标核、量化和插值，避免同时增容/增频。新增独立engine/writer源与构建入口：

1. 两份`WIDTH*8`个16bit像素stripe。1080几何每份15,360像素/30,720字节，两份共61,440字节（60KiB），比旧writer增加30KiB逻辑像素存储；另外保留一个512字节16-beat输出burst缓冲。这只是逻辑容量，物理DRM数以PDS为准。
2. 每个stripe状态为FREE/COLLECT/READY/DRAIN，写入owner与读出owner分开。tile-tag严格验证全局expected顺序和stripe_base范围，然后写`tag-stripe_base`。一份DRAIN时另一份继续COLLECT；没有FREE bank时反压，绝不覆盖READY/DRAIN数据。
3. READ改为带valid/index的同步流水：RAM每拍读一个16bit像素，下一拍PACK，前后像素可重叠，II=1。只保留一个burst时，完整装好256像素后暂停RAM issue，执行AW与16拍W；必须保留AW握手同拍首W和最后W的正确处理。预留issued/packed计数和RAM返回valid，防止burst满时多发一个RAM读导致丢像素。
4. CRC只对按光栅顺序真正PACK的16bit像素更新，仍使用既有`video_crc32_pixel`。采集tile顺序不能用于CRC；背压不能重算同一像素。这样无需立即新增4pixel并行CRC逻辑；每拍一像素已经满足writer本身的30FPS预算。若实际RAM/DDR争用使此方案不足，再独立升级64bit四像素排空和对应CRC。
5. stripe只有完整验证后能READY，全部RAM返回/已pack数据和已发DDR burst确认完成后才FREE。帧done必须同时满足accepted=N、packed=N、written_beats=N/16、两stripe都FREE、RAM read-valid为空、AW/W无未结事务、最终CRC已定。保留现有source/result bank锁和display边界；不把最后输入像素当完成。
6. 共用C现有同步释放边界。reset/故障时阻止新stripe/新帧，保留已发总线事务的既有约束；不能让修改后的writer在stall时撤回AW或改变W数据/所属bank。

## 30FPS的精确预算与风险

125MHz下每30Hz结果间隔平均4,166,666.667周期；所需像素率62,208,000/秒，即平均0.497664像素/周期。每帧4,147,200字节RGB565，129,600个256bit beat、8,100个16-beat结果写burst、135个8行stripe。

上述一像素流水writer可以保守按每256像素`256 issue + 1 RAM填管 + 1 AW + 16 W = 274周期`预算；AW同拍首W时会少一拍，此处保留一拍余量。无外部stall时每stripe最多60×274=16,440周期（131.52µs），每帧排空预算2,219,400周期（17.7552ms）。COLLECT与排空重叠，目标30FPS下排空占53.2656%的core周期、采集占49.7664%；两者在不同stripe存储上并行。因此第一版无需4pixel/周期排空，但必须实测RAM/DDR能否达到这个重叠。

既有C镜头地址模型（`cache-address-profile-a.json`、`cache-address-tiled-profile-a.json`）在策略不变时，fill8仅把每miss的scatter成本减24拍。以下**只是在已保存地址trace模型中替换写拍数**，不是RTL实测周期或硬件FPS：

| 顺序 / INDEX | 256B fill/帧 | fill8乐观core周期 | @125MHz时间 | 距30FPS平均周期预算余量 |
|---|---:|---:|---:|---:|
| raster / 7 | 275,060 | 10,928,065 | 87.4245ms | -6,761,398.33 |
| tiled / 7 | 49,465 | 3,647,654 | 29.1812ms | 519,012.67 |
| tiled / 8 | 37,483 | 3,263,109 | 26.1049ms | 903,557.67 |
| tiled / 9 | 31,110 | 3,057,400 | 24.4592ms | 1,109,266.67 |

INDEX7 tile模型的519,013周期余量，平均只有10.49额外周期/fill，尚需支付AR等待/DDR首数据等待、display/capture仲裁、每miss流水排空、最后stripe排空和bank/display相位等。按最后stripe16,440周期先预留后只剩502,573周期（约10.16/fill）。因此INDEX7是最小验证候选，**不能据29.18ms估算承诺30FPS**；必要时由实际stripe stall分布决定是否INDEX8/9增容或改miss路径。双stripe也不能保证整帧严格等于max(生产时间,排空时间)：stripe之间不均匀、两bank已占用时仍会产生生产反压。

DDR有效payload预算按目标30次新图/秒、source只接受30次/秒、display读30次/秒计算：

| 业务 | 每帧字节 | 每秒有效payload |
|---|---:|---:|
| tiled INDEX7鱼眼源块读取 | 12,663,040 | 379.8912MB/s |
| 输入采集写DDR | 4,147,200 | 124.4160MB/s |
| 结果写DDR | 4,147,200 | 124.4160MB/s |
| HDMI结果读DDR | 4,147,200 | 124.4160MB/s |
| 合计 | 25,104,640 | 753.1392MB/s |

256bit×125MHz用户接口的单通道名义字节时钟是4GB/s；753.14MB/s为18.82848%的这个名义值，**不是外部DDR保证带宽**。命令开销、refresh、读写切换、controller时序与display urgent仲裁必须计入。若实际采集接收60帧/秒，额外再加124.416MB/s，总计877.5552MB/s。当前raster源读取本身在30FPS要2,112.4608MB/s，四项总计2,485.7088MB/s；tile是优先降低需求的方式。

## 下一实现与验收顺序

1. 先完成fill8 native系统结果和新PDS/原生宏/STA闭合，再按根代理持续授权的原流程下载/实测；保留已验C作为回退。单独fill8可确认可靠改善，但raster地址模型已证明它不足以单独解决30FPS。
2. 实现独立tile双stripe writer单元：tile/global tag错误、重复/缺失/越界、两bank反压、同拍收最后像素/排空最后beat、AW/W全部stall边界、最后burst未结束禁止done、跨帧reset都要用独立raster像素与CRC参考检查。
3. small完整系统通过后跑1920×1080矫正→raw→矫正及持续输入压力，分别记录producer阻塞、writer阻塞、stripe READY等待、RAM有效返回、每miss额外等待、read/write contention、bank wait与新结果扫描次数。这样能判断INDEX7的约4ms余量具体花在哪里。
4. 保持125MHz，检查新TDP/stripe/CRC与标签valid对应路径和现有C同步释放边界；PDS全闭合后再上板分别测30秒。只以实际processed/unique-presented改善称提帧，HDMI30Hz刷新和地址模型倒数均不作为硬件FPS。

## 同拍AR/首R缺口已补（随后实际验证）

根代理要求补实测后，另建`tb_fill8_rowpipe_cache_samecycle.sv`和`run_fill8_rowpipe_cache_samecycle_sim.py`，保留unit-a bench/runner及其报告原字节。`unit-b-samecycle/simulation.json`实际Passed，InputDrift=[]；分别执行fill8/fill32×639/1920，同拍AR/首R计数在每种cache均为57/47次，322输出、完整RAM lane检查、六故障、64输出/63拍及首valid延迟4拍全部保持。正常burst首beat在AR握手边沿即到达，其余七拍保留真实间隙；FILL超时用例仍故意不发首beat。此补充关闭上文缺口1的**cache局部**部分，不扩写为系统arbiter/物理DDR同拍行为或warm系统复位通过。
