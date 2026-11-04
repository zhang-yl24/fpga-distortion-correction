# 竞赛代码包导出

`package_submission.py` 从一个已提交 Git 快照读取原始 blob。不会读取工作区未提交源码，
不会 checkout、改分支、运行 EDA、仿真或硬件，也不会创建 RAR。

先完成提交，再用新目录导出：

```text
python -B tools/package_submission.py --ref HEAD --output <全新目录> --plan-only
python -B tools/package_submission.py --ref HEAD --output <全新目录>
```

准备目录已存在时拒绝继续。源提交必须包含 directfill v3 的实际 110 项生产闭包和冻结当前包，
否则导出失败。即使工作区有未提交修改，也只导出 `--ref` 指定的原始提交字节。

保留全部作者代码/脚本/约束/常见测试向量、当前完整 tile8/directfill 结果包、所有展开的
delivery 目录、必要平台 DDR/PLL/IP 源及 C/S3/tile8 各版源清单引用的正式 bit。
剔除嵌套发布压缩包、其他旧 results 非代码数据、原始采集图像、vendor 参考文档与历史构建数据、
缓存及环境目录。所有排除文件列出路径、Git blob、大小、原因和代码标记，不静默省略代码。
本轮以完整 manifest 及源闭包优先，未压缩文件可能略大于 200 MiB。

导出会生成 `START_HERE_SUBMISSION.md`、included SHA256 清单、excluded 明细及独立只读验证器。
随包运行 `python -B VERIFY_SUBMISSION.py` 可验证每份 included 文件字节；清单自身不列自身哈希。
最终 RAR 应另做 `Rar.exe t`、解压后逐文件校验及 **小于 200,000,000 字节** 的硬检查。
不要把 ZIP 改后缀冒充 RAR。

Windows 旧交付含超过 260 字符的路径，导出器和独立 SHA 验证器自动使用扩展路径。
原有验证脚本应以扩展绝对路径启动，使其内部路径继承扩展前缀，例如：

```powershell
$taskPrefix = [string][char]92 + [char]92 + '?' + [char]92
$taskEntry = $taskPrefix + (Resolve-Path ./delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py).Path
$taskPackage = $taskPrefix + (Resolve-Path ./distortion/results/hdmi-camera-fisheye-tile8-20261103-a).Path
python -B $taskEntry --package $taskPackage
```

较早长路径 probe 上，tile8 / fill8 / fisheye-c 源闭包和 directfill 完整 portable 校验均通过；
该记录仅属于其原快照。实际 RAR 仍需解压后按新的最终清单再验，不能沿用旧包结论。

PR #28 的统一入口及其新增实验聚合已按要求撤回。当前源包只导出新提交实际保留的文件，
不依赖被撤回的统一入口或目录表，不重新加入被撤回的实验目录；直接使用各交付脚本。

建议在新 stage 内执行：

```text
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B delivery/20261103-hdmi-camera-fisheye-fill8/verify_source.py
python -B delivery/20261103-hdmi-camera-fisheye-c/verify_source.py
python -B distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py --manifest portable-evidence-manifest-c.json
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py --package distortion/results/hdmi-camera-fisheye-tile8-20261103-a
```

完整旧 results 原始数据已被有记录地裁剪；本包不宣称全仓所有历史测量回放均可执行。
当前 directfill 没有独立便携 `prepare_build.py`，旧 tile8 prepare 绑定旧 bit，不能冒称重建当前 bit。
准确重建边界、编译快照和依赖见包内启动说明及原交付 README。

导出工具自身测试：

```text
python -B -m unittest discover -s tools/tests -p test_package_submission.py -v
```
