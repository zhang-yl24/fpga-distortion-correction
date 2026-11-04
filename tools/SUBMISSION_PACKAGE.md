# 两套选定工程的竞赛代码包

`package_submission.py` 从已提交 Git 快照读取原始 blob，导出 **OV5640 720p15 原图／校正切换**与 **HDMI 1080p15 directfill INDEX8 v3** 两套工程。本轮只整理保存的源码与证据，不访问硬件；不读取未提交源码、切换分支、运行 EDA 或创建 RAR。

先提交两套独立交付及材料，再指定全新目录：

```text
python -B tools/package_submission.py --ref HEAD --output <全新目录> --plan-only
python -B tools/package_submission.py --ref HEAD --output <全新目录>
```

输出目录已存在即拒绝继续。`--plan-only` 检查所需清单及 Git 条目、统计选择范围；正式导出逐项核对原始 Git 字节及落盘 SHA256，并自动执行包内四个只读校验入口。缺少已提交的源码、位流或报告时失败，不把工作区未提交文件补入包中。

## 保留范围

- 完整 `delivery/20261104-camera720p15/`：正式位流、369项冻结源码／构建输入、18项原生报告及独立校验器。
- 完整 `distortion/results/camera720-view-toggle-live-20261102-a/` 与包外同名 `.json`：206项原封存文件及汇总，含原位流 gzip、板测和构建身份。
- `delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/` 与同层 `reports/`：110项生产输入、RCF、6份编译差异、唯一正式位流、同版板测与原生报告。
- 完整 `submission/`：报告、参数、海报和离线补充证据；以及导出器明确列出的少量报告／打包支持文件。实物照片待用户提供后另行补入。

720p的 `source-manifest.json`、`reports-manifest.json` 与1080p独立 `source-manifest.json` 的相对路径、字节数和 SHA256均强校验；1080p `report_files` 只相对固定 `reports/` 根解析。来源字段 `original_path` 仅供追溯，不作为本机路径读取或执行。原始报告 gzip保留原字节，解压身份由所选交付校验器核对。

720p位流 SHA256：`0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5`。
1080p位流 SHA256：`aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b`。
导出器检查所有选中文件中 `.sbit`／`.bit`（含 gzip）的身份，拒绝混入其他位流。

旧C、S3、旧tile8、throughput、stable30等其他路线的交付、位流、实验源码和历史数据不进入本包。这些文件仍保留在仓库；逐项裁剪原因写入 `SUBMISSION_EXCLUDED_FILES.json`。`ExcludedCodeFiles` 允许大于零，表示有记录裁剪的其他路线／历史／非必要支持代码，不是选定工程源闭包缺失；本包不宣称包含全仓历史实验。PR #28统一入口已撤回，本工具不依赖 `project.py` 或 catalog，也不重新引入其目录。

## 解压后校验

只需 Python 3.10+ 标准库，无需 Git、PDS 或板卡：

```text
python -B VERIFY_SUBMISSION.py
python -B delivery/20261104-camera720p15/verify_selected.py
python -B distortion/results/camera720-view-toggle-live-20261102-a/verify_bundle.py --summary distortion/results/camera720-view-toggle-live-20261102-a.json
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/verify_selected.py
```

导出器自动运行以上四项。Windows扩展路径由导出器及新的独立校验器处理；原720归档校验器在深路径下的启动方式见包根 `START_HERE_SUBMISSION.md`。旧1080p整包校验器依赖未选入的ABC/D证据，不能在精选包中替代以上入口。

`VERIFY_SUBMISSION.py` 绑定所有included文件SHA、原提交与树，清单自身不递归列自身哈希。通过表示文件完整、保存的证据身份一致，不代表重新完成了时序、仿真或上板验收。720p原gzip位流不能直接下载，新delivery提供无损解压的 `.sbit`；原压缩存储也完整保留。

## 重建边界与RAR

两套冻结包保留真实源输入、构建记录和约束，不承诺一条命令重建完全相同的物理实现。历史工作区／工具绝对路径仅为来源，应重定位并使用相容PDS后重新验证。厂商安装、许可证、安装目录原语库和模拟器不随包发布。

720p历史生成工具副本在 `source/generator-inputs/distortion/tools/`；离线包校验不需要根 `distortion/tools`。报告补充模型和投影比较没有集成进两套位流，不能当作第三套部署版本。

父流程另行创建真正RAR、运行 `Rar.exe t`、解压重跑校验，并硬检查 **最终RAR小于200,000,000字节**。不按未压缩大小删除清单必要证据，也不把ZIP改后缀充作RAR。

导出工具自身测试：

```text
python -B -m unittest discover -s tools/tests -p test_package_submission.py -v
```
