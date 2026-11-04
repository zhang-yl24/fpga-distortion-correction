# F 双读信用：已验证前缀与组件的实验源码

本交付共享三个显式opt-in模块及已执行组件bench/模型，方便同学复核有序双请求的缓存填充与仲裁方法。它仍是实验候选，完整帧、组合故障/公平性、真实DDR多请求合同和实板60fps均未验收。没有重新运行或代跑被拒的测试、EDA或硬件。

## 已有证据与性能边界

8组已有真实xsim回执逐项核过当前输入哈希和原日志PASS标记：仲裁器8case、双缓冲store 8case、cache两种模型的328项查询/热命中II1、排队模型，以及三个131072像素原生前缀。所有相应Job已退出，早期失败回执保留；退出码0本身不代表功能PASS。

| 131072像素前缀 | 周期 | 实际最多接受的源读请求 |
|---|---:|---:|
| Q2_L32_A模型、legacy单信用 | 143032 | 1 |
| 同一Q2_L32_A模型、双信用 | 131986 | 2 |
| 原one-pending L32兼容控制、双信用 | 145017 | 1 |

同模型双信用减少11046周期，约7.72%；不能把不同模型行混作单变量比较。双信用前缀确实覆盖5次完成与分配同周期、两条cache lease。原日志虽然使用PASS_FULL_CAMERA_PILOT名称，但明确written_pixels=131072、done=0、full_frame=0，**不是2073600像素完整帧PASS**，也没有验证完整帧CRC。

前缀使用1920×1080预加载源图、64×16 macro、Q512、INDEX6、lookahead256，Gamma关闭且角度0°，仅有有限capture/scan代理，没有真实HDMI输入、扫描或E2E。不能与E2的另一组运行时角度/Gamma小帧证据拼接成F组合场景已通过。这里不外推全帧fps、延迟或16.667ms截止时间。

Q2_L32_A是明确另命名的实验排队模型：32周期读启动延迟、有序返回、共享数据总线。它不是实测DDR延迟，也不证明实际Pango IP能接受两个未完成读请求。[S-c探针](../../../diagnostics/ddr-service-probe/20261104-sc/README.md)仍为single outstanding，同样不能补足这一证据。

## 源码身份与静态提取

三个模块是ddr_read_arbiter、quad_parity_prefetch_store、d256_runtime_prefetch_cache。宏EXPERIMENTAL_DUAL_READ_CREDIT默认未定义，保留legacy逻辑；仅显式启用才选择双读。没有改动同学main或O/P、E2冻结源码。

F原生151项输入哈希逐项匹配，三个实验分支主体字节与已Map的F实际源一致，其余输入仅机械include根路径变化。注意：作者的opt_off_raw_byte_exact标志对直接提取else分支不精确，三个else分支各比E2原件多一个末尾LF；除该LF外逐字节一致。交付保留原作者源，记录真实SHA，legacy静态提取时明确去掉这一个额外LF并校验基线SHA。

~~~text
python -B verify_delivery.py
python -B extract_sources.py --output <全新目录>
python -B extract_sources.py --output <另一个全新目录> --mode experimental
~~~
工具只提取三个现有模块的最外层分支，保留所有内层条件指令。默认legacy；experimental输出与F原生激活主体哈希一致。它不生成testbench或PDS工程，不编译、仿真或访问设备，也不替代其它设计依赖及许可获取。

提供已执行的4份组件bench、双请求模型及适配器供审查。原生前缀bench、独立golden/vectors和完整帧/组合fault/fairness驱动不在本包；VERIFIED_EVIDENCE记录实际输入与fixture哈希，没有上传相机数据、位图或大向量。

## 物理证据范围

2026-11-04 04:26（北京时间）补齐F自己的最终ADF、独立STA和修正后的时钟叶节点审计。交付工程师核验151项输入不变，重新解析实际F独立报告的两角12张内部汇总表；不引用E2的时序作为F结果。Map资源FF27919、LUT32611、DRM28.5、APM68、IO144，相比E2增加140FF和190.5LUT。原有43个GTP_RAM32X2X4填充缓冲原语使用深度8→16，实际读写slot选择已在主工程Map审查中确认；未新增DRM/APM。具体资源、源清单及诊断PNR快照见SUMMARY/PROVENANCE。

F原生清单SHA：eb7e4169f5d8541b128c07d3b30c2a22cc421bca03f4a6ec00481caa41739f94。
| F内部检查 | slow裕量 ns | fast裕量 ns | 两角失败端点 |
|---|---:|---:|---:|
| setup | +0.022 | +2.596 | 0 |
| hold | +0.060 | +0.044 | 0 |
| recovery | +0.783 | +3.471 | 0 |
| removal | +0.353 | +0.240 | 0 |
| 最小脉宽 | +0.035 | +0.035 | 0 |
| skew | +0.223 | +0.240 | 0 |

最终ADF SHA为ccbc98f7affb0806eb7e5d2d05ec48022565613277119ed90615d3cbdebc082c；独立报告SHA为b19d813ebb293fe4a3a55bbda3a60bc8011898b038911e590ac05bef5103dc33。只发布哈希及去标识表，不上传ADF或厂商报告原件。

这是当前模型下的内部检查，slow setup仅22ps。沿用三个DDR单组asynchronous声明及原8/0ns规则，模型把每个单组时钟与组外时钟（含派生时钟）视作异步；实际叶节点仅在DDR IP内的审查不能替代物理门控/复位或完整CDC证明。仍有55项输入、111项输出缺少外部delay。

原PNR运行中快照属于较早时点，SUMMARY单独保留，并新增final_internal_physical_milestone。最初时钟审计曾继承错误根路径并报缺文件；原失败回执与哈希保留，随后在F实际目录修正审计，没有重跑原生实现。

**诊断bit仅本地封存，未经上板或完整功能验收。** 2026-11-04 04:30封存的bit SHA为435f37eae899b8b9ed100119c4f3a6f537e20190247851536377aa5976610cd1，3791112字节，只发布哈希，原件不上传。它不是功能发布。 内部时序通过不能替代完整帧、组合特性/故障/公平性、外部IO/复位/CDC和真实DDR多请求支持验证；也不证明实板60fps或帧延迟。所有前述功能限制继续有效。
