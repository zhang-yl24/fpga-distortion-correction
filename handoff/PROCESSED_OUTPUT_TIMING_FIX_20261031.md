# 2026-10-31 独立处理/输出候选的 DDR 定向时序修复

本轮按用户“继续”推进测试图→DDR矫正→HDMI输出，物理输入排查继续暂停，摄像头仍连接。没有修改生产RTL、DDR IP、原候选FDC或原始布局布线数据库；没有生成位流、下载板卡或访问UART。

## 修复结果

候选原始ADF为 `97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980`。隔离修复最终ADF为 `1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b`，位于 `distortion/build/processed-output/physical-final-report-20261031-a/input.adf`，STA前快照与它逐字节相同。新进程重载后双角十类内部时序全部零失败：

| 检查 | slow最差(ns) | fast最差(ns) | 每角保留检查数 |
| --- | ---: | ---: | ---: |
| setup | +0.286 | +2.924 | 58,129 |
| hold | +0.136 | +0.099 | 56,828 |
| recovery | +1.751 | +4.039 | 4,475 |
| removal | +0.311 | +0.158 | 4,011 |
| minimum pulse width | +0.035 | +0.035 | 15,992 |

这些结果只覆盖本候选报告中的内部检查。外部HDMI输出AC、跨时钟实际布线及板上DDR训练/处理图显示继续按各自证据验收，不能把内部零失败写成已上板。

## 真实数据 hold 修复

本次端点属于 `phy_dq_sysclk_1 → ddrphy_sysclk`，与旧工程 `_N173` 写路径不同。实际读路径为：

```text
group1 dq_loop[0]/opit_1/RX_DATA[5]
→ CLKROUTE_71 / CLMA_345_852/CR2
→ _N107
→ CLMS_339_847/M3
→ ddrphy_dqs_rddata_align/rddata_r1[5]/opit_0_inv_srl/D
```

仅拆接 `_N107:M3:CLMS_339_847` 分支，使用本机器件模型支持的 `ZDNE[1]:SRB_342_816 → IDNE[1]:SRB_348_822` 作为路由锚点，其他连接由原生工具完成。两端物理位置及逻辑端点保持，路径由8个物理pin变成24个。没有修改时钟、不确定度、多周期或数据检查。

该具体端点的slow/fast hold由−0.058/−0.262ns提升为+0.760/+0.299ns；相应setup由+5.093/+5.952ns变为+3.822/+5.156ns，均保留正裕量。上表的全局最差hold来自其他端点，不能混为同一个数值。

`physical-hold-report-20261031-c` 单独验证过仅数据绕行：全部其他时序汇总行与原基线相同，复位失败也按原样保留。之后才在新副本合并精确复位约束。

## 复位约束依据及范围

当前候选的IDF与74个展开IP源和本机同配置原厂例程逐字节一致。原厂约束声明复位/PHY相关时钟异步；本轮没有导入全局clock groups，而是完整提取新报告中的实际复位路径。

每角251条原生变体对应244个内部检查，来自4组复位源：dqs104、iol14、training7、CPD1个目标。slow内部244失败，fast229失败及15非负；另有独立入口1项。旧工具中fast11非负的历史假设没有套用。原生 `get_pins` 查询严格匹配5个源和127个目标，10条查询均有实际对象名记录。

本候选的实际功能网表验证两级入口异步clear同步器、CE常1、FF1仅驱动FF2、输出取FF2、LOCK无反馈。新布局产生两份逻辑等价的clear LUT和18个缓冲，逐一验证其函数为 `~(reset_n & power_ready)`；入口输出10个负载，四组126个内部功能复位目标均直接连接对应实际源。旧入口审计器假设单LUT/11负载，首次拒绝被保留，使用新候选专用审计器核对完整实际结构。

应用5条精确source-clock-pin→reset-pin约束后，每角recovery和removal恰好各减少245项；setup和hold检查数量不变。完整例外集合及其他既有例外另由最终审计核对。原始失败报告不覆盖、不改成通过。

## 执行与失败记录

全部原生阶段由新 `run_processed_output_physical.py` / `run_processed_output_export.py` 限时运行，只操作独立ADF副本，源闭包111项与编译副本107项始终绑定。工作目录均位于 `distortion/build/processed-output/`：

| 目录 | 真实结果 |
| --- | --- |
| physical-query-20261031-a | 原路线和完整双角报告完成；末尾dummy工程导出被Flow-0044拒绝，整阶段记录为失败 |
| physical-hold-20261031-a / b | channel0锚点被其他网占用，Route-0027失败，未保存修改 |
| export-baseline-20261031-a | 原始候选功能网表导出通过，只执行Report Timing与Generate Netlist |
| physical-reset-query-20261031-a | 5组复位精确对象只读查询通过 |
| physical-route-query-20261031-a | 原基线完整route ADIF只读导出通过 |
| physical-hold-20261031-c | channel1绕行成功并保存，ADF为9781d3c3…52870d |
| physical-hold-report-20261031-c | 新进程重载，仅hold修复验证通过，复位失败保留 |
| physical-final-20261031-a | 在hold修复副本上加入5条精确复位约束并保存 |
| physical-final-report-20261031-a | 新进程重载，双角十类内部检查全部零失败，导出实际完整路线 |
| export-final-20261031-a | 最终候选功能网表导出通过，无额外综合/布局布线 |

原生查询报告中的false-path无穷裕量使用GBK字节 `A1 DE`，最终审计按严格GB18030解码保留其含义。不能以忽略解码错误的方式跳过检查。

## 复现与接续

[163项持久证据](../distortion/results/processed-output-physical-20261031/manifest.json)已完成逐文件回读/解压核验，manifest SHA256为 `0957abf4a93067a96d844d34d46fa7744ea214fcb3cba5d8131f7dc8fbf74b28`。26项本地引用保留原始/最终ADF、含厂商逻辑的功能导出与大型route数据库路径及哈希，不复制其正文。

最终[时序/功能网表审计压缩副本](../distortion/results/processed-output-physical-20261031/comparison/physical-comparison-20261031-a.json.gz) 解压后SHA256 `a2748a74291c296689845720aa54d9a513bf8520189466e9c4b76caefa1b871d`：38,007单元全部参数/连接及模块声明一致，18,600个FF位置/属性一致。每角recovery/removal各245个独立检查、252种时钟边沿身份、490条原生变体准确匹配；setup/hold false-path为0，其他全部时序例外路径与延迟不变。

[完整路线对照](../distortion/results/processed-output-physical-20261031/stages/physical-final-report-20261031-a/route-comparison.json) SHA256 `145ae163525ed15c6173412891a0574c9029a4abe385fbed436e22f0d725d7d8`：35,847条NETANNOTATE中仅 `_N107` 改变，其他路线以及功能、库、放置语义完全一致。对照明确排除并记录时间戳、源码路径/行号及CDB约束引用元数据；这些约束的身份及效果由上述查询/时序审计单独验证。

27项定向CPU测试通过（21项准备/查询、6项真实网表变异），旧入口结构假设拒绝和原生占用失败均保留。原9帧数字回归因生产RTL未变直接复用，没有无因重跑。所有EDA进程已退出，本轮临时P盘映射已清理。

本轮准备器、查询器、实际Tcl、结果、失败记录、精确约束清单及审计均保留。原始候选的[151项证据](../distortion/results/processed-output-20261031/manifest.json)不变。修复是对该确切ADF的隔离派生：重新综合/布局布线后必须重新识别网络和端点，不能直接套用 `_N107` 或本次物理位置。

本记录后的离板工作已完成位流生成、有限CDC/级间路径核验与332条TX原生延迟分析，见[最新上板准备](PROCESSED_OUTPUT_READY_20261031.md)。用户已将开发板断电，旧SRAM配置丢失；下一项通知上电并按确切SRAM计划验证处理图。外部AC仍未签核，摄像头采集和HDMI IN排查继续暂停。
