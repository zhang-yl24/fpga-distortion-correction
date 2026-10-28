# DDR recovery 归因：已有官方证据与下一步

日期：2026-10-28。CPU 审计和本机 PDS 2023.2 官方示例独立重构建均已完成；新构建运行到最终 STA，未生成位流或操作开发板。该跨版本对照不替代队友机器上的最新 1080P 候选报告。

## 自己生成报告是否需要上板

不需要。这里要的是综合、器件映射和布局布线完成后，对最终数据库执行的静态时序分析（STA）。普通 RTL 功能仿真不包含实际布线延迟，不能代替最终 STA；板卡、下载器及摄像头均不参与生成。

若要复现当前 245 项 recovery，应使用队友实际失败的同一份源清单、顶层、器件/速度等级、FDC/RCF 和工具/IP 版本，在独立输出目录运行综合 → 器件映射 → 布局布线 → Report Timing（slow/fast、min/max）。保留最终 ADF、`.rtr`、原生 XML `rtr.db`、全部执行日志及实际加载约束，并记录输入和最终 ADF 的 SHA256。已有最终数据库且工具兼容时，可以直接对它重新 STA，免去重新综合和布线。

本机使用 PDS 2023.2-SP3 build 154097；原项目/IP 生成与历史报告使用 PDS 2022.2-SP6.4 build 146967。因此本机新跑只作跨版本独立诊断，不能与原版本数据混为一轮，也不能凭生成了报告就宣称完整时序或实板验证通过。

本轮独立运行目录为 `distortion/build/ddr-reference-sta-20261028-a/`。`plan.json` 冻结原官方工程、IDF、FDC/RCF 及 92 项 HDL 输入；`full-reference.tcl` 执行 compile/synthesize/dev_map/pnr/report_timing；`execution.json` 保存真实退出码 0、耗时 772.004 秒、日志哈希和无输入漂移。历史 PCF 未复用，新 dev_map 生成的 PCF 已与原件比较。

## 本机跨版本重构建的实际结果

汇总及 21 份原始输出/日志的哈希保存在 `distortion/results/ddr-reference-pds2023-20261028.json`。92 项 HDL/IDF/FDC/RCF 输入的哈希在执行前后均匹配；fresh PCF 的 86 条有效指令与原件逐条相同，且生成工程及实际布局日志均绑定新 PCF。最终 IO 报告另核 71 个 mem 端口的 355 项位置/电气属性均一致并标记 `CONSTRAINT=YES`。CPD/两 IOCLK gate 的固定位置由 PCF 与布局日志核实；所选 STA 详细路径另采样到 CPD/gate0，未用 gate1 缺样本推断通过或失败。

RCF 的两个目标在最终 `test_ddr_route_optimize.netlist` 中各唯一出现，工程已登记 RCF，两条 `def_route -prior_net` 原生命令成功。它们仍不足以证明逐网优先策略的物理效果或时序收益，`PositivePerNetApplicationProven=false`。

| 类型 | slow 失败检查/总检查 | fast 失败检查/总检查 |
| --- | ---: | ---: |
| setup | 0/21168 | 0/21168 |
| hold | **2/21168** | **2/21168** |
| recovery | 0/5556 | 0/5556 |
| removal | 0/5556 | 0/5556 |
| MPW | 0/5840 | 0/5840 |

两个角的 hold 失败均位于 `phy_dq_sysclk_1 → ddrphy_sysclk`，最差裕量分别为 **−0.138ns/−0.341ns**。因此这是成功生成的失败报告，不能称为完整时序通过。此处每角 2 项 hold 属于新 2023.2 官方示例对照，不能混同当前 1080P 候选每角 245 项 recovery。

新 XML 的六组异步排除仍各为 34/3/35/84/4/84，TNS、THS 分别合计 244；同域 recovery 零失败不代表这 244 项的训练/复位释放已经验证。无输入/输出延迟仍为 34/78，五个时钟仍缺完整同域 setup/hold 观测。

最终 ADF 为 `place_route/test_ddr_pnr.adf`，SHA256 `b1d5d8425243b2a522dbe34c3a2e0ba5a92c75adad94003886c47fb5d2f7513a`；原生报告为 `report_timing/test_ddr.rtr` 与 `report_timing/rtr.db`。日志明确读取 PNR 数据库，时间顺序一致；本轮未单独记录 STA 前 ADF 哈希，不声称具备 STA 前后不变性证明。没有启动第二轮尝试来随机消除这两项 hold。

## CPU 审计入口及范围

从仓库根目录运行 `python distortion/tools/audit_ddr_reference.py --output distortion/build/ddr-reference-audit-new.json`。输出路径必须尚不存在。已执行的结果为 `distortion/results/ddr-reference-audit-20261028.json`，对应 24 项针对解析拒绝、来源绑定和计数比较的测试通过。

该入口核对 IDF 的 371 参数、74 项当前 IP 综合源的字节及清单绑定、选定 DDR 时钟/例外/位置命令与历史 XML。它不执行 EDA，不比较全部 IO/PCF/RCF 正文，不验证完整示例的 92 源闭包，也不自动验证 XML 与 ADF 的生成关系；不将它描述成完整物理签核。可选 `--current-xml` 与 `--current-final-adf` 必须成对提供，只增加报告计数对照和文件哈希，仍不能证明逐端点相同或解除 recovery 阻塞。

## 已确认的关键线索

仓库已经包含完整的同配置 DDR 官方示例：

`vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test/pnr`

其中 `ddr3_test.pds`、原配 FDC/PCF/RCF、最终 `test_ddr_pnr.adf`、网表、`report_timing/test_ddr.rtr`、原生 XML `report_timing/rtr.db` 和日志均已跟踪。历史 PNR/STA 使用 PDS 2022.2-SP6.4 build 146967，报告日期为 2025-01-06。

本工程和该官方示例的 IDF 逐字节一致，SHA256 为 `b600d6102995be4e76b060dd45786b5e1497bd2e7499bbc04b870de9355f2747`：HMIC_S 1.10、PG2L100H/-6/FBG676、x32、两个 PHY bank、参考时钟 125MHz、DFI/core 周期 8ns。74 项综合源（71 个加密体、3 个生成 Verilog）全部逐字节一致。本轮只计算厂商源文件哈希，不解密或新增分发正文。

规范化实例层级后，DDR 生成时钟、多周期、不确定性、三个 CPD/IOCLK 位置约束及 RCF 一致。当前诊断工程没有沿用官方 FDC 中的宽异步时钟组。

官方报告虽为 `All Constraints Met`，原生 Clock Interaction 表明确列出下列未计时关系：

| Launch Clock | Capture Clock | 分类 | TNS/THS 各自的端点计数 |
| --- | --- | --- | ---: |
| rst_clk | phy_dq_clk_0 | Asynchronous Groups | 34 |
| ddrphy_sysclk | phy_dq_clk_0 | Asynchronous Groups | 3 |
| rst_clk | phy_dq_sysclk_0 | Asynchronous Groups | 35 |
| rst_clk | phy_dq_clk_1 | Asynchronous Groups | 84 |
| ddrphy_sysclk | phy_dq_clk_1 | Asynchronous Groups | 4 |
| rst_clk | phy_dq_sysclk_1 | Asynchronous Groups | 84 |
| 合计 | | | **244** |

两个工艺角的恢复检查摘要只列出同域路径。这六组共 244 的数量与当前“244 个 PHY 检查＋1 个入口检查”的记录吻合，提供了直接的约束覆盖差异线索。**当前详细失败 XML 未在本机，尚不能证明这两组 244 是同一端点集合。** 表中数字是原生表的每类检查计数，不相加为独立寄存器数量。

官方示例还报告 34 项缺输入延迟、78 项缺输出延迟。其既有 STA 表只能证明当时有效约束下报告通过；还需厂商解释动态训练/复位释放保证，才能判断例外适用性。现有资料未保存历史 STA 前后 ADF 哈希，不能由当前文件哈希补造当时的不变性证明。

## 对主要阻塞的判断

优先归因方向是 **DDR IP 官方时钟例外与训练/复位释放契约之间的关系**。目前没有证据指向图像运算、缓存容量或随机布线种子；增加地址流水测试也不会解决这类恢复检查。

单独的入口检查指向 `sig_async_r1[0]/opit_0_srl/RS`。现有交接记录观察到两级 V_FFASYN 共享 SR/CK，首级 D 接 PLL LOCK，最终映射成 gopSRL2。它的安全条件同样需要核对首个有效时钟和复位释放，不能只凭 RTL 中存在两级同步就判通过。

先保留当前诊断约束。官方宽异步组可以作为对照证据，未经适用条件确认，不把它们直接加入正式候选来消除红项。

## 最短推进顺序

1. **获得最新已有报告。** 从队友机器提供下列两处现存资料的可访问副本，不必先重跑：
   - `distortion/build/offline-20261024/ddr-iponly-control-20261028-a/` 的厂商问题包、入口附录、最终 STA XML/文本、实际使用 FDC/RCF、执行日志及最终 ADF 哈希。
   - `distortion/build/offline-20261024/resume-parallel-20261028-a/rcf-diagnostic/` 的相同原始结果，用于对应最新 `897ef3...` 数据库。
2. **逐组再逐端点映射。** 先把新报告六个跨时钟 recovery 组与上表对应，再从详细路径核对 TSR/RST/RST_TRAINING_N 和额外入口 RS。主线、独立 IP 对照及官方历史例分别保存，不能混用报告身份。
3. **给厂商一个有证据的具体问题。** 确认上述六组的官方异步例外，是否以同配置训练流程保证复位解除与首有效边沿关系；要求说明精确对象、适用条件、内部原语保证和验证方法。另问入口 gopSRL2 共享 SR 的第二级保证。需要的答复是技术依据或适用修补方案，不只是建议关闭时序检查。
4. **按答复作一次针对性验证。** 若为约束遗漏，核匹配对象和实际效果；若为使用条件不满足，修复复位/训练顺序；若为特定 IP/工具问题，使用厂商认可的版本或补丁，并固定全部版本。先完成相关定向回归和最终数据库的完整检查，再安排实板。

本机 PDS 2023.2 的安装清单只登记 HMIC_S 1.7，归档及展开目录均未找到。它不能重新生成与现有 1.10 同源的 IP；如需同版本重构建，应恢复有权使用的原 PDS 2022.2-SP6.4/HMIC_S 1.10 环境。跨版本诊断可以另做，结论须单列。

## 可直接交给厂商审阅的问题摘要（未发送）

> PG2L100H/-6/FBG676，HMIC_S 1.10（PDS 2022.2-SP6.4），DDR3 x32/两 PHY bank，ref125MHz/DFI8ns。本工程与随板官方示例 IDF、74 项综合源一致。官方历史最终 STA 中，上表六组明确为 Asynchronous Groups，端点各34/3/35/84/4/84，合计244；未沿用这些宽异步组的诊断候选仍有每角244条PHY恢复检查和1条入口同步器检查失败。请确认六组例外对应的训练/复位释放与首有效时钟保证、精确适用范围，以及入口gopSRL2共享SR的安全条件；若应修使用顺序、约束或IP版本，请提供最小方案及验证要求。

完整原生报告应在获准的技术支持渠道按需提供；此文只整理问题，没有发送消息或上传文件。
