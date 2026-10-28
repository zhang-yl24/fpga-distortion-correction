# CAM2 guarded 原始采集候选的边界与接板检查

这是独立的 `raw_camera_capture_cam2_guarded` 候选。原 `raw_camera_capture_cam2_ref` 的 97 份来源与已有位流保留。相机仍是现有 OV5640 VGA/RGB565 初始化、CAM2 连接槽位；D5=AA23，UART RX=B24/TX=C24，921600 baud。CAM2/slot=2 不表示物理左眼、右眼或双目同步。集中常量为 `CAMERA_ID=0x43414d32`、`CAMERA_SLOT=2`、`GUARDED_BUILD_TAG=0x52473201`。

上电默认没有采集授权，只发送 PGSTAT02 状态。OPEN 仅在原始核心空闲、没有不可恢复的核心/银行所有权故障时建立非零会话；ADC 或相机初始化失败时可以 OPEN/QUERY 读取诊断，但不能 GRANT。GRANT 同时要求相机初始化成功、held sensor ID=0x5640 且未 failed、DDR ready、8 秒 warmup 完成、ADC 健康且新鲜。GRANT 真实进入 lease 后才 ACK；该 ACK 所在完整状态包的最后 stop bit 结束以前，不准入第一帧。

每次新 GRANT 限 1–3 帧、最多 24,000 ms 对应的 **125MHz 核心周期数**。QUERY、重复命令或主机失联不能续租。STOP、租约到期、帧预算用尽、温度无效/失败/陈旧/超限/告警只关闭新的帧请求，不在已接受的 DDR/UART 事务中途复位。`admitted_frames` 是当前 grant 的计数；`completed_frames` 是本次 FPGA 配置复位以来的全局累计，仅在完整原始包最后 stop bit 完成后递增。未导出完成的银行保持锁定，核心故障需要主机受控退出并恢复 idle。

温度复用已独立实测过的 27MHz 内部 ADC 读取来源。健康条件在 27MHz 寄存后才做单 bit 两级同步；多位 ADC 与 sensor ID/ACK/readback 信息经 held-bus request/ack 原子快照，约每 100ms 更新。准入还检查 held 快照本身 valid、未 failed、sample age<54,000,000 个 27MHz 周期、samples>=2、raw>>4=code、code=1913..2732、OT=0/alarm=0；core 必须在 125,000,000 个自身周期内收到新的快照。ADC 只是内部近似估计，不能证明已独立校准、器件热点温度或重负载热安全。

UART 以完整包为单位仲裁。原始帧从请求准入到 PGFRAME1 最后 stop bit 期间独占发送端；状态不能插进原始 payload。PGSTAT02 的 120B body 在开始时一次冻结，后接 CRC32-IEEE 和 `ST02`，最后 byte_done 后才释放。捕获阶段尚未输出任何原始字节的故障可以安全释放 UART 并发状态；已经发出部分原始包再发生故障则保持 UART 锁，主机必须按有限超时退出并恢复 idle，不能依靠在半包中插状态自救。

该租约与 core 的快照新鲜度检查均以 core 周期计时。core/DDR 时钟停转会使计时暂停、UART 可能静默；27MHz ADC 继续运行也不能构成独立 UART 监督器。时钟恢复不是新会话，也不保证先前待确认的 held bus 是新的墙钟测量。尚未实现独立墙钟看门狗、自动断电或降频。因此仍须主机有限总批次/超时、异常退出、finally 恢复已验证 heartbeat。数字仿真覆盖的是 **27MHz 源停止而 core 继续运行** 的失联检测，不代表所有双时钟失效场景或数小时无人值守已验收。

离线入口：先运行 `tools/prepare-guarded-camera-board.py` 绑定独立候选来源，再运行 `tools/run-guarded-board-sim.ps1`。`tools/build-guarded-camera-board.ps1` 默认只产生离线计划；显式 `-ExecuteBuild -SimulationEvidence <已通过报告>` 才运行有界 PDS 编译/布局布线/生成 SRAM 文件，脚本没有硬件或 Flash 操作。实际接板必须另行核对新位流来源、最终 after-hold-fix 时序、全部 129 个 routed ports、PGSTAT02 build tag/序号/CRC、sensor ID/初始化结果、fresh ADC、授权 ACK 与真实原始帧，退出后重新扫描确认 heartbeat DONE。仿真通过与离线时序通过都不等于本候选已经实板验收。
