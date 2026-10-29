# HDMI 初始化故障检测与隔离候选（2026-10-29）

## 本轮改变

新增独立 checked 候选，修复 HDMI 配置失败无法可靠上报的问题。旧原生构建输入、已修复 ADF 和位流没有替换；新候选需要自己的完整 PDS 构建及约束审查。

- `iic_dri_checked.v` 检查设备地址、寄存器地址、数据阶段的 ACK；设备缺席、总线卡住、SCL 拉伸超时及发送冲突会置位粘滞错误。失败不产生成功 `byte_over`，只有公共复位清除故障。SCL/SDA 采用开漏语义并读取实际线电平。
- `ms72xx_checked_ctl.v` 在失败当拍禁止配置完成，停止推进初始化；修复 RX 完成并让出总线后，TX 完成时 RX 后台轮询无法恢复的问题。
- 实际联调发现原 MS7210 控制器在 INIT→WAIT 边界多发一次第 19 项命令。`ms7210_checked_ctl.v` 限定触发条件，保留原 49 条寄存器命令和原等待时间。精确变换审计阻止无关修改。
- `board1080_checked_top.v` 接入同步后的 HDMI 故障，启动前禁止放行；运行后记录 A7 并使用已有停止/排空机制，保留尚待完成的 AXI AW，避免撤销有效事务。它不以 HDMI 错误直接复位 DDR 或数据流水线。

## 已实际执行的验证

| 验证 | 结果 | 覆盖范围 |
| --- | --- | --- |
| 驱动线级仿真 | 17 个场景、8 个非法参数拒绝通过 | 真实 checked 驱动；开漏从机模型；读写、5 个 NACK 阶段、缺设备、卡总线、拉伸、复位恢复 |
| RX/TX/驱动联合线级仿真 | 7 个场景、2117 条有序事务通过 | 真实 RX、TX、checked wrapper 和驱动；逐条 CSV 对照，失败注入及恢复 |
| 控制器协议仿真 | 7 个场景通过 | 实际 RX/TX/wrapper，事务级驱动测试桩 |
| 板级控制仿真 | 启动与运行后故障、3 次公共复位通过 | 实际 checked 顶层控制；DDR、PLL、系统状态等明确使用测试桩 |

每次实际 compile/elaborate/simulate 原生返回 0；最终回执与源码、测试向量和日志的 SHA256 均复核。驱动 10 MHz 配置时钟下实测数字低/高相位最短 1400/1600 ns，不代表板上上升沿、负载或模拟 AC 已合规。故障后不自动重试的线级观察窗口为 40 个配置周期，粘滞状态机由公共复位恢复。

独立复核执行 CI 最后一步的 9 个 CPU 测试文件，162 项全部通过（45.86 秒，Windows Python）；`handoff/audit-baselines.py` 四个交付基线及依赖闭包全部通过。未声称在 Linux 上执行过本轮原生验证。板级 A7/LED7 仅表示 HDMI 配置故障类别，内部 4 位 ACK 错误码没有导出到板上可读接口。

回执：

- `distortion/results/board1080-checked-iic-20261029.json`：驱动阶段原始快照，其中“仍需集成”是该阶段状态。
- `distortion/results/board1080-checked-integration-20261029.json`：随后完成的联合线级、事务测试桩和板级控制回执，包含精确来源和产物哈希。嵌入的 RX EDID 审计描述的是 EDID-only 变换，不能将其历史 I²C 限制误读为 checked 驱动未实现 ACK 检查。
- 本地详细日志保留于 `distortion/build/iic-checked/native-1029-b`、`board1080-checked/wire-20261029-b`、`board1080-checked/wrapper-20261029-c`、`board1080-checked-control/native-1029-a`。失败或输入漂移的早期运行保留，没有改写为通过。

## 明确的候选边界

`distortion/board/board1080-checked-sources.json` 在 EDID-only 的 109 项闭包上精确替换 4 项（驱动、TX、wrapper、顶层），105 项不变。清单和审计工具验证当前字节，不宣称它已完成 PDS 编译。现有 PDS 准备器会拒绝此新顶层，这是预期行为。

当前已修复位流不包含本轮 checked 驱动；本轮已完成的 `hdmi30-1029-a` 完整 PDS 构建也只包含 EDID-only 改动。两个候选的仿真与时序证据必须分开。没有执行真实 HDMI 芯片访问、下载或烧录。`init_over` 表示配置流程完成，不代表链路锁定、输入模式读回、DDR 训练或真实画面验收。

## EDID-only 新构建的实际结果

北京时间 2026-10-29 20:13:57 至 20:46:13，PDS 2023.2-SP3 完成 compile、synthesize、dev_map、pnr、route_optimize、report_timing，原生退出 0。115 项输入、109 项编译副本及精确 include 变换通过审计，原生日志没有 E/F 错误；最终 ADF 与 STA 前快照均为 `dc346eb3ed5f926aa69dae11f586f8407a4b05695c4da2ebda8fcecfec910b02`。

流程完成不等于时序通过。新原生 RTR 与 XML 的全部十类汇总逐项一致，结果如下：

| 检查 | slow 最差裕量 / 失败数 | fast 最差裕量 / 失败数 |
| --- | --- | --- |
| setup | +0.447 ns / 0 | +3.248 ns / 0 |
| hold | -0.037 ns / 1 | -0.222 ns / 1 |
| recovery | -4.056 ns / 245 | -3.023 ns / 234 |
| removal | +0.353 ns / 0 | +0.160 ns / 0 |
| minimum pulse width | +0.035 ns / 0 | +0.035 ns / 0 |

本次未应用 DDR 复位例外或局部绕行，八类 false-path 列表为空。外部输入/输出延迟仍缺 54/110 项；新库 PCF 和路由报告核实 142 项声明、134 个实际 IO，占用差异为 RGB565 丢弃的 8 个低位。这不是 checked 顶层的 inout 引脚验证，也不是实际供电测量。

可复核结果：`distortion/results/board1080-hdmi30-full-build-20261029.json`。独立收集工具为 `distortion/tools/audit_hdmi30_build.py`，只读取已有原生报告并生成新的诊断 JSON，不运行 EDA、不生成位流、不会将退出 0 作为时序验收。首次保存被改名目录的沙箱写权限拒绝；随后获得路径写入授权保存，原生构建结果和输入不变。

## 下一步

1. 对上述新 ADF 取得扩展 DDR 端点/路线/RDC 证据，判断原 DDR 局部修复是否仍适用；汇总相同不足以直接复用精确修复，不绕过旧固定 SHA 门禁。
2. 对 checked 顶层生成独立派生 FDC：将 `board1080-cdc-reset-diagnostic.fdc` 第 201 行 `hd_scl` 的 `PAP_IO_DIRECTION` 从 `OUTPUT` 精确替换为 `INOUT`，原清单与 FDC 保持为历史快照。K22/K23、3.3V/LVCMOS33、4mA/SLOW 与 DDR RCF 暂保留；不能凭空添加上拉或 IODELAY。需要确认板上 SCL 的外部上拉，原推挽 SCL 可工作不能证明已存在上拉。
3. 为 checked 候选新增受约束的 PDS 准备入口，运行其自身综合、PNR、STA和必要 DDR 准入/修复；最终导出位流前再次审计。
4. 硬件条件具备后依次测配置 ACK/错误状态、DDR 训练、HDMI1080p30 模式与画面、标定效果和长时间稳定性。OV5640 直入不是本候选的输入路径。

PDS `User_Constraint_Editor_User_Guide.pdf` 第 127 页说明 `PAP_IO_DIRECTION` 不转换至 PCF；因此新构建须核路由 `.prt` 的方向，以及实现网表中 SCL 三态使能和输入回读，不能只查 PCF。`vendor/board/hardware-guide.pdf` 第 21 页的 L3/L4/L5 3.3V 信息支持暂保留电平设置，未替代实板电压与上拉确认。

本轮属于离线功能与控制改进；没有把分立仿真等同整板数据链联合仿真，也没有用旧候选的时序通过结论替代新候选验收。
