# FPGA 分支导航

**已整理：远端分支从 38 条精简为 13 条。** 25 条历史分支先保存为 `archive/20261107/<原分支名>` 标签，并验证原提交和树，再移除旧远端分支名称。源码和提交历史可恢复。核验时间：2026-11-07 08:13:47 UTC。

## 先选入口

| 要做什么 | 使用入口 | 状态 |
| --- | --- | --- |
| 查看项目、正式交付和报告 | [main 项目说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/136af4fedce0f4e001b455cb5cdbb320a1a124e4/README.md) | 团队共享入口 |
| 测试最新 AA 的 HDMI 摄像头与 KEY1 | [AA 测试候选](https://github.com/zhang-yl24/fpga-distortion-correction/tree/af8ad8149679124c872f37cf37d155b9208daf2c/delivery/20261107-camera1080p60-key1-aa) | 已发布；摄像头新帧率、实体 KEY1 仍需现场验证 |
| 查看 a266 的 1080p30 现场说明与限制 | [30 FPS 版本说明](docs/HDMI1080_30FPS.md) | 现场结果与原始负时序分别保留 |
| 维护同学的 directfill 路线 | `codex/hdmi-camera-fisheye-tile8-directfill` | 保留协作入口，已有成果经 PR #30 入 main |
| 查找或恢复旧分支 | [完成回执与恢复映射](docs/branches-20261107/CLEANUP_RESULT.json) | 25 个标签全部验证，可逐条恢复 |
| 查看源码整合验证 | [接口审计](docs/source-integration-20261104/README.md)、[独立 DDR 单元](integration-units/ddr-read-return-20261104/) | 小单元通过不代表整机或板测通过 |

## 保留的 13 条分支

| 分支 | 用途 |
| --- | --- |
| `codex/hdmi1080-stable30` | 旧 stable30 路线，开放 PR #23 的 head |
| `codex/hdmi1080-throughput` | 旧吞吐路线，开放 PR #22 head / #23 base |
| `codex/hdmi-camera-fisheye-tile8-directfill` | 同学 directfill 维护线，PR #30 已合入 main；保留协作入口 |
| `codex/tile8-cache64-evaluation-20261104` | 64 KiB 缓存研究；PR #29 未合并，时序未过 |
| `delivery/20261103-hdmi1080-demo-source` | O/P、F、E2 基础交付；PR #22/#29 的 base |
| `delivery/20261104-a266044d-timing-review` | a266 独立原始时序证据；与 unified 分叉，独立保留 |
| `delivery/20261104-camera60-key1-unified` | 历史 U/M8 交付；含未闭合时序诊断，不等于实测 60 FPS |
| `delivery/20261104-op-camera-input-diagnostics` | a266 摄像头输入诊断基线；现场 30 FPS 与 4 条负时序并存 |
| `delivery/20261104-op-camera-key1-phase-contract` | KEY1 输入阶段源码候选；本候选无新增位流/最终 STA |
| `delivery/20261104-op-camera-key1-raw-corr` | KEY1 cf9f 诊断候选；内部 STA 通过，摄像头和实体按键仍待验证 |
| `delivery/20261107-camera1080p60-key1-aa` | 当前 AA 摄像头测试候选；已发布，现场验收待完成 |
| `integration/20261104-fpga-branches` | 仓库组织、历史快照、源码契约和独立 DDR 单元验证 |
| `main` | 团队正式导航和共享已收录内容 |

开放 PR 的关系：#22 为 throughput → demo-source；#23 为 stable30 → throughput；#29 为 cache64 → demo-source。相关四个分支和同学维护入口均保留，不因“已经是 main 祖先”自动移除。

## O/P 到 KEY1 的关系

以下为 Git 祖先关系，不是测试通过关系：

1. `delivery/20261103-hdmi1080-demo-source`（1b9727e3）
2. → `delivery/20261104-op-camera-input-diagnostics`（dbf928e9）
3. → `delivery/20261104-op-camera-key1-raw-corr`（8c3fe2a0）
4. → `delivery/20261104-op-camera-key1-phase-contract`（5d53319c）
5. → `delivery/20261104-camera60-key1-unified`（623e7a20）

phase-contract 是源码候选；unified 的分支名含 camera60 也不证明每秒 60 个新校正画面。a266 timing-review 从 diagnostics 独立发展，与 unified 分叉，独立证据入口保留。

**AA 发布提交 af8ad814 直接基于 main 136af4fe，不是旧 unified 的 Git 后继。** 它是独立冻结的测试包，不对旧链做盲目合并，也不把旧 U、cf9f 或 a266 的验证结论移植给 AA。

## 命名与历史保全

- `main`：团队共享入口。
- `delivery/YYYYMMDD-功能-版本`：有固定源码、位流和证据身份的候选/交付；是否验收以具体说明为准。AA 保持现名，不另造别名。
- 现有 `codex/...`：保留有协作或开放 PR 依赖的开发/研究线。后续新开发建议用 `feature/功能` 或 `experiment/功能`，避免同一 SHA 的重复别名。
- `integration/20261104-fpga-branches`：组织工作区，沿用原名，不新增重复整理分支。
- `archive/20261107/原分支名`：本轮 25 个历史**标签**，不是新建 25 条分支。它们精确保留原始提交。

[执行前完整清单](docs/branches-20261107/INVENTORY.json)和[归档/恢复方案](docs/branches-20261107/CLEANUP_PLAN.md)保留审计历史；当前完成状态以[清理回执](docs/branches-20261107/CLEANUP_RESULT.json)为准。

main、AA、directfill 和其余保留分支在清理前后 head 均未变化；4 个原标签全部保留。此次不删除本地分支或工作树，不修改生产 RTL、约束、位流或 EDA 作业。组织说明仅在本 integration 分支更新，尚未合入 main。

PR #28 的统一工程已被回退；其历史 head 已用标签保全，不表示应恢复到当前主线。旧 fisheye60 名称仅表示历史目标，不代表实板性能。

## 既有记录

- [2026-11-04 原分支导航](https://github.com/zhang-yl24/fpga-distortion-correction/blob/170303592e0f735a551fa94a72e852ff0acc9227/BRANCHES.md)
- [原分支审计](docs/branches-20261104/)与[逐日开发历史](docs/DEVELOPMENT_HISTORY.md)
- [源码接口审计](docs/source-integration-20261104/)与[独立 DDR 单元](integration-units/ddr-read-return-20261104/)完整保留。原 5 项 HDL 编译/仿真证据不变，板级整合仍须独立验证。
