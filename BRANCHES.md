# 分支选择与归档

## 常驻分支：7 条

| 分支 | 用途 | 为什么保留 |
| --- | --- | --- |
| `main` | 项目统一入口、已收录文件和协作主线 | 从这里找当前候选、历史证据和报告 |
| `delivery/20261107-camera1080p60-key1-aa` | 当前 1080p60 摄像头＋KEY1 工作线 | 后续复现/验证补充沿用它，不每次建新分支 |
| `codex/hdmi-camera-fisheye-tile8-directfill` | 同学维护的 directfill 路线 | 保留协作边界 |
| `codex/tile8-cache64-evaluation-20261104` | cache64 研究 | 开放 PR #29 的 head |
| `delivery/20261103-hdmi1080-demo-source` | O/P、F、E2 基础与 PR 基底 | 开放 PR #22/#29 的 base |
| `codex/hdmi1080-throughput` | 同学吞吐研究 | PR #22 的 head、#23 的 base |
| `codex/hdmi1080-stable30` | 同学 stable30 研究 | PR #23 的 head |

这七条是保持当前目标、同学协作和三个开放 PR 后的最小整理范围。PR #22/#23 的提交虽存在于 main 历史，但相关目录曾随 PR #28 回退；不能因此认定功能已被 AA 完整替代或同学已放弃。三个 PR 不关闭、不改基底。

整理过程中暂用的 `integration/20261104-fpga-branches` 在组织内容核验并进入 main 时一并归档移除，不作为第八条常驻开发线。

## 从哪里开始

- [当前目标、成果脉络和文件入口](docs/PROJECT_MAP.md)
- [固定版本/验证状态索引](docs/PROJECT_INDEX.json)
- [全部 13 个审计头的文件联合清单](docs/file-inventory/PROJECT_FILES.csv)
- [以后如何发布](docs/PUBLISHING.md)

当前默认是 HDMI 摄像头 1920×1080、标称60 Hz输入，KEY1切 RAW/CORR，不另加旋转。当前 AA 发布 SHA 为 `87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99`；内部时序与现场新帧率/按键验收分开理解。

## 历史如何保留

先后整理的旧分支均保存为 `archive/20261107/<原分支名>` 标签，完整提交和树经读回验证后才移除旧名称。先从 38→13，再归档五条历史交付，并收掉临时整理线后保留上面的七条。

- [第一轮25条的完整恢复映射](https://github.com/zhang-yl24/fpga-distortion-correction/blob/58490f3345e4a53b915b20768ac867f6f66f13c4/docs/branches-20261107/CLEANUP_RESULT.json)
- [第二轮五条及整理线的归档说明](docs/BRANCH_ARCHIVES.md)
- [旧整理成果完整快照](https://github.com/zhang-yl24/fpga-distortion-correction/tree/58490f3345e4a53b915b20768ac867f6f66f13c4)，包含原 archive、源码接口审计和独立 DDR 单元。新 main 不重复抄入这些大目录，历史仍可访问和恢复。

归档不等于功能合并或硬件通过。尤其 PR #28 的已撤回工程、旧 fisheye60、U/M8 和失败诊断，都保持原始验证状态，不能靠分支名字提升为当前正式版本。
