# stable-a 最终约束审计结果

2026-11-03，候选 source param ID `8c73465e`。

独立脚本 `audit_stable_constraints.py --build D:/fpga-stable/build/stable-a --output D:/fpga-stable/reset/stable-a-constraint-audit-final.json --require-final` 返回 **PASS，33项检查通过，0个待完成项**。结果确认约束集及工具输出的作用范围，硬件稳定性由板上测试验收。

关键证据：

- 三条厂商时钟组恰好为 rst_clk、phy_dq_clk_0、phy_dq_clk_1；没有新增 false_path。
- board27、cfg_clk、input_pixel、pixel_clk、ddrphy_sysclk 的20个有向跨域组合均保留8 ns max/0 ns min。
- core 与 phy_dq_sysclk_0/1 仍保留 multicycle=2、0.4 ns uncertainty，最终 clock interaction 为 Timed；core→phy_sys0/1 余量分别 +0.017/+0.009 ns。
- 最终完整时钟树：rst_clk126负载、phy_dq_clk_0 35负载、phy_dq_clk_1 84负载，两个divided PHY 35/84负载；这些时钟的全部端点均在 DDR IP 内，用户负载0。core 19727负载中15883属于IP外用户逻辑，其跨域与同域检查保持有效。
- Map、Route、STA、Bitstream 的原生 `.pds` 均注册匹配 FDC 与 RCF 类型；preparation 的文件SHA一致。
- 实际 `run_route.log` 第27–30行分别记录两个 `def_route -prior_net` 成功，未出现对应未匹配警告；原始厂商RCF的总线空格写法被PDS接受。

文件 SHA256：

| 文件 | SHA256 |
|---|---|
| 原诊断FDC | `2ff6dd8510e7b0566f550143561ac4138c19cd255944811b4561979f6e8b0f23` |
| DDR时钟关系FDC | `e50c487f732019f59882386e558649c1777f03e540a0d5db971194ebcae6a47c` |
| DDR RCF | `4195e9a465a277e3e242f191d55b78bde4e713e2145121825008d83e7b2aab1d` |
| UART FDC | `70b4b2f39c0da2703216abdbf320d9dbe7a0dd95bfbda5253cfc0a518ef090e5` |
| 最终routed ADF | `0c6615b2dd9b83ee032e47c0bf990865d31ef9ba6baea68547099370e8981249` |

同ADF诊断尝试：`D:/fpga-stable/build/stable-a-diagnostic` 只在新工程中加载原诊断FDC、UART、map PCF，然后对上述最终ADF运行STA。运行成功、ADF哈希前后不变，但结果仍继承三个 Asynchronous Groups。审计 `stable-a-constraint-audit-with-diagnostic.json` 正确判定 **FAIL: diagnostic_really_removes_inherited_ip_clock_groups**。这份结果用于记录工具的约束继承行为，不可称为去除三个组后的诊断，也不作为位流导出门槛。

正式约束集与参考IP逐字节匹配证据、复位边界和加密同步器结构的未验证部分，见 `DDR_RESET_CONSTRAINT_AUDIT.md`。目前无法据公开产物声称已经独立证明 ips2l_rst_sync_v1_3 的首级/次级实现。用户上电复位边界采用匹配IP的厂商模型，并保留同域复位分发检查。
