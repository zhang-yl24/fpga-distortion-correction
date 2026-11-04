# 分支交付归档

这 4 个目录共 602 文件、13,738,898 字节，直接复用原始 Git 子树，没有修改任何包内文件。它们集中保存可追溯快照；不构成生产 RTL 合并、时序修复、摄像头适配成功或 60 个新校正帧/秒的板测验收。

| 原始包 | 归档文件数 | 精确原始提交 |
|---|---:|---|
| [20261103-hdmi1080-demo-source](delivery/20261103-hdmi1080-demo-source/README.md) | 457 | [`1b9727e3`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/1b9727e31f690a2598ab51cdb27ba645c0d5eda5/delivery/20261103-hdmi1080-demo-source) |
| [20261104-op-camera-input-diagnostics](delivery/20261104-op-camera-input-diagnostics/README.md) | 15 | [`dbf928e9`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261104-op-camera-input-diagnostics) |
| [20261104-op-camera-input-unclosed4-diagnostic](delivery/20261104-op-camera-input-unclosed4-diagnostic/README.md) | 3 | [`dbf928e9`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261104-op-camera-input-unclosed4-diagnostic) |
| [20261104-tile8-cache64-candidate](delivery/20261104-tile8-cache64-candidate/README.md) | 127 | [`bfd1c77c`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/bfd1c77c36bc790ecbd19c2fe7a53edde96ac132/delivery/20261104-tile8-cache64-candidate) |

完整来源、每文件 Git blob/SHA256、字节数和复核方式见 [FILE_MANIFEST.json](FILE_MANIFEST.json)。600 个文件已本地逐字节重算 Git SHA 与 SHA256。两份 3,791,112 字节位流按原始 blob 与子树身份原样保留；连接器未提供二进制原文，因此本轮没有重算这两份位流的 SHA256，表中 SHA256 取自原包身份记录。

四条 setup 违例诊断位流的报告身份为 `a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`，WNS −0.032 ns，`TimingClosed=false`。64 KiB 包包含已有 vendor/generated `.vp` 等依赖，不是纯自研源码；该候选没有新位流，物理时序仍 FAIL。

归档路径较原仓库多出 `archive/branches-20261104/` 前缀。历史 README 的仓库相对链接、构建根假定和本地绝对路径保留原文，请优先使用表中精确提交来源及各包自己的依赖说明。demo 原生源清单有 50 个随包源码与 80 个外部依赖；不能把此归档视为独立完整 PDS 工程。只验证了 cache64 的 111 项输入重定位准备，未执行其 Tcl 或 EDA。

获取完整 Git 对象后，可从仓库根目录运行 `python docs/branches-20261104/verify_integration.py --ref HEAD`，复核原 main 文件无改删、4 个归档子树和 602 个文件的哈希。该工具不调用 EDA 或硬件。
