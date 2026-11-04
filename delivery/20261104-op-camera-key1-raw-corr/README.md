# O/P 摄像头诊断基线：KEY1 原始／矫正画面切换源码增量

**本目录先交付源码，没有新的 KEY1 位流。原生综合／布局布线／STA／本版实板测试尚未完成，时序未知。a266 基线的 4 条 setup、WNS −0.032 ns 不代表本版结果。**

这是同一个 HDMI 输入的原始／矫正画面切换，不切换电脑与摄像头两个物理输入。基于先前 A2 首故障诊断源码；用户反馈 a266 诊断位流在同学摄像头现场测试成功，这不等于本版完成实板验证。

## 使用行为

- 上电默认 CORR（矫正）。KEY1 是 C23、低有效、3.3 V LVCMOS33、上拉；在 125 MHz core 域双触发同步，释放和按下各稳定 20 ms 后切换一次。按住不连发；复位时按住须先有效释放。
- 请求模式在现有 `source_valid && source_ready` 握手时锁定；已处理／扫描的帧继续旧模式，后续完整帧切换。LED6 表示请求 CORR=1／RAW=0，不表示已呈现模式。
- RAW 仍走恒等坐标、采样器、结果 DDR 写回、CRC 和扫描，是 RGB565 量化原始画面，不是 RGB888 直接旁路。本固定配置 Gamma OFF，RAW 忽略旋转。bank／mapper／cache／writer 功能逻辑未改。
- 输入资格、147000–150000 PCLK 窗口和故障保护保持原样。串口仍为原诊断 PGIQ0001；没有新增 SGA／SGT／PGSTAT02 或帧率／端到端延迟测量能力。

## 接入独立源码副本

父源码：[不可变 f8 交付](https://github.com/zhang-yl24/fpga-distortion-correction/tree/f8f58a161111ecbac3400d0629a5064d43c405d8/delivery/20261104-op-camera-input-diagnostics)。仅应用于此父版本。

1. 在父交付目录的独立副本根目录（含 native/），先执行 `git apply --check /path/to/KEY1_PORTABLE.patch`，再执行 `git apply /path/to/KEY1_PORTABLE.patch`。补丁只改顶层并新增控制器；本目录 native/ 同时提供最终便携文件。
2. 将 `native/source/rtl/experimental/camera720_view_control.v` 加入实际编译输入。顶层仍是 board1080_top。继承诊断 SystemVerilog 输入须用官方 `compile -verilog_standard SystemVerilog`，不能只凭文件扩展名。
3. 综合阶段导入 KEY1_ONLY.fdc 的单引脚属性；在匹配工程的实际完整 PCF 中合入 KEY1_ONLY.pcf 一行。两片段描述同一 C23，不是新时序例外。不要用片段替换完整 PCF；reset C22、DDR 电气要求不变，不增加宽泛 false path／clock group。
4. 保持父工程器件、其余约束、PLL、IP 与参数，另行完成原生构建、全角 STA 和实板验证。父交付不含厂商依赖，须有匹配的合法依赖才能重建。

公开顶层仅将原始 native 顶层两条 include 根路径改为相对路径。KEY1_DELTA_IDENTITY.json 分别记录原始与便携 SHA；补丁已在父便携文件上实际 check／apply，并与候选导出逐字节核对。原始含本机路径的 patch 未发布。

## 验证范围

官方 xsim 最小短测三项通过、7 个编译／展开／仿真阶段均 exit 0，输入 SHA 未变化，仿真子进程全部退出：

- 控制器：debounce=4/1，覆盖抖动、按住、复位、脉冲与边界。
- 实际 native core/cache/bilinear RAW 查询 32／输出 32，含 1920×1080 四角，outstall=15、ARstall=16；CORR/RAW 帧锁存与复位通过。
- 真实 bank 控制器：wait-ready／busy／pending／old-scan／grant-backpressure／repeat／reset，参数 ID、模式、CRC 与 lease 保持；该项替代 engine 完成输出，不是完整像素系统测试。

首轮因仿真 runner 缺 include 搜索路径而编译失败，保留失败记录；只修 include 搜索路径后完成上述复测，RTL 未改。

这些检查不覆盖新的全帧系统、原生时序、相机现场、长时稳定性或 60 个新矫正帧／秒。旧 a266 位流不含 KEY1；后续 KEY1 位流须以实际构建身份另交。

父 a266 SHA256：`a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`。旧源码和位流目录未变；现场回退使用操作者自己已验证的位流。

## 来源

控制器来自同学提交 [b3b296979c4bc7c6e2c4ebef1e61879611172e7f](https://github.com/zhang-yl24/fpga-distortion-correction/tree/b3b296979c4bc7c6e2c4ebef1e61879611172e7f)，Git blob `49c5c8e36cf397a2d25b210ecc83c94ada6b46f5`，SHA256 `6793037fdcf22cad71af36fff203f3ed85fe8b79c9a9dd86e0320bf49846e255`；C23 合同来自同提交 hdmi-camera-fisheye-c-internal.fdc。控制器测试来源为提交 14397de26605b0f0422e01aa87f9fa092b3ea5b9 的 blob d0f94646b2bb0f026ea769205d0fd1388deac23c。同学历史结果不替代本版验证。
