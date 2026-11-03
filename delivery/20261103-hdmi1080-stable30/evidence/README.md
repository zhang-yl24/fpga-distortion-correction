# 证据读取顺序

- `board/summary.json` 与四个阶段回执：本次 `8c73465e` 原生构建结果，未上板。
- `engine/report.json`：最终读回寄存版完整 1080p 引擎验证，2,831,328 周期；同目录日志和配置保留实际运行记录。
- `scheduler/README.md`：冻结的三源槽调度、DMA、共享写链路和真实小帧整机验证。该目录的 MANIFEST 绑定冻结内容。
- `writer-ab.json`：最终寄存写数据模块的 25 案例验证。
- `readstage/validated/results.json`：最终读回寄存模块的汇总验证；同目录树中早期运行记录用于追溯，最终判定以 validated 记录和其源哈希为准。
- `cache/run-a/results.json` 与 `cache/supplement/run-a/results.json`：缓存周期等价、边界与故障验证。
- `constraints/`：厂商约束匹配与最终 33 项审计；独立去组诊断未成功清除 ADF 内嵌时钟组，其失败记录保留，未用于证明时序通过。
- `integration-source-binding.json`：最终源码、编译闭包和旧封存版本保护检查。

历史实验脚本和回执保留生成时的路径及依赖位置；将文件复制到其他电脑后，历史绝对路径不自动有效。可移植的标准库核验由候选 `tools/verify_candidate.py` 执行；完整引擎复现入口为 `tools/run_engine_benchmark.py`；完整原生工程由 prepare/rebuild 在当地路径重新生成。所有仿真数据均不代表板级实测 FPS 或端到端延迟。
