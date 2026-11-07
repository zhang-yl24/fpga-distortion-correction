# 全文件联合清单

本目录盘点整理前的 **13 个固定头**，包括 5 条已归档交付、7 条保留工作线，以及旧整理快照。AA 使用最新复现补充 `87cf6ca4`；其余完整 SHA 见 [SUMMARY.json](SUMMARY.json)。这是历史盘点快照，不宣称包含本次新增的导航文件或未来提交。

- [PROJECT_FILES.csv](PROJECT_FILES.csv)：13,703 行，覆盖 13,683 个路径、8,835 个不同 blob。
- [SUMMARY.json](SUMMARY.json)：每个固定头的行数/逻辑字节、类别、重复族例子和范围限制。
- CSV 为 UTF-8、LF；3,307,768 字节，SHA256 `70c06e8b1943e36162f5c7107fdc93b18059a942cec3fcc34d5c3e7f3c4fea48`。

## 列的意思

- `path`：仓库相对路径，区分大小写。
- `blob_sha`、`size`：该文件版本的 Git 对象 SHA 和逻辑字节。
- `category`：按路径生成的导航类别，不是综合输入、许可或可删除判定。
- `duplicate_group`：同一 blob 出现在多个路径时填写其 SHA。
- `duplicate_path_count`：该 blob 在联合清单中不同路径的数量。
- `ref_ids`：分号分隔的快照 ID；通过 SUMMARY 的 per_ref 映射到完整提交。
- `modes`：观察到的 Git 模式；当前审计未出现 gitlink/子模块。

一个路径如在两个头对应不同 blob，保留两行，不把内容差异抹掉。相同 path/blob 横跨多个头则合并一行，以 ref_ids 保留归属。筛选包含 r13 的 ref_ids 可还原 main136 的 11,802 个文件；r11 为 AA87 的 11,926 个文件；r12 为 integration584 的 12,450 个文件。

使用 Python 3 运行 `python docs/file-inventory/verify_catalog.py`，可离线检查 CSV 哈希、行唯一性、每个头数量/大小、联合计数和重复族计数。它验证盘点清单自身的一致性，不代替从 GitHub 重取对象、源码审核、综合、STA 或板测。

## 不自动删除重复文件

联合逻辑字节约 1.706 GB，唯一 blob 逻辑字节约 1.465 GB；这些都不是 Git pack 下载量。Git 已按对象去重。冻结包中的副本可能分别受 manifest、相对路径、构建脚本、证据身份或许可绑定。当前无需额外核验即可删除/移动的既有文件白名单为空。

例如同版位流同时位于交付包和编译证据中、空 stderr 日志或不同构建目录中的 masks.mem，均不能仅因 blob 一样删除。详见 [项目脉络](../PROJECT_MAP.md) 与 [发布流程](../PUBLISHING.md)。

Git 标签保存可达 Git 对象，不补齐厂商 IP、私有输入、外部资产或工具安装。LFS 检查仅覆盖已列属性文件和标准尺寸指针候选，不断言所有历史或非标准指针均无 LFS。
