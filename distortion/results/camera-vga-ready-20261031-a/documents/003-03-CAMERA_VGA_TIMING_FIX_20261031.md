# 2026-10-31 摄像头候选 DDR 定向时序修复

> 2026-10-31 当前状态：摄像头候选位流已生成并核验，SHA256 acec0a65…b25e0；128个实际引脚、35对跨级端点/140项时序检查及34位Gray双角68项覆盖通过。单次SRAM计划已准备，开发板仍按断电处理；上板前先通知并等待新的上电确认。下一步观察中央640×480实时相机画面及LED5/6帧进度，默认零畸变系数先验证传输。外部AC/长期稳定性未验收；HDMI IN支线继续暂停。详见[摄像头位流与上板步骤](CAMERA_VGA_READY_20261031.md)。下文旧“无摄像头位流”“时序未通过”“物理检查待做”均为历史状态，不覆盖本条。

**本轮内部时序修复与独立审计已完成，开发板仍按断电处理。** 最终 ADF 为 daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f，位于 distortion/work/camera-vga-output/physical-final-report-20261031-a/input.adf。新进程重载 STA、单目标查询、实际功能导出均完成，所有输入校验无漂移。

[338文件证据归档](../distortion/results/camera-vga-physical-20261031-a/manifest.json)已逐文件回读/解压核验，另76项大型原生文件保留本地路径和hash引用；manifest SHA256 aa41d625afa8759121cacca7be7dcefa4f6909f5c685b5d2988e86868762c3be。14个原生阶段中4个失败原样保存，所有阶段输入漂移为空。归档内文档为封存时快照；本段归档链接为封存后补充。所有自有PDS进程已退出，未执行Git提交/推送、位流生成或硬件操作。

| 检查 | Slow最差(ns) | Fast最差(ns) | 每角剩余检查数 |
|---|---:|---:|---:|
| Setup | +0.238 | +2.939 | 55,450 |
| Hold | +0.045 | +0.016 | 54,143 |
| Recovery | +2.546 | +4.599 | 4,458 |
| Removal | +0.402 | +0.175 | 3,582 |
| Minimum pulse width | +0.035 | +0.035 | 14,829 |

十个原生内部检查表全部0失败。recovery/removal每角恰好移除当前证明中的245个检查，数据setup/hold false-path均0，其余检查数、时钟定义和负载不变。最终 [物理综合审计](../distortion/work/camera-vga-output/physical-comparison-20261031-a.json) SHA256为17d68f155e2c7585ccc45e14d9aad7c32ab4f8c25debe40578c660021996938f，AuditPassed和AllInternalChecksMet均true。

36,469个primitive的参数/连接、模块声明和17,417个FF的位置全部与原基线一致。33,562条实际路线中仅_N101/_N188/_N78改变，节点数分别8→27、14→32、8→22；所有其他路线和非约束语义相同。纯hold阶段CDB原文及token均完全相同，仅同父CDBENTRY记录排序规范化；复位阶段只新增132条约束pin引用、无删除。保存后再重载，全部路线及CDB又完全一致。

非false例外报告的最差路径选择会变化，不能用top-N原始文本不同就断言逻辑变化。已用双边union补齐14个换出/14个换入成员，严格比较31条路径；1条原布线记录出现1ps显示量化差异，1条_N78快角hold改选数据下降跳变，均逐项记录。后者只在精确身份、原语/连线/位置不变和完整原生STA的支持下接受代表变化，不声称同一数据边沿变体或只有网络延迟变化。旧拒绝和失败诊断保留，详见 [例外对照](../distortion/work/camera-vga-output/physical-final-report-20261031-a/exception-union-comparison.json)。

三网同源同终点setup/hold共12项均有准确原生记录。最终setup slow/fast：_N101 +3.212/+4.752、_N188 +3.747/+5.761、_N78 +3.074/+4.748ns；hold：+1.290/+0.599、+1.105/+0.016、+0.853/+0.407ns。最小hold裕量16ps需如实保留，不能外推板级裕量或长期稳定性。

**下一步核查本摄像头候选的实际引脚、CDC/外部接口和启动条件，再准备新位流与单次SRAM计划；上板前先通知并等待新的上电确认。** 当前没有摄像头候选位流、下载、UART访问或实时相机实物结果；HDMI IN排查继续暂停。旧RTL集成/控制仿真因源逻辑未变不重复。

以下为本轮原始基线、失败试验和修复过程；不覆盖顶部最终结果。

本轮承接 OV5640 CAM2 → DDR/处理 → HDMI 主线。开发板按用户最新要求保持断电；任何下载之前必须通知并收到新的上电确认。没有 UART、JTAG、位流或硬件操作，原始 RTL、DDR IP、FDC 和 routed ADF 不改。

## 原始基线与精确路径

基线位于 distortion/work/camera-vga-output/pds-20261031-a/place_route/camera_vga_output_top_pnr.adf，SHA256 为 32c8aa75c766425765b7cd20bbe26dbee9f9072a069d43a297de07b3e730be3b。所有工作在该工作根下的独立新副本中进行。

三条实际数据支路是 _N101（DDR读数据）、_N188（dll_update_n 同步器 D 输入）、_N78（DDR写数据），不可套用旧 _N107/_N173 名称或物理位置。完整报告加精确端点查询得到：

| 网络 | Hold slow/fast (ns) | 同源同端点 Setup slow/fast (ns) |
|---|---|---|
| _N101 | -0.169 / -0.342 | +5.205 / +6.029 |
| _N188 | -0.336 / -0.912 | +5.760 / +7.082 |
| _N78 | +0.190 / -0.059 | +4.191 / +5.387 |

_N188 是真实 sequential D 检查，不能使用 reset recovery 例外。_N78 的已有 multicycle setup -end 2 保留。同终点但不同源的 setup 不能替代准确匹配。

完整原生 route dump 解析 33,562 条路线、578,531 个物理节点，三目标都是单驱动单负载线性树；选择绕行锚点时检查全量占用及本机 wirepattern。原始功能导出包含 36,469 个 primitive、17,417 个 FF 位置。

## PDS 查询崩溃与规避

physical-reset-query-20261031-a 在 mpnr 加载之后的第一条 get_pins 查询处崩溃，Windows exit 为 3221225477 / 0xC0000005，用户看到“内存不能为 written”弹窗。该次没有完成标记，不作为通过证据；InputDrift 为空，原始和副本 ADF 均保持原 hash。

physical-reset-query-20261031-b 在新副本上先执行 mpnr_report_timing，再执行相同 10 条精确 get_pins 和三组端点时序查询，119.939 秒完成、exit 0、零输入漂移。由此观察到初始化顺序可绕过当前崩溃点，但尚未证明 PDS 内部错误的底层原因。后续 get_pins/set_false_path 必须先建立时序上下文，不能原样重跑失败调用。无需给开发板上电或重启电脑。

查询 b 的原生 names/count 确认 5 个源、127 个精确复位目标。当前报告重建每角 245 个逻辑 recovery、252 个原生变体，slow/fast 245/231 个失败。实际网表验证入口两个异步 clear FF 直接串联、首级只到后级 D、等价 clear 逻辑，以及 126 个内部端点连接。仅允许在原始 ADF 隔离副本应用精确复位范围；不导入全局 clock groups 或数据 false-path。证明位于 distortion/work/camera-vga-output/reset-proof-20261031-a/proof.json。

## 当前进展

三网绕行首次试验 physical-hold-20261031-a 因 _N188 的多锚点分隔语法被 DesignEditor-0029 拒绝；b 的连续多锚点也被 Route-0024 拒绝，两次均未 save，ADF 保持原始 hash。c 改单锚点后成功，但 _N188 快角 hold 仍 -0.161ns。失败与未闭合试验全部保留。

physical-hold-20261031-d 改用已核对空闲的单锚点 ZDNE[0]:SRB_258_360 → IDNE[0]:SRB_264_366；92.326秒完成、exit0，ADF为73391f865f6df1b03bb9627f92114a7fafa6ca7f8661c9252df4894c9c0c605c。所有数据 setup/hold 两角0失败；全局slow/fast setup +0.238/+2.939ns、hold +0.045/+0.016ns。最小正hold裕量仅16ps，属于当前确定性报告结果，不能外推为板级裕量或长期稳定性。复位失败仍保留，尚未整体闭合。

合并同一组三网绕行与精确复位约束的 physical-final-20261031-a 完成 save，但同一进程第二次 mpnr_report_timing 报错，整阶段记为失败，不据该结果放行。后续将保存修复和 fresh-process STA 拆开，仍从原始基线新副本重做，不把失败回执改成通过。

后续 physical-final-20261031-b 仅应用/保存完成；physical-final-report-20261031-a 在新进程完成完整STA和union查询，export-final-20261031-a 仅执行 Report Timing/Generate Netlist，physical-final-target-20261031-a 补齐单源写路径setup。最终审计结论以本文件顶部为准；所有14个阶段和其中4个原生失败都保留。正式接续入口仍为 [摄像头接入交接](CAMERA_VGA_INPUT_20261031.md)。
