# 已发布摄像头输入诊断接口审计

来源 `dbf928e91082e7c81b5a188b8b464726040da0a7`，O/P 基线 `1b9727e31f690a2598ab51cdb27ba645c0d5eda5`。本审计只读取工作区发布快照，没有读取活动候选、运行 HDL/EDA 或访问硬件。

## 最小单元

两个诊断模块加 O/P 已有的 `uart_tx.v` 构成无厂商依赖的三模块闭包。可新增唯一命名的 `input_diag_probe_ref27` 包装器，接收 27MHz 同域状态与显式 32 位字段，只输出独立 `diag_tx`，不接回 DDR、复位、准入、FIFO 或 bank ownership 控制。

这只是可准备的最小真实源码整合方案；本报告没有新增 wrapper 或执行 HDL 编译，不能把它称为已经验证的整机组合。接入同学板级 top 前，须绑定准确 source list 和状态语义。

## 接口和时钟

- `hdmi_input_runtime_snapshot`：6 个 1 位控制输入与 256 位 `live_tuple`；输出 first/follow valid、各 256 位快照、32 位 uptime 和 wrap 标志。`rst_n` 异步低有效。释放后首次 `!qualified || input_failed || !ready_all` 触发，默认 54000 个参考沿后再拍一次，即 27MHz 下 2ms；此后保持到共同复位。
- `hdmi_input_runtime_diag_uart`：同域三组 256 位 tuple 和三标志输入，只有 UART TX 输出。**没有外部 reset 端口**；初始化释放链控制自身启动。系统手动复位不会清 UART 的 packet_count/240 包预算，必须明确这是配置/上电周期而非 snapshot epoch。
- 这两个模块不完成像素域多位总线的同步或握手。所有输入必须已在参考域中一致；已发布 top 先同步 PLL/RX/TX/DDR 状态，并使用 input-status 现有参考域快照。

## UART 与 tuple

`PGIQ0001`、84 字节、小端、115200 名义 baud、8N1。0..7 为 magic，8 为 first/follow/wrapped 三标志，9 为84，10..11为零，12..15为序号，16..47为first或live，48..79为follow或live，80..83为前80字节的CRC32。每个包开始时整体锁存 payload，包内不会被输入变化撕裂。默认0.25s空档，最多240包、约62s。

tuple 由低至高的8个32位字：uptime、flags、reason、PCLK窗口计数、good frames、bad frames、`{lines,pixels}`、`{board_fault,input_fault,ref_fault,source_fault}`。顶层 L194 的 flags 确为 `[31:0]`，L195 的拼接宽度正确。协议不是 PGSTAT02，不能发送/使用 SGA1、SGT1 或据此计算新校正帧率。

已发布 top 的 UART 为编译时整端口选择：runtime诊断优先，其次startup，再其次原normal telemetry。不能把两套 TX 同时连接到同一引脚，也不能把 PGIQ 和 PGSTAT02 作为同一种流解码。

## 已跑与未跑

原包短测报告8项快照场景、168真实UART字节/2包、81548个参考沿的输入状态控制miter，状态为 `RUNTIME_DIAGNOSTIC_SHORT_PASS`。它不是完整top等价、主线新适配器验证、CDC/IO物理签核或板测。物理实验仍有4条setup/WNS−0.032ns，不能作为时序通过。

本审计新增的是CPU合成数据协议检查：84字节/CRC/8word全字段往返、几何与fault字节、坏CRC/头/follow标志/截断/prefix/trailer，全部通过；无HDL或硬件执行。详见 `diag-interface-cpu-checks.json`。

## 真正接入需要解决的项目

1. 固定同学已发布板版 top/source list，逐项映射参考域状态；不要覆盖同名 `board1080_top`、`hdmi1080_input_status` 或 `dvp_mode_admission_monitor`。
2. 源表只选择一份同字节 `uart_tx`，wrapper 采用唯一模块名；原DDR/像素/KEY1控制保持主线实现。
3. 先验证包装器字段、snapshot/reset与包原子性，再做原控制输出/DDR事务对照。KEY1与scout未发布，不需要为此等待，也不能借用其验收。
4. 板级组合要独立新Build/Profile、IP/约束/引脚哈希、双角STA和CDC/RDC/IO签核；不得继承O/P旧位流验收。

完整端口、协议位定义、源SHA256、精确行号及链接见 `diag-interface-review.json`。
