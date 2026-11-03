# 09:55 请求后重新核对：stable30 e89a2d42

本轮重新读取了最新分支、main提交列表及开放PR。核对起点为2026-11-03 01:56:51 UTC（北京时间09:56:51）：main仍是8adda884（00:15:51 UTC），旧throughput分支仍是bdaf8c1；新增的是 **codex/hdmi1080-stable30@e89a2d42c21e6a216df00e4f0fdeb7c94439ba89**，提交时间00:57:53 UTC/北京时间08:57:53，父提交bdaf8c1，PR #23以throughput为base。它不是旧工程包入口更新。

[固定新源码](https://github.com/zhang-yl24/fpga-distortion-correction/tree/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89/delivery/20261103-hdmi1080-stable30) · [PR #23](https://github.com/zhang-yl24/fpga-distortion-correction/pull/23)

## 新变化与身份

- 三源槽0/1/4替代两源槽，结果槽仍2/3，额外4MiB外部DDR；DMA描述符排队、CDC/DMA/link/system/bank共五处调度源码联动，不能只改bank常数。
- cache在两项FIFO入队时预计算四邻点线性地址和bounds，切断head选择→有符号坐标运算→tag/valid索引组合路径，没有新增查询拍。是FIFO预解码，不是此前独立CHECK失效实验。
- writer增加256bit发送寄存；DDR返回的data/valid/last/ID整组增加一拍，包含原始时刻所有权检查，违规返回fault40、重叠AR fault41进入sticky quarantine。
- 新增匹配DDR IP的三条时钟关系FDC与两条优先布线RCF，源码闭包从130变为132项，仍有原80项依赖。参数ID **8c73465e**，完整identity **8c73465ec4d368f9d80f1abf0309c171d84b6c17559bfb606a585ac48ea1e5e2**。
- 诊断bit声明SHA256 **f77c4991ef485466971fc9145d173769c1dcda3839665d72abfc4bc6288adeb4**；routed ADF **0c6615b2dd9b83ee032e47c0bf990865d31ef9ba6baea68547099370e8981249**。本任务核对回执身份，没有下载/烧录bit或运行EDA。

## 新证据及范围

| 项目 | 本次上游记录 |
|---|---|
| 原生内部时序 | Slow/Fast setup、hold、recovery、removal、skew、MPW共12类零违例；最小setup **+0.009ns** |
| 资源 | FF27184、LUT18782.5、DRM19.5、APM69、IO144；比旧both增加766FF、490LUT，未降低资源 |
| 完整1080p处理模型 | 2073600像素与mask一致，CRC4be2b2a6、输出SHA0af8395d…；**2831328周期/22.650624ms @ nominal125MHz，约44.15模型fps** |
| 与旧both比较 | 原2814828周期；新多16500周期/0.132ms，约0.586%，时序隔离换取少量额外模型耗时 |
| 调度对照 | 30案例；受控不利相位下两槽240输入/180新显示，三槽240/240；处理时间为受控模型 |
| 真实小帧整机RTL | **32×16、8/8唯一输出、4096扫描像素**，真实处理模块、DDR UI模型，第三源槽重复写读、故障/复位恢复通过；不是完整1080p采集显示60fps |
| 实板与最终签核 | **未板测**；physical_timing_accepted、external_io_timing_accepted、cdc_protocol_and_reset_signoff均false；标签DIAGNOSTIC_NOT_TIMING_SIGNOFF |

新引擎模型未包含采集/显示共享DDR仲裁；既有完整1080p逐像素正确性不等于长时间整机吞吐。三槽可能减少相位丢帧，也可能增加排队延迟，实际新帧率和延迟需同条件测量。不能把它称为1080p60校正完成，亦不能把其内部零违例成绩贴到我们的D256/slowAB上。

## 约束审查的实质

FDC只恢复厂商rst_clk、phy_dq_clk_0/1三条单独异步组，未复制free/ref组，也未增加自拟false_path。其单组语义会豁免涉及该域的跨时钟检查，不能称所有恢复检查均由RTL流水化消除。

上游最终审计回执33项通过：匹配HMIC_S1.10/371参数及原生IP哈希；三域叶节点全在DDR IP中，用户负载0；五个用户域之间20个有向8ns max/0ns min约束保留；core↔divided PHY仍Timed，multicycle2和0.4ns不确定度保留。RCF两网实际prior_route成功。最小+0.009ns处于core↔PHY，不能再扩大例外掩盖该数据路径。

同ADF“省略附加FDC”的诊断仍继承三组，去组审计明确FAIL；这不是已成功完成去组A/B。加密复位同步器级数未独立证明，冷启动、复位与DDR长期稳定性及HDMI外部AC/CDC签核仍开放。移植前要核对我们候选的同版本IP、实例名、全部时钟端点及实际导入，不能直接复制三组宣称全工程签核。

## 给主工程师的可吸收范围

1. **优先核对DDR RCF与精确IP约束集成**。此项有实际路由与端点审计价值；在独立候选验证，不改变已板显slowAB，也不能省略用户/PHY真实数据检查。
2. **优先评估带原始owner guard的DDR返回寄存**。模块35行，data/valid/last/ID必须同拍，fault40/41接入现有sticky故障并共同复位；只延迟data或valid会改变无主返回与下一AR的语义。新增一拍/可能增加burst周转，需重跑完整D256周期、CRC、lease及背压/错误测试。
3. **FIFO预解码与writer寄存要先避免重复**。我们的HEAD_PREDECODE1已有同类入队/解码前移思路，但D256 runtime cache协议不同，不能整块覆盖。已核本机HEAD的RAM_BUFFER1 writer：16 lane同步RAM的read_pixel已注册，按read_first/read_next预取且停顿保持，不能再机械叠加256bit寄存或回退为旧FF双缓冲。
4. **第三源槽单独做调度实验**。它修复30Hz模型相位阻塞，不加速核心到60；涉及bank宽度、DDR地址、描述符与所有权，必须检查0/1/4与2/3不重叠、实际容量及完整新帧序列。源帧仍在引擎完成后释放，不自动提供同源raw/校正严格A/B；低延迟目标还需比较排队/丢旧帧策略。

slowAB保留bit2793ab0b…的已板显29.97Hz慢切换；原D256连续三帧60预算RTL结论仍来自主集成回报，key/HEAD是不同139项源码与尚未收敛的物理候选。新stable30没有替代这些身份，也没有新摄像头标定、动态旋转/Gamma、E2E或竞赛已提交证明。

## 本任务实际复核与磁盘

已在用户指定 **D盘 git-review-20261103** 创建只读稀疏克隆，仅取新stable30及其自有冻结基线，未拉厂商工作树、大ZIP、位流或构建。HEAD精确e89a2d42；本地226个Git blob字节核对，225个封存文件通过，132项输入与四阶段回执身份通过，**12项标准库绑定/反例测试实际重跑全过**。没有重跑HDL、EDA或访问板卡。

上游同SHA的stable30、throughput、delivery、reference CI均通过。本独立交付只增补复核说明，不写main、强推、批准PR或合并生产源码。

本分任务既有C盘review目录统计为10645697字节（约10.15MiB，729文件）；这只是本分任务目录，不是整机C盘占用归因。本轮新副本、临时测试与交付说明均在D盘；既有C盘数据没有自行删除或移动。一次大终端传输被自动审查以内容过大拒绝、执行前未写文件，随后改用获准的明确目标稀疏拉取，记录保留。
