# 11月3日上午合并进展：源码、验证与实板计数

本次合并交付RX framing短测、RX原生Map、INDEX6单帧完整引擎，以及冻结PGSTAT02位流的实板计数结果。每项单独绑定身份，没有将模型、Map、板测拼成同一版成绩；GitHub交付不代表竞赛已经提交。

## 明确区分四项成果

| 身份 | 当前结果 | 边界 |
|---|---|---|
| 冻结纯校正PGSTAT02 bit57044fe8… | 20.033093928 nominal秒内468次新校正完成/新呈现，23.361344fps；133次重复，成功非空扫描重复占22.13% | fixed mode1/Gamma OFF；实际125MHz未独立测量；descriptor不等于全部HDMI到达帧，drop0不等于无输入丢帧 |
| 同位流内部耗时 | 两个last-completion样本31.155160/31.260184ms | 只有一个新样本在统计窗内，覆盖468次完成的约0.214%；不是全帧分布、曝光到显示E2E或物理光子时刻 |
| RX framing修复 | 真实UART连续包、双向嵌magic、CRC/schema拒绝、截包/复位、物理RX错误和disabled alias共5类标记通过；新135源Map退出0且结构审查无stop reason | 仅SGA1/SGT1 framing；不改变原CRC/schema校验。Map资源FF24016/LUT18597/DRM19.5/APM69/IO144；不是PNR/STA/bit/板测通过 |
| INDEX6完整engine | 1920×1080单个预装源，2073600输出像素、8294400 raw-neighbor像素核验；2073957周期，nominal125MHz下16.591656ms | INDEX7→6相对HEAD1/LOCAL_MASK1/AREA2/KEY2/writerRAM1；不是连续摄像头60、采集/显示共享DDR仲裁、实板60或已测资源下降 |

## RX源码与短测修正

新router与wrapper精确SHA见rx/NATIVE_MAP_SUMMARY.json，分别为85be43f0…、1b7b77e7…，已核与D盘native135输入一致。router分派完整四字节magic及其固定24B报文，不在payload重新搜索另一magic；原解析器仍验证CRC/schema。STATS_ENABLE=0仍是原始三线alias；不包含全帧snapshot协议。

此前失败短测的watchdog字面量在XSim2017.4截为1215752192ps。只改成显式64位、保持原100ms，并将主机simulate预算30→180s；RTL、激励、断言未放宽。最终短测compile/elaborate/simulate均退出0。rx/COMPATIBILITY_BINDING.json记录差异，旧失败与审查记录仍在本机，没有上传私聊/审批原文。

rx/MANIFEST.json是24文件交付子集清单，明确标为derived，不伪装原28项清单；run_short.py仅把原机器安装路径改为必填FPGA_VIVADO_BIN环境变量；这一安装路径包装未复跑HDL，原执行脚本SHA保留。此交付没有重新执行HDL。核心路径不因RX修复获得新的帧率、时序或显示验收。

## INDEX6的容量与证据

已核作者147项证据哈希和50项自有源文件；本交付保留50项精确源码、两个INDEX6 patch、bench、执行回执与实际process/raw audit CSV。证据ZIP357705B、SHA aaea25cf49c09189484a886c40af60aa52ef4852118feec7fb4f3919be092a06只留本机，不上传ZIP或大.mem fixture。完整fixture/replay依据仍是原作者plan，当前是源码与证据子集，未宣称一键完整重建包。

实际miss/AR/fill为18268，R146144，scatter584576，符合独立CPU18268。旧16200 advisory不匹配的事实保留，未用理论值覆盖实测。AW8100、W129600，原始背压不变，writer输入stall0、coordinate stall1。实际单帧nominal60预算余量约9376周期/75.01微秒，很小；没有匹配当前INDEX7的全帧A/B，不可据旧历史HEAD宣布零代价或连续60。

INDEX6没有新的Map/PNR资源和路由结论。本轮未把正在开展的其他连续测试自动提升为通过。

## 实板计数复核

板测已终态FINISHED_GOLDEN_REST，完成后恢复指定golden休息位流；它不是RX新候选或INDEX6上板。独立离线重放已发布固定哈希v1 parser，对原始77248B UART及原文件字节绑定重新解析通过，605包。原始UART与位流不上传，仅给SHA及派生计数说明。

board/VALIDATED_COUNTER_SUMMARY.json保留源语义：source descriptors只数已准入完整描述符；presented是成功新ID显示lease，不是光子。实际场景/PCLK没有独立重采，不能据此完成新镜头标定或摄像头光学唯一FPS验收。端到端延迟仍未测；OT1状态异常/正式热签核仍开放。源profile旧build_status字段为离板历史状态，今晨执行证据另列，不改写原报告。

## stable30厂商异步组审查边界

同学e89a2d42的内部12类零违例、setup+0.009ns仍只属于它的132项候选。三条single-group异步关系会排除涉及rst_clk/fast PHY的跨域检查；不能写成所有recovery/removal由流水线消除，也不能整组豁免用户core。

移植必须验证匹配HMIC_S1.10/371参数、源hash/实例层级、所有叶端点IP归属、RCF实际导入、保留20个用户域方向max8/min0及core↔divided PHY的multicycle2和0.4ns不确定度。加密同步器级数不能猜。其“同ADF省略附加FDC”诊断仍继承组、去组审查FAIL，不是成功去组A/B。这里没有接收独立约束终审的正式通过结果，不替该审查签字。外部IO/CDC/复位、冷启动/长期DDR和物理60仍待分别验收。

## D盘工作空间约定

新main控制/构建/硬件证据位于distortion/output/workspaces/main；性能候选位于performance，验证回放位于verification，本分任务只读克隆和说明位于output/project/git-review-20261103。新大文件、临时测试与构建显式指向各自D盘目录，保持英文短路径并检查EDA路径限制；仅使用进程级临时目录参数，不全局改TEMP。旧C盘数据由迁移责任人校验后处理，不自动删除、移动或强停正在运行作业。

本增量只发布自有源码、小证据和说明；没有上传厂商受限原件、许可/密钥、QQ私聊/录屏、大构建、位流或原始图像。

## 分享前去标识及额外板测来源核对

RX结果/兼容性文件是明确标识的派生摘要，去除了原机绝对路径及审批过程字段；INDEX6日志只保留原输出中的功能标记行。原文件SHA保留在SOURCE_PROVENANCE，未将派生文件冒充执行原件。源码RTL/bench不改。未传播用户目录、机器安装位置、私聊或原始UART。

同时核对性能工作区的REPORT.md和SUMMARY.json原件SHA，确认605包、23.361344 nominal fps及两条稀疏样本一致。实际发送为SGA1一次、SGT1两次，journal的intent/drained不是两倍命令。最高实测温度约45摄氏度，回golden约31摄氏度；OT1异常及正式热签核仍开放。
