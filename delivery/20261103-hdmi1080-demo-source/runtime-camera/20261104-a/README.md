# 摄像头运行时旋转＋自适应Gamma：离板源码候选

本交付是**独立功能候选**，不替换已板测O/P。实际摄像头fisheye ROM、Q512、macro64×16 writer和帧锁存链在128×32短仿真通过6帧/24,576像素；0°/Gamma关闭配对4096像素相同。完整1080运行时性能、物理最终时序、新bit、UART线波形、HDMI扫描与实板60fps均未验收。

## 功能和身份

- 顶层CAMERA_RUNTIME_GAMMA默认为0，保留旧路径。显式1选择HDMI_FISHEYE_PROFILE=2、允许SGR1旋转和编译启用自适应Gamma。
- Gamma不是UART命令可切换功能；原自适应算法在两次一致的完整帧判定后切曲线。SGR1只配置输出到输入旋转。
- 摄像头完整标定身份仍ed59f83e3cfbc77b，参数/ROM不改；opt-in静态基ID为708006b9，具体命令生成独立param_id。不得把该候选当成O/P bit99f8a734…支持了新命令。
- 既有36字节SGR1、128位held配置跨域，接受source边界后锁存到整帧；旧显示metadata仍属于旧帧。测试实际覆盖24705周期旧/新metadata交叠。
- 路由器检查Q30系数范围，但不证明phase/cos/sin一致或单位圆；离线camera_rotation_command.py负责生成一致系数，发送命令本身不代表板上确认。

## 已有真实短仿真

| 项目 | 结果 |
|---|---|
| 几何与真实链路 | 128×32；实际摄像头ROM、Q512、macro16 writer、DDR接口/背压与bank快照 |
| 运行时帧 | 6帧，24576像素逐项参考，单小帧engine4940周期 |
| 角度 | 0、+13.37、−13.37、−13.37、0、0度 |
| 自适应曲线 | 0、0、2、2、1、1，非手工UART Gamma命令 |
| CRC | fbdc28aa、3c58eb94、bf2b3a89、bf2b3a89、8d4463a3、8d4463a3 |
| 配对对照 | 原0°/Gamma关闭路径4096像素bit-exact |
| 协议范围 | 字节router＋held CDC；没有测试真实UART串行电气波形 |
| 系统集成 | 默认关闭及开启配置的实际系统展开通过；该项目仅elaboration，没有跑完整系统仿真 |

所有原阶段compile/elab/sim退出0且本轮Job结束。151项作者源码当前哈希全部匹配冻结SOURCE_CLOSURE，原闭包SHA **997f97a2fd804d7a9335ab5b0ddc8f01ad0622bf6ed5f53bda4cf600b18ed215**；原语义patch SHA **ef4470f3ac36182ce15566fdd8c71f279a95e3ad45dc4a8a0a3527d7f9e18e0d**。本页仅给去标识摘要与原件SHA，不改作者历史回执。

短测输入清单182项中当前run_short.py已被作者后来调整；保存的scripts/run_short.py.as_tested精确匹配当时输入SHA，其他当前输入匹配。发布不把后来runner冒充已执行版本。早先命令行长度失败、wrapper timescale失败保留为历史；不能抹去，也不能将它们当最终短测失败。此交付工程师没有重新运行HDL/EDA/硬件。

## 源码复用和依赖

151项作者闭包包含69项项目输入及82项未发布依赖。项目输入中58项复用同分支已冻结[O/P项目源码](../../stable30-OP/README.md)，11项实际增量放在delta/；其中包括运行时4个既有模块窄改动、两个控制模块和macro16上下文差异。不要只把4文件patch直接套在O/P后就称完整macro16候选。

SOURCE_BINDING逐项记录作者原SHA、导出SHA、复用引用及变换：绝对include仅重定位；部分复用文件仅CRLF→LF以匹配作者快照。未发布原vendor/PLL/IP约束和供应商控制文件，不重新授权原来源。prepare_sources.py必须取得82项**精确**合法依赖；不能靠同名旧文件替代。

在本目录运行：
~~~text
python -B verify_delivery.py
python -B scripts/camera_rotation_command.py --angle 13.37 --request-id 1
python -B prepare_sources.py --dependencies <合法native依赖根目录> --output <全新目录>
~~~
准备脚本只重建151项普通源码；不生成完整PDS项目，不编译/仿真、不打开串口。默认保持顶层开关0；明确加--enable-runtime才派生为1，记录新的准备身份。全部输出需要自身完整功能/物理验收。

编码器只输出或保存JSON/packet，不发送到设备；应使用camera_rotation_command.py读取本PROFILE_CONTRACT，避免底层通用编码器的旧Penn默认基ID。13.37度应生成param_id 91066c87；0度旋转命令派生ID为dfabf241。后续只有新会话/nonce、实际新帧ID与参数身份同时匹配，才可确认新配置生效。

## 主工程去重与物理边界

主工程明确将发布owner交给专职Git交付任务，主工不重复push。其E原生151项已做独立路径/开关接线，快照中的Map状态只写在SUMMARY；不会据Map启动/完成推导PNR/STA通过。作者历史handoff“尚未原生集成”属于短测结束时点，原件不改写；后续E属于另一阶段、顶层开关1。

D父候选最新内部slow setup仍3条/−0.052ns，未生成bit；不能把O/P +0.068ns借给这条macro16/runtime链。所有源时钟/复位/IO/CDC与实际UART/扫描仍需单独审查；已有8ns/0ns held-bundle规则和PAP属性不是本候选物理通过证据。

同学PR28仍为整合/入口工作，已含O/P源码，不重复上传原稳定版；PR25的双路模型仍物理FAIL，不能当实板60fps。当前只增量发布本功能候选源码、离线编码器和去标识证据，未上传厂商/生成原件、许可证、bit/ADF、原始UART或留出相机照片，不写main、不merge/approve PR。

基础/提高任务中的运行时旋转/Gamma有了这个小帧离板证据，但不等于整机/实板全项完成。光学质量、1080性能、延迟分布/E2E、长期稳定及60个新校正帧/s仍未完成。
