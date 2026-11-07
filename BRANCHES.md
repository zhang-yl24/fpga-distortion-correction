# FPGA 分支导航

更新：2026-11-07。以 main `136af4fedce0f4e001b455cb5cdbb320a1a124e4` 和远端 38 条分支快照为准。AA 正在发布，读取固定提交后再测试，不按名称推断性能。

## 先选入口

| 要做什么 | 使用入口 | 状态 |
| --- | --- | --- |
| 查看项目、两套正式 15 FPS 交付和报告 | [main 项目说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/136af4fedce0f4e001b455cb5cdbb320a1a124e4/README.md) | 团队共享入口 |
| 测试最新 AA 的 HDMI 摄像头与 KEY1 | [AA 测试候选](https://github.com/zhang-yl24/fpga-distortion-correction/tree/af8ad8149679124c872f37cf37d155b9208daf2c/delivery/20261107-camera1080p60-key1-aa) | 当前主攻线，发布中；摄像头新帧率、实体 KEY1 尚待实测 |
| 查看 a266 的 1080p30 现场说明与限制 | [30 FPS 版本说明](docs/HDMI1080_30FPS.md) | 现场结果与原始负时序分别保留 |
| 维护同学的 directfill 路线 | `codex/hdmi-camera-fisheye-tile8-directfill` | 保留协作入口，已有成果经 PR #30 入 main |
| 查看历史分支、源码契约和独立单元 | [历史索引](docs/DEVELOPMENT_HISTORY.md)、[源码整合审计](docs/source-integration-20261104/README.md) | 独立单元通过不代表整机或板测通过 |
| 实际减少分支列表 | [25 条归档清单和恢复方案](docs/branches-20261107/CLEANUP_PLAN.md) | 38 → 13 的执行方案；尚未删除或改名 |

## 分支按用途分层

- `main`：团队共享使用说明、正式交付与文档。
- `delivery/YYYYMMDD-功能-版本`：有固定源码/位流/证据身份的候选或交付，是否验收以目录说明为准。AA 保持现名，不额外创建别名。
- `codex/...`：现有开发/研究线。本轮保留正在协作的 directfill 与仍有关联开放 PR 的分支。后续新开发使用 `feature/功能` 或 `experiment/功能`，不要给同一 SHA 批量加别名。
- `integration/20261104-fpga-branches`：本次组织工作区；保留现名以免再加一条重复分支。
- `archive/YYYYMMDD/原分支名`：建议用于**标签**保全历史，不再作为额外分支制造同量拥挤。当前尚未创建这些标签。

## O/P 到 KEY1 的关系

以下为 Git 祖先关系，不是测试通过关系：

1. `delivery/20261103-hdmi1080-demo-source`（1b9727e3）
2. → `delivery/20261104-op-camera-input-diagnostics`（dbf928e9）
3. → `delivery/20261104-op-camera-key1-raw-corr`（8c3fe2a0）
4. → `delivery/20261104-op-camera-key1-phase-contract`（5d53319c）
5. → `delivery/20261104-camera60-key1-unified`（623e7a20）

phase-contract 是源码候选；unified 的分支名含 camera60 也不证明每秒 60 个新校正画面。a266 timing-review 从 diagnostics 独立发展，与 unified 分叉，不能当作可丢弃的同内容别名。

**AA 的发布提交 af8ad814 直接基于 main 136af4fe，不是旧 unified 的 Git 后继。** 它是独立冻结的测试包；不能对旧链做盲目合并、以祖先关系代替源码对应关系。

## 保留与待精简

当前 38 条远端分支中，28 条非 main 分支已是 main 祖先，8 条分叉，AA 在 main 之上有 1 个提交。已筛出 25 条可进入“先标签归档、再移除旧分支”的历史候选；另外 13 条保留。

详见[完整清单与固定 SHA](docs/branches-20261107/INVENTORY.json)及[精简与回退方案](docs/branches-20261107/CLEANUP_PLAN.md)。删除执行前仍必须刷新 head、开放 PR 和工作所有者状态。此次没有删除、重命名分支、修改 AA 或把功能源码合入 main。

PR #28 的统一工程已被回退。历史头可从 Git 取回，不表示应恢复进当前主线；旧 fisheye60/stable30/throughput 的历史合并也不能替代当前内容与验证检查。

## 2026-11-04 的既有成果

- [原分支导航快照](https://github.com/zhang-yl24/fpga-distortion-correction/blob/170303592e0f735a551fa94a72e852ff0acc9227/BRANCHES.md)
- [原分支审计及清单](docs/branches-20261104/)
- [原源码接口审计](docs/source-integration-20261104/)
- [独立 DDR 读返回单元](integration-units/ddr-read-return-20261104/)，5 项 HDL 编译/仿真证据完整保留；尚未据此声明板级整合完成。
