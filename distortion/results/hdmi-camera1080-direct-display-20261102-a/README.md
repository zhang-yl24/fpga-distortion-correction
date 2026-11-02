# 新 HDMI 摄像头：1080p60 RGB888 稳定直通（已实屏验收）

本发布对应 `hdmi_camera_direct_top`，设备 PG2L100H-6IFBG676。2026-11-02 已下载易失 SRAM，DONE/器件 ID 核对通过，**Flash 未写**。用户在镜头前移动后确认“能看到，画面稳定”。

**分辨率与帧率：1920×1080 @ 60Hz 数字视频信号直通。** 输入约148.501MHz，2200像素/行、1125行/帧；输出连续转发输入 PCLK，RGB/HS/VS/DE 通过同一27位采样级，未经过 DDR、缩放、帧缓存或矫正。60Hz是源同步信号帧节拍，**没有独立测量摄像头光学唯一 FPS**，也未宣称颜色精度、光学全视场或外部AC签核完成。

- 已验收位流：[hdmi_camera_direct_top.sbit](candidate/hdmi_camera_direct_top.sbit)，3,791,112字节。
- 位流 SHA256：`33aca64d692778a9ba316828c32b9b816a0878de701e8e7fd4febcc703335156`。
- 最终 ADF SHA256：`2c88e0d98fee65326afbea25ae2282e0a182a7a0becbc5baf434da36dd84287f`。
- 源码：[`source/`](source/)；实际构建副本：[`compiled/`](compiled/)；原始来源映射与每个文件哈希：[`manifest.json`](manifest.json)。

## 离线核验，无需原电脑的 work 目录

```sh
python -B verify_bundle.py
```

仅需 Python 标准库；不调用 PDS/仿真器，不访问 UART/JTAG。核验所有包内文件及解压后原件哈希、原始引用映射、7份RTL与FDC副本、canonical top默认0到构建副本配置1的唯一改动、原始raw v2线包的19个有效守恒窗口、1080/60数字形状、控制仿真日志、最终十类双角STA摘要、位流头/身份、生成前gate、SRAM回执及用户实屏验收记录。

**历史回执的绝对路径只作不可变原件中的来源键。** 每个包内来源通过 `OriginIndex` 映射到按内容哈希存储的 gzip 原件；核验器不打开这些绝对路径。包内保留原始回执字节，不重写历史记录。重复证据只保存一份对象。

模型源码、PDS/仿真器/Python二进制、许可证和本机 `team-config.local.json` 不分发，仅在 `ExternalInputs` 记录角色及SHA256。仿真器生成可执行文件亦只留SHA；没有任何摄像头场景图片被上传。原始模拟器/EDA全流程复查需要合法安装及原厂环境；portable核验不冒称重新执行厂商物理模型或源到网表等价证明。

## 独立源码复现入口

在 ASCII 路径生成一份新的、闭合的7RTL工程：

```sh
python -B reproduce_build.py --output D:/fpga-repro/hdmi-direct-a
```

此命令只核验和准备文件，不运行工具。`build.tcl` 使用包内已编译副本，包含确切的输入150MHz包络、配置10MHz PLL、源时钟转发及69引脚；需要本机有许可的 PDS2023.2-SP3 build154097。另恢复相同哈希的 `accepted-final.adf` 并生成 `inspect-final.tcl`，供原生只读检查。

新的综合/布局布线须重新完成其自身引脚/复位/CDC/时序审查，不保证与历史位流逐字节相同；不会盲用历史放置相关的例外。`source/tools/` 是原始审查工具的冻结来源快照，其绝对work/SDK依赖用于历史来源说明；可移植入口是本目录两个脚本。

## 已记录验证与使用边界

- 实际top/sampler仿真：4006次bundle比较、4006次ready检查、576次相位扰动、8012个转发时钟边沿、6次共同复位、完整1,048,579参考周期冷启动。
- 69个实际引脚/电气、27路唯一输入采样、双角十类内部时序、路由/功能/FF位置保持、生成前全新时序gate通过。
- UART时序证据来自上一个同输入源raw v2：20包、19有效窗口，双沿守恒通过；direct版本本身不含UART遥测。
- 本版本只打通显示，未包含图像导出、新镜头标定或畸变矫正；旧DDR30Hz候选不纳入此次发布。
- 配置仅易失SRAM，掉电后需重新下载。复位/当前接线和上电状态应先核对，历史DONE不是当前板上状态或逐位配置回读。
