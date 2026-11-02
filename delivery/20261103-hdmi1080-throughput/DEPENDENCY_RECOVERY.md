# 原生依赖恢复与校验

冻结演示工程清单共 130 项：50 项项目源码保存在相邻的
`20261103-hdmi1080-demo-source/native/`，80 项原生依赖已在本地恢复。
每项恢复结果都与原清单的字节长度、SHA256 完全一致。

本地完整包采用以下相对布局：

```text
fpga1080/
  native-dependencies/source/...
  delivery/20261103-hdmi1080-demo-source/...
  delivery/20261103-hdmi1080-throughput/...
```

## 校验完整包

从解压根运行：

```powershell
python -B delivery/20261103-hdmi1080-throughput/tools/recover_native_dependencies.py --verify-only --out native-dependencies
```

脚本默认相对自身定位冻结清单。`--out` 必填；`--verify-only` 仅读取该目录和清单，
无需 `--repo`、Git、网络、原电脑路径或 EDA，也不会修改附带文件。
预期结果为 `passed: true`、`required: 80`、`matched: 80`。

若清单单独保存，可指定 `--manifest path/to/source-manifest.json`。
缺文件、长度变化、SHA 不一致或越界路径均会报错。校验通过后，
将 `native-dependencies` 传给候选准备工具的 `--dependency-native`。

## 从本地源码重新恢复

具备仓库内对应 `distortion/` 源码时，从仓库根运行：

```powershell
python -B delivery/20261103-hdmi1080-throughput/tools/recover_native_dependencies.py --repo . --out ../native-dependencies
```

恢复过程无需 Git 历史。77 项直接匹配本地源码；必要时只规范换行并检查最终哈希。
另外三项按历史修改还原：

| 文件 | 变换 |
| --- | --- |
| `iic_dri_cfg100_reset.v` | 模块重命名，给 `trans_en`、`busy` 加入同步复位分支 |
| `ms7210_ctl.v` | 对 INIT 最后一次触发增加 `dri_cnt != 18` 条件 |
| `ms7200_1080p30_ctl.v` | 将现有 rearm 控制模块重命名为封存版本的模块名 |

所有变换均保留在脚本中，只有输出匹配冻结 SHA 后才写入目标目录。
已有不同内容的文件会被拒绝覆盖。原厂文件与许可证保持原样。
恢复目录会生成 `recovery-report.json`，记录每项来源哈希、变换和结果身份。

## 已执行的验证

`evidence/dependencies/` 保存本次结果：

- 从本地源码重新恢复全部 80 项，逐项核验通过。
- 不传 `--repo` 校验全部 80 项，校验前后文件哈希保持一致。
- 在仅有随包清单、脚本和依赖的解压布局中，以相对路径校验通过。
- 修改一个依赖后校验失败，工具保持损坏文件原样，未自动修复。
- 未提供 `--out` 时正确拒绝；显式清单在其他工作目录中可用。

这些验证确认源码依赖身份。候选的整机编译、时序与上板结果由对应构建回执记录。
