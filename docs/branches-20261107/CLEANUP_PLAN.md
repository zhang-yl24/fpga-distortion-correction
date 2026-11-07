# 分支精简与回退方案

快照：2026-11-07 08:01:54 UTC，main `136af4fedce0f4e001b455cb5cdbb320a1a124e4`。完整机器可读清单：[INVENTORY.json](INVENTORY.json)。

## 具体结果

建议将 **38 条远端分支减少到 13 条**：25 条历史分支先保全为固定标签，核验后再移除旧分支。**本提交只提供方案，未创建标签、删除或改名任何分支。** 这不是把所有分支机械合并成一套 FPGA 工程。

25 条候选均满足：head 是 main 祖先（ahead=0），当前 3 个开放 PR 均不以其为 head/base。所有 head 完整 SHA 已记录。Git 可达性说明历史可恢复，不说明其文件今天都在 main；PR #28 回退尤其如此。

已经检查 main 的全部 6 个 workflow 文件：未发现这 25 个分支名的显式依赖。工作流引用的是仓库目录，不是同名远端分支。未据此保证外部脚本、同学本地 worktree 或未提交工作没有依赖；执行前须确认这部分。

## 第一批：25 条历史归档候选

采用轻量标签 `archive/20261107/原分支名` 指向下面的原始提交；标签对象须解析回同一提交。不要创建 25 条 archive 分支，否则列表不会减少。

| 旧分支 | 必须保存的原 head | 建议归档标签 |
| --- | --- | --- |
| `codex/board1080-rowpipe` | `31f7df667e830ca6a3e0ae0a3b261b1fcd8112e9` | `archive/20261107/codex/board1080-rowpipe` |
| `codex/camera720-output` | `3dfcab39d0437ae14025e75837116da491ce277c` | `archive/20261107/codex/camera720-output` |
| `codex/camera720-view-toggle` | `30ce89b6639b8183bafdf6897f4e2cfe09556adf` | `archive/20261107/codex/camera720-view-toggle` |
| `codex/camera-vga-calibrated` | `90f6e4a0f23aa253f098144a00a7c656897d04e9` | `archive/20261107/codex/camera-vga-calibrated` |
| `codex/camera-vga-upright` | `0643c1856175a3963d01a3d47f07ad121776fda8` | `archive/20261107/codex/camera-vga-upright` |
| `codex/ddr-ip-timing-fix` | `18f6f036eb483120c2b900fff7d28259b3221819` | `archive/20261107/codex/ddr-ip-timing-fix` |
| `codex/ddr-recovery-diagnosis` | `cc596af563803b07ef7ab06aa8d6df903d80fe28` | `archive/20261107/codex/ddr-recovery-diagnosis` |
| `codex/dvp-capture-cdc` | `7cb0236eacd999eb00bc0626151d9ac6ee4846fd` | `archive/20261107/codex/dvp-capture-cdc` |
| `codex/fisheye60` | `25015cf3b2c1c31d7940828ac583d5d1eb6feeb3` | `archive/20261107/codex/fisheye60` |
| `codex/fix-portable-ci` | `4903f7d9bd72e70a0375fcdf0ad2c56b18d801a1` | `archive/20261107/codex/fix-portable-ci` |
| `codex/hdmi-camera1080-bringup` | `ee45af47e2d01859f8cb203dbacdacaacf713d61` | `archive/20261107/codex/hdmi-camera1080-bringup` |
| `codex/hdmi-camera1080-display` | `214cc2ece823737d384d68350f6b5679c18c210b` | `archive/20261107/codex/hdmi-camera1080-display` |
| `codex/hdmi-camera1080-fisheye` | `c53fdecc5dfce176700d8d6160a6ee458e1689d3` | `archive/20261107/codex/hdmi-camera1080-fisheye` |
| `codex/hdmi-camera-fisheye-fill8` | `13e5aac346b6d85a2716d81ebc07cbc3bc73668e` | `archive/20261107/codex/hdmi-camera-fisheye-fill8` |
| `codex/hdmi-camera-fisheye-tile8` | `a6558c9987528455bd3102b5ac98729452f2ec8f` | `archive/20261107/codex/hdmi-camera-fisheye-tile8` |
| `codex/hdmi-input-observer` | `19aed6247f52f4c3312a150d0bbc1aa03c02faea` | `archive/20261107/codex/hdmi-input-observer` |
| `codex/hdmi-uart-status` | `03d54ae6834ff1ec4064d886524177ed55fd5d8e` | `archive/20261107/codex/hdmi-uart-status` |
| `codex/portable-rtl-regressions` | `e61afd45cd21d1d8d8c939496bbe7248f36cc9b4` | `archive/20261107/codex/portable-rtl-regressions` |
| `codex/readme-hdmi-bringup` | `ba3a0a21995f3ff8128e667e571f0139ab1e3a68` | `archive/20261107/codex/readme-hdmi-bringup` |
| `codex/unify-fpga-projects` | `b73e846316d97ea52ef0dfbcd4155729ae27d058` | `archive/20261107/codex/unify-fpga-projects` |
| `delivery/20261029-acceptance` | `048d0328d405ea6cb20264f325d2384c03e627c6` | `archive/20261107/delivery/20261029-acceptance` |
| `delivery/20261030-b4-readback-pap` | `12f9a5ac34e9d5b4925d6115c2da0117fd47cb68` | `archive/20261107/delivery/20261030-b4-readback-pap` |
| `delivery/20261030-tx49-cfg100-ce` | `db4fed4387ee60087609ee2148bcd392e0d351df` | `archive/20261107/delivery/20261030-tx49-cfg100-ce` |
| `delivery/20261031-offline-validation` | `2f463a90adf028b792d991f98daf41cdd8c86a3f` | `archive/20261107/delivery/20261031-offline-validation` |
| `docs/20261101-hdmi1080p30-plan` | `b246076e8e257871c2e162f7e459de4fe251795b` | `archive/20261107/docs/20261101-hdmi1080p30-plan` |

其中 `codex/unify-fpga-projects` 必须标记“已回退”；旧 `codex/fisheye60` 必须标记“历史实验，不能由名称宣称 60 FPS”。这些头不需要再次 merge 才能归档。

## 暂保留：13 条

| 分支 | 快照 head | 保留理由 |
| --- | --- | --- |
| `codex/hdmi1080-stable30` | `e89a2d42` | 旧 stable30 路线，开放 PR #23 的 head |
| `codex/hdmi1080-throughput` | `bdaf8c15` | 旧吞吐路线，开放 PR #22 head / #23 base |
| `codex/hdmi-camera-fisheye-tile8-directfill` | `421f7cc9` | 同学 directfill 维护线，PR #30 已合入 main；保留协作入口 |
| `codex/tile8-cache64-evaluation-20261104` | `bfd1c77c` | 64 KiB 缓存研究；PR #29 未合并，时序未过 |
| `delivery/20261103-hdmi1080-demo-source` | `1b9727e3` | O/P、F、E2 基础交付；PR #22/#29 的 base |
| `delivery/20261104-a266044d-timing-review` | `8e88b396` | a266 独立原始时序证据；与 unified 分叉，独立保留 |
| `delivery/20261104-camera60-key1-unified` | `623e7a20` | 历史 U/M8 交付；含未闭合时序诊断，不等于实测 60 FPS |
| `delivery/20261104-op-camera-input-diagnostics` | `dbf928e9` | a266 摄像头输入诊断基线；现场 30 FPS 与 4 条负时序并存 |
| `delivery/20261104-op-camera-key1-phase-contract` | `5d53319c` | KEY1 输入阶段源码候选；本候选无新增位流/最终 STA |
| `delivery/20261104-op-camera-key1-raw-corr` | `8c3fe2a0` | KEY1 cf9f 诊断候选；内部 STA 通过，摄像头和实体按键仍待验证 |
| `delivery/20261107-camera1080p60-key1-aa` | `af8ad814` | 当前 AA 摄像头测试候选；发布中，禁止清理/改名/合并其 head |
| `integration/20261104-fpga-branches` | `17030359` | 仓库组织、历史快照、源码契约和独立 DDR 单元验证 |
| `main` | `136af4fe` | 团队正式导航和共享已收录内容 |

- PR #22：throughput → demo-source；PR #23：stable30 → throughput；PR #29：cache64 → demo-source。四个相关分支不得在开放 PR 状态下随意重命名或删除。
- O/P → diagnostics → raw-corr → phase-contract → unified 已确认连续祖先关系。但它们目前没有全部进入 main，且板测、位流、时序身份不同，第一批不移除。
- a266 timing-review 与 unified 是分叉关系（相对 unified，独有 12 个提交、缺 7 个提交），保持独立证据入口。
- AA 当前 af8ad814 基于 main，仍在发布/现场验证阶段。其摄像头帧率与按键验证不可从旧 U、cf9f 或 a266 继承。本轮不修改 AA 的 ref、文件或 PR。
- integration 需要先与主线组织改动对齐并审阅；其 DDR 小单元不能擅自接进 AA 或同学 fill8r2 路径。

## 执行顺序与停止条件

1. 刷新完整分支和开放 PR 清单。对 25 条逐项校验当前 head 仍等于本表 SHA；任何变化则跳过该条并重新评估，不强推覆盖。
2. 确认候选分支没有继续工作的所有者、未推送本地工作、外部自动化或以分支名为入口的下载链接。已合并不等于已无人使用。
3. 只创建标签，不先删除。对每个标签读回解析的完整提交 SHA，并核对其树与原分支头一致；保存核验回执。
4. 需要继续使用旧分支名的链接改为固定提交链接；开放 PR 不作自动关闭/改基底。先保留本清单作为操作日志。
5. 获得本轮实际移除范围的确认后，仅删除通过前四步的远端旧分支。删除前再次比对 head，遇到新增提交立即停止该条。main、AA、13 条保留分支不在删除集合。
6. 重新列举远端 refs，核验 25 个归档标签、全部保留分支的 SHA 未变。若期间新增其他分支，真实最终数量需按当时快照重算，不硬凑 13。

## 回退

恢复任意旧分支时，从本清单或已核验标签取原完整 SHA，再在同一仓库创建同名分支指向它。示例：

```text
git push origin 31f7df667e830ca6a3e0ae0a3b261b1fcd8112e9:refs/heads/codex/board1080-rowpipe
```

这只是恢复示例，本轮未执行。恢复前先确认旧名尚不存在；若已有人重建同名分支，不覆盖、不强推。标签保留为第二恢复入口。原提交本来可从 main 历史到达，但仍先建立并读回标签，不依靠 reflog 或 GitHub 的自动恢复功能。

## 可合入 main 的组织改动

当前 integration 将最新 main 的现有文件保留，只叠加既有 archive、单元和审计目录，并更新导航。下一步可选择：

- **最小文档路径（推荐先做）：** 从最新 main 建立一次仅文档提交，加入 BRANCHES.md、此目录与清单，并加 README/REPOSITORY_GUIDE 入口。对涉及旧 integration 审计目录的链接使用固定提交 URL；不需要把历史源码归档重拷进 main。
- **完整组织分支合入：** 审阅 integration 与 main 差异，只允许导航、历史归档和独立单元新增，不改变现有生产源码/约束/位流。完成 CI 后再合入。此操作不是 AA 功能验收。

无论选择哪种，都先确认 main 的最新 head，使用正常非覆盖提交。第一批分支精简不要求把已回退内容重合并，也不要求等待新的 FPGA 布局布线。
