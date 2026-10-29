# HDMI 芯片复位释放后的配置等待补丁

日期：2026-10-30。供队友统一集成，当前主工程未应用此补丁。

目标是 `distortion/board/board1080_checked_top.v`。G25 仍随原 `global_reset_n` 释放；随后用 27 MHz 参考时钟等待 2,700,000 周期（标称 100 ms），再释放 `ms72xx_checked_ctl.rst_n`。每次公共复位重新完整等待，I²C 失败不触发自动重试。

补丁只有新增等待计数/完成寄存器和改变 HDMI 配置控制器的一个复位连接。原 `global_reset_n`、DDR IP 复位、pipeline 复位及其余逻辑均保留；没有修改源清单、约束或任何已生成位流。

受控诊断实板对比中，原立即启动版本在首次 device-write 遇到 NACK、成功事务数为 0；独立延迟诊断版本收到 ACK，`error=0`，成功事务数从 311623 增至 341865，处于等待 HDMI 输入的状态读取阶段。这支持把相同等待策略交接到主工程，但不能证明 HDMI 视频、TX 完整初始化或整条矫正链路已通过。

独立诊断顶层的 5 项启动时序仿真和完整 PDS 原生时序检查已通过。**本补丁应用后的主工程尚未综合、布局布线、STA 或上板验证**；诊断版本结果不能替代主工程重建。源文件变化会使当前主工程绑定哈希失效，统一集成时应按原准备/审计流程重新生成对应闭包和证据，不应仅改哈希沿用旧结果。

补丁通过 `difflib.diff_bytes` 从原始字节产生，保留目标现有换行。2026-10-30 在当前仓库执行以下检查，退出码 0；只检查可应用性，没有应用补丁：

```powershell
git apply --check handoff/patches/hdmi-post-reset-wait.patch
```

核对基线及审核改动后，由统一集成者在仓库根目录执行：

```powershell
git apply handoff/patches/hdmi-post-reset-wait.patch
```

| 文件/状态 | SHA256 |
|---|---|
| 原始 `board1080_checked_top.v` | `4a355e17d49dc5e46ab4fca6cbceee461ac9cc5d3f192cc00b2aa052a6691476` |
| `hdmi-post-reset-wait.patch` | `ec990aba532e291b68dc0607c9d94da2a0cf0951a5a01a17a8cdabd223a35772` |
| 按补丁生成的预期新顶层字节（未写入主工程） | `6d15b0b4aed22bf08241c3b3d12339decb7ccdec5b5986aef143833101e952ec` |

关联诊断证据保存在本机忽略目录：`distortion/build/hdmi-uart-diagnostic/startup-1030-a/simulation-result.json`、`distortion/build/hdmi-uart-diagnostic/delayed-pds-1030-a/native-audit.json`。这些是独立诊断候选的证据，不是本补丁应用后的主工程结果。
