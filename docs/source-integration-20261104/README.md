# 第二阶段：源码接口与最小真实组合

本阶段源码审计参照 main `327ef108f48b467b8bbe5c4e67f9b503e4983b50`。它是第一阶段基线 `8f2a5b76` 的后继，只有 submission 报告变化，delivery/distortion 源树相同。既有 integration 归档保留其第一阶段身份；本阶段只加新目录，不改 main、现有板级工程、工作流或活动分支，也不恢复 PR28 的旧入口。

## 精确来源与可执行清单

| 路线 | 必须使用的来源/顶层 | 已绑定内容 | 不可混用项 |
|---|---|---|---|
| 同学 directfill | main327 的 `delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission`；`compiled-snapshots/board/hdmi_camera_fisheye_top.v` / `hdmi_camera_fisheye_top` | 110输入路径，22关键源哈希；实际 INPUT_TIMING_CONFIGURED=1 | 原 source top 参数0不是选中编译顶层；14397de研究不是此板版 |
| O/P原版 | demo `1b9727e3` / stable30-OP / `board1080_top` | 147 native=65项目+82依赖，另route/PCF形成66导出+83依赖 | 4MiB逻辑stride、source0/1、result2/3；Gamma0/rotation0/correction1 |
| runtime A/E2 | 同一demo的runtime-camera目录 / `board1080_top` | 各69项目、82 native依赖；E2原生开关1，与共享导出默认0有别 | 128MiB逻辑stride及地址位排列；不能因开关0就视为O/P原bit |
| 旧60候选 | `25015cf3` / `delivery/20261103-hdmi-camera-fisheye-60` / `hdmi_camera_fisheye_top` | 116输入聚合身份d931793d…；物理仍FAIL | source bank为2bit，逻辑2映射物理4；不能截成1bit或套同学四槽；不是scout-local-a |
| 当前KEY1/scout | 主任务未发布 | 只知道KEY1请求原图/校正切换 | 没有SHA、精确源清单或位流身份，本轮不读取活动构建目录、不推断实现或验收 |

完整参数、像素转换、DDR单位/地址、UART、KEY1、IP/约束、故障排空/复位、来源SHA/文件/模块/行号分别见 [peer契约](peer-source-contract.md)、[O/P契约](op-source-contract.md)、[旧60契约](published60-source-contract.md) 及相应JSON。

共同帧存格式是RGB565、每256bit beat含16像素、UI地址单位4B，但peer量化为round、O/P采集为截位，不能默默当成相同图像路径。peer/旧60的UART为PGHFPS02 v2/96B；O/P含SGA1/SGK1/PGSIG001和84B PGSTAT02诊断扩展，runtime另有36B SGR1；新first-loss诊断为84B PGIQ0001。协议、模式意义和身份校验必须按精确路线选择。

## KEY1：锁定的是处理接收，不是采集入队

peer selected `hdmi_camera_fisheye_bank_tile8.v` L64-65与O/P `lens1080_bank_core_geometry_bypass.v` L59-64/L104-105都在 `source_valid && source_ready` 的处理接收边沿锁模式及source id/bank。`source_commit` 是该事件的寄存回执；O/P发布top实际 `.FIXED_MODE(1)`，没有KEY1端口，不能根据选择器通用注释宣称已自动切换。

DMA head/tail只带bank/id/CRC/pixels，没有mode。等待队列中的旧采集帧在实际被处理接收时取得当前请求。请求在同一上升沿翻转时，非阻塞赋值使该次接收读旧值。随后engine/mapper/writer配置及结果/显示lease必须保持本帧一致。不能用当前请求位代替已显示mode；peer/旧60 UART无显示mode ACK，稳定请求窗口也可能仍含旧pending/front结果。

默认建议沿用现有“下一次处理接收生效”语义。若需求变成“采集时的模式随帧排队”，才需把mode显式加入head/tail、processing、result、display元数据，属于另一项架构变更。当前主任务KEY1候选发布前，不建立竞争版本。发布后只需补绑定其精确SHA/source-binding，再检查同拍切换、满队列、stall、fault/drain、reset和逐帧ID/param/mode，不需用户重新选择低层架构。

## 真正准备的新源码组合：独立DDR读返回单元

代码位于 [integration-units/ddr-read-return-20261104](../../integration-units/ddr-read-return-20261104/README.md)。这不是板级候选：3份RTL已经形成无厂商IP的源码闭包，包含2份精确已有模块和1份新纯连线wrapper；3份原始TB原样保留，新增wrapper专用派生TB。10份绑定文件及14/32/36端口静态检查通过，**尚未编译或仿真**。本机不启动EDA，云端Icarus由主任务独立验证。

- `ddr_read_return_register`：旧60 blob `504d127378dc7a2633fa916f54baf0408d3f9081`，SHA256 `bb106a1b03d30f041b0b38eba2a687bef7fb54afa457d06f833d57787fae3427`。
- `ddr_read_arbiter`：main327与O/P共同blob `dad2ea07876ad11cfeb15bca21a845d043eb639e`，SHA256 `59283dd5d5d292cf8dd6d1bff51b565c13357ce94bdead0d467421604c5f72be`。不是peer fill8r2实现。
- `integration_ddr_read_return_unit`：公共AR保持原连接并供raw owner guard观察；R(data256/valid/last/id4)整束过一拍后回原仲裁器。无AR门控/撤回、地址重排、CDC、RREADY、隐式reset或flush。

两块共用交易域clk/rst_n。failed只OR导出、fault按原inline bench以arbiter优先，独立两组故障也保留；busy只表示arbiter状态。父级仍须停新work、保留已发AR至handshake及已占用的事务epoch。guard fault为寄存粘滞信号，不是零周期release否决；同沿rawfault+lease release必须另做真实parent测试。此wrapper单独不能证明父级已经实现安全drain/lease/reset。

下一步先在云端编译wrapper并跑4个TB及同时双fault导出检查；再将通过的单元与某一精确发布parent绑定，做FIFO容量/descriptor/bank/CRC/整帧scoreboard和fault/reset/drain。只有组合回归通过，才谈完整native依赖、时钟/IO/CDC/RDC、双角STA、新BuildID位流及SRAM/回退验收。本轮不把任何旧候选的通过结论移给新单元。

## 同字节复用和真实冲突

peer/O/P写仲裁器blob同为 `424fd88d…`；generic main/O/P读仲裁器同为 `dad2ea07…`，但peer实际选的是fill8r2 `16d81dd2…`。同名 `hdmi1080_input_dma` 的peer `6d28f912…` 与O/P `736bcb4f…` 不同；旧60又扩为2bit bank/三源槽。peer writer为dualstripe，O/P同名文件实际声明capture_local/overlap；source top与compiled top也有绑定差别。不能通过glob或文件名覆盖解决。

旧60物理输入中10个main和5个O/P模块同SHA；19个RTL overlay与main/O/P各自不同，其中有纯属性变化也有实质架构变化。raw mapper与指定O/P profile mapper仅include根不同，并非缺握手。逐项源路径/模块/字节和归一化差异见 [完整模块矩阵](published60-module-comparison.json) 和peer JSON的hazards。

## 四类状态和剩余门禁

| 状态 | 本轮结论 |
|---|---|
| 已归档 | 第一阶段602文件身份保全；本阶段3路源码契约、完整来源和差异矩阵已形成 |
| 真正可构建且已由本轮编译证明 | 暂无新的板级组合达到此状态；已有历史构建/板测只归原精确身份。独立unit仅证明源码闭包和静态接线，云端编译待回执 |
| 仅设计建议 | KEY1按处理接收锁模式的复用计划、采集时mode方案、被动诊断wrapper/CDC/TX仲裁 |
| 缺少依赖/组合验证 | O/P83依赖在两份已审索引中仅匹配76，7项范围内未匹配，不等于全main缺7；peer110路径齐备仍需最终物理重建链；新unit HDL/parent/物理/板测、未发布KEY1与scout身份均待补 |

已有本轮检查：O/P66导出、A/E2各69项目绑定核验；A和E2的发布包离线verify通过（E2只做外部路径resolve兼容）；peer22关键源；旧60的55读取文件、23 overlay及116输入聚合身份核验；旧60 UART纯CPU27 passed、诊断CPU10项。它们不是本次新wrapper的HDL测试，也不代表摄像头或60帧上板成功。详细限制在各契约和unit VALIDATION.json。
