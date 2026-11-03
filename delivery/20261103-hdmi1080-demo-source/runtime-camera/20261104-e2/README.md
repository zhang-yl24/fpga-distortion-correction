# E2：运行时旋转与自适应 Gamma 诊断候选的内部时序里程碑

2026-11-04 02:44（北京时间）封存。独立 STA 对最终布线 ADF 的两角共12项内部检查全部零违例，诊断 bit 已在本地封存，**未经上板**。结论限于下述时钟模型；外部IO、物理复位、完整CDC/MTBF与1080p60性能仍待签核。不要据工具的 All Constraints Met 文本宣布整机验收。

## 版本与可复用变化

这版在[上一份离板源码候选](../20261104-a/README.md)基础上，只为现有同步寄存器声明增加Pango属性：
~~~verilog
(* async_reg="true", PAP_ASYNC_REG=1 *) reg [1:0] core_reset=0,qualified_core=0,board_failed_core=0;
~~~
151项原生输入哈希逐项匹配冻结清单；E→E2除include根路径外，唯一代码差异就是这条声明属性，没有新寄存器、逻辑表达式或周期变化。SOURCE_DELTA.patch可直接审查。物理流程同时使用单个合并RCF保留两个官方门控优先级并加入CA优先级，布线也重新执行，因此不把时序结果归因为单一属性的性能提升。

共享导出的CAMERA_RUNTIME_GAMMA继续默认0；E2独立原生构建明确为1，选择HDMI_FISHEYE_PROFILE=2、自适应Gamma与SGR1运行时旋转。完整相机标定ID仍ed59f83e3cfbc77b，静态基参数ID708006b9。Gamma需编译启用，没有UART Gamma命令；SGR1只配置旋转。

只新增一项项目顶层源码，其余68项项目输入复用已冻结交付；82项依赖只列精确哈希，原件未发布。E2原生清单SHA：
5b8bade298b8fdd8dc5ba24277f7b78841d0e484f1173fa8e7173b6175daea2d

## 独立 STA 证据

| 检查 | slow最小裕量 ns | fast最小裕量 ns | 两角失败端点 |
|---|---:|---:|---:|
| setup | +0.016 | +2.537 | 0 |
| hold | +0.054 | +0.044 | 0 |
| recovery | +0.597 | +3.277 | 0 |
| removal | +0.354 | +0.250 | 0 |
| 最小脉宽 | +0.035 | +0.035 | 0 |
| skew | +0.223 | +0.240 | 0 |

交付工程师从实际独立STA报告重新解析12张汇总表，逐项匹配主工程审计。STA_TABLES.json保留去标识后的时钟对、端点计数与裕量；原始27MB报告不上传。slow setup只有16ps余量，后续任何源码、约束或布局变化都必须重新完成物理验证。

最终ADF SHA为3eb22f1481e0a768676d76641ecea94b48a8def5df65314139102d848a5fdeb5。
本地诊断bit SHA为4cce7396779c78ef5879f3f3b9c2c5e2ff4a762f05d251006bc82b189465e5df，3791112字节。发布仅给哈希，不上传ADF、bit或厂商生成物。Map、PNR、独立STA、bitgen阶段各退出0，所属Job均已结束；早期阶段回执中的pending是当时时点状态，不改写历史。

## 资源与约束范围

以下为本E2候选的Map统计；百分比按Used/Available计算，保留两位：
| 资源 | 使用/可用 | 占比 |
|---|---:|---:|
| FF | 27779/133200 | 20.86% |
| LUT | 32420.5/66600 | 48.68% |
| DRM | 28.5/155 | 18.39% |
| APM | 68/240 | 28.33% |
| IO | 144/300 | 48.00% |

模型core为125MHz、输出像素148.5MHz、输入包络150.2MHz；这些是STA时钟约束，不是已测输入或新增校正帧率。Map资源计数不能直接替代最终布局利用率或其它bit的资源统计。

约束身份、输入PCF、RCF和原始审计哈希见CONSTRAINT_REVIEW与PROVENANCE。原有三个单组asynchronous声明为rst_clk、phy_dq_clk_0、phy_dq_clk_1；每个单组将该时钟与组外时钟视作异步，包含派生时钟关系。主工程叶节点归属审查确认这些组的直接负载仅在DDR IP内，用户core仍保有IP外负载。该来源匹配和内部检查通过不证明硅片门控或物理复位安全。

E→E2原生时钟约束逐字节相同，没有新false path或放宽周期预算；board27→core的held-bundle规则仍是8ns max/0ns min。PNR/STA/bitgen中单个RCF只注册一次，实际路由日志确认官方gate0、gate1和CA三个优先项全部接受，避免后注册文件清掉门控优先级。

**尚有55项输入、111项输出没有外部delay；新增CDC、物理复位、完整外部IO及MTBF均未签核。PAP属性与8/0ns规则不能替代这些验收。**

## 离线源码重建与验收边界

~~~text
python -B verify_delivery.py
python -B prepare_sources.py --dependencies <合法native依赖根目录> --output <全新目录>
python -B prepare_sources.py --dependencies <合法native依赖根目录> --output <另一个全新目录> --enable-runtime
~~~
准备脚本只重建151项普通源码，默认开关0；显式启用后开关1，与本地原生E2身份仅差机械include路径。它不生成完整PDS项目，不编译、仿真、调用PDS或打开串口；准备出来的代码仍需自身物理验证。

功能证据沿用上一候选的128×32真实摄像头ROM/Q512/macro16/DDR短测：零角Gamma关闭4096像素配对一致，6帧24576像素及默认OFF/ON系统展开通过。E2仅属性修订；交付工程师没有重新执行HDL/EDA/硬件。

本候选尚未验证真实UART波形、HDMI扫描、完整1080运行时吞吐、新帧率、延迟分布或外部E2E；不能宣称60个新校正帧/s。O/P稳定版及golden保持原身份，不因E2内部时序里程碑自动替换。后续先完成模型/IO/复位审查，再单独安排安全上板与性能、视觉验收。
