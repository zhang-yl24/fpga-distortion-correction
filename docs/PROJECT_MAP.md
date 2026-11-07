# 项目脉络与文件入口

## 当前统一目标

后续开发和发布围绕 **HDMI 摄像头 1920×1080、标称 60 Hz 输入，KEY1 在 RAW／CORR 之间切换，不另加旋转**。当前 AA 默认 CORR、Gamma 关闭。60 Hz 是输入/扫描时序，不能代替每秒新校正帧的实测结果。

当前入口为 [AA 固定交付 87cf6ca4](https://github.com/zhang-yl24/fpga-distortion-correction/blob/87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99/delivery/20261107-camera1080p60-key1-aa/README.md)。[测试流程](https://github.com/zhang-yl24/fpga-distortion-correction/blob/87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99/delivery/20261107-camera1080p60-key1-aa/TEST_INSTRUCTIONS.md)与[重建流程](https://github.com/zhang-yl24/fpga-distortion-correction/blob/87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99/delivery/20261107-camera1080p60-key1-aa/rebuild/README.md)分别使用，不混为一项验收。

源码核对结果：`RATIONAL_BROWN_PROFILE=1` 使 `ENABLE_RUNTIME_ROTATION=0`，`cfg_rot_cos=2^30`、`cfg_rot_sin=0`。KEY1 的 C23 输入经同步和 20 ms 消抖，只改变请求 RAW/CORR；模式在 `source_valid && source_ready` 时锁存。保留历史 rotation 模块文件不表示当前选中旋转功能。RAW 也经过 DDR、采样和 RGB565 量化，不是 HDMI 物理直通。

## 把已有成果串起来

| 阶段 | 解决了什么 | 本轮如何使用 | 不能混淆的边界 |
| --- | --- | --- | --- |
| DVP/VGA → 720p | 采集、标定、CDC、完整帧控制和 KEY1 的早期来源 | 保留独立 720p15 基线与原证据 | 是另一输入路线，不作当前默认工程 |
| HDMI C → fill8 → tile8 → directfill | HDMI 输入、鱼眼映射、DDR 缓存/写回和显示交接逐步落地 | 同学 directfill 维护线及已验证 1080p15 回退继续保留 | 15 FPS 指新画面，不能用显示扫描率替代 |
| O/P、F、E2 → a266 输入诊断 | 前瞻预取、帧所有权、输入资格与首故障定位 | O/P 基础仍为 PR 基底；a266 可追溯摄像头 30 FPS 现场说明和原时序 | a266 有 4 条 setup 负裕量，且旧 a266 不含 KEY1 |
| KEY1 cf9f → phase-contract → U/M8 | 引入 RAW/CORR 请求，推进输入资格、启动/模式交接 | 五条历史交付已用标签保全；按固定提交阅读和复用 | cf9f PC 输入未准入；phase 未完成实现；U/M8 名称不是 60 FPS 验收 |
| AA | Rational Brown 路线、缓存/DDR 优化、KEY1、同版遥测与重建补充 | 当前摄像头测试与后续工作唯一默认入口 | 内部 STA 通过与现场功能、全新重建分开验收 |
| 独立 DDR 读返回单元 | 对仲裁器/返回寄存/错误隔离做五项 HDL 测试 | 保留为可复用研究证据 | 没有因此替换 AA 或同学 fill8r2 整链 |

这些是功能演进关系，不是说所有 Git 分支都已合并成一个可构建顶层。实际 Git 链为 demo-source → diagnostics → raw-corr → phase-contract → unified；a266 timing-review 是独立证据侧线。AA 发布链直接基于 main，再追加复现工具，不能把旧 unified 的全部功能和验证结论移植给 AA。

## AA 已有与待验

- 已公开：78 份项目源码、固定 SRAM 位流、12 项内部时序表、测试与同版遥测说明。
- 复现补充：371 项 DDR 参数、PLL 参数、严格核对工具、155 文件闭包和 68 项有序导入、PDS 分阶段脚本。合法匹配原输入补齐后的静态闭包已检查。
- 仍需使用者合法生成/恢复 77 项厂商 IP/PLL 输入。工具生成版本与实现版本分别记录，不能随意替换模型。
- **未完成**：全新 IP 生成、公开路径副本的完整重新实现、持续摄像头新帧率、实体 KEY1、完整外部 IO/CDC/reset 签核。
- 位流 SHA256：`1665586da54bdbf5ed8cefa7d0bbe35f3cbb0219e03ae060fa68f6dfdb717f8a`。最差 setup +0.003 ns、hold +0.044 ns；3 ps 不是宽裕余量。

## 按任务找文件

| 需要 | 入口 | 文件处理原则 |
| --- | --- | --- |
| 当前 AA 运行/重建 | 上方固定交付及 [机器可读项目索引](PROJECT_INDEX.json) | 当前候选按固定 SHA，后续在原工作线补充 |
| 已有正式交付/报告 | [仓库使用导航](REPOSITORY_GUIDE.md)、[submission](../submission/README.md) | 不用新候选覆盖已验证证据 |
| RTL、板级与约束 | `distortion/rtl`、`distortion/board` 与各冻结包实际选中输入 | 同名不代表同一版本；以源绑定/编译输入为准 |
| 主机工具、仿真与校验 | `distortion/tools`、`distortion/tests`、`tools` | 不绕过现有 verifier 和失败门槛 |
| 厂商依赖 | `distortion/platform`、`vendor` 及具体包的 IP 说明 | 保留归属；不以占位源码伪装闭包 |
| 实验/构建/板测证据 | `distortion/results`、`handoff` 与交付报告 | 位流、源 SHA、约束、STA 与板测要绑定同版 |
| 逐个文件/重复族查询 | [全文件联合清单](file-inventory/PROJECT_FILES.csv)、[盘点摘要](file-inventory/SUMMARY.json) | 全量覆盖本轮 13 个固定头；一行唯一 path/blob，不重复抄多份整树 |
| 旧分支恢复 | [分支与归档](../BRANCHES.md) | Git 标签保全源码与历史，不代替缺失厂商输入 |

## 为什么不按文件名把目录大搬家

被冻结的 720p/directfill 包有相对路径和哈希清单校验；原 archive 校验固定 602 文件与 4 棵子树；CI 指向 `distortion` 的具体路径，Tcl/include 与 IP 生成结果也有绑定。blob 相同只说明字节相同，不说明某副本可以从它所在交付中删除。

本轮实际整理的是：收敛工作分支、统一主线入口、建立全文件索引与版本/验证关系、保留冻结源码路径；没有把重复 blob 当作垃圾删掉。Git 本身已按 blob 去重，清单中的逻辑字节总和不是 Git 压缩下载大小。

旧整理分支中新增的整套 archive 副本和 DDR 小单元不再次复制到 main 根目录。它们保留在 [58490f3 的完整快照](https://github.com/zhang-yl24/fpga-distortion-correction/tree/58490f3345e4a53b915b20768ac867f6f66f13c4)及可达历史中；从这里的固定入口访问即可。

## 同学协作保留

[#22](https://github.com/zhang-yl24/fpga-distortion-correction/pull/22) throughput、[#23](https://github.com/zhang-yl24/fpga-distortion-correction/pull/23) stable30、[#29](https://github.com/zhang-yl24/fpga-distortion-correction/pull/29) cache64 都保留。#23 依赖 throughput，#22/#29 依赖 demo-source；作者与同学的待合工作不能仅为凑分支数量而关闭。throughput/stable30 虽出现在 main 的祖先历史，其目录曾随 PR #28 回退，当前不等于被 AA 完整替代。

后续发布遵守[固定发布流程](PUBLISHING.md)：复用已有工作线、main 做统一入口、固定标签记录版本，不每次交付都建新的日期分支。
