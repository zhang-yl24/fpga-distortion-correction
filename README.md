# FPGA 实时视频畸变矫正

## 最新成果：1080p60 摄像头实板反馈（2026-11-13）

当前交付为三结果槽 A，位流 SHA256 `9abf8895212af90b5c55c7fcdc442c6a75cc425187be69a8511bbd16aff6663a`。团队在 11 月 13 日反馈“验证成功60帧”。本页据此记录为**团队报告的 1920×1080、60 个新校正画面/秒实板成功**；新的原始 UART、精确统计窗口和长期稳定性数据尚未随该反馈归档，不虚构小数帧率或测试时长。显示扫描 60 Hz 与新画面 60 FPS 仍是不同指标。

[当前位流、配套遥测、源码与复现入口](https://github.com/zhang-yl24/fpga-distortion-correction/blob/e160e100a272a75ab65945d99f097040eb6cd6de/delivery/20261113-camera1080p60-key1-result3-a/README.md)。保持 **HDMI 摄像头输入、KEY1 原始/校正切换、Brown 校正、Gamma OFF、旋转 0°**；不是电脑输入演示，不另加旋转。KEY1 已包含在实现中，详细按键稳定窗口仍以独立板测记录为准。

### 我们完成了什么

- **视频闭环：** 摄像头采集、DDR 源帧缓存、反向坐标映射、四邻域读取与双线性插值、结果帧缓存、HDMI 连续显示，以及 RAW/CORR 对照和串口统计。
- **算法与标定：** 从实拍棋盘格、镜头标定、定点参数/ROM生成到软件/RTL核对；当前使用固定相机的 rational Brown 径向及非零切向参数，不把旧 fisheye 标定成绩套给当前版本。完整帧边界用于参数与结果交接。
- **性能迭代：** 从 VGA、720p/1080p15 基线，到已板测1080p30，再到当前1080p60反馈；先后实现分块缓存、前瞻预取、DDR突发写回与流水处理。三结果槽解耦处理完成和显示交接，针对此前“三新一重”现象改进缓冲调度。此前44.96新帧/秒、约60.01Hz扫描的短测没有绑定完整位流SHA，不冒充本版的正式前后对照。
- **工程交付：** 源码与构建输入身份、位流SHA、时序/资源记录、专用slot2遥测解析、文件校验、重建依赖说明及版本导航。公开仓库并不包含全部厂商私有依赖；完整重建需要合法原始seed、PDS及许可证。

### 基础任务、提高任务与验收口径

| 项目 | 当前版本/项目成果 |
| --- | --- |
| 采集、缓存、显示 | 已形成连续摄像头视频闭环，当前1080p60由团队现场反馈确认 |
| 径向、切向畸变校正 | 当前Brown反向映射已实现；固定参数，不宣称任意参数文件可在运行时热加载 |
| 双线性重采样 | 已实现四邻域插值；不等于所有裁剪黑边均消除 |
| 动态处理及硬件加速 | 连续视频处理、流水线及DDR访问优化已实现；动态视频不等同于必须旋转 |
| 旋转 / Gamma增强 | 历史版本已有实现与分层验证，见下文；本次60帧位流旋转0°、Gamma关闭 |
| 定量验收 | 不能仅凭出图和60帧宣布全部评分项满分；本版端到端延时、MTF50/SFR、全视场直线指标及长稳窗口仍需对应实测 |

### 当前版本资源、时序与延时

以下绑定本次 A / `9abf8895` 的最终布线记录，不套用其他候选的综合结果：

| 项目 | 结果 |
| --- | --- |
| LUT | 31,709 / 66,600，47.61% |
| FF | 27,277 / 133,200，20.48% |
| APM（乘法/DSP资源） | 68 / 240，28.33% |
| DRM | 18K × 6 ＋ 36K × 36；物理grid 40 / 155，25.81%（原语数不直接等于物理grid） |
| 时钟与内部setup裕量 | core 125 MHz：+0.109 ns；pixel 148.5 MHz：+0.071 ns |
| 时序范围 | 建模约束下两角12类检查无失败；不扩大为完整外部IO、CDC和板级DDR保证 |
| 延时 | 尚无本位流摄像头到屏幕的端到端实测ms；60FPS的16.67ms帧周期不是总延时 |

资源和原始构建身份见交付包 `BUILD_IDENTITY.json`。不要把其他离板候选的资源节省、模拟DDR吞吐或处理周期当作本位流板测成绩。

## 历史扩展：旋转与 Gamma 确实做过

这些是项目积累，不是当前60帧位流已同时开启的功能：

| 版本/工作 | 实现与已保存证据 | 边界 |
| --- | --- | --- |
| 640×480历史链路（10月8–9日） | 动态角度控制、坐标映射、双线性插值、Gamma与HDMI闭环；12角度自动旋转短测约15.98新帧/秒、视频错误0；五组同源导出中校正与Gamma输出各307,200像素均与独立整数参考零差异 | 有限板测及数值一致性，不是1080p60旋转/Gamma验收，也不等于光学质量完全无失真 |
| 1080摄像头运行时旋转＋自适应Gamma源码候选（11月4日） | SGR1配置旋转，整帧锁存；Gamma编译启用后由完整帧判定自适应选曲线。实际摄像头ROM链路128×32短测6帧/24,576像素，含±13.37°；0°/Gamma关闭配对4096像素一致 | 小帧RTL和系统展开证据，不是完整1080实板验收；Gamma不是UART即时切换命令 |
| E2物理候选 | 上述功能路径独立构建，两角12项内部时序零违例，slow setup +0.016ns | 历史记录明确未经上板，不能借当前9abf的60帧反馈补成E2板测成功 |

证据入口：[VGA成果记录](https://github.com/zhang-yl24/fpga-distortion-correction/blob/6f837343f4044c91e2e0f14482d7a715ea87f562/distortion/output/project/成果记录.md) · [运行时旋转＋自适应Gamma源码及短测](https://github.com/zhang-yl24/fpga-distortion-correction/blob/1b9727e31f690a2598ab51cdb27ba645c0d5eda5/delivery/20261103-hdmi1080-demo-source/runtime-camera/20261104-a/README.md) · [E2时序与验证边界](https://github.com/zhang-yl24/fpga-distortion-correction/blob/1b9727e31f690a2598ab51cdb27ba645c0d5eda5/delivery/20261103-hdmi1080-demo-source/runtime-camera/20261104-e2/README.md)。

## 历史基线与使用说明

以下保留此前各历史版本说明和结果，不替代上面的当前版本状态。

本项目基于紫光同创盘古100 Pro+开发板，对广角摄像头视频进行镜头畸变矫正，经HDMI实时显示。项目支持OV5640 DVP 720p和HDMI摄像头1080p两类输入，并配套采图、镜头标定、参数生成、RTL仿真与串口统计工具。此前HDMI优化位流已由团队成员在本地摄像头下载验证中达到**1080p 30 FPS**；两套已归档15 FPS工程提供完整的使用与校验入口。

[设计报告与演示材料](submission/README.md) · [版本与文件导航](docs/REPOSITORY_GUIDE.md) · [逐日分支开发记录](docs/DEVELOPMENT_HISTORY.md)

## 硬件与处理流程

- 开发平台：盘古100 Pro+（MES2L676-100HP），Logos2 PG2L100H-6IFBG676 FPGA，板载DDR3。
- 输入方式：OV5640经转接板接入CAM2 DVP接口，或第三方广角摄像头接入HDMI IN。
- 输出与调试：HDMI OUT连接显示器，JTAG下载，UART采图或接收运行统计；两套15 FPS交付支持KEY1切换原图／矫正、KEY0复位，30 FPS方案按专页的版本说明使用。

```text
摄像头 → DVP／HDMI输入前端 → DDR源帧缓存
                               ↓
显示器 ← HDMI扫描 ← 结果帧缓存 ← 坐标反向映射＋四邻域取数＋双线性插值

PC辅助流程：完整帧采图 → 棋盘格标定 → 镜头参数与定点表生成 → 软件／RTL核对
```

矫正采用输出坐标到源图坐标的反向映射，再对相邻四个像素做双线性插值。两套镜头使用独立标定参数；1080p15实现使用8×8分块访问、DDR直接填充缓存及双条带写回，1080p30路线采用前瞻预取缓存。完整帧边界负责参数生效与结果交接。

## 方案与验证结果

此前1080p30方案采用前瞻预取缓存和DDR突发写回，技术说明、固定版本源码及位流入口见[1080p30方案说明](docs/HDMI1080_30FPS.md)。现场验证位流为`a266044d…`；其原始时序仍有4条DDR PHY setup负裕量。后续KEY1版本另有源码、位流与时序身份，分别列在方案说明中。

以下两套15 FPS基线已整理为独立交付，均支持KEY1原图／矫正切换，可按后文完成校验与运行：

| 方案 | 输入与有效处理图像 | 新矫正画面帧率 | HDMI输出扫描 | 工程入口 |
| --- | --- | --- | --- | --- |
| OV5640 DVP | CAM2，1280×720 | 15 FPS；29秒窗口435帧 | 1920×1080、30 Hz；720p居中显示 | [720p15源码、位流与报告](delivery/20261104-camera720p15/README.md) |
| HDMI广角摄像头 | HDMI IN，1920×1080；对应板测输入约60 Hz | 15 FPS；599秒窗口8985帧 | 1920×1080、30 Hz | [1080p15 direct-fill源码、位流与报告](delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md) |

新矫正帧率统计实际更新的不同画面；HDMI刷新可能重复显示上一帧。上述结果分别绑定各自的位流与镜头档案。720p已有两帧RTL仿真处理耗时均值约14.09 ms；1080p15 direct-fill基线实板串口处理耗时采样均值约35.45 ms，测试条件不同，均不代表摄像头至显示器的端到端延迟。详细口径见[设计报告](submission/report/README.md)。

## 获取与校验

建议在较短的英文路径下克隆完整仓库。只核验交付文件需要Python 3.10或更新版本，不依赖PDS、串口或开发板。

```powershell
git -c core.longpaths=true clone https://github.com/zhang-yl24/fpga-distortion-correction.git
cd fpga-distortion-correction

python -B delivery/20261104-camera720p15/verify_selected.py
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/verify_selected.py
```

两条命令分别核对源码、位流、构建输入和保存的验证证据，成功时返回通过结果。若使用已导出的程序包，从包根目录按`START_HERE_SUBMISSION.md`执行校验；完整性校验不会重新编译或下载FPGA。

## 接线与运行

1. 选择输入方案：OV5640通过转接板连接CAM2；HDMI摄像头连接HDMI IN。将HDMI OUT连接显示器，并接好开发板电源与JTAG。
2. 运行上面的对应校验器，确认交付文件完整。
3. 在PDS Programmer中扫描JTAG器件，核对PG2L100H，选择下表对应的`.sbit`，通过JTAG配置到易失SRAM。安装环境与驱动以板卡、PDS配套说明为准。
4. 下载完成后查看画面。默认矫正模式，按KEY1切换原图／矫正，模式在完整帧边界后生效；KEY0复位。两套方案分开运行，使用各自的输入设备与标定参数。

| 方案 | 下载文件 | 位流SHA256前缀 |
| --- | --- | --- |
| OV5640 720p15 | [camera720_view_toggle_top.sbit](delivery/20261104-camera720p15/bitstream/camera720_view_toggle_top.sbit) | `0ca6d19bf074c73c` |
| HDMI 1080p15 | [hdmi_camera_fisheye_top.sbit](delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/bitstream/hdmi_camera_fisheye_top.sbit) | `aa21991374fbeb4a` |

完整SHA256与版本身份见各工程入口。已验证下载方式为SRAM配置，断电后需要重新下载；Flash自启动未作为这两套交付的使用方式验证。更换镜头或摄像头成像模式时，应重新标定并生成对应参数。

## 开发环境与重建

Python图像处理与辅助工具可按仓库依赖安装：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
```

需要调用本机EDA工具时，在尚无本地配置的情况下复制配置模板：

```powershell
Copy-Item team-config.example.json team-config.local.json
```

修改`team-config.local.json`中的Python、PDS、Vivado路径和串口号。示例安装路径仅供填写格式参考，具体版本以所选工程的构建记录为准。720p冻结实现记录使用PDS 2023.2-SP3；厂商软件、器件支持与许可证需要在本机安装。部分RTL仿真入口使用Vivado的`xvlog`、`xelab`和`xsim`。

两套正式工程保留了实际编译输入、约束、Tcl及实现报告。重建时从各自的冻结源码入口开始，重定位原脚本中的工具与工作目录，再执行布局布线、时序及功能验证：

- [720p生产源码与构建说明](delivery/20261104-camera720p15/source/README.md)
- [1080p生产源码、编译差异与重建说明](delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)

归档源码中保留历史绝对路径，尚未提供经验证的一键跨机器重建命令。新的实现结果需要自身的时序、源码身份和板测记录。

## 采图、标定与运行统计

采图程序从FPGA输入链路导出完整帧，经UART回传PC，检查尺寸与CRC并保存原始像素、PNG和元数据。标定使用棋盘角点估计镜头参数，再生成定点参数并与浮点参考核对。采图固件和实时矫正固件承担不同任务，应按对应工具与工程说明选择。

- [正式镜头参数](submission/parameters/LENS_CALIBRATION_PARAMETERS.json)
- [采图、标定、映射及验证设计](submission/report/README.md)
- [720p同版UART与板测归档](distortion/results/camera720-view-toggle-live-20261102-a/README.md)
- [1080p帧率统计与原始证据](delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)

串口端口应按本机设备指定，统计协议和解析器需与运行位流匹配。输入帧数、处理帧数、新显示帧数、重复扫描数分别统计，不能用显示器的60 Hz或30 Hz设置代替新矫正帧率。

## 目录说明

| 目录 | 内容 |
| --- | --- |
| `delivery/` | 各方案的冻结源码、位流、构建与交付说明；正式使用入口见上表 |
| `distortion/rtl/`、`distortion/board/` | RTL模块、板级顶层与约束 |
| `distortion/tools/`、`distortion/tests/` | 主机工具、仿真入口与检查程序 |
| `distortion/platform/`、`vendor/` | 必要厂商IP、平台资料与手册 |
| `distortion/results/` | 保存的仿真、实现与实板验证证据 |
| `submission/` | 设计报告、海报、镜头参数、实物照片和视频稿 |
| `docs/` | 使用导航与逐日分支开发记录 |
| `handoff/` | 详细交接与实验记录；按日期理解其中的阶段状态 |

[程序包导出说明](tools/SUBMISSION_PACKAGE.md)提供两套选定工程的文件筛选与校验方法。旧版本、独立候选、合并与回退过程统一见[开发历史](docs/DEVELOPMENT_HISTORY.md)，不作为当前运行版本说明。

## 许可与归属

厂商IP、配套资料与第三方引用保留其原有归属和许可。仓库目前未为全部工程另设统一开源许可证；PDS软件及本机许可证不随工程发布。
