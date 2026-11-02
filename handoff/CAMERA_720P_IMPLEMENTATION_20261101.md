# 720p独立实现（2026-11-01，离线阶段成果）

任务顺序仍为：有效相机/处理分辨率1280×720并验收镜头矫正，然后在720p基础上优化帧率。HDMI IN暂停。当前开发板没有被本阶段访问，最后已确认的SRAM内容仍是640×480实际镜头矫正版；如用户告知断电，立即撤销该实时状态。

已验收VGA成果已推送到`origin/codex/camera-vga-calibrated`，远端HEAD已核对为`90f6e4a0f23aa253f098144a00a7c656897d04e9`，主成果提交`a4a84c352351d69703eeb369e502f3ffcfd11564`，未合并main。新720p代码和离线阶段证据独立提交至`codex/camera720-output`；代码入库不等于720p已验收或已上板。

## 新候选的范围

`board/camera720_transport_top.v`保留已验收DDR实例、四bank所有权、scatter4处理核、输入延迟和1080p30扫描；将有效输入/处理图像设为1280×720，画面居中，不放大VGA。新的`ov5640_current720_frontend`复用留存403动作ROM，检查完整2560字节×720行，至少两完整好帧后才允许启动。默认首个好帧宽限1秒；运行时丢失授权只停止新事务，不撤销已经释放的流水线共同复位。

当前`board/camera720-identity.vh`是精确单位映射，用来核验真实720p运输；**不是720p镜头校正参数，也不继承VGA光学验收**。CPU独立整数参考检查全部921600坐标逐一等于原像素位置，包含四边和角点；算术无溢出，最大radius Q22为2152802，小于8388608保护值。新模式的传感器裁剪与VGA不同，不能简单倍乘VGA的K就称完成校正。

RGB565一帧1843200字节、57600个256bit beat、460800个4字节UI地址单位。BANK_STRIDE继续为1048576个UI，即4MiB；四bank间隔足够。HDMI仍是1920×1080p30扫描，720图像位于有效画面的x320..1599、y180..899；扫描格式不是相机实际帧率。留存传感器模式在24MHz XVCLK假设下模型约15fps，42MHz PCLK；这些数值不是本次实测，不能声称720p已保持VGA约24fps。

## 已完成的离线验证

- `prepare_camera720_sensor.py`核对四份留存原文件SHA、403动作与ROM一致性，并验证新initializer只改模块名和include路径。6项CPU测试通过；旧生成器的proposal已缺失，因此只称留存源码受控移植。
- `run_camera720_sensor_sim.py`的9个RTL场景通过。真实`reg16_i2c`配合合成开漏寄存器模型；42/47.25MHz场景执行完整720行，验证两帧授权、停钟粘滞故障、短行拒绝。证据：`work/camera720-sensor-sim-20261101T041857527800Z-0b72f2/camera720-sensor-simulation.json`。
- `run_camera720_capture_sim.py`的`attempt-b`通过：四个完整好帧、3686400像素，两个源bank各两次，逐像素/beat/CRC独立核对；正常输入FIFO峰值14/64，坏行与已接收AW后DDR停顿导致的溢出均丢弃、排空并恢复。包含14201个背景结果写bursts；末burst相对UI地址460672。证据：`work/camera720-capture-sim/attempt-b/camera720-capture-simulation.json`。保留attempt-a的bench时间常量宽度失败记录，生产RTL未改。
- `run_camera720_control_sim.py`的`sim-a`通过：实际新top及warmup，8个启动、7个运行故障、17次复位、9次释放、4项LED及1项readiness抖动检查；配置完成而live授权未满足时保持关闭。传感器/处理/物理IP/输入延迟均为显式状态stub，不把此项称传感器或像素验证。
- `prepare_camera720_output.py`生成111项源码闭包，30个显式Verilog+1个IDF，74项展开的DDR源不重复加入，5个header；独立新FDC保留CAM2引脚及48MHz时钟预算。新monitor全部CDC还需自己的物理端点枚举/时序审计，不能套用旧VGA结果。
- `test_camera720_identity.py`的3项CPU检查通过，全部坐标和RGB565像素（包括最后一行/列的零权重越界邻点）不变。`test_camera720_output_prepare.py`的19项CPU检查通过，涵盖来源/计划/Tcl/编译副本漂移拒绝、模拟执行与超时处理；实际EDA不由这些测试执行。
- `run_camera720_output_sim.py`的`run-a`完整通过：生产四bank、非线性合成映射、reader/FIFO与74.25MHz实际1080p30扫描；三帧共2764800坐标和实际扫描像素完全匹配独立参考，CRC依次43B96F32/D35A9EF4/F2E7C5C1，零欠载/CRC不符，source/result bank各复用一次并最终排空。FIFO峰值512，并发处理/显示3003681周期；18项CPU负测通过。源在模型DDR预装，该项不含实时DVP或完整system控制器。
- `run_camera720_system_sim.py`的`attempt-c`通过：实际`camera_vga_video_system`全部控制与生产采集、处理、读写仲裁、FIFO、扫描共同执行，48MHz DVP/125MHz core/74.25MHz像素模型。两帧1843200个实际HDMI像素独立核对一致，源/结果/扫描/CPU的CRC均为DF5734A7、73964307；四个完整1080扫描、5760000个黑边样本、零欠载/CRC错误、最终排空。捕获/处理/显示重叠均非零，DDR读写争用91/13周期；完整运行1683.668秒，全部源码/fixture哈希不变。6项CPU负测通过。两帧使用不同bank，不宣称本次覆盖bank复用；独立采集/输出回归已覆盖。attempt-a主动停止、attempt-b错误xelab选项失败的原记录保留，不据其宣称通过。

合成传感器和DDR模型不是实板电气或吞吐证明。本次[可移植离线证据](../distortion/results/camera720-offline-20261101-a/README.md)封存报告、日志和哈希；大型ADF、网表及像素dump保留本机并明确列为本地引用。已冻结VGA源码、位流和manifest未改。

提交前统一复核新增CPU测试：196项及50项子测试全部通过，另外`handoff/audit-baselines.py`的四份原有基线闭包检查通过；JUnit原记录随阶段证据保存。CI新增`test_camera720_*.py`检查，不在GitHub Actions执行PDS或访问板卡。

## 后续关口

新构建入口静态复查及19项CPU测试已通过；PDS独立`build-b`已于北京时间12:33:51开始、12:45完成原生compile/synth/map/pnr/STA，执行回执成功且输入不变。构建计划SHA256为`3c1780236ff00448472e7bce2f1ce2b34e638d844fdc6c65f992aefa60dcf51d`，其prepare工具SHA为`dda5db3443830e1da06952e5f8c3c747b12730c7798f8ab1b43df7217a161376`；原始ADF SHA为`420127079b4123b3942edd45c1f5b725221a4e3b3a1b8a91a448d9526e6d0cbe`。`build-a`仅准备，之后因修正Headers元数据而失效，不能执行；不得改build-b输入。

首轮时序尚未通过：slow/fast hold最差−0.122/−0.199ns，各2项，均为`cam_vsync`到采集的两个数据采样分支；slow/fast recovery失败245/229项，当前均为DDR组，setup/removal/MPW均通过。独立`export-a`和`query-a`执行通过，未改变原始ADF。新monitor 1680条recovery细节无失败。

`reset-proof-a`按本次原生report动态重建两角各245逻辑检查、252原生变体，已由`reset-query-a`实际查询精确5源/127对端点，加上新export图连通与75份厂商原字节闭包完成scope审计。`reset-save-ready-a/stage-plan.json`的完整CPU准备通过，435项输入、5条精确命令/127对端点，计划SHA为`17cb7c96877912b02f7f7bc6697dc1e16c5265638da9a7de09095d8c834630fb`；**尚未执行应用**，未宣称时序通过。新增monitor不在DDR例外中。新应用/检查工具63项CPU测试通过。

`hold-route-a`原生保存成功，候选SHA为`2d7b577dc6bb0a42364f2e2bf6490d3003a5c8cbb4ebf21fd5057ce9b38c074e`，仅改_N50两末端分支。原始应用回执`ExecutionPassed=false`必须保留：严格原始token比较遇到PDS的CDBENTRY同父相邻条目重排，以及空FILEMAP 2占位删除。新增`camera720_derived_inspect.bind`独立限定核查这些非功能差异，逐项比较逻辑、placement、全部非目标route、CDB原始文本，另从同ADF原生query回执绑定的报告重推hold/setup测量以补原执行器只现哈希build报告的缺口。其`hold-export-a`已实际通过新进程STA/export，131.909秒、输入无漂移、ADF不变；slow/fast hold最差+0.061/+0.020ns均零失败，setup仍+0.148/+3.143ns零失败。DDR recovery仍245/229项失败，尚非整体时序通过。不能把原failed回执直接改写为通过，也不能允许任意FILETABLE或约束变化。

`cdc-e/structure.json`是原始ADF的最终结构枚举，全部组件通过、无Errors；34FIFO+64monitor Gray、22+4标量同步、9单复位链与1棵28末级复制树、128pads、8路输入delay。held实际存活37位、773逻辑source→首寄存器路径，折合601对原生查询；新LUT解析正确处理CIN/进位选择，13项CPU测试通过。`cdc-c/d`是不完整历史计划，不能用于最终验收。原始结构报告不代表修路/复位派生候选通过，最终派生候选仍需重新导出/绑定和原生覆盖核对。

新增`camera720_cdc_batch.py`按最终export重新枚举并将同源端点合并查询，16项CPU测试通过。`cdc-batch-original-b`仅对原始ADF完成CPU工具验证：601对、双角setup/hold或max/min共2404项、262条命令；没有执行原生查询，不是最终候选CDC通过。原始a因工具后续加严已过期。缺失path/corner/min证据会保持未通过，不能据top-N路径或仅max通过推断全覆盖。

## 下次接续

本次先提交/推送离线成果，不继续启动新PDS或访问板卡。使用上述规范绝对路径计划执行`camera720_reset_apply.py --stage-plan ... --execute`；输入若漂移先定位原因，不覆写原回执。应用成功后用`camera720_reset_inspect.py`重新export，`audit_camera720_reset_effect.py`比较相对于`hold-export-a`的十类时序、仅限复位的例外和路线不变。该效果工具的16项新CPU测试通过，尚无本候选实际通过报告。然后以新的最终export运行`camera720_cdc_batch.py`准备/执行/覆盖核验；不要复用原始ADF的结构报告作放行证明。

完成双角时序、输入延迟/引脚/CDC审查，准备可核对位流和SRAM计划后，再通知用户下载。执行器`Cleanup.Complete`只直接证明启动的父进程结束；本轮另于UTC05:19:45进行只读Win32_Process核查，PDS/仿真名称和记录的父子PID均无匹配，见封存的`camera720-process-exit-20261101.json`，不据父进程字段推断整个树状态。当前没有720p下载计划、没有可宣称已验收的720p位流，也没有720p镜头profile。真实720p模式画面确认和对应标定/独立留出验证完成后，才验收用户要求的720p矫正；之后测量该模式帧率并优化。
