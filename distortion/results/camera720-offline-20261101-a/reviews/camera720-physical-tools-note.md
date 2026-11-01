# 720p独立只读物理检查工具（2026-11-01）

本子任务仅新增工具与CPU测试，未执行PDS、原生查询、复位例外应用、布局布线、位流或硬件操作。编写时build-b仍无execution-result.json，因此没有宣称本次720p原生检查通过。原VGA冻结文件未修改。

## 新文件

- `tools/camera720_inspect.py`：接受新`prepare_camera720_output`构建及`run_camera720_output_diagnostic`执行回执，支持受限只读query和带原工程上下文的功能网表export。默认只验证，只有`--execute`启动原生程序；外部时限120..300秒。
- `tools/audit_camera720_timing_inventory.py`：消费上项完整重绑定的result.json，盘点新top的双角十类时序及所有失败clock group；详细recovery记录按原生source/endpoint保留，包括新增monitor路径。它不生成或批准任何例外，也不声明详细路径覆盖完整。
- `tests/test_camera720_inspect.py`：22项CPU测试全部通过，涵盖来源/ADF/compiled/log漂移、伪造阶段、越权Tcl、额外报告、query dummy LF、export缺失原生placed网表、mock成功仍无硬件/时序权限、timeout与未知stage只传自有mock进程给cleanup、新monitor恢复失败不被旧DDR白名单隐藏。

新inspect是旧`run_camera_vga_calibrated_inspect.py`（SHA256 8d22beada2ac5a8d60390ff3740db06b044d23137dce326c2230956d330b41a2）的独立移植，不在运行时加载或改写旧inspect。改为新schema/top/prep/diagnostic；自带UTC函数，避免调用新prep没有的utc；dummy.v显式LF，修复历史Windows CRLF准备/验证不一致；增加build原生stdout阶段、命令和scope flags检查，以及可供下游CPU审计使用的`bind_receipt()`。

时序盘点工具仅调用`audit_ddr_final_timing.parse_summaries`和`path_record`两个通用语法函数，不调用其旧expected_paths/build，也不使用旧PAIRS、固定245总数或历史endpoint。helper自身及其import依赖通过SHA绑定。它的SummaryChecksAllMet只是报告表统计，TimingAccepted、HardwareReleaseAllowed、ConstraintsApplied均保持false。

## 下一步调用

先等待本次`work/camera720-output/build-b/execution-result.json`真实完成，核对ExecutionCompletedWithoutError、SourcesStable、ADF快照一致。随后对该build实际`place_route/camera720_transport_top_pnr.adf`计算SHA。

1. 用`camera720_inspect.py --plan <build-b的规范绝对plan.json路径> --source-adf <本次ADF规范绝对路径> --source-adf-sha256 <实际SHA> --name export-a --mode export --prepare-only`准备独立export。
2. 对生成`export-a/stage-plan.json`执行`--validate-only`，然后主代理可按已授权离线范围使用`--execute`。只有实际阶段为Report Timing、Generate Netlist，源码/原ADF不变且placed原生网表存在，才得到ExecutionPassed。
3. 初始monitor对象发现body已写入`work/camera720-output/monitor-discovery-query-a.txt`。它查询当前原生clock/port/monitor/reset pins及route dump，不假定未用诊断位一定存活。用相同工具`--name query-a --mode query --body <该body规范绝对路径>`准备。
4. 通过的export/query回执可传`audit_camera720_timing_inventory.py --receipt <result.json> --output <新720工作目录内JSON路径>`，只做CPU盘点。

固定query模板由`camera720_inspect.monitor_query_template()`生成。当前仅发现对象，尚未生成逐位Gray/held-bus/同步器级间/输入delay的精确timing查询或实际CDC通过结论。

## 故意未建立的权限链

尚未生成720p reset-apply或derived-inspection工具。原因是新增monitor恢复/移除路径与实际优化后的FF端点尚未读取；必须先按新native数据完整分类，并证明任何DDR例外与monitor逻辑分离。不能直接移植旧5源/127pair/245check或复用旧exception FDC。若后续采用旧DDR结构图算法，只允许top-header适配、实际endpoint动态枚举和新原生精确名查询；新增monitor不得被忽略。

完整IO/CDC、128pad/输入delay首采样点、复位图、布线前后不变/例外精确效果、fresh双角STA、位流与硬件下载权限仍待主代理后续处理。这里未声称这些阶段已完成。

测试命令：

```powershell
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s distortion/tests -p test_camera720_inspect.py -v
```

全部22测试通过，3.096秒。mock执行/假ADF仅用于CPU单元测试，临时目录在已验证720工作目录内清理，没有任何原生进程执行。

## 源码SHA256

- `tools/camera720_inspect.py`：`acf9e32ebc117585ed27126eb361e2235c83970fb3ec4d2bd210a6f4e5a9935e`
- `tools/audit_camera720_timing_inventory.py`：`38beefd1c93dfad535d52af0014a800e86eafeec11320a74c7496daf7b58fcc7`
- `tests/test_camera720_inspect.py`：`6ebf2794f60de6b9e4dd26323483ef0125432d09cf3209826a4a42742ed81e6e`

初始query SHA256：`dfb2a351ab631ea97e562fe66af05557b5a340c9a2bb8c2184f296887cc58295`。
