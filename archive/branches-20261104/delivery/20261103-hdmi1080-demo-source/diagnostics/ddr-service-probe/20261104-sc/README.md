# S-c：有限 DDR 服务诊断源码与内部时序证据

这是独立DDR诊断入口，不包含HDMI图像流水线。它用于区分AR等待与一次被接受读请求的首拍/尾拍延迟，为后续真实板测准备；目前没有真实DDR测量结果，也不证明多请求带宽或图像60fps。2026-11-04 03:18（北京时间）本地bit封存，未经上板。

## 源码和已有功能证据

冻结原生归档156项输入的当前哈希全部匹配。实际PDS TCL只注册8个design：7项项目RTL和1个外部DDR IDF；归档中的旧视频文件不等于参与当前设计。这里只新增5项自有RTL，复用同分支已有held_bundle_cdc和uart_tx两项，另提供3份已经执行的短测bench及离线解码器。合法DDR IP、时钟/引脚约束和厂商原件未上传。

编译标准必须明确为SystemVerilog，顶层为独立board1080_top，不能与其它同名视频顶层一起加入。S-c在此前入口上仅补充key_reset_sync的PAP属性；所有功能测量RTL与既有短测输入逐项匹配，未增加周期或更改复位逻辑表达式。

- 核心6项短测＋2项边界短测通过；每组16读，覆盖16预写/48读、768返回拍、同周期响应、停顿、超时、协议/数据/CRC及初始化边界。
- 读出短测真实8N1波形480字节/6包通过，包含跨域快照、包原子性、公共复位使旧快照失效、传输后core停钟而REF仍发送、有限停止。
- native TIMEOUT=4096；短测按场景为32/128，不能把测试参数当成封存bit参数。native默认120包与短测6包也要区分。
- 新交付只核验原回执、日志PASS标记和实际输入哈希，没有重新运行HDL、EDA或硬件。早期Verilog模式Map失败、readout-c的32位bench延时问题均保留历史，不能用编译退出0代替功能PASS。

## 原生配置与协议

先预写16个突发，再按约定的samebank-row、alternatingrows、rotatingbanks三种请求地址模式各读16次；每次16拍，始终single outstanding。这里使用Pango原生UI的实际端口，未假设存在RREADY/WVALID/B通道；真实bank/row服务表现仍需板上验证。

PGDDR001为80字节、版本1、小端字段，末4字节是前76字节的IEEE CRC32。REF名义27MHz，UART115200 8N1，默认有限120包，三个group轮转。反复发送的终态快照仍描述同一批48次读，不能算成更多事务或统计独立样本。

byte10为group及SnapshotValid/KEY/GlobalResetN/DDRInit/DDRLock标志，byte11为包序号；12/16/20为REF uptime、快照次数、快照年龄；24..71为12个统计字；72为status；76为CRC。每组统计含GroupCount、ARWait/FirstR/LastR各min/max/sum、ActualCRC和ExpectedCRC。实际单位是core周期，125MHz仅是名义模型频率。

离线解析器：
~~~python
import json
from pathlib import Path
from host.decode_pgddr import decode_stream
print(json.dumps(decode_stream(Path("capture.bin").read_bytes()), indent=2))
~~~
**解析器不是严格LIVE验收工具。Measured字段只检查SnapshotValid和GroupCount>0。** 不能据该字段或CRC单独接受性能结论；还需确认最新有效epoch、GlobalResetN/DDRInit/DDRLock、Done/Failed/Fault、各错误标志、组数与实际/期望CRC，并排除捕获后复位及重复终态包。该交付没有串口采集或自动上板工具。

## 独立 STA 与资源

| 内部检查 | slow裕量 ns | fast裕量 ns | 两角失败端点 |
|---|---:|---:|---:|
| setup | +0.143 | +2.683 | 0 |
| hold | +0.067 | +0.043 | 0 |
| recovery | +3.854 | +5.250 | 0 |
| removal | +0.338 | +0.232 | 0 |
| 最小脉宽 | +0.035 | +0.035 | 0 |
| skew | +0.223 | +0.240 | 0 |

交付工程师从实际独立STA报告重新解析12张汇总表。结论限于原有DDR三个单组asynchronous模型；叶节点归属审查和8/0ns held-bus规则不能替代完整CDC、物理复位或外部IO签核。报告仍有33项输入、80项输出缺少外部delay。

Map资源为FF11537、LUT9553.5、DRM0、APM0、IO84。它没有视频处理功能，不能将这些占用当作同功能图像流水线资源下降。

原生归档SHA：73d5d3d0c91f6abbe3106b910ef87652108828cf2f9087ea78d9b5dd54bca4dd。
本地bit SHA：024944b5c8e362b1fed03c15ed43f4b1b7ffbe119267e6db0b5de6f2ac93c3b8。
最终ADF SHA：7359ff0e4db8cbbc2579e602df4881a1501f48e38c25c07a5f2808a14d051a59。
这里只发布哈希及去标识证据，不上传bit、ADF、厂商报告、许可证或原始UART。

## 使用范围

~~~text
python -B verify_delivery.py
python -B prepare_sources.py --output <全新目录>
~~~
准备工具只重建7项项目RTL；不是完整PDS项目，不复制厂商依赖，不编译/仿真，也不打开串口。实际设计/约束输入哈希见SOURCE_BINDING、FROZEN_NATIVE_ARCHIVE与CONSTRAINT_REVIEW。

S-c仅能诊断single-outstanding事务。它不能证明[F双读实验](../../../experiments/dual-read-credit/20261104-f/README.md)所需的真实DDR多请求支持，更不能代替并发capture/scan压力、图像fps、延迟分布或E2E验收。O/P与E2保持独立身份。
