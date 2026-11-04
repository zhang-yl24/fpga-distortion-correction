# 分支整理的精确范围与待解决事项

本分支为基于 main `8f2a5b7679ca77153bd36d52a2660e286bff7730` 的单父提交加法归档。没有运行 `git merge`、re-revert、ours/theirs 冲突解决，也没有将活跃候选标为已合并。main 所有原文件保持相同 blob 与 mode；只新增 `BRANCHES.md`、`docs/branches-20261104/`、`archive/branches-20261104/`。

## 为什么不直接 merge 全部分支

PR #28 的 merge `e1ec8904` 被 `97b13975` 完整回退。回退与 PR 前 `8f365e48` 的真实 tree SHA 相同：`463238e9ad63641826b4d5b79fdb66453aa12238`。该回退删除 2758 文件、修改 `.gitattributes` / `.gitignore` / `README.md`，没有新增文件。

随后 main 新增 1826 文件、修改 3 文件，包括同学 directfill、camera720p15、报告海报和板测证据。直接恢复 PR #28 会重新引入其旧工程入口及源码；本次保留所有当前 main 内容，并将部分历史交付仅保存在独立归档路径。

| 历史候选 | PR 当前状态 | main 历史关系与当前文件状态 |
|---|---|---|
| throughput `bdaf8c15` | #22 open / draft | head 是 main 祖先；交付包 214 文件当前 main 全部缺失 |
| stable30 `e89a2d42` | #23 open / draft | head 是 main 祖先；交付包 226 文件当前 main 全部缺失 |
| fisheye60 `25015cf3` | #25 closed / merged | head 是 main 祖先；交付包 1617 文件当前 main 全部缺失，旧候选时序 FAIL |
| unify `b73e8463` | #28 closed / merged | 内容完整回退；旧 project.py、project-catalog.json、acceptance 与工作流不能自动恢复 |

完整删除/改动路径和 PR 查询记录见 [revert-impact.json](revert-impact.json)。本轮没有恢复这些工程入口或改变上述 PR 状态。需要恢复的功能应按精确源码差异另开任务，先与当前 main 比较，再分别做离线与硬件验收。

## 活跃交付与精确差异

demo `1b9727e3` 是 camera `dbf928e9` 和 cache64 `bfd1c77c` 的共同交付祖先。camera 相对 demo 仅新增 18 个文件；cache64 仅新增 127 个文件。demo 子树只归档一次，camera 的 15 个源码诊断文件与 3 个违例诊断文件、cache64 的 127 文件分别保全。

源分支与当前 main 有 4 个内容不同的既有路径：`.gitattributes`、`.gitignore`、`README.md`、`handoff/CURRENT.md`。它们是精确内容差异清单，不是未经执行的 Git 文本冲突结论。本次均保留 main 原件；源分支的 `hdmi-source-delivery.yml` 工作流也不导入。细节见 [source-overlaps.json](source-overlaps.json)。

最新 directfill `14397de2` 相对 `45223998` 仅修改两行属性、新增一个工作流和 1063 文件独立研究包（88,036,646 字节）。本轮只列目录，不导入其活跃研究包。它仍有时序失败，不能作为 60 帧上板成功证据。

## 本轮验证

- 完整 main 13055 条树条目重新构造 Git tree 哈希，等于 `93b06e5ba395bd80ded06828783bb58050405fa3`；4 个导入子树也重新计算并匹配原 SHA。
- 600 个可读取文件完成字节数、Git blob SHA、SHA256 核验；两份位流用精确原始 blob/子树及原包身份绑定，未本地重算其二进制 SHA256。发布后还须核对远端归档子树和所有 main 原对象。
- demo 包清单 455/456 项原文哈希核验，一份二进制位流采用对象身份保全；其 50 项随包源码全部匹配，80 项外部依赖仍需要。
- camera 包 14 项清单、5 项导出源码哈希通过；cache64 112 项清单与 111 项输入重定位准备通过。Windows 普通长路径首次准备失败，使用扩展路径后通过，源文件未更改。
- [verify_integration.py](verify_integration.py) 可在有完整对象的克隆里再次核对所有 602 个归档文件，包含两份二进制 SHA256。

没有运行 RTL 仿真、PDS、布局布线、STA、SRAM 下载或 Flash 操作。原提交历史 CI success 只说明原快照的离线检查，不替代本次组合验证或硬件门禁。摄像头时序修复、60 帧 scout-local-a 上板和同学 directfill 研究均继续保持各自负责人和工作区；本轮没有访问其构建目录。

本分支只发布归档与目录：现有分支数量与原名保留，main 与 PR 状态均不修改；后续删除/改名不是本轮执行内容。精确元数据和验证限制见 [validation.json](validation.json)。
