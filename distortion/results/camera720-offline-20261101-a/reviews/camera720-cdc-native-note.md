# 720p 当前原生 IO/CDC 结构与查询计划（2026-11-01）

仅新增两个工具和一个测试文件；未运行 PDS、未访问硬件、未改冻结源或其它代理工具。

最新有效入口：`tools/audit_camera720_io_cdc.py`（CLI `--export-receipt ... --output-dir ...`），调用 `tools/audit_camera720_monitor.py`。来源严格重绑 `camera720_inspect` 的实际 export 完成回执/ADF/构建/网表/全部本地传递依赖。

已实际读取本轮 `export-a/result.json`，完成结果为 `work/camera720-output/cdc-e/structure.json`。全部枚举组件检查通过；总体 `StructuralAuditPassed=false` / `PhysicalTimingAccepted=false` / `HardwareReleaseAllowed=false`，因为精确原生时序、复位范围、电气设置尚未验收。

## 当前实际数量

```json
{
  "ComponentChecksPassed": true,
  "NativeQueryPairs": 601,
  "Pins": 128,
  "InputDelayCells": 8,
  "InputDataFirstFFSinks": 164,
  "InputDataFirstDRMSinks": 8,
  "SyncPadFirstSinks": {
    "cam_vsync": 656,
    "cam_href": 644
  },
  "FIFOGrayBits": 34,
  "MonitorGrayBits": 64,
  "ApplicationScalarChains": 22,
  "MonitorScalarChains": 4,
  "SingleResetChains": 9,
  "ReplicatedResetTrees": 1,
  "ReplicatedResetSecondStages": 28,
  "HeldBits": 37,
  "HeldLogicalFirstSequentialPairs": 773,
  "NativeHandshakeConeProofComplete": true,
  "StructuralAuditPassed": false,
  "PhysicalTimingAccepted": false
}
```

## 原生查询

`cdc-e/query-00.tcl`、`query-01.tcl`、`query-02.tcl`、`query-03.tcl`分别含200、200、200、1条只读 `report_path_timing`；共601对原生source/endpoint，已由新inspect的受限Tcl语法校验。773对held逻辑source→first-sequential pair被保留在结构报告；原生同一物理父对象上的合并查询不等于丢弃逻辑位，核验结果时必须检查实际路径覆盖，不能只凭601个命令成功或top-N的正slack判通过。查询未执行。

当前查询涵盖34个FIFO Gray位、64个新monitor Gray位的源→stage1，非同BLE同步级间，以及全部held首寄存器消费者（含frame_age/比较器）。新monitor四条注册标量源→first-stage已列入最终计划；电气sites和全部外部输入时序仍需追加审查。所有数字结果只属于此次ADF。

## 新监测器结构

两帧准入新监测器的edge/vs/href共64条Gray链已按实际寄存器来源、时钟、复位、CE、级间逻辑和first-stage唯一功能扇出核对。原应用层scalar检查改为camera_configuration/initializer/bus新层级。应用复位按实际FF动态枚举，包含monitor p_reset/r_reset，没有沿用旧固定7链计数。

held_snapshot逻辑105位中实际存活37位：good_frames32位、healthy1位、fault4位。9..72是顶层未使用的诊断字段，4/6/7/8对应源故障码恒零位；不虚构105个物理位。正常已释放运行条件下，Boolean cofactor证明源端只在pending request时同拍更新held与ack，接收端在同步ack后增加settle周期、同拍捕获字段和ack_seen，新的request等待ack_seen且不在settle期发出。对reset重新断言/释放的电气与恢复/移除路径无验收主张。

source_fault被综合成active-low的source_fault_reg[0]存在标志：检查其SET/INIT=1，正常p_reset释放时故障低态不能自行变高，failed_sync第一D确为反相标志与r_reset相与。没有把这种检查说成所有数值故障码语义的形式等价证明。

## 关键解析修正

本次native比较器用I5_TO_LUT=FALSE，Z由CIN选择，不能把V_LUT6CARRY一律当普通六输入LUT。新工具按本机官方模型的选择器语义独立实现Z/Z5/COUT及常量/重复输入cofactor，Graph子类覆盖门控检查而不改旧Graph全局。模型参考为`arch/vendor/pango/verilog/bsim/V_LUT6CARRY.v`，SHA256 `aa7ca57e8ce35845b0d61b02358d4a546facc52be65ec1ca5e68fe37a8bdcf98`；仅记录来源/hash，不复制vendor代码。

旧cdc-a/b为调试失败，cdc-c只有206对且缺完整carry/CIN消费者，不是当前最终计划，不得用于完整验收；cdc-d覆盖该修正，最终cdc-e再加四条新monitor注册标量源→first-stage；所有前版都是历史记录。

## 测试

`tests/test_camera720_monitor.py`共13项CPU测试通过，包含缺失Gray位、错误来源、额外扇出、stage clock/reset不一致、常量/重复输入cofactor、active-low sticky故障、carry→CIN尾端的held消费者路径等。

## 新工具SHA256

- `tools/audit_camera720_io_cdc.py`: `48044ccc940c686fc4d96d2f8793cea68fecfa848d16283bb1a5b5e8dfd35ee7`
- `tools/audit_camera720_monitor.py`: `c450dfec452a69fa752e50830bc7e02a4a6db44bf28bd5c56ebc058561cf6a5c`
- `tests/test_camera720_monitor.py`: `33e136f82d3951657f8f8616e0bbbdad2ad299de4e906ff5c6aba8d56a3355af`

## 后续必须完成

1. 将601对查询绑定同一原生ADF并实际执行，逐角逐对检查源/端点、约束/报告覆盖及arrival；跨域路径不要求同步时钟setup解释，但仍需验证实际max-delay和source-period上界。
2. 新增monitor四标量源→first-stage路径已列入查询，源/目标复位释放域及held异步reset路径仍需要明确scope；原有板层held mailbox协议仍需各自对应的物理约束检查。
3. 128pin FDC/PCF/route/export一致和八位1500ps结构通过；native electrical drive/slew、外部AC/clock实测及native sites查询尚未通过，不继承旧VGA的物理验收。
4. 本结构报告绑定原始build-b ADF；任何后续hold修路或reset例外派生ADF都必须重新导出并重新绑定，不能挪用该报告为新ADF签核。

最终cdc-e已实际完成，所有组件Passed=true，Errors=[]，601对查询；输入哈希前后稳定。原生查询并未由本代理执行。
