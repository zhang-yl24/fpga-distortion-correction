# 四条 setup 违例的摄像头输入诊断位流

**未签核、可能不稳定；不是摄像头兼容修复完成版，不证明 60 新帧。发布时尚未实板验证。**

仅供现场短时受控 SRAM 诊断，不写 Flash。实际文件 `camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit` 共 **3,791,112 字节**，SHA256：

```text
a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547
```

它只由最终 ADF `8de179b8c4e620d2f9a5baff70287aa2d8126fb6fada90caeb9975a054be35a9` 生成：slow setup **4 条 / WNS −0.032 ns**，其余 11 项报告检查无违例。clocktree 目标 50ps、SRB100；不是原 6 条违例的数据库。完整文件级身份见 `DIAGNOSTIC_IDENTITY.json`。

目标硬件 PG2L100H-6 FBG676 / ID 0x00602899；输入为 MS7200 接收的 1920×1080 逐行 HDMI，名义 148.5MHz/60Hz，输出名义 148.5MHz。原输入资格和故障保护保持，A2 原因尚未修复。本版只用独立 27MHz UART 读首失效及 2ms 后状态。

按现场既有供电、接线和温度流程预检，保留同学自己已验证的 tile8 15fps 回退位流，不猜其本机路径。发生异常先保存证据、停止并回退，不改硬件温度阈值，不长期无人值守。O/P 99f8 位流只通过电脑输入验证，不保证作为摄像头回退；本提交不新增 golden 位流。

[此前的源码/工具包](../20261104-op-camera-input-diagnostics/README.md)保持原样，仍对应源码中间交付 f8f58a16。此目录独立放位流及最小身份，不改动其 SOURCE_BINDING 或源码文件清单。独立重建须重新验自己的完整构建身份，不能称重建位流与本文件相同；PDS 需要 `compile -verilog_standard SystemVerilog`。

先核文件 SHA，再在 SRAM 下载前打开该源码包的接收工具（填写现场实际 CP210x 端口）：

```text
python -X utf8 -B ../20261104-op-camera-input-diagnostics/host/capture_runtime_diag.py --port COMx --seconds 100 --outdir D:/FPGA-captures/new-camera-run --bit-sha256 a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547 --source camera
```

接收工具不会编程或发送 UART；参数中的 SHA 是操作者声明，不自动验证 FPGA 已加载身份。随后用官方工具 SRAM 加载本位流。

协议只有 **PGIQ0001 / 84 字节 / 115200 baud**，最多 240 包，约 62 秒发送期；**没有 PGSTAT02、SGA1/ARM 或 SGT1**。`first_valid=false` 是 live 状态；有效时首段永久保留第一次资格掉线，`follow_valid=true` 后第二段是 2ms 后证据。优先看 rate_bad/sticky、geometry/五项 fresh、全局 ready、PCLK 和 good/bad 计数。严格 timing 在 report-only 模式下不直接等于功能失败。保留加载日志、原始接收字节及 SHA、视频源实际模式和 decoded.json。

此协议没有呈现计数，不计算校正新帧率或端到端延迟。请勿把解析成功、显示出图或普通时钟状态当作摄像头修复或时序签核。
