# Lane 描述符锁存与启动寄存

`physical-d` 的一条剩余核心路径从 `writer/front_failed` 经 `writer.frame_ready`、lane 就绪、组合 `begin_frame` 到 mapper 时钟使能，最差 −2.433 ns。运行期两项输出 FIFO 已切断 writer 到 sampler 的 ready 直通；此路径属于帧初始化。

lane 现在在合法描述符握手时锁存 `source_base`、`output_base`、`frame_id` 和 `cfg_corrected`，并置位寄存的 `begin_frame`。下一周期处于 START 状态，core/writer 在该周期末的时钟边沿初始化；再进入 SCAN，发送第一组坐标。帧初始化驱动从寄存器发出，不再包含布局检查和下游就绪的组合链。

上游可以在握手后立即改动描述符引脚。源帧读取、输出基址、标识和模式均使用锁存值；完成基址继续使用保留的输出基址。每帧增加一个初始化周期（125 MHz 时为 8 ns），像素算术与扫描顺序保持。

`frame_ready` 仅在 IDLE、两个子模块就绪、输出 FIFO 为空且未故障时有效。START 不发送坐标；共同复位可以取消待启动描述符。错误布局在握手时进入故障状态，初始化脉冲保持低。故障恢复沿用共同复位流程。

独立准备目录为 `D:/f60-work/lane-launch`，在 system-e 完成后应用共享源码。`tools/run_lane_fifo_checks.py` 的预检与应用后验证均通过，最新证据为 `evidence/lane-local-launch/`：

- 6 个完整帧，3,077 次 FIFO 像素/标签核对，3,083 组全局坐标与局部标签核对。
- 8 次初始化；每次合法握手后立即更改上游全部描述符字段，子模块保持原接受值。
- 2,036 个 FIFO 满周期、445 次满时弹出、2,626 次同时进出，遮罩和背压保持。
- 覆盖非空 FIFO 复位、START 阶段复位、错误布局、sticky fault 和复位后连续帧恢复；首坐标与初始化不重叠，完成基址/ID/FIFO 排空均核对。

lane SHA256：`78f2d0546b6c4574e124feb2f15baf91b92482c21ff7d1f503bce49f30aeab3a`。

单元验证采用可控 core/writer 替身，真实数据通路与争用由组合系统回归另行记录。新物理时序须绑定包含本文件的新工程；板卡帧率仍需实测。
