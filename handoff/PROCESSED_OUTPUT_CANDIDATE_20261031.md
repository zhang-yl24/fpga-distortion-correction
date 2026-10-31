# 2026-10-31 独立处理与HDMI输出候选

**本候选现已完成首次实板试显。** SRAM下载成功、DONE=1，用户确认红十字和彩色网格显示，处理计数灯变化、故障灯熄灭；见[最新实板记录](PROCESSED_OUTPUT_LIVE_20261031.md)。下方“待上电/未下载/待试显”保留为开发阶段历史。本次为片内测试图，输入排查继续暂停。

**最新状态：诊断位流已生成并校验，用户已断电，待通知上电后试显。** 当前位流SHA256 `0537394b548eff5035be031e8056444bad50e20e76cd4b5d49046f477ed01c72`。有限CDC、3条级间路径和332条TX延迟已核对，外部AC仍未签核；SRAM计划已准备，尚无硬件访问。以[最新上板准备](PROCESSED_OUTPUT_READY_20261031.md)为接续入口，以下基线构建与修复记录保留原貌。

**后续状态更新：本候选的内部时序已定向修复。** 最终隔离ADF为 `1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b`，双角十类内部检查全部0失败，功能图和全部FF位置一致，仅 `_N107` 读取数据支路路线变化。见[修复交接](PROCESSED_OUTPUT_TIMING_FIX_20261031.md)。下方失败表保留原始a构建结果；其“下一项修复”已完成。外部输出AC/实际CDC及实板显示仍待核验，没有下载新位流。

按[当前方向](ACTIVE_DIRECTION_20261031.md)继续推进。摄像头仍接在板上，本轮暂停物理输入排查。新增独立候选使用片内受控图像经过真实DDR/矫正/读帧链后显示，用来验证处理结果上屏；它不是实时相机工程，也不是直接输出八色彩条。

## 实现

入口为 `distortion/board/processed_output_top.v`，模块 `processed_output_top`。源为可综合 `processed_output_pattern.v`，生成白色边框、红十字、绿色网格及带渐变的棋盘。数据路径为：

```text
27MHz片内受控RGB源 → 原有采集DMA/跨时钟FIFO/写仲裁 → 源DDR
→ 原有生产bank manager/rowpipe矫正 → 结果DDR
→ 读仲裁/读帧器/真实异步FIFO/扫描 → MS7210 HDMI OUT
```

复用 `hdmi1080_video_system_cdc_reset.v` 及现有rowpipe源闭包，未修改它们、DDR IP或共享约束。System内的数字采集DMA仅用于注入受控数据，不访问相机或HDMI IN。生产bank core当前固定Gamma旁路，不能描述为自适应Gamma已开启。

独立TX由原 `hdmi_tx_init.v` 直接用27MHz初始化；不实例化MS7200、输入观察器或10MHz cfg PLL，不包含HDMI输入管脚，也没有RX就绪门禁。SCL/SDA均为双向开漏接口。

默认处理1920×1080；输出复用74.25MHz PLL，2200×1125总时序，设计刷新30Hz。受控源使用27MHz，帧周期2200×1125，约10.91帧/秒；重复刷新由System计数，不能当成新增处理帧率。小尺寸参数用于定向数字验证，不能替代原生全尺寸或实物验收。

几何为合成Brown压力模型，native13项与既有 `board1080-synthetic.vh` 模型一致；小尺寸按尺寸缩放中心/焦距并将倒数四舍五入。不是当前镜头标定。

## 启动与故障

保留原2^20个27MHz周期的冷启动等待及已寄存power_ready；DDR/APB/debug连接与原rowpipe top除换行外一致。启动只等待DDR就绪、视频PLL锁定和TX配置完成，TX错误优先于同时到达的ready。

`pipeline_release` 一旦置位，仅共同手动/上电复位清除。运行故障锁存首个错误，停止新准入并交给System隔离/排空，保持共同FIFO和bank epoch，不能通过拉低本地reset撤销已发出的DDR事务。

本轮review修复一个新top接线缺陷：若故障后停掉源，下一次VS消失，原采集CDC不能结束最后一帧。因此pattern在pipeline共同复位释放后始终继续raster，故障只关闭新准入；生产采集模块未修改。

| 板层故障 | 含义 |
|---|---|
| A3 | DDR就绪状态丢失 |
| A4 | 视频PLL锁定状态丢失 |
| A5 | TX配置ready丢失 |
| A6 | System故障已同步到板层 |
| A7 | 独立TX初始化错误，启动前后均锁存 |

状态异常的逻辑处理不等于真实时钟停止或DDR PHY失效后仍可完成事务；后者没有新的恢复证明。候选没有主机正常停止接口。片内源disable只保证完整raster收尾；原采集CDC依赖下一VS关闭帧，测试中的正常排空需明确其台架停止方式，不能冒称现场停止API。

## 验证与构建状态

受控源单独数字验证已通过：64×32小尺寸3完整帧及部分帧，共6,496个像素；帧中disable收尾、重新enable、异步复位及两级释放通过。原生1920×1080单帧共2,073,600个像素及2200×1125逐拍时序通过，源RGB565 CRC为C58CBE14。两运行源码及夹具无漂移，使用原27MHz时间尺度。

32×16小尺寸的真实top/System集成已通过9次源commit/处理/发布及9个不同帧ID实际扫描，另14次重复刷新，共11,776像素与独立CPU参考逐点一致，源CRC6E5172F7、结果/扫描CRC511CD37A。源/结果bank各复用7次，正常台架定向停止后源reserve、输出lease、总线及真实FIFO完整排空，0欠载/CRC错误。图像内容静态，不同ID不代表不同场景。

4个启动条件（DDR/视频PLL/TX未就绪及TX错误优先）、5个运行故障A3–A7的首故障保持、共同复位不撤回、阻塞AW保持以及已发总线/末帧capture收尾通过。运行故障在首次源AW阶段注入，未新增验证持有显示lease时的故障隔离。正常排空通过测试台阻止新DMA grant并等待terminalVS，属于台架停止，不是候选新增主机停止接口。

最终运行 `build/processed-output-integration/top-20261031-g` 三阶段原生exit0，92.023秒；源码及夹具无漂移。报告SHA256为 `1aca06dde201fc17a1b37fad95660875d90b28c2566655fae762355e42cd4a86`。g准确记载 `runtime_fault_sticky_until_common_reset=true`、`active_display_lease_fault_tested=false`；旧f已通过但有过宽quarantine布尔，因此由g收窄替代，原件保留，`supersession.json`绑定两者及a–e失败。a为参考helper尺寸合同，b为测试台CRC函数，c为旧模拟器截止常量截断，d/e为测试台停止时NBA采样竞态；失败不改写为通过。

## 该候选自己的物理结果

唯一全流程 `build/processed-output/pds-20261031-a` 原生exit0，771.657秒，编译/综合/映射/布局布线及双角报告全部完成。111项输入和107份编译副本无漂移；STA前快照与最终 `_pnr.adf` SHA256相同：`97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980`。

流程完成不等于时序通过。原生双角结果如下，未增加复位例外或旧物理绕行：

| 检查 | slow最差(ns) / 失败数 | fast最差(ns) / 失败数 |
|---|---:|---:|
| setup | +0.286 / 0 | +2.924 / 0 |
| hold | −0.058 / 1 | −0.262 / 1 |
| recovery | −4.405 / 245 | −3.280 / 230 |
| removal | +0.311 / 0 | +0.158 / 0 |
| minimum pulse width | +0.035 / 0 | +0.035 / 0 |

新hold失败属于 `phy_dq_sysclk_1 → ddrphy_sysclk`，方向与旧 `_N173` 修复不同，必须查询本候选的实际端点和路线，不能照抄旧命令。复位恢复也须按新网表逐端点分类/核对准入；保留原失败，不以全局false path消除。

实际最差hold从 `i_dqs_group[1].ddrphy_data_slice/dq_loop[0].u_iobuf_dq/opit_1/ICLKDIV` 到 `ddrphy_dqs_rddata_align/rddata_r1[5]/opit_0_inv_srl/D`；完整层次名及两角记录见[原生审计](../distortion/results/processed-output-20261031/pds/native-audit-final-v2.json)。最终布线资源LUT13,917、FF18,600、DRM16.5、APM78、IO114；映射阶段LUT13,997是优化前值，分别保存。

候选约束从原rowpipe绑定FDC精确派生：删除28个物理输入脚及输入/cfg时钟，保留114个脚（含71个DDR脚）、原DDR电气和RCF，SCL修正为与真实TX接口一致的INOUT。新FDC独立保存，不改旧FDC。源码/IDF/include闭包用独立profile冻结，74个DDR展开体由IDF拥有，不重复add_design。

新候选的时序当前未通过；外部TX AC/板级skew及CDC物理也仍未签核。PDS忽略RTL `async_reg` 属性，不能据此声称同步器已实现要求的放置。没有生成或下载新位流，板上最后确认仍是旧合成彩条诊断，Flash未写。

## 下一项与复现入口

下一项只针对这个新候选的DDR hold实际端点/路线及复位恢复分类准备定向修复与验证，原始a保留，不重复无差异全流程，不回到输入调试。正式外部时序和实板显示仍按实际验收推进。

准备器为 `tools/prepare_processed_output.py`，独立manifest为 `board/processed-output-sources.json`。24项定向CPU测试通过；profile验证实际114脚、DDR IDF所有权、include唯一搬迁、hash漂移、路径逃逸/新目标独占等。当前 `run_processed_output_diagnostic.py` 执行合同只支持映射盘（本轮P:/）；准备器的direct选项尚不受执行器支持。执行器原生exit0只表示配方完成，始终不自动置TimingAccepted。

数字回归入口为 `tools/run_processed_output_pattern_sim.py` 和 `tools/run_processed_output_sim.py`；当前最终成功运行复用即可，相关源码修改后再补对应验证。完成证据使用 `tools/archive_processed_output_evidence.py` 封存到 `results/processed-output-20261031`，自有RTL可还原，厂商IP/生成PLL/大型ADF保留本地路径及哈希。

[本轮持久证据清单](../distortion/results/processed-output-20261031/manifest.json)已封存并逐文件回读/解压核验151项，清单SHA256 `3acafbfaf01b2f51452e05e4599c469468d7394ca49360ac0cb495f9fcada94c`。含两项pattern回归、最终g集成及精确像素、原生PDS回执/日志/十表/最终管脚与审计、完整自有源码快照和失败原路径绑定。`native-audit-final-v2.json` 是最终原生审计，旧中间audit原样保留。所有EDA进程已退出，无板卡/串口操作。
