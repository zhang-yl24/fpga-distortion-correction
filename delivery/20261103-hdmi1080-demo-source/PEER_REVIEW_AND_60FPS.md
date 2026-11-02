# 同学最新代码审查与 1080p60 预算

本审查固定到 `main` 提交 `c81898c0fa16e1c2f67887468400663ffb09907f`；GitHub 仓库为 private，最新主线 push CI [41415634815](https://github.com/zhang-yl24/fpga-distortion-correction/actions/runs/41415634815) 成功。PR [#19](https://github.com/zhang-yl24/fpga-distortion-correction/pull/19)、[#20](https://github.com/zhang-yl24/fpga-distortion-correction/pull/20) 已合入，后者含 `ee45af47` 的可移植测试夹具修复；旧 PR #17 不是最新版本。审查不改变同学分支和冻结源码。

## 同学实际接口与成果

最新封存 top 为 `camera720_view_toggle_top`：`cam_pclk/cam_vsync/cam_href/cam_data[7:0]`，连接 CAM2、`ov5640_current720_frontend`，8bit DVP/RGB565；处理尺寸 `WIDTH=1280, HEIGHT=720`，输出扫描区域仍 1920×1080、74.25MHz/30Hz。输入前端检查每行 2560 字节、每帧 720 行。

该提交的交接记录为接受/处理/唯一输出 **15.0fps**，KEY1 原图/校正切换有实屏确认，非 1080p60 代码或结果。用户说新购 1080p60 摄像头是同学今天使用的设备；仓库当前实现只能证明上述模式，尚不能把设备标称能力、物理设备型号与实际 FPGA 输入模式视为同一结论。

若后续设备走 **HDMI OUT → FPGA HDMI IN**，应复用我们的 HDMI 接收路径并核 EDID/模式；若走 CAM2 DVP，应修改传感器模式、输入字节吞吐、尺寸和采样约束。两种接口不可直接互换。8bit RGB565 的 1080p60 最小有效字节速率为 **248.832MB/s，即至少 248.832MHz 字节时钟**，尚未含消隐；不能把旧 48MHz DVP 约束或 720p15 的证明套为 1080p60。

## 可利用的改动与限制

| 代码/方法 | 对我们有用的部分 | 集成条件 |
|---|---|---|
| `camera720_view_control.v` | 两级同步、去抖、长按一次事件、复位按住不误触发；22bit/20ms 计数无帧缓冲 | 可用于未来手动模式键；要新增主线端口/FDC/CDC 审计，不能在当前 top 直接按键 mux 像素 |
| `camera720-view-select.vh` | 模式只作为帧请求；mapper 在已有完整帧 handshake 锁存整组参数 | 原图身份参数是 720p 镜头/缩放专用；我们的 raw 已有坐标旁路，不能直接复制 720 常量 |
| `test_camera720_view_toggle_sim.py` / full-system runner | 处理中更改模式、待发布帧/重复扫描、反压、source/结果 ID 与逐像素独立 oracle | 改成 1920×1080、主线实际 Gamma/rotation/接口，保留独立参考；不能只改期望 CRC 或去掉断言 |
| `ee45af47` route fixture 修复 | 消除对 ignored work 中 serializer 的依赖，改成独立 fixture 并绑定 SHA，缺失/变更必须拒绝 | 已在 main，无需重复 cherry-pick；可复用其“源码+依赖完整绑定”的准备模式 |
| 当前源/双角/CDC/IO 分片核验工具 | 提供终态清单、漏项/重复查询和 source/ADF 绑定思路 | 同学 reset scope、hold 路由、130pin/2486cases 属于其 ADF，不能作为我们的 144pin/不同 DDR reset 签核 |
| `board1080_edid.py` 与 EDID bench | EDID 两块 checksum、DTD 像素时钟/active/blanking、其余控制寄存器/FSM 不变的审计 | 旧文件只生成 74.25MHz/1080p30；60 模式需新 profile、148.5MHz、CTA/DTD 一致和实际 RX 读回 |
| [历史 1080P 性能预算](../../handoff/BOARD1080_PERFORMANCE_BUDGET.md) | 已定位 writer 收集/写回空泡、cache 32 拍 scatter、单 lane 60fps 极小余量，避免重复 rowpipe 提帧误判 | 文内 30.53ms/32.76fps 是旧数字模型；只借用结构分析，不能写为今晚实板延迟/FPS |

本交付已利用同学“精确依赖闭包与派生编译副本”思路，加入可移植的源码校验/准备工具；未将其摄像头 top、镜头常量、reset 豁免或物理成绩强行套入 HDMI 主链。主工程师统一评审集成 RTL。

## 冻结 HDMI 源码重新核对后的 60fps 约束

1920×1080 为 2073600 像素/帧，RGB565 为 4147200 字节/帧。125MHz、60 新帧/秒预算只有 **2083333.333 个核心周期/帧**，单像素流水消耗 99.5328%，平均仅余 0.004694 周期/像素。

当前 `ddr_adaptive_result_writer_capture_local` 非 tiled 模式仍为 256 像素 COLLECT → 1 拍 FLUSH → 16 拍 DDR write。以零 AW/W 等待、首 beat 与 AW 同拍的最理想条件，8100 个 burst 至少 **2211300 周期（17.6904ms）/帧**，只看 writer 就不高于 **56.5278fps**，还未计最终 drain、cache miss、仲裁或其他等待。旧文 2203200 周期是未计这版 FLUSH 的保守下界；当前结构不能达到 60 个新帧/秒。

当前邻域 cache 已有 1 query/clk 快 hit 路径；miss 仍等待快路径排空并串行 SELECT/CHECK/AR/FILL/SCATTER/LOAD/PICK。每次 fill 8×256bit=256B，随后 32 拍 scatter。当前输出 writer 双缓冲只能消除部分空泡，cache 打包/预取/并行查询才可能继续缩短处理时间；不能仅将核心频率或 EDID 改为 60 作为完成。

60fps 的最低 capture 写、result 写、display 读总有效负载 **746.496MB/s**；假设源每像素仅读一次再加 **248.832MB/s**，共 **995.328MB/s**。实际 cache refill 重读、DDR 效率、仲裁与重复显示必须测；256bit×125MHz=4GB/s 只是用户口名义峰值，不等于物理 DDR 可用带宽。

接口也硬限在 30：top 的输入热身窗口接受 `73500..75000` PCLK 边沿，输出 PLL nominal 74.25MHz，2200×1125。新 60 模式需要 148.5MHz 输出、正确输入活动窗口/observer、EDID、FIFO 预算、FDC 与 RX/TX 外部 AC 核验，保留独立 30 回退配置。

建议主工程按独立候选推进：writer 双缓冲（保持不可撤销 AW/W、最后 drain/CRC、tag、fault/reset）；cache 32bit/更宽打包或预取（验证真实 DRM 推断和同步读 metadata）；若仍差距明显，设计多像素 lane，统一评估 mapper、双线性、Gamma、tag 和写回。所有性能改善先报同源离线实测周期，再报真实上板接受/处理/唯一显示 FPS。
