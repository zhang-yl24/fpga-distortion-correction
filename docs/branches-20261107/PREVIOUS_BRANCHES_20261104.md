# FPGA 分支目录（2026-11-04）

本次入口是 `integration/20261104-fpga-branches`。以 main `8f2a5b76` 为父提交，只新增目录说明与独立交付归档；**没有进行生产 RTL 代码合并或硬件验收**。32 个原远端分支均保留，没有改名、删除、强推或修改现有 PR 状态。下表建议名仅用于未来新任务，未再复制出 32 条分支。

已核对 27 个非 main 分支头是 main 的祖先，4 个仍与 main 分叉。祖先关系仅表示提交历史：PR #28 已完整回退，不能由此宣称所有历史文件当前仍在 main。

## 当前应使用的入口

- 当前共享源码：[`main`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/8f2a5b7679ca77153bd36d52a2660e286bff7730)。同学 directfill、camera720p15、报告、海报和板测资料原样保留。
- 摄像头排障：原 `delivery/20261104-op-camera-input-diagnostics`；四条 setup 违例的位流仅为诊断，WNS −0.032 ns，未修复摄像头兼容问题。
- 缓存 64 KiB 候选：`codex/tile8-cache64-evaluation-20261104` / [草稿 PR #29](https://github.com/zhang-yl24/fpga-distortion-correction/pull/29)，时序未通过。
- 同学最新 directfill 研究：`codex/hdmi-camera-fisheye-tile8-directfill` / `14397de2`；独立 256 KiB 双路缓存研究，仍有 setup −1.481 ns、224 个失败端点，没有新位流或新板测结论。
- 本轮保全的交付包：[归档目录](archive/branches-20261104/README.md)。这不是新的默认工程根。正在进行的 60 帧 scout-local-a 和摄像头时序修复不属于本轮离线归档，也未受本轮操作改动。

## 全部分支与命名映射

“作者证据”来自 PR 或末端提交，不能据此推断唯一维护人或分支删除授权。精确 SHA、ahead/behind、PR 状态及证据链接见 [机器目录](docs/branches-20261104/catalog.json)。

| 现有分支（完整原名） | 用途 / 分类 | 作者证据 | 今后新任务的命名建议 |
|---|---|---|---|
| [`codex/board1080-rowpipe`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/31f7df667e830ca6a3e0ae0a3b261b1fcd8112e9) | 已进入主线历史：1080p 行乘积流水和原生仿真历史 | lrt24-thu | `archive/20261028-hdmi1080-rowpipe` |
| [`codex/camera720-output`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/3dfcab39d0437ae14025e75837116da491ce277c) | 已进入主线历史：720p 镜头校正输出与 15 fps 遥测历史 | lrt24-thu | `archive/20261101-camera720p15-output` |
| [`codex/camera720-view-toggle`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/30ce89b6639b8183bafdf6897f4e2cfe09556adf) | 已进入主线历史：720p 原图/校正帧边界切换历史 | lrt24-thu | `archive/20261101-camera720p15-view-toggle` |
| [`codex/camera-vga-calibrated`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/90f6e4a0f23aa253f098144a00a7c656897d04e9) | 已进入主线历史：VGA 实际镜头标定历史 | lrt24-thu | `archive/20261031-camera-vga-calibration` |
| [`codex/camera-vga-upright`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/0643c1856175a3963d01a3d47f07ad121776fda8) | 已进入主线历史：OV5640 VGA 正立图像流水历史 | lrt24-thu | `archive/20261031-camera-vga-upright` |
| [`codex/ddr-ip-timing-fix`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/18f6f036eb483120c2b900fff7d28259b3221819) | 已进入主线历史：DDR/IP 与 HDMI 候选时序审计和历史导出 | lrt24-thu | `archive/20261029-ddr-ip-timing-audit` |
| [`codex/ddr-recovery-diagnosis`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/cc596af563803b07ef7ab06aa8d6df903d80fe28) | 已进入主线历史：DDR recovery/时钟例外离线诊断历史 | lrt24-thu | `archive/20261028-ddr-recovery-audit` |
| [`codex/dvp-capture-cdc`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/7cb0236eacd999eb00bc0626151d9ac6ee4846fd) | 已进入主线历史：DVP 采集跨时钟处理历史 | lrt24-thu | `archive/20261029-dvp-capture-cdc` |
| [`codex/fisheye60`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3) | 受回退影响历史：双 lane / tile 的 1080p60 源码候选；旧物理时序 FAIL，包已受 PR28 回退影响 | Jason-liu210606 | `experiment/20261103-fisheye1080p60-timing-open` |
| [`codex/fix-portable-ci`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/4903f7d9bd72e70a0375fcdf0ad2c56b18d801a1) | 已进入主线历史：可移植 CI fixture 与故障恢复 timeout 修复历史 | lrt24-thu | `archive/20261028-portable-ci-fix` |
| [`codex/hdmi1080-stable30`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89) | 受回退影响历史：三源槽 stable30 历史候选；包目前不在 main，PR23 仍 open draft | Jason-liu210606 | `experiment/20261103-hdmi1080p30-three-buffer-board-pending` |
| [`codex/hdmi1080-throughput`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/bdaf8c1527fb46cc5b8753415fa02f464a8c08b0) | 受回退影响历史：HDMI 1080p 缓存/写回吞吐诊断候选；包目前不在 main，PR22 仍 open draft | Jason-liu210606 | `experiment/20261103-hdmi1080-throughput-timing-open` |
| [`codex/hdmi-camera1080-bringup`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/ee45af47e2d01859f8cb203dbacdacaacf713d61) | 已进入主线历史：HDMI 摄像头 1080p bring-up 历史线；PR20 标题复用了旧 720p 切换说明 | lrt24-thu | `archive/20261102-hdmi-camera1080-bringup` |
| [`codex/hdmi-camera1080-display`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/214cc2ece823737d384d68350f6b5679c18c210b) | 已进入主线历史：HDMI 摄像头 1080p60 直显历史交付；不等同 60 个新校正帧/秒 | lrt24-thu | `archive/20261102-hdmi-camera1080-direct-display` |
| [`codex/hdmi-camera1080-fisheye`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/c53fdecc5dfce176700d8d6160a6ee458e1689d3) | 已进入主线历史：HDMI 摄像头 fisheye C 版源码、标定和历史板测交付 | lrt24-thu | `archive/20261103-hdmi-camera-fisheye-c` |
| [`codex/hdmi-camera-fisheye-fill8`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/13e5aac346b6d85a2716d81ebc07cbc3bc73668e) | 已进入主线历史：8 拍填充 fisheye 历史交付与约 5 fps 记录 | lrt24-thu | `archive/20261103-fisheye-fill8` |
| [`codex/hdmi-camera-fisheye-tile8-directfill`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/14397de26605b0f0422e01aa87f9fa092b3ea5b9) | 活跃研究：同学 directfill 线；新增 256 KiB 双路 cache 容量/时序研究提交，时序失败证据随包保留 | lrt24-thu | `experiment/20261104-tile8-cache256k-two-way-timing-open` |
| [`codex/hdmi-camera-fisheye-tile8`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/a6558c9987528455bd3102b5ac98729452f2ec8f) | 已进入主线历史：tile8 历史源码、位流与约 15 fps 新校正显示记录 | lrt24-thu | `archive/20261103-fisheye-tile8` |
| [`codex/hdmi-input-observer`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/19aed6247f52f4c3312a150d0bbc1aa03c02faea) | 已进入主线历史：HDMI 输入 UART 观察器和 CDC 审计历史 | lrt24-thu | `archive/20261030-hdmi-input-observer` |
| [`codex/hdmi-uart-status`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/03d54ae6834ff1ec4064d886524177ed55fd5d8e) | 已进入主线历史：HDMI I2C/UART 与复位后等待诊断历史 | lrt24-thu | `archive/20261030-hdmi-uart-reset-delay` |
| [`codex/portable-rtl-regressions`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/e61afd45cd21d1d8d8c939496bbe7248f36cc9b4) | 已进入主线历史：可移植 RTL 仿真与变化坐标回归历史 | lrt24-thu | `archive/20261028-portable-rtl-regressions` |
| [`codex/readme-hdmi-bringup`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/ba3a0a21995f3ff8128e667e571f0139ab1e3a68) | 已进入主线历史：HDMI bring-up 状态与接线文档历史 | lrt24-thu | `archive/20261030-hdmi-bringup-docs` |
| [`codex/tile8-cache64-evaluation-20261104`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/bfd1c77c36bc790ecbd19c2fe7a53edde96ac132) | 活跃研究：32→64 KiB 邻域缓存独立评估包，PR29 草稿；未通过物理时序，非硬件放行 | Jason-liu210606 | `experiment/20261104-tile8-cache64-timing-open` |
| [`codex/unify-fpga-projects`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/b73e846316d97ea52ef0dfbcd4155729ae27d058) | 受回退影响历史：PR28 全版本整合历史，已被精确回退；不能直接再次 merge 或 re-revert | Jason-liu210606 | `archive/20261103-unified-projects-reverted` |
| [`delivery/20261029-acceptance`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/048d0328d405ea6cb20264f325d2384c03e627c6) | 冻结交付：10 月 29 日冻结验收证据及 PR10 祖先关系 | zhang-yl24 | `delivery/20261029-acceptance` |
| [`delivery/20261030-b4-readback-pap`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/12f9a5ac34e9d5b4925d6115c2da0117fd47cb68) | 冻结交付：b4 readback/PAP 离线证据冻结包；HardwareReleaseAllowed=false | zhang-yl24 | `delivery/20261030-b4-readback-pap` |
| [`delivery/20261030-tx49-cfg100-ce`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/db4fed4387ee60087609ee2148bcd392e0d351df) | 冻结交付：TX49/CFG100/CE 离线证据冻结包；recovery/覆盖待验收 | zhang-yl24 | `delivery/20261030-tx49-cfg100-ce` |
| [`delivery/20261031-offline-validation`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/2f463a90adf028b792d991f98daf41cdd8c86a3f) | 冻结交付：10 月 31 日离线验证冻结包；HardwareReleaseAllowed=false | zhang-yl24 | `delivery/20261031-offline-validation` |
| [`delivery/20261103-hdmi1080-demo-source`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/1b9727e31f690a2598ab51cdb27ba645c0d5eda5) | 活跃交付：O/P 演示及精确历史上板位流交付祖先；camera/cache64 共用此基线 | zhang-yl24 | `delivery/20261103-hdmi1080-op-board-package` |
| [`delivery/20261104-op-camera-input-diagnostics`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/dbf928e91082e7c81b5a188b8b464726040da0a7) | 活跃交付：摄像头 O/P 首次输入丢失诊断；包含 4 条 setup 违例的诊断位流 | zhang-yl24 | `diagnostic/20261104-camera-op-firstloss-setup-open` |
| [`docs/20261101-hdmi1080p30-plan`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/b246076e8e257871c2e162f7e459de4fe251795b) | 已进入主线历史：电脑 HDMI 1080p30 主线与同学分工计划文档历史 | zhang-yl24 | `archive/20261101-hdmi1080p30-plan-docs` |
| [`main`](https://github.com/zhang-yl24/fpga-distortion-correction/tree/8f2a5b7679ca77153bd36d52a2660e286bff7730) | 共享主线：当前共享主线，含同学 directfill、报告海报和板测资料；本次作为不可覆盖基线 | lrt24-thu | `main` |

## 今后的命名约定

- `main`：同学共享主线；功能与交付验证完成后再按正常审查流程进入。
- `integration/YYYYMMDD-<topic>`：一次可审查的整合，如本次分支。
- `delivery/YYYYMMDD-<pipeline>-<purpose>`：固定来源与身份的交付快照。
- `diagnostic/YYYYMMDD-<pipeline>-<failure>-timing-open`：明确未关闭时序的诊断候选。
- `experiment/YYYYMMDD-<architecture>-timing-open`：未验收的架构或性能研究。
- `fix/<pipeline>-<problem>`、`feature/<pipeline>-<capability>`、`docs/YYYYMMDD-<topic>`：后续明确范围的修复、功能与文档任务。

分支名不使用 `stable` / `60fps-success` 等未经当前完整时序与板测支持的结论。日期固定快照身份；1080p60 扫描、处理模型 FPS 与实测新校正帧 FPS 分开记录。

详细的 [回退与整合决策](docs/branches-20261104/README.md)、[入口差异清单](docs/branches-20261104/source-overlaps.json) 和 [验证结果](docs/branches-20261104/validation.json) 随本分支提供。
