# KEY1 原始／矫正画面切换：位流与源码

**已增加真实生成的 KEY1 位流。内部两角六类 STA 在既定模型下均零违例，但本机 PC HDMI 本轮输入资格失败、业务未启动。此版作为诊断候选供同学摄像头现场验证，不能称稳定版、实体按键已验或 60 个新矫正帧／秒通过。**

[下载 KEY1 位流](bits/camera-op-key1-rawcorr-pgiq-internal-timing-closed.sbit) · [最小身份](bits/BIT_IDENTITY.json) · [12 项 STA 表](bits/STA_12_CHECKS.csv)

位流 3,791,112 字节，SHA256：
cf9fcf563f7487bafccf083f5ad83f7e94c18759beea3236187e32c8b2c66731

对应源码提交 7ec412b；native 150 输入绑定 SHA256 为 2b7f2e2ed904574b2367cc9e75abf1bec9e4720e5512903113a69ab81fbe67a6（仅不透明绑定值，不上传依赖清单）。最终 ADF SHA256：920a7ffc2828794920d13608e455277e4c8ceba031d0251da6e3f9f3765c0d61。PDS 2025.2 ADS / build 211867，PG2L100H-6FBG676；bitgen 2026-11-04 14:01:44→14:02:34（UTC+08:00），exit 0。

## 本轮 PC HDMI 实板结果

父线程唯一板操作者最终回执：184 个有效 PGIQ 包；PCLK 窗口 148352、RX/TX/DDR ready=1；good=0、bad=2348、last_pixels_per_line=1919、lines=1080、source/input fault=0x12、ref fault=0xC5，qualified=0、pipeline_release=0。**业务未启动，无法观察 RAW/CORR 切换。** first_valid／follow_valid 始终为 false，仅有 live 快照；这是 release 前的启动资格阻塞，不是运行后 A2 首故障复现。184 包 DecodeErrors 为空，UART 写入／ARM／SGT 均为 0。

14:07:26.398（UTC+08:00）已结束并恢复 golden、原显示设置，温度峰值 48.422℃、回退后 34.04–34.16℃；串口、UART 线程和自有 Job 均退出，脚本 exit 0。原始采集 SHA256 为 755a01366b5ff729b5075cf1c8fe14cbe1a0c24f2803eab4befa11fd52e34a5d；本包不上传 raw UART。最终采集回执 SHA256：39b4b508a50b4d7caec303692963b35856e7746865df81fba3eabba87737d252。

这不是摄像头或实体 KEY1 按压结果。PGIQ 不暴露模式或帧率，不能据它推断画面模式、新呈现率或端到端延迟。摄像头在同学处，仍需现场验证。故障精确原因在分析，不能把 1919 观测当作已修复问题。

## 两角六项 STA

单位 ns。原生报告身份见最小身份；本表汇总内部模型检查。

| Corner | Check | Failing endpoints | Worst slack |
|---|---|---:|---:|
| slow | setup | 0 | 0.009 |
| slow | hold | 0 | 0.070 |
| slow | recovery | 0 | 0.673 |
| slow | removal | 0 | 0.340 |
| slow | mpw | 0 | 0.035 |
| slow | skew | 0 | 0.223 |
| fast | setup | 0 | 2.586 |
| fast | hold | 0 | 0.045 |
| fast | recovery | 0 | 3.384 |
| fast | removal | 0 | 0.235 |
| fast | mpw | 0 | 0.035 |
| fast | skew | 0 | 0.240 |

厂商 IP 时钟分组排除了其覆盖的跨域检查；适用的 core↔divided PHY／同域仍检查。零报告不代表物理复位、外部 IO 或新增 KEY1 CDC 完整签核；+0.009 ns 不是宽裕余量。旧 a266 四条负裕量不是此新位流结果，本表也不是实板功能通过。

## 上板与回退

确认相同器件／引脚合同、供电、接口、温度和可用回退后，通过官方工具仅下载到 SRAM，不写 Flash。故障时停止并恢复操作者自己已验证的位流。旧 a266 原件不变，本目录不新增 golden。

串口 115200、PGIQ0001、84 字节，被动接收。使用父诊断交付 host/capture_runtime_diag.py 与 decode_runtime_diag.py；串口号按现场 CP210x 实际识别，在 SRAM 下载前打开，工具不发送命令。声明的 bit SHA 不能由串口自动验证。first_valid=0 是 live 状态，须同时看 qualified／release／sticky／计数，不能当作通过。

KEY1 切换同一 HDMI 的 RAW/CORR，不选择电脑／摄像头物理输入。原 KEY1_DELTA_IDENTITY.json 保留源码阶段历史；当前位流身份以 bits/BIT_IDENTITY.json 为准。

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

以上短测不覆盖完整像素系统、相机现场、实体 KEY1 或新矫正帧率。当前位流已另完成原生构建及下表模型内 STA；本机 PC 输入本轮未通过资格，不能称业务已运行。旧 a266 不含 KEY1。

父 a266 SHA256：`a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`。旧源码和位流目录未变；现场回退使用操作者自己已验证的位流。

## 来源

控制器来自同学提交 [b3b296979c4bc7c6e2c4ebef1e61879611172e7f](https://github.com/zhang-yl24/fpga-distortion-correction/tree/b3b296979c4bc7c6e2c4ebef1e61879611172e7f)，Git blob `49c5c8e36cf397a2d25b210ecc83c94ada6b46f5`，SHA256 `6793037fdcf22cad71af36fff203f3ed85fe8b79c9a9dd86e0320bf49846e255`；C23 合同来自同提交 hdmi-camera-fisheye-c-internal.fdc。控制器测试来源为提交 14397de26605b0f0422e01aa87f9fa092b3ea5b9 的 blob d0f94646b2bb0f026ea769205d0fd1388deac23c。同学历史结果不替代本版验证。
