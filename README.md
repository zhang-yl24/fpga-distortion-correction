# FPGA 实时视频畸变矫正

## 最新实验测试入口（2026-11-13）

[1080p摄像头＋KEY1：三结果槽实验A，位流9abf8895＋专用slot2遥测](delivery/20261113-camera1080p60-key1-result3-a/README.md)。两包已生成并校验，供同学按步骤做SRAM实板测试；**尚未验证本位流达到60个新校正画面/秒**。请使用配套新profile，勿套用旧062工具，也勿把显示扫描Hz当新画面fps。页面列出完整SHA、测试/回传步骤、已知证据和必须有合法私有seed/PDS依赖的复现边界。

以下保留原有各历史版本说明与结果，不代表新实验的板测结论。

本项目基于紫光同创盘古100 Pro+开发板，对广角摄像头视频进行镜头畸变矫正，经HDMI实时显示。项目支持OV5640 DVP 720p和HDMI摄像头1080p两类输入，并配套采图、镜头标定、参数生成、RTL仿真与串口统计工具。最新HDMI优化位流已由团队成员在本地摄像头下载验证中达到**1080p 30 FPS**；两套已归档15 FPS工程提供完整的使用与校验入口。

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

最新1080p30方案采用前瞻预取缓存和DDR突发写回，技术说明、固定版本源码及位流入口见[1080p30方案说明](docs/HDMI1080_30FPS.md)。现场验证位流为`a266044d…`；其原始时序仍有4条DDR PHY setup负裕量。后续KEY1版本另有源码、位流与时序身份，分别列在方案说明中。

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
