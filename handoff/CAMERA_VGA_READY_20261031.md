# 2026-10-31 摄像头候选离板准备与上板观察

> 最新用户观察：相机画面随景物更新、LED5/6闪烁、LED7长灭，基础链路已运行；但画面180°倒置，尚未修复。当前有效图像640×480，用户已提出后续1080p升级问题：存储/主要参数具备基础，输入模式和帧率待验证，不承诺1080p30。下一步先解决方向，再验证目标分辨率；详见[当前实板记录](CAMERA_VGA_LIVE_20261031.md)。下文旧“等待实屏反馈”为历史状态。

> 2026-10-31 当前状态：用户本次确认上电后，camera_vga_output_top 已于北京时间15:38–15:40下载到易失SRAM，位流SHA256 acec0a65…b25e0；芯片PG2L100H/0x00602899、下载成功、DONE=1、Flash未写、清理错误0。开发板最近确认上电，当前等待用户反馈相机画面及LED5/6/7。下载成功不等于实时相机验收；外部AC/标定/长稳仍未验收，HDMI IN支线继续暂停。见[摄像头下载与实屏观察](CAMERA_VGA_LIVE_20261031.md)。下文旧“开发板断电”“等待上电”“尚未下载”为此前阶段记录，不覆盖本条。

本页保留下载前检查、约束边界与复现步骤；本候选已完成本次SRAM下载，当前实屏反馈与硬件状态以[下载记录](CAMERA_VGA_LIVE_20261031.md)为准。旧准备计划保持只读，禁止直接再次执行已有receipt的单次计划。

## 当前候选

- 入口 camera_vga_output_top；OV5640 CAM2 → RGB565 采集 → DDR → 图像处理 → HDMI OUT。摄像头仍接着，旧“未接摄像头”为误点。HDMI IN / MS7200 支线继续暂停。
- 相机目标 640×480，画面居中放在 1920×1080、30Hz HDMI 扫描区域，四周黑边。30Hz 是显示刷新率，不代表每秒产生 30 个新相机帧。
- 默认畸变系数全部为零，先验证真实相机传输；当前镜头标定及畸变矫正效果尚未验收。本候选不应显示固定红十字/棋盘测试图。
- 本候选没有 UART 接口，不运行此前 COM7/HDMI 输入诊断命令。
- 最终 ADF：distortion/work/camera-vga-output/physical-final-report-20261031-a/input.adf，SHA256 daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f。
- 内部时序双角十类检查零失败；fast hold 最小裕量 +0.016ns。详细证据见 [内部时序修复](CAMERA_VGA_TIMING_FIX_20261031.md)。
- 摄像头 PCLK 48MHz、输入延迟 0..5ns 是当前工程预算，未作为实测外部 AC 参数。实际摄像头输出、板级采样裕量及长期稳定性需实板验证。

## 下载后观察方法

以下仅是源码对应的预期，尚无本候选实板结果：

1. 仅使用新候选的已核验位流和单次易失 SRAM 计划，不写 Flash。扫描芯片身份、下载完成、DONE 状态与实物画面分开记录。
2. 相机、DDR、HDMI 初始化全部就绪后，还需连续等待 8 秒预热才释放处理流水线；不能下载后立刻把暂时黑屏判作失败。
3. 正常期望为黑色背景中央的相机画面。改变镜头前景物，检查图像是否随之更新；固定测试图、DONE=1 都不等于摄像头链路成功。
4. LED0 是心跳；LED1 是同步后的 DDR 就绪；LED2 是视频 PLL 锁定；LED3 是相机配置就绪；LED4 是 HDMI 配置就绪。
5. LED5 为采集帧计数 bit4，LED6 为处理完成帧计数 bit4；持续亮灭说明相应计数在推进，不能据此推算精确帧率。LED7 是粘滞故障指示，正常应熄灭。
6. 运行故障保留证据、停止新任务接纳，不自动重置已接收的 DDR 事务。需要复位时按共同复位流程处理，不以重复拔插 HDMI IN 排障。

## 准备记录

2026-10-31：重新核验原始 115 项输入、109 项编译输入及最终 ADF 的来源绑定，通过且无漂移。

摄像头位流已于北京时间 15:20 生成并通过独立复核。工作目录 distortion/work/camera-vga-output/bit-20261031-a；文件 generate_bitstream/camera_vga_output_top.sbit，3,791,112 字节，SHA256 acec0a6528760cabe8291d4452c635e26d7e0f7b3fdfef997a386d1c365b25e0。原生退出码 0，用时 259.218 秒，输入漂移为空；芯片/顶层/工具版本头部核对通过。

生成前在新进程中重新执行 STA，双角十类内部检查、时钟和全部时序例外均与最终候选一致，CPU 校验通过后才执行 Generate Bitstream。实际流程仅 Report Timing → 校验 → Generate Bitstream，没有重新综合/布局布线，也没有板卡访问。回执为该目录 execution-result.json、pre-bit-audit.json 和 verification.json。

最后的引脚与 CDC 精确路径查询已在独立副本上正常完成：release-interface-query-20261031-b，原生退出码 0，用时 252.986 秒，诊断错误与输入漂移均为空，ADF 保持原 hash。当前结构清单为 34 位 Gray 指针、22 条标量同步链、7 条普通复位链及 28 个 core reset 二级副本；最终覆盖解析仍需完成，不能只凭查询退出码宣称全部物理路径通过。SRAM 计划需绑定补齐后的检查证据。本节仍不表示已经下载或实时相机已出图。

初版 release-interface-query-20261031-a 对 45 个端点分别调用报告；PDS 每次重新加载架构，耗时过长。已核对进程命令行后只终止该自有查询树，保留 native exit 1、248.854 秒的失败记录，没有输入漂移或原生错误。b 版改为 4 组报告，保留全部 45 个精确源/终点要求，并再次查询 128 个实际 IO site。不得将 a 版中断描述为设计失败或本轮 PDS 内存崩溃。

引脚/接口证据位于 distortion/results/camera-vga-io-analysis-20261031-a/io-evidence.json，SHA256 67bfe887cc9074ffd531d93da48567360fe6eab9561bc6ae856755f9ecdfe2c7。128 个端口的声明、原始构建位置、最终功能连接与最终原生 IO site 映射全部一致，含 71 个 DDR 存储信号、2 个 DDR 参考时钟端口及 14 个 CAM2 端口；摄像头 D5 为 AA23。

HDMI 初始化 49 项设置及 56 条最大延迟输出路径已核对，但未取得完整外部最小延迟/采样边沿/PCB skew 证据，TX 外部 AC 不签核。DVP 10 个数据/控制口在暂定输入预算下最小 setup +6.493ns、hold +0.022ns，仅为条件 STA，不能写成实测摄像头采样裕量。功能库导出出现 14 项 DRIVE、28 项 SLEW 参数与 FDC/PCF 声明不同；导出默认参数不能当作最终硬件电气配置，FinalNativeElectricalAttributesVerified 保持 false。当前是诊断试上板准备，不是外部 AC 或长期稳定性验收。

最终 CDC 证据位于 distortion/work/camera-vga-output/cdc-review-20261031-c/cdc-structure.json，SHA256 b3fd8f86c80e0c9b3713a79330de2b4e345ae38209de69112c0cb3c658ab929f。35 对精确端点的双角 setup/hold 共 140 项检查全部通过，最小 setup +5.796ns、hold +0.133ns；34 位 Gray 指针双角 68/68 覆盖，最大数据路径 1.092ns，均小于对应源时钟周期。NativeInterstageTimingComplete 与 GrayDatapathBoundComplete 均 true；模拟 MTBF、全设计 CDC 与硬件验收均未声称通过。还保留最终 primitive 的启动 clear LUT 和粘滞释放寄存器核对，不因运行故障撤销已释放的流水线复位。

## 下载计划与执行边界

单次计划位于 distortion/work/camera-vga-output/program-20261031-a/plan.json，SHA256 17b67e5afee9994c131c46bcd223134904505f4ee57a46f416cc0816d7fd0596，绑定上述位流、完整 CDC 和引脚证据。prepare 已完成，执行器默认离板模式重新验证 ValidationPassed=true、HardwareAccessed=false。下载器使用 1MHz，必须扫描 PG2L100H / 0x00602899，只写易失 SRAM、核对 DONE，不写 Flash。

离板重新验证命令（不访问硬件）：

```powershell
.venv/Scripts/python.exe -B distortion/tools/execute_camera_vga_program.py --plan distortion/work/camera-vga-output/program-20261031-a/plan.json
```

只有在用户收到上板通知并明确本次已上电后，才能在同一命令末尾追加 --execute --board-powered；旧对话中的上电反馈不能复用。当前尚未提供新的上电确认，禁止先行扫描 JTAG 或下载。

## 本轮封存与交接

145 项文件及 497 项本地依赖引用已封存并逐文件回读/解压校验通过：[归档清单](../distortion/results/camera-vga-ready-20261031-a/manifest.json)，SHA256 1b0dd54bacd04831021b6cb6fb8da39e274bc88d6db9ecb2cb9e874070befc8c。保存位流生成、完整 IO/CDC 证据、成功分组查询和首次中断查询；大型 ADF、位流及厂商网表保留本地哈希引用，归档不是独立可搬迁的完整构建包。文档使用封存时快照，本段归档指针为封存后补充。

9 个 README/交接/计划入口已同步当前候选状态，链接回读通过；没有 Git 提交或远端推送。自有 PDS/JTAG 进程均已退出。已向用户发出本次上电确认请求，尚未收到新确认；停在离板准备完成，HardwareAccessed=false，不把待执行计划当作实时相机成功。
