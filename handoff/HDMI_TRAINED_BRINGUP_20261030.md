# HDMI 启动修复版实板交接（2026-10-30）

**2026-10-31用户已暂停本输入支线。** 后续重点是摄像头目标链的处理与HDMI输出，暂不处理输入。本页的源线拔插/重新下载等历史步骤不再自动执行，见[当前方向](ACTIVE_DIRECTION_20261031.md)。

**最新为17:22 V3累计计数诊断，板上已运行 `hdmi_uart_interval_diag`。** V3首窗口VS计数全0，仍未形成有效帧；见[当前交接](CURRENT.md)和[V3详细记录](HDMI_INTERVAL_DIAGNOSTIC_20261030.md)。以下trained/V2描述保留为历史对照。

## 后续实测：V2 freshness 采样点未见 VS 更新

2026-10-30 16:29–16:30（北京时间）：重新上电后，旧 SRAM 配置不在；COM7 4 秒无字节。新建并完整审计 `hdmi_uart_activity_diag`，它复用已训练极性观察器，只输出原有参考域 freshness 状态，不更改帧判定。V2 build tag 为 `0x48444902`，旧 V1 UART 解码仍兼容。

候选 PDS、161 FF/81 连接/46 脚映射、74/92/1/4 原生 CDC 查询及限定双角 STA 都是该候选自身的新结果。双角十类零失败，slow setup/hold +1.077/+0.164 ns，fast +1.942/+0.104 ns。scoped ADF SHA256 `baa50510f3ed907fe103563571b59e4f9cfcde989548fa603a1b50d3c6af4e23`；最终 5087 单元网表功能图和寄存器位置与候选原始 ADF 一致。V2 位流 SHA256 `c1bcd72519050967e13607b574e684831ecb6ba8d5759c9d90e1ca725b104ba7`，于 16:29 左右下载到 PG2L100H SRAM，DONE=1，未写 Flash。

下载后 COM7 5 秒 10 包、CRC 错误 0、RX/ALL done、快照新鲜。PCLK freshness 10/10，DE freshness 10/10，snapshot freshness 10/10；VS freshness 0/10，frame freshness 0/10。每包开始时 freshness 只回看此前 100ms，包间隔 500ms，十个回看窗口并不连续。几何为 1920×0、fault `0x12`、good/bad 帧计数不变。最终功能网表确认 `vs_in → polarity normalization → geometry VS counter/Gray CDC → vsync_fresh_ref → UART V2 byte 52` 路径连通，未发现静态断线。证据在[活动诊断实测包](../distortion/results/hdmi-activity-live-20261030/manifest.json)。这支持采样时没有近期 VS 帧起始活动且 mailbox 正常；仍不能据此断言整个 5 秒没有 VS 边沿、不能定位源/接收器/物理路径中的具体原因，也没有输入像素内容或 HDMI PHY 锁定证明。

下一步保持上电重拔插 HDMI IN 源线并重复只读窗口。如果 VS freshness 仍为零，再加包间 VS 边沿计数或读取器件 mode/clock 状态的专用诊断，避免重复下载或仅依据 Windows 模式信息判断。

新 `hdmi_uart_trained_diag` 已完成自身构建、限定 STA、位流生成和 SRAM 下载。RX/TX 初始化本次无需拔插即完成，但首次输入窗口仍未通过，报 `0xC5`、没有好帧计数。当前板上运行此修复诊断，尚不包含 RGB 像素采集、DDR 或畸变主链。

后续用户已完成电脑端 HDMI IN 线拔插；20包均报0x12短DE行，1920×35、好帧0、PCLK约74.249MHz。随后用同一精确位流重新下载SRAM复位，第二次下载后DONE=1/Flash未写；再读20包仍0x12，宽1920、高0、无好/坏帧计数变化。该次复位/拔插结果在[补充采集记录](../distortion/results/hdmi-trained-live-20261030/)保存。当前用户准备关机，本轮停止；关机后板卡易失SRAM状态会丢失。

[当前结果](../distortion/results/hdmi-trained-20261030.json)、[仿真证据](../distortion/results/hdmi-trained-20261030/sim-progress.json)、[244 项原生与实板证据清单](../distortion/results/hdmi-trained-native-20261030/manifest.json)及[补充快照静态复核](../distortion/results/hdmi-trained-mailbox-20261030/manifest.json)均随仓库保存。旧观察器的拔插前后失败对照见[首次上板记录](HDMI_INPUT_LIVE_20261030.md)，原始记录未覆盖。

## 已完成的修复和验证

新 RX 控制器在四个状态字节均成功读取后，接受首轮已经 ready=02 的情况；持续 ready 不重复设置，后续 00→02 仍重新设置。新极性观察器要求两段完整、恰好 WIDTH 拍且 VS/HS 电平稳定一致的 DE 行才锁定，锁定后的光栅和故障准入不放宽。

原生验证包括 RX 七场景、训练 11 场景、完整 1080p30 同输入瞬态 A/B、原两极性/短行/停钟/复位回归，以及真实 checked I²C 七场景的 2117 笔有序事务与 2112 笔成功遥测逐项匹配。额外八相位/双极性复位释放测试中，源与参考域均只启动一次，快照与好帧正确推进。225 项相关 CPU 检查及四个交付基线审计通过。

独立新 PDS 构建退出 0、16 项输入和 12 个冻结编译副本无漂移。原新库 ADF 为 `4a3c40ccd467c09038b8629f7d3158eba9399e01c2dc2c55876af6131a79715b`。新原生查询逐项匹配 74 个同步首级、92 个 held bus 捕获位、1 个反向请求首级和 4 个像素域复位同步引脚；仅新副本应用限定约束。

最终 ADF 为 `88a6d04e25fa6de3d280d1458a06ef2ded506f1b6768476ae94dc7ce45fab399`。双角十类零失败，slow/fast setup 为 +0.641/+1.676 ns，hold +0.140/+0.090 ns，recovery +0.818/+1.955 ns，removal +0.160/+0.023 ns。每角 167 条 8 ns MaxDelay，setup false-path 为 0、hold 167、recovery/removal 各 4；非目标行、时钟与外部 IO 警告集合不变。最终库直接导出后，5066 个单元的功能图及全部寄存器位置与本候选原库一致；46 脚/方向、161 个同步 FF 和 81 对同 CLM 直连核验通过。

6 条属性忽略警告保留；同 CLM、限定约束和内部时序通过不等于完整物理 CDC/MTBF 或外部接口 AC 验收。没有使用旧观察器的 ADF、优化后对象名或位流来代替新候选证据。

## 实际位流和下载

| 项目 | 记录 |
|---|---|
| 位流 | `distortion/build/hdmi-uart-diagnostic/trained-bit-1030-a/generate_bitstream/hdmi_uart_trained_diag.sbit` |
| 长度 / SHA256 | 3,791,112 字节 / `174324853d6e294c6e2aa5a03af72a0195d063b3f7ce8460abfa6dd024919d81` |
| 位流生成时间 | 北京时间 13:34:12 |
| 生成流程 | 新 STA → 精确原生报告/例外及来源门禁 → 位流生成；原生退出 0 |
| 实际下载 | 北京时间 13:38–13:39，115 项绑定核验，PG2L100H / `0x00602899`，下载后 DONE=1 |
| 存储范围 | 仅易失 SRAM，Flash 未写 |

独立一次性执行脚本、计划、扫描和下载原始日志已封存。下载器只管理自有进程，最终清理无错误。包含新位流的离线 ZIP 已核验并保存在本机，尚未发布；路径与哈希见结果文件 `LocalArchive`。

## 当前实板结论与下一项

首次 COM7 / 115200 / 8N1 只接收 10 秒获得 20 包，CRC 拒绝 0、配置错误 0、RX/ALL done=true、observer_released=true，未先进行新一次拔插。flags=0x05bf，VS/HS 学得 inactive=0，PCLK 约 74.248–74.249 MHz；宽高、好帧、坏帧均为 0，fault=0xC5。独立原始字节 CRC/序号/tick 检查通过，输入窗口评估失败。

C5 的准确含义是启动窗口内没有看到好帧计数更新。当前 UART 不提供 geometry 快照新鲜度和原始 VS/DE 联合计数，不能单凭 C5 区分源域未形成帧边界与快照未送达。最终网表 VS 归一化、frame_started、源使能/复位、request/ack 同步链、held→ref→good 连接及采样使能均已逐项核对或真值枚举，未发现静态断开或常值复位；这仍不证明实物信号正确。

已请求用户保持上电，再把电脑端 HDMI IN 源线拔下约 3 秒再插回，并报告完成。收到完成反馈后，保存新的原始 UART 窗口，观察好/坏帧和几何是否开始变化；旧 C5 是粘滞状态，不用后续计数覆盖首次失败记录。若仍无更新，下一独立诊断应增加原始 VS/HS/DE 活动和 geometry 快照新鲜度观测，先取得区分证据。

未进行新修复版的重复冷启动、长稳、真实输入像素或矫正画面验收。温度状态仍未核实，测温支线按用户指示暂停；历史 over_temp 标志不是温度读数。
