# 历史分支与恢复

## 第一轮：38 → 13

25 条历史分支已经在 2026-11-07 先打标签、核验，再移除旧远端名称。[第一轮原始回执](https://github.com/zhang-yl24/fpga-distortion-correction/blob/58490f3345e4a53b915b20768ac867f6f66f13c4/docs/branches-20261107/CLEANUP_RESULT.json)保留全部原 SHA、归档标签和恢复命令。原有四个旧标签未改变。

## 第二轮：五条历史交付，13 → 8

于 2026-11-07 08:48:37 UTC 核验完成：先创建 `archive/20261107/<原分支名>` 轻量标签并读回 commit/tree，再通过精确 SHA 保护原子移除五个旧 head。它们不是 main 的冗余副本，各自独有历史仍完整保留。

| 原分支 | 固定提交 | 固定树 |
| --- | --- | --- |
| `delivery/20261104-a266044d-timing-review` | `8e88b3962fc03ca20c92761720f41ab886d3d34c` | `f7236c306a1e4f514622afe617de86f50890e591` |
| `delivery/20261104-camera60-key1-unified` | `623e7a20cbb00d4b0da8047fcab3dce4852d3ca9` | `a55d654b4191f2c7cc63d5cf32678db3452c1f95` |
| `delivery/20261104-op-camera-input-diagnostics` | `dbf928e91082e7c81b5a188b8b464726040da0a7` | `a97c1d4b166017fe6b142b4adcb3d08b3cdb4d29` |
| `delivery/20261104-op-camera-key1-phase-contract` | `5d53319c4167596cd2f577c65a3b2d8dfd54494d` | `a9a449a848223065b9f6502920457ce969bfb5a5` |
| `delivery/20261104-op-camera-key1-raw-corr` | `8c3fe2a05ae56e3338a495f5085d489506352439` | `92727c90918b0ceb1eefb6f695461a601978d609` |

这些头无开放 PR head/base 依赖，已知工作区未占用。诊断、raw-corr、phase 的目录在 unified 中字节相同，但 a266 timing-review 是独立证据侧线。均未因此重新合入生产 RTL。

核查了完整递归树，无子模块/gitlink、.gitmodules 或 .lfsconfig；相应两种属性文件无 LFS filter，32 个 110–200 字节指针候选无命中。此为有范围的检查，不把非标准大指针或缺失外部资料说成已备份。厂商 IP/PLL 原件、私有构建输入和外部资产不由 Git 标签补齐。

## 整理线收尾：8 → 7

本次组织内容通过核验后，正常进入 main，并将临时 `integration/20261104-fpga-branches` 保存为同名归档标签后移除。标签全名：

`archive/20261107/integration/20261104-fpga-branches`

它指向本次最终组织提交；Git 中仍可到达旧 `58490f3345e4a53b915b20768ac867f6f66f13c4` 的完整归档/单元树。当前主线不重复复制这些目录，不代表其历史被删除。实际发布以远端 main 与标签读回核验为准；CI候选期间该步骤属于发布事务的一部分。

## 恢复任一旧分支

1. 从映射取原完整 SHA，或读取对应 archive 标签；核对 commit/tree。
2. 确认同名分支尚不存在。若已有新的同名工作，不覆盖。
3. 将该 SHA 创建为同名远端分支，例如：

```text
git push origin 8e88b3962fc03ca20c92761720f41ab886d3d34c:refs/heads/delivery/20261104-a266044d-timing-review
```

只恢复 Git 内容，不会自动恢复厂商输入、运行 EDA、下载开发板或改变历史验证结论。不要以强推覆盖他人后来重建的同名分支。
