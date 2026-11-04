# O/P 摄像头输入首故障诊断

**A2 定位源码中间交付：不是已完成的摄像头兼容修复，暂无新位流。最终时序尚未闭合，不能当作原生构建、摄像头实板或 60 新帧通过。**

原独立实现最终 slow setup 为 6 条违例、WNS −0.030 ns；随后同源码的 50ps 增量物理实验仍有 4 条违例、WNS −0.032 ns。两次物理数据库不同，不能混用报告或以较少违例宣称通过。本目录没有生成或发布新的诊断位流；此前的 O/P 位流也不包含本诊断。

它保留 O/P 的输入资格、147000–150000 像素时钟窗口和故障排空，仅增加独立 27MHz 诊断 UART，供同学审查和使用其工具独立重建、协助定位现场 A2。重建结果须重新绑定完整源码、依赖、约束、工具、ADF 与位流 SHA，不能声称与主线程的任何位流为同一份。

以下现场采集步骤仅供后续完成构建和验证的诊断位流使用；当前源码交付不满足加载条件。

基线为独立 delivery 分支提交 `1b9727e31f690a2598ab51cdb27ba645c0d5eda5` 的 O/P；实测原位流 SHA256 为 `99f8a734161364618e18800de2ebdc01f4c7261c2c6579a8be2b11df870708a9`。原 O/P 通过的是电脑 HDMI 1080p59.94 输入。现场摄像头加载的 `03497abc09f878e596677806c73dbdcf39d7750d66a9da94c8537b7dcfa80e36` 是另一份文件；其重建身份尚未闭合，文件哈希不同不能单独证明逻辑不同。

## 现场采集

确认器件为 PG2L100H、接线和温度满足既有安全流程，并保留已验证回退位流。只做 SRAM 加载，不写 Flash，不改温度阈值。先校验最终位流 SHA256，再在下载前打开接收程序；填写现场真实 CP210x 端口，不直接沿用其他电脑的 COM5/COM7。

```text
python -X utf8 -B host/capture_runtime_diag.py --port COMx --seconds 100 --outdir D:/FPGA-captures/new-camera-run --bit-sha256 FINAL_SHA256 --source camera
```

随后用官方工具 SRAM 加载最终诊断位流。该程序只接收串口、不会编程或发送 UART 字节；位流 SHA 是操作者声明，程序不会自行验证 FPGA 加载身份。不要发送 SGA1、SGT1，也不要用 PGSTAT02 解码此版。

```text
python -B host/decode_runtime_diag.py D:/FPGA-captures/new-camera-run/uart.raw.bin --out D:/FPGA-captures/new-camera-run/redecoded.json
```

PGIQ0001 每包 84 字节、115200 baud，最多 240 包，约 62 秒发送期。`first_valid=false` 时两段都是当前 live 状态；有效时第一段是不可变首失效快照，`follow_valid=true` 后第二段是 2ms 后快照。重点回传原始文件及其 SHA、加载身份、视频源实际模式和 decoded.json。

优先看 `selected_qualified/selected_failed`、`rate_bad/rate_failed_sticky`、几何健康与五个 fresh 子项、PLL/RX/TX/DDR ready、PCLK 窗口计数及 good/bad frame。严格 HS/VS timing 在原 report-only 模式下不直接代表功能资格失败。A2 可先于速率或新鲜度的 sticky fault 锁存，单个 A2 不能确定具体原因。开头或截窗尾的非完整包要保留并区分主机采集边界，不能直接归为 DUT 错误。

此协议没有呈现帧计数，不计算新帧率、板上图像正确率或端到端延迟。

## 源码合同

`native/` 只含 5 项第一方新/变源；83 项厂商/生成依赖仍不发布，原 O/P 源与匹配依赖由既有交付提供。`SOURCE_BINDING.json` 区分实际编译 SHA 和仅 include 路径脱敏后的导出 SHA。`integration/INPUT_FIRSTLOSS.patch` 针对基线已导出 native 路径，应用到独立副本，不覆盖稳定工程。

新 snapshot 使用 `.sv`；PDS 需要官方 `compile -verilog_standard SystemVerilog`。仅修改后缀不足。原硬 IP、PCF、时钟、约束和输入阈值保持基线；不加入任何时序例外。不是不依赖 IP 的完整工程包。

短测覆盖 8 项首失效/保持/follow/reset、168 个真实 UART 字节及 CRC、81548 沿原/新监控一致性。该结果不是摄像头实板验证；详细边界见 `evidence/SHORT_HDL_SUMMARY.json`。
