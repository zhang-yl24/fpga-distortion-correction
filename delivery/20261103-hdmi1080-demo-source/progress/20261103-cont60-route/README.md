# INDEX6连续三帧与真实60Hz配置路由：协作交付

本页合并发布新的连续三帧数字验证和实际路由失败路径，供同学帮助收敛。两者与旧板测各自绑定身份；没有新位流、烧录或实板60结论，也不代表竞赛已提交。

## 三项结果分别看

| 身份 | 已完成 | 未完成 |
|---|---|---|
| 精确INDEX6连续RTL | 1920×1080、2200×1125、148.5MHz规范化输入，连续3帧，真实DMA/校正/扫描共享行为DDR；6220800像素及各帧CRC通过，3次新呈现、0重复/丢弃/overflow/no_free | 有限3帧，不是无限持续摄像头负载；排除物理接收器、PLL、PHY与板测 |
| 正确60Hz配置Map/实际route | 139原生输入+2附加约束；输入STA包络150.2MHz、输出PLL/像素148.5MHz、core125MHz；Map FF25347、LUT30535、DRM23、APM68、IO144；route与独立STA均退出0 | slow setup **10213端点、WNS−2.105ns、TNS−6350.999ns**；没有bit、不签核、不上板 |
| 旧冻结板测57044fe8… | 20.033094 nominal秒内468新完成/新呈现，23.3613fps；仅两条内部样本31.155160/31.260184ms | 不属于本连续RTL或60Hz路由候选；125MHz未独立测频，硬件E2E未测 |

完整三帧的DUT50项源码/清单与前次INDEX6单帧交付逐字节相同，直接复用[既有源码](../20261103-morning/index6/source/)。本次补充精确bench、时序配置、CSV和摘要，不重复上传大fixture。原本机ZIP 288174B、SHA256 2af940096ae4680d511d6365dbc19af525b1a7ac8d4c25a2dda90ed42e6fc3e4 只留本地；117项封存输入均已核验。

三帧无source-ready gating、无帧间stop/wait，不向DDR预装源图；真实输入DMA与显示仲裁同在DUT中。第二帧有1997893个三方重叠周期；整个测试观测到read-dual706、write-dual407。每帧实际miss18268，原16200 advisory保持不匹配，不能用理论值覆盖实际总数。

## 数字链路延迟，不能当板上E2E

| 帧ID | engine begin→done周期 | nominal处理ms | 输入SOF驱动→首个对应扫描观测ms |
|---|---:|---:|---:|
| 1 | 2073970 | 16.591760 | 33.941813181 |
| 2 | 2073971 | 16.591768 | 33.941813180 |
| 3 | 2073961 | 16.591688 | 33.941813181 |

SOF驱动到源接受的合并阶段约16.66673ms，接受到engine开始8ns，engine完成到首次扫描观测约0.6833ms。**原始capture/DMA-ready时间没有日志，capture-ready→accept队列等待必须留null，不能把16.66673ms全部叫排队。** registered source_commit是接受之后的通知，也不能反推更早的DMA完成。

首/末扫描是output negedge观测，较输出寄存posedge晚半像素周期；末扫描约49.939921ms。上述只是数字模型时钟/事件边界，排除曝光、摄像头、PC、物理HDMI、显示电子链路与光学。不能与旧板31ms内部样本互换，也不能宣布33.94ms硬件E2E。

## 实际slow setup分组与同学协作重点

| 分类 | 失败端点 | 最差ns | 实际路径方向 |
|---|---:|---:|---|
| cache | 8683 | −2.105 | decoded_line/block → pending_tag表更新 |
| scan | 898 | −1.198 | words地址寄存→地址寄存复位/控制端，148.5MHz域 |
| writer | 589 | −1.363 | writer failed广播→mapper tags/CE，非单纯Wdata mux |
| DMA | 39 | −0.402 | board_failed_core→active_id/CE |
| other | 4 | −0.245 | telemetry ticket→mailbox |

[TIMING_PATH_SUMMARY.json](route/TIMING_PATH_SUMMARY.json) 提供每类最差3条原生路径和启动/捕获寄存族排名，全部10213个唯一端点分类总数已核对。来源routed ADF SHA256 29d333c937f25c3e4a4749a644e6b3b7b02f59ce8d598e7e1369e27bb49f6104；原始report SHA256 e2eae935adae9273a113a3503e16bbc97200904c4d3c1013aba66a7e9114e457，未上传巨大raw report或ADF。

最差cache路径6级、fanout197，data9.746ns中route8.346ns/85.6%，logic1.400ns/14.4%。writer样本fanout281、route85.4%；scan样本7级、fanout128、route72%。优先请协作评估局部寄存/分块使能和物理扇出，而非照搬旧writer输出寄存；我们的RAM writer已经注册读出。保持query/lease/ABA、CRC、accepted-AW排空、故障隔离与显示首末像素语义，任何方案先做短等价/错误路径验证，再进入实际Map/route。不能用false_path隐藏这些同域setup，或降像素/core频率后仍称当前60配置通过。

## 厂商约束：登记不等于生效

本次两条gate优先RCF实际执行成功，但三条single-clock异步组仅登记文件，**最终interaction中Asynchronous Group行数为0，实际未应用**。从placed ADF恢复后继承了原未分组时序模型；额外FDC注册并未重建该模型。FINAL_AUDIT的早期“登记即生效”假设已纠正，原数字与源码不变。这里不能套用同学stable30最终已应用组的结果。

实际slow/fast recovery仍245/228个失败、removal各1；fast setup为0、双角hold为0。外部input/output delay仍缺55/111，CDC与复位/硅片/硬件均未签核。三类IP域的叶负载归属已读回，但归属正确不意味着异步组已生效或物理复位可靠。用户core有大量IP外负载，绝不能整组豁免。

下一候选若恢复匹配IP模型，必须在fresh compile/Map阶段正确加载并在最终interaction/完整leaf ownership再验证；保留用户域、core↔divided PHY的真实时序、MCP2与0.4ns uncertainty。没有据此授权忽略10213条用户同域setup。只发布约束配置摘要和hash，不发布厂商受限原件/PLL包装源。

## 复核及使用范围

[native-critical](native-critical/) 是关键自有RTL的便携include副本；原始native SHA和交付SHA均列明，只有绝对include路径改为同目录头文件，没有宣称重新HDL验证该副本。它不是完整139输入/IP构建包。连续bench精确保留；大.mem源/期望fixture只给原哈希，不附大数据或宣称一键重放。

运行python -B verify_release.py核验复用50项、精确bench/CSV、便携副本与数字边界；不运行HDL/EDA、不打开COM/JTAG。原始证据、源码和新暂存均在项目D工作空间。新增交付不含机器用户名路径、私聊、许可证/密钥、厂商实现、位流或巨大中间件。